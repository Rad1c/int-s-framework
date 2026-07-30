import httpx

from integration_framework.http_client import ApiClient


def make_client(handler, **kwargs) -> ApiClient:
    return ApiClient(
        base_url="https://api.example.com",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


async def test_get_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/thing/1"
        return httpx.Response(200, json={"id": 1}, headers={"X-Custom": "yes"})

    client = make_client(handler)
    success, data, headers, error = await client.get("/api/thing/1")

    assert success is True
    assert data == {"id": 1}
    assert headers["x-custom"] == "yes"
    assert error == ""
    await client.close()


async def test_post_sends_json_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert b'"key"' in request.content
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler)
    success, data, _, _ = await client.post("/api/thing", {"key": "value"})
    assert success is True
    assert data == {"ok": True}
    await client.close()


async def test_api_key_header():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "secret"
        return httpx.Response(200, json={})

    client = make_client(handler, api_key="secret")
    success, *_ = await client.get("/api/thing")
    assert success is True
    await client.close()


async def test_4xx_not_retried():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(404, json={"error": "not found"})

    client = make_client(handler, retry_attempts=3)
    success, data, _, error = await client.get("/api/thing")

    assert success is False
    assert error == "HTTP 404"
    assert data == {"error": "not found"}
    assert calls["count"] == 1
    await client.close()


async def test_5xx_retried(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(500)
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler, retry_attempts=3)
    success, data, _, _ = await client.get("/api/thing")

    assert success is True
    assert calls["count"] == 3
    await client.close()


async def test_connection_error_exhausts_retries(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", _no_sleep)
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        raise httpx.ConnectError("refused")

    client = make_client(handler, retry_attempts=2)
    success, data, headers, error = await client.get("/api/thing")

    assert success is False
    assert "Request error" in error
    assert calls["count"] == 2
    await client.close()


async def test_non_dict_json_wrapped():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1, 2, 3])

    client = make_client(handler)
    success, data, *_ = await client.get("/api/list")
    assert success is True
    assert data == {"data": [1, 2, 3]}
    await client.close()


async def _no_sleep(_delay):
    pass
