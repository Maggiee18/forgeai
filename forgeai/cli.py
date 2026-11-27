"""ForgeAI command line.

  forgeai build  --brief brief.txt --docs folder/ --out runs/name [--answers answers.yaml] [--unattended] [--approve]
  forgeai chat   runs/name/agent_definition.json            (generic chat runner for ANY produced definition)
  forgeai eval   --definition some_agent.json --run runs/name --name human_baseline
  forgeai regress --old-run runs/name --docs changed_folder/ --out runs/name_regression
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Config
from .llm import Budget, LLMClient
from .pipeline import Factory
from .runner import Agent


def _common(p):
    p.add_argument("--config", default=None, help="path to forgeai.yaml")
    p.add_argument("--backend", choices=["ollama", "groq", "openai", "mock"])
    p.add_argument("--model")
    p.add_argument("--judge-model")
    p.add_argument("--agent-model")
    p.add_argument("--base-url")


def _cfg(a, **extra) -> Config:
    return Config.load(a.config, backend=a.backend, model=a.model, judge_model=a.judge_model, agent_model=a.agent_model, base_url=a.base_url, **extra)


def _mock_fn(cfg):
    if cfg.backend == "mock":
        from .mock import mock_llm

        return mock_llm
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(prog="forgeai", description="The agent that builds agents.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="run the factory end to end")
    _common(b)
    b.add_argument("--brief", required=True)
    b.add_argument("--docs", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--answers", help="YAML file with pre-recorded answers to the intake questions")
    b.add_argument("--unattended", action="store_true", help="never prompt; unanswered intake questions use recorded assumptions")
    b.add_argument("--approve", action="store_true", help="human checkpoint: approve/edit requirements before generation")
    b.add_argument("--iterations", type=int)
    b.add_argument("--max-tokens", type=int)
    b.add_argument("--no-tournament", action="store_true")

    c = sub.add_parser("chat", help="chat with a produced agent definition")
    _common(c)
    c.add_argument("definition")
    c.add_argument("--docs", help="override the documents folder")
    c.add_argument("--show-sources", action="store_true")

    e = sub.add_parser("eval", help="score any agent definition against a run's eval set")
    _common(e)
    e.add_argument("--definition", required=True)
    e.add_argument("--run", required=True)
    e.add_argument("--name", default="external")
    e.add_argument("--docs")

    r = sub.add_parser("regress", help="documents changed: replay the old eval set against a regenerated agent")
    _common(r)
    r.add_argument("--old-run", required=True)
    r.add_argument("--docs", required=True)
    r.add_argument("--out", required=True)

    a = ap.parse_args(argv)

    if a.cmd == "build":
        cfg = _cfg(a, answers_file=a.answers, max_iterations=a.iterations, max_tokens=a.max_tokens)
        if a.unattended:
            cfg.interactive = False
        if a.approve:
            cfg.human_checkpoint = True
        if a.no_tournament:
            cfg.tournament = False
        out = Factory(cfg, mock_fn=_mock_fn(cfg)).build(a.brief, a.docs, a.out)
        print(json.dumps(out["scorecard"], indent=2))
        return 0

    if a.cmd == "chat":
        cfg = _cfg(a)
        llm = LLMClient(cfg.backend, cfg.agent_model or cfg.model, budget=Budget(max_tokens=10**9), base_url=cfg.base_url, api_key=cfg.api_key, mock_fn=_mock_fn(cfg), temperature=0.0, role="agent")
        agent = Agent.from_file(a.definition, llm, docs_folder=a.docs)
        print(f"\n{agent.d.name} (v{agent.d.version}) · {len(agent.docs)} documents · tools: {agent.d.tool_names() or 'none'}")
        print("Type a question. 'exit' to quit, '/sources' to toggle sources.\n")
        show = a.show_sources
        history: list[tuple[str, str]] = []
        while True:
            try:
                q = input("you > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not q:
                continue
            if q.lower() in ("exit", "quit"):
                break
            if q == "/sources":
                show = not show
                continue
            resp = agent.answer(q, history)
            tag = " [refused]" if resp.refused else ""
            print(f"\nagent{tag} > {resp.answer}")
            if resp.citations:
                print(f"   sources: {', '.join(resp.citations)}")
            if resp.tool_calls:
                for t in resp.tool_calls:
                    print(f"   tool: {t.get('tool')}({t.get('args')}) -> {str(t.get('result', t.get('error')))[:160]}")
            if show:
                for r in resp.retrieved:
                    print(f"   retrieved {r['chunk_id']} ({r['score']})")
            if not resp.contract_ok:
                print(f"   (contract warnings: {resp.contract_errors})")
            print()
            history.append((q, resp.answer))
        return 0

    if a.cmd == "eval":
        cfg = _cfg(a)
        out = Factory(cfg, mock_fn=_mock_fn(cfg)).evaluate_definition(a.definition, a.run, a.name, a.docs)
        print(json.dumps(out["scorecard"], indent=2))
        return 0

    if a.cmd == "regress":
        cfg = _cfg(a)
        out = Factory(cfg, mock_fn=_mock_fn(cfg)).regress(a.old_run, a.docs, a.out)
        print(json.dumps({"old_pass_rate": out["old_pass_rate"], "regenerated_pass_rate": out["regenerated"]["pass_rate"],
                          "replayed_pass_rate": out["replayed"]["pass_rate"], "document_changes": len(out["document_changes"]),
                          "untested_changes": sum(1 for c in out["document_changes"] if not c["covered_by"])}, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
