# Browser Demo Walkthrough

This is the repeatable local walkthrough for the synthetic Munim-AI prototype. It keeps the active preview database untouched by creating a new SQLite file in the Windows temp folder. All amounts are synthetic; there is no live Paytm integration.

## Start a clean browser demo

In PowerShell terminal 1, from the repository root:

```powershell
cd backend
$demoDbPath = Join-Path $env:TEMP ("munim-browser-demo-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".sqlite3")
$env:MUNIM_DB_PATH = $demoDbPath
python seed_demo.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The seed command creates Raju bhai with ₹500 opening due and Maggi with 12 packs. The API startup adds the deterministic synthetic payment history used by the facts brief. Keep this terminal running.

In PowerShell terminal 2:

```powershell
cd mobile
$env:EXPO_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
npm run web
```

Open `http://localhost:8081/`. These commands use a fresh timestamped database; they do not delete or replace the current preview database.

## Walkthrough

1. **Check the opening balance.** On Home, enter `Raju bhai ka balance batao`. Expect ₹500 due. This is read-only.
2. **Record shop credit.** Enter `Raju bhai ka ₹50 udhaar likh do`. Review the exact customer and ₹50 preview, then confirm. Expect ₹550 due.
3. **Reconcile a mock payment.** Open Payment Review, enter ₹300 as the synthetic payment amount, add it, then manually allocate it to Raju bhai with the confirmation checked. Expect the review queue to clear and the derived due to become ₹250. The payment is labelled synthetic; it is not a real UPI event.
4. **Show inventory memory.** Open Inventory and look up Maggi. Record a stockout observation and verify on-hand stays at 12. Then enter a physical count of 10 and confirm; on-hand should become 10. These are separate events.
5. **Show the growth brief.** On Home, press `Aaj kaisa raha?`. The brief should show synthetic facts, evidence IDs, and caveats. Gemini may be unavailable; the deterministic summary is the expected fallback and is visibly labelled.
6. **Let the merchant approve a shop-side action.** Review or edit the counter notice. Example: `Ask us about this week's in-store offers. UPI accepted.` Click `Approve & Track for 7 Days (Mock)` only after reviewing it. Expect the exact saved text, `APPROVED_MOCK`, and a scheduled seven-day observation window. Nothing is published or sent.
7. **Check the timeline.** Confirm it contains the credit, payment allocation, physical count, and mock-action approval. Keep comparisons observational; do not claim the action caused sales changes.
8. **Try merchant commands on Home (typed or by transcript).** Examples: `Raju bhai ka balance batao`, `How many Maggi packs are left?`, `Summarize payments`, or `What happened in the shop today?`. Read-only results are labeled synthetic and stock is the latest recorded count, not a sensor reading.
9. **Preview safe voice writes.** Use `Add new customer Rajju Sharma` to preview the exact spelling, then confirm to create only the customer profile. Use `Set Maggi stock count to 10 packs` or `Maggi khatam ho gaya` to see the preview; count and stockout remain distinct actions. Review the transcript before Send and the exact preview before Confirm.

## Expected limitations to say aloud

- All customer, inventory, payment, and transaction data in this demo are synthetic.
- Gemini requests currently return 503 or time out in this environment; facts remain available and the app uses deterministic fallback.
- Payment events and action publishing are mocked. No Paytm production API or merchant account is connected.
- The seven-day outcome is a comparison window, not proof that the action caused any difference.
- Voice transcription can feed these commands after transcript review. Name and number recognition may be imperfect; typed input remains the reliable fallback. The summary covers all synthetic demo history, not a live “today” feed.

## Safe recovery

- If a payment exceeds the customer's current due, allocation is rejected and no repayment is posted. Use an amount no larger than the verified due.
- If the browser shows a different starting balance or stock count, a previous demo action is present. Start a new walkthrough with a new timestamped `MUNIM_DB_PATH`; do not delete the old database.
- If the brief takes several seconds, wait for the eight-second Gemini timeout and deterministic fallback. The key is server-side and must never be placed in `EXPO_PUBLIC_*` variables.

## Physical phone follow-up

Phone-to-laptop LAN access is not verified by this browser walkthrough. For Expo Go, run Uvicorn with `--host 0.0.0.0`, set `EXPO_PUBLIC_API_BASE_URL` to the laptop's reachable LAN address on port 8000, and use the same network. Keep the Gemini key on the backend only.
