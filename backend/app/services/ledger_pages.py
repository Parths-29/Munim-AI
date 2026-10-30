"""Bahi-khata scanner: a photographed udhaar notebook page becomes a reviewed ledger draft.

The draft never writes. On explicit confirmation one transaction creates any
customers the merchant chose to create, appends one ledger entry per accepted
line (keeping the notebook date as ``occurred_at`` so overdue aging is honest),
and records a posting batch. Names are matched exactly; nothing is guessed.
"""

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.domain.intake import ExtractionView, Issue
from app.domain.ledger_pages import (
    PageConfirm,
    PageDraft,
    PageLine,
    PageLineView,
    PagePostedEntry,
    PagePostingView,
    PageReject,
    PageRevise,
    PageTotals,
    PageView,
    PageVoiceCorrection,
    PageVoiceCorrectionResult,
)
from app.domain.models import CustomerView
from app.services.database import connect, current_shop
from app.services.events import append_event
from app.services.image_validation import validate_invoice_image
from app.services.invoice_extraction import ProviderUnavailable
from app.services.ledger import normalize_alias
from app.services.notebook_extraction import get_notebook_provider
from app.services.proposals import _confidence, _parse_date, _text, expiry_days, min_confidence, now_utc
from app.services.units import ascii_digits, parse_money_to_paise

SHOP_TZ = ZoneInfo("Asia/Kolkata")
CREDIT_WORDS = {"udhaar", "udhar", "udhaari", "उधार", "उधारी", "baki", "baaki", "बाकी", "बाकि", "credit", "cr", "+", "lena", "लेना",
                "ઉધાર", "બાકી", "dena baki", "len"}
REPAYMENT_WORDS = {"jama", "jamaa", "जमा", "jamma", "paid", "received", "mila", "mile", "मिला", "मिले", "-", "dr", "repaid",
                   "વસૂલ", "જમા", "वसूल", "wapas", "वापस"}
VOICE_PATTERN = re.compile(
    r"^(?P<name>.+?)[\s,:-]+(?:₹|rs\.?\s*)?(?P<amount>[\d,०-९૦-૯]+(?:\.\d{1,2})?)\s*(?:rupees?|rupaye|rs|₹)?\s*(?P<kind>[^\d\s,]+)?\s*[.!]?$",
    re.I,
)


def _kind(value: object) -> str | None:
    text = _text(value, 30)
    if not text:
        return None
    norm = normalize_alias(text).strip(" .()")
    if norm in CREDIT_WORDS:
        return "CREDIT"
    if norm in REPAYMENT_WORDS:
        return "REPAYMENT"
    return None


