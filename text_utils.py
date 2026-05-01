import re
import numpy as np
from difflib import SequenceMatcher
from typing import Any, Dict, Optional

from sentence_transformers import SentenceTransformer

from config import (
    PAGE_PAT,
    DIGITS_PAT,
    PLACE_PATS,
)

model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

_emb_cache: Dict[str, np.ndarray] = {}


def embed(text: str) -> np.ndarray:
    if text not in _emb_cache:
        _emb_cache[text] = model.encode(text, normalize_embeddings=True)
    return _emb_cache[text]


def cosim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def norm(text: Any) -> str:
    text = str(text).replace("\xa0", " ")
    text = re.sub(r"Page\s+\d+\s+sur\s+\d+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def normh(text: Any) -> str:
    text = norm(text).lower()

    replacements = [
        ("éèêë", "e"),
        ("àâä", "a"),
        ("îï", "i"),
        ("ôö", "o"),
        ("ùûü", "u"),
        ("ç", "c"),
    ]

    for chars, replacement in replacements:
        for char in chars:
            text = text.replace(char, replacement)

    return text


def normk(text: Optional[str]) -> str:
    return normh(text or "")


def sem(text: Optional[str]) -> str:
    text = normh(text or "")
    text = re.sub(r"\blot\.?\b", "lot", text)
    text = re.sub(r"\b0+(\d+)\b", r"\1", text)
    text = re.sub(r"[^a-z0-9+\- ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similar(a: str, b: str, threshold: float = 0.8) -> bool:
    return SequenceMatcher(None, a, b).ratio() >= threshold


def is_noise(text: str) -> bool:
    text = norm(text)
    return not text or bool(PAGE_PAT.match(text)) or bool(DIGITS_PAT.match(text))


def lot_code(text: Optional[str]) -> str:
    text = normh(text or "")

    match = re.search(
        r"lot\.?\s*(\d+(?:\.[a-z])?(?:\s*et\s*\d+(?:\.[a-z])?)?)",
        text,
    )

    return f"lot {match.group(1)}" if match else ""


def lot_name_key(text: Optional[str]) -> str:
    text = normh(text or "")

    text = re.sub(
        r"\blot\.?\s*0*\d+(?:\.[a-z])?(?:\s*et\s*0*\d+(?:\.[a-z])?)?",
        " ",
        text,
    )

    text = re.sub(r"[^a-z0-9]+", " ", text)

    stop = {
        "lot", "et", "de", "du", "des", "la", "le", "les",
        "a", "au", "aux", "d", "l",
    }

    return " ".join(
        token for token in text.split()
        if token not in stop and len(token) > 1
    )


def lot_key(text: Optional[str]) -> str:
    return f"{lot_code(text)} {lot_name_key(text)}".strip()


def same_lot(a: Optional[str], b: Optional[str], threshold: float = 0.88) -> bool:
    code_a, code_b = lot_code(a), lot_code(b)

    if not code_a or code_a != code_b:
        return False

    name_a, name_b = lot_name_key(a), lot_name_key(b)

    return not name_a or not name_b or similar(name_a, name_b, threshold)


def find_place(text: str) -> Optional[str]:
    for pattern in PLACE_PATS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def location_tokens(location: Optional[str]) -> set:
    text = normh(location or "")
    tokens = set()

    for match in re.finditer(r"\bcage\s+[a-z0-9]+\b", text):
        tokens.add(match.group(0))

    for match in re.finditer(r"\br\s*\+\s*\d+\b", text):
        tokens.add(re.sub(r"\s+", "", match.group(0)))

    if re.search(r"\brdc\b", text):
        tokens.add("rdc")

    if re.search(r"\b(ss|sous sol|sous-sol)\b", text):
        tokens.add("ss")

    for match in re.finditer(
        r"\bfa[cç]ade\s+(so|se|no|ne|nord|sud|est|ouest)\b",
        text,
    ):
        tokens.add(match.group(0))

    return tokens


def compatible_locations(loc_a: Optional[str], loc_b: Optional[str]) -> bool:
    tok_a = location_tokens(loc_a)
    tok_b = location_tokens(loc_b)

    if not tok_a or not tok_b:
        return True

    return tok_a.issubset(tok_b) or tok_b.issubset(tok_a)


def best_location(loc_a: Optional[str], loc_b: Optional[str]) -> Optional[str]:
    if len(location_tokens(loc_b)) > len(location_tokens(loc_a)):
        return loc_b
    return loc_a


def merge_loc(lot: Any, section: Any = None, real_loc: Any = None) -> Optional[str]:
    parts = []

    for value in (lot, section, real_loc):
        value = norm(value) if value else None

        if value and all(normk(value) != normk(existing) for existing in parts):
            parts.append(value)

    return " - ".join(parts) if parts else None


def find_similar_task(
    task_name,
    location,
    tasks_index: Dict,
    task_thr: float = 0.82,
) -> Optional[Any]:
    task_text = sem(task_name)

    task_emb = embed(task_text)

    for key, entry in tasks_index.items():
        ex_task = sem(entry.get("task"))

        if not ex_task:
            continue

        if not compatible_locations(entry.get("location"), location):
            continue

        if cosim(task_emb, embed(ex_task)) >= task_thr:
            return key

    return None