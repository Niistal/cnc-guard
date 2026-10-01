"""Entrenamiento sin etiquetas de fallo entre las entradas; test aislado."""

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

from cnc_guard.data import FEATURES, TARGET, split_ordered, validate
from cnc_guard.models import model_candidates, preprocessor


def metrics(y, scores, threshold: float) -> dict:
    predicted = np.asarray(scores) >= threshold
    return {
        "average_precision": float(average_precision_score(y, scores)),
        "roc_auc": float(roc_auc_score(y, scores)),
        "precision": float(precision_score(y, predicted, zero_division=0)),
        "recall": float(recall_score(y, predicted, zero_division=0)),
        "f2": float(fbeta_score(y, predicted, beta=2, zero_division=0)),
        "confusion_matrix_tn_fp_fn_tp": confusion_matrix(y, predicted, labels=[0, 1]).ravel().tolist(),
    }


def choose_threshold(y, scores) -> float:
    """Maximiza F2 en validación, no en test. Empates: umbral mayor."""
    options = np.linspace(.01, .99, 99)
    return float(max(options, key=lambda t: (fbeta_score(
        y, scores >= t, beta=2, zero_division=0), t)))


def train(csv_path: Path, output: Path) -> dict:
    frame = pd.read_csv(csv_path)
    train_df, val_df, test_df = split_ordered(frame)
    x_train, x_val, x_test = (validate(p) for p in (train_df, val_df, test_df))
    candidates, validation = model_candidates(), {}
    for name, model in candidates.items():
        model.fit(x_train, train_df[TARGET])
        scores = model.predict_proba(x_val)[:, 1]
        threshold = .5 if name == "Dummy" else choose_threshold(val_df[TARGET], scores)
        validation[name] = {"threshold": threshold, **metrics(val_df[TARGET], scores, threshold)}
    selected = max((n for n in candidates if n != "Dummy"),
                   key=lambda n: validation[n]["average_precision"])
    model = candidates[selected]
    threshold = validation[selected]["threshold"]
    anomaly = Pipeline([("preprocessing", preprocessor()),
                        ("model", IsolationForest(random_state=42, n_estimators=150,
                                                  contamination="auto", n_jobs=2))])
    # Aprendizaje no supervisado: sin consultar etiquetas, todas las filas de train.
    anomaly.fit(x_train)
    anomaly_threshold = float(np.quantile(-anomaly.score_samples(x_val), .95))
    data_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    version = f"ai4i-v1-{data_hash[:8]}-sklearn{sklearn.__version__}-{output.name}"
    bounds = {c: [float(x_train[c].min()), float(x_train[c].max())]
              for c in FEATURES if c != "Type"}
    bundle = {"model": model, "anomaly": anomaly, "threshold": threshold,
              "anomaly_threshold": anomaly_threshold, "version": version,
              "bounds": bounds, "features": FEATURES}
    test_scores = model.predict_proba(x_test)[:, 1]
    report = {
        "model_version": version, "selected_model": selected, "seed": 42,
        "dataset_sha256": data_hash, "synthetic": True,
        "target": "Machine failure de la misma fila; sin horizonte futuro ni RUL",
        "split": "60/20/20 por orden UDI; sin equivalencia a tiempo real",
        "partitions": {name: {"rows": len(p), "failures": int(p[TARGET].sum()),
                              "udi_min": int(p.UDI.min()), "udi_max": int(p.UDI.max())}
                       for name, p in zip(["train", "validation", "test"],
                                          [train_df, val_df, test_df])},
        "validation": validation, "threshold": threshold,
        "test": metrics(test_df[TARGET], test_scores, threshold),
        "dummy_test": metrics(test_df[TARGET], candidates["Dummy"].predict_proba(x_test)[:, 1], .5),
        "anomaly_test_average_precision": float(average_precision_score(
            test_df[TARGET], -anomaly.score_samples(x_test))),
        "anomaly_threshold": anomaly_threshold,
        "anomaly_note": "Percentil 95 de validación sin etiquetas; anomalía no implica fallo",
        "global_importance": None,
    }
    estimator = model.named_steps["model"]
    names = model.named_steps["preprocessing"].get_feature_names_out()
    importance = (estimator.feature_importances_ if hasattr(estimator, "feature_importances_")
                  else np.abs(estimator.coef_[0]))
    report["global_importance"] = dict(zip(names.tolist(), importance.tolist()))
    accepted = np.array([all(lo <= float(row[c]) <= hi for c, (lo, hi) in bounds.items())
                         for _, row in x_test.iterrows()])
    report["coverage"] = {"accepted": int(accepted.sum()), "total": len(accepted),
                          "fraction": float(accepted.mean()),
                          "note": "Métricas de test completas; en la aplicación se abstiene fuera de rango"}
    if accepted.any() and test_df.loc[accepted, TARGET].nunique() == 2:
        report["coverage"]["accepted_metrics"] = metrics(
            test_df.loc[accepted, TARGET], test_scores[accepted], threshold)
    else:
        report["coverage"]["accepted_metrics"] = None
    output.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, output / "model.joblib")
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    predictions = test_df[["UDI", TARGET]].copy()
    predictions["failure_score"] = test_scores
    predictions["anomaly_score"] = -anomaly.score_samples(x_test)
    predictions.to_csv(output / "test_predictions.csv", index=False)
    return report
