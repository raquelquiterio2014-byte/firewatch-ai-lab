import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .models import HumanReview, PilotEvaluation, RunResult


class Store:
    """Each operation owns its connection, including calls from GUI workers."""
    def __init__(self, directory="data"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db_path = self.directory / "firewatch.sqlite3"
        self.trace_path = self.directory / "trace.jsonl"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY, snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS evidence(id TEXT NOT NULL, incident_id TEXT NOT NULL,
                    snapshot TEXT NOT NULL, PRIMARY KEY(id, incident_id));
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, incident_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS human_reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL REFERENCES runs(id), snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS pilot_evaluations(id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL, snapshot TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, result):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO incidents VALUES (?, ?)",
                       (result.incident.id, result.incident.model_dump_json()))
            for record in result.incident.evidence:
                db.execute("INSERT OR REPLACE INTO evidence VALUES (?, ?, ?)",
                           (record.id, result.incident.id, record.model_dump_json()))
            db.execute("INSERT INTO runs VALUES (?, ?, ?, ?)",
                       (result.run_id, result.incident.id, result.created_at.isoformat(), result.model_dump_json()))
        # SQLite's run snapshot is authoritative; JSONL is a convenient trace export.
        with self.trace_path.open("a", encoding="utf-8") as output:
            for event in result.trace:
                output.write(event.model_dump_json() + "\n")

    def load(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT snapshot FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError("Run not found")
        return RunResult.model_validate_json(row[0])

    def recent(self, limit=30):
        with self.connect() as db:
            return db.execute("SELECT id, created_at FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()

    def review(self, review):
        review = HumanReview.model_validate(review.model_dump())
        with self.connect() as db:
            db.execute("INSERT INTO human_reviews(run_id, snapshot) VALUES (?, ?)",
                       (review.run_id, review.model_dump_json()))

    def reviews(self, run_id):
        with self.connect() as db:
            rows = db.execute("SELECT snapshot FROM human_reviews WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
        return [HumanReview.model_validate_json(row[0]) for row in rows]

    def save_evaluation(self, evaluation):
        evaluation = PilotEvaluation.model_validate(evaluation.model_dump())
        with self.connect() as db:
            db.execute("INSERT INTO pilot_evaluations VALUES (?, ?, ?)",
                       (evaluation.evaluation_id, evaluation.evaluated_at.isoformat(), evaluation.model_dump_json()))

    def load_evaluation(self, evaluation_id):
        with self.connect() as db:
            row = db.execute("SELECT snapshot FROM pilot_evaluations WHERE id=?", (evaluation_id,)).fetchone()
        if row is None:
            raise KeyError("Evaluation not found")
        return PilotEvaluation.model_validate_json(row[0])

    def evaluations(self, limit=10):
        with self.connect() as db:
            return db.execute("SELECT id, created_at FROM pilot_evaluations ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
