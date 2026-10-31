# Running Munim-AI: laptop web, Expo Go on a phone, and phone browser

Keys live only in the ignored root `.env` (backend). Never put `SARVAM_API_KEY` or `GEMINI_API_KEY` in `mobile/.env`
or any `EXPO_PUBLIC_*` variable: everything `EXPO_PUBLIC_*` is bundled into the app.

Check the voice agent's interpreter first (prints only a status category, never the key):

```powershell
cd backend
python -m scripts.check_gemini
```

`status: ok` means Gemini is used (it also prints which key slot answered). `auth_error`/`quota` after all configured
keys → update the keys; `model_not_found` → set `GEMINI_MODEL` (default `gemini-3.6-flash`); `unreachable` →
network/proxy. Without Gemini the agent still works on deterministic Hinglish rules and says so in the app.

### Local `.env` (repo root, ignored by Git)

Copy `.env.example` to `.env` and fill in values on each laptop. Never paste keys into chat, docs, or mobile code.

```
SARVAM_API_KEY=...                 # speech-to-text and spoken replies
GEMINI_API_KEY=...                 # primary
GEMINI_API_KEY_FALLBACK_2=...      # optional; used only if a key is rejected or over quota
GEMINI_API_KEY_FALLBACK_3=...      # optional
GEMINI_MODEL=gemini-3.6-flash
# optional: SARVAM_TTS_MODEL=bulbul:v3   SARVAM_TTS_SPEAKER=shubh
```

Restart the backend after editing `.env`. `GET /agent/health` lists configured key **slot names** and the voice-output
mode (`live`, `fake`, `off`), never key values.

### Spoken replies

After each answer, proposal, question, and confirmed save, the app shows the reply text and asks the backend for audio
(`POST /agent/speak`, Sarvam Bulbul). Use the speaker toggle to turn voice off, **Replay** to hear it again, and **Stop**
to cut it off. Audio is never stored: the backend returns it, the app plays it (on a phone via a temporary cache file
that is deleted afterwards). If voice output fails, the text stays and a short error explains why (missing key, quota,
timeout). Voice requests time out after 25 s.

## 1. Web on the same laptop

```powershell
# terminal 1 (backend)
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# terminal 2 (app)
cd mobile
npx expo start --web          # opens http://localhost:8081
```

- No `mobile/.env` needed: the app defaults to `http://127.0.0.1:8000`.
- CORS already allows `http://localhost:8081` and `http://127.0.0.1:8081`.
- The microphone works because `localhost` counts as a secure context.

## 2. Expo Go on a physical phone (same Wi-Fi)

1. Find the laptop's Wi-Fi IPv4 address: `ipconfig` → "Wireless LAN adapter Wi-Fi" → IPv4 (for example `192.168.1.42`).
2. Create `mobile/.env` (ignored by Git):
   ```
   EXPO_PUBLIC_API_BASE_URL=http://192.168.1.42:8000
   ```
3. Bind the backend to all interfaces (a `127.0.0.1` backend is unreachable from the phone):
   ```powershell
   cd backend
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
4. Allow port 8000 through Windows Firewall on the Private profile (admin PowerShell, once):
   ```powershell
   New-NetFirewallRule -DisplayName "Munim backend 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private
   ```
   The Wi-Fi network must be set to **Private**, and guest networks with client isolation will block the phone.
5. Restart Expo with a clean cache so the new `.env` value is bundled: `npx expo start -c`, then scan the QR code
   with Expo Go.
6. Sanity check from the phone's browser: `http://192.168.1.42:8000/health` should show `{"status":"ok", ...}`.

Native apps do not use CORS. Voice: tap the mic, speak, tap again; the transcript appears in the text box for editing
and is **never sent automatically**. Transcription gives up with a clear message after 45 seconds and agent calls after
20 seconds, so the indicator cannot spin forever. If the server is unreachable, the message names the address it tried.

## 3. Phone browser (the web build opened on the phone)

Browsers allow the microphone only in a **secure context**: HTTPS, or `localhost` on the same device. Opening
`http://192.168.1.42:8081` on the phone loads the app but the browser will block the microphone. Options:

- **Recommended:** use Expo Go (setup 2) on the phone.
- **HTTPS tunnel** for both the web app and the backend, for example with Cloudflare's `cloudflared`:
  ```powershell
  cloudflared tunnel --url http://localhost:8081    # → https://<web>.trycloudflare.com
  cloudflared tunnel --url http://localhost:8000    # → https://<api>.trycloudflare.com
  ```
  Then set `EXPO_PUBLIC_API_BASE_URL=https://<api>.trycloudflare.com` in `mobile/.env`, restart Expo with `-c`, and
  start the backend with `MUNIM_CORS_ORIGINS=https://<web>.trycloudflare.com` (in `.env` or the shell). The backend must
  also be HTTPS: an HTTPS page cannot call an `http://` API (mixed content). Tunnels are public URLs; use synthetic
  data only and stop them after the demo.
- Typed commands work over plain `http://LAN-IP:8081` if you add that origin to `MUNIM_CORS_ORIGINS`
  (for example `MUNIM_CORS_ORIGINS=http://localhost:8081,http://192.168.1.42:8081`); only the mic needs HTTPS.

## What was verified (2026-10-31, spoken replies)

- Web build in headless Chromium against a seeded backend with Sarvam TTS in fake mode: every reply (balance, proposal,
  saved receipt with the balance read back after the write, clarifications) requested `/agent/speak` (HTTP 200) and the
  reply bar went from playing to Replay; zero console errors. Expo export Android (744 modules) and web (335) clean.
- Not verified: live Sarvam Bulbul audio, live Gemini wording/rotation against Google, a physical phone.

## What was verified earlier (2026-10-31)

- Expo `export` for Android (742 modules) and web (333 modules) bundled with no errors or warnings.
- The web build was driven in headless Chromium against the backend: balance answer, credit proposal → Confirm →
  Saved, "aur 500 add kar do" follow-up with inferred customer/action, compound new-customer + udhaar, "pachs"
  clarification, "Amul" product choice; zero browser console errors.
- Network rules: a `127.0.0.1` backend was unreachable via a non-loopback address; a `0.0.0.0` backend answered
  `/health`; a CORS preflight from a LAN web origin was rejected (400) by default and allowed (200) once added to
  `MUNIM_CORS_ORIGINS`.
- Not verified here: a physical phone with Expo Go, Windows Firewall, live Sarvam STT, live Gemini (the sandbox's
  proxy blocks Google's API host).
