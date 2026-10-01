"""NASA Milling: descarga original, señales por ejecución y regresión de desgaste."""

import io
import os
import urllib.request
import uuid
import zipfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.stats import kurtosis
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from cnc_guard.registry import sha256, write_json

URL = "https://phm-datasets.s3.amazonaws.com/NASA/3.+Milling.zip"
SIGNALS = ["smcAC", "smcDC", "vib_table", "vib_spindle", "AE_table", "AE_spindle"]
STATISTICS = ["mean", "std", "rms", "peak_to_peak", "kurtosis"]
CONDITIONS = ["DOC", "feed", "material"]
FEATURES = [f"{signal}_{stat}" for signal in SIGNALS for stat in STATISTICS] + CONDITIONS


def download(raw: Path) -> dict:
    raw.mkdir(parents=True, exist_ok=True)
    archive_path = raw / "nasa-milling.zip"
    if not archive_path.exists():
        with urllib.request.urlopen(URL, timeout=60) as response:
            payload = response.read(30_000_001)
        if len(payload) > 30_000_000:
            raise ValueError("Archivo NASA mayor que el límite permitido")
        with zipfile.ZipFile(io.BytesIO(payload)) as outer:
            inner_bytes = outer.read("3. Milling/mill.zip")
        with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
            if inner.getinfo("mill.mat").file_size > 100_000_000:
                raise ValueError("Contenido NASA demasiado grande")
            inner.read("Readme.pdf")
            inner.read("mill.mat")
        pending = raw / f"nasa-{uuid.uuid4().hex}.part"
        pending.write_bytes(payload)
        os.replace(pending, archive_path)
    with zipfile.ZipFile(archive_path) as outer:
        inner_bytes = outer.read("3. Milling/mill.zip")
    with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
        for name in ["mill.mat", "Readme.pdf"]:
            target = raw / name
            content = inner.read(name)
            if target.exists() and target.read_bytes() != content:
                raise ValueError(f"Archivo original NASA modificado: {name}")
            if not target.exists():
                target.write_bytes(content)
    metadata = {"source": URL, "sha256": sha256(archive_path), "synthetic": False,
                "citation": "A. Agogino and K. Goebel (2007), BEST Lab, UC Berkeley; NASA PCoE",
                "license_source": "https://data.nasa.gov/dataset/milling-wear",
                "readme": "Readme.pdf", "mat_sha256": sha256(raw / "mill.mat")}
    write_json(raw / "nasa.metadata.json", metadata)
    return metadata


def load_records(raw: Path) -> list[dict]:
    values = loadmat(raw / "mill.mat", simplify_cells=True)["mill"]
    return list(values)


def signal_features(record: dict) -> dict:
    features = {}
    for name in SIGNALS:
        values = np.asarray(record[name], dtype=float).reshape(-1)
        if len(values) < 4 or not np.isfinite(values).all():
            raise ValueError(f"Señal inválida: {name}")
        stats = [np.mean(values), np.std(values), np.sqrt(np.mean(values ** 2)),
                 np.ptp(values), kurtosis(values, fisher=True, bias=False)
                 if np.std(values) > 0 else 0.0]
        features.update({f"{name}_{key}": float(value) for key, value in zip(STATISTICS, stats)})
    features.update({key: float(record[key]) for key in CONDITIONS})
    if not np.isfinite(list(features.values())).all():
        raise ValueError("Características no finitas")
    return features


def prepare(raw: Path, processed: Path) -> pd.DataFrame:
    records = load_records(raw)
    rows = [{"case": int(r["case"]), "run": int(r["run"]),
             "VB": float(r["VB"]), "time": float(r["time"]), **signal_features(r)} for r in records]
    frame = pd.DataFrame(rows).sort_values(["case", "run"]).reset_index(drop=True)
    if frame.duplicated(["case", "run"]).any():
        raise ValueError("Ejecuciones NASA duplicadas")
    processed.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(processed / "nasa_features.parquet", index=False)
    write_json(processed / "nasa_audit.json", {
        "records": len(frame), "cases": int(frame["case"].nunique()),
        "labeled": int(frame.VB.notna().sum()), "unlabeled": int(frame.VB.isna().sum()),
        "features": FEATURES, "label": "VB", "label_unit": "mm",
        "signals": SIGNALS, "signal_units": "Unidades de adquisición; no se aplica calibración física",
        "source_sha256": sha256(raw / "mill.mat")})
    return frame


def split_cases(frame: pd.DataFrame) -> dict[str, list[int]]:
    cases = np.array(sorted(frame["case"].unique()))
    if len(cases) != 16:
        raise ValueError("Se esperan los 16 ensayos del dataset NASA Milling")
    shuffled = np.random.default_rng(42).permutation(cases)
    return {"train": sorted(shuffled[:8].tolist()), "validation": sorted(shuffled[8:12].tolist()),
            "test": sorted(shuffled[12:].tolist())}


