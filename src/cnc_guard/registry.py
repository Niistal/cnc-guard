"""Modelos propios e inmutables, activación atómica y comprobación de integridad."""

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import joblib

DATASETS = {"ai4i", "nasa"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
                    encoding="utf-8")


class Registry:
    def __init__(self, root: Path):
        self.root = root
        self.cache: dict[str, tuple[str, dict]] = {}

    def new_run(self, dataset: str) -> Path:
        if dataset not in DATASETS:
            raise ValueError("Dataset desconocido")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run = self.root / "runs" / dataset / f"{stamp}-{uuid.uuid4().hex[:10]}"
        run.mkdir(parents=True, exist_ok=False)
        return run

    def activate(self, dataset: str, run: Path) -> dict:
        expected = (self.root / "runs" / dataset).resolve()
        if dataset not in DATASETS or run.resolve().parent != expected:
            raise ValueError("Ruta de modelo no autorizada")
        report = json.loads((run / "report.json").read_text(encoding="utf-8"))
        model_path = run / "model.joblib"
        if not model_path.is_file() or "model_version" not in report:
            raise ValueError("Entrenamiento incompleto")
        manifest = {"dataset": dataset, "run_id": run.name,
                    "model_version": report["model_version"],
                    "model_sha256": sha256(model_path),
                    "report_sha256": sha256(run / "report.json")}
        write_json(run / "manifest.json", manifest)
        self.root.mkdir(parents=True, exist_ok=True)
        pending = self.root / f".{dataset}-{uuid.uuid4().hex}.pending"
        write_json(pending, manifest)
        os.replace(pending, self.root / f"active-{dataset}.json")
        self.cache.pop(dataset, None)
        return manifest

    def resolve(self, dataset: str) -> tuple[dict, Path]:
        if dataset not in DATASETS:
            raise ValueError("Dataset desconocido")
        pointer = self.root / f"active-{dataset}.json"
        if not pointer.exists():
            raise FileNotFoundError(f"No hay un modelo activo de {dataset}")
        manifest = json.loads(pointer.read_text(encoding="utf-8"))
        parent = (self.root / "runs" / dataset).resolve()
        run = (parent / manifest["run_id"]).resolve()
        if run.parent != parent:
            raise ValueError("Manifiesto de modelo inválido")
        if manifest != json.loads((run / "manifest.json").read_text(encoding="utf-8")):
            raise ValueError("Manifiestos inconsistentes")
        return manifest, run

    def report(self, dataset: str) -> dict:
        manifest, run = self.resolve(dataset)
        if sha256(run / "report.json") != manifest["report_sha256"]:
            raise ValueError("Informe alterado")
        return json.loads((run / "report.json").read_text(encoding="utf-8"))

    def load(self, dataset: str) -> dict:
        manifest, run = self.resolve(dataset)
        if sha256(run / "model.joblib") != manifest["model_sha256"]:
            raise ValueError("Modelo alterado; se rechaza la carga")
        key = manifest["model_sha256"]
        if dataset not in self.cache or self.cache[dataset][0] != key:
            # Solo artefactos creados localmente. El hash detecta corrupción, no sustituye una firma.
            self.cache[dataset] = key, joblib.load(run / "model.joblib")
        return self.cache[dataset][1]
