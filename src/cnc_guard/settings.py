"""Rutas explícitas del proyecto, sin leer archivos de credenciales."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    root: Path

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @property
    def database(self) -> Path:
        return self.artifacts / "history.sqlite3"

    @property
    def raw(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def processed(self) -> Path:
        return self.root / "data" / "processed"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]
