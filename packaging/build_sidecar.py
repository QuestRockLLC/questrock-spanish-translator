#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "packaging" / "dist" / "sidecar"
WORK = ROOT / "packaging" / "work"
SPEC = ROOT / "packaging" / "sidecar.spec"


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    if WORK.exists():
        shutil.rmtree(WORK)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(SPEC),
            "--noconfirm",
            f"--distpath={ROOT / 'packaging' / 'dist'}",
            f"--workpath={WORK}",
        ],
        check=True,
        cwd=ROOT,
    )
    config_dir = DIST / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "config" / "mortgage_glossary.json", config_dir / "mortgage_glossary.json")
    example = ROOT / ".env.example"
    if example.is_file():
        shutil.copy2(example, DIST / ".env.example")
    if sys.platform == "darwin":
        helper = ROOT / "native" / "macos" / "AudioTap"
        if not helper.is_file():
            subprocess.run([str(ROOT / "native" / "macos" / "build.sh")], check=True)
        shutil.copy2(helper, DIST / "AudioTap")
        (DIST / "AudioTap").chmod(0o755)
    print(f"sidecar bundle: {DIST}")


if __name__ == "__main__":
    main()
