"""API local versionada y web estática; ningún endpoint controla maquinaria."""

import asyncio
import contextlib
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from cnc_guard import nasa
from cnc_guard.inference import predict
from cnc_guard.registry import Registry
from cnc_guard.service import DemoService
from cnc_guard.settings import Settings, project_root
from cnc_guard.storage import Store


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class AI4IReading(StrictModel):
    product_type: Literal["L", "M", "H"]
    air_temperature_k: float = Field(gt=0)
    process_temperature_k: float = Field(gt=0)
    rotational_speed_rpm: float = Field(gt=0)
    torque_nm: float = Field(gt=0)
    tool_wear_min: float = Field(ge=0)

    def dataset_reading(self):
        return {"Type": self.product_type, "Air temperature [K]": self.air_temperature_k,
                "Process temperature [K]": self.process_temperature_k,
                "Rotational speed [rpm]": self.rotational_speed_rpm,
                "Torque [Nm]": self.torque_nm, "Tool wear [min]": self.tool_wear_min}


class NoteInput(StrictModel):
    body: str = Field(min_length=1, max_length=2000)


class ActionInput(StrictModel):
    action: Literal["play", "pause"]


class MillingInput(StrictModel):
    case: int = Field(ge=1, le=16)
    run: int = Field(ge=1)


def create_app(root: Path | None = None, background: bool = True) -> FastAPI:
    settings = Settings(root or project_root())
    registry = Registry(settings.artifacts)
    store = Store(settings.database)
    demo = DemoService(store, registry, settings.raw / "ai4i2020.csv")
    records_cache: list[dict] = []

    @asynccontextmanager
    async def lifespan(app):
        store.pause_on_startup()
        task = asyncio.create_task(demo.worker()) if background else None
        yield
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="CNC Guard", version="1.0.0", lifespan=lifespan)
    app.state.store, app.state.demo, app.state.registry = store, demo, registry

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in {
            "http://127.0.0.1:8000", "http://localhost:8000",
            "http://127.0.0.1:5173", "http://localhost:5173"}:
            return JSONResponse({"error": "Origen no permitido"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"error": "Entrada inválida", "details": [
            {"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]},
            status_code=422)

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        return JSONResponse({"error": str(exc)}, status_code=400)

    @app.exception_handler(KeyError)
    async def missing_key(request, exc):
        return JSONResponse({"error": "Recurso no encontrado"}, status_code=404)

    @app.exception_handler(FileNotFoundError)
    async def missing_file(request, exc):
        return JSONResponse({"error": "Datos o modelo no disponibles. Ejecuta la preparación del dataset."},
                            status_code=503)

    @app.get("/api/v1/health")
    def health():
        models = {}
        for dataset in ["ai4i", "nasa"]:
            try:
                manifest, _ = registry.resolve(dataset)
                registry.report(dataset)
                models[dataset] = {"ready": True, "version": manifest["model_version"]}
                store.register_model(manifest)
            except (FileNotFoundError, ValueError, KeyError):
                models[dataset] = {"ready": False, "version": None}
        return {"status": "ok", "mode": "local_academic_demo", "models": models}

    @app.get("/api/v1/machines")
    def machines(session_id: int | None = Query(default=None, ge=1)):
        return store.machines(session_id)

    @app.get("/api/v1/machines/{machine_id}/readings")
    def readings(machine_id: str, session_id: int | None = Query(default=None, ge=1)):
        return store.machine_history(machine_id, session_id)

    @app.get("/api/v1/sessions")
    def sessions():
        return store.sessions()

    @app.post("/api/v1/sessions", status_code=201)
    async def new_session():
        return await demo.restart()

    @app.patch("/api/v1/sessions/{session_id}")
    async def session_action(session_id: int, payload: ActionInput):
        return await demo.change_state(session_id, payload.action)

    @app.get("/api/v1/alerts")
    def alerts(session_id: int | None = Query(default=None, ge=1)):
        return store.alerts(session_id)

    @app.post("/api/v1/alerts/{alert_id}/acknowledge")
    def acknowledge(alert_id: int):
        store.acknowledge(alert_id)
        return {"acknowledged": True}

    @app.post("/api/v1/alerts/{alert_id}/notes", status_code=201)
    def add_note(alert_id: int, payload: NoteInput):
        if not payload.body.strip():
            raise ValueError("La nota no puede estar vacía")
        return {"id": store.add_note(alert_id, payload.body.strip())}

    @app.post("/api/v1/predictions/ai4i", status_code=201)
    def classify(payload: AI4IReading):
        reading = payload.dataset_reading()
        result = predict(registry.load("ai4i"), reading)
        result.update({"dataset": "ai4i", "source": "UCI AI4I 2020"})
        return {**result, "id": store.record_manual(reading, result, "ai4i")}

    @app.get("/api/v1/predictions")
    def predictions():
        return store.predictions()

    @app.get("/api/v1/evaluations/{dataset}")
    def evaluation(dataset: Literal["ai4i", "nasa"]):
        return registry.report(dataset)

    @app.get("/api/v1/evaluations/{dataset}/download")
    def export(dataset: Literal["ai4i", "nasa"]):
        return JSONResponse(registry.report(dataset), headers={
            "Content-Disposition": f'attachment; filename="cnc-guard-{dataset}-evaluation.json"'})

    def nasa_records():
        if not records_cache:
            records_cache.extend(nasa.load_records(settings.raw))
        return records_cache

    def find_record(case: int, run: int):
        record = next((r for r in nasa_records() if int(r["case"]) == case and int(r["run"]) == run), None)
        if record is None:
            raise KeyError((case, run))
        return record

    @app.get("/api/v1/milling/cases")
    def cases():
        records = nasa_records()
        return [{"case": c, "runs": sum(int(r["case"]) == c for r in records),
                 "labeled": int(sum(int(r["case"]) == c and np.isfinite(float(r["VB"])) for r in records))}
                for c in sorted({int(r["case"]) for r in records})]

    @app.get("/api/v1/milling/cases/{case}")
    def case_detail(case: int):
        _, run_path = registry.resolve("nasa")
        scores = pd.read_csv(run_path / "predictions.csv")
        subset = scores[scores["case"] == case]
        if subset.empty:
            raise KeyError(case)
        return json.loads(subset.to_json(orient="records"))

    @app.get("/api/v1/milling/cases/{case}/runs/{run}/signals")
    def signals(case: int, run: int):
        record = find_record(case, run)
        length = len(record[nasa.SIGNALS[0]])
        indices = np.linspace(0, length - 1, min(300, length), dtype=int)
        return {"case": case, "run": run, "sample_count": length,
                "axis": "Índice de muestra", "decimated": True,
                "points": [{"sample": int(i), **{s: float(record[s][i]) for s in nasa.SIGNALS}}
                           for i in indices]}

    @app.post("/api/v1/predictions/milling", status_code=201)
    def estimate(payload: MillingInput):
        record = find_record(payload.case, payload.run)
        result = nasa.predict(registry.load("nasa"), record)
        return {**result, "id": store.record_manual(payload.model_dump(), result, "nasa")}

    dist = settings.root / "web" / "dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Ruta API no encontrada")
        if (dist / "index.html").exists():
            return FileResponse(dist / "index.html")
        return JSONResponse({"message": "API disponible. Compila la web con pnpm build.",
                             "documentation": "/docs"})

    return app
