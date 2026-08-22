import pytest

from ai.translation.translator import MortgageTranslator, TranslationResult


class FakeCompletions:
    def __init__(self, create):
        self.create = create


class FakeChat:
    def __init__(self, create):
        self.completions = FakeCompletions(create)


class FakeOpenAI:
    def __init__(self, create):
        self.chat = FakeChat(create)


@pytest.mark.asyncio
async def test_translate_returns_model_text():
    async def create(**kwargs):
        assert kwargs["model"] == "gpt-4.1-mini"
        assert kwargs["temperature"] == 0

        class Choice:
            message = type("M", (), {"content": "I want to take cash out from my home."})()

        return type("R", (), {"choices": [Choice()]})()

    translator = MortgageTranslator(
        client=FakeOpenAI(create),
        model="gpt-4.1-mini",
        system_prompt="sys",
        timeout_s=8,
    )
    result = await translator.translate("Quiero sacar dinero de mi casa.")
    assert result == TranslationResult(
        original_text="Quiero sacar dinero de mi casa.",
        translated_text="I want to take cash out from my home.",
    )


@pytest.mark.asyncio
async def test_translate_timeout_keeps_spanish():
    async def create(**kwargs):
        raise TimeoutError("openai")

    translator = MortgageTranslator(
        client=FakeOpenAI(create),
        model="gpt-4.1-mini",
        system_prompt="sys",
        timeout_s=8,
    )
    result = await translator.translate("Hola")
    assert result.original_text == "Hola"
    assert result.translated_text is None
