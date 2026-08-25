from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from uuid import uuid4

import numpy as np

from ai.translation.translator import MortgageTranslator
from ai.vad.segmenter import Utterance, VadSegmenter
from ai.whisper.transcriber import WhisperTranscriber
from audio.factory import AudioCapture
from audio.types import AudioFrame
from backend.websocket.protocol import ErrorMessage, ServerMessage, Status, Transcript


def _next_frame(frames: Iterator[AudioFrame]) -> AudioFrame | None:
    return next(frames, None)


class CallSession:
    def __init__(
        self,
        *,
        call_session_id: str,
        device_id: str,
        capture: AudioCapture,
        vad: VadSegmenter,
        whisper: WhisperTranscriber,
        translator: MortgageTranslator,
        emit: Callable[[ServerMessage], None],
        on_stop: Callable[[], None] | None = None,
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
        self._frames_seen = 0

    async def run(self) -> None:
        if self._stopped:
            return
        try:
            self._status("loading_model")
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
            self.stop()

    async def _handle_frame(self, frame: AudioFrame) -> None:
        self._frames_seen += 1
        if self._frames_seen == 1 or self._frames_seen % 25 == 0:
            level = _peak_level(frame.pcm_s16le)
            self._status("listening", detail=f"signal {level:.0%}")
        utterance = self._vad.push(frame)
        if utterance is None:
            return
        try:
            await self._process(utterance)
        except Exception as exc:
            self._emit(
                ErrorMessage(
                    code="session",
                    message=str(exc),
                )
            )
            self._status("listening")

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
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

    async def _process(self, utterance: Utterance) -> None:
        if self._stopped:
            return
        self._status("transcribing")
        transcription = await asyncio.to_thread(
            self._whisper.transcribe,
            utterance.pcm_s16le,
        )
        if self._stopped or transcription is None:
            return

        self._status("translating")
        translation = await self._translator.translate(transcription.text)
        if self._stopped:
            return
        self._emit(
            Transcript(
                call_session_id=self.call_session_id,
                id=str(uuid4()),
                is_final=True,
                original_language="es",
                original_text=transcription.text,
                translated_text=translation.translated_text,
                confidence=transcription.confidence,
                t0_ms=utterance.t0_ms,
                t1_ms=utterance.t1_ms,
            )
        )

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
