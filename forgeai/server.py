"""ForgeAI HTTP API (FastAPI) + static hosting of the React dashboard.

Every number the dashboard shows comes from artifacts on disk under runs/ (nothing is computed for display
only). Long factory runs execute in a background thread; the UI polls /api/jobs/{id} for log lines.

Run:  uvicorn forgeai.server:app --port 7860
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import shutil
import threading
import time
import traceback
import uuid
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import Config
from .docs import SUPPORTED, inventory, load_folder
from .intake import ask_questions
from .llm import Budget, LLMClient
from .pipeline import Factory
from .runner import Agent
from .schemas import AgentDefinition, Requirements

ROOT = Path(__file__).resolve().parent.parent
RUNS = Path(os.environ.get("FORGE_RUNS_DIR", ROOT / "runs"))
WORK = Path(os.environ.get("FORGE_WORK_DIR", ROOT / ".workspaces"))
WEB = ROOT / "web" / "dist"
MAX_UPLOAD_MB = 25
log = logging.getLogger("forgeai.server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="ForgeAI", version="1.0.0")
JOBS: dict[str, dict] = {}
AGENTS: dict[str, Agent] = {}
_NAME = re.compile(r"^[a-zA-Z0-9_\-]{1,60}$")


_OLLAMA_OK: dict = {}


def _ollama_up(url: str) -> bool:
    if url not in _OLLAMA_OK or time.time() - _OLLAMA_OK[url][1] > 30:
        try:
            import requests

            ok = requests.get(url.rstrip("/") + "/api/tags", timeout=0.8).status_code == 200
        except Exception:  # noqa: BLE001
            ok = False
        _OLLAMA_OK[url] = (ok, time.time())
    return _OLLAMA_OK[url][0]


def cfg() -> Config:
    """No usable model (no API key, Ollama not running) -> the deterministic mock, and the UI says so loudly."""
    c = Config.load(os.environ.get("FORGE_CONFIG"))
    if c.backend == "groq" and not os.environ.get("GROQ_API_KEY"):
        c.backend = "mock"
    elif c.backend == "openai" and not os.environ.get("OPENAI_API_KEY"):
        c.backend = "mock"
    elif c.backend == "ollama" and not _ollama_up(c.base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")):
        c.backend = "mock"
    return c


def mock_fn(c: Config):
    if c.backend == "mock":
        from .mock import mock_llm

        return mock_llm
    return None


def safe_name(name: str) -> str:
    if not _NAME.match(name or ""):
        raise HTTPException(400, "names may only contain letters, digits, - and _ (max 60)")
    return name


def run_dir(name: str) -> Path:
    d = RUNS / safe_name(name)
    if not (d / "agent_definition.json").exists():
        raise HTTPException(404, f"run '{name}' not found")
    return d


def jload(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def jlines(p: Path) -> list:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def run_summary(d: Path) -> dict:
    sc = jload(d / "scorecard.json", []) or []
    last = sc[-1]["scorecard"] if sc else {}
    first = sc[0]["scorecard"] if sc else {}
    best = max(sc, key=lambda x: x["scorecard"].get("dev_pass_rate") or 0)["scorecard"] if sc else {}
    defn = jload(d / "agent_definition.json", {})
    req = jload(d / "requirements.json", {})
    budget = jload(d / "budget.json", {})
    cfgd = jload(d / "config.json", {})
    return {
        "name": d.name,
        "agent_name": defn.get("name"),
        "agent_version": defn.get("version"),
        "description": defn.get("description"),
        "tools": [t["name"] for t in defn.get("tools", [])],
        "n_cases": last.get("n_cases"),
        "initial_pass_rate": first.get("pass_rate"),
        "final_pass_rate": best.get("pass_rate"),
        "dev_pass_rate": best.get("dev_pass_rate"),
        "holdout_pass_rate": best.get("holdout_pass_rate"),
        "iterations": max(0, len(sc) - 1),
        "flags": len(req.get("flags", [])),
        "conflicts": len(req.get("conflicts", [])),
        "ungroundable": req.get("ungroundable_topics", []),
        "tokens": budget.get("tokens_used"),
        "elapsed_s": budget.get("elapsed_seconds"),
        "model": cfgd.get("model"),
        "judge_model": cfgd.get("judge_model"),
        "backend": cfgd.get("backend"),
        "created": (d / "REPORT.md").stat().st_mtime if (d / "REPORT.md").exists() else None,
        "readiness": _readiness_line(d),
        "failures": best.get("failures_by_category", {}),
        "history": [{"iteration": x["iteration"], "dev": x["scorecard"].get("dev_pass_rate"), "holdout": x["scorecard"].get("holdout_pass_rate"),
                     "overall": x["scorecard"].get("pass_rate"), "decision": x.get("decision")} for x in sc],
    }


def _readiness_line(d: Path) -> str | None:
    rep = d / "REPORT.md"
    if not rep.exists():
        return None
    m = re.search(r"## Deployment readiness\s+\*\*(.+?)\*\*", rep.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def list_runs() -> list[Path]:
    if not RUNS.exists():
        return []
    # factory builds only: regression replays (no scorecard.json) are reports about a build, not builds
    return sorted([d for d in RUNS.iterdir() if (d / "agent_definition.json").exists() and (d / "scorecard.json").exists()],
                  key=lambda d: -(d / "agent_definition.json").stat().st_mtime)


# ------------------------------------------------------------------- overview
@app.get("/api/status")
def status():
    c = cfg()
    from .embeddings import get_embedder

    emb = get_embedder(c.embedding)
    return {
        "backend": c.backend,
        "model": c.model,
        "agent_model": c.agent_model or c.model,
        "judge_model": c.judge_model or c.model,
        "api_key_present": bool(os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")),
        "embedding": emb.describe() if emb else {"provider": "none"},
        "mock_mode": c.backend == "mock",
        "running_jobs": sum(1 for j in JOBS.values() if j["state"] == "running"),
    }


@app.get("/api/overview")
def overview():
    runs = [run_summary(d) for d in list_runs()]
    rated = [r for r in runs if r["final_pass_rate"] is not None]
    return {
        "agents_generated": len(runs),
        "successful_builds": len(rated),
        "avg_final_pass_rate": round(sum(r["final_pass_rate"] for r in rated) / len(rated), 3) if rated else None,
        "avg_initial_pass_rate": round(sum(r["initial_pass_rate"] or 0 for r in rated) / len(rated), 3) if rated else None,
        "total_eval_cases": sum(r["n_cases"] or 0 for r in runs),
        "total_iterations": sum(r["iterations"] for r in runs),
        "total_tokens": sum(r["tokens"] or 0 for r in runs),
        "runs": runs,
        "status": status(),
    }


@app.get("/api/runs")
def runs():
    return [run_summary(d) for d in list_runs()]


@app.get("/api/runs/{name}")
def run_detail(name: str):
    d = run_dir(name)
    return {
        "summary": run_summary(d),
        "brief": (d / "brief.txt").read_text(encoding="utf-8") if (d / "brief.txt").exists() else "",
        "requirements": jload(d / "requirements.json", {}),
        "definition": jload(d / "agent_definition.json", {}),
        "system_prompt": AgentDefinition.model_validate(jload(d / "agent_definition.json")).system_prompt,
        "scorecard": jload(d / "scorecard.json", []),
        "iteration_log": jload(d / "iteration_log.json", []),
        "tournament": jload(d / "tournament.json"),
        "judge_selftest": jload(d / "judge_selftest.json", {}),
        "budget": jload(d / "budget.json", {}),
        "config": jload(d / "config.json", {}),
        "eval_generation": jload(d / "eval_generation_log.json", {}),
        "tool_selection": jload(d / "tool_selection.json", {"tools_kept": jload(d / "agent_definition.json", {}).get("tools", []), "tools_rejected": []}),
        "registry": [s.describe() for s in __import__("forgeai.tools", fromlist=["REGISTRY"]).REGISTRY.values()],
        "stop_reason": (m.group(1) if (m := re.search(r"Loop stopped because: (.+?)\.?\n", (d / "REPORT.md").read_text(encoding="utf-8") if (d / "REPORT.md").exists() else "")) else None),
        "versions": sorted(int(m.group(1)) for p in d.glob("agent_definition.v*.json") if (m := re.search(r"v(\d+)", p.name))),
    }


@app.get("/api/runs/{name}/evalset")
def run_evalset(name: str):
    return jlines(run_dir(name) / "evalset.jsonl")


@app.get("/api/runs/{name}/results")
def run_results(name: str, iteration: int | None = None):
    d = run_dir(name)
    p = d / "final_results.jsonl" if iteration is None else d / "iterations" / f"iter_{iteration}_results.jsonl"
    if not p.exists():
        raise HTTPException(404, "no results for that iteration")
    return jlines(p)


@app.get("/api/runs/{name}/definition/{version}")
def run_definition_version(name: str, version: int):
    p = run_dir(name) / f"agent_definition.v{version}.json"
    if not p.exists():
        raise HTTPException(404, "no such version")
    return jload(p)


@app.get("/api/runs/{name}/file/{fname}")
def run_file(name: str, fname: str):
    d = run_dir(name)
    p = (d / fname).resolve()
    if d.resolve() not in p.parents or not p.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(p, filename=p.name)


@app.get("/api/runs/{name}/zip")
def run_zip(name: str):
    d = run_dir(name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in d.rglob("*"):
            if f.is_file() and ".cache" not in f.parts:
                z.write(f, f.relative_to(d))
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{name}.zip"'})


# ----------------------------------------------------------- create workflow
@app.post("/api/workspaces")
async def create_workspace(brief: str = Form(...), files: list[UploadFile] = File(...)):
    if len(brief.strip()) < 20:
        raise HTTPException(400, "the brief should be at least one full sentence")
    if not files:
        raise HTTPException(400, "upload at least one document")
    wid = uuid.uuid4().hex[:12]
    docs_dir = WORK / wid / "docs"
    docs_dir.mkdir(parents=True)
    total = 0
    for f in files:
        name = Path(f.filename or "").name
        if Path(name).suffix.lower() not in SUPPORTED:
            shutil.rmtree(WORK / wid, ignore_errors=True)
            raise HTTPException(400, f"unsupported file type: {name} (supported: {', '.join(sorted(SUPPORTED))})")
        data = await f.read()
        total += len(data)
        if total > MAX_UPLOAD_MB * 1024 * 1024:
            shutil.rmtree(WORK / wid, ignore_errors=True)
            raise HTTPException(413, f"uploads are limited to {MAX_UPLOAD_MB} MB")
        (docs_dir / name).write_bytes(data)
    (WORK / wid / "brief.txt").write_text(brief.strip(), encoding="utf-8")
    return _workspace(wid)


@app.post("/api/workspaces/demo/{demo}")
def demo_workspace(demo: str):
    src = ROOT / "demos" / safe_name(demo)
    if not (src / "brief.txt").exists():
        raise HTTPException(404, "no such demo")
    wid = uuid.uuid4().hex[:12]
    shutil.copytree(src / "docs", WORK / wid / "docs")
    shutil.copy(src / "brief.txt", WORK / wid / "brief.txt")
    return _workspace(wid)


def _ws(wid: str) -> Path:
    d = WORK / safe_name(wid)
    if not (d / "brief.txt").exists():
        raise HTTPException(404, "workspace not found")
    return d


def _workspace(wid: str) -> dict:
    d = _ws(wid)
    docs = load_folder(d / "docs")
    return {"id": wid, "brief": (d / "brief.txt").read_text(encoding="utf-8"), "inventory": inventory(docs),
            "requirements": jload(d / "requirements.json"), "questions": jload(d / "questions.json")}


@app.get("/api/workspaces/{wid}")
def get_workspace(wid: str):
    return _workspace(wid)


@app.post("/api/workspaces/{wid}/questions")
def workspace_questions(wid: str):
    d = _ws(wid)
    c = cfg()
    llm = LLMClient(c.backend, c.model, budget=Budget(), mock_fn=mock_fn(c), cache_dir=d / ".cache")
    try:
        qs = ask_questions((d / "brief.txt").read_text(encoding="utf-8"), load_folder(d / "docs"), llm)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"model call failed: {e}") from e
    (d / "questions.json").write_text(json.dumps(qs, indent=2), encoding="utf-8")
    return qs


class AnswersIn(BaseModel):
    answers: list[str]


def _start_job(kind: str, target, *args) -> str:
    jid = uuid.uuid4().hex[:12]
    job = {"id": jid, "kind": kind, "state": "running", "log": [], "result": None, "error": None, "started": time.time()}
    JOBS[jid] = job

    def logline(msg=""):
        for line in str(msg).splitlines() or [""]:
            job["log"].append(line)

    def work():
        try:
            job["result"] = target(logline, *args)
            job["state"] = "done"
        except Exception as e:  # noqa: BLE001
            job["state"] = "failed"
            job["error"] = str(e)
            logline("ERROR: " + str(e))
            log.error("job %s failed: %s", jid, traceback.format_exc())

    threading.Thread(target=work, daemon=True).start()
    return jid


@app.post("/api/workspaces/{wid}/requirements")
def workspace_requirements(wid: str, body: AnswersIn):
    d = _ws(wid)

    def task(logline):
        c = cfg()
        req = Factory(c, mock_fn=mock_fn(c), log=logline).requirements_only((d / "brief.txt").read_text(encoding="utf-8"), str(d / "docs"), body.answers)
        (d / "requirements.json").write_text(req.model_dump_json(indent=2), encoding="utf-8")
        return {"requirements": req.model_dump()}

    return {"job_id": _start_job("requirements", task)}


class BuildIn(BaseModel):
    run_name: str
    requirements: dict | None = None   # edited + approved requirements (human checkpoint)
    max_iterations: int = 3
    tournament: bool = True


@app.post("/api/workspaces/{wid}/build")
def workspace_build(wid: str, body: BuildIn):
    d = _ws(wid)
    name = safe_name(body.run_name)
    if any(j["state"] == "running" and j["kind"] == "build" for j in JOBS.values()):
        raise HTTPException(409, "a build is already running; wait for it to finish")
    req = None
    if body.requirements:
        try:
            req = Requirements.model_validate(body.requirements)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"requirements are not valid: {e}") from e
        req.approved, req.approval_note = True, "approved in the web UI by the requester"

    def task(logline):
        c = cfg()
        c.max_iterations = max(0, min(3, body.max_iterations))
        c.tournament = body.tournament
        c.interactive = False
        return Factory(c, mock_fn=mock_fn(c), log=logline).build(str(d / "brief.txt"), str(d / "docs"), str(RUNS / name), requirements=req)

    return {"job_id": _start_job("build", task), "run_name": name}


@app.get("/api/jobs/{jid}")
def job(jid: str, since: int = 0):
    j = JOBS.get(jid)
    if not j:
        raise HTTPException(404, "job not found")
    return {"id": jid, "state": j["state"], "kind": j["kind"], "log": j["log"][since:], "next": len(j["log"]),
            "result": j["result"] if j["state"] == "done" else None, "error": j["error"], "elapsed_s": round(time.time() - j["started"], 1)}


# ------------------------------------------------------------------ playground
class ChatIn(BaseModel):
    run: str | None = None
    baseline: str | None = None
    message: str
    history: list[list[str]] = []


@app.get("/api/agents")
def agents():
    out = [{"id": f"run:{r['name']}", "label": f"{r['agent_name']} (v{r['agent_version']})", "run": r["name"], "tools": r["tools"]} for r in runs()]
    for p in sorted((ROOT / "baseline").glob("*.json")):
        d = jload(p, {})
        out.append({"id": f"baseline:{p.stem}", "label": f"{d.get('name')} (hand written baseline)", "baseline": p.stem, "tools": [t["name"] for t in d.get("tools", [])]})
    return out


def _agent(run: str | None, baseline: str | None) -> Agent:
    key = f"{run}|{baseline}"
    if key not in AGENTS:
        c = cfg()
        llm = LLMClient(c.backend, c.agent_model or c.model, budget=Budget(max_tokens=10**9), mock_fn=mock_fn(c), temperature=0.0, role="agent",
                        cache_dir=Path(os.environ.get("FORGE_CACHE", ROOT / ".cache")))
        path = run_dir(run) / "agent_definition.json" if run else ROOT / "baseline" / f"{safe_name(baseline or '')}.json"
        if not path.exists():
            raise HTTPException(404, "agent not found")
        AGENTS[key] = Agent.from_file(path, llm)
    return AGENTS[key]


@app.post("/api/chat")
def chat(body: ChatIn):
    if not body.message.strip():
        raise HTTPException(400, "empty message")
    if len(body.message) > 2000:
        raise HTTPException(400, "message too long (max 2000 characters)")
    agent = _agent(body.run, body.baseline)
    hist = [(h[0], h[1]) for h in body.history[-4:] if len(h) == 2]
    try:
        r = agent.answer(body.message.strip(), hist)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"model call failed: {e}") from e
    return {**r.model_dump(exclude={"raw"}), "agent": {"name": agent.d.name, "version": agent.d.version, "tools": agent.d.tool_names(),
                                                      "retrieval": {k: agent.d.retrieval.get(k) for k in ("strategy", "top_k", "chunk_size")}}}


@app.exception_handler(Exception)
async def unhandled(_, exc):
    log.error("unhandled: %s", traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": f"internal error: {exc}"})


# ------------------------------------------------------------- static frontend
if WEB.exists():
    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = WEB / path
        if path and f.is_file() and WEB.resolve() in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(WEB / "index.html")
