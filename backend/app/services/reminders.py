"""Consent-aware overdue-credit reminders with a mock-only notification outbox.

Eligibility = positive balance whose oldest still-unpaid credit (FIFO: each
repayment settles the oldest open credit first) is at least N calendar days
old in the shop timezone. This is an overdue rule only: the system has no
visit records, and missing UPI activity is never treated as a missed visit.

Eligibility creates a reminder awaiting merchant approval. Approval, mock
send, and delivery receipt are separate audited transitions. No real SMS or
WhatsApp provider exists in this build.
"""

import os
import re
import sqlite3
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException

from app.domain.reminders import (
    ConsentView,
    ConsentWrite,
    CustomerConsentSummary,
    EligibilityPreview,
    EligibilityRow,
    EligibilityRunResult,
    MockDeliveryReceipt,
    OpenCredit,
    ReminderAction,
    ReminderApprove,
    ReminderView,
    ShopSettingsUpdate,
    ShopSettingsView,
    TransitionView,
)
from app.services.database import DEMO_SHOP_ID, connect
from app.services.events import append_event
from app.services.suppliers import mask_phone

DEFAULTS = {
    "timezone": "Asia/Kolkata",
    "reminder_overdue_days": 15,
    "quiet_hours_start": "21:00",
    "quiet_hours_end": "09:00",
    "reminder_min_interval_days": 7,
    "max_mock_sends_per_day": 20,
}
ACTIVE = ("PENDING_APPROVAL", "APPROVED_MOCK", "SENT_MOCK")
TRANSITIONS = {
    "PENDING_APPROVAL": {"APPROVED_MOCK", "CANCELLED", "BLOCKED_OPTED_OUT"},
    "APPROVED_MOCK": {"SENT_MOCK", "CANCELLED", "BLOCKED_OPTED_OUT"},
    "SENT_MOCK": {"DELIVERED_MOCK", "FAILED_MOCK"},
}
POLICY = ("Eligible when balance > 0 and the oldest still-unpaid credit (repayments settle oldest credits first) is at least "
          "{days} calendar days old in {tz}, with a verified contact, explicit opt-in, no opt-out, no active reminder, and no "
          "reminder in the last {interval} days. Visits are not tracked; missing UPI payments are not treated as missed visits.")
INDIAN_MOBILE = re.compile(r"^(?:\+?91|0)?([6-9]\d{9})$")


def now_utc() -> datetime:
    """Clock seam for tests and demos."""
    return datetime.now(timezone.utc)


# --- Settings ---------------------------------------------------------------

