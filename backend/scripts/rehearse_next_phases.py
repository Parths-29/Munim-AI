"""End-to-end rehearsal of the backend-first phases against an explicit SQLite copy.

Usage (PowerShell, from backend/):
    python scripts/rehearse_next_phases.py C:\\temp\\munim-rehearsal.sqlite3

Uses the fake invoice provider and the mock notification provider only. It
refuses to run against the default demo database path.
"""

import json
import os
import struct
import sys
import uuid
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path


def tiny_png() -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\xff" * 400 for _ in range(300))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 400, 300, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    target = Path(sys.argv[1]).resolve()
    backend = Path(__file__).resolve().parents[1]
    if target == (backend / "data" / "munim.sqlite3").resolve():
        print("Refusing to rehearse against the default demo database. Copy it first.")
        return 2
    os.environ["MUNIM_DB_PATH"] = str(target)
    os.environ["MUNIM_INVOICE_PROVIDER"] = "fake"
    os.environ["MUNIM_INWARD_LLM"] = "0"
    os.environ["MUNIM_NOTIFICATION_PROVIDER"] = "mock"
    sys.path.insert(0, str(backend))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    from fastapi.testclient import TestClient

    import seed_demo
    from app.main import app

    results = {}
    run = uuid.uuid4().hex[:8]

    def k(name):
        return f"rehearsal-{run}-{name}"

    def ok(response, *codes):
        if response.status_code not in (codes or (200, 201)):
            raise SystemExit(f"FAILED {response.request.method} {response.request.url.path}: {response.status_code} {response.text[:300]}")
        return response.json()

    with TestClient(app) as client:  # runs migrations + synthetic payment fixture
        seed_demo.main()
        product = {name: ok(client.get("/products/resolve", params={"query": name}))["matches"][0] for name in ("Amul Taaza", "Dahi", "Maggi")}
        raju = ok(client.get("/customers/resolve", params={"query": "Raju bhai"}))["matches"][0]
        sharma = ok(client.get("/suppliers/resolve", params={"query": "Sharma Distributors"}))["matches"][0]
        before = {name: ok(client.get(f"/inventory/products/{p['product_id']}/stock"))["on_hand_quantity"] for name, p in product.items()}
        raju_before = ok(client.get(f"/ledger/customers/{raju['customer_id']}/balance"))["balance_due_paise"]
        results["existing_before"] = {"stock": before, "raju_due_paise": raju_before}

        # Invoice photo -> draft -> merchant review -> atomic confirm
        draft = ok(client.post("/invoices/proposals", files={"file": ("bill.png", tiny_png(), "image/png")},
                               data={"idempotency_key": k("invoice")}))
        results["invoice_draft"] = {"status": draft["status"], "issues": sorted({i["code"] for i in draft["issues"]}),
                                    "line_status": [l["match_status"] for l in draft["lines"]]}
        lines = []
        for line in draft["lines"]:
            accepted = line["product_name_text"] != "Bread"
            lines.append({"line_id": line["line_id"], "product_id": line["matched_product_id"] or product["Dahi"]["product_id"],
                          "quantity": line["quantity"], "unit_text": line["unit_text"], "unit_cost_paise": line["unit_cost_paise"],
                          "line_total_paise": line["line_total_paise"], "accepted": accepted})
        inv = draft["invoice"]
        revised = ok(client.post(f"/invoices/proposals/{draft['proposal_id']}/revise", json={
            "expected_version": draft["version"], "supplier": {"supplier_id": sharma["supplier_id"]},
            "invoice": {"invoice_number": f"{inv['invoice_number']}-{run}", "subtotal_paise": 113000, "tax_paise": 0,
                        "discount_paise": 0, "freight_paise": 0, "other_charges_paise": 0, "rounding_paise": 0, "total_paise": 113000},
            "lines": lines,
        }))
        receipt = ok(client.post(f"/invoices/proposals/{draft['proposal_id']}/confirm", json={
            "expected_version": revised["version"], "content_hash": revised["content_hash"], "paid_now_paise": 30000,
            "acknowledge_warnings": True, "confirmed": True, "idempotency_key": k("invoice-confirm")}), 201)
        replay = ok(client.post(f"/invoices/proposals/{draft['proposal_id']}/confirm", json={
            "expected_version": revised["version"], "content_hash": revised["content_hash"], "paid_now_paise": 30000,
            "acknowledge_warnings": True, "confirmed": True, "idempotency_key": k("invoice-confirm")}), 201)
        results["invoice_receipt"] = {"payable_status": receipt["payable_status"], "due_before": receipt["supplier_due_before_paise"],
                                      "due_after": receipt["supplier_due_after_paise"], "replay_same": replay["receipt_id"] == receipt["receipt_id"],
                                      "lines": [(l["product_name"], l["on_hand_before"], l["on_hand_after"]) for l in receipt["lines"]]}

        # Voice inward example -> unit clarification -> stock only
        inward = ok(client.post("/inventory/inward/proposals", json={
            "utterance": "Doodh wale se 15 packet Amul Taaza aur 10 dahi liye.", "source_channel": "voice", "idempotency_key": k("inward")}))
        proposal = inward["proposal"]
        results["inward_draft"] = {"lines": [(l["product_name_text"], l["quantity"], l["unit"]) for l in proposal["lines"]],
                                   "questions": [i["message"] for l in proposal["lines"] for i in l["issues"] if i["code"] == "UNIT_MISSING"]}
        amul, dahi = proposal["lines"]
        fixed = ok(client.post(f"/inventory/inward/proposals/{proposal['proposal_id']}/revise", json={
            "expected_version": proposal["version"], "supplier": {"label": "Doodh wale"},
            "lines": [{"line_id": amul["line_id"], "product_name_text": "Amul Taaza", "quantity": 15, "unit_text": "packet"},
                      {"line_id": dahi["line_id"], "product_name_text": "dahi", "quantity": 10, "unit_text": "cup"}]}))
        inward_receipt = ok(client.post(f"/inventory/inward/proposals/{proposal['proposal_id']}/confirm", json={
            "expected_version": fixed["version"], "content_hash": fixed["content_hash"], "confirmed": True,
            "idempotency_key": k("inward-confirm"), "source_channel": "voice"}), 201)
        results["inward_receipt"] = {"payable_status": inward_receipt["payable_status"],
                                     "lines": [(l["product_name"], l["on_hand_before"], l["on_hand_after"]) for l in inward_receipt["lines"]]}

        # Reminders: consent, preview (now and +16 days), run, approve, mock send
        ok(client.post(f"/customers/{raju['customer_id']}/reminder-consent", json={
            "channel": "whatsapp", "consent_status": "OPTED_IN", "contact_value": "+91 90000 00001", "contact_verified": True,
            "verification_method": "Synthetic rehearsal number", "evidence_note": "Synthetic consent for rehearsal",
            "confirmed": True, "idempotency_key": k("consent")}), 201)
        now = datetime.now(timezone.utc)
        today = ok(client.get("/reminders/eligibility/preview", params={"as_of": now.isoformat()}))
        future = now + timedelta(days=16)
        later = ok(client.get("/reminders/eligibility/preview", params={"as_of": future.isoformat()}))
        run_result = ok(client.post("/reminders/eligibility/run", params={"as_of": future.isoformat()}))
        rerun = ok(client.post("/reminders/eligibility/run", params={"as_of": future.isoformat()}))
        results["reminders"] = {
            "today": [(r["display_name"], r["overdue_days"], r["reasons"]) for r in today["rows"]],
            "plus_16_days": [(r["display_name"], r["overdue_days"], r["eligible"]) for r in later["rows"]],
            "created": len(run_result["created"]), "rerun_created": len(rerun["created"]),
        }
        if run_result["created"]:
            rid = run_result["created"][0]["reminder_id"]
            approved = ok(client.post(f"/reminders/{rid}/approve", json={"confirmed": True, "idempotency_key": k("approve")}))
            send = client.post(f"/reminders/{rid}/mock-send", json={"confirmed": True, "idempotency_key": k("send")})
            results["reminders"]["approved_message"] = approved["message_preview"]
            results["reminders"]["mock_send"] = send.status_code if send.status_code != 200 else send.json()["status"]
            if send.status_code != 200:
                results["reminders"]["mock_send_detail"] = send.json()["detail"]

        after = {name: ok(client.get(f"/inventory/products/{p['product_id']}/stock"))["on_hand_quantity"] for name, p in product.items()}
        results["existing_after"] = {
            "stock": after,
            "raju_due_paise": ok(client.get(f"/ledger/customers/{raju['customer_id']}/balance"))["balance_due_paise"],
            "sharma_due_paise": ok(client.get(f"/suppliers/{sharma['supplier_id']}/balance"))["amount_due_paise"],
            "facts_count": len(ok(client.get("/insights/facts", params={"persona": "kirana"}))["facts"]),
            "event_summary_events": ok(client.get("/events/summary"))["recorded_event_count"],
        }
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
