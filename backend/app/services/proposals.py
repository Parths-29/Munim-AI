"""Versioned stock-inflow proposals: creation, merchant revision, and validation.

Nothing in this module changes stock or supplier payables. Validation is
recomputed on every read so a proposal always reflects current products,
suppliers, conversions, and posted invoices.
"""

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException

from app.domain.intake import (
    DraftContent,
    DraftInvoice,
    DraftLine,
    DraftSupplier,
    ExtractionView,
    InvoiceEdit,
    InvoiceHeaderView,
    Issue,
    LineEdit,
    LineView,
    ManualInvoiceCreate,
    ProposalReject,
    ProposalRevise,
    ProposalTotals,
    ProposalView,
    SupplierEdit,
    SupplierMatchView,
)
from app.domain.models import ProductView
from app.services.database import DEMO_SHOP_ID, connect
from app.services.image_validation import validate_invoice_image
from app.services.invoice_extraction import ProviderUnavailable, RawExtraction, get_invoice_provider
from app.services.ledger import normalize_alias
from app.services.suppliers import resolve_supplier_in, supplier_view
from app.services.units import canonical_unit, normalize_invoice_number, parse_money_to_paise, parse_quantity

TERMINAL = {"CONFIRMED", "REJECTED", "EXPIRED"}
INVOICE_KINDS = {"invoice_image", "manual_invoice"}
INWARD_KINDS = {"voice_inward", "text_inward"}
HEADER_FIELDS = ("invoice_number", "invoice_date", "total_paise")


