import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GlossaryTerm:
    en: str
    es: list[str]
    preferred_en: str


@dataclass(frozen=True)
class Glossary:
    terms: list[GlossaryTerm]


def load_glossary(path: Path) -> Glossary:
    data = json.loads(path.read_text(encoding="utf-8"))
    terms = [
        GlossaryTerm(
            en=entry["en"],
            es=entry["es"],
            preferred_en=entry["preferred_en"],
        )
        for entry in data["terms"]
    ]
    return Glossary(terms=terms)
