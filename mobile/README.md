# Munim-AI Mobile — KiranaOS Mobile Client

**Owner:** Rachit (mobile UI)  
**Expo SDK:** 58 · **React Native:** 0.88.0 · **TypeScript:** ~5.7.2

> **Scope:** Merchant-facing Expo application connected to the synthetic KiranaOS backend slice (`backend-api-v0.md` / `origin/codex/payment-review`).
> All data is strictly synthetic. No connection or access to Paytm live systems is claimed.

---

## Features Implemented in Mobile

1. **Copilot (Ledger & Commands):**
   - Quick customer lookup and derived debt balance query (`GET /customers/resolve`, `GET /ledger/customers/{id}/balance`).
   - Confirmed credit posting (`POST /ledger/credits`).
   - Confirmed repayment posting (`POST /ledger/repayments`).
   - Utterance logging and example command chips.

2. **Payment Review (`PaymentReviewScreen`):**
   - Lists unallocated or ambiguous payments (`GET /payments/review`).
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
# 1. Clone the repo and check out the mobile scaffold branch
git clone https://github.com/Parths-29/Munim-AI.git
cd Munim-AI
git checkout antigravity/phase-1-mobile-scaffold

# 2. Enter the mobile directory
cd mobile

# 3. Install dependencies
npm install
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

## Environment variables

Copy and fill in values before adding any real API calls (Phase 2+):

```bash
cp ../.env.example .env
```

The only variable the scaffold reads is:

```
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000
```

This is used by `src/api/placeholder.ts`; no network request is made in
Phase 1 regardless of the value.

---

## Project structure

```text
mobile/
├── App.tsx                 # Root component
├── index.ts                # Application entry (registerRootComponent)
├── assets/                 # Placeholder PNG icons (replace before EAS build)
├── src/
│   ├── api/
│   │   └── placeholder.ts  # Stub API client
│   ├── components/
│   │   └── InfoBanner.tsx  # Reusable banner + synthetic-data pill
│   ├── features/
│   │   └── home/
│   │       └── HomeScreen.tsx  # Main home screen
│   └── types/
│       └── index.ts        # Shared TypeScript types
├── app.json                # Expo config (SDK 58, no microphone permission)
├── babel.config.js
├── expo-env.d.ts
├── metro.config.js
├── package.json
├── README.md               # ← you are here
└── tsconfig.json
```

---

## What is deliberately NOT here (Phase 1 boundaries)

| Feature | Status |
|---|---|
| Microphone / speech permission | ❌ Not requested |
| Sarvam STT / TTS | ❌ Not included |
| LLM / AI command parsing | ❌ Not included |
| Credit / repayment / ledger | ❌ Not included |
| Payment reconciliation | ❌ Not included |
| Analytics / business brief | ❌ Not included |
| Backend API calls | ❌ Stub only (`src/api/placeholder.ts`) |
| SQLite / local DB | ❌ Not included |
| Audio libraries | ❌ Not installed |
| Real merchant data | ❌ Never commit |

---

## Expo SDK and assumptions

- **Expo SDK 58** is the `latest` tag as of 30 October 2026 (`expo@58.0.21`).
- **expo-router 4** is the compatible file-based routing library for SDK 58.
- **React Native 0.77.2** ships with SDK 58.
- **New Architecture** is enabled in `app.json` (`newArchEnabled: true`);
  disable it if you encounter issues with older Expo Go builds.
- The Android `permissions` array in `app.json` is explicitly empty to
  prevent any permission dialogs.
- No EAS project ID is configured; `eas build` / `eas submit` are Phase 5+.
- `@expo/vector-icons` is included for the mic-off and send icons; it is
  bundled with Expo SDK and adds no extra native dependencies.

---

## Connecting to the backend (Phase 2)

Set `EXPO_PUBLIC_API_BASE_URL` in `.env` to the FastAPI address (e.g.
`http://192.168.1.42:8000` for LAN) and implement the fetch call in
`src/api/placeholder.ts`. The backend health route is already live at
`GET /health` (see `backend/README.md`).

---

## Known limits and follow-up

- Asset PNGs are 1×1 pixel placeholders. Replace with real brand assets
  before any EAS or production build.
- The local input log (history cards on the home screen) is in-memory only;
  it resets on reload.
- Text path is the only input channel. Voice is a Phase 3 stretch goal,
  pending Sarvam credentials and tested latency.