def _env_number(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def min_confidence() -> float:
    return min(max(_env_number("MUNIM_INTAKE_MIN_CONFIDENCE", 0.80), 0), 1)


def rounding_tolerance() -> int:
    return max(int(_env_number("MUNIM_INVOICE_ROUNDING_TOLERANCE_PAISE", 100)), 0)


def expiry_days() -> int:
    return max(int(_env_number("MUNIM_PROPOSAL_EXPIRY_DAYS", 7)), 1)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def content_hash(draft: DraftContent) -> str:
    canonical = json.dumps(draft.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def new_line_id() -> str:
    return f"line_{uuid.uuid4().hex[:10]}"


# --- Converting untrusted extraction output into a draft --------------------

def _text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] or None


def _confidence(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0.0, min(1.0, float(value)))


def _parse_date(value: object, notes: list[str]) -> date | None:
    text = _text(value, 20)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    for separator in ("/", "-", "."):
        parts = text.split(separator)
        if len(parts) == 3 and all(part.isdigit() for part in parts) and len(parts[2]) == 4:
            day, month, year = (int(part) for part in parts)
            try:
                parsed = date(year, month, day)
            except ValueError:
                break
            if day <= 12 and month <= 12 and day != month:
                notes.append(f"Invoice date '{text}' read as day/month/year (Indian convention); please verify.")
            return parsed
    notes.append(f"Invoice date '{text}' could not be read; enter it manually if needed.")
    return None


def draft_from_extraction(raw: RawExtraction, supplier_id: str | None = None) -> tuple[DraftContent, list[str]]:
    data = raw.data
    notes: list[str] = []
    header_conf_raw = data.get("header_confidence") if isinstance(data.get("header_confidence"), dict) else {}
    field_confidence = {}
    for source_key, target in (("invoice_number", "invoice_number"), ("invoice_date_text", "invoice_date"), ("total", "total_paise")):
        value = _confidence(header_conf_raw.get(source_key))
        if value is not None:
            field_confidence[target] = value

    def money(name: str, allow_negative: bool = False) -> int | None:
        paise, note = parse_money_to_paise(data.get(name), allow_negative=allow_negative)
        if note:
            notes.append(f"{name}: {note}")
        return paise

    invoice = DraftInvoice(
        invoice_number=_text(data.get("invoice_number"), 60),
        invoice_date=_parse_date(data.get("invoice_date_text"), notes),
        subtotal_paise=money("subtotal"),
        tax_paise=money("tax_total"),
        discount_paise=money("discount"),
        freight_paise=money("freight"),
        other_charges_paise=money("other_charges"),
        rounding_paise=money("rounding", allow_negative=True),
        total_paise=money("total"),
        field_confidence=field_confidence,
    )
    supplier = DraftSupplier(
        supplier_id=supplier_id,
        label=_text(data.get("supplier_name"), 100),
        confidence=_confidence(data.get("supplier_confidence") if data.get("supplier_confidence") is not None else header_conf_raw.get("supplier_name")),
        verified=supplier_id is not None,
    )
    lines = []
    raw_lines = data.get("lines") if isinstance(data.get("lines"), list) else []
    if len(raw_lines) > 100:
        notes.append("Only the first 100 lines were kept; add the rest manually.")
    for item in raw_lines[:100]:
        if not isinstance(item, dict):
            continue
        line_notes: list[str] = []
        quantity, note = parse_quantity(item.get("quantity"))
        if note:
            line_notes.append(note)
        unit_cost, note = parse_money_to_paise(item.get("unit_price"))
        if note:
            line_notes.append(f"unit price: {note}")
        line_total, note = parse_money_to_paise(item.get("line_total"))
        if note:
            line_notes.append(f"line total: {note}")
        lines.append(DraftLine(
            line_id=new_line_id(),
            source_text=_text(item.get("source_text"), 240),
            product_name_text=_text(item.get("product_name"), 120),
            quantity=quantity,
            unit_text=_text(item.get("unit"), 32),
            unit_cost_paise=unit_cost,
            line_total_paise=line_total,
            confidence=_confidence(item.get("confidence")),
            parse_notes=line_notes,
        ))
    return DraftContent(supplier=supplier, invoice=invoice, lines=lines), notes


def draft_from_edits(
    supplier: SupplierEdit,
    invoice: InvoiceEdit,
    line_edits: list[LineEdit],
    previous: DraftContent | None = None,
) -> DraftContent:
    previous_lines = {line.line_id: line for line in previous.lines} if previous else {}
    previous_conf = previous.invoice.field_confidence if previous else {}
    lines = []
    seen = set()
    for edit in line_edits:
        if edit.line_id and edit.line_id in seen:
            raise HTTPException(status_code=422, detail=f"Line {edit.line_id} appears more than once.")
        if edit.line_id and edit.line_id not in previous_lines:
            raise HTTPException(status_code=422, detail=f"Line {edit.line_id} is not part of this proposal; omit line_id to add a line.")
        old = previous_lines.get(edit.line_id) if edit.line_id else None
        line_id = old.line_id if old else new_line_id()
        seen.add(line_id)
        lines.append(DraftLine(
            line_id=line_id,
            source_text=old.source_text if old else None,
            product_name_text=edit.product_name_text.strip() if edit.product_name_text else None,
            product_id=edit.product_id,
            quantity=edit.quantity,
            unit_text=edit.unit_text.strip() if edit.unit_text else None,
            conversion_factor=edit.conversion_factor,
            unit_cost_paise=edit.unit_cost_paise,
            line_total_paise=edit.line_total_paise,
            confidence=old.confidence if old else None,
            merchant_verified=edit.merchant_verified,
            accepted=edit.accepted,
            parse_notes=[],
        ))
    previous_supplier = previous.supplier if previous else DraftSupplier()
    return DraftContent(
        supplier=DraftSupplier(
            supplier_id=supplier.supplier_id,
            label=supplier.label.strip() if supplier.label else None,
            confidence=previous_supplier.confidence,
            verified=True,
        ),
        invoice=DraftInvoice(
            **invoice.model_dump(exclude={"verified"}),
            field_confidence=previous_conf,
            verified=invoice.verified,
        ),
        lines=lines,
    )


# --- Persistence ------------------------------------------------------------

def insert_proposal(
    connection: sqlite3.Connection,
    *,
    source_kind: str,
    draft: DraftContent,
    extraction: ExtractionView,
    idempotency_key: str,
    image_sha256: str | None = None,
    source_utterance: str | None = None,
    actor: str,
    parse_notes: list[str] | None = None,
) -> str:
    proposal_id = f"proposal_{uuid.uuid4().hex[:12]}"
    created = now_utc()
    digest = content_hash(draft)
    draft_json = draft.model_dump_json()
    extraction_payload = {**extraction.model_dump(mode="json"), "notes": parse_notes or []}
    connection.execute(
        """INSERT INTO intake_proposals
           (proposal_id, shop_id, source_kind, status, version, content_hash, draft_json, extraction_json,
            image_sha256, source_utterance, idempotency_key, posted_receipt_id, created_at, updated_at, expires_at)
           VALUES (?, ?, ?, 'NEEDS_REVIEW', 1, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)""",
        (proposal_id, DEMO_SHOP_ID, source_kind, digest, draft_json, json.dumps(extraction_payload),
         image_sha256, source_utterance, idempotency_key, created.isoformat(), created.isoformat(),
         (created + timedelta(days=expiry_days())).isoformat()),
    )
    connection.execute(
        """INSERT INTO intake_proposal_revisions (revision_id, proposal_id, version, content_hash, draft_json, actor, created_at)
           VALUES (?, ?, 1, ?, ?, ?, ?)""",
        (f"rev_{uuid.uuid4().hex[:12]}", proposal_id, digest, draft_json, actor, created.isoformat()),
    )
    _store_status(connection, proposal_id)
    return proposal_id


def _store_status(connection: sqlite3.Connection, proposal_id: str) -> None:
    view = evaluate(connection, load_row(connection, proposal_id))
    if view.status not in TERMINAL:
        connection.execute("UPDATE intake_proposals SET status = ? WHERE proposal_id = ?", (view.status, proposal_id))


def load_row(connection: sqlite3.Connection, proposal_id: str, kinds: set[str] | None = None) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM intake_proposals WHERE shop_id = ? AND proposal_id = ?", (DEMO_SHOP_ID, proposal_id)
    ).fetchone()
    if row is None or (kinds and row["source_kind"] not in kinds):
        raise HTTPException(status_code=404, detail="Proposal not found in this demo shop.")
    return row


