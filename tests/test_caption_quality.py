from ai.caption.quality import (
    should_emit_transcription,
    should_translate,
    translation_too_expansive,
)


def test_short_fragment_is_not_emitted():
    assert not should_emit_transcription("a la", 0.0, 1200, partial=False)
    assert not should_translate("a la", 0.0, partial=False)
    assert should_emit_transcription("Hola mundo", 0.8, 1200, partial=False)


def test_two_word_partial_is_emitted():
    assert should_emit_transcription("Hola mundo", 0.8, 800, partial=True)
    assert should_translate("Hola mundo", 0.8, partial=True)


def test_substantial_speech_is_emitted_and_translated():
    text = "yo me voy a hablar tranquilamente y como estas estos dias"
    assert should_emit_transcription(text, 0.28, 2500, partial=False)
    assert should_translate(text, 0.28, partial=False)


def test_expansive_translation_is_rejected():
    spanish = "a la"
    english = (
        "Hello, this is Name calling from Company about cash-out refinance "
        "and preapproval with closing costs."
    )
    assert translation_too_expansive(spanish, english)
