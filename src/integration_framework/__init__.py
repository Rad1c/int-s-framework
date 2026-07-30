"""
integration-service-framework — shared foundation for Monroe integration services.

Public API:

    from integration_framework import (
        FrameworkSettings, HandlerRegistry, IntegrationService,
        ConsumerState, IntegrationLogRepository, ok, error,
    )
"""

from integration_framework.app import IntegrationService
from integration_framework.envelope import envelope, error, ok
from integration_framework.handlers import HandlerRegistry, route_payload
from integration_framework.integration_log_repository import IntegrationLogRepository
from integration_framework.logging import setup_logging
from integration_framework.messaging import (
    ConsumerState,
    RequestConsumer,
    create_robust_connection,
    publish_response,
)
from integration_framework.settings import FrameworkSettings

__all__ = [
    "ConsumerState",
    "FrameworkSettings",
    "HandlerRegistry",
    "IntegrationLogRepository",
    "IntegrationService",
    "RequestConsumer",
    "create_robust_connection",
    "envelope",
    "error",
    "ok",
    "publish_response",
    "route_payload",
    "setup_logging",
]
