# Munim-AI Mobile — KiranaOS Mobile Client

**Owner:** Hackathon team
**Expo SDK:** 58 · **React Native:** 0.88.0 · **TypeScript:** ~5.7.2

> **Scope:** Merchant-facing Expo application connected to the synthetic KiranaOS backend slice documented in [`docs/contracts/backend-api-v0.md`](../docs/contracts/backend-api-v0.md).
> All data is strictly synthetic. No connection or access to Paytm live systems is claimed.

---

## Features Implemented in Mobile

1. **Copilot (Ledger & Text Commands):**
   - A bounded deterministic text parser recognizes one supported request at a time: udhaar, jama, customer balance, or stockout observation.
   - Example inputs: `Raju bhai ka ₹50 udhaar likh do`, `Raju bhai ka ₹300 jamma kar lo`, `Raju bhai ka balance batao`, and `Maggi khatam ho gaya`.
   - Customer/product names resolve through exact backend aliases. Ambiguous matches require the merchant to choose; unsupported or incomplete input does not write data.
   - Credit, repayment, and stockout requests show a preview and require explicit confirmation. Backend writes use idempotency keys.
   - If a credit customer is not found, the preview says that confirmation will create that exact customer and post the credit. Missing repayment/balance customers and missing products are not created automatically.
   - Stockout is recorded as an observation; on-hand quantity stays unchanged until a physical count is confirmed.
   - This command parser is a narrow demo rule set, not an LLM command parser. The separate facts explainer can use Gemini with deterministic fallback.

2. **Payment Review (`PaymentReviewScreen`):**
   - Lists unmatched or review-required successful mock payments (`GET /payments/review`).
   - Can add a clearly labelled synthetic ₹300 payment to populate the review queue (`POST /payments/intake`).
   - Explicit synthetic mock disclaimer banner.
   - Merchant-confirmed manual allocation to a verified customer (`POST /payments/{event_id}/allocate`).

3. **Inventory & Stock (`InventoryScreen`):**
   - Product alias resolution (`GET /products/resolve`) and product catalog creation (`POST /products`).
   - Derived on-hand quantity and movement count (`GET /inventory/products/{id}/stock`).
   - Auditable stockout observation recording (`POST /inventory/stockout-observations`) marked clearly as observation only (does not mutate physical stock count).
   - Confirmed physical count adjustment (`POST /inventory/counts`).

4. **Timeline (`TimelineScreen`):**
   - Append-only business memory stream from `GET /events?limit=50`.
   - Audit trail for credit, repayment, count deltas, and payment events.

5. **Business Insights & Facts (`InsightsScreen`):**
   - Deterministic facts from `GET /insights/facts?persona=kirana|tea_stall|medical_store`.
   - Evidence IDs mapping and explicit synthetic caveats table.
   - Observational-only before/after comparisons (no causal claims).

---

## Prerequisites

| Tool | Minimum version | Check |
|---|---|---|
| Node.js | 20 LTS | `node -v` |
| npm | 10+ | `npm -v` |
| Expo Go on Android | Latest (Play Store) | install on the demo phone |

> **No Android Studio or Xcode is needed** to run on a physical Android
> device via Expo Go. EAS / native builds are not part of Phase 1.

---

## Setup

```bash
# 1. Clone the repo and check out the current product branch
git clone https://github.com/Parths-29/Munim-AI.git
cd Munim-AI
git fetch origin
git switch --track origin/codex/merchant-command-flow

# 2. Enter the mobile directory
cd mobile

# 3. Install the locked dependencies
npm ci
```

---

## Run on Android (Expo Go)

```bash
npm start
# or specifically for Android:
npm run android
```

This prints a **QR code** in the terminal. Open **Expo Go** on your Android
phone, tap **"Scan QR code"**, and point the camera at the code.

> **Same-network requirement:** your laptop and phone must be on the same
> Wi-Fi network. If on a hotspot, scan the QR code from the Expo Go app
> directly; LAN URLs must be reachable.

### Tunnel mode (if LAN fails)

```bash
npx expo start --tunnel
```

Install `@expo/ngrok` if prompted (`npm install -g @expo/ngrok`).

---

## Typecheck

```bash
npm run typecheck
```

---

## Environment variables & Phone Demo Connection

Configure `EXPO_PUBLIC_API_BASE_URL` in `mobile/.env`:

Start by copying `mobile/.env.example` to `mobile/.env`, then replace the
example LAN address with the laptop's current Wi-Fi address. `mobile/.env` is
ignored by Git and must not contain credentials.

