"""Basic tests for the FastAPI app."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from src.app import create_app


@pytest.fixture
def client():
    with patch("src.app.JobManager") as mock_jm:
        mock_jm.return_value = MagicMock()
        app = create_app()
        yield TestClient(app, follow_redirects=False)


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_index_redirects_to_login(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Sign in with Slack" in resp.content


def test_dashboard_requires_auth(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 302


def test_api_requires_auth(client):
    resp = client.get("/api/conversations")
    assert resp.status_code == 302


def test_nuke_requires_auth(client):
    resp = client.post("/api/nuke")
    assert resp.status_code == 302
