"""GUI by default; command-line evaluation works without a display."""
import argparse
import json
from datetime import datetime
from pathlib import Path

from firewatch.evaluation import evaluate, evaluation_csv
from firewatch.pipeline import Pipeline
from firewatch.integration import check_gemini
from firewatch.scenarios import SCENARIOS, get_scenario
from firewatch.storage import Store
from firewatch.models import ShadowDataset
from firewatch.research import run_shadow
from firewatch.v5_demo import shadow_demo


def main():
    parser = argparse.ArgumentParser(description="FireWatch AI educational prototype")
    parser.add_argument("--evaluate", action="store_true", help="Run the 10 synthetic reference scenarios")
    parser.add_argument("--scenario", type=int, choices=range(1, 11), help="Analyze a catalogue scenario without GUI")
    parser.add_argument("--llm", action="store_true", help="Use optional Gemini for a single CLI scenario")
    parser.add_argument("--output", type=Path, help="Write CLI output JSON")
    parser.add_argument("--data-dir", default="data", help="SQLite and trace destination")
    parser.add_argument("--repetitions", type=int, choices=range(2, 6), default=2, help="Decision-stability trials per evaluation case")
    parser.add_argument("--csv", type=Path, help="Write per-scenario CSV for --evaluate")
    parser.add_argument("--check-gemini", action="store_true", help="Explicit provider JSON probe, without incident observations")
    parser.add_argument("--model", help="Gemini model override for --llm or --check-gemini")
    parser.add_argument("--shadow", type=Path, help="Analyze a normalized shadow dataset JSON offline")
    parser.add_argument("--shadow-demo", action="store_true", help="Run the V5 synthetic cutoff demo offline")
    parser.add_argument("--cutoff", help="Shadow decision cutoff, ISO 8601 with timezone")
    args = parser.parse_args()
    if args.shadow or args.shadow_demo:
        if args.shadow and args.shadow_demo:
            parser.error("Choose --shadow OR --shadow-demo")
        if args.evaluate or args.scenario or args.check_gemini or args.llm or args.csv or args.model:
            parser.error("Shadow Mode is a separate offline analysis; --llm is not supported")
        if not args.cutoff:
            parser.error("Shadow Mode requires --cutoff with a timezone")
        try:
            cutoff = datetime.fromisoformat(args.cutoff.replace("Z", "+00:00"))
            dataset = ShadowDataset.model_validate_json(args.shadow.read_text(encoding="utf-8-sig")) if args.shadow else shadow_demo()
            analysis = run_shadow(dataset, cutoff, store=Store(args.data_dir))
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
        content = analysis.model_dump_json(indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content + "\n", encoding="utf-8")
        print(content)
        return 0
    if args.cutoff:
        parser.error("--cutoff requires --shadow or --shadow-demo")
    if args.csv and not args.evaluate:
        parser.error("--csv requires --evaluate")
    if args.check_gemini:
        if args.evaluate or args.scenario or args.csv or args.llm:
            parser.error("--check-gemini is separate from scenario analysis and evaluation")
        record = check_gemini(model=args.model, store=Store(args.data_dir))
        content = record.model_dump_json(indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content + "\n", encoding="utf-8")
        print(content)
        return 0 if record.succeeded and record.output_validated else 2
    if args.evaluate or args.scenario:
        store = Store(args.data_dir)
        if args.evaluate:
            if args.llm:
                parser.error("--evaluate is deterministic; --llm requires --scenario")
            data = evaluate(store, repetitions=args.repetitions)
            if args.csv:
                args.csv.parent.mkdir(parents=True, exist_ok=True)
                args.csv.write_text(evaluation_csv(data), encoding="utf-8-sig")
            code = 0 if data["passed"] == data["total"] else 1
        else:
            name = list(SCENARIOS)[args.scenario - 1]
            result = Pipeline(model=args.model).run(get_scenario(name), use_llm=args.llm)
            store.save(result)
            data, code = result.model_dump(mode="json"), 0
        content = json.dumps(data, indent=2, ensure_ascii=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content + "\n", encoding="utf-8")
        print(content)
        return code
    from firewatch.gui import launch
    launch(args.data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
