"""N8 recovery concierge (focused core).

* Explain who owes what and why, using the same FIFO aging and eligibility rules as reminders.
* Draft the reminder in the customer's language (Sarvam translate; numbers must survive, else English).
* At approval, optionally attach a UPI pay link carrying a unique reference (``tr=``).
* Payments that come back with that reference are matched to the customer (see payments.py).

Nothing here sends a message: approval and the mock outbox in reminders.py are unchanged.
"""

import sqlite3
import uuid
from datetime import datetime
from urllib.parse import quote, urlencode

from fastapi import HTTPException

from app.domain.recovery import (
    ActiveReminderSummary,
    CollectionRequestView,
    LanguagePreferenceView,
    LanguagePreferenceWrite,
    PaymentLinkPreview,
    PaymentProfileView,
    PaymentProfileWrite,
    RecoveryBrief,
    RecoveryDraft,
)
from app.services import reminders, sarvam
from app.services.database import connect, current_shop
from app.services.events import append_event

DEFAULT_LANGUAGE = "en-IN"
REASON_TEXT = {
    "NO_OUTSTANDING_BALANCE": "Nothing is due.",
    "NOT_YET_OVERDUE": "The oldest unpaid udhaar is {days} days old; reminders start at {threshold} days.",
    "NO_CONSENT_RECORDED": "No reminder consent is recorded. Ask the customer at the counter before reminding them.",
    "CONTACT_NOT_VERIFIED": "The customer opted in, but their number is not verified yet.",
    "OPTED_OUT": "The customer opted out of reminders.",
    "REMINDER_ALREADY_ACTIVE": "A reminder is already waiting for approval or was just sent.",
    "REMINDED_RECENTLY": "The customer was reminded within the last {interval} days.",
}


def _rupees(paise: int) -> str:
    return f"₹{paise // 100:,}.{paise % 100:02d}"


# --- Shop UPI profile ---------------------------------------------------------

def _profile_row(connection: sqlite3.Connection) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM shop_payment_profiles WHERE shop_id = ?", (current_shop(),)).fetchone()


def _profile_view(row: sqlite3.Row) -> PaymentProfileView:
    return PaymentProfileView(shop_id=row["shop_id"], upi_vpa=row["upi_vpa"], payee_name=row["payee_name"],
                              updated_at=datetime.fromisoformat(row["updated_at"]))


def get_payment_profile() -> PaymentProfileView:
    with connect() as connection:
        row = _profile_row(connection)
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "UPI_PROFILE_MISSING", "message": "Set the shop's UPI ID first."})
    return _profile_view(row)


def set_payment_profile(request: PaymentProfileWrite) -> PaymentProfileView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required to set the shop's UPI ID.")
    stamp = reminders.now_utc().isoformat()
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """INSERT INTO shop_payment_profiles (shop_id, upi_vpa, payee_name, updated_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(shop_id) DO UPDATE SET upi_vpa = excluded.upi_vpa, payee_name = excluded.payee_name,
               updated_at = excluded.updated_at""",
            (current_shop(), request.upi_vpa.strip(), request.payee_name.strip(), stamp),
        )
        event_key = f"upi-profile:{uuid.uuid4().hex[:12]}"
        append_event(
            connection, event_type="UPI_PROFILE_UPDATED", entity_type="SHOP", entity_id=current_shop(),
            source_event_id=event_key, source_channel="text", source_utterance=None, status="POSTED",
            summary="Merchant set the shop UPI ID used for customer pay links.", idempotency_key=event_key,
        )
        return _profile_view(_profile_row(connection))


# --- Customer language ----------------------------------------------------------

def _language(connection: sqlite3.Connection, customer_id: str) -> tuple[str, bool]:
    row = connection.execute(
        "SELECT language_code FROM customer_preferences WHERE shop_id = ? AND customer_id = ?", (current_shop(), customer_id)
    ).fetchone()
    return (row["language_code"], False) if row else (DEFAULT_LANGUAGE, True)


def _language_view(customer_id: str, code: str, is_default: bool) -> LanguagePreferenceView:
    return LanguagePreferenceView(customer_id=customer_id, language_code=code, language_name=sarvam.LANGUAGES[code],
                                  is_default=is_default)


def get_language(customer_id: str) -> LanguagePreferenceView:
    with connect() as connection:
        reminders._require_customer(connection, customer_id)
        return _language_view(customer_id, *_language(connection, customer_id))


