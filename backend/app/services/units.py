"""Deterministic unit words, money text, and quantity parsing for stock inflow.

Synonyms only map spellings of the *same* unit ("pkt" == "packet"). Converting
between different units (case -> packet) needs a merchant-confirmed factor.
"""

import re
from decimal import Decimal, InvalidOperation

from app.services.ledger import normalize_alias

UNIT_SYNONYMS = {
    "packet": {"packet", "packets", "pack", "packs", "pkt", "pkts", "pckt", "paket"},
    "cup": {"cup", "cups", "katori"},
    "piece": {"piece", "pieces", "pc", "pcs", "nos", "no", "unit", "units", "item", "items"},
    "bottle": {"bottle", "bottles", "btl"},
    "box": {"box", "boxes"},
    "case": {"case", "cases"},
    "carton": {"carton", "cartons", "ctn"},
    "crate": {"crate", "crates"},
    "dozen": {"dozen", "dozens", "dz"},
    "tray": {"tray", "trays"},
    "bag": {"bag", "bags", "bori"},
    "sachet": {"sachet", "sachets"},
    "jar": {"jar", "jars"},
    "tin": {"tin", "tins", "can", "cans"},
    "kg": {"kg", "kgs", "kilo", "kilos", "kilogram", "kilograms"},
    "gram": {"g", "gm", "gms", "gram", "grams"},
    "litre": {"l", "ltr", "litre", "litres", "liter", "liters"},
    "ml": {"ml"},
    "loaf": {"loaf", "loaves"},
}
_LOOKUP = {word: canonical for canonical, words in UNIT_SYNONYMS.items() for word in words}
UNIT_WORDS = sorted(_LOOKUP, key=len, reverse=True)

NUMBER_WORDS = {
    "ek": 1, "one": 1, "do": 2, "two": 2, "teen": 3, "three": 3, "char": 4, "chaar": 4, "four": 4,
    "paanch": 5, "panch": 5, "five": 5, "chhe": 6, "chhah": 6, "six": 6, "saat": 7, "seven": 7,
    "aath": 8, "eight": 8, "nau": 9, "nine": 9, "das": 10, "dus": 10, "ten": 10,
    "gyarah": 11, "eleven": 11, "barah": 12, "baarah": 12, "twelve": 12, "terah": 13, "thirteen": 13,
    "chaudah": 14, "fourteen": 14, "pandrah": 15, "pandrah": 15, "fifteen": 15, "solah": 16, "sixteen": 16,
    "satrah": 17, "seventeen": 17, "atharah": 18, "eighteen": 18, "unnis": 19, "nineteen": 19,
    "bees": 20, "twenty": 20, "pachchis": 25, "pachees": 25, "tees": 30, "thirty": 30,
    "chalis": 40, "forty": 40, "pachaas": 50, "pachas": 50, "fifty": 50, "sau": 100, "hundred": 100,
}


def canonical_unit(text: str | None) -> str | None:
    if text is None:
        return None
    normalized = normalize_alias(text).strip(".")
    if not normalized:
        return None
    return _LOOKUP.get(normalized, normalized)


def is_known_unit_word(text: str) -> bool:
    return normalize_alias(text).strip(".") in _LOOKUP


def parse_quantity(value: object) -> tuple[int | None, str | None]:
    """Return a positive whole quantity, or ``(None, note)``. Never rounds."""
    if value is None or value == "":
        return None, None
    if isinstance(value, bool):
        return None, "Quantity was not a number."
    if isinstance(value, int):
        return value, None
    text = ascii_digits(str(value).strip().replace(",", ""))
    if normalize_alias(text) in NUMBER_WORDS:
        return NUMBER_WORDS[normalize_alias(text)], None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None, f"Quantity '{text[:20]}' is not a number."
    if number != number.to_integral_value():
        return None, f"Quantity {text[:20]} is fractional; enter a whole count in a smaller unit."
    return int(number), None


# Devanagari, Gujarati, Gurmukhi, Bengali, Tamil, Telugu, Kannada, Malayalam, Odia digits -> ASCII.
_INDIC_DIGIT_BASES = (0x0966, 0x0AE6, 0x0A66, 0x09E6, 0x0BE6, 0x0C66, 0x0CE6, 0x0D66, 0x0B66)
INDIC_DIGITS = {base + offset: str(offset) for base in _INDIC_DIGIT_BASES for offset in range(10)}


def ascii_digits(text: str) -> str:
    return text.translate(INDIC_DIGITS)


MONEY_TEXT = re.compile(r"^(-)?\s*(?:₹|rs\.?|inr)?\s*(-)?\s*(\d[\d,]*(?:\.\d{1,2})?|\.\d{1,2})\s*(?:/-)?$", re.I)


def parse_money_to_paise(value: object, allow_negative: bool = False) -> tuple[int | None, str | None]:
    """Convert printed rupee text (e.g. "₹1,475.00") to integer paise. Never guesses."""
    if value is None or value == "":
        return None, None
    if isinstance(value, bool):
        return None, "Amount was not a number."
    if isinstance(value, (int, float)):
        text = str(value)
    else:
        text = ascii_digits(str(value).strip())
    match = MONEY_TEXT.fullmatch(text)
    if not match:
        return None, f"Amount '{text[:24]}' could not be read as rupees."
    negative = bool(match.group(1) or match.group(2))
    try:
        amount = Decimal(match.group(3).replace(",", ""))
    except InvalidOperation:
        return None, f"Amount '{text[:24]}' could not be read as rupees."
    paise = amount * 100
    if paise != paise.to_integral_value():
        return None, f"Amount '{text[:24]}' has more than two decimal places."
    result = int(paise)
    if negative:
        if not allow_negative:
            return None, f"Amount '{text[:24]}' is negative."
        result = -result
    return result, None


def normalize_invoice_number(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[\s\-_/#.]", "", value).casefold()
    return normalized or None
