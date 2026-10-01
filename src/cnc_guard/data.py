"""Descarga oficial, contrato de datos y partición por orden del fichero."""

import hashlib
import io
import json
import os
import urllib.request
import uuid
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

DATA_URL = "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip"
NUMERIC = ["Air temperature [K]", "Process temperature [K]", "Rotational speed [rpm]",
           "Torque [Nm]", "Tool wear [min]"]
FEATURES = ["Type", *NUMERIC]
TARGET = "Machine failure"
FORBIDDEN = ["UDI", "Product ID", TARGET, "TWF", "HDF", "PWF", "OSF", "RNF"]


def download(destination: Path) -> dict:
    """Cache local: no sobrescribe una descarga existente; registra su SHA256."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        with urllib.request.urlopen(DATA_URL, timeout=60) as response:
            payload = response.read(5_000_001)
        if len(payload) > 5_000_000:
            raise ValueError("Descarga mayor que el límite permitido")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            member = next(x for x in archive.infolist() if x.filename == "ai4i2020.csv")
            if member.file_size > 5_000_000:
                raise ValueError("CSV demasiado grande")
            csv = archive.read(member)
        validate(pd.read_csv(io.BytesIO(csv)), training=True)
        pending = destination.with_name(f".{destination.name}-{uuid.uuid4().hex}.part")
        pending.write_bytes(csv)
        os.replace(pending, destination)
    frame = pd.read_csv(destination)
    validate(frame, training=True)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    metadata_path = destination.with_suffix(".metadata.json")
    if metadata_path.exists():
        old = json.loads(metadata_path.read_text(encoding="utf-8"))
        if old["sha256"] != digest:
            raise ValueError("El CSV local difiere de la descarga registrada")
    metadata = {
        "source": DATA_URL, "doi": "10.24432/C5HS5C", "license": "CC BY 4.0",
        "synthetic": True, "rows": len(frame), "columns": frame.columns.tolist(),
        "sha256": digest,
        "failures": int(frame[TARGET].sum()),
        "missing_values": int(frame.isna().sum().sum()),
        "duplicate_rows": int(frame.duplicated().sum()),
    }
    destination.with_suffix(".metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def validate(frame: pd.DataFrame, training: bool = False) -> pd.DataFrame:
    required = FEATURES + ([TARGET, "UDI"] if training else [])
    missing = sorted(set(required) - set(frame.columns))
    if missing or frame.empty:
        raise ValueError(f"Datos vacíos o columnas ausentes: {missing}")
    if not frame["Type"].isin(["L", "M", "H"]).all():
        raise ValueError("Type debe ser L, M o H")
    values = frame[NUMERIC].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(values.to_numpy()).all() or (values < 0).any().any():
        raise ValueError("Sensores: se requieren números finitos no negativos")
    if (values[NUMERIC[:4]] <= 0).any().any():
        raise ValueError("Temperatura, velocidad y par deben ser positivos")
    if training:
        if not frame[TARGET].isin([0, 1]).all():
            raise ValueError("Machine failure debe ser binaria")
        if frame["UDI"].isna().any() or frame["UDI"].duplicated().any():
            raise ValueError("UDI debe ser único y no nulo")
        order = pd.to_numeric(frame["UDI"], errors="coerce")
        if not np.isfinite(order).all() or not order.is_monotonic_increasing:
            raise ValueError("UDI debe conservar orden numérico creciente")
    result = frame[FEATURES].copy()
    result[NUMERIC] = values
    return result


def split_ordered(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """60/20/20 por orden UDI; UDI NO se interpreta como tiempo físico."""
    validate(frame, training=True)
    a, b = int(len(frame) * .6), int(len(frame) * .8)
    parts = frame.iloc[:a].copy(), frame.iloc[a:b].copy(), frame.iloc[b:].copy()
    if any(len(p) < 2 or p[TARGET].nunique() != 2 for p in parts):
        raise ValueError("Cada partición necesita ejemplos de ambas clases")
    return parts
