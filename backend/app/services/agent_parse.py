"""Deterministic Hinglish/English interpreter for common shop requests (fallback when Gemini is unavailable).

Produces the same draft shape the Gemini interpreter is validated into. It never guesses: missing or
uncertain details stay empty so the agent can ask a targeted question.
"""

import re
from dataclasses import dataclass, field

from app.services.agent_language import is_no, is_yes, strip_wake
from app.services.hindi_numbers import FRACTION_WORDS, NUMBER_WORDS, SCALE_WORDS
from app.services.units import ascii_digits, is_known_unit_word

RUPEE_WORDS = {"rupaye", "rupay", "rupya", "rupees", "rupee", "rs", "rs.", "inr", "₹"}
PRONOUNS = {"uske", "usko", "uska", "uski", "unka", "unko", "unke", "unki", "iske", "isko", "iska", "inko", "inka", "use", "usse"}
CONTINUATION = {"aur", "and", "bhi", "phir", "also", "plus"}
STOPWORDS = {
    "ko", "ka", "ki", "ke", "ne", "se", "mein", "me", "main", "par", "pe", "naam", "hai", "hain", "tha", "the", "thi", "ho", "hua",
    "kar", "karo", "kro", "krdo", "kardo", "karde", "kardena", "kariye", "kijiye", "karna", "kiye", "kiya", "do", "de", "dena",
    "diya", "diye", "dijiye", "likh", "likho", "likhdo", "likhna", "likhiye", "note", "add", "daal", "daalo", "dalo", "chadha",
    "chadhao", "entry", "please", "plz", "zara", "jara", "mera", "meri", "mere", "mujhe", "maine", "humne", "hum", "ab", "abhi",
    "aaj", "the", "a", "an", "of", "to", "for", "is", "are", "was", "in", "on", "by", "from", "account", "khata", "khate", "wala",
    "wali", "wale", "gaya", "gaye", "gayi", "lo", "le", "lena", "liya", "liye", "bolo", "batao", "bata", "bataiye", "dikhao",
    "show", "tell", "me", "check", "kitna", "kitne", "kitni", "kya", "what", "how", "much", "many", "hisaab", "hisab", "total",
    "sirf", "bas", "wo", "woh", "ye", "yeh", "ek", "baar", "ok", "okay", "haan", "ji", "accha", "acha", "ya", "or", "athva",
    "nahi", "nahin", "nai", "galat", "wrong", "sorry", "actually", "matlab", "correct", "change", "badlo", "instead",
}
CREDIT_WORDS = re.compile(r"\b(?:udhaar|udhar|udhari|udhaari|udhaar[iy]|credit|borrowed|lend|lent)\b")
REPAYMENT_WORDS = re.compile(
    r"\b(?:jama|jamaa|jamma|repay(?:ment)?|paid|received|vasool(?:i)?|chuka(?:ya|ye|yi|\s+diye|\s+diya)|wapas|waapas|vapas|lauta(?:ya|ye))\b"
)
GAVE_BY_CUSTOMER = re.compile(r"\bne\b.*\b(?:diye|diya|de\s+diye|de\s+gaye|de\s+gaya|bheje|bheja)\b")
GAVE_TO_CUSTOMER = re.compile(r"\bko\b.*\b(?:diye|diya|de\s+diye)\b")
BALANCE_WORDS = re.compile(
    r"\b(?:balance|baki|baaki|bakaya|baqaya|due|owes?|outstanding|hisaab|hisab)\b|\bkitn[aei]\s+(?:udhaar|udhar|paise|paisa|dena|lena)\b"
)
CREATE_WORDS = re.compile(
    r"\b(?:naya|nayi|new)\s+(?:customer|grahak)\b|\b(?:add|create|register|banao|jodo)\s+(?:a\s+)?(?:new\s+)?(?:customer|grahak)\b"
    r"|\b(?:customer|grahak)\s+(?:add|create|banao|bana\s+do|jodo)\b"
)
SALE_WORDS = re.compile(r"\b(?:bech|becha|beche|bechi|bechiye|bik|bika|bike|biki|sold|sell|sale)\b")
STOCK_WORDS = re.compile(r"\b(?:stock|inventory|bacha|bache|bachi|left|remaining|available|maal)\b")
PAYMENT_SUMMARY_WORDS = re.compile(r"\b(?:payments?|upi|collections?)\b.*\b(?:summary|today|aaj|total|kitne|kitna|aaye|aaya)\b")
TIMELINE_WORDS = re.compile(r"\b(?:what happened|kya hua|activity|timeline|din kaisa|aaj kaisa)\b")
GENERIC_WRITE = re.compile(r"\b(?:add|likh|likho|likhdo|note|daal|daalo|dalo|chadha|chadhao|entry|jod|jodo)\b")
CANCEL_WORDS = re.compile(r"^\s*(?:cancel|cancel\s+karo|rehne\s+do|rahne\s+do|mat\s+karo|nahi\s+chahiye|chhodo|chodo|stop)\s*[.!]?\s*$")
KIND_WORDS = {
    "udhaar", "udhar", "udhari", "udhaari", "credit", "borrowed", "lend", "lent", "jama", "jamaa", "jamma", "repay", "repayment",
    "paid", "received", "vasool", "vasooli", "chukaya", "chukaye", "wapas", "waapas", "vapas", "lautaya", "lautaye", "balance",
    "baki", "baaki", "bakaya", "baqaya", "due", "owe", "owes", "outstanding", "naya", "nayi", "new", "customer", "grahak",
    "create", "register", "banao", "bana", "jodo", "bech", "becha", "beche", "bechi", "bechiye", "bik", "bika", "bike", "biki",
    "sold", "sell", "sale", "stock", "inventory", "bacha", "bache", "bachi", "left", "remaining", "available", "maal",
}
TOKEN = re.compile(r"₹|\d[\d,]*(?:\.\d+)?|[^\W\d_]+(?:\.[^\W\d_]+)*", re.UNICODE)