def set_language(customer_id: str, request: LanguagePreferenceWrite) -> LanguagePreferenceView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required to change the reminder language.")
    if request.language_code not in sarvam.LANGUAGES:
        raise HTTPException(status_code=422, detail={"code": "UNSUPPORTED_LANGUAGE", "supported": sorted(sarvam.LANGUAGES)})
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        reminders._require_customer(connection, customer_id)
        connection.execute(
            """INSERT INTO customer_preferences (shop_id, customer_id, language_code, updated_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(shop_id, customer_id) DO UPDATE SET language_code = excluded.language_code,
               updated_at = excluded.updated_at""",
            (current_shop(), customer_id, request.language_code, reminders.now_utc().isoformat()),
        )
        event_key = f"language:{uuid.uuid4().hex[:12]}"
        append_event(
            connection, event_type="CUSTOMER_LANGUAGE_SET", entity_type="CUSTOMER", entity_id=customer_id,
            source_event_id=event_key, source_channel="text", source_utterance=None, status="POSTED",
            summary=f"Reminder language set to {sarvam.LANGUAGES[request.language_code]}.", idempotency_key=event_key,
        )
        return _language_view(customer_id, request.language_code, False)


# --- UPI links and collection requests -----------------------------------------

def build_upi_link(upi_vpa: str, payee_name: str, reference: str, amount_paise: int | None) -> str:
    """Standard UPI deep link. Without an amount the customer types it in their UPI app."""
    params = {"pa": upi_vpa, "pn": payee_name, "tr": reference, "tn": f"Shop balance {reference}", "cu": "INR"}
    if amount_paise is not None:
        params["am"] = f"{amount_paise // 100}.{amount_paise % 100:02d}"
    return "upi://pay?" + urlencode(params, quote_via=quote)


