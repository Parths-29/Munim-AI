"""Every test gets its own temporary SQLite file; the demo database is never touched."""

import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from app.services import database


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    path = tmp_path / "munim-test.sqlite3"
    monkeypatch.setattr(database, "DB_PATH", path)
    # Tests must never reach live providers even if a developer has local keys.
    for name in ("GEMINI_API_KEY", "SARVAM_API_KEY", "MUNIM_ADMIN_TOKEN", "MUNIM_INVOICE_PROVIDER", "MUNIM_INWARD_LLM",
                 "MUNIM_NOTEBOOK_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MUNIM_SARVAM_MODE", "fake")  # offline translate/TTS; never the live API in tests
    monkeypatch.setattr("app.services.speech._api_key", lambda: None)
    monkeypatch.setattr("app.services.sarvam._api_key", lambda: None)
    monkeypatch.setattr("app.services.agent_llm._api_keys", lambda: [])  # agent: deterministic unless a test fakes Gemini
    for target in ("explainer", "command_nlp", "inward_parser", "invoice_extraction"):
        monkeypatch.setattr(f"app.services.{target}._get_api_key", lambda: None)

    def no_network(*args, **kwargs):
        raise AssertionError("Tests must not make outbound network calls.")

    monkeypatch.setattr("urllib.request.urlopen", no_network)
    database.initialize_database()
    return path


@pytest.fixture
def client():
    from app.main import app

    # No context manager: skip lifespan so the 90-day synthetic fixture is not seeded per test.
    return TestClient(app)


def key(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


@pytest.fixture
def make_customer(client):
    def _make(name="Raju bhai", aliases=None):
        response = client.post("/customers", json={
            "display_name": name, "aliases": aliases or [], "confirmed": True, "idempotency_key": key("cust"),
        })
        assert response.status_code == 201, response.text
        return response.json()
    return _make


@pytest.fixture
def make_product(client):
    def _make(name, unit, aliases=None):
        response = client.post("/products", json={
            "name": name, "unit": unit, "aliases": aliases or [], "confirmed": True, "idempotency_key": key("prod"),
        })
        assert response.status_code == 201, response.text
        return response.json()
    return _make


@pytest.fixture
def make_supplier(client):
    def _make(name, aliases=None, **extra):
        response = client.post("/suppliers", json={
            "display_name": name, "aliases": aliases or [], "confirmed": True, "idempotency_key": key("sup"), **extra,
        })
        assert response.status_code == 201, response.text
        return response.json()
    return _make


def table_count(path, table: str) -> int:
    with sqlite3.connect(path) as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
