# Backend-First Phases — Operator Runbook

How to run and verify the supplier khata, invoice scanner, quick voice inward, and 15-day reminder APIs. Backend only; the mobile UI is unchanged. All data is synthetic. There is no live Paytm integration, and no real customer messaging.

## 1. Setup (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Keys live only in the ignored root `.env` (template: `.env.example`). `GEMINI_API_KEY` is optional (invoice vision, inward/command assist). `SARVAM_API_KEY` is only needed for live speech. `MONGODB_URI` is unused.

| Variable | Default | Purpose |
|---|---|---|
| `MUNIM_DB_PATH` | `backend/data/munim.sqlite3` | Use a separate file for experiments. |
| `MUNIM_INVOICE_PROVIDER` | `gemini` | `fake` = deterministic synthetic bill (no key needed); `none` = manual drafts only. |
| `GEMINI_VISION_MODEL` / `MUNIM_VISION_TIMEOUT_SECONDS` | `GEMINI_MODEL` / `20` | Vision model and timeout. |
| `MUNIM_INVOICE_MAX_BYTES` | 8 MB | Upload limit. |
| `MUNIM_INTAKE_MIN_CONFIDENCE` | `0.80` | Below this, lines/fields need merchant verification. |
| `MUNIM_INVOICE_ROUNDING_TOLERANCE_PAISE` | `100` | Arithmetic tolerance. |
| `MUNIM_PROPOSAL_EXPIRY_DAYS` | `7` | Draft expiry. |
| `MUNIM_INWARD_LLM` | `1` | `0` disables the Gemini fallback for inward parsing. |
| `MUNIM_ADMIN_TOKEN` | unset | When set, reminder run/mock-send/receipt need header `X-Munim-Admin-Token`. |
| `MUNIM_REMINDER_SCHEDULER_MINUTES` | `0` (off) | Optional periodic eligibility run (idempotent). |
| `MUNIM_NOTIFICATION_PROVIDER` | `mock` | Only `mock` exists; anything else returns 503. |

## 2. Automated checks

```powershell
cd backend
python -m pytest -q tests
```

Each test uses its own temporary SQLite file. Outbound network calls are blocked, so no test can reach Gemini, Sarvam, SMS, or WhatsApp.

## 3. End-to-end rehearsal on a copy

```powershell
cd backend
# Clean database:
python scripts/rehearse_next_phases.py "$env:TEMP\munim-clean-$(Get-Date -Format yyyyMMddHHmmss).sqlite3"
# Existing database: copy first, then rehearse on the copy.
Copy-Item data\munim.sqlite3 "$env:TEMP\munim-copy.sqlite3"
python scripts/rehearse_next_phases.py "$env:TEMP\munim-copy.sqlite3"
```

Verified on 2026-10-30 against a clean DB and against an upgraded copy of a database built by the pre-change commit `5bec501`. The legacy balances, stock, and 9,611 synthetic transactions were preserved. The script refuses to run against `backend/data/munim.sqlite3`. It uses the fake invoice provider and the mock notifier. It prints stock, supplier dues, receipts, inward questions, and reminder outcomes as JSON. Between 21:00 and 09:00 IST, mock-send correctly reports `QUIET_HOURS`.

**Migrations / rollback:** on startup, `initialize_database()` applies migrations 1–4 and records them in `schema_migrations`. The migrations are additive, and a failed migration rolls back entirely. To roll back an upgraded database, stop the API and restore the copy you took before upgrading.

## 4. Manual API walk-through

Start the API with the fake provider and a demo DB:

```powershell
cd backend
$env:MUNIM_DB_PATH = "$env:TEMP\munim-demo.sqlite3"
$env:MUNIM_INVOICE_PROVIDER = "fake"
python seed_demo.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

These commands were executed against a live server on 2026-10-30, with results matching section 3. In a second PowerShell window (`$api = "http://127.0.0.1:8000"`; Swagger UI at `$api/docs`):

```powershell
$api = "http://127.0.0.1:8000"
function Post($path, $body) { Invoke-RestMethod -Method Post -Uri "$api$path" -ContentType "application/json" -Body ($body | ConvertTo-Json -Depth 10) }

