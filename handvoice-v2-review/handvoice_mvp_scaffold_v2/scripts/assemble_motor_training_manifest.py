"""Assemble a motor training manifest from blinded local study files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.video.motor_study import assemble_motor_training_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify source videos, landmark tracks and independent blinded-rater "
            "exports, then assemble the frozen motor training manifest."
        )
    )
    parser.add_argument("plan", type=Path)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        manifest = assemble_motor_training_manifest(
            args.plan,
            data_root=args.data_root,
        )
    except (OSError, TypeError, ValueError) as error:
        print(f"Motor study assembly failed: {error}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"Assembled {len(manifest['cases'])} hash-verified cases: {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
