"""Integración y regresiones: API, datos dañados, sesiones y migración del prototipo."""

import io
import json
import sqlite3
import zipfile

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from cnc_guard.api import create_app
from cnc_guard.data import FEATURES, TARGET, download
from cnc_guard.registry import Registry, write_json
from cnc_guard.storage import Store
from cnc_guard.training import train


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    root = tmp_path_factory.mktemp("app")
    raw = root / "data" / "raw"
    raw.mkdir(parents=True)
    rng = np.random.default_rng(24)
    n = 500
    frame = pd.DataFrame({"UDI": np.arange(1, n + 1), "Type": np.resize(["L", "M", "H"], n),
                          "Air temperature [K]": rng.uniform(290, 320, n),
                          "Process temperature [K]": rng.uniform(325, 345, n),
                          "Rotational speed [rpm]": rng.uniform(1200, 2300, n),
                          "Torque [Nm]": rng.uniform(15, 70, n),
                          "Tool wear [min]": rng.uniform(0, 200, n),
                          TARGET: np.resize([0, 0, 0, 1], n)})
    csv = raw / "ai4i2020.csv"
    frame.to_csv(csv, index=False)
    registry = Registry(root / "artifacts")
    run = registry.new_run("ai4i")
    train(csv, run)
    registry.activate("ai4i", run)
    return root, frame


def test_api_sessions_notes_and_restart_preserve_history(trained):
    root, _frame = trained
    with TestClient(create_app(root, background=False)) as client:
        assert client.get("/api/v1/health").json()["models"]["ai4i"]["ready"]
        assert len(client.get("/api/v1/machines").json()) == 50
        created = client.post("/api/v1/sessions")
        assert created.status_code == 201, created.text
        session = created.json()
        machines = client.get("/api/v1/machines").json()
        assert sum(m["prediction"] is not None for m in machines) == 50
        assert all(m["source_udi"] >= 401 for m in machines)
        assert client.patch(f"/api/v1/sessions/{session['id']}", json={"action": "play"}).json()["state"] == "running"
        assert client.patch(f"/api/v1/sessions/{session['id']}", json={"action": "pause"}).json()["state"] == "paused"
        alerts = client.get("/api/v1/alerts").json()
        assert alerts
        alert_id = alerts[0]["id"]
        assert client.post(f"/api/v1/alerts/{alert_id}/acknowledge").status_code == 200
        note = "Revisar husillo; no parar automáticamente. ' ; --"
        assert client.post(f"/api/v1/alerts/{alert_id}/notes", json={"body": note}).status_code == 201
        updated = client.get("/api/v1/alerts").json()[0]
        assert updated["acknowledged_at"] and updated["notes"][0]["body"] == note
        old_count = len(client.get("/api/v1/machines/CNC-001/readings").json())
        assert client.post("/api/v1/sessions").status_code == 201
        assert len(client.get("/api/v1/sessions").json()) == 2
        assert client.get(f"/api/v1/machines?session_id={session['id']}").json() == machines
        assert len(client.get("/api/v1/machines/CNC-001/readings").json()) == old_count + 1
        assert client.patch(f"/api/v1/sessions/{session['id']}", json={"action": "play"}).status_code == 400
        assert client.get("/api/v1/evaluations/ai4i/download").headers["content-disposition"].startswith("attachment")


def payload():
    return {"product_type": "L", "air_temperature_k": 300.0,
            "process_temperature_k": 330.0, "rotational_speed_rpm": 1500.0,
            "torque_nm": 40.0, "tool_wear_min": 100.0}


@pytest.mark.parametrize("patch", [{"extra": 1}, {"product_type": "Z"},
                                  {"torque_nm": -1}, {"torque_nm": "40"}])
def test_api_strict_contract(trained, patch):
    with TestClient(create_app(trained[0], background=False)) as client:
        assert client.post("/api/v1/predictions/ai4i", json={**payload(), **patch}).status_code == 422


def test_api_unknown_and_invalid_origin(trained):
    with TestClient(create_app(trained[0], background=False)) as client:
        response = client.post("/api/v1/predictions/ai4i", json={**payload(), "torque_nm": 99999})
        assert response.status_code == 201
        assert response.json()["status"] == "UNKNOWN"
        assert response.json()["failure_score"] is None
        assert client.post("/api/v1/sessions", headers={"Origin": "https://untrusted.example"}).status_code == 403
        assert client.get("/api/v1/machines/INVALID/readings").status_code == 404
        assert client.post("/api/v1/alerts/999999/acknowledge").status_code == 404


def test_missing_model_and_web(tmp_path):
    with TestClient(create_app(tmp_path, background=False)) as client:
        assert client.post("/api/v1/predictions/ai4i", json=payload()).status_code == 503
        assert client.post("/api/v1/sessions").status_code == 503
        assert client.get("/api/v1/unknown").status_code == 404
        assert client.get("/").status_code == 200


def test_additive_legacy_migration(tmp_path):
    path = tmp_path / "history.sqlite3"
    legacy = {"created_at": "2026-01-01", "status": "NORMAL"}
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE predictions(id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, reading_json TEXT NOT NULL, result_json TEXT NOT NULL)")
        db.execute("INSERT INTO predictions VALUES (1,?,?,?)", ("2026-01-01", "{}", json.dumps(legacy)))
    store = Store(path)
    Store(path)
    assert store.predictions() == [{"id": 1, "dataset": "ai4i", "result": legacy}]


def test_incomplete_run_cannot_replace_active(trained):
    registry = Registry(trained[0] / "artifacts")
    before, _ = registry.resolve("ai4i")
    run = registry.new_run("ai4i")
    write_json(run / "report.json", {"model_version": "incomplete"})
    with pytest.raises(ValueError):
        registry.activate("ai4i", run)
    assert registry.resolve("ai4i")[0] == before


def test_modified_artifact_rejected(tmp_path):
    import joblib
    registry = Registry(tmp_path)
    run = registry.new_run("ai4i")
    joblib.dump({"value": 1}, run / "model.joblib")
    write_json(run / "report.json", {"model_version": "test"})
    registry.activate("ai4i", run)
    (run / "model.joblib").write_bytes(b"broken")
    with pytest.raises(ValueError, match="alterado"):
        registry.load("ai4i")


def test_download_interrupted_does_not_publish_file(tmp_path, monkeypatch):
    def interrupted(*args, **kwargs):
        raise TimeoutError("Interrupted")
    monkeypatch.setattr("urllib.request.urlopen", interrupted)
    destination = tmp_path / "data.csv"
    with pytest.raises(TimeoutError):
        download(destination)
    assert not destination.exists()


def test_download_invalid_csv_does_not_publish_file(tmp_path, monkeypatch):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("ai4i2020.csv", "wrong\n1")
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: io.BytesIO(stream.getvalue()))
    destination = tmp_path / "data.csv"
    with pytest.raises(ValueError):
        download(destination)
    assert not destination.exists()


def test_cached_csv_hash_verified(trained, tmp_path):
    frame = trained[1]
    path = tmp_path / "data.csv"
    frame.to_csv(path, index=False)
    download(path)
    frame.loc[0, FEATURES[1]] += 1
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="difiere"):
        download(path)