# Suppliers
$sharma = (Invoke-RestMethod "$api/suppliers/resolve?query=Sharma%20Distributors").matches[0]
Invoke-RestMethod "$api/suppliers/$($sharma.supplier_id)/balance"

# Invoice photo -> draft (any JPEG/PNG/WebP photo; the fake provider returns a synthetic bill)
$draft = curl.exe -s -F "file=@C:\path\to\bill.jpg;type=image/jpeg" -F "idempotency_key=demo-invoice-001" "$api/invoices/proposals" | ConvertFrom-Json
$draft.lines | Select-Object product_name_text, match_status, quantity, unit, @{n='issues';e={$_.issues.code -join ','}}

# Review: keep matched lines, mark Dahi verified, exclude unmatched Bread, select supplier
$lines = $draft.lines | ForEach-Object { @{ line_id=$_.line_id; product_id=$_.matched_product_id; quantity=$_.quantity;
    unit_text=$_.unit_text; unit_cost_paise=$_.unit_cost_paise; line_total_paise=$_.line_total_paise;
    accepted=($null -ne $_.matched_product_id) } }
$rev = Post "/invoices/proposals/$($draft.proposal_id)/revise" @{ expected_version=$draft.version;
    supplier=@{ supplier_id=$sharma.supplier_id }; invoice=@{ invoice_number="INV-204"; total_paise=113000 }; lines=@($lines) }
$rev.status; $rev.issues.code

# Confirm atomically (paid nothing now -> full payable)
Post "/invoices/proposals/$($draft.proposal_id)/confirm" @{ expected_version=$rev.version; content_hash=$rev.content_hash;
    paid_now_paise=0; acknowledge_warnings=$true; confirmed=$true; idempotency_key="demo-invoice-confirm-001" }

# Quick voice inward (transcript reviewed first)
$in = Post "/inventory/inward/proposals" @{ utterance="Doodh wale se 15 packet Amul Taaza aur 10 dahi liye."; source_channel="voice"; idempotency_key="demo-inward-001" }
$in.proposal.lines | Select-Object product_name_text, quantity, unit, @{n='q';e={$_.issues.message}}

# Reminders (Raju's seeded credit is new, so preview 16 days ahead)
$raju = (Invoke-RestMethod "$api/customers/resolve?query=Raju%20bhai").matches[0]
Post "/customers/$($raju.customer_id)/reminder-consent" @{ channel="whatsapp"; consent_status="OPTED_IN"; contact_value="+91 90000 00001";
    contact_verified=$true; verification_method="Synthetic demo number"; evidence_note="Synthetic consent for demo"; confirmed=$true; idempotency_key="demo-consent-001" }
$asOf = [Uri]::EscapeDataString((Get-Date).ToUniversalTime().AddDays(16).ToString("o"))
Invoke-RestMethod "$api/reminders/eligibility/preview?as_of=$asOf"
$run = Invoke-RestMethod -Method Post "$api/reminders/eligibility/run?as_of=$asOf"
$rid = $run.created[0].reminder_id
Post "/reminders/$rid/approve" @{ confirmed=$true; include_amount=$false; idempotency_key="demo-approve-001" }
Post "/reminders/$rid/mock-send" @{ confirmed=$true; idempotency_key="demo-send-001" }   # QUIET_HOURS 21:00-09:00 IST
Invoke-RestMethod "$api/events?limit=20" | Select-Object event_type, summary
```

## 5. Truthful limitations

- Live Gemini vision is wired but was not verified in this run. Recent Gemini calls returned 503/timeouts, and the deterministic/manual paths are the reliable ones.
- There is no authentication, only the optional admin token on reminder run/send. It is a single demo shop.
- Reminders never reach a phone. `SENT_MOCK`/`DELIVERED_MOCK` are simulated states.
- No visit tracking. Eligibility is overdue-credit age only.
- Quantities are whole numbers in each product's base unit. Pack sizes need a merchant-confirmed conversion.
- No GST or tax compliance claims; printed values are only checked for arithmetic consistency.
