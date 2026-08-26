import httpx
import pytest

from ai.inference.modal_client import (
    ModalInferenceClient,
    ModalInferenceConfig,
    RemoteMortgageTranslator,
    RemoteWhisperTranscriber,
)
from backend.sessions.manager import production_dependencies
from backend.settings import Settings


def test_remote_transcribe_parses_json_response() -> None:
    pcm = b"\x00\x01" * 160

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/transcribe"
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(
            200,
            json={"text": "Hola mundo", "confidence": 0.82},
        )

    client = ModalInferenceClient(
        ModalInferenceConfig(
            base_url="https://example.modal.run",
            token="test-token",
            sync_transport=httpx.MockTransport(handler),
        )
    )
    result = client.transcribe(pcm, partial=True)

    assert result is not None
    assert result.text == "Hola mundo"
    assert result.confidence == 0.82


@pytest.mark.asyncio
async def test_remote_translate_parses_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/translate"
        return httpx.Response(
            200,
            json={
                "original_text": "Hola",
                "translated_text": "Hello",
            },
        )

    client = ModalInferenceClient(
        ModalInferenceConfig(
            base_url="https://example.modal.run/",
            token="secret",
            async_transport=httpx.MockTransport(handler),
        )
    )
    result = await client.translate("Hola", retries=0, max_tokens=96)

    assert result.original_text == "Hola"
    assert result.translated_text == "Hello"


def test_remote_transcribe_timeout_is_a_runtime_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        raise httpx.ReadTimeout("timed out")

    client = ModalInferenceClient(
        ModalInferenceConfig(
            base_url="https://example.modal.run",
            token="test-token",
            timeout_s=0.01,
            sync_transport=httpx.MockTransport(handler),
        )
    )
    with pytest.raises(RuntimeError, match="Modal transcribe timed out"):
        client.transcribe(b"\x00\x01" * 160)


def test_remote_caption_parses_combined_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/caption"
        return httpx.Response(
            200,
            json={
                "text": "Hola mundo",
                "confidence": 0.9,
                "translated_text": "Hello world",
            },
        )

    client = ModalInferenceClient(
        ModalInferenceConfig(
            base_url="https://example.modal.run",
            token="test-token",
            sync_transport=httpx.MockTransport(handler),
        )
    )
    result = client.caption(b"\x00\x01" * 160)
    assert result is not None
    assert result.text == "Hola mundo"
    assert result.translated_text == "Hello world"
    assert result.confidence == 0.9


def test_remote_warmup_hits_health() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"ok": True})

    client = ModalInferenceClient(
        ModalInferenceConfig(
            base_url="https://example.modal.run",
            token="test-token",
            sync_transport=httpx.MockTransport(handler),
        )
    )
    client.warmup()
    assert seen == ["/health"]


def test_remote_transcribe_treats_empty_payload_as_silence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json=None)

    client = ModalInferenceClient(
        ModalInferenceConfig(
            base_url="https://example.modal.run",
            token="test-token",
            sync_transport=httpx.MockTransport(handler),
        )
    )
    assert client.transcribe(b"\x00\x01" * 160) is None


def test_remote_loaders_match_local_interface() -> None:
    whisper = RemoteWhisperTranscriber.load(
        "small",
        base_url="https://example.modal.run",
        token="secret",
    )
    translator = RemoteMortgageTranslator.load(
        base_url="https://example.modal.run",
        token="secret",
    )
    assert whisper._model_name == "small"  # noqa: SLF001
    assert hasattr(translator, "translate")


def test_production_dependencies_use_modal_when_configured() -> None:
    deps = production_dependencies(
        Settings(
            questrock_modal_url="https://example.modal.run",
            questrock_modal_token="secret",
            whisper_model="small",
        )
    )
    whisper = deps.load_whisper()
    translator = deps.load_translator()
    assert isinstance(whisper, RemoteWhisperTranscriber)
    assert isinstance(translator, RemoteMortgageTranslator)
