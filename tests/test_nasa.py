"""Ensayos sintéticos solo para comprobar aislamiento de grupos y tratamiento de etiquetas."""

import numpy as np
import pandas as pd
import pytest
from scipy.io import savemat

from cnc_guard import nasa


def make_records():
    rng = np.random.default_rng(7)
    return [{"case": case, "run": run, "VB": run * .1 if run != 4 else np.nan,
             "time": run, "DOC": 1.5, "feed": .5, "material": 1,
             **{s: rng.normal(run, .1, 64) for s in nasa.SIGNALS}}
            for case in range(1, 17) for run in range(1, 5)]


def test_nasa_features_exclude_labels_and_identifiers():
    features = nasa.signal_features(make_records()[0])
    assert len(features) == 33
    assert not {"VB", "case", "run", "time"}.intersection(features)
    assert np.isfinite(list(features.values())).all()


def test_nasa_invalid_signal():
    record = make_records()[0]
    record["smcAC"][0] = np.nan
    with pytest.raises(ValueError):
        nasa.signal_features(record)


def test_nasa_test_cases_do_not_change_fit(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    records = make_records()
    savemat(raw / "mill.mat", {"mill": records})
    first = nasa.train(raw, tmp_path / "processed", tmp_path / "first")
    groups = first["groups"]
    assert [len(groups[k]) for k in ["train", "validation", "test"]] == [8, 4, 4]
    assert set(groups["train"]).isdisjoint(groups["test"])
    assert set(groups["train"]).isdisjoint(groups["validation"])
    assert set(groups["validation"]).isdisjoint(groups["test"])
    assert first["partitions"]["train"]["rows"] == 24
    for record in records:
        if record["case"] in groups["test"]:
            record["smcAC"] += 100
    savemat(raw / "mill.mat", {"mill": records})
    second = nasa.train(raw, tmp_path / "processed", tmp_path / "second")
    for name, metrics in first["validation"].items():
        repeated = second["validation"][name]
        for metric in ("mae", "rmse", "macro_case_mae"):
            assert metrics[metric] == pytest.approx(repeated[metric], abs=1e-10)
        assert metrics["per_case"].keys() == repeated["per_case"].keys()
        for case, case_metrics in metrics["per_case"].items():
            assert case_metrics["rows"] == repeated["per_case"][case]["rows"]
            assert case_metrics["mae"] == pytest.approx(
                repeated["per_case"][case]["mae"], abs=1e-10
            )
    assert first["selected_model"] == second["selected_model"]
    frame = pd.read_parquet(tmp_path / "processed" / "nasa_features.parquet")
    assert len(frame) == 64 and frame.VB.isna().sum() == 16
