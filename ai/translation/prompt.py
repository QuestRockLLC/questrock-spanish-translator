from ai.translation.glossary import Glossary


def build_system_prompt(glossary: Glossary) -> str:
    lines = [
        "Translate Spanish mortgage borrower speech into natural English.",
        "Preserve meaning.",
        "Use US mortgage terminology.",
        "Do not hallucinate content that was not said.",
        "Preserve numbers, loan amounts, interest rates, and dates exactly.",
        "",
        "Glossary (Spanish -> preferred English):",
    ]
    for term in glossary.terms:
        for es_phrase in term.es:
            lines.append(f"- {es_phrase} -> {term.preferred_en}")
    return "\n".join(lines)
