"""Inferencia local y almacenamiento consultivo; sin operaciones OT."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import joblib
import pandas as pd

from cnc_guard.data import validate


def load_model(path: Path) -> dict:
    # joblib es formato ejecutable: cargar exclusivamente artefactos propios.
    return joblib.load(path)


def predict(bundle: dict, reading: dict) -> dict:
    frame = validate(pd.DataFrame([reading]))
    outside = [c for c, (low, high) in bundle["bounds"].items()
               if not low <= float(frame[c].iloc[0]) <= high]
    common = {"created_at": datetime.now(UTC).isoformat(),
              "model_version": bundle["version"], "synthetic_demo": True,
              "prediction_horizon": None, "rul": None}
    if outside:
        return {**common, "status": "UNKNOWN", "failure_score": None, "anomaly_score": None,
                "data_quality_status": "OUT_OF_TRAINING_RANGE",
                "explanation": f"Fuera del rango de entrenamiento: {', '.join(outside)}",
                "recommended_action": "Revisar lectura; el modelo se abstiene."}
    score = float(bundle["model"].predict_proba(frame)[0, 1])
    anomaly = float(-bundle["anomaly"].score_samples(frame)[0])
    failure_flag, anomaly_flag = score >= bundle["threshold"], anomaly >= bundle["anomaly_threshold"]
    status = "CRITICAL" if failure_flag else "WARNING" if anomaly_flag else "NORMAL"
    return {**common, "status": status, "failure_score": score, "anomaly_score": anomaly,
            "data_quality_status": "VALID",
            "explanation": f"Score {score:.3f} frente a umbral {bundle['threshold']:.3f}; "
                           f"anomalía {'alta' if anomaly_flag else 'baja'}. "
                           "Score sin calibrar; no es diagnóstico ni probabilidad futura.",
            "recommended_action": "Revisar con mantenimiento; confirmar sensores y condición."
            if status != "NORMAL" else "Continuar observación; NORMAL no garantiza ausencia de fallo."}


def save_prediction(db_path: Path, reading: dict, result: dict) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS predictions ("
                           "id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, "
                           "reading_json TEXT NOT NULL, result_json TEXT NOT NULL)")
        cursor = connection.execute(
            "INSERT INTO predictions (created_at, reading_json, result_json) VALUES (?, ?, ?)",
            (result["created_at"], json.dumps(reading), json.dumps(result)))
        return cursor.lastrowid


def history(db_path: Path) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT id, result_json FROM predictions ORDER BY id DESC LIMIT 100")
        return pd.DataFrame([{"id": i, **json.loads(r)} for i, r in rows])
