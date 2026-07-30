import asyncio

from fastapi.testclient import TestClient

from integration_framework.app import IntegrationService
from integration_framework.handlers import HandlerRegistry
from integration_framework.messaging.request_consumer import RequestConsumer
from tests.conftest import make_settings


async def echo_handler(payload, context, logger):
    return True, {"data": payload.get("message")}, ""


def make_service(**kwargs):
    defaults = {
        "settings": make_settings(**kwargs.pop("settings_overrides", {})),
        "registry": HandlerRegistry({"Echo": echo_handler}),
    }
    defaults.update(kwargs)
    return IntegrationService(**defaults)


async def idle_consumer(self):
    await asyncio.Future()


def test_debug_routes_only_in_development(monkeypatch):
    monkeypatch.setattr(RequestConsumer, "run", idle_consumer)

    prod_routes = {route.path for route in make_service().app.routes}
    assert "/debug/simulate-request" not in prod_routes

    dev = make_service(settings_overrides={"app_env": "development"})
    dev_routes = {route.path for route in dev.app.routes}
    assert "/debug/simulate-request" in dev_routes


def test_lifespan_runs_tasks_and_shutdown_hooks(monkeypatch):
    monkeypatch.setattr(RequestConsumer, "run", idle_consumer)

    events = []

    async def extra_task(settings, context):
        events.append("task-started")
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            events.append("task-cancelled")
            raise

    async def shutdown_hook():
        events.append("shutdown-hook")

    service = make_service(extra_tasks=[extra_task], on_shutdown=[shutdown_hook])

    with TestClient(service.app) as client:
        assert client.get("/health").status_code == 200

    assert events == ["task-started", "task-cancelled", "shutdown-hook"]


def test_configure_app_hook(monkeypatch):
    monkeypatch.setattr(RequestConsumer, "run", idle_consumer)

    def configure(app):
        @app.get("/custom")
        async def custom():
            return {"custom": True}

    service = make_service(configure_app=configure)
    with TestClient(service.app) as client:
        assert client.get("/custom").json() == {"custom": True}


def test_context_reaches_handlers(monkeypatch):
    monkeypatch.setattr(RequestConsumer, "run", idle_consumer)

    seen = {}

    async def handler(payload, context, logger):
        seen["context"] = context
        return True, {}, ""

    sentinel = object()
    service = make_service(
        registry=HandlerRegistry({"Echo": handler}),
        context=sentinel,
        settings_overrides={"app_env": "development"},
    )

    with TestClient(service.app) as client:
        response = client.post(
            "/debug/simulate-request",
            json={"serviceType": "test_service", "payload": {"messageType": "Echo"}},
        )
        assert response.json()["success"] == 0

    assert seen["context"] is sentinel


def test_shutdown_hook_failure_does_not_block_others(monkeypatch):
    monkeypatch.setattr(RequestConsumer, "run", idle_consumer)

    events = []

    async def failing_hook():
        raise RuntimeError("hook failed")

    async def second_hook():
        events.append("second-hook")

    service = make_service(on_shutdown=[failing_hook, second_hook])
    with TestClient(service.app):
        pass

    assert events == ["second-hook"]
