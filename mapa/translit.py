"""Preslovljavanje srpske ćirilice u latinicu i normalizacija naziva opština."""

import unicodedata

_CYR_TO_LAT = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Ђ": "Đ", "Е": "E",
    "Ж": "Ž", "З": "Z", "И": "I", "Ј": "J", "К": "K", "Л": "L", "Љ": "Lj",
    "М": "M", "Н": "N", "Њ": "Nj", "О": "O", "П": "P", "Р": "R", "С": "S",
    "Т": "T", "Ћ": "Ć", "У": "U", "Ф": "F", "Х": "H", "Ц": "C", "Ч": "Č",
    "Џ": "Dž", "Ш": "Š",
}
_CYR_TO_LAT.update({k.lower(): v.lower() for k, v in _CYR_TO_LAT.items()})


def to_latin(text: str) -> str:
    return "".join(_CYR_TO_LAT.get(ch, ch) for ch in text)


def _key(text: str) -> str:
    """Ključ za poređenje: latinica, bez dijakritika, mala slova, bez prefiksa."""
    text = to_latin(text).lower().replace("đ", "dj")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    for prefix in ("gradska opstina ", "opstina ", "go "):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return " ".join(text.split())


def canonical_municipality(name: str | None, known: list[str]) -> str | None:
    """Vraća naziv iz `known` koji odgovara `name` (ćirilica ili latinica), inače None."""
    if not name:
        return None
    wanted = _key(name)
    for candidate in known:
        if _key(candidate) == wanted:
            return candidate
    return None
