from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests

from config import AppConfig


class CPQClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self._configure_auth()

    def _configure_auth(self) -> None:
        # Prefer Bearer token if provided
        if self.config.api.bearer_token:
            self.session.headers.update(
                {"Authorization": f"Bearer {self.config.api.bearer_token}"}
            )
        # Otherwise fall back to basic auth if username/password exist
        elif self.config.api.username and self.config.api.password:
            self.session.auth = (
                self.config.api.username,
                self.config.api.password,
            )

        # Always request JSON
        self.session.headers.update({"Accept": "application/json"})

    def fetch_transaction_data(self, transaction_id: str) -> Dict[str, Any]:
        base = self.config.api.base_url.rstrip("/")

        # Default v16 endpoint (as specified)
        # Example: /commerceDocumentsUcpqStandardCommerceProcessTransaction/{transactionId}
        url = f"{base}/commerceDocumentsUcpqStandardCommerceProcessTransaction/{transaction_id}"

        # Retry logic for transient failures
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.config.api.retry_attempts + 1):
            try:
                resp = self.session.get(url, timeout=self.config.api.timeout)
                
                # Debug: Print response details on auth failure
                if resp.status_code == 401:
                    print(f"  DEBUG: HTTP 401 Response Details:")
                    print(f"    URL: {url}")
                    print(f"    Status: {resp.status_code}")
                    print(f"    Response Headers: {dict(resp.headers)}")
                    print(f"    Response Body (first 500 chars): {resp.text[:500]}")
                    if hasattr(self.session, 'auth') and self.session.auth:
                        import base64
                        auth_str = f"{self.session.auth[0]}:{self.session.auth[1]}"
                        auth_bytes = auth_str.encode('utf-8')
                        auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
                        print(f"    Auth Header would be: Basic {auth_b64[:20]}...")
                    raise CPQAuthError("Authentication failed - check credentials/token")
                
                if resp.status_code == 404:
                    raise CPQNotFoundError(f"Transaction ID not found: {transaction_id}")
                resp.raise_for_status()
                return resp.json()
            except (requests.Timeout, requests.ConnectionError) as ex:
                last_exc = ex
                if attempt < self.config.api.retry_attempts:
                    time.sleep(0.5 * attempt)
                    continue
                raise CPQConnectionError("API connection timeout") from ex
            except requests.HTTPError as ex:
                # Surface 5xx as server error
                if 500 <= ex.response.status_code < 600:
                    raise CPQServerError(
                        f"Server error: {ex.response.status_code}"
                    ) from ex
                raise

        if last_exc:
            raise last_exc
        raise RuntimeError("Unreachable")

    def fetch_transaction_lines(self, transaction_id: str) -> Dict[str, Any]:
        """Fetch transactionLine child collection for a transaction.

        Returns JSON as provided by the API (often with items under 'items'/'links').
        """
        base = self.config.api.base_url.rstrip("/")
        url = f"{base}/commerceDocumentsUcpqStandardCommerceProcessTransaction/{transaction_id}/transactionLine"
        resp = self.session.get(url, timeout=self.config.api.timeout)
        if resp.status_code == 404:
            return {"items": []}
        if resp.status_code == 401:
            raise CPQAuthError("Authentication failed - check credentials/token")
        resp.raise_for_status()
        return resp.json()


class CPQError(Exception):
    pass


class CPQNotFoundError(CPQError):
    pass


class CPQAuthError(CPQError):
    pass


class CPQServerError(CPQError):
    pass


class CPQConnectionError(CPQError):
    pass


