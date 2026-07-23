"""Train and validate the HandVoice temporal motor-event model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.video.motor_model import (  # noqa: E402
    load_motor_training_manifest,
    train_temporal_motor_model,
)


def _git_state() -> tuple[str | None, bool | None]:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=ROOT,
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()
        )
        return revision, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Train a compact motor-event model from blinded annotations and "
            "computer-vision landmark tracks. A non-passing artifact is written "
            "for analysis but cannot be enabled in HandVoice."
        )
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("models/development/motor-event.json"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("validation/results/motor_model_training.json"),
    )
    parser.add_argument("--epochs", type=int, default=1000)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    args = parser.parse_args()

    revision, dirty = _git_state()
    try:
        cases, provenance, _ = load_motor_training_manifest(
            args.manifest,
            data_root=args.data_root,
            software_revision=revision,
            working_tree_dirty=dirty,
        )
        artifact, report = train_temporal_motor_model(
            cases,
            provenance=provenance,
            model_version=args.model_version,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"Motor model training failed: {error}", file=sys.stderr)
        return 2

    args.artifact.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.artifact.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["release_gate_passed"]:
        print(f"Release-eligible artifact: {args.artifact}")
        return 0
    print(
        "Artifact is NOT release-eligible and HandVoice will reject it. "
        "Complete the human-recording sample and agreement gates.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
