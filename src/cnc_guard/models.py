"""Selección adaptada de CNC.model_map del proyecto Shengwei-Peng (MIT).

Origen: utils.py, commit 20308e0cc0093882f66d3602d15c2d234b0f311b.
Copyright (c) 2024 Shengwei-Peng. Ver third_party/CNC-Predictive-Maintenance.LICENSE.
Cambios: factoría de instancias independientes, pipelines, escalado, pesos y límites.
"""

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from cnc_guard.data import NUMERIC


def preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("numeric", StandardScaler(), NUMERIC),
        ("type", OneHotEncoder(handle_unknown="error", sparse_output=False), ["Type"]),
    ])


def model_candidates(seed: int = 42) -> dict[str, Pipeline]:
    model_map = {
        "Dummy": DummyClassifier(strategy="prior"),
        "Logistic Regression": LogisticRegression(random_state=seed, class_weight="balanced",
                                                   max_iter=2000),
        "Random Forest": RandomForestClassifier(random_state=seed, class_weight="balanced",
                                                 n_estimators=200, min_samples_leaf=2, n_jobs=2),
    }
    return {name: Pipeline([("preprocessing", preprocessor()), ("model", model)])
            for name, model in model_map.items()}
