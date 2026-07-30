import json
from unittest.mock import MagicMock, Mock, patch

import psycopg2

from integration_framework.integration_log_repository import IntegrationLogRepository
from tests.conftest import make_settings


def make_repository(**settings_overrides):
    settings = make_settings(
        postgres_db="integration",
        postgres_user="service",
        postgres_password="secret",
        service_user_id=7,
        **settings_overrides,
    )
    return IntegrationLogRepository(settings, Mock())


def test_connection_pool_is_lazy():
    with patch(
        "integration_framework.integration_log_repository.psycopg2.pool.ThreadedConnectionPool"
    ) as pool_factory:
        make_repository()

    pool_factory.assert_not_called()


async def test_create_pending_log_connects_and_uses_framework_service_type():
    pool = MagicMock()
    connection = Mock()
    cursor = Mock()
    pool.getconn.return_value = connection
    connection.cursor.return_value = cursor
    cursor.fetchone.side_effect = [(5,), (42,)]

    with patch(
        "integration_framework.integration_log_repository.psycopg2.pool.ThreadedConnectionPool",
        return_value=pool,
    ):
        repository = make_repository(db_pool_max=5)
        log_id = await repository.create_pending_log(
            "RedeemTicket",
            {"barcode": "123"},
            "device-1",
            "request-1",
            "GET",
            "https://example.test/ticket/123",
            None,
        )

    assert log_id == 42
    insert_sql, params = cursor.execute.call_args_list[-1].args
    assert "INSERT INTO integration_request_response" in insert_sql
    assert params[1:7] == (
        "test_service",
        "RedeemTicket",
        json.dumps({"barcode": "123"}),
        "request-1",
        "GET",
        "https://example.test/ticket/123",
    )
    assert params[11:13] == (7, 7)
    connection.commit.assert_called_once()
    pool.putconn.assert_called_once_with(connection)


async def test_complete_log_updates_only_returned_log_id():
    pool = MagicMock()
    connection = Mock()
    cursor = Mock()
    pool.getconn.return_value = connection
    connection.cursor.return_value = cursor

    with patch(
        "integration_framework.integration_log_repository.psycopg2.pool.ThreadedConnectionPool",
        return_value=pool,
    ):
        repository = make_repository()
        await repository.complete_log(42, 500, {"error": "failed"}, {"x": "y"}, 125)

    update_sql, params = cursor.execute.call_args.args
    assert "WHERE id = %s" in update_sql
    assert params[0] == 500
    assert params[4] is True
    assert params[7] == 42


async def test_missing_request_id_and_log_id_are_noops():
    repository = make_repository()

    assert (
        await repository.create_pending_log(
            "RedeemTicket", {}, None, None, "GET", "https://example.test", None
        )
        is None
    )
    await repository.complete_log(None, 200, {}, {}, 10)

    assert repository._pool is None


async def test_database_write_failure_is_swallowed():
    pool = MagicMock()
    connection = Mock()
    pool.getconn.return_value = connection
    connection.cursor.side_effect = RuntimeError("write failed")

    with patch(
        "integration_framework.integration_log_repository.psycopg2.pool.ThreadedConnectionPool",
        return_value=pool,
    ):
        repository = make_repository()
        log_id = await repository.create_pending_log(
            "RedeemTicket",
            {},
            None,
            "request-1",
            "GET",
            "https://example.test",
            None,
        )

    assert log_id is None
    connection.rollback.assert_called_once()
    pool.putconn.assert_called_once_with(connection)


def test_failed_connection_retries_after_cooldown(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(
        "integration_framework.integration_log_repository.time.monotonic", lambda: now[0]
    )
    pool = MagicMock()

    with patch(
        "integration_framework.integration_log_repository.psycopg2.pool.ThreadedConnectionPool",
        side_effect=[psycopg2.OperationalError("offline"), pool],
    ) as pool_factory:
        repository = make_repository(db_reconnect_interval=60)
        assert repository._ensure_pool() is None

        now[0] = 159.0
        assert repository._ensure_pool() is None
        assert pool_factory.call_count == 1

        now[0] = 160.0
        assert repository._ensure_pool() is pool
        assert pool_factory.call_count == 2


def test_close_prevents_future_connections():
    with patch(
        "integration_framework.integration_log_repository.psycopg2.pool.ThreadedConnectionPool"
    ) as pool_factory:
        repository = make_repository()
        repository.close()

        assert repository._ensure_pool() is None

    pool_factory.assert_not_called()