@dataclass
class NumberSpan:
    start: int  # token indexes [start, end)
    end: int
    value: float
    text: str
    money: bool = False  # ₹ before or rupee word after
    quantity_unit: str | None = None  # unit word right after


@dataclass
class Draft:
    kind: str | None = None  # credit | repayment | balance | customer_create | sale | stock_check | payment_summary | timeline_summary
    customer_text: str | None = None
    product_text: str | None = None
    amount_text: str | None = None
    amount_paise: int | None = None
    quantity: int | None = None
    quantity_text: str | None = None
    unit_text: str | None = None
    pronoun_ref: bool = False
    continuation: bool = False
    generic_write: bool = False
    issues: list[str] = field(default_factory=list)  # AMBIGUOUS_AMOUNT, QUANTITY_NOT_MONEY, GAVE_TO_CUSTOMER
    uncertain_numbers: list[tuple[str, list[tuple[str, int]]]] = field(default_factory=list)
    # Filled by the agent while resolving (never by an interpreter):
    customer_id: str | None = None
    product_id: str | None = None
    create_ref: int | None = None  # index of a customer_create draft in the same turn
    new_customer_ok: bool = False  # merchant chose "create new" despite a similar existing customer
    inferred: list[str] = field(default_factory=list)


@dataclass
class Parsed:
    control: str | None = None  # cancel | affirm
    drafts: list[Draft] = field(default_factory=list)
    text: str = ""


def _edit_distance(left: str, right: str) -> int:
    row = list(range(len(right) + 1))
    for i in range(1, len(left) + 1):
        previous, row[0] = row[0], i
        for j in range(1, len(right) + 1):
            saved = row[j]
            row[j] = min(row[j] + 1, row[j - 1] + 1, previous + (left[i - 1] != right[j - 1]))
            previous = saved
    return row[-1]


def uncertain_number_words(tokens: list[str]) -> list[tuple[str, list[tuple[str, int]]]]:
    """Words that look like a misheard number word ("pachs" → pachas 50 / pachis 25). Reported, never converted."""
    found = []
    for token in tokens:
        low = token.lower()
        if (len(low) < 4 or low in NUMBER_WORDS or low in SCALE_WORDS or low in STOPWORDS or low in KIND_WORDS or low in RUPEE_WORDS
                or is_known_unit_word(low)):
            continue
        limit = 2 if len(low) >= 6 else 1
        seen: dict[int, str] = {}
        for word, value in NUMBER_WORDS.items():
            if len(word) >= 4 and value not in seen and _edit_distance(low, word) <= limit:
                seen[value] = word
        if seen:
            found.append((token, sorted(((w, v) for v, w in seen.items()), key=lambda item: item[1])[:3]))
    return found


