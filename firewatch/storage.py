import sqlite3
import json
from contextlib import contextmanager
from pathlib import Path

from .models import HumanAssessment, HumanReview, LLMCallRecord, PilotEvaluation, RunResult, ShadowAnalysis


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
                CREATE TABLE IF NOT EXISTS provider_checks(id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL, snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS human_assessments(id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(id), snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS shadow_analyses(id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(id), executed_at TEXT NOT NULL, snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS comparative_evaluations(id TEXT PRIMARY KEY,
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

    def _save_run(self, db, result):
        db.execute("INSERT OR REPLACE INTO incidents VALUES (?, ?)",
                   (result.incident.id, result.incident.model_dump_json()))
        for record in result.incident.evidence:
            db.execute("INSERT OR REPLACE INTO evidence VALUES (?, ?, ?)",
                       (record.id, result.incident.id, record.model_dump_json()))
        db.execute("INSERT INTO runs VALUES (?, ?, ?, ?)",
                   (result.run_id, result.incident.id, result.created_at.isoformat(), result.model_dump_json()))

    def save(self, result):
        with self.connect() as db:
            self._save_run(db, result)
        self._append_trace(result)

    def _append_trace(self, result):
        # SQLite's run snapshot is authoritative; JSONL is a convenient trace export.
        with self.trace_path.open("a", encoding="utf-8") as output:
            for event in result.trace:
                output.write(event.model_dump_json() + "\n")

    def save_human_assessment(self, assessment):
        assessment = HumanAssessment.model_validate(assessment.model_dump())
        with self.connect() as db:
            row = db.execute("SELECT snapshot FROM runs WHERE id=?", (assessment.run_id,)).fetchone()
            if row is None:
                raise ValueError("Analyze or load an existing run first")
            result = RunResult.model_validate_json(row[0])
            if assessment.recorded_at < result.created_at:
                raise ValueError("Human assessment cannot precede its saved run")
            db.execute("INSERT INTO human_assessments VALUES (?, ?, ?)",
                       (assessment.assessment_id, assessment.run_id, assessment.model_dump_json()))

    def human_assessments(self, run_id):
        with self.connect() as db:
            rows = db.execute("SELECT snapshot FROM human_assessments WHERE run_id=? ORDER BY rowid", (run_id,)).fetchall()
        return [HumanAssessment.model_validate_json(row[0]) for row in rows]

    def save_shadow(self, analysis):
        analysis = ShadowAnalysis.model_validate(analysis.model_dump())
        with self.connect() as db:
            self._save_run(db, analysis.result)
            db.execute("INSERT INTO shadow_analyses VALUES (?, ?, ?, ?)",
                       (analysis.shadow_id, analysis.result.run_id, analysis.executed_at.isoformat(), analysis.model_dump_json()))
        self._append_trace(analysis.result)

    def load_shadow(self, shadow_id):
        with self.connect() as db:
            row = db.execute("SELECT snapshot FROM shadow_analyses WHERE id=?", (shadow_id,)).fetchone()
        if row is None:
            raise KeyError("Shadow analysis not found")
        return ShadowAnalysis.model_validate_json(row[0])

    def shadows(self, limit=30):
        with self.connect() as db:
            return db.execute("SELECT id, executed_at FROM shadow_analyses ORDER BY executed_at DESC LIMIT ?", (limit,)).fetchall()

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

    def save_provider_check(self, record):
        record = LLMCallRecord.model_validate(record.model_dump())
        with self.connect() as db:
            db.execute("INSERT INTO provider_checks VALUES (?, ?, ?)",
                       (record.call_id, record.started_at.isoformat(), record.model_dump_json()))

    def latest_provider_check(self):
        with self.connect() as db:
            row = db.execute("SELECT snapshot FROM provider_checks ORDER BY created_at DESC LIMIT 1").fetchone()
        return LLMCallRecord.model_validate_json(row[0]) if row else None

    def save_comparison(self, evaluation):
        from .comparison import validate_comparison
        evaluation = validate_comparison(evaluation)
        with self.connect() as db:
            for row in evaluation.rows:
                for result in (row.reference, row.candidate):
                    saved = db.execute("SELECT snapshot FROM runs WHERE id=?", (result.run_id,)).fetchone()
                    if saved is None or RunResult.model_validate_json(saved[0]) != result:
                        raise ValueError("Comparison must reference its existing saved runs")
            db.execute("INSERT INTO comparative_evaluations VALUES (?, ?, ?)",
                       (evaluation.comparison_id, evaluation.evaluated_at.isoformat(), evaluation.model_dump_json()))

    def load_comparison(self, comparison_id):
        from .comparison import validate_comparison
        with self.connect() as db:
            row = db.execute("SELECT snapshot FROM comparative_evaluations WHERE id=?", (comparison_id,)).fetchone()
        if row is None:
            raise KeyError("Comparison not found")
        return validate_comparison(json.loads(row[0]))

    def comparisons(self, limit=30):
        with self.connect() as db:
            return db.execute("SELECT id, created_at FROM comparative_evaluations ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
