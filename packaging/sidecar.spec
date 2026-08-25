# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

ROOT = Path(SPECPATH).resolve().parent

datas: list = [
    (str(ROOT / "config" / "mortgage_glossary.json"), "config"),
    (str(ROOT / ".env.example"), "."),
]
binaries: list = []
hiddenimports: list = [
    "backend.main",
    "backend.sessions.manager",
    "audio.macos",
    "audio.windows",
    "silero_vad",
    "silero_vad.data",
    "silero_vad.model",
    "silero_vad.utils_vad",
    "ctranslate2",
    "faster_whisper",
]

for pkg in (
    "silero_vad",
    "faster_whisper",
    "ctranslate2",
    "onnxruntime",
    "av",
    "tokenizers",
    "huggingface_hub",
):
    collected_datas, collected_binaries, collected_hidden = collect_all(pkg)
    datas += collected_datas
    binaries += collected_binaries
    hiddenimports += collected_hidden

binaries += collect_dynamic_libs("ctranslate2")

if sys.platform == "win32":
    hiddenimports += ["pyaudiowpatch", "comtypes"]
    try:
        w_datas, w_bins, w_hidden = collect_all("pyaudiowpatch")
        datas += w_datas
        binaries += w_bins
        hiddenimports += w_hidden
    except Exception:
        pass

a = Analysis(
    [str(ROOT / "packaging" / "sidecar_entry.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="questrock-sidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="sidecar",
)