def _settings_row(connection: sqlite3.Connection) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM shop_settings WHERE shop_id = ?", (DEMO_SHOP_ID,)).fetchone()
    if row is None:
        connection.execute(
            """INSERT OR IGNORE INTO shop_settings (shop_id, timezone, reminder_overdue_days, quiet_hours_start, quiet_hours_end,
               reminder_min_interval_days, max_mock_sends_per_day, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (DEMO_SHOP_ID, *DEFAULTS.values(), now_utc().isoformat()),
        )
        row = connection.execute("SELECT * FROM shop_settings WHERE shop_id = ?", (DEMO_SHOP_ID,)).fetchone()
    return row


def _settings_view(row: sqlite3.Row) -> ShopSettingsView:
    return ShopSettingsView(
        shop_id=row["shop_id"], timezone=row["timezone"], reminder_overdue_days=row["reminder_overdue_days"],
        quiet_hours_start=row["quiet_hours_start"], quiet_hours_end=row["quiet_hours_end"],
        reminder_min_interval_days=row["reminder_min_interval_days"], max_mock_sends_per_day=row["max_mock_sends_per_day"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def get_settings() -> ShopSettingsView:
    with connect() as connection:
        return _settings_view(_settings_row(connection))


def update_settings(request: ShopSettingsUpdate) -> ShopSettingsView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required to change reminder settings.")
    try:
        ZoneInfo(request.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=422, detail="Unknown timezone name.") from None
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _settings_row(connection)
        stamp = now_utc().isoformat()
        connection.execute(
            """UPDATE shop_settings SET timezone = ?, reminder_overdue_days = ?, quiet_hours_start = ?, quiet_hours_end = ?,
               reminder_min_interval_days = ?, max_mock_sends_per_day = ?, updated_at = ? WHERE shop_id = ?""",
            (request.timezone, request.reminder_overdue_days, request.quiet_hours_start, request.quiet_hours_end,
             request.reminder_min_interval_days, request.max_mock_sends_per_day, stamp, DEMO_SHOP_ID),
        )
        settings_key = f"settings:{uuid.uuid4().hex[:12]}"
        append_event(
            connection, event_type="REMINDER_SETTINGS_UPDATED", entity_type="SHOP", entity_id=DEMO_SHOP_ID,
            source_event_id=settings_key, source_channel="text", source_utterance=None, status="POSTED",
            summary=(f"Reminder settings: {request.reminder_overdue_days}-day threshold, {request.timezone}, quiet "
                     f"{request.quiet_hours_start}-{request.quiet_hours_end}, every {request.reminder_min_interval_days}+ days."),
            idempotency_key=settings_key,
        )
        return _settings_view(_settings_row(connection))


def _tz(settings: sqlite3.Row) -> ZoneInfo:
    return ZoneInfo(settings["timezone"])


def _in_quiet_hours(settings: sqlite3.Row, moment: datetime) -> bool:
    local = moment.astimezone(_tz(settings)).time()
    start = time.fromisoformat(settings["quiet_hours_start"])
    end = time.fromisoformat(settings["quiet_hours_end"])
    if start == end:
        return False
    return start <= local < end if start < end else (local >= start or local < end)


# --- Consent ----------------------------------------------------------------

def normalize_indian_mobile(value: str) -> str | None:
    digits = re.sub(r"[\s\-()]", "", value)
    match = INDIAN_MOBILE.fullmatch(digits)
    return f"+91{match.group(1)}" if match else None


def _require_customer(connection: sqlite3.Connection, customer_id: str) -> sqlite3.Row:
    customer = connection.execute(
        "SELECT customer_id, display_name FROM customers WHERE shop_id = ? AND customer_id = ?", (DEMO_SHOP_ID, customer_id)
    ).fetchone()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found in this demo shop.")
    return customer


def _consent_view(row: sqlite3.Row) -> ConsentView:
    return ConsentView(
        consent_id=row["consent_id"], customer_id=row["customer_id"], channel=row["channel"],
        consent_status=row["consent_status"], contact_masked=mask_phone(row["contact_value"]),
        contact_verified=bool(row["contact_verified"]), verification_method=row["verification_method"],
        evidence_note=row["evidence_note"], recorded_at=datetime.fromisoformat(row["created_at"]),
        usable_for_reminders=row["consent_status"] == "OPTED_IN" and bool(row["contact_verified"]) and bool(row["contact_value"]),
    )


def _latest_consents(connection: sqlite3.Connection, customer_id: str) -> dict[str, sqlite3.Row]:
    latest = {}
    for row in connection.execute(
        """SELECT * FROM customer_contact_consents WHERE shop_id = ? AND customer_id = ?
           ORDER BY created_at, rowid""",
        (DEMO_SHOP_ID, customer_id),
    ):
        latest[row["channel"]] = row
    return latest


def record_consent(customer_id: str, request: ConsentWrite) -> ConsentView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required to record contact consent.")
    contact = None
    if request.consent_status == "OPTED_IN":
        if not request.contact_value:
            raise HTTPException(status_code=422, detail="An opt-in needs the customer's contact number.")
        contact = normalize_indian_mobile(request.contact_value)
        if contact is None:
            raise HTTPException(status_code=422, detail="Contact must be a 10-digit Indian mobile number (optionally +91).")
        if request.contact_verified and not request.verification_method:
            raise HTTPException(status_code=422, detail="Say how the number was verified (for example 'customer read it back at counter').")
    elif request.contact_value:
        contact = normalize_indian_mobile(request.contact_value)
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _require_customer(connection, customer_id)
        existing = connection.execute(
            "SELECT * FROM customer_contact_consents WHERE idempotency_key = ?", (request.idempotency_key,)
        ).fetchone()
        if existing:
            same = (existing["customer_id"] == customer_id and existing["channel"] == request.channel
                    and existing["consent_status"] == request.consent_status and existing["contact_value"] == contact)
            if not same:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different consent record.")
            return _consent_view(existing)
        consent_id = f"consent_{uuid.uuid4().hex[:12]}"
        connection.execute(
            """INSERT INTO customer_contact_consents (consent_id, shop_id, customer_id, channel, contact_value, contact_verified,
               verification_method, consent_status, evidence_note, recorded_by, idempotency_key, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'merchant', ?, ?)""",
            (consent_id, DEMO_SHOP_ID, customer_id, request.channel, contact, int(request.contact_verified),
             request.verification_method, request.consent_status, request.evidence_note.strip(), request.idempotency_key,
             now_utc().isoformat()),
        )
        append_event(
            connection, event_type=f"REMINDER_CONSENT_{request.consent_status}", entity_type="CUSTOMER", entity_id=customer_id,
            source_event_id=request.idempotency_key, source_channel="text", source_utterance=None, status="POSTED",
            summary=f"Merchant recorded {request.channel} reminder consent: {request.consent_status}.",  # no contact data
            idempotency_key=request.idempotency_key,
        )
        if request.consent_status == "OPTED_OUT":
            for reminder_id in _active_reminders(connection, customer_id, channel=request.channel):
                _transition(connection, reminder_id, "BLOCKED_OPTED_OUT", "Customer opted out.", "merchant")
        row = connection.execute("SELECT * FROM customer_contact_consents WHERE consent_id = ?", (consent_id,)).fetchone()
        return _consent_view(row)


def get_consent(customer_id: str) -> CustomerConsentSummary:
    with connect() as connection:
        _require_customer(connection, customer_id)
        latest = _latest_consents(connection, customer_id)
        count = connection.execute(
            "SELECT COUNT(*) FROM customer_contact_consents WHERE shop_id = ? AND customer_id = ?", (DEMO_SHOP_ID, customer_id)
        ).fetchone()[0]
    return CustomerConsentSummary(customer_id=customer_id, channels=[_consent_view(row) for row in latest.values()], record_count=count)


# --- FIFO aging ---------------------------------------------------------------

def open_credits(connection: sqlite3.Connection, customer_id: str, zone: ZoneInfo) -> list[OpenCredit]:
    """Credits still (partly) unpaid after applying every repayment to the oldest open credit first."""
    queue: list[dict] = []
    for row in connection.execute(
        """SELECT entry_id, entry_type, amount_paise, created_at FROM ledger_entries
           WHERE shop_id = ? AND customer_id = ? AND status = 'POSTED' ORDER BY created_at, rowid""",
        (DEMO_SHOP_ID, customer_id),
    ):
        if row["entry_type"] == "CREDIT":
            queue.append({"entry_id": row["entry_id"], "created_at": row["created_at"],
                          "original": row["amount_paise"], "remaining": row["amount_paise"]})
            continue
        payment = row["amount_paise"]
        for credit in queue:
            if payment == 0:
                break
            applied = min(payment, credit["remaining"])
            credit["remaining"] -= applied
            payment -= applied
    result = []
    for credit in queue:
        if credit["remaining"] > 0:
            created = datetime.fromisoformat(credit["created_at"])
            result.append(OpenCredit(
                entry_id=credit["entry_id"], created_at=created, local_date=created.astimezone(zone).date(),
                original_paise=credit["original"], remaining_paise=credit["remaining"],
            ))
    return result


def _active_reminders(connection: sqlite3.Connection, customer_id: str, channel: str | None = None) -> list[str]:
    rows = connection.execute(
        "SELECT reminder_id, channel FROM reminders WHERE shop_id = ? AND customer_id = ?", (DEMO_SHOP_ID, customer_id)
    ).fetchall()
    return [row["reminder_id"] for row in rows
            if (channel is None or row["channel"] == channel) and _status(connection, row["reminder_id"]) in ACTIVE]


def _status(connection: sqlite3.Connection, reminder_id: str) -> str:
    return connection.execute(
        "SELECT to_status FROM reminder_transitions WHERE reminder_id = ? ORDER BY seq DESC LIMIT 1", (reminder_id,)
    ).fetchone()[0]


def _evaluate_customer(connection, customer, settings, as_of: datetime) -> tuple[EligibilityRow, list[OpenCredit], sqlite3.Row | None]:
    zone = _tz(settings)
    credits = open_credits(connection, customer["customer_id"], zone)
    balance = sum(credit.remaining_paise for credit in credits)
    reasons: list[str] = []
    oldest = credits[0] if credits else None
    overdue_days = (as_of.astimezone(zone).date() - oldest.local_date).days if oldest else None
    if balance <= 0:
        reasons.append("NO_OUTSTANDING_BALANCE")
    elif overdue_days < settings["reminder_overdue_days"]:
        reasons.append("NOT_YET_OVERDUE")

    consents = _latest_consents(connection, customer["customer_id"])
    usable = [row for row in consents.values()
              if row["consent_status"] == "OPTED_IN" and row["contact_verified"] and row["contact_value"]]
    chosen = sorted(usable, key=lambda row: row["channel"])[0] if usable else None
    if chosen is None:
        if consents and all(row["consent_status"] == "OPTED_OUT" for row in consents.values()):
            reasons.append("OPTED_OUT")
        elif any(row["consent_status"] == "OPTED_IN" for row in consents.values()):
            reasons.append("CONTACT_NOT_VERIFIED")
        else:
            reasons.append("NO_CONSENT_RECORDED")

    if _active_reminders(connection, customer["customer_id"]):
        reasons.append("REMINDER_ALREADY_ACTIVE")
    last = connection.execute(
        "SELECT MAX(created_at) FROM reminders WHERE shop_id = ? AND customer_id = ?", (DEMO_SHOP_ID, customer["customer_id"])
    ).fetchone()[0]
    if last and as_of - datetime.fromisoformat(last) < timedelta(days=settings["reminder_min_interval_days"]):
        reasons.append("REMINDED_RECENTLY")

    row = EligibilityRow(
        customer_id=customer["customer_id"], display_name=customer["display_name"], balance_due_paise=balance,
        oldest_unpaid_since=oldest.created_at if oldest else None,
        oldest_unpaid_local_date=oldest.local_date if oldest else None,
        overdue_days=overdue_days, open_credits=credits, eligible=not reasons, reasons=reasons,
        channel=chosen["channel"] if chosen else None, contact_masked=mask_phone(chosen["contact_value"]) if chosen else None,
    )
    return row, credits, chosen


def _customers_with_ledger(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """SELECT DISTINCT c.customer_id, c.display_name FROM customers c
           JOIN ledger_entries l ON l.shop_id = c.shop_id AND l.customer_id = c.customer_id
           WHERE c.shop_id = ? ORDER BY c.display_name""",
        (DEMO_SHOP_ID,),
    ).fetchall()


def preview_eligibility(as_of: datetime | None = None) -> EligibilityPreview:
    moment = _as_of(as_of)
    with connect() as connection:
        settings = _settings_row(connection)
        rows = [_evaluate_customer(connection, customer, settings, moment)[0] for customer in _customers_with_ledger(connection)]
    return EligibilityPreview(
        as_of=moment, timezone=settings["timezone"], overdue_threshold_days=settings["reminder_overdue_days"],
        policy=POLICY.format(days=settings["reminder_overdue_days"], tz=settings["timezone"],
                             interval=settings["reminder_min_interval_days"]),
        rows=[row for row in rows if row.balance_due_paise > 0],
    )


def _as_of(value: datetime | None) -> datetime:
    if value is None:
        return now_utc()
    if value.tzinfo is None:
        raise HTTPException(status_code=422, detail="as_of must include a timezone offset.")
    return value


def run_eligibility(as_of: datetime | None = None) -> EligibilityRunResult:
    """Scheduler-safe: re-running for the same debt never creates a second reminder (dedupe key + active check)."""
    moment = _as_of(as_of)
    created_ids: list[str] = []
    cancelled: list[str] = []
    skipped: dict[str, int] = {}
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        settings = _settings_row(connection)
        cancelled += _cancel_settled(connection)
        for customer in _customers_with_ledger(connection):
            row, credits, consent = _evaluate_customer(connection, customer, settings, moment)
            if row.balance_due_paise <= 0:
                continue
            if not row.eligible:
                for reason in row.reasons:
                    skipped[reason] = skipped.get(reason, 0) + 1
                continue
            anchor = credits[0]
            cycle = row.overdue_days // settings["reminder_min_interval_days"]
            dedupe_key = f"{customer['customer_id']}:{anchor.entry_id}:{consent['channel']}:{cycle}"
            if connection.execute("SELECT 1 FROM reminders WHERE dedupe_key = ?", (dedupe_key,)).fetchone():
                skipped["DUPLICATE_SUPPRESSED"] = skipped.get("DUPLICATE_SUPPRESSED", 0) + 1
                continue
            reminder_id = f"reminder_{uuid.uuid4().hex[:12]}"
            connection.execute(
                """INSERT INTO reminders (reminder_id, shop_id, customer_id, channel, consent_id, anchor_entry_id,
                   oldest_unpaid_since, oldest_unpaid_local_date, overdue_days, outstanding_paise, dedupe_key, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (reminder_id, DEMO_SHOP_ID, customer["customer_id"], consent["channel"], consent["consent_id"], anchor.entry_id,
                 anchor.created_at.isoformat(), anchor.local_date.isoformat(), row.overdue_days, row.balance_due_paise,
                 dedupe_key, moment.isoformat()),
            )
            _transition(connection, reminder_id, "PENDING_APPROVAL",
                        f"Oldest unpaid credit is {row.overdue_days} days old (threshold {settings['reminder_overdue_days']}).",
                        "system", allow_initial=True)
            created_ids.append(reminder_id)
        created = [_reminder_view(connection, reminder_id) for reminder_id in created_ids]
    return EligibilityRunResult(as_of=moment, created=created, cancelled_reminder_ids=cancelled, skipped_by_reason=skipped)


def _cancel_settled(connection: sqlite3.Connection) -> list[str]:
    cancelled = []
    customers = {row["customer_id"] for row in connection.execute("SELECT DISTINCT customer_id FROM reminders WHERE shop_id = ?", (DEMO_SHOP_ID,))}
    for customer_id in customers:
        cancelled += cancel_reminders_if_settled(connection, customer_id)
    return cancelled


def cancel_reminders_if_settled(connection: sqlite3.Connection, customer_id: str) -> list[str]:
    """Called inside ledger/payment transactions after a repayment: full repayment cancels pending reminders."""
    balance = connection.execute(
        """SELECT COALESCE(SUM(CASE entry_type WHEN 'CREDIT' THEN amount_paise ELSE -amount_paise END), 0)
           FROM ledger_entries WHERE shop_id = ? AND customer_id = ? AND status = 'POSTED'""",
        (DEMO_SHOP_ID, customer_id),
    ).fetchone()[0]
    if balance > 0:
        return []
    cancelled = []
    for reminder_id in _active_reminders(connection, customer_id):
        if _status(connection, reminder_id) in ("PENDING_APPROVAL", "APPROVED_MOCK"):
            _transition(connection, reminder_id, "CANCELLED", "Balance fully repaid.", "system")
            cancelled.append(reminder_id)
    return cancelled


# --- Transitions ------------------------------------------------------------

def _transition(connection, reminder_id: str, to_status: str, reason: str, actor: str, *, allow_initial: bool = False,
                message_text: str | None = None, include_amount: bool | None = None, provider: str | None = None,
                provider_message_id: str | None = None, idempotency_key: str | None = None) -> None:
    if not allow_initial:
        current = _status(connection, reminder_id)
        if to_status not in TRANSITIONS.get(current, set()):
            raise HTTPException(status_code=409, detail={"code": "INVALID_TRANSITION", "from": current, "to": to_status})
    stamp = now_utc().isoformat()
    transition_id = f"rtr_{uuid.uuid4().hex[:12]}"
    connection.execute(
        """INSERT INTO reminder_transitions (transition_id, reminder_id, to_status, reason, actor, message_text, include_amount,
           provider, provider_message_id, idempotency_key, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (transition_id, reminder_id, to_status, reason, actor, message_text,
         None if include_amount is None else int(include_amount), provider, provider_message_id, idempotency_key, stamp),
    )
    customer_id = connection.execute("SELECT customer_id FROM reminders WHERE reminder_id = ?", (reminder_id,)).fetchone()[0]
    append_event(
        connection, event_type=f"REMINDER_{to_status}", entity_type="REMINDER", entity_id=reminder_id,
        source_event_id=transition_id, source_channel="provider_mock" if actor == "provider_mock" else ("system" if actor == "system" else "text"),
        source_utterance=None, status="POSTED",
        summary=f"Reminder for customer {customer_id} → {to_status} ({reason})" + (" [MOCK — nothing sent]" if "MOCK" in to_status else ""),
        idempotency_key=transition_id,
    )


def _replayed(connection, reminder_id: str, idempotency_key: str, to_statuses: set[str]) -> bool:
    row = connection.execute(
        "SELECT reminder_id, to_status FROM reminder_transitions WHERE idempotency_key = ?", (idempotency_key,)
    ).fetchone()
    if row is None:
        return False
    if row["reminder_id"] != reminder_id or row["to_status"] not in to_statuses:
        raise HTTPException(status_code=409, detail="Idempotency key was already used for a different reminder action.")
    return True


def _message(display_name: str, amount_paise: int | None) -> str:
    amount = f" of ₹{amount_paise // 100:,}.{amount_paise % 100:02d}" if amount_paise is not None else ""
    return (f"Hello {display_name}, our records show an outstanding shop balance{amount}. "
            "Please contact the shop if you'd like to review it. Reply STOP to stop these reminders.")


def _current_balance(connection, customer_id: str) -> int:
    return int(connection.execute(
        """SELECT COALESCE(SUM(CASE entry_type WHEN 'CREDIT' THEN amount_paise ELSE -amount_paise END), 0)
           FROM ledger_entries WHERE shop_id = ? AND customer_id = ? AND status = 'POSTED'""",
        (DEMO_SHOP_ID, customer_id),
    ).fetchone()[0])


def _load(connection, reminder_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM reminders WHERE shop_id = ? AND reminder_id = ?", (DEMO_SHOP_ID, reminder_id)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Reminder not found in this demo shop.")
    return row


def _revalidate(connection, reminder: sqlite3.Row) -> None:
    """Before approval/send: debt must still exist and consent must still be valid."""
    if _current_balance(connection, reminder["customer_id"]) <= 0:
        _transition(connection, reminder["reminder_id"], "CANCELLED", "Balance fully repaid.", "system")
        connection.commit()
        raise HTTPException(status_code=409, detail={"code": "BALANCE_CLEARED", "status": "CANCELLED"})
    consent = _latest_consents(connection, reminder["customer_id"]).get(reminder["channel"])
    if consent is None or consent["consent_status"] != "OPTED_IN" or not consent["contact_verified"]:
        _transition(connection, reminder["reminder_id"], "BLOCKED_OPTED_OUT", "Consent no longer valid.", "system")
        connection.commit()
        raise HTTPException(status_code=409, detail={"code": "CONSENT_NOT_VALID", "status": "BLOCKED_OPTED_OUT"})


def approve_reminder(reminder_id: str, request: ReminderApprove) -> ReminderView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant approval must be explicit.")
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        reminder = _load(connection, reminder_id)
        if not _replayed(connection, reminder_id, request.idempotency_key, {"APPROVED_MOCK"}):
            if _status(connection, reminder_id) != "PENDING_APPROVAL":
                raise HTTPException(status_code=409, detail={"code": "INVALID_TRANSITION", "from": _status(connection, reminder_id)})
            _revalidate(connection, reminder)
            name = _require_customer(connection, reminder["customer_id"])["display_name"]
            amount = _current_balance(connection, reminder["customer_id"]) if request.include_amount else None
            _transition(connection, reminder_id, "APPROVED_MOCK", "Merchant reviewed recipient, amount, and message.", "merchant",
                        message_text=_message(name, amount), include_amount=request.include_amount,
                        idempotency_key=request.idempotency_key)
        return _reminder_view(connection, reminder_id)


def cancel_reminder(reminder_id: str, request: ReminderAction) -> ReminderView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required to cancel a reminder.")
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _load(connection, reminder_id)
        if not _replayed(connection, reminder_id, request.idempotency_key, {"CANCELLED"}):
            _transition(connection, reminder_id, "CANCELLED", request.reason or "Cancelled by merchant.", "merchant",
                        idempotency_key=request.idempotency_key)
        return _reminder_view(connection, reminder_id)


class MockNotificationProvider:
    """Records a simulated send. Never contacts a phone number or network."""

    name = "mock"

    def send(self, channel: str, message: str) -> str:
        return f"mock_{uuid.uuid4().hex[:16]}"


def get_notification_provider() -> MockNotificationProvider:
    choice = os.environ.get("MUNIM_NOTIFICATION_PROVIDER", "mock").strip().lower()
    if choice != "mock":
        # Real SMS/WhatsApp adapters are intentionally absent: this prototype has no authentication,
        # consent audit sign-off, approved templates, or provider credentials.
        raise HTTPException(status_code=503, detail="Only the mock notification provider exists in this build; no real sending is possible.")
    return MockNotificationProvider()


def mock_send(reminder_id: str, request: ReminderAction) -> ReminderView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Explicit confirmation is required for a mock send.")
    provider = get_notification_provider()
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        reminder = _load(connection, reminder_id)
        if _replayed(connection, reminder_id, request.idempotency_key, {"SENT_MOCK"}):
            return _reminder_view(connection, reminder_id)
        if _status(connection, reminder_id) != "APPROVED_MOCK":
            raise HTTPException(status_code=409, detail={"code": "NOT_APPROVED", "status": _status(connection, reminder_id)})
        _revalidate(connection, reminder)
        settings = _settings_row(connection)
        moment = now_utc()
        if _in_quiet_hours(settings, moment):
            raise HTTPException(status_code=409, detail={
                "code": "QUIET_HOURS", "message": f"Quiet hours {settings['quiet_hours_start']}-{settings['quiet_hours_end']} ({settings['timezone']}).",
            })
        zone = _tz(settings)
        day_start = datetime.combine(moment.astimezone(zone).date(), time(0), tzinfo=zone).astimezone(timezone.utc).isoformat()
        sent_today = connection.execute(
            """SELECT COUNT(*) FROM reminder_transitions t JOIN reminders r ON r.reminder_id = t.reminder_id
               WHERE r.shop_id = ? AND t.to_status = 'SENT_MOCK' AND t.created_at >= ?""",
            (DEMO_SHOP_ID, day_start),
        ).fetchone()[0]
        if sent_today >= settings["max_mock_sends_per_day"]:
            raise HTTPException(status_code=429, detail={"code": "DAILY_LIMIT", "limit": settings["max_mock_sends_per_day"]})
        message = connection.execute(
            """SELECT message_text FROM reminder_transitions WHERE reminder_id = ? AND to_status = 'APPROVED_MOCK'
               ORDER BY seq DESC LIMIT 1""", (reminder_id,),
        ).fetchone()[0]
        message_id = provider.send(reminder["channel"], message)
        _transition(connection, reminder_id, "SENT_MOCK", "Simulated send recorded; no real message left the system.",
                    "provider_mock", provider=provider.name, provider_message_id=message_id,
                    idempotency_key=request.idempotency_key)
        return _reminder_view(connection, reminder_id)


def record_mock_delivery(reminder_id: str, request: MockDeliveryReceipt) -> ReminderView:
    target = "DELIVERED_MOCK" if request.outcome == "DELIVERED" else "FAILED_MOCK"
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _load(connection, reminder_id)
        if not _replayed(connection, reminder_id, request.idempotency_key, {target}):
            _transition(connection, reminder_id, target, f"Simulated delivery receipt: {request.outcome}.", "provider_mock",
                        provider="mock", idempotency_key=request.idempotency_key)
        return _reminder_view(connection, reminder_id)


# --- Views ------------------------------------------------------------------

def _reminder_view(connection, reminder_id: str) -> ReminderView:
    reminder = _load(connection, reminder_id)
    customer = _require_customer(connection, reminder["customer_id"])
    transitions = connection.execute(
        "SELECT * FROM reminder_transitions WHERE reminder_id = ? ORDER BY seq", (reminder_id,)
    ).fetchall()
    approved = [row for row in transitions if row["to_status"] == "APPROVED_MOCK"]
    include_amount = bool(approved[-1]["include_amount"]) if approved else False
    message = approved[-1]["message_text"] if approved else _message(customer["display_name"], None)
    consent = connection.execute("SELECT contact_value FROM customer_contact_consents WHERE consent_id = ?", (reminder["consent_id"],)).fetchone()
    return ReminderView(
        reminder_id=reminder_id, customer_id=reminder["customer_id"], display_name=customer["display_name"],
        channel=reminder["channel"], contact_masked=mask_phone(consent["contact_value"]), status=transitions[-1]["to_status"],
        outstanding_at_eligibility_paise=reminder["outstanding_paise"],
        current_balance_paise=_current_balance(connection, reminder["customer_id"]),
        oldest_unpaid_local_date=date.fromisoformat(reminder["oldest_unpaid_local_date"]),
        overdue_days_at_eligibility=reminder["overdue_days"], eligibility_reason=transitions[0]["reason"],
        message_preview=message, include_amount=include_amount, created_at=datetime.fromisoformat(reminder["created_at"]),
        transitions=[TransitionView(
            to_status=row["to_status"], reason=row["reason"], actor=row["actor"], provider=row["provider"],
            provider_message_id=row["provider_message_id"], created_at=datetime.fromisoformat(row["created_at"]),
        ) for row in transitions],
    )


def get_reminder(reminder_id: str) -> ReminderView:
    with connect() as connection:
        return _reminder_view(connection, reminder_id)


def list_reminders(status: str | None = None, limit: int = 50) -> list[ReminderView]:
    with connect() as connection:
        ids = [row[0] for row in connection.execute(
            "SELECT reminder_id FROM reminders WHERE shop_id = ? ORDER BY created_at DESC LIMIT ?",
            (DEMO_SHOP_ID, min(max(limit, 1), 200)),
        )]
        views = [_reminder_view(connection, reminder_id) for reminder_id in ids]
    return [view for view in views if status is None or view.status == status]
