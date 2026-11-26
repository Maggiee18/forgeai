"""API tests: the full create -> requirements -> build -> chat flow over HTTP, on the mock backend."""
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("FORGE_WORK_DIR", str(tmp_path / "ws"))
    monkeypatch.setenv("FORGE_CACHE", str(tmp_path / "cache"))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # no forgeai.yaml here -> defaults; no key -> mock mode
    import importlib

    import forgeai.server as srv

    importlib.reload(srv)
    from fastapi.testclient import TestClient

    return TestClient(srv.app)


def _wait(client, jid, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/jobs/{jid}").json()
        if j["state"] != "running":
            return j
        time.sleep(0.3)
    raise AssertionError("job timed out")


def test_status_reports_mock_mode_without_key(client):
    s = client.get("/api/status").json()
    assert s["mock_mode"] is True and s["api_key_present"] is False


def test_upload_validation(client):
    r = client.post("/api/workspaces", data={"brief": "short"}, files=[("files", ("a.txt", b"x"))])
    assert r.status_code == 400
    r = client.post("/api/workspaces", data={"brief": "An assistant that answers questions about our policies."}, files=[("files", ("evil.exe", b"x"))])
    assert r.status_code == 400 and "unsupported" in r.json()["detail"]


def test_full_flow_with_human_checkpoint(client):
    files = [("files", (p.name, p.read_bytes())) for p in sorted((ROOT / "demos/hr_policy/docs").iterdir())]
    ws = client.post("/api/workspaces", data={"brief": (ROOT / "demos/hr_policy/brief.txt").read_text()}, files=files).json()
    assert len(ws["inventory"]) == 3
    qs = client.post(f"/api/workspaces/{ws['id']}/questions").json()
    assert 1 <= len(qs) <= 5
    job = _wait(client, client.post(f"/api/workspaces/{ws['id']}/requirements", json={"answers": [q["default_answer"] for q in qs]}).json()["job_id"])
    assert job["state"] == "done", job
    req = job["result"]["requirements"]
    req["tone"] = "Edited by the requester: warm and brief."          # human edit at the checkpoint
    b = client.post(f"/api/workspaces/{ws['id']}/build", json={"run_name": "api_test", "requirements": req, "max_iterations": 1, "tournament": False}).json()
    job = _wait(client, b["job_id"], timeout=300)
    assert job["state"] == "done", job["error"]
    detail = client.get("/api/runs/api_test").json()
    assert detail["requirements"]["tone"].startswith("Edited by the requester")
    assert detail["requirements"]["approved"] is True
    assert len(client.get("/api/runs/api_test/evalset").json()) >= 20
    assert client.get("/api/overview").json()["agents_generated"] == 1
    r = client.post("/api/chat", json={"run": "api_test", "message": "What is the capital of France?"}).json()
    assert r["refused"] is True
    assert client.get("/api/runs/api_test/file/../../secret").status_code == 404
    assert client.get("/api/runs/api_test/zip").status_code == 200
