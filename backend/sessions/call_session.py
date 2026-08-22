from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from uuid import uuid4

from ai.translation.translator import MortgageTranslator
from ai.vad.segmenter import Utterance, VadSegmenter
from ai.whisper.transcriber import WhisperTranscriber
from audio.factory import AudioCapture
from audio.types import AudioFrame
from backend.websocket.protocol import ServerMessage, Status, Transcript


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

    async def run(self) -> None:
        if self._stopped:
            return
        try:
            self._status("loading_model")
            self._capture.start(self.device_id)
            self._status("listening")
            frames = self._capture.frames()
            while not self._stopped:
                frame = await asyncio.to_thread(_next_frame, frames)
                if frame is None:
                    break
                utterance = self._vad.push(frame)
                if utterance is not None:
                    await self._process(utterance)
        finally:
            self.stop()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        try:
            self._capture.stop()
        finally:
            if self._on_stop is not None:
                self._on_stop()

    async def _process(self, utterance: Utterance) -> None:
        self._status("transcribing")
        transcription = await asyncio.to_thread(
            self._whisper.transcribe,
            utterance.pcm_s16le,
        )
        if transcription is None:
            return

        self._status("translating")
        translation = await self._translator.translate(transcription.text)
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

    def _status(self, state: str) -> None:
        self._emit(Status(call_session_id=self.call_session_id, state=state))
