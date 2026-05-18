import os

import pytest

from app.config import reset_settings
from app.gemini_service import reset_vertex


@pytest.fixture(autouse=True)
def env_config(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    monkeypatch.setenv("GCP_LOCATION", "us-central1")
    monkeypatch.setenv("BQ_TABLE", "test-project.dataset.precios")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("GEMINI_MODEL_FALLBACK", "gemini-2.5-flash")
    monkeypatch.setenv("SKIP_IF_PROCESSED", "true")
    monkeypatch.setenv("REQUIRE_PDF", "true")
    monkeypatch.setenv("STRICT_FECHA", "false")
    monkeypatch.delenv("ALLOWED_BUCKET", raising=False)
    reset_settings()
    reset_vertex()
    yield
    reset_settings()
    reset_vertex()


@pytest.fixture
def flask_app():
    from main import app

    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()
