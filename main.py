"""GUI by default; command-line evaluation works without a display."""
import argparse
import json
from pathlib import Path

from firewatch.evaluation import evaluate
from firewatch.pipeline import Pipeline
from firewatch.scenarios import SCENARIOS, get_scenario
from firewatch.storage import Store


def main():
    parser = argparse.ArgumentParser(description="FireWatch AI educational prototype")
    parser.add_argument("--evaluate", action="store_true", help="Run the 10 synthetic reference scenarios")
    parser.add_argument("--scenario", type=int, choices=range(1, 11), help="Analyze a catalogue scenario without GUI")
    parser.add_argument("--llm", action="store_true", help="Use optional Gemini for a single CLI scenario")
    parser.add_argument("--output", type=Path, help="Write CLI output JSON")
    parser.add_argument("--data-dir", default="data", help="SQLite and trace destination")
    args = parser.parse_args()
    if args.evaluate or args.scenario:
        store = Store(args.data_dir)
        if args.evaluate:
            if args.llm:
                parser.error("--evaluate is deterministic; --llm requires --scenario")
            data = evaluate(store)
            code = 0 if data["passed"] == data["total"] else 1
        else:
            name = list(SCENARIOS)[args.scenario - 1]
            result = Pipeline().run(get_scenario(name), use_llm=args.llm)
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
