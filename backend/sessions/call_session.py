from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from uuid import uuid4

import numpy as np

from ai.caption.quality import should_emit_transcription
from ai.inference.modal_client import CaptionResult, RemoteWhisperTranscriber
from ai.translation.translator import MortgageTranslator
from ai.vad.segmenter import Utterance, VadSegmenter
from ai.whisper.transcriber import WhisperTranscriber
from audio.factory import AudioCapture
from audio.types import AudioFrame
from backend.logging import get_logger
from backend.websocket.protocol import ErrorMessage, ServerMessage, Status, Transcript

_log = get_logger("questrock.session")

MIN_UTTERANCE_MS = 1000


def _next_frame(frames: Iterator[AudioFrame]) -> AudioFrame | None:
    return next(frames, None)


class CallSession:
    def __init__(
        self,
        *,
        call_session_id: str,
        capture: AudioCapture,
        device_id: str,
        emit: Callable[[ServerMessage], None],
        on_stop: Callable[[], None] | None = None,
        translator: MortgageTranslator,
        vad: VadSegmenter,
        whisper: WhisperTranscriber,
    ) -> None:
        self.call_session_id = call_session_id
        self.device_id = device_id
        self._capture = capture
        self._vad = vad
        self._whisper = whisper
        self._translator = translator
        self._emit = emit
        self._on_stop = on_stop
        self._stopped = False
        self._capture_finalized = False
        self._frames_seen = 0
        self._inferring = False
        self._queue: asyncio.Queue[Utterance | None] = asyncio.Queue()
        self._quiet_ms = 0

    async def run(self) -> None:
        if self._stopped:
            return
        worker = asyncio.create_task(self._transcribe_worker())
        try:
            self._status(
                "loading_model",
                detail=(
                    "Modal GPU"
                    if isinstance(self._whisper, RemoteWhisperTranscriber)
                    else "local Whisper"
                ),
            )
            warmup = getattr(self._whisper, "warmup", None)
            if callable(warmup):
                try:
                    await asyncio.to_thread(warmup)
                except Exception as exc:
                    _log.warning("modal warmup failed: %s", exc)
            self._capture.start(self.device_id)
            self._status("listening")
            frames = self._capture.frames()
            first = await asyncio.wait_for(
                asyncio.to_thread(_next_frame, frames),
                timeout=5,
            )
            if first is None:
                raise RuntimeError("system audio capture ended before any audio arrived")
            await self._handle_frame(first)
            while not self._stopped:
                frame = await asyncio.to_thread(_next_frame, frames)
                if frame is None:
                    break
                await self._handle_frame(frame)
        except TimeoutError:
            self._emit(
                ErrorMessage(
                    code="session",
                    message=(
                        "No system audio arrived. Keep Screen Recording enabled for "
                        "Electron and AudioTap, play sound through the Mac speakers "
                        "or current output device, then click Start again."
                    ),
                )
            )
        except Exception as exc:
            self._emit(
                ErrorMessage(
                    code="session",
                    message=str(exc),
                )
            )
        finally:
            await self._queue.put(None)
            await worker
            self._finalize_stop()

    async def _handle_frame(self, frame: AudioFrame) -> None:
        self._frames_seen += 1
        peak = _peak_level(frame.pcm_s16le)
        if (
            not self._inferring
            and self._queue.empty()
            and (self._frames_seen == 1 or self._frames_seen % 25 == 0)
        ):
            self._status("listening", detail=f"signal {peak:.0%}")
        result = self._vad.push(frame)
        utterances = list(result.finals or ((result.final,) if result.final else ()))
        if peak < 0.02:
            self._quiet_ms += frame.duration_ms
            if self._quiet_ms >= 500:
                flushed = self._vad.flush()
                if flushed is not None:
                    utterances.append(flushed)
                self._quiet_ms = 0
        else:
            self._quiet_ms = 0
        for utterance in utterances:
            self._enqueue(utterance)

    def _enqueue(self, utterance: Utterance) -> None:
        duration_ms = utterance.t1_ms - utterance.t0_ms
        if duration_ms < MIN_UTTERANCE_MS:
            _log.info("skip short utterance duration_ms=%s", duration_ms)
            return
        _log.info(
            "queued utterance duration_ms=%s bytes=%s",
            duration_ms,
            len(utterance.pcm_s16le),
        )
        if self._inferring:
            dropped = 0
            saw_stop = False
            while True:
                try:
                    item = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if item is None:
                    saw_stop = True
                else:
                    dropped += 1
            if dropped:
                _log.info("drop stale utterances count=%s", dropped)
            self._queue.put_nowait(utterance)
            if saw_stop:
                self._queue.put_nowait(None)
            return
        self._queue.put_nowait(utterance)

    async def _transcribe_worker(self) -> None:
        while True:
            utterance = await self._queue.get()
            if utterance is None:
                return
            if self._stopped:
                continue
            try:
                await self._transcribe_final(utterance)
            except Exception as exc:
                self._emit(
                    ErrorMessage(
                        code="session",
                        message=str(exc),
                    )
                )
                self._finish_inference()

    async def _transcribe_final(self, utterance: Utterance) -> None:
        duration_ms = utterance.t1_ms - utterance.t0_ms
        waiting = self._queue.qsize()
        self._inferring = True
        self._status(
            "transcribing",
            detail=f"{waiting} waiting" if waiting else None,
        )
        _log.info(
            "transcribe start duration_ms=%s bytes=%s waiting=%s",
            duration_ms,
            len(utterance.pcm_s16le),
            waiting,
        )
        caption_fn = getattr(self._whisper, "caption", None)
        if callable(caption_fn):
            caption = await asyncio.to_thread(caption_fn, utterance.pcm_s16le)
            await self._emit_caption(utterance, duration_ms, caption)
            return

        transcription = await asyncio.to_thread(
            lambda: self._whisper.transcribe(utterance.pcm_s16le, partial=False),
        )
        if self._stopped:
            self._inferring = False
            return
        if transcription is None:
            _log.info("transcribe returned no text")
            self._finish_inference()
            return

        spanish = transcription.text
        if not should_emit_transcription(
            spanish,
            transcription.confidence,
            duration_ms,
            partial=False,
        ):
            _log.info("transcribe dropped by quality gate")
            self._finish_inference()
            return

        self._status("translating")
        translation = await self._translator.translate(spanish, retries=1, max_tokens=256)
        if self._stopped:
            self._inferring = False
            return

        self._emit(
            Transcript(
                call_session_id=self.call_session_id,
                id=str(uuid4()),
                is_final=True,
                original_language="es",
                original_text=spanish,
                translated_text=translation.translated_text or spanish,
                confidence=transcription.confidence,
                t0_ms=utterance.t0_ms,
                t1_ms=utterance.t1_ms,
            )
        )
        self._finish_inference()

    async def _emit_caption(
        self,
        utterance: Utterance,
        duration_ms: int,
        caption: CaptionResult | None,
    ) -> None:
        if self._stopped:
            self._inferring = False
            return
        if caption is None:
            _log.info("caption returned no text")
            self._finish_inference()
            return
        spanish = caption.text
        if not should_emit_transcription(
            spanish,
            caption.confidence,
            duration_ms,
            partial=False,
        ):
            _log.info("caption dropped by quality gate")
            self._finish_inference()
            return
        self._emit(
            Transcript(
                call_session_id=self.call_session_id,
                id=str(uuid4()),
                is_final=True,
                original_language="es",
                original_text=spanish,
                translated_text=caption.translated_text or spanish,
                confidence=caption.confidence,
                t0_ms=utterance.t0_ms,
                t1_ms=utterance.t1_ms,
            )
        )
        self._finish_inference()

    def _finish_inference(self) -> None:
        self._inferring = False
        if self._stopped:
            return
        waiting = self._queue.qsize()
        if waiting:
            self._status("transcribing", detail=f"{waiting} waiting")
        else:
            self._status("listening")

    def _finalize_stop(self) -> None:
        if self._capture_finalized:
            return
        self._capture_finalized = True
        try:
            self._capture.stop()
        finally:
            if self._on_stop is not None:
                self._on_stop()
            self._emit(
                Status(
                    call_session_id=self.call_session_id,
                    state="idle",
                )
            )

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._finalize_stop()

    def _status(self, state: str, detail: str | None = None) -> None:
        if self._stopped:
            return
        self._emit(
            Status(call_session_id=self.call_session_id, state=state, detail=detail)
        )


def _peak_level(pcm_s16le: bytes) -> float:
    if not pcm_s16le:
        return 0.0
    samples = np.frombuffer(pcm_s16le, dtype="<i2").astype(np.float32)
    peak = float(np.max(np.abs(samples)))
    return min(1.0, peak / 32768.0)