def _replay(connection: sqlite3.Connection, idempotency_key: str, check) -> ProposalView | None:
    row = connection.execute("SELECT * FROM intake_proposals WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
    if row is None:
        return None
    if not check(row):
        raise HTTPException(status_code=409, detail="Idempotency key was already used for a different proposal.")
    return evaluate(connection, row)


# --- Public operations ------------------------------------------------------

def create_invoice_proposal_from_image(image: bytes, declared_type: str | None, idempotency_key: str, supplier_id: str | None = None) -> ProposalView:
    if not (8 <= len(idempotency_key) <= 150):
        raise HTTPException(status_code=422, detail="idempotency_key must be 8-150 characters.")
    info = validate_invoice_image(image, declared_type)
    image_sha = hashlib.sha256(image).hexdigest()
    with connect() as connection:
        replay = _replay(connection, idempotency_key, lambda row: row["image_sha256"] == image_sha)
        if replay:
            return replay
        if supplier_id:
            supplier_view(connection, supplier_id)  # 404 if unknown
    provider = get_invoice_provider()
    try:
        raw = provider.extract(image, info.mime_type)
        draft, notes = draft_from_extraction(raw, supplier_id)
        extraction = ExtractionView(provider=raw.provider, model=raw.model, status="EXTRACTED", correlation_id=raw.correlation_id)
    except ProviderUnavailable:
        draft = DraftContent(supplier=DraftSupplier(supplier_id=supplier_id, verified=supplier_id is not None))
        notes = []
        extraction = ExtractionView(
            provider=getattr(provider, "name", "unknown"),
            status="PROVIDER_UNAVAILABLE",
            correlation_id=f"extract_{uuid.uuid4().hex[:12]}",
            message="Automatic reading is unavailable right now. Nothing was guessed; enter the bill lines manually using the revise endpoint.",
        )
    finally:
        del image  # bytes are never persisted; release our reference promptly
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        replay = _replay(connection, idempotency_key, lambda row: row["image_sha256"] == image_sha)
        if replay:
            return replay
        proposal_id = insert_proposal(
            connection, source_kind="invoice_image", draft=draft, extraction=extraction,
            idempotency_key=idempotency_key, image_sha256=image_sha, actor="extraction", parse_notes=notes,
        )
        return evaluate(connection, load_row(connection, proposal_id))


def create_manual_invoice_proposal(request: ManualInvoiceCreate) -> ProposalView:
    draft = draft_from_edits(request.supplier, request.invoice, request.lines)
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        replay = _replay(
            connection, request.idempotency_key,
            lambda row: row["source_kind"] == "manual_invoice" and _same_edits(connection, row, draft),
        )
        if replay:
            return replay
        proposal_id = insert_proposal(
            connection, source_kind="manual_invoice", draft=draft,
            extraction=ExtractionView(provider="manual", status="NOT_REQUESTED"),
            idempotency_key=request.idempotency_key, actor="merchant",
        )
        return evaluate(connection, load_row(connection, proposal_id))


def _same_edits(connection: sqlite3.Connection, row: sqlite3.Row, draft: DraftContent) -> bool:
    revision = connection.execute(
        "SELECT draft_json FROM intake_proposal_revisions WHERE proposal_id = ? AND version = 1", (row["proposal_id"],)
    ).fetchone()
    stored = DraftContent.model_validate_json(revision["draft_json"])

    def strip(content: DraftContent) -> list[dict]:
        return [{k: v for k, v in line.model_dump().items() if k != "line_id"} for line in content.lines]

    return stored.supplier == draft.supplier and stored.invoice == draft.invoice and strip(stored) == strip(draft)


def get_proposal(proposal_id: str, kinds: set[str] | None = None) -> ProposalView:
    with connect() as connection:
        return evaluate(connection, load_row(connection, proposal_id, kinds))


def list_proposals(kinds: set[str], status: str | None = None, limit: int = 50) -> list[ProposalView]:
    with connect() as connection:
        placeholders = ",".join("?" for _ in kinds)
        rows = connection.execute(
            f"""SELECT * FROM intake_proposals WHERE shop_id = ? AND source_kind IN ({placeholders})
                ORDER BY created_at DESC LIMIT ?""",
            (DEMO_SHOP_ID, *sorted(kinds), min(max(limit, 1), 100)),
        ).fetchall()
        views = [evaluate(connection, row) for row in rows]
    return [view for view in views if status is None or view.status == status]


def revise_proposal(proposal_id: str, request: ProposalRevise, kinds: set[str]) -> ProposalView:
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = load_row(connection, proposal_id, kinds)
        _require_open(connection, row)
        if row["version"] != request.expected_version:
            raise HTTPException(status_code=409, detail={"code": "STALE_PROPOSAL", "current_version": row["version"]})
        previous = DraftContent.model_validate_json(row["draft_json"])
        draft = draft_from_edits(request.supplier, request.invoice, request.lines, previous)
        digest = content_hash(draft)
        version = row["version"] + 1
        stamp = now_utc().isoformat()
        connection.execute(
            "UPDATE intake_proposals SET version = ?, content_hash = ?, draft_json = ?, updated_at = ? WHERE proposal_id = ?",
            (version, digest, draft.model_dump_json(), stamp, proposal_id),
        )
        connection.execute(
            """INSERT INTO intake_proposal_revisions (revision_id, proposal_id, version, content_hash, draft_json, actor, created_at)
               VALUES (?, ?, ?, ?, ?, 'merchant', ?)""",
            (f"rev_{uuid.uuid4().hex[:12]}", proposal_id, version, digest, draft.model_dump_json(), stamp),
        )
        _store_status(connection, proposal_id)
        return evaluate(connection, load_row(connection, proposal_id))


def reject_proposal(proposal_id: str, request: ProposalReject, kinds: set[str]) -> ProposalView:
    if not request.confirmed:
        raise HTTPException(status_code=409, detail="Merchant confirmation is required to reject a proposal.")
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = load_row(connection, proposal_id, kinds)
        if row["status"] == "REJECTED":
            return evaluate(connection, row)
        _require_open(connection, row)
        if row["version"] != request.expected_version:
            raise HTTPException(status_code=409, detail={"code": "STALE_PROPOSAL", "current_version": row["version"]})
        connection.execute(
            "UPDATE intake_proposals SET status = 'REJECTED', updated_at = ? WHERE proposal_id = ?",
            (now_utc().isoformat(), proposal_id),
        )
        return evaluate(connection, load_row(connection, proposal_id))


def _require_open(connection: sqlite3.Connection, row: sqlite3.Row) -> None:
    if row["status"] in TERMINAL:
        raise HTTPException(status_code=409, detail={"code": f"PROPOSAL_{row['status']}", "receipt_id": row["posted_receipt_id"]})
    if datetime.fromisoformat(row["expires_at"]) <= now_utc():
        connection.execute("UPDATE intake_proposals SET status = 'EXPIRED' WHERE proposal_id = ?", (row["proposal_id"],))
        connection.commit()
        raise HTTPException(status_code=409, detail={"code": "PROPOSAL_EXPIRED"})


# --- Validation -------------------------------------------------------------

def _product(connection: sqlite3.Connection, product_id: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT product_id, name, unit FROM products WHERE shop_id = ? AND product_id = ?", (DEMO_SHOP_ID, product_id)
    ).fetchone()


def _product_view(connection: sqlite3.Connection, product_id: str) -> ProductView:
    product = _product(connection, product_id)
    aliases = [row["alias"] for row in connection.execute(
        "SELECT alias FROM product_aliases WHERE shop_id = ? AND product_id = ? ORDER BY alias", (DEMO_SHOP_ID, product_id)
    )]
    return ProductView(product_id=product["product_id"], name=product["name"], aliases=aliases, unit=product["unit"])


def _exact_products(connection: sqlite3.Connection, text: str) -> list[str]:
    return [row["product_id"] for row in connection.execute(
        """SELECT DISTINCT p.product_id FROM products p
           JOIN product_aliases a ON a.shop_id = p.shop_id AND a.product_id = p.product_id
           WHERE p.shop_id = ? AND a.alias_normalized = ? ORDER BY p.name""",
        (DEMO_SHOP_ID, normalize_alias(text)),
    )]


def _suggested_products(connection: sqlite3.Connection, text: str) -> list[str]:
    """Whole-word containment suggestions. Shown as candidates only; never auto-selected."""
    words = f" {normalize_alias(text)} "
    found = []
    for row in connection.execute(
        "SELECT DISTINCT product_id, alias_normalized FROM product_aliases WHERE shop_id = ?", (DEMO_SHOP_ID,)
    ):
        alias = row["alias_normalized"]
        if len(alias) >= 3 and (f" {alias} " in words or f" {words.strip()} " in f" {alias} ") and row["product_id"] not in found:
            found.append(row["product_id"])
    return found[:5]


def stored_conversion(connection: sqlite3.Connection, product_id: str, unit: str) -> int | None:
    row = connection.execute(
        """SELECT base_units_per_unit FROM product_unit_conversions
           WHERE shop_id = ? AND product_id = ? AND unit = ? ORDER BY created_at DESC, conversion_id DESC LIMIT 1""",
        (DEMO_SHOP_ID, product_id, unit),
    ).fetchone()
    return int(row[0]) if row else None


def _unit_options(connection: sqlite3.Connection, product: sqlite3.Row | None) -> list[str]:
    if product is None:
        return []
    others = [row["unit"] for row in connection.execute(
        "SELECT DISTINCT unit FROM product_unit_conversions WHERE shop_id = ? AND product_id = ? ORDER BY unit",
        (DEMO_SHOP_ID, product["product_id"]),
    )]
    return list(dict.fromkeys([product["unit"], *others]))


def _evaluate_line(connection: sqlite3.Connection, line: DraftLine, source_kind: str, threshold: float, tolerance: int) -> LineView:
    issues: list[Issue] = []

    def issue(code: str, severity: str, message: str, field: str | None = None) -> None:
        issues.append(Issue(code=code, severity=severity, message=message, line_id=line.line_id, field=field))

    for note in line.parse_notes:
        issue("EXTRACTION_NOTE", "warning", note)

    product = None
    candidates: list[str] = []
    if line.product_id:
        product = _product(connection, line.product_id)
        match_status = "SELECTED" if product else "NOT_FOUND"
        if product is None:
            issue("PRODUCT_INVALID", "blocking", "Selected product does not exist in this shop.", "product_id")
    elif line.product_name_text:
        exact = _exact_products(connection, line.product_name_text)
        if len(exact) == 1:
            product = _product(connection, exact[0])
            match_status = "MATCHED"
        elif len(exact) > 1:
            candidates = exact
            match_status = "NEEDS_SELECTION"
            issue("PRODUCT_AMBIGUOUS", "blocking", f"'{line.product_name_text}' matches more than one product; choose one.", "product_id")
        else:
            candidates = _suggested_products(connection, line.product_name_text)
            match_status = "NEEDS_SELECTION" if candidates else "NOT_FOUND"
            hint = "choose a suggested product, " if candidates else ""
            issue("PRODUCT_UNRESOLVED", "blocking", f"No exact product for '{line.product_name_text}'; {hint}select or create one.", "product_id")
    else:
        match_status = "NOT_PROVIDED"
        issue("PRODUCT_MISSING", "blocking", "Line has no product name; enter or select a product.", "product_id")

    if line.quantity is None:
        issue("QUANTITY_MISSING", "blocking", "Quantity is missing.", "quantity")
    elif line.quantity <= 0:
        issue("QUANTITY_INVALID", "blocking", "Quantity must be a positive whole number.", "quantity")

    unit = canonical_unit(line.unit_text)
    base_unit = product["unit"] if product else None
    options = _unit_options(connection, product)
    factor = None
    if unit is None:
        name = line.product_name_text or (product["name"] if product else "this item")
        quantity_text = f"{line.quantity} " if line.quantity else ""
        choices = f" Options: {', '.join(options)}." if options else ""
        issue("UNIT_MISSING", "blocking", f"Which unit is '{quantity_text}{name}' (cup, packet, or another unit)?{choices}", "unit_text")
    elif product is not None:
        if unit == canonical_unit(base_unit):
            factor = 1
        elif line.conversion_factor:
            factor = line.conversion_factor
            issue("CONVERSION_ENTERED", "info", f"Using merchant-entered 1 {unit} = {factor} {base_unit}.", "conversion_factor")
        else:
            factor = stored_conversion(connection, product["product_id"], unit)
            if factor is None:
                issue("UNIT_CONVERSION_UNKNOWN", "blocking",
                      f"How many {base_unit} are in 1 {unit}? Enter conversion_factor or save a unit conversion; it is not assumed.",
                      "conversion_factor")
    base_quantity = line.quantity * factor if factor and line.quantity and line.quantity > 0 else None

    if line.quantity and line.unit_cost_paise is not None and line.line_total_paise is not None:
        expected = line.quantity * line.unit_cost_paise
        if abs(expected - line.line_total_paise) > tolerance:
            issue("LINE_TOTAL_MISMATCH", "warning",
                  f"Quantity × unit cost is {expected} paise but the line total says {line.line_total_paise} paise. Both values were kept; correct one or acknowledge.",
                  "line_total_paise")

    if line.confidence is not None and line.confidence < threshold and not line.merchant_verified:
        issue("LOW_CONFIDENCE", "blocking", f"This line was read with low confidence ({line.confidence:.2f}); review and mark it verified.")

    return LineView(
        line_id=line.line_id,
        source_text=line.source_text,
        product_name_text=line.product_name_text,
        matched_product_id=product["product_id"] if product else None,
        match_status=match_status,
        candidates=[_product_view(connection, pid) for pid in candidates],
        quantity=line.quantity,
        unit_text=line.unit_text,
        unit=unit,
        unit_options=options,
        conversion_factor=factor,
        base_quantity=base_quantity,
        base_unit=base_unit,
        unit_cost_paise=line.unit_cost_paise,
        line_total_paise=line.line_total_paise,
        confidence=line.confidence,
        merchant_verified=line.merchant_verified,
        accepted=line.accepted,
        issues=issues if line.accepted else [],
    )


def evaluate(connection: sqlite3.Connection, row: sqlite3.Row) -> ProposalView:
    draft = DraftContent.model_validate_json(row["draft_json"])
    extraction_data = json.loads(row["extraction_json"])
    notes = extraction_data.pop("notes", [])
    extraction = ExtractionView.model_validate(extraction_data)
    source_kind = row["source_kind"]
    threshold = min_confidence()
    tolerance = rounding_tolerance()
    issues: list[Issue] = [Issue(code="EXTRACTION_NOTE", severity="warning", message=note) for note in notes]
    invoice = draft.invoice
    has_total = invoice.total_paise is not None

    # Supplier
    supplier_candidates = []
    supplier_id = None
    if draft.supplier.supplier_id:
        exists = connection.execute(
            "SELECT 1 FROM suppliers WHERE shop_id = ? AND supplier_id = ?", (DEMO_SHOP_ID, draft.supplier.supplier_id)
        ).fetchone()
        supplier_status = "SELECTED" if exists else "NOT_FOUND"
        supplier_id = draft.supplier.supplier_id if exists else None
        if not exists:
            issues.append(Issue(code="SUPPLIER_INVALID", severity="blocking", message="Selected supplier does not exist.", field="supplier_id"))
    elif draft.supplier.label:
        resolution = resolve_supplier_in(connection, draft.supplier.label)
        supplier_status = resolution.status
        if resolution.status == "RESOLVED":
            supplier_id = resolution.matches[0].supplier_id
        else:
            supplier_candidates = resolution.matches
            severity = "blocking" if has_total and resolution.status == "AMBIGUOUS" else "info"
            issues.append(Issue(
                code=f"SUPPLIER_{resolution.status}", severity=severity, field="supplier_id",
                message=(f"'{draft.supplier.label}' matches several suppliers; select one." if resolution.status == "AMBIGUOUS"
                         else f"No supplier record for '{draft.supplier.label}'; select or create one to track what is owed."),
            ))
    else:
        supplier_status = "NOT_PROVIDED"

    if source_kind == "invoice_image":
        if draft.supplier.confidence is not None and draft.supplier.confidence < threshold and not draft.supplier.verified:
            issues.append(Issue(code="LOW_CONFIDENCE_SUPPLIER", severity="blocking", field="supplier_id",
                                message="Supplier name was read with low confidence; confirm or select the supplier."))
        if not invoice.verified:
            for name in HEADER_FIELDS:
                value = invoice.field_confidence.get(name)
                if value is not None and value < threshold:
                    issues.append(Issue(code="LOW_CONFIDENCE_HEADER", severity="blocking", field=name,
                                        message=f"{name} was read with low confidence ({value:.2f}); review the invoice header."))

    # Lines
    line_views = [_evaluate_line(connection, line, source_kind, threshold, tolerance) for line in draft.lines]
    accepted = [line for line in line_views if line.accepted]
    if not accepted:
        issues.append(Issue(code="NO_ACCEPTED_LINES", severity="blocking", message="Add or accept at least one received line."))

    # Arithmetic (never fills in unknown components)
    line_totals = [line.line_total_paise for line in accepted]
    lines_total = sum(line_totals) if accepted and all(value is not None for value in line_totals) else None
    components = [invoice.subtotal_paise, invoice.tax_paise, invoice.freight_paise, invoice.other_charges_paise,
                  invoice.discount_paise, invoice.rounding_paise]
    computed_total = None
    if all(value is not None for value in components):
        computed_total = (invoice.subtotal_paise + invoice.tax_paise + invoice.freight_paise + invoice.other_charges_paise
                          - invoice.discount_paise + invoice.rounding_paise)
        if has_total and abs(computed_total - invoice.total_paise) > tolerance:
            issues.append(Issue(code="INVOICE_TOTAL_MISMATCH", severity="warning", field="total_paise",
                                message=f"Subtotal + tax + charges − discount + rounding = {computed_total} paise, but the invoice total says {invoice.total_paise} paise."))
    elif has_total and source_kind in INVOICE_KINDS:
        unknown = [name for name, value in zip(("subtotal", "tax", "freight", "other_charges", "discount", "rounding"), components) if value is None]
        issues.append(Issue(code="COMPONENTS_UNKNOWN", severity="info",
                            message=f"Not shown or not read: {', '.join(unknown)}. Total arithmetic was not checked for those; nothing was assumed."))
    if lines_total is not None and invoice.subtotal_paise is not None and abs(lines_total - invoice.subtotal_paise) > tolerance:
        issues.append(Issue(code="LINES_SUBTOTAL_MISMATCH", severity="warning", field="subtotal_paise",
                            message=f"Accepted line totals add up to {lines_total} paise but the subtotal says {invoice.subtotal_paise} paise."))

    # Payable
    if has_total:
        payable_note = "On confirm, supplier payable = total − amount paid now (enter paid_now_paise, 0 if unpaid)."
        if supplier_id is None:
            issues.append(Issue(code="SUPPLIER_REQUIRED_FOR_PAYABLE", severity="info", field="supplier_id",
                                message="Select a supplier to record what is owed. Without one, confirm only with paid_now equal to the total."))
    else:
        payable_note = "No verified total supplied: confirming records stock only; no supplier payable is created."
        if source_kind in INVOICE_KINDS:
            issues.append(Issue(code="TOTAL_UNKNOWN", severity="info", field="total_paise", message=payable_note))

    # Duplicates
    number = normalize_invoice_number(invoice.invoice_number)
    if number:
        if supplier_id:
            posted = connection.execute(
                """SELECT receipt_id, total_paise, proposal_id FROM stock_receipts
                   WHERE shop_id = ? AND supplier_id = ? AND invoice_number_normalized = ?""",
                (DEMO_SHOP_ID, supplier_id, number),
            ).fetchone()
            if posted and posted["proposal_id"] != row["proposal_id"]:
                conflicting = posted["total_paise"] != invoice.total_paise
                issues.append(Issue(
                    code="DUPLICATE_INVOICE_CONFLICT" if conflicting else "DUPLICATE_INVOICE_ALREADY_POSTED",
                    severity="blocking", field="invoice_number",
                    message=(f"Invoice {invoice.invoice_number} from this supplier was already posted as {posted['receipt_id']}"
                             + (" with different details." if conflicting else ".")),
                ))
        else:
            posted_any = connection.execute(
                "SELECT receipt_id FROM stock_receipts WHERE shop_id = ? AND invoice_number_normalized = ? AND proposal_id != ? LIMIT 1",
                (DEMO_SHOP_ID, number, row["proposal_id"]),
            ).fetchone()
            if posted_any:
                issues.append(Issue(code="POSSIBLE_DUPLICATE_INVOICE", severity="warning", field="invoice_number",
                                    message=f"An invoice numbered {invoice.invoice_number} was already posted ({posted_any['receipt_id']})."))
        open_drafts = connection.execute(
            """SELECT proposal_id, draft_json FROM intake_proposals WHERE shop_id = ? AND proposal_id != ?
               AND status IN ('NEEDS_REVIEW', 'READY')""",
            (DEMO_SHOP_ID, row["proposal_id"]),
        ).fetchall()
        for other in open_drafts:
            other_number = normalize_invoice_number(json.loads(other["draft_json"])["invoice"].get("invoice_number"))
            if other_number == number:
                issues.append(Issue(code="POSSIBLE_DUPLICATE_DRAFT", severity="info", field="invoice_number",
                                    message=f"Another open draft ({other['proposal_id']}) has the same invoice number."))
                break
    if row["image_sha256"]:
        same_image = connection.execute(
            "SELECT proposal_id FROM intake_proposals WHERE shop_id = ? AND image_sha256 = ? AND proposal_id != ? LIMIT 1",
            (DEMO_SHOP_ID, row["image_sha256"], row["proposal_id"]),
        ).fetchone()
        if same_image:
            issues.append(Issue(code="POSSIBLE_DUPLICATE_IMAGE", severity="warning",
                                message=f"The same photo was uploaded before ({same_image['proposal_id']})."))

    all_issues = issues + [issue for line in accepted for issue in line.issues]
    blocking = any(issue.severity == "blocking" for issue in all_issues)
    warnings = any(issue.severity == "warning" for issue in all_issues)
    expires_at = datetime.fromisoformat(row["expires_at"])
    status = row["status"]
    if status not in TERMINAL:
        status = "EXPIRED" if expires_at <= now_utc() else ("NEEDS_REVIEW" if blocking else "READY")

    return ProposalView(
        proposal_id=row["proposal_id"],
        source_kind=source_kind,
        status=status,
        version=row["version"],
        content_hash=row["content_hash"],
        supplier=SupplierMatchView(
            label=draft.supplier.label, supplier_id=supplier_id, match_status=supplier_status,
            candidates=supplier_candidates, confidence=draft.supplier.confidence, verified=draft.supplier.verified,
        ),
        invoice=InvoiceHeaderView(**invoice.model_dump(exclude={"field_confidence", "verified"}),
                                  field_confidence=invoice.field_confidence, verified=invoice.verified),
        lines=line_views,
        issues=issues,
        totals=ProposalTotals(
            accepted_line_count=len(accepted),
            computed_lines_total_paise=lines_total,
            computed_invoice_total_paise=computed_total,
            amount_due_if_unpaid_paise=invoice.total_paise,
            rounding_tolerance_paise=tolerance,
            payable_note=payable_note,
        ),
        requires_merchant_review=status not in TERMINAL,
        ready_to_confirm=status == "READY",
        warnings_require_acknowledgement=warnings,
        extraction=extraction,
        source_utterance=row["source_utterance"],
        posted_receipt_id=row["posted_receipt_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        expires_at=expires_at,
    )
