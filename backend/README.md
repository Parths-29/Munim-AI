# Munim-AI backend scaffold

Phase 1 provides only a small FastAPI health endpoint. Domain commands, storage, and AI integrations are intentionally not implemented in this scaffold.

## Requirements

- Python 3.11 or a compatible Python version supported by the team environment.

## Run on Windows PowerShell

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/health` or `http://127.0.0.1:8000/docs`.

## Run on macOS/Linux

From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The health response confirms only that the local API process is responding. It does not indicate a Paytm connection or a ready database.
