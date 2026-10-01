"""Servicio de demo: sesiones virtuales separadas del entrenamiento."""

import asyncio
from pathlib import Path

import pandas as pd

from cnc_guard.data import FEATURES, split_ordered
from cnc_guard.inference import predict
from cnc_guard.registry import Registry
from cnc_guard.storage import Store


class DemoService:
    def __init__(self, store: Store, registry: Registry, csv_path: Path):
        self.store = store
        self.registry = registry
        self.csv_path = csv_path
        self.lock = asyncio.Lock()
        self.frame: pd.DataFrame | None = None

    def data(self) -> pd.DataFrame:
        if self.frame is None:
            if not self.csv_path.exists():
                raise FileNotFoundError("Descarga y entrena AI4I antes de iniciar una demo")
            _, _, test = split_ordered(pd.read_csv(self.csv_path))
            self.frame = test.reset_index(drop=True)
        return self.frame

    def tick(self, count: int = 5):
        session = self.store.current()
        if not session:
            raise ValueError("No existe una sesión")
        frame = self.data()
        bundle = self.registry.load("ai4i")
        records = []
        start = session["cursor"]
        for index in range(start, start + count):
            row = frame.iloc[index % len(frame)]
            reading = row[FEATURES].to_dict()
            result = predict(bundle, reading)
            result.update({"dataset": "ai4i", "source": "UCI AI4I 2020",
                           "simulated_identity": True, "simulated_time": True})
            records.append({"machine_id": f"CNC-{index % 50 + 1:03d}", "udi": int(row.UDI),
                            "step": index // 50, "reading": reading, "result": result})
        self.store.record_batch(session["id"], records, start + count)

    async def restart(self) -> dict:
        async with self.lock:
            self.registry.load("ai4i")
            self.data()
            session = self.store.create_session()
            try:
                self.tick(50)
            except Exception:
                self.store.set_state(session["id"], "error", "No se pudo preparar la sesión")
                raise
            return self.store.current()

    async def change_state(self, session_id: int, action: str) -> dict:
        async with self.lock:
            current = self.store.current()
            if not current or current["id"] != session_id:
                raise ValueError("Solo se puede controlar la sesión actual")
            if action == "play":
                self.registry.load("ai4i")
                self.data()
            self.store.set_state(session_id, "running" if action == "play" else "paused")
            return self.store.current()

    async def worker(self):
        while True:
            await asyncio.sleep(1)
            async with self.lock:
                session = self.store.current()
                if session and session["state"] == "running":
                    try:
                        self.tick()
                    except Exception as error:  # noqa: BLE001 - keep background worker alive
                        self.store.set_state(session["id"], "error", str(error))