def words_value(words: list[str]) -> float | None:
    """'paanch sau' 500, 'dedh hazaar' 1500, 'saadhe teen sau' 350, 'do hazaar paanch sau' 2500."""
    total, current, fraction, seen = 0.0, 0.0, 0.0, False
    for raw in words:
        word = raw.lower()
        if word in FRACTION_WORDS and word not in ("saadhe", "sadhe", "sava", "paune"):
            current += FRACTION_WORDS[word]
            seen = True
        elif word in ("saadhe", "sadhe", "sava", "paune"):
            fraction = FRACTION_WORDS[word]
        elif word in NUMBER_WORDS:
            current += NUMBER_WORDS[word] + fraction
            fraction, seen = 0.0, True
        elif word in SCALE_WORDS:
            current = (current or 1) * SCALE_WORDS[word]
            if SCALE_WORDS[word] >= 1000:
                total, current = total + current, 0.0
            seen = True
        else:
            return None
    return total + current if seen else None


def _is_number_word(token: str) -> bool:
    low = token.lower()
    return low in NUMBER_WORDS or low in SCALE_WORDS or low in FRACTION_WORDS


def number_spans(tokens: list[str]) -> list[NumberSpan]:
    spans, index = [], 0
    while index < len(tokens):
        token = tokens[index]
        if re.fullmatch(r"\d[\d,]*(?:\.\d+)?", token):
            grouped = token.replace(",", "")
            try:
                spans.append(NumberSpan(index, index + 1, float(grouped), token))
            except ValueError:
                pass
            index += 1
            continue
        # "do" alone is usually the verb "give"; only count it as a number when a scale/unit/rupee word follows.
        if _is_number_word(token):
            end = index
            while end < len(tokens) and _is_number_word(tokens[end]):
                end += 1
            words = tokens[index:end]
            nxt = tokens[end].lower() if end < len(tokens) else ""
            lone_verb = len(words) == 1 and words[0].lower() in {"do", "de", "so"}
            # "do" is a number only at the start ("Do Amul packets") or right before a rupee/unit word ("do packet").
            if lone_verb and not (index == 0 or nxt in RUPEE_WORDS or is_known_unit_word(nxt)):
                index += 1
                continue
            value = words_value(words)
            if value is not None:
                spans.append(NumberSpan(index, end, value, " ".join(words)))
            index = end
            continue
        index += 1
    for span in spans:
        before = tokens[span.start - 1].lower() if span.start > 0 else ""
        after = tokens[span.end].lower() if span.end < len(tokens) else ""
        if before in {"₹", "rs", "rs.", "inr"} or after in RUPEE_WORDS:
            span.money = True
        elif after and is_known_unit_word(after):
            span.quantity_unit = tokens[span.end]
    return spans


def _name_from(tokens: list[str], skip: set[int]) -> str | None:
    words = [t for i, t in enumerate(tokens) if i not in skip and t.lower() not in STOPWORDS and t.lower() not in KIND_WORDS
             and t.lower() not in RUPEE_WORDS and t.lower() not in PRONOUNS and t.lower() not in CONTINUATION
             and not is_known_unit_word(t.lower()) and not re.fullmatch(r"\d[\d,.]*", t)]
    return " ".join(words) or None


def _kind(norm: str) -> str | None:
    if CREATE_WORDS.search(norm):
        return "customer_create"
    if PAYMENT_SUMMARY_WORDS.search(norm):
        return "payment_summary"
    if TIMELINE_WORDS.search(norm):
        return "timeline_summary"
    if SALE_WORDS.search(norm):
        return "sale"
    question = bool(re.search(r"\b(?:kitn[aei]|kya|how much|what)\b|\?", norm))
    if BALANCE_WORDS.search(norm) and (question or not (CREDIT_WORDS.search(norm) or REPAYMENT_WORDS.search(norm))):
        return "balance"
    credit, repayment = bool(CREDIT_WORDS.search(norm)), bool(REPAYMENT_WORDS.search(norm) or GAVE_BY_CUSTOMER.search(norm))
    if credit and repayment:
        return "conflict"
    if credit:
        return "credit"
    if repayment:
        return "repayment"
    if STOCK_WORDS.search(norm) and (question or "?" in norm or re.search(r"\b(?:kitn[aei]|check)\b", norm)):
        return "stock_check"
    return None


