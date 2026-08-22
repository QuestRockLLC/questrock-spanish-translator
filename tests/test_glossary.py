from pathlib import Path

from ai.translation.glossary import load_glossary
from ai.translation.prompt import build_system_prompt


def test_seed_terms_present():
    glossary = load_glossary(Path("config/mortgage_glossary.json"))
    ens = {t.preferred_en for t in glossary.terms}
    assert "cash-out refinance" in ens
    assert "loan officer" in ens
    assert "closing costs" in ens
    assert "interest rate" in ens
    assert "monthly payment" in ens
    assert "down payment" in ens
    assert "preapproval" in ens


def test_prompt_contains_preferred_english_and_rules():
    glossary = load_glossary(Path("config/mortgage_glossary.json"))
    prompt = build_system_prompt(glossary)
    assert "cash-out refinance" in prompt
    assert "sacar dinero de mi casa" in prompt
    assert "Do not hallucinate" in prompt
    assert "Preserve numbers" in prompt
