from fastapi import FastAPI
from fastapi.testclient import TestClient

from integration_framework.api.health import register_health_routes
from integration_framework.messaging.state import ConsumerState


def make_client(state: ConsumerState) -> TestClient:
    app = FastAPI()
    register_health_routes(app, state, "Test Service")
    return TestClient(app)


def test_health_connected():
    state = ConsumerState()
    state.mark_connected()
    response = make_client(state).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["rabbitmq"]["connected"] is True
    assert body["rabbitmq"]["state"] == "connected"
    assert body["rabbitmq"]["last_connected_at"] is not None
    assert body["rabbitmq"]["last_error"] is None


def test_health_degraded_when_disconnected():
    state = ConsumerState()
    state.mark_disconnected("broker unreachable")
    response = make_client(state).get("/health")

    body = response.json()
    assert body["status"] == "degraded"
    assert body["rabbitmq"]["connected"] is False
    assert body["rabbitmq"]["last_error"] == "broker unreachable"


def test_root():
    response = make_client(ConsumerState()).get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Test Service"}
