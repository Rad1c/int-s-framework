"""
Generic async HTTP client for calling external APIs from handlers.
GET/POST with retry logic, optional API key header and custom CA cert.
Returns (success, data, headers, error_message) — generalized from the
betbox API client so services don't re-implement retry/SSL plumbing.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

import httpx

Response = Tuple[bool, Dict[str, Any], Dict[str, str], str]

_logger = logging.getLogger(__name__)


class ApiClient:
    def __init__(
        self,
        base_url: str,
        retry_attempts: int = 3,
        timeout: float = 30.0,
        verify_ssl: bool = True,
        api_key: str = "",
        api_key_header: str = "x-api-key",
        cert_path: str = "",
        logger: logging.Logger = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.retry_attempts = max(1, retry_attempts)
        self.api_key = api_key
        self.api_key_header = api_key_header
        self.logger = logger or _logger

        # verify_ssl=True with a cert path verifies against that cert;
        # verify_ssl=True without one uses system CAs; False disables verification.
        verify = cert_path if (verify_ssl and cert_path) else verify_ssl
        self._client = httpx.AsyncClient(verify=verify, timeout=timeout, transport=transport)

    async def close(self) -> None:
        await self._client.aclose()

    def _build_url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers[self.api_key_header] = self.api_key
        return headers

    async def get(self, path: str) -> Response:
        return await self._request("GET", path)

    async def post(self, path: str, payload: Optional[Dict[str, Any]] = None) -> Response:
        return await self._request("POST", path, payload)

    async def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Response:
        url = self._build_url(path)
        last_error = ""

        for attempt in range(1, self.retry_attempts + 1):
            try:
                self.logger.debug("%s %s (attempt %d/%d)", method, url, attempt, self.retry_attempts)
                response = await self._client.request(
                    method, url, json=payload, headers=self._build_headers()
                )
                data = self._parse_body(response)
                headers = dict(response.headers)

                if response.is_success:
                    return True, data, headers, ""

                last_error = f"HTTP {response.status_code}"
                self.logger.warning("%s %s failed: %s", method, url, last_error)
                # Client errors (4xx) are not transient; don't retry.
                if response.status_code < 500:
                    return False, data, headers, last_error

            except httpx.HTTPError as e:
                last_error = f"Request error: {e}"
                self.logger.warning("%s %s failed: %s", method, url, last_error)

            if attempt < self.retry_attempts:
                await asyncio.sleep(min(2 ** (attempt - 1), 10))

        return False, {}, {}, last_error

    @staticmethod
    def _parse_body(response: httpx.Response) -> Dict[str, Any]:
        try:
            body = response.json()
            return body if isinstance(body, dict) else {"data": body}
        except ValueError:
            return {"raw": response.text} if response.text else {}