def _hash(draft: PageDraft) -> str:
    canonical = json.dumps(draft.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _line_id() -> str:
    return f"pline_{uuid.uuid4().hex[:10]}"


def draft_from_raw(data: dict) -> tuple[PageDraft, list[str]]:
    notes: list[str] = []
    raw_lines = data.get("lines") if isinstance(data.get("lines"), list) else []
    if len(raw_lines) > 60:
        notes.append("Only the first 60 rows were kept; add the rest manually.")
    lines = []
    for item in raw_lines[:60]:
        if not isinstance(item, dict):
            continue
        line_notes: list[str] = []
        amount, note = parse_money_to_paise(item.get("amount_text"))
        if note:
            line_notes.append(f"amount: {note}")
        kind_text = item.get("kind_text")
        kind = _kind(kind_text)
        if kind_text and kind is None:
            line_notes.append(f"Marker '{_text(kind_text, 20)}' is not a known udhaar/jama word; choose credit or repayment.")
        lines.append(PageLine(
            line_id=_line_id(),
            source_text=_text(item.get("source_text"), 240),
            name_text=_text(item.get("name_text"), 100),
            name_latin=_text(item.get("name_latin"), 100),
            amount_paise=amount,
            entry_type=kind,
            entry_date=_parse_date(ascii_digits(str(item.get("date_text") or "")) or None, line_notes),
            confidence=_confidence(item.get("confidence")),
            parse_notes=line_notes,
        ))
    language = _text(data.get("language_hint"), 20)
    return PageDraft(language_hint=language, lines=lines), notes


# --- Persistence --------------------------------------------------------------

def _insert(connection, draft: PageDraft, extraction: ExtractionView, idempotency_key: str, image_sha: str | None,
            notes: list[str], actor: str) -> str:
    proposal_id = f"page_{uuid.uuid4().hex[:12]}"
    created = now_utc()
    digest = _hash(draft)
    connection.execute(
        """INSERT INTO ledger_page_proposals (proposal_id, shop_id, status, version, content_hash, draft_json, extraction_json,
           image_sha256, idempotency_key, posted_batch_id, created_at, updated_at, expires_at)
           VALUES (?, ?, 'NEEDS_REVIEW', 1, ?, ?, ?, ?, ?, NULL, ?, ?, ?)""",
        (proposal_id, current_shop(), digest, draft.model_dump_json(),
         json.dumps({**extraction.model_dump(mode="json"), "notes": notes}), image_sha, idempotency_key,
         created.isoformat(), created.isoformat(), (created + timedelta(days=expiry_days())).isoformat()),
    )
    connection.execute(
        "INSERT INTO ledger_page_revisions VALUES (?, ?, 1, ?, ?, ?, ?)",
        (f"prev_{uuid.uuid4().hex[:12]}", proposal_id, digest, draft.model_dump_json(), actor, created.isoformat()),
    )
    return proposal_id


def _load(connection, proposal_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM ledger_page_proposals WHERE shop_id = ? AND proposal_id = ?", (current_shop(), proposal_id)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Notebook page proposal not found in this demo shop.")
    return row


def _save_revision(connection, row: sqlite3.Row, draft: PageDraft, actor: str) -> None:
    version = row["version"] + 1
    digest = _hash(draft)
    stamp = now_utc().isoformat()
    connection.execute(
        "UPDATE ledger_page_proposals SET version = ?, content_hash = ?, draft_json = ?, updated_at = ? WHERE proposal_id = ?",
        (version, digest, draft.model_dump_json(), stamp, row["proposal_id"]),
    )
    connection.execute(
        "INSERT INTO ledger_page_revisions VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"prev_{uuid.uuid4().hex[:12]}", row["proposal_id"], version, digest, draft.model_dump_json(), actor, stamp),
    )


def _require_open(row: sqlite3.Row, expected_version: int) -> None:
    if row["status"] in {"CONFIRMED", "REJECTED"}:
        raise HTTPException(status_code=409, detail={"code": f"PROPOSAL_{row['status']}", "batch_id": row["posted_batch_id"]})
    if datetime.fromisoformat(row["expires_at"]) <= now_utc():
        raise HTTPException(status_code=409, detail={"code": "PROPOSAL_EXPIRED"})
    if row["version"] != expected_version:
        raise HTTPException(status_code=409, detail={"code": "STALE_PROPOSAL", "current_version": row["version"]})


# --- Public operations ------------------------------------------------------

def create_from_image(image: bytes, declared_type: str | None, idempotency_key: str) -> PageView:
    if not (8 <= len(idempotency_key) <= 150):
        raise HTTPException(status_code=422, detail="idempotency_key must be 8-150 characters.")
    info = validate_invoice_image(image, declared_type)
    image_sha = hashlib.sha256(image).hexdigest()

    def replay(connection):
        row = connection.execute("SELECT * FROM ledger_page_proposals WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
        if row is None:
            return None
        if row["image_sha256"] != image_sha:
            raise HTTPException(status_code=409, detail="Idempotency key was already used for a different page.")
        return evaluate(connection, row)

    with connect() as connection:
        existing = replay(connection)
        if existing:
            return existing
    provider = get_notebook_provider()
    try:
        raw = provider.extract(image, info.mime_type)
        draft, notes = draft_from_raw(raw.data)
        extraction = ExtractionView(provider=raw.provider, model=raw.model, status="EXTRACTED", correlation_id=raw.correlation_id)
    except ProviderUnavailable:
        draft, notes = PageDraft(), []
        extraction = ExtractionView(provider=getattr(provider, "name", "unknown"), status="PROVIDER_UNAVAILABLE",
                                    message="Automatic reading is unavailable. Nothing was guessed; add the rows manually.")
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = replay(connection)
        if existing:
            return existing
        proposal_id = _insert(connection, draft, extraction, idempotency_key, image_sha, notes, "extraction")
        return _store_status(connection, proposal_id)


def get_page(proposal_id: str) -> PageView:
    with connect() as connection:
        return evaluate(connection, _load(connection, proposal_id))


def revise_page(proposal_id: str, request: PageRevise) -> PageView:
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = _load(connection, proposal_id)
        _require_open(row, request.expected_version)
        previous = {line.line_id: line for line in PageDraft.model_validate_json(row["draft_json"]).lines}
        lines = []
        for edit in request.lines:
            if edit.line_id and edit.line_id not in previous:
                raise HTTPException(status_code=422, detail=f"Line {edit.line_id} is not part of this page.")
            old = previous.get(edit.line_id) if edit.line_id else None
            lines.append(PageLine(
                line_id=old.line_id if old else _line_id(),
                source_text=old.source_text if old else None,
                name_text=edit.name_text, name_latin=edit.name_latin, customer_id=edit.customer_id,
                create_customer=edit.create_customer, amount_paise=edit.amount_paise, entry_type=edit.entry_type,
                entry_date=edit.entry_date, confidence=old.confidence if old else None,
                merchant_verified=edit.merchant_verified, accepted=edit.accepted,
            ))
        draft = PageDraft(language_hint=request.language_hint or PageDraft.model_validate_json(row["draft_json"]).language_hint,
                          lines=lines)
        _save_revision(connection, row, draft, "merchant")
        return _store_status(connection, proposal_id)


def voice_correction(proposal_id: str, request: PageVoiceCorrection) -> PageVoiceCorrectionResult:
    """Apply a spoken confirmation such as "Sharma ji, 1,200" to the single matching row."""
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = _load(connection, proposal_id)
        _require_open(row, request.expected_version)
        draft = PageDraft.model_validate_json(row["draft_json"])
        match = VOICE_PATTERN.fullmatch(" ".join(request.utterance.split()))
        amount = parse_money_to_paise(match.group("amount"))[0] if match else None
        if not match or not amount:
            return PageVoiceCorrectionResult(status="clarification", matched_line_id=None, proposal=evaluate(connection, row),
                                             message="Say the name and amount, for example 'Sharma ji, 1200 udhaar'.")
        spoken = normalize_alias(match.group("name"))
        candidates = [line for line in draft.lines if spoken in {normalize_alias(line.name_text or ""), normalize_alias(line.name_latin or "")}]
        if len(candidates) != 1:
            hint = "more than one row" if candidates else "no row"
            return PageVoiceCorrectionResult(status="clarification", matched_line_id=None, proposal=evaluate(connection, row),
                                             message=f"'{match.group('name')}' matches {hint} on this page; edit the row directly.")
        target = candidates[0]
        target.amount_paise = amount
        spoken_kind = _kind(match.group("kind"))
        if spoken_kind:
            target.entry_type = spoken_kind
        target.merchant_verified = True
        _save_revision(connection, row, draft, "merchant_voice")
        view = _store_status(connection, proposal_id)
        kind_text = f" as {target.entry_type.lower()}" if target.entry_type else ""
        return PageVoiceCorrectionResult(status="applied", matched_line_id=target.line_id, proposal=view,
                                         message=f"Updated {target.name_latin or target.name_text}: ₹{amount / 100:,.2f}{kind_text}. Review and confirm the page.")


def reject_page(proposal_id: str, request: PageReject) -> PageView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required to reject a page.")
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = _load(connection, proposal_id)
        _require_open(row, request.expected_version)
        connection.execute("UPDATE ledger_page_proposals SET status = 'REJECTED', updated_at = ? WHERE proposal_id = ?",
                           (now_utc().isoformat(), proposal_id))
        return evaluate(connection, _load(connection, proposal_id))


def _store_status(connection, proposal_id: str) -> PageView:
    view = evaluate(connection, _load(connection, proposal_id))
    if view.status in {"READY", "NEEDS_REVIEW"}:
        connection.execute("UPDATE ledger_page_proposals SET status = ? WHERE proposal_id = ?", (view.status, proposal_id))
    return evaluate(connection, _load(connection, proposal_id))


# --- Validation -------------------------------------------------------------

def _customer_view(connection, customer_id: str) -> CustomerView:
    customer = connection.execute("SELECT customer_id, display_name FROM customers WHERE shop_id = ? AND customer_id = ?",
                                  (current_shop(), customer_id)).fetchone()
    aliases = [r["alias"] for r in connection.execute(
        "SELECT alias FROM customer_aliases WHERE shop_id = ? AND customer_id = ? ORDER BY alias", (current_shop(), customer_id))]
    return CustomerView(customer_id=customer["customer_id"], display_name=customer["display_name"], aliases=aliases)


def _exact_customers(connection, names: list[str]) -> list[str]:
    found: list[str] = []
    for name in names:
        for row in connection.execute(
            """SELECT DISTINCT customer_id FROM customer_aliases WHERE shop_id = ? AND alias_normalized = ?""",
            (current_shop(), normalize_alias(name)),
        ):
            if row["customer_id"] not in found:
                found.append(row["customer_id"])
    return found


def _suggest_customers(connection, names: list[str]) -> list[str]:
    found: list[str] = []
    for name in names:
        words = f" {normalize_alias(name)} "
        for row in connection.execute("SELECT customer_id, alias_normalized FROM customer_aliases WHERE shop_id = ?", (current_shop(),)):
            alias = row["alias_normalized"]
            if len(alias) >= 3 and (f" {alias} " in words or words.strip() in alias) and row["customer_id"] not in found:
                found.append(row["customer_id"])
    return found[:5]


def _balance(connection, customer_id: str) -> int:
    return int(connection.execute(
        """SELECT COALESCE(SUM(CASE entry_type WHEN 'CREDIT' THEN amount_paise ELSE -amount_paise END), 0)
           FROM ledger_entries WHERE shop_id = ? AND customer_id = ? AND status = 'POSTED'""",
        (current_shop(), customer_id),
    ).fetchone()[0])


def _sort_key(line: PageLineView, index: int):
    return (line.entry_date or date.max, index)


def evaluate(connection, row: sqlite3.Row) -> PageView:
    draft = PageDraft.model_validate_json(row["draft_json"])
    extraction_data = json.loads(row["extraction_json"])
    notes = extraction_data.pop("notes", [])
    threshold = min_confidence()
    today = now_utc().astimezone(SHOP_TZ).date()
    issues = [Issue(code="EXTRACTION_NOTE", severity="warning", message=note) for note in notes]
    views: list[PageLineView] = []
    new_names: dict[str, str] = {}
    for line in draft.lines:
        line_issues: list[Issue] = []

        def add(code, severity, message, field=None):
            line_issues.append(Issue(code=code, severity=severity, message=message, line_id=line.line_id, field=field))

        for note in line.parse_notes:
            add("EXTRACTION_NOTE", "warning", note)
        names = [n for n in (line.name_latin, line.name_text) if n]
        candidates: list[str] = []
        customer_id = None
        if line.customer_id:
            exists = connection.execute("SELECT 1 FROM customers WHERE shop_id = ? AND customer_id = ?",
                                        (current_shop(), line.customer_id)).fetchone()
            status = "SELECTED" if exists else "NOT_FOUND"
            customer_id = line.customer_id if exists else None
            if not exists:
                add("CUSTOMER_INVALID", "blocking", "Selected customer does not exist.", "customer_id")
        elif not names:
            status = "NOT_PROVIDED"
            add("NAME_MISSING", "blocking", "Row has no name; enter or select the customer.", "customer_id")
        else:
            exact = _exact_customers(connection, names)
            if len(exact) == 1:
                status, customer_id = "MATCHED", exact[0]
            elif len(exact) > 1:
                status, candidates = "AMBIGUOUS", exact
                add("CUSTOMER_AMBIGUOUS", "blocking", f"'{names[0]}' matches more than one customer; choose one.", "customer_id")
            elif line.create_customer:
                status = "WILL_CREATE"
                new_names.setdefault(normalize_alias(line.name_latin or line.name_text), line.line_id)
            else:
                status, candidates = "NOT_FOUND", _suggest_customers(connection, names)
                hint = "choose a suggested customer, or " if candidates else ""
                add("CUSTOMER_UNRESOLVED", "blocking", f"No customer named '{names[0]}'. {hint}set create_customer to add them.", "customer_id")
        if line.amount_paise is None:
            add("AMOUNT_MISSING", "blocking", "Amount is missing or unreadable.", "amount_paise")
        elif line.amount_paise <= 0:
            add("AMOUNT_INVALID", "blocking", "Amount must be positive.", "amount_paise")
        if line.entry_type is None:
            add("ENTRY_TYPE_MISSING", "blocking", "Is this udhaar (credit) or jama (repayment)?", "entry_type")
        if line.entry_date and line.entry_date > today:
            add("DATE_IN_FUTURE", "blocking", "Entry date is in the future.", "entry_date")
        if line.entry_date is None:
            add("DATE_UNKNOWN", "info", "No date read; the entry will be dated today, which affects overdue reminders.", "entry_date")
        if line.confidence is not None and line.confidence < threshold and not line.merchant_verified:
            add("LOW_CONFIDENCE", "blocking", f"Row read with low confidence ({line.confidence:.2f}); check it against the page.")
        if customer_id and line.amount_paise and line.entry_type and line.entry_date:
            duplicate = connection.execute(
                """SELECT entry_id FROM ledger_entries WHERE shop_id = ? AND customer_id = ? AND entry_type = ? AND amount_paise = ?
                   AND substr(COALESCE(occurred_at, created_at), 1, 10) = ? LIMIT 1""",
                (current_shop(), customer_id, line.entry_type, line.amount_paise, line.entry_date.isoformat()),
            ).fetchone()
            if duplicate:
                add("POSSIBLE_DUPLICATE_ENTRY", "warning", f"A matching entry already exists ({duplicate['entry_id']}).")
        views.append(PageLineView(
            line_id=line.line_id, source_text=line.source_text, name_text=line.name_text, name_latin=line.name_latin,
            matched_customer_id=customer_id, match_status=status,
            candidates=[_customer_view(connection, cid) for cid in candidates],
            amount_paise=line.amount_paise, entry_type=line.entry_type, entry_date=line.entry_date,
            confidence=line.confidence, merchant_verified=line.merchant_verified, accepted=line.accepted,
            issues=line_issues if line.accepted else [],
        ))

    accepted = [view for view in views if view.accepted]
    if not accepted:
        issues.append(Issue(code="NO_ACCEPTED_LINES", severity="blocking", message="Add or accept at least one row."))
    # Repayments may not exceed the running balance (existing balance + earlier rows on this page).
    running: dict[str, int] = {}
    for index, view in sorted(enumerate(accepted), key=lambda pair: _sort_key(pair[1], pair[0])):
        key = view.matched_customer_id or (f"new:{normalize_alias(view.name_latin or view.name_text or '')}" if view.match_status == "WILL_CREATE" else None)
        if key is None or view.amount_paise is None or view.entry_type is None:
            continue
        if key not in running:
            running[key] = _balance(connection, key) if view.matched_customer_id else 0
        if view.entry_type == "CREDIT":
            running[key] += view.amount_paise
        elif view.amount_paise > running[key]:
            view.issues.append(Issue(code="REPAYMENT_EXCEEDS_BALANCE", severity="blocking", line_id=view.line_id, field="amount_paise",
                                     message=f"Jama of {view.amount_paise} paise exceeds the balance of {running[key]} paise at that point."))
        else:
            running[key] -= view.amount_paise
    if row["image_sha256"]:
        same = connection.execute(
            "SELECT proposal_id FROM ledger_page_proposals WHERE image_sha256 = ? AND proposal_id != ? LIMIT 1",
            (row["image_sha256"], row["proposal_id"]),
        ).fetchone()
        if same:
            issues.append(Issue(code="POSSIBLE_DUPLICATE_PAGE", severity="warning", message=f"The same photo was scanned before ({same['proposal_id']})."))

    all_issues = issues + [issue for view in accepted for issue in view.issues]
    blocking = any(issue.severity == "blocking" for issue in all_issues)
    status = row["status"]
    expires_at = datetime.fromisoformat(row["expires_at"])
    if status not in {"CONFIRMED", "REJECTED"}:
        status = "EXPIRED" if expires_at <= now_utc() else ("NEEDS_REVIEW" if blocking else "READY")
    extraction = ExtractionView.model_validate(extraction_data)
    return PageView(
        proposal_id=row["proposal_id"], status=status, version=row["version"], content_hash=row["content_hash"],
        language_hint=draft.language_hint, lines=views, issues=issues,
        totals=PageTotals(
            accepted_lines=len(accepted),
            credit_total_paise=sum(v.amount_paise or 0 for v in accepted if v.entry_type == "CREDIT"),
            repayment_total_paise=sum(v.amount_paise or 0 for v in accepted if v.entry_type == "REPAYMENT"),
            customers_to_create=len(new_names),
        ),
        ready_to_confirm=status == "READY",
        warnings_require_acknowledgement=any(issue.severity == "warning" for issue in all_issues),
        extraction=extraction, posted_batch_id=row["posted_batch_id"],
        created_at=datetime.fromisoformat(row["created_at"]), updated_at=datetime.fromisoformat(row["updated_at"]),
        expires_at=expires_at,
    )


# --- Posting ------------------------------------------------------------------

def confirm_page(proposal_id: str, request: PageConfirm) -> PagePostingView:
    from app.services.reminders import cancel_reminders_if_settled  # lazy: avoids import cycle

    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required before posting notebook entries.")
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = _load(connection, proposal_id)
        existing = connection.execute(
            "SELECT * FROM ledger_page_postings WHERE proposal_id = ? OR idempotency_key = ? LIMIT 2",
            (proposal_id, request.idempotency_key),
        ).fetchall()
        if existing:
            posting = existing[0]
            if (len(existing) == 1 and posting["proposal_id"] == proposal_id and posting["idempotency_key"] == request.idempotency_key
                    and posting["content_hash"] == request.content_hash):
                return _posting_view(connection, posting, replay=True)
            raise HTTPException(status_code=409, detail={"code": "PAGE_ALREADY_POSTED", "batch_id": posting["batch_id"]})
        _require_open(row, request.expected_version)
        if row["content_hash"] != request.content_hash:
            raise HTTPException(status_code=409, detail={"code": "STALE_PROPOSAL", "current_content_hash": row["content_hash"]})
        view = evaluate(connection, row)
        accepted = [line for line in view.lines if line.accepted]
        blocking = [i for i in view.issues + [i for line in accepted for i in line.issues] if i.severity == "blocking"]
        if blocking:
            raise HTTPException(status_code=409, detail={"code": "PROPOSAL_NOT_READY", "issues": [i.model_dump() for i in blocking]})
        if view.warnings_require_acknowledgement and not request.acknowledge_warnings:
            raise HTTPException(status_code=409, detail={"code": "WARNINGS_NOT_ACKNOWLEDGED"})

        batch_id = f"pagebatch_{uuid.uuid4().hex[:12]}"
        stamp = now_utc().isoformat()
        created_ids: dict[str, str] = {}
        customers_created = 0
        ordered = [line for _, line in sorted(enumerate(accepted), key=lambda pair: _sort_key(pair[1], pair[0]))]
        posted_rows = []
        for line in ordered:
            customer_id = line.matched_customer_id
            created_now = False
            if customer_id is None:
                key = normalize_alias(line.name_latin or line.name_text)
                customer_id = created_ids.get(key)
                if customer_id is None:
                    customer_id = f"cust_{uuid.uuid4().hex[:12]}"
                    display = line.name_latin or line.name_text
                    connection.execute(
                        "INSERT INTO customers(customer_id, shop_id, display_name, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?)",
                        (customer_id, current_shop(), display, f"{request.idempotency_key}:customer:{line.line_id}", stamp),
                    )
                    for alias in dict.fromkeys(n for n in (line.name_latin, line.name_text) if n):
                        connection.execute(
                            "INSERT INTO customer_aliases(alias_id, shop_id, customer_id, alias, alias_normalized) VALUES (?, ?, ?, ?, ?)",
                            (f"alias_{uuid.uuid4().hex[:12]}", current_shop(), customer_id, alias, normalize_alias(alias)),
                        )
                    append_event(connection, event_type="CUSTOMER_CREATED", entity_type="CUSTOMER", entity_id=customer_id,
                                 source_event_id=f"{request.idempotency_key}:customer:{line.line_id}", source_channel="text",
                                 source_utterance=None, status="POSTED", summary=f"Customer record created for {display} from a notebook page.",
                                 idempotency_key=f"{request.idempotency_key}:customer:{line.line_id}")
                    created_ids[key] = customer_id
                    customers_created += 1
                    created_now = True
            occurred = (datetime.combine(line.entry_date, time(12, 0), tzinfo=SHOP_TZ).astimezone(timezone.utc).isoformat()
                        if line.entry_date else None)
            entry_id = f"entry_{uuid.uuid4().hex[:12]}"
            source_event_id = f"ledger-page:{proposal_id}:{line.line_id}"
            connection.execute(
                """INSERT INTO ledger_entries (entry_id, shop_id, customer_id, entry_type, amount_paise, source_event_id,
                   idempotency_key, status, created_at, occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'POSTED', ?, ?)""",
                (entry_id, current_shop(), customer_id, line.entry_type, line.amount_paise, source_event_id,
                 f"{request.idempotency_key}:{line.line_id}", stamp, occurred),
            )
            append_event(connection, event_type=f"{line.entry_type}_POSTED", entity_type="LEDGER_ENTRY", entity_id=entry_id,
                         source_event_id=source_event_id, source_channel="text", source_utterance=line.source_text,
                         status="POSTED", summary=f"{line.entry_type.title()} of {line.amount_paise} paise recorded from a notebook page"
                         + (f" dated {line.entry_date.isoformat()}." if line.entry_date else "."),
                         idempotency_key=f"{request.idempotency_key}:{line.line_id}")
            if line.entry_type == "REPAYMENT":
                cancel_reminders_if_settled(connection, customer_id)
            posted_rows.append((line, entry_id, customer_id, created_now))
        connection.execute(
            """INSERT INTO ledger_page_postings (batch_id, shop_id, proposal_id, proposal_version, content_hash, entry_count,
               customers_created, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (batch_id, current_shop(), proposal_id, row["version"], row["content_hash"], len(posted_rows), customers_created,
             request.idempotency_key, stamp),
        )
        connection.execute("UPDATE ledger_page_proposals SET status = 'CONFIRMED', posted_batch_id = ?, updated_at = ? WHERE proposal_id = ?",
                           (batch_id, stamp, proposal_id))
        return _posting_view(connection, connection.execute("SELECT * FROM ledger_page_postings WHERE batch_id = ?", (batch_id,)).fetchone())


def _posting_view(connection, posting: sqlite3.Row, replay: bool = False) -> PagePostingView:
    prefix = f"ledger-page:{posting['proposal_id']}:"
    rows = connection.execute(
        """SELECT l.*, c.display_name, c.idempotency_key AS customer_key FROM ledger_entries l
           JOIN customers c ON c.shop_id = l.shop_id AND c.customer_id = l.customer_id
           WHERE l.shop_id = ? AND l.source_event_id LIKE ? ORDER BY l.rowid""",
        (current_shop(), prefix + "%"),
    ).fetchall()
    entries = []
    for entry in rows:
        balance = int(connection.execute(
            """SELECT COALESCE(SUM(CASE entry_type WHEN 'CREDIT' THEN amount_paise ELSE -amount_paise END), 0)
               FROM ledger_entries WHERE shop_id = ? AND customer_id = ? AND rowid <= ?""",
            (current_shop(), entry["customer_id"], connection.execute("SELECT rowid FROM ledger_entries WHERE entry_id = ?", (entry["entry_id"],)).fetchone()[0]),
        ).fetchone()[0])
        occurred = entry["occurred_at"]
        entries.append(PagePostedEntry(
            line_id=entry["source_event_id"][len(prefix):], entry_id=entry["entry_id"], customer_id=entry["customer_id"],
            display_name=entry["display_name"], entry_type=entry["entry_type"], amount_paise=entry["amount_paise"],
            occurred_on=datetime.fromisoformat(occurred).astimezone(SHOP_TZ).date() if occurred else None,
            customer_created=entry["customer_key"].startswith(f"{posting['idempotency_key']}:customer:"),
            balance_after_paise=balance,
        ))
    return PagePostingView(batch_id=posting["batch_id"], proposal_id=posting["proposal_id"], entries=entries,
                           customers_created=posting["customers_created"], created_at=datetime.fromisoformat(posting["created_at"]),
                           idempotent_replay=replay)
