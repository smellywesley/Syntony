from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.validation.agreement import (  # noqa: E402
    evaluate_agreement_manifest,
    load_agreement_manifest,
)


def _software_provenance(manifest: Path) -> dict[str, object]:
    manifest_sha256 = hashlib.sha256(manifest.read_bytes()).hexdigest()
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
    except (OSError, subprocess.CalledProcessError):
        revision = "unavailable"
        dirty = None
    return {
        "manifest_sha256": manifest_sha256,
        "software_revision": revision,
        "working_tree_dirty": dirty,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Score blinded HandVoice motor/speech annotations against detector "
            "events using the frozen handvoice-agreement-v1 gates."
        ),
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("validation/results/measurement_agreement.json"),
    )
    args = parser.parse_args()

    try:
        manifest = load_agreement_manifest(args.manifest)
        report = evaluate_agreement_manifest(manifest)
        report["provenance"] = _software_provenance(args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Agreement validation failed: {error}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["human_recording_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
