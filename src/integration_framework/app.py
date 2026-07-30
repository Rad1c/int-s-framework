"""
IntegrationService — the main orchestrator.

Builds a FastAPI app whose lifespan starts the request/response consumer and
any extra background tasks, mounts the health (and, in development, debug)
routes, and runs uvicorn with graceful shutdown. A service only supplies its
settings, handlers, and context:

    service = IntegrationService(
        settings=Settings(),            # subclass of FrameworkSettings
        registry=registry,              # HandlerRegistry with the service's handlers
        context=api_client,             # passed to every handler
        extra_tasks=[my_poller],        # optional: async (settings, context) -> None
        configure_app=setup_routes,     # optional: (app) -> None, mount extra routers
        on_shutdown=[api_client.close], # optional: async cleanup hooks
    )
    service.run()
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI

from integration_framework.api import register_debug_routes, register_health_routes
from integration_framework.handlers import HandlerRegistry
from integration_framework.integration_log_repository import IntegrationLogRepository
from integration_framework.logging import setup_logging
from integration_framework.messaging.request_consumer import RequestConsumer
from integration_framework.messaging.state import ConsumerState
from integration_framework.settings import FrameworkSettings

BackgroundTask = Callable[[FrameworkSettings, Any], Awaitable[None]]

_logger = logging.getLogger(__name__)


class IntegrationService:
    def __init__(
        self,
        settings: FrameworkSettings,
        registry: HandlerRegistry,
        context: Any = None,
        extra_tasks: Iterable[BackgroundTask] = (),
        configure_app: Callable[[FastAPI], None] | None = None,
        on_shutdown: Iterable[Callable[[], Awaitable[None]]] = (),
    ):
        self.settings = settings
        self.registry = registry
        self.context = context
        self.extra_tasks = list(extra_tasks)
        self.on_shutdown = list(on_shutdown)

        setup_logging(settings.log_level, settings.log_file, settings.log_retention_days)
        self.logger = logging.getLogger(settings.service_name)
        self.audit_repository = IntegrationLogRepository(settings, self.logger)

        self.consumer_state = ConsumerState()
        self.consumer = RequestConsumer(
            settings=settings,
            registry=registry,
            context=context,
            audit_repository=self.audit_repository,
            state=self.consumer_state,
            logger=self.logger,
        )

        self.app = FastAPI(title=settings.service_name, lifespan=self._lifespan)
        register_health_routes(self.app, self.consumer_state, settings.service_name)
        if settings.is_development:
            register_debug_routes(self.app, self.consumer.process, self.logger)
            self.logger.info("Debug routes registered (development mode)")

        if configure_app:
            configure_app(self.app)

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        self.logger.info("%s starting", self.settings.service_name)

        tasks = [asyncio.create_task(self.consumer.run(), name="request-consumer")]
        for task_fn in self.extra_tasks:
            tasks.append(asyncio.create_task(task_fn(self.settings, self.context), name=task_fn.__name__))

        self.logger.info("Started %d background task(s)", len(tasks))
        try:
            yield
        finally:
            self.logger.info("%s stopping", self.settings.service_name)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for hook in self.on_shutdown:
                try:
                    await hook()
                except Exception:
                    self.logger.exception("Shutdown hook %s failed", hook)
            self.audit_repository.close()
            self.logger.info("%s stopped", self.settings.service_name)

    def run(self) -> None:
        """Run uvicorn (blocking). Consumer and extra tasks are managed by the
        FastAPI lifespan, so SIGINT/SIGTERM shut everything down gracefully."""
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=self.settings.http_port,
            log_level="warning",
        )
