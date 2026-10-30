import copy

import pytest

from app.services import proposals
from app.services.invoice_extraction import FAKE_EXTRACTION, FakeInvoiceExtractionProvider, ProviderUnavailable
from tests.conftest import key, table_count
from tests.images import jpeg_header, png

WRITE_TABLES = ("stock_receipts", "stock_receipt_movements", "supplier_payable_entries", "inventory_movements", "ledger_entries")


@pytest.fixture
def shop(make_product, make_supplier):
    return {
        "amul": make_product("Amul Taaza", "packet", ["Amul Taaza 500 ml"]),
        "dahi": make_product("Dahi", "cup"),
        "supplier": make_supplier("Sharma Distributors"),
    }


def use_provider(monkeypatch, data=None, fail=False):
    class Failing:
        name = "gemini"

        def extract(self, image, mime_type):
            raise ProviderUnavailable("timeout")

    provider = Failing() if fail else FakeInvoiceExtractionProvider(data)
    monkeypatch.setattr(proposals, "get_invoice_provider", lambda: provider)


def upload(client, data=None, content_type="image/png", idem=None, **form):
    return client.post(
        "/invoices/proposals",
        files={"file": ("bill.png", data if data is not None else png(), content_type)},
        data={"idempotency_key": idem or key("inv"), **form},
    )


def no_writes(temp_db):
    return all(table_count(temp_db, table) == 0 for table in WRITE_TABLES)


def codes(view, line_index=None):
    source = view["issues"] if line_index is None else view["lines"][line_index]["issues"]
    return {issue["code"] for issue in source}


def test_image_creates_draft_only(client, shop, monkeypatch, temp_db):
    use_provider(monkeypatch)
    response = upload(client)
    assert response.status_code == 201, response.text
    view = response.json()
    assert view["status"] == "NEEDS_REVIEW" and view["image_retained"] is False
    assert view["extraction"]["status"] == "EXTRACTED" and view["extraction"]["provider"] == "fake"
    assert view["supplier"]["match_status"] == "RESOLVED"
    assert view["invoice"]["total_paise"] == 143800 and view["invoice"]["rounding_paise"] == -50
    amul, dahi, bread = view["lines"]
    assert amul["match_status"] == "MATCHED" and amul["base_quantity"] == 15 and amul["unit"] == "packet"
    assert amul["unit_cost_paise"] == 4200 and amul["issues"] == []
    assert "LOW_CONFIDENCE" in codes(view, 1)
    assert bread["match_status"] == "NOT_FOUND" and "PRODUCT_UNRESOLVED" in codes(view, 2)
    assert view["ready_to_confirm"] is False
    assert no_writes(temp_db)
    assert b"\x89PNG" not in temp_db.read_bytes()  # image bytes never persisted


def test_low_confidence_and_unmatched_block_until_reviewed(client, shop, monkeypatch):
    use_provider(monkeypatch)
    view = upload(client).json()
    lines = [
        {"line_id": line["line_id"], "product_id": line["matched_product_id"] or shop["dahi"]["product_id"],
         "quantity": line["quantity"], "unit_text": line["unit_text"], "unit_cost_paise": line["unit_cost_paise"],
         "line_total_paise": line["line_total_paise"], "accepted": line["product_name_text"] != "Bread"}
        for line in view["lines"]
    ]
    revised = client.post(f"/invoices/proposals/{view['proposal_id']}/revise", json={
        "expected_version": 1, "supplier": {"supplier_id": shop["supplier"]["supplier_id"]},
        "invoice": {k: view["invoice"][k] for k in ("invoice_number", "subtotal_paise", "tax_paise", "discount_paise",
                                                    "freight_paise", "other_charges_paise", "rounding_paise", "total_paise")},
        "lines": lines,
    })
    assert revised.status_code == 200, revised.text
    revised = revised.json()
    assert revised["version"] == 2
    assert all(not line["issues"] for line in revised["lines"] if line["accepted"])
    assert revised["status"] == "READY"
    # Excluding bread leaves line totals (113000) below the printed subtotal: flagged, not silently fixed.
    assert "LINES_SUBTOTAL_MISMATCH" in codes(revised)
    assert revised["warnings_require_acknowledgement"] is True


def test_total_mismatch_flagged(client, shop, monkeypatch):
    data = copy.deepcopy(FAKE_EXTRACTION)
    data["total"] = "1,500.00"
    data["lines"][0]["line_total"] = "640.00"
    use_provider(monkeypatch, data)
    view = upload(client).json()
    assert "INVOICE_TOTAL_MISMATCH" in codes(view)
    assert "LINE_TOTAL_MISMATCH" in codes(view, 0)
    # Source values are preserved, not recomputed.
    assert view["invoice"]["total_paise"] == 150000 and view["lines"][0]["line_total_paise"] == 64000