def create_collection_request(connection: sqlite3.Connection, customer_id: str, reminder_id: str | None,
                              amount_paise: int | None, balance_paise: int) -> sqlite3.Row:
    """Inside the caller's transaction. Raises 409 when the shop has no UPI ID."""
    profile = _profile_row(connection)
    if profile is None:
        raise HTTPException(status_code=409, detail={"code": "UPI_PROFILE_MISSING",
                                                     "message": "Set the shop's UPI ID (POST /recovery/payment-profile) first."})
    request_id = f"collect_{uuid.uuid4().hex[:12]}"
    reference = f"MJ{uuid.uuid4().hex[:12].upper()}"
    link = build_upi_link(profile["upi_vpa"], profile["payee_name"], reference, amount_paise)
    connection.execute(
        """INSERT INTO collection_requests (request_id, shop_id, customer_id, reminder_id, reference, amount_paise,
           balance_at_request_paise, upi_vpa, payee_name, upi_link, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (request_id, current_shop(), customer_id, reminder_id, reference, amount_paise, balance_paise,
         profile["upi_vpa"], profile["payee_name"], link, reminders.now_utc().isoformat()),
    )
    append_event(
        connection, event_type="COLLECTION_REQUEST_CREATED", entity_type="CUSTOMER", entity_id=customer_id,
        source_event_id=request_id, source_channel="text", source_utterance=None, status="POSTED",
        summary=f"UPI pay link prepared with reference {reference}" + (f" for {_rupees(amount_paise)}." if amount_paise else "."),
        idempotency_key=request_id,
    )
    return connection.execute("SELECT * FROM collection_requests WHERE request_id = ?", (request_id,)).fetchone()


def find_collection_request(connection: sqlite3.Connection, reference: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM collection_requests WHERE shop_id = ? AND reference = ?", (current_shop(), reference.strip().upper())
    ).fetchone()


def _collection_view(connection: sqlite3.Connection, row: sqlite3.Row) -> CollectionRequestView:
    paid = int(connection.execute(
        """SELECT COALESCE(SUM(amount_paise), 0) FROM payment_events
           WHERE shop_id = ? AND collection_request_id = ? AND resolution_status = 'ALLOCATED'""",
        (current_shop(), row["request_id"]),
    ).fetchone()[0])
    # Payments that went to review and were later allocated by the merchant to this same customer.
    paid += int(connection.execute(
        """SELECT COALESCE(SUM(r.amount_paise), 0) FROM payment_resolutions r
           JOIN payment_events p ON p.shop_id = r.shop_id AND p.event_id = r.event_id
           WHERE r.shop_id = ? AND p.collection_request_id = ? AND r.customer_id = ?""",
        (current_shop(), row["request_id"], row["customer_id"]),
    ).fetchone()[0])
    target = row["amount_paise"] or row["balance_at_request_paise"]
    status = "OPEN" if paid == 0 else ("PAID" if paid >= target else "PART_PAID")
    return CollectionRequestView(
        request_id=row["request_id"], customer_id=row["customer_id"], reminder_id=row["reminder_id"],
        reference=row["reference"], amount_paise=row["amount_paise"], balance_at_request_paise=row["balance_at_request_paise"],
        paid_paise=paid, status=status, upi_link=row["upi_link"], created_at=datetime.fromisoformat(row["created_at"]),
    )


def collection_requests_for(connection: sqlite3.Connection, customer_id: str) -> list[CollectionRequestView]:
    rows = connection.execute(
        "SELECT * FROM collection_requests WHERE shop_id = ? AND customer_id = ? ORDER BY created_at DESC, rowid DESC",
        (current_shop(), customer_id),
    ).fetchall()
    return [_collection_view(connection, row) for row in rows]


def collection_for_reminder(connection: sqlite3.Connection, reminder_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM collection_requests WHERE reminder_id = ? ORDER BY created_at DESC LIMIT 1", (reminder_id,)
    ).fetchone()


def list_collection_requests(customer_id: str) -> list[CollectionRequestView]:
    with connect() as connection:
        reminders._require_customer(connection, customer_id)
        return collection_requests_for(connection, customer_id)


# --- Recovery brief (read-only) --------------------------------------------------

def _explanation(name: str, balance: int, credits, overdue_days: int | None) -> str:
    if balance <= 0 or not credits:
        return f"{name} has nothing due."
    oldest = credits[0]
    part = "" if oldest.remaining_paise == oldest.original_paise else f" ({_rupees(oldest.remaining_paise)} still unpaid)"
    text = (f"{name} owes {_rupees(balance)}. The oldest unpaid udhaar is {_rupees(oldest.original_paise)}{part} from "
            f"{oldest.local_date.isoformat()}, {overdue_days} days ago. Repayments are applied to the oldest udhaar first.")
    if len(credits) > 1:
        text += f" {len(credits)} udhaar entries are still open."
    return text


def recovery_brief(customer_id: str, language: str | None = None, include_amount: bool = True,
                   as_of: datetime | None = None) -> RecoveryBrief:
    if language is not None and language not in sarvam.LANGUAGES:
        raise HTTPException(status_code=422, detail={"code": "UNSUPPORTED_LANGUAGE", "supported": sorted(sarvam.LANGUAGES)})
    moment = reminders._as_of(as_of)
    with connect() as connection:
        customer = reminders._require_customer(connection, customer_id)
        settings = reminders._settings_row(connection)
        row, credits, _ = reminders._evaluate_customer(connection, customer, settings, moment)
        active_ids = reminders._active_reminders(connection, customer_id)
        active = (ActiveReminderSummary(reminder_id=active_ids[-1], status=reminders._status(connection, active_ids[-1]))
                  if active_ids else None)
        requests = collection_requests_for(connection, customer_id)
        profile = _profile_row(connection)
        stored_language, _ = _language(connection, customer_id)
    # Network (Sarvam) happens after the database connection is closed.
    target = language or stored_language
    source = reminders._message(customer["display_name"], row.balance_due_paise if include_amount and row.balance_due_paise > 0 else None)
    translated = sarvam.translate(source, target)
    numbers_ok = sarvam.numbers_match(source, translated.text)
    if translated.status == "TRANSLATED" and not numbers_ok:  # defensive: never show a draft whose numbers changed
        translated = sarvam.TranslationResult(source, "en-IN", "FALLBACK_SOURCE", translated.provider)
        numbers_ok = True
    draft = RecoveryDraft(
        source_text=source, language_code=translated.language_code, text=translated.text,
        translation_status=translated.status, translation_provider=translated.provider,
        include_amount=include_amount and row.balance_due_paise > 0, numbers_verified=numbers_ok,
    )
    reason_texts = [REASON_TEXT.get(reason, reason).format(
        days=row.overdue_days, threshold=settings["reminder_overdue_days"], interval=settings["reminder_min_interval_days"],
    ) for reason in row.reasons]
    approve_payload = {"confirmed": True, "include_amount": draft.include_amount, "include_payment_link": profile is not None,
                       "idempotency_key": "<new unique key>"}
    if draft.translation_status == "TRANSLATED":
        approve_payload |= {"language_code": draft.language_code, "localized_message": draft.text}
    return RecoveryBrief(
        customer_id=customer_id, display_name=customer["display_name"], as_of=moment,
        balance_due_paise=row.balance_due_paise, overdue_threshold_days=settings["reminder_overdue_days"],
        overdue_days=row.overdue_days, oldest_unpaid_local_date=row.oldest_unpaid_local_date, open_credits=credits,
        explanation=_explanation(customer["display_name"], row.balance_due_paise, credits, row.overdue_days),
        eligible=row.eligible, reasons=row.reasons, reason_explanations=reason_texts,
        channel=row.channel, contact_masked=row.contact_masked, active_reminder=active, draft=draft,
        payment_link=PaymentLinkPreview(
            available=profile is not None, upi_vpa=profile["upi_vpa"] if profile else None,
            payee_name=profile["payee_name"] if profile else None,
            note=("A unique payment reference is created when the merchant approves the reminder with include_payment_link."
                  if profile else "Set the shop's UPI ID (POST /recovery/payment-profile) to attach a pay link."),
        ),
        collection_requests=requests, approve_payload=approve_payload,
    )
