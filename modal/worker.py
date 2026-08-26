"""QuestRock GPU inference on Modal (Whisper + OpenAI translation)."""

from __future__ import annotations

import asyncio
import base64
import os
import threading
from pathlib import Path

import modal

APP_NAME = "questrock-inference"
REPO_ROOT = Path(__file__).resolve().parent.parent
INFERENCE_SECRET = modal.Secret.from_name("questrock-inference")

image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04",
        add_python="3.12",
    )
    .entrypoint([])
    .uv_pip_install(
        "faster-whisper>=1.1",
        "nvidia-cublas-cu12",
        "nvidia-cudnn-cu12==9.*",
        "numpy>=2.0",
        "openai>=1.50",
        "fastapi>=0.115",
        "pydantic>=2.0",
    )
    .env({"PYTHONPATH": "/root", "LD_LIBRARY_PATH": "/usr/local/cuda/lib64:/usr/local/nvidia/lib"})
    .add_local_dir(str(REPO_ROOT / "ai"), remote_path="/root/ai", copy=True)
    .add_local_dir(str(REPO_ROOT / "config"), remote_path="/root/config", copy=True)
)

app = modal.App(APP_NAME, image=image)

_whisper_lock = threading.Lock()
_whisper = None
_translator = None


def _expected_token() -> str:
    return os.environ.get("QUESTROCK_MODAL_TOKEN", "").strip()


def _verify_bearer(authorization: str | None) -> None:
    from fastapi import HTTPException

    expected = _expected_token()
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=403, detail="Invalid bearer token")


def _load_models() -> None:
    global _whisper, _translator
    if _whisper is not None and _translator is not None:
        return
    with _whisper_lock:
        if _whisper is not None and _translator is not None:
            return
        from faster_whisper import WhisperModel
        from openai import AsyncOpenAI

        from ai.translation.glossary import load_glossary
        from ai.translation.prompt import build_system_prompt
        from ai.translation.translator import MortgageTranslator

        model_name = os.environ.get("WHISPER_MODEL", "small")
        print(f"loading whisper model={model_name}", flush=True)
        _whisper = WhisperModel(
            model_name,
            device="cuda",
            compute_type="float16",
            num_workers=1,
        )
        glossary = load_glossary(Path("/root/config/mortgage_glossary.json"))
        _translator = MortgageTranslator(
            client=AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"]),
            model=os.environ.get("OPENAI_TRANSLATION_MODEL", "gpt-4.1-mini"),
            system_prompt=build_system_prompt(glossary),
        )
        print("whisper ready", flush=True)


def _transcribe_pcm(pcm: bytes):
    from ai.whisper.decode import transcribe_pcm

    _load_models()
    assert _whisper is not None
    with _whisper_lock:
        print(f"transcribe start bytes={len(pcm)}", flush=True)
        result = transcribe_pcm(_whisper, pcm)
        if result is None:
            print("transcribe empty", flush=True)
        else:
            print(f"transcribe done chars={len(result.text)}", flush=True)
        return result


@app.function(
    gpu="T4",
    secrets=[INFERENCE_SECRET],
    timeout=120,
    scaledown_window=300,
)
@modal.concurrent(max_inputs=2)
@modal.asgi_app()
def web_app():
    from fastapi import FastAPI, Header, HTTPException, Response

    _load_models()
    web = FastAPI(title="QuestRock Inference")

    @web.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @web.post("/v1/caption")
    async def caption(
        data: dict,
        authorization: str | None = Header(default=None),
    ):
        _verify_bearer(authorization)
        pcm_b64 = data.get("pcm_b64")
        if not isinstance(pcm_b64, str) or not pcm_b64:
            raise HTTPException(status_code=400, detail="pcm_b64 is required")
        pcm = base64.b64decode(pcm_b64, validate=True)
        result = await asyncio.to_thread(_transcribe_pcm, pcm)
        if result is None:
            return Response(status_code=204)
        assert _translator is not None
        try:
            translation = await _translator.translate(
                result.text,
                retries=1,
                max_tokens=256,
            )
            translated = translation.translated_text or result.text
        except Exception as exc:
            print(f"translate failed: {exc}", flush=True)
            translated = result.text
        return {
            "text": result.text,
            "confidence": result.confidence,
            "translated_text": translated,
        }

    @web.post("/v1/transcribe")
    async def transcribe(
        data: dict,
        authorization: str | None = Header(default=None),
    ):
        _verify_bearer(authorization)
        pcm_b64 = data.get("pcm_b64")
        if not isinstance(pcm_b64, str) or not pcm_b64:
            raise HTTPException(status_code=400, detail="pcm_b64 is required")
        pcm = base64.b64decode(pcm_b64, validate=True)
        result = await asyncio.to_thread(_transcribe_pcm, pcm)
        if result is None:
            return Response(status_code=204)
        return {"text": result.text, "confidence": result.confidence}

    @web.post("/v1/translate")
    async def translate(
        data: dict,
        authorization: str | None = Header(default=None),
    ):
        _verify_bearer(authorization)
        spanish = data.get("spanish")
        if not isinstance(spanish, str) or not spanish.strip():
            raise HTTPException(status_code=400, detail="spanish is required")
        _load_models()
        assert _translator is not None
        retries = data.get("retries", 1)
        max_tokens = data.get("max_tokens")
        if not isinstance(retries, int):
            retries = 1
        if max_tokens is not None and not isinstance(max_tokens, int):
            max_tokens = None
        result = await _translator.translate(
            spanish,
            retries=retries,
            max_tokens=max_tokens,
        )
        return {
            "original_text": result.original_text,
            "translated_text": result.translated_text,
        }

    return web
