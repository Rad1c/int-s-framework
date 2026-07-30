from fastapi import FastAPI
from fastapi.testclient import TestClient

from integration_framework.api.debug import register_debug_routes
from integration_framework.envelope import ok


def make_client(process_fn) -> TestClient:
    app = FastAPI()
    register_debug_routes(app, process_fn)
    return TestClient(app, raise_server_exceptions=False)


def test_simulate_request_returns_envelope_and_headers():
    async def process(message_data, device_id, request_id):
        return ok({"echo": message_data["payload"]["message"]})

    client = make_client(process)
    response = client.post(
        "/debug/simulate-request",
        json={"serviceType": "test_service", "payload": {"messageType": "Echo", "message": {"a": 1}}},
        headers={"X-Device-Id": "dev-9", "X-Request-Id": "req-9"},
    )

    assert response.status_code == 200
    assert response.json() == {"success": 0, "payload": {"echo": {"a": 1}}, "error_message": ""}
    assert response.headers["X-Device-Id"] == "dev-9"
    assert response.headers["X-Request-Id"] == "req-9"


def test_simulate_request_default_headers():
    async def process(message_data, device_id, request_id):
        assert device_id == "debug"
        assert request_id == "debug-request"
        return ok()

    response = make_client(process).post("/debug/simulate-request", json={"serviceType": "x", "payload": {}})
    assert response.status_code == 200


def test_simulate_request_ignored_service_type():
    async def process(message_data, device_id, request_id):
        return None

    response = make_client(process).post(
        "/debug/simulate-request", json={"serviceType": "other", "payload": {}}
    )
    assert response.status_code == 200
    assert response.json() == {"ignored": True}


def test_simulate_request_invalid_json():
    async def process(message_data, device_id, request_id):
        return ok()

    response = make_client(process).post(
        "/debug/simulate-request", content=b"not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400


def test_simulate_request_processing_error():
    async def process(message_data, device_id, request_id):
        raise RuntimeError("kaboom")

    response = make_client(process).post("/debug/simulate-request", json={"serviceType": "x"})
    assert response.status_code == 500
