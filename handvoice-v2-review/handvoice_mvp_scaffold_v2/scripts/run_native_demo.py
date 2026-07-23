"""Run the loopback-only native demo with state kept under .native_demo."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
STATE_ROOT = ROOT / ".native_demo"


def configure_ffmpeg_path() -> None:
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return
    package_root = (
        Path(local_app_data)
        / "Microsoft"
        / "WinGet"
        / "Packages"
        / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    )
    candidates = sorted(
        package_root.glob("ffmpeg-*-full_build/bin"),
        reverse=True,
    )
    if candidates:
        os.environ["PATH"] = f"{candidates[0]}{os.pathsep}{os.environ.get('PATH', '')}"


os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
configure_ffmpeg_path()
os.environ["HANDVOICE_ENVIRONMENT"] = "native-demo"
os.environ["HANDVOICE_BOOTSTRAP_KEY"] = (STATE_ROOT / "operator-key.txt").read_text(
    encoding="utf-8"
).strip()
os.environ["HANDVOICE_DEMO_BYPASS_OPERATOR_AUTH"] = "true"
os.environ["HANDVOICE_DATABASE_URL"] = "sqlite:///./handvoice-native-demo.db"
os.environ["HANDVOICE_STORAGE_ROOT"] = ".native_demo/storage"

import uvicorn  # noqa: E402


if __name__ == "__main__":
    uvicorn.run("services.api.app.main:app", host="127.0.0.1", port=8000)
