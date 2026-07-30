"""
Development-only debug routes.

POST /debug/simulate-request accepts the same JSON payload as a RabbitMQ
request message and runs it through the same processing path, returning the
response envelope directly instead of publishing it. Only registered when
settings.app_env == 'development'.
"""

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from integration_framework.messaging.publisher import correlation_headers

ProcessFn = Callable[[dict, str, str], Awaitable[dict | None]]

_logger = logging.getLogger(__name__)


def register_debug_routes(
    app: FastAPI, process_fn: ProcessFn, logger: logging.Logger | None = None
) -> None:
    logger = logger or _logger

    @app.post("/debug/simulate-request")
    async def simulate_request(request: Request):
        try:
            message_data = await request.json()
        except ValueError as e:
            logger.error("Invalid JSON in debug request: %s", e)
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

        device_id = request.headers.get("X-Device-Id", "debug")
        request_id = request.headers.get("X-Request-Id", "debug-request")

        logger.info(
            "Debug endpoint received request - serviceType=%s, X-Request-Id=%s, X-Device-Id=%s",
            message_data.get("serviceType"), request_id, device_id,
        )

        try:
            response = await process_fn(message_data, device_id, request_id)
        except Exception as e:
            logger.exception("Error processing debug request")
            raise HTTPException(status_code=500, detail=f"Processing error: {e}")

        if response is None:
            return JSONResponse(content={"ignored": True}, status_code=200)

        logger.info(
            "Debug request processed - X-Request-Id=%s, success=%s", request_id, response.get("success")
        )
        return JSONResponse(content=response, headers=correlation_headers(device_id, request_id))
