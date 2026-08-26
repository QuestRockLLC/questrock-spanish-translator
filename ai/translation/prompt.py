from ai.translation.glossary import Glossary


def build_system_prompt(glossary: Glossary) -> str:
    terms = "; ".join(
        f"{term.es[0]}={term.preferred_en}"
        for term in glossary.terms
        if term.es
    )
    return (
        "Translate the Spanish message to English literally. "
        "Use only what was said. Do not add sales language or extra sentences. "
        "If the message is incomplete, translate the fragment only. "
        "English only. Keep numbers. "
        f"Terms: {terms}"
    )
