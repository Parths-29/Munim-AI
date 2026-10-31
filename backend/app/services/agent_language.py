"""Deterministic Hinglish/English helpers for the voice agent: wake phrase, yes/no, spoken numbers."""

import re

from app.services.ledger import normalize_alias
from app.services.units import NUMBER_WORDS, ascii_digits

WAKE = re.compile(
    r"^\s*(?:(?:hey|hi|hello|ok|okay|oye|arre|suno|he|हे|अरे|सुनो)[\s,]+)?(?:munim\s+ji|muneem\s+ji|munimji|munim|muneem|मुनीम\s+जी|मुनीम)(?=$|[\s,!.:-])[\s,!.:-]*",
    re.I,
)
YES = {"haan", "haa", "ha", "han", "haanji", "haan ji", "ji haan", "yes", "yeah", "yep", "confirm", "confirmed", "kar do", "kardo",
       "kar dijiye", "theek hai", "thik hai", "ok", "okay", "sahi hai", "bilkul", "done", "save", "save karo", "likh do",
       "हाँ", "हां", "हा", "ठीक है", "जी हाँ", "कर दो", "हो", "होय", "hoy", "ho"}
NO = {"nahi", "nahin", "na", "no", "nope", "cancel", "mat karo", "rehne do", "rahne do", "galat", "wrong", "ruko", "stop",
      "नहीं", "नही", "ना", "रहने दो", "मत करो", "नको", "nako"}

HINDI_UNITS = {**{k: v for k, v in NUMBER_WORDS.items() if v < 100},
               "ikkis": 21, "bais": 22, "teis": 23, "chaubis": 24, "chhabbis": 26, "sattais": 27, "atthais": 28, "untees": 29,
               "pachpan": 55, "saath": 60, "sattar": 70, "assi": 80, "nabbe": 90, "pachattar": 75, "paintis": 35, "paintalis": 45,
               "dedh": 1.5, "dhai": 2.5, "dhaai": 2.5, "aadha": 0.5}
MULTIPLIERS = {"sau": 100, "so": 100, "hundred": 100, "hazaar": 1000, "hazar": 1000, "thousand": 1000, "lakh": 100000, "lac": 100000}
FRACTION_PREFIX = {"saadhe": 0.5, "sadhe": 0.5, "sava": 0.25, "savaa": 0.25, "paune": -0.25}


def strip_wake(text: str) -> tuple[str, bool]:
    match = WAKE.match(text)
    if not match:
        return text.strip(), False
    return text[match.end():].strip(), True


def _norm(text: str) -> str:
    return normalize_alias(re.sub(r"[.!?,]", " ", text))


def is_yes(text: str) -> bool:
    norm = _norm(text)
    return norm in YES or any(norm == f"{word} ji" or norm.startswith(f"{word} ") and len(norm.split()) <= 3 for word in ("haan", "ha", "yes", "theek hai", "confirm"))


def is_no(text: str) -> bool:
    norm = _norm(text)
    return norm in NO or (norm.split()[:1] and norm.split()[0] in {"nahi", "nahin", "no", "cancel", "नहीं"} and len(norm.split()) <= 3)


def words_to_number(text: str) -> float | None:
    """'paanch sau' -> 500, 'dedh hazaar' -> 1500, 'saadhe teen sau' -> 350, 'do hazaar paanch sau' -> 2500."""
    tokens = _norm(text).split()
    if not tokens:
        return None
    total, current, fraction, seen = 0.0, 0.0, 0.0, False
    for token in tokens:
        if token in FRACTION_PREFIX:
            fraction = FRACTION_PREFIX[token]
            continue
        if token in HINDI_UNITS:
            current += HINDI_UNITS[token] + fraction
            fraction, seen = 0.0, True
        elif token in MULTIPLIERS:
            current = (current or 1) * MULTIPLIERS[token]
            if MULTIPLIERS[token] >= 1000:
                total += current
                current = 0
            seen = True
        elif token in {"aur", "and"}:
            continue
        else:
            return None
    return total + current if seen else None


DIGIT_AMOUNT = re.compile(
    r"(?:₹|rs\.?|inr)\s*(?P<a>\d[\d,]*(?:\.\d{1,2})?)"
    r"|(?P<b>\d[\d,]*(?:\.\d{1,2})?)\s*(?:rupees?|rupaye|rupay|rupiya|rs\.?|₹|/-)",
    re.I,
)
RUPEE_WORDS = {"rupees", "rupee", "rupaye", "rupay", "rupiya", "rs"}
TOKEN = re.compile(r"[^\s,.!?]+")


def _word_amounts(text: str):
    """Yield (value, span) for runs of number words that are clearly money: followed by 'rupaye' or containing sau/hazaar."""
    tokens = [(m.group(0), m.start(), m.end()) for m in TOKEN.finditer(text)]
    index = 0
    while index < len(tokens):
        run = []
        while index < len(tokens):
            word = normalize_alias(tokens[index][0])
            if word in HINDI_UNITS or word in MULTIPLIERS or word in FRACTION_PREFIX:
                run.append(tokens[index])
                index += 1
            else:
                break
        if run:
            words = [normalize_alias(t[0]) for t in run]
            followed_by_rupee = index < len(tokens) and normalize_alias(tokens[index][0]) in RUPEE_WORDS
            if followed_by_rupee or any(w in MULTIPLIERS for w in words):
                value = words_to_number(" ".join(words))
                if value:
                    end = tokens[index][2] if followed_by_rupee else run[-1][2]
                    yield value, text[run[0][1]:end]
        else:
            index += 1


def find_amount(text: str) -> tuple[int | None, str | None]:
    """Return (paise, span) for the first explicit rupee amount. Bare numbers without ₹/rupees are not amounts."""
    source = ascii_digits(text)
    candidates = []
    for match in DIGIT_AMOUNT.finditer(source):
        value = float((match.group("a") or match.group("b")).replace(",", ""))
        if value > 0:
            candidates.append((match.start(), round(value * 100), match.group(0).strip()))
    for value, span in _word_amounts(source):
        candidates.append((source.find(span), round(value * 100), span))
    if not candidates:
        return None, None
    _, paise, span = min(candidates)
    return paise, span


def find_bare_amount(text: str) -> tuple[int | None, str | None]:
    """For replies to 'how much?': accept a lone number or number words as rupees."""
    source = ascii_digits(text).strip(" .")
    paise, span = find_amount(source)
    if paise:
        return paise, span
    match = re.fullmatch(r"(\d[\d,]*(?:\.\d{1,2})?)", source)
    if match:
        return round(float(match.group(1).replace(",", "")) * 100), match.group(1)
    value = words_to_number(source)
    return (round(value * 100), source) if value else (None, None)


def parse_count(token: str) -> int | None:
    token = ascii_digits(token.strip())
    if token.isdigit():
        return int(token)
    value = words_to_number(token)
    return int(value) if value and value == int(value) else None