def regression_metrics(frame: pd.DataFrame, predicted: np.ndarray) -> dict:
    per_case = {str(case): {"mae": float(mean_absolute_error(frame.loc[mask, "VB"], predicted[mask])),
                            "rows": int(mask.sum())}
                for case in sorted(frame["case"].unique()) for mask in [frame["case"].to_numpy() == case]}
    return {"mae": float(mean_absolute_error(frame.VB, predicted)),
            "rmse": float(np.sqrt(mean_squared_error(frame.VB, predicted))),
            "macro_case_mae": float(np.mean([r["mae"] for r in per_case.values()])),
            "per_case": per_case}


def domain_mask(frame: pd.DataFrame, bounds: dict) -> np.ndarray:
    return np.array([all(np.isfinite(float(row[k])) and lo <= float(row[k]) <= hi
                         for k, (lo, hi) in bounds.items()) for _, row in frame.iterrows()])


def train(raw: Path, processed: Path, output: Path) -> dict:
    frame = prepare(raw, processed)
    groups = split_cases(frame)
    parts = {name: frame[frame["case"].isin(ids) & frame.VB.notna()].copy()
             for name, ids in groups.items()}
    if any(p.empty for p in parts.values()):
        raise ValueError("Partición sin etiquetas de desgaste")
    candidates = {
        "Median": DummyRegressor(strategy="median"),
        "Ridge": make_pipeline(StandardScaler(), Ridge(alpha=10)),
        "Random Forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=2,
                                                 random_state=42, n_jobs=2),
    }
    validation = {}
    for name, model in candidates.items():
        model.fit(parts["train"][FEATURES], parts["train"].VB)
        validation[name] = regression_metrics(parts["validation"],
                                               model.predict(parts["validation"][FEATURES]))
    selected = min(candidates, key=lambda n: validation[n]["macro_case_mae"])
    model = candidates[selected]
    training_data = parts["train"]
    # Se admiten solo valores del dominio observado en train; no se ajusta con test.
    bounds = {c: [float(training_data[c].min()), float(training_data[c].max())] for c in FEATURES}
    version = f"nasa-v1-{sha256(raw / 'mill.mat')[:8]}-{output.name}"
    test_predictions = model.predict(parts["test"][FEATURES])
    mask = domain_mask(parts["test"], bounds)
    report = {
        "model_version": version, "dataset": "nasa", "selected_model": selected,
        "seed": 42, "target": "Desgaste VB de la ejecución observada", "unit": "mm",
        "synthetic": False, "groups": groups, "validation": validation,
        "test": regression_metrics(parts["test"], test_predictions),
        "dummy_test": regression_metrics(parts["test"], candidates["Median"].predict(parts["test"][FEATURES])),
        "coverage": {"accepted": int(mask.sum()), "total": len(mask), "fraction": float(mask.mean()),
                     "accepted_metrics": regression_metrics(parts["test"].loc[mask], test_predictions[mask])
                     if mask.any() else None},
        "partitions": {name: {"rows": len(p), "cases": groups[name]} for name, p in parts.items()},
        "features": FEATURES, "source_sha256": sha256(raw / "mill.mat"),
        "limitations": ["16 ensayos; evidencia limitada de generalización",
                        "No predice fecha de fallo ni RUL", "No se rellenan VB ausentes",
                        "Las métricas completas incluyen predicciones fuera del dominio; ver cobertura"],
    }
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES, "bounds": bounds, "version": version},
                output / "model.joblib")
    write_json(output / "report.json", report)
    scored = frame[["case", "run", "VB"]].copy()
    scored["predicted_vb"] = model.predict(frame[FEATURES])
    scored["in_domain"] = domain_mask(frame, bounds)
    scored["partition"] = [next(name for name, ids in groups.items() if c in ids) for c in frame["case"]]
    scored.to_csv(output / "predictions.csv", index=False)
    return report


def predict(bundle: dict, record: dict) -> dict:
    from cnc_guard.storage import now
    frame = pd.DataFrame([signal_features(record)])
    accepted = bool(domain_mask(frame, bundle["bounds"])[0])
    return {"created_at": now(), "model_version": bundle["version"], "dataset": "nasa",
            "source": "NASA Milling / BEST Lab", "synthetic": False,
            "case": int(record["case"]), "run": int(record["run"]),
            "estimated_wear": float(bundle["model"].predict(frame[FEATURES])[0]) if accepted else None,
            "unit": "mm", "data_quality_status": "VALID" if accepted else "OUT_OF_TRAINING_RANGE",
            "status": "ESTIMATED" if accepted else "UNKNOWN", "prediction_horizon": None, "rul": None,
            "explanation": "Estimación de desgaste de esta ejecución; no es una predicción de fallo."
            if accepted else "Fuera del dominio de entrenamiento: el modelo se abstiene."}
