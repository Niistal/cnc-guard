"""SQLite transaccional, migración aditiva y sesiones reproducibles."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


def now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connect(self):
        with sqlite3.connect(self.path, timeout=20) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            yield db

    def migrate(self) -> None:
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS machines (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, area TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY, created_at TEXT NOT NULL,
                    state TEXT NOT NULL, cursor INTEGER NOT NULL DEFAULT 0,
                    error TEXT);
                CREATE TABLE IF NOT EXISTS readings (
                    id INTEGER PRIMARY KEY, session_id INTEGER REFERENCES sessions(id),
                    machine_id TEXT REFERENCES machines(id), source_udi INTEGER,
                    simulated_step INTEGER, created_at TEXT NOT NULL, payload_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY, created_at TEXT NOT NULL,
                    reading_json TEXT NOT NULL, result_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY, prediction_id INTEGER UNIQUE REFERENCES predictions(id),
                    machine_id TEXT REFERENCES machines(id), session_id INTEGER REFERENCES sessions(id),
                    status TEXT NOT NULL, created_at TEXT NOT NULL, acknowledged_at TEXT);
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY, alert_id INTEGER REFERENCES alerts(id),
                    created_at TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS models (
                    version TEXT PRIMARY KEY, dataset TEXT NOT NULL, registered_at TEXT NOT NULL,
                    manifest_json TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS readings_session_machine ON readings(session_id,machine_id,id);
                CREATE INDEX IF NOT EXISTS alerts_session ON alerts(session_id,id);
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(predictions)")}
            if "reading_id" not in columns:
                db.execute("ALTER TABLE predictions ADD COLUMN reading_id INTEGER REFERENCES readings(id)")
            if "dataset" not in columns:
                db.execute("ALTER TABLE predictions ADD COLUMN dataset TEXT NOT NULL DEFAULT 'ai4i'")
            db.execute("CREATE INDEX IF NOT EXISTS predictions_reading ON predictions(reading_id)")
            db.executemany("INSERT OR IGNORE INTO machines VALUES (?,?,?)", [
                (f"CNC-{i:03d}", f"Centro de mecanizado {i:02d}",
                 ["Fresado", "Torneado", "Acabado"][(i - 1) % 3]) for i in range(1, 51)])
            db.execute("PRAGMA user_version=1")

    def pause_on_startup(self):
        with self.connect() as db:
            db.execute("UPDATE sessions SET state='paused' WHERE state='running'")

    def sessions(self) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT 100")]

    def current(self) -> dict | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT 1").fetchone()
            return dict(row) if row else None

    def create_session(self) -> dict:
        with self.connect() as db:
            db.execute("UPDATE sessions SET state='archived' WHERE state!='archived'")
            cursor = db.execute("INSERT INTO sessions(created_at,state) VALUES (?,'paused')", (now(),))
            session_id = cursor.lastrowid
        return {"id": session_id, "state": "paused", "cursor": 0, "error": None}

    def set_state(self, session_id: int, state: str, error: str | None = None):
        with self.connect() as db:
            cursor = db.execute("UPDATE sessions SET state=?,error=? WHERE id=? AND state!='archived'",
                                (state, error, session_id))
            if cursor.rowcount == 0:
                raise ValueError("La sesión no existe o está archivada")

    def record_batch(self, session_id: int, records: list[dict], next_cursor: int):
        with self.connect() as db:
            for item in records:
                reading, result = item["reading"], item["result"]
                timestamp = result["created_at"]
                cursor = db.execute("INSERT INTO readings(session_id,machine_id,source_udi,"
                                    "simulated_step,created_at,payload_json) VALUES (?,?,?,?,?,?)",
                                    (session_id, item["machine_id"], item["udi"], item["step"],
                                     timestamp, json.dumps(reading)))
                reading_id = cursor.lastrowid
                prediction_id = self.insert_prediction(db, reading, result, "ai4i", reading_id)
                if result["status"] in {"WARNING", "CRITICAL", "UNKNOWN"}:
                    db.execute("INSERT INTO alerts(prediction_id,machine_id,session_id,status,created_at)"
                               " VALUES (?,?,?,?,?)", (prediction_id, item["machine_id"], session_id,
                                                        result["status"], timestamp))
            db.execute("UPDATE sessions SET cursor=? WHERE id=?", (next_cursor, session_id))

    @staticmethod
    def insert_prediction(db, reading, result, dataset, reading_id=None) -> int:
        cursor = db.execute("INSERT INTO predictions(created_at,reading_json,result_json,reading_id,dataset)"
                            " VALUES (?,?,?,?,?)", (result["created_at"], json.dumps(reading),
                                                   json.dumps(result), reading_id, dataset))
        return cursor.lastrowid

    def record_manual(self, reading: dict, result: dict, dataset: str) -> int:
        with self.connect() as db:
            return self.insert_prediction(db, reading, result, dataset)

    def machines(self, session_id: int | None = None) -> list[dict]:
        current = self.current()
        chosen = session_id if session_id is not None else current["id"] if current else -1
        with self.connect() as db:
            rows = db.execute("""SELECT m.*,r.source_udi,r.simulated_step,r.payload_json,
                p.result_json FROM machines m LEFT JOIN readings r ON r.id=(
                    SELECT MAX(id) FROM readings WHERE machine_id=m.id AND session_id=?)
                LEFT JOIN predictions p ON p.reading_id=r.id ORDER BY m.id""", (chosen,)).fetchall()
        return [{"id": r["id"], "name": r["name"], "area": r["area"], "simulated": True,
                 "source_udi": r["source_udi"], "step": r["simulated_step"],
                 "reading": json.loads(r["payload_json"]) if r["payload_json"] else None,
                 "prediction": json.loads(r["result_json"]) if r["result_json"] else None} for r in rows]

    def machine_history(self, machine_id: str, session_id: int | None) -> list[dict]:
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM machines WHERE id=?", (machine_id,)).fetchone():
                raise KeyError(machine_id)
            rows = db.execute("""SELECT r.id,r.source_udi,r.simulated_step,r.created_at,r.payload_json,
                p.result_json FROM readings r JOIN predictions p ON p.reading_id=r.id
                WHERE r.machine_id=? AND (? IS NULL OR r.session_id=?) ORDER BY r.id DESC LIMIT 100""",
                (machine_id, session_id, session_id)).fetchall()
        return [{"id": r["id"], "source_udi": r["source_udi"], "step": r["simulated_step"],
                 "created_at": r["created_at"], "reading": json.loads(r["payload_json"]),
                 "prediction": json.loads(r["result_json"])} for r in reversed(rows)]

    def alerts(self, session_id: int | None = None) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("""SELECT a.*,p.result_json FROM alerts a JOIN predictions p
                ON p.id=a.prediction_id WHERE (? IS NULL OR a.session_id=?)
                ORDER BY a.id DESC LIMIT 200""", (session_id, session_id)).fetchall()
            return [{**{k: r[k] for k in r.keys() if k != "result_json"},  # noqa: SIM118 - sqlite3.Row keys
                     "prediction": json.loads(r["result_json"]),
                     "notes": [dict(n) for n in db.execute(
                         "SELECT * FROM notes WHERE alert_id=? ORDER BY id", (r["id"],))]} for r in rows]

    def acknowledge(self, alert_id: int) -> None:
        with self.connect() as db:
            cursor = db.execute("UPDATE alerts SET acknowledged_at=COALESCE(acknowledged_at,?) WHERE id=?",
                                (now(), alert_id))
            if cursor.rowcount == 0:
                raise KeyError(alert_id)

    def add_note(self, alert_id: int, body: str) -> int:
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM alerts WHERE id=?", (alert_id,)).fetchone():
                raise KeyError(alert_id)
            return db.execute("INSERT INTO notes(alert_id,created_at,body) VALUES (?,?,?)",
                              (alert_id, now(), body)).lastrowid

    def predictions(self) -> list[dict]:
        with self.connect() as db:
            return [{"id": r["id"], "dataset": r["dataset"],
                     "result": json.loads(r["result_json"])} for r in db.execute(
                         "SELECT * FROM predictions ORDER BY id DESC LIMIT 100")]

    def register_model(self, manifest: dict):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO models VALUES (?,?,?,?)",
                       (manifest["model_version"], manifest["dataset"], now(), json.dumps(manifest)))
