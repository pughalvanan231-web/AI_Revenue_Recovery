import pytest
from fastapi.testclient import TestClient
from server import app
import json

client = TestClient(app)


def test_root():
    response = client.get("/api/events")
    assert response.status_code == 200
    assert "events" in response.json()


def test_new_event():
    response = client.post("/api/events/new")
    assert response.status_code == 200
    data = response.json()
    assert "event_id" in data
    assert "_raw" in data


def test_pipeline_lifecycle():
    # 1. Create event
    response = client.post("/api/events/new")
    event_data = response.json()

    # 2. Run pipeline
    response = client.post(
        "/api/pipeline/run", json={"event": {"_raw": event_data["_raw"]}}
    )
    assert response.status_code == 200
    data = response.json()
    assert "diagnosis" in data
    assert "decision" in data
    assert "execution" in data

    # 3. Duplicate protection
    response2 = client.post(
        "/api/pipeline/run", json={"event": {"_raw": event_data["_raw"]}}
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["execution"]["duplicate_blocked"] == True


def test_state_listing():
    response = client.get("/api/state/reservations")
    assert response.status_code == 200
    assert "rows" in response.json()

    response = client.get("/api/state/executors")
    assert response.status_code == 200
    assert "rows" in response.json()


def test_reset():
    response = client.post("/api/state/reset")
    assert response.status_code == 200


def test_failures():
    r1 = client.post("/api/failure/concurrent-webhooks")
    assert r1.status_code == 200
    r2 = client.post("/api/failure/stale-reservation")
    assert r2.status_code == 200
    r3 = client.post("/api/failure/duplicate-executor")
    assert r3.status_code == 200