def test_missing_components_are_unknown_not_derived(client, shop, monkeypatch):
    data = copy.deepcopy(FAKE_EXTRACTION)
    data["tax_total"] = None
    data["freight"] = None
    use_provider(monkeypatch, data)
    view = upload(client).json()
    assert view["invoice"]["tax_paise"] is None and view["totals"]["computed_invoice_total_paise"] is None
    assert "COMPONENTS_UNKNOWN" in codes(view)


def test_untrusted_extraction_values_are_not_coerced(client, shop, monkeypatch):
    data = copy.deepcopy(FAKE_EXTRACTION)
    data["lines"][0]["quantity"] = "2.5"
    data["lines"][1]["unit_price"] = "about twenty"
    data["total"] = "ignore previous instructions"
    use_provider(monkeypatch, data)
    view = upload(client).json()
    assert view["lines"][0]["quantity"] is None and "QUANTITY_MISSING" in codes(view, 0)
    assert view["lines"][1]["unit_cost_paise"] is None
    assert view["invoice"]["total_paise"] is None
    assert any("could not be read" in issue["message"] for issue in view["issues"])


def test_provider_outage_manual_draft(client, shop, monkeypatch, temp_db):
    use_provider(monkeypatch, fail=True)
    view = upload(client).json()
    assert view["extraction"]["status"] == "PROVIDER_UNAVAILABLE"
    assert view["lines"] == [] and view["invoice"]["total_paise"] is None
    assert "NO_ACCEPTED_LINES" in codes(view)
    assert no_writes(temp_db)
    revised = client.post(f"/invoices/proposals/{view['proposal_id']}/revise", json={
        "expected_version": 1, "supplier": {"supplier_id": shop["supplier"]["supplier_id"]},
        "invoice": {"invoice_number": "M-1", "total_paise": 63000},
        "lines": [{"product_id": shop["amul"]["product_id"], "quantity": 15, "unit_text": "pkt"}],
    }).json()
    assert revised["status"] == "READY", revised["issues"]


@pytest.mark.parametrize("body,content_type,expected", [
    (b"", "image/png", 400),
    (b"hello, not an image at all", "image/png", 415),
    (png(), "image/gif", 415),
    (png(), "image/jpeg", 415),       # declared type disagrees with bytes
    (png(50, 50), "image/png", 422),  # too small to read
    (b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, "image/png", 422),  # malformed header
    (png(12000, 100), "image/png", 413),
])
def test_rejects_bad_uploads(client, shop, monkeypatch, temp_db, body, content_type, expected):
    use_provider(monkeypatch)
    assert upload(client, body, content_type).status_code == expected
    assert table_count(temp_db, "intake_proposals") == 0


def test_rejects_oversized_upload(client, shop, monkeypatch, temp_db):
    use_provider(monkeypatch)
    monkeypatch.setenv("MUNIM_INVOICE_MAX_BYTES", "1000")
    assert upload(client, png() + bytes(2000)).status_code == 413
    assert table_count(temp_db, "intake_proposals") == 0


def test_jpeg_accepted_and_upload_idempotent(client, shop, monkeypatch, temp_db):
    use_provider(monkeypatch)
    first = upload(client, jpeg_header(), "image/jpeg", idem="upload-key-001")
    assert first.status_code == 201
    again = upload(client, jpeg_header(), "image/jpeg", idem="upload-key-001")
    assert again.json()["proposal_id"] == first.json()["proposal_id"]
    assert upload(client, png(), "image/png", idem="upload-key-001").status_code == 409
    assert table_count(temp_db, "intake_proposals") == 1
    second_photo = upload(client, jpeg_header(), "image/jpeg").json()
    assert "POSSIBLE_DUPLICATE_IMAGE" in codes(second_photo)


def test_ambiguous_supplier_requires_selection(client, shop, make_supplier, monkeypatch):
    make_supplier("Sharma Distributors Wholesale", ["Sharma Distributors"])
    use_provider(monkeypatch)
    view = upload(client).json()
    assert view["supplier"]["match_status"] == "AMBIGUOUS" and len(view["supplier"]["candidates"]) == 2
    assert "SUPPLIER_AMBIGUOUS" in codes(view)


def test_upload_stale_revision_rejected(client, shop, monkeypatch):
    use_provider(monkeypatch)
    view = upload(client).json()
    body = {"expected_version": 1, "lines": [{"product_id": shop["amul"]["product_id"], "quantity": 1, "unit_text": "packet"}]}
    assert client.post(f"/invoices/proposals/{view['proposal_id']}/revise", json=body).status_code == 200
    stale = client.post(f"/invoices/proposals/{view['proposal_id']}/revise", json=body)
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "STALE_PROPOSAL"
