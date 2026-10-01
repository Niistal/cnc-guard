"""Pruebas de leakage, contrato, abstención, persistencia y ejecución completa."""

import json

import numpy as np
import pandas as pd
import pytest

from cnc_guard.data import FEATURES, FORBIDDEN, TARGET, split_ordered, validate
from cnc_guard.inference import history, load_model, predict, save_prediction
from cnc_guard.training import train


@pytest.fixture
def frame():
    # Fixture artificial de prueba; nunca se usa como evidencia del dataset UCI.
    n = 300
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "UDI": np.arange(1, n + 1), "Type": np.resize(["L", "M", "H"], n),
        "Air temperature [K]": rng.uniform(295, 305, n),
        "Process temperature [K]": rng.uniform(305, 315, n),
        "Rotational speed [rpm]": rng.integers(1200, 2000, n),
        "Torque [Nm]": rng.uniform(20, 70, n), "Tool wear [min]": rng.integers(0, 200, n),
        TARGET: np.resize([0, 0, 0, 0, 1], n), "TWF": np.ones(n),
    })


def test_split_order_and_no_overlap(frame):
    parts = split_ordered(frame)
    assert [len(p) for p in parts] == [180, 60, 60]
    assert parts[0].UDI.max() < parts[1].UDI.min() < parts[2].UDI.min()
    assert set(parts[0].UDI).isdisjoint(parts[2].UDI)


def test_labels_never_enter_features(frame):
    x = validate(frame)
    assert x.columns.tolist() == FEATURES
    assert not set(FORBIDDEN).intersection(x.columns)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, "invalid"])
def test_invalid_sensor_rejected(frame, value):
    frame["Torque [Nm]"] = frame["Torque [Nm]"].astype(object)
    frame.loc[0, "Torque [Nm]"] = value
    with pytest.raises(ValueError):
        validate(frame)


def test_missing_feature_rejected(frame):
    with pytest.raises(ValueError):
        validate(frame.drop(columns=["Type"]))


def test_unordered_data_rejected(frame):
    with pytest.raises(ValueError):
        split_ordered(frame.iloc[::-1])


def test_duplicate_ids_rejected(frame):
    frame.loc[1, "UDI"] = 1
    with pytest.raises(ValueError):
        split_ordered(frame)


def test_training_inference_and_storage(frame, tmp_path):
    csv = tmp_path / "fixture.csv"
    frame.to_csv(csv, index=False)
    output = tmp_path / "artifacts"
    report = train(csv, output)
    bundle = load_model(output / "model.joblib")
    assert report["test"]["average_precision"] >= 0
    assert sum(report["test"]["confusion_matrix_tn_fp_fn_tp"]) == 60
    assert json.loads((output / "report.json").read_text())["seed"] == 42
    reading = frame.iloc[0][FEATURES].to_dict()
    result = predict(bundle, reading)
    assert result["status"] in {"NORMAL", "WARNING", "CRITICAL"}
    assert 0 <= result["failure_score"] <= 1
    assert result["prediction_horizon"] is None
    assert result["rul"] is None
    db = tmp_path / "test.sqlite3"
    save_prediction(db, reading, result)
    assert len(history(db)) == 1
    assert history(db).iloc[0]["model_version"] == bundle["version"]
    reading["Torque [Nm]"] = 10000
    result = predict(bundle, reading)
    assert result["status"] == "UNKNOWN"
    assert result["failure_score"] is None


def test_test_data_does_not_fit_scaler_or_select_model(frame, tmp_path):
    csv = tmp_path / "fixture.csv"
    frame.to_csv(csv, index=False)
    first = train(csv, tmp_path / "first")
    # Modificar exclusivamente el test no cambia modelo ni umbral de validación.
    frame.loc[240:, "Torque [Nm]"] += 1000
    frame.to_csv(csv, index=False)
    second = train(csv, tmp_path / "second")
    assert first["selected_model"] == second["selected_model"]
    assert first["validation"] == second["validation"]
    bundle = load_model(tmp_path / "second" / "model.joblib")
    scaler = bundle["model"].named_steps["preprocessing"].named_transformers_["numeric"]
    assert scaler.n_samples_seen_ == 180