```bash
# For local web/emulator testing:
EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000

# For physical phone demo via Expo Go (same Wi-Fi network):
# Replace with your laptop's Wi-Fi LAN IP (e.g. 192.168.0.102)
EXPO_PUBLIC_API_BASE_URL=http://192.168.0.102:8000
```

> **FastAPI backend startup:**
> Run `uvicorn app.main:app --host 0.0.0.0 --port 8000` in `backend/` so that
> it listens on all network interfaces and accepts connections from the phone on LAN.

---

## Project structure

```text
mobile/
├── App.tsx                 # Root component
├── index.ts                # Application entry (registerRootComponent)
├── assets/                 # Placeholder PNG icons (replace before EAS build)
├── src/
│   ├── api/
│   │   ├── ledgerClient.ts # Full typed client for backend v0.5 endpoints
│   │   └── placeholder.ts  # Stub API client
│   ├── components/
│   │   └── InfoBanner.tsx  # Reusable banner + synthetic-data pill
│   ├── features/
│   │   ├── home/
│   │   │   ├── HomeScreen.tsx  # Main hub, command review and business brief
│   │   │   └── parseMerchantCommand.ts # Bounded, deterministic demo parser
│   │   ├── insights/
│   │   │   └── InsightsScreen.tsx  # Business facts & evidence IDs
│   │   ├── inventory/
│   │   │   └── InventoryScreen.tsx # Stock lookup, count & observations
│   │   ├── paymentReview/
│   │   │   └── PaymentReviewScreen.tsx # Review queue & manual allocation
│   │   └── timeline/
│   │       └── TimelineScreen.tsx  # Append-only activity stream
│   └── types/
│       └── index.ts        # Shared TypeScript types
├── app.json                # Expo config (SDK 58, no microphone permission)
├── .env.example            # Safe LAN URL template for Expo Go
├── babel.config.js
├── expo-env.d.ts
├── metro.config.js
├── package.json
├── README.md               # ← you are here
└── tsconfig.json
```

---

## Status and Integrity Boundaries

| Feature | Status |
|---|---|
| Microphone / speech permission | ❌ Not requested (text fallback active) |
| Sarvam STT / TTS | ❌ Not included (future stretch) |
| Live Paytm API / processor | ❌ Never claimed (mock UPI intake only) |
| Customer / Ledger mutations | ✅ Implemented via backend v0.5 |
| Text commands for udhaar, jama, balance, and stockout | ✅ Limited deterministic parser; confirmation required before writes |
| LLM command parsing | ❌ Not implemented; the text parser is not presented as AI |
| Derived balance | ✅ Computed from posted entries only |
| Stockout observation | ✅ Preserved as observation (no count mutation) |
| Physical inventory count | ✅ Explicit count delta confirmation |
| Business facts ("Aaj kaisa raha?") | ✅ Deterministic facts from synthetic fixture |
| Merchant actions | ✅ Clearly mocked (never published to real customers) |
| Backend API calls | ✅ Typed client and screens use the synthetic FastAPI endpoints; `placeholder.ts` is unused legacy scaffold code. |
| SQLite / local DB | ❌ Not included |
| Audio libraries | ❌ Not installed |
| Real merchant data | ❌ Never commit |

---

## Expo SDK and assumptions

- **Expo SDK 58** is pinned at `expo@58.0.21` in the lockfile.
- **React Native 0.88.0** is pinned in `package.json` for this app.
- The app currently uses its own tab navigation; `expo-router` is not installed.
- **New Architecture** is enabled in `app.json` (`newArchEnabled: true`);
  disable it if you encounter issues with older Expo Go builds.
- The Android `permissions` array in `app.json` is explicitly empty to
  prevent any permission dialogs.
- No EAS project ID is configured; `eas build` / `eas submit` are Phase 5+.
- `@expo/vector-icons` is included for the mic-off and send icons; it is
  bundled with Expo SDK and adds no extra native dependencies.

---

## Backend setup for the demo

Set `EXPO_PUBLIC_API_BASE_URL` in `mobile/.env` to the reachable FastAPI address.
The mobile app uses `src/api/ledgerClient.ts`; `src/api/placeholder.ts` is not
used by the current screens. Start and seed the synthetic backend as described
in `backend/README.md` before opening the app.

---

## Known limits and follow-up

- Asset PNGs are 1×1 pixel placeholders. Replace with real brand assets
  before any EAS or production build.
- The local input log (history cards on the home screen) is in-memory only;
  it resets on reload.
- Text path is the only input channel. Voice is a Phase 3 stretch goal,
  pending Sarvam credentials and tested latency.

