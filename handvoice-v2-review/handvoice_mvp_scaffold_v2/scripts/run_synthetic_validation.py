from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.validation.synthetic import run_synthetic_validation  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic, non-clinical HandVoice engineering validation.",
    )
    parser.add_argument("--replicates", type=int, default=20)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("validation/results/synthetic_validation.json"),
    )
    args = parser.parse_args()

    result = run_synthetic_validation(replicates=args.replicates)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
