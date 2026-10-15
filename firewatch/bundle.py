"""Portable ZIP dossiers with comparison, original runs, traces and checksums."""
import hashlib
import io
import json
import zipfile

from .comparison import comparison_csv, comparison_report, validate_comparison
from .research import human_comparison


def comparison_bundle(evaluation, store):
    evaluation = validate_comparison(evaluation)
    files = {"comparison.json": evaluation.model_dump_json(indent=2).encode("utf-8"),
             "comparison.csv": comparison_csv(evaluation).encode("utf-8-sig"),
             "report.txt": comparison_report(evaluation).encode("utf-8")}
    traces = []
    for row in evaluation.rows:
        for result in (row.reference, row.candidate):
            saved = store.load(result.run_id)
            if saved != result:
                raise ValueError("Saved run differs from comparison snapshot")
            content = result.model_dump(mode="json")
            content["human_reviews"] = [r.model_dump(mode="json") for r in store.reviews(result.run_id)]
            assessments = store.human_assessments(result.run_id)
            content["human_assessments"] = [r.model_dump(mode="json") for r in assessments]
            content["human_comparison"] = human_comparison(result, assessments)
            # Use numeric filenames rather than externally supplied IDs as archive paths.
            index = len(files) - 3
            files[f"runs/{index + 1:03d}.json"] = json.dumps(content, indent=2, ensure_ascii=False).encode("utf-8")
            traces.extend(e.model_dump_json() for e in result.trace)
    files["trace.jsonl"] = ("\n".join(traces) + ("\n" if traces else "")).encode("utf-8")
    manifest = {"comparison_id": evaluation.comparison_id, "version": evaluation.version,
                "requested_candidate": evaluation.requested_candidate, "status": evaluation.status,
                "run_ids": [run.run_id for row in evaluation.rows for run in (row.reference, row.candidate)],
                "sha256": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
                "note": "Checksums detect changed files; they do not authenticate source truth or reviewer identity. Human records reflect export time, separately from immutable run snapshots."}
    files["manifest.json"] = json.dumps(manifest, indent=2).encode("utf-8")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()