def parse_segment(text: str) -> Draft:
    norm = ascii_digits(text).lower()
    tokens = TOKEN.findall(ascii_digits(text))
    draft = Draft()
    if tokens and tokens[0].lower() in CONTINUATION:
        draft.continuation = True
    draft.kind = _kind(norm)
    draft.generic_write = bool(GENERIC_WRITE.search(norm))
    draft.pronoun_ref = any(t.lower() in PRONOUNS for t in tokens)
    if draft.kind is None and GAVE_TO_CUSTOMER.search(norm):
        draft.issues.append("GAVE_TO_CUSTOMER")
    spans = number_spans(tokens)
    skip: set[int] = set()
    for span in spans:
        skip.update(range(span.start, span.end))
        if span.quantity_unit:
            skip.add(span.end)
    if draft.kind == "sale":
        if spans:
            span = spans[0]
            if span.value == int(span.value) and span.value > 0 and not span.money:
                draft.quantity, draft.quantity_text = int(span.value), span.text
                draft.unit_text = span.quantity_unit or next((t for t in tokens[span.end:] if is_known_unit_word(t.lower())), None)
        draft.product_text = _name_from(tokens, skip)
    elif draft.kind == "customer_create":
        draft.customer_text = _name_from(tokens, skip)
    elif draft.kind in ("balance", "stock_check"):
        name = _name_from(tokens, skip)
        if draft.kind == "balance":
            draft.customer_text = name
        else:
            draft.product_text = name
    elif draft.kind not in ("payment_summary", "timeline_summary"):
        money = [s for s in spans if not s.quantity_unit]
        if any(s.quantity_unit for s in spans) and not money:
            draft.issues.append("QUANTITY_NOT_MONEY")
            draft.quantity_text = f"{spans[0].text} {spans[0].quantity_unit}"
        if len(money) > 1:
            draft.issues.append("AMBIGUOUS_AMOUNT")
        elif len(money) == 1:
            span = money[0]
            paise = round(span.value * 100)
            if paise > 0 and abs(span.value * 100 - paise) < 1e-6:
                draft.amount_paise = paise
                end = span.end + (1 if span.end < len(tokens) and tokens[span.end].lower() in RUPEE_WORDS else 0)
                start = span.start - (1 if span.start > 0 and tokens[span.start - 1] == "₹" else 0)
                draft.amount_text = " ".join(tokens[start:end])
        draft.customer_text = _name_from(tokens, skip)
    if draft.amount_paise is None and draft.quantity is None:
        draft.uncertain_numbers = uncertain_number_words([t for i, t in enumerate(tokens) if i not in skip])
        if draft.uncertain_numbers and draft.customer_text:
            unsure = {word.lower() for word, _ in draft.uncertain_numbers}
            draft.customer_text = " ".join(w for w in draft.customer_text.split() if w.lower() not in unsure) or None
        if draft.uncertain_numbers and draft.product_text:
            unsure = {word.lower() for word, _ in draft.uncertain_numbers}
            draft.product_text = " ".join(w for w in draft.product_text.split() if w.lower() not in unsure) or None
    return draft


SPLIT = re.compile(r"\s*(?:,|;|\.\s|\baur\b|\band\b|\bphir\b|\bthen\b)\s*", re.I)


def parse(utterance: str) -> Parsed:
    text, _ = strip_wake(utterance or "")
    text = " ".join(text.split())
    result = Parsed(text=text)
    if not text:
        return result
    has_number = bool(number_spans(TOKEN.findall(ascii_digits(text))))
    if not has_number and (CANCEL_WORDS.match(text.lower()) or is_no(text)):
        result.control = "cancel"
        return result
    if not has_number and is_yes(text):
        result.control = "affirm"
        return result
    lead = re.match(r"^\s*(?:aur|and|phir|also)\b\s*", text, re.I)
    body = text[lead.end():] if lead else text
    parts = [part for part in SPLIT.split(body) if part.strip()]
    if len(parts) > 1:
        drafts = [parse_segment(part) for part in parts]
        if all(d.kind and d.kind != "conflict" for d in drafts):
            if lead:
                drafts[0].continuation = True
            result.drafts = drafts
            return result
    draft = parse_segment(body)
    draft.continuation = draft.continuation or bool(lead)
    result.drafts = [draft]
    return result
