"""ClinicIQ REST API client with OAuth 2.0 authentication.

Handles:
- OAuth 2.0 Client Credentials token lifecycle
- Automatic cursor-based pagination
- Rate limiting (respects X-RateLimit-* headers)
- Retries with exponential backoff
- Incremental sync state persistence
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from etl.config import CLINICIQ_API, SYNC_STATE_FILE

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised when OAuth 2.0 authentication fails."""


class APIError(Exception):
    """Raised on non-retryable API errors."""

    def __init__(self, status_code: int, message: str, details: Any = None):
        self.status_code = status_code
        self.details = details
        super().__init__(f"HTTP {status_code}: {message}")


class ClinicIQClient:
    """HTTP client for ClinicIQ REST API with OAuth 2.0 Client Credentials."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        scope: Optional[str] = None,
    ):
        cfg = CLINICIQ_API
        self.base_url = (base_url or cfg["base_url"]).rstrip("/")
        self.token_url = token_url or cfg["token_url"]
        self.client_id = client_id or cfg["client_id"]
        self.client_secret = client_secret or cfg["client_secret"]
        self.scope = scope or cfg["scope"]
        self.api_prefix = cfg["api_prefix"]
        self.page_size = cfg["page_size"]
        self.timeout = cfg["request_timeout"]

        if not self.client_id or not self.client_secret:
            raise AuthError(
                "CLINICIQ_CLIENT_ID and CLINICIQ_CLIENT_SECRET must be set. "
                "Check your .env file."
            )

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

        # Rate limiting state
        self._rate_remaining: Optional[int] = None
        self._rate_reset: Optional[float] = None
        self._min_interval = 60.0 / cfg["rate_limit_per_minute"]

        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        """Build requests session with retry strategy for 5xx and network errors."""
        session = requests.Session()
        retry = Retry(
            total=CLINICIQ_API["max_retries"],
            backoff_factor=1.0,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    # ── OAuth 2.0 ──────────────────────────────────────────────

    def _ensure_token(self) -> None:
        """Obtain or refresh access token if needed."""
        now = time.time()
        if self._access_token and now < self._token_expires_at - 60:
            return  # token still valid (with 60s buffer)

        logger.info("Requesting new OAuth 2.0 access token...")
        resp = self._session.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": self.scope,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )

        if resp.status_code != 200:
            raise AuthError(
                f"OAuth token request failed: HTTP {resp.status_code} — {resp.text}"
            )

        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expires_at = now + data.get("expires_in", 3600)
        logger.info(
            "Access token obtained (expires in %ds)", data.get("expires_in", 3600)
        )

    # ── Rate Limiting ──────────────────────────────────────────

    def _respect_rate_limit(self) -> None:
        """Sleep if we're about to hit the rate limit."""
        if self._rate_remaining is not None and self._rate_remaining <= 2:
            if self._rate_reset:
                wait = max(0, self._rate_reset - time.time()) + 1
                logger.warning("Rate limit nearly exhausted, sleeping %.1fs", wait)
                time.sleep(wait)
                return

        time.sleep(self._min_interval)

    def _update_rate_limits(self, headers: dict) -> None:
        """Parse X-RateLimit-* response headers."""
        if "X-RateLimit-Remaining" in headers:
            self._rate_remaining = int(headers["X-RateLimit-Remaining"])
        if "X-RateLimit-Reset" in headers:
            try:
                self._rate_reset = float(headers["X-RateLimit-Reset"])
            except ValueError:
                pass

    # ── Core Request ───────────────────────────────────────────

    def _request(
        self, method: str, path: str, params: Optional[dict] = None
    ) -> requests.Response:
        """Execute authenticated API request with rate-limit awareness."""
        self._ensure_token()
        self._respect_rate_limit()

        url = f"{self.base_url}{self.api_prefix}{path}"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        logger.debug("API %s %s params=%s", method, url, params)
        resp = self._session.request(
            method, url, params=params, headers=headers, timeout=self.timeout
        )

        self._update_rate_limits(resp.headers)

        if resp.status_code == 401:
            logger.warning("Token expired mid-session, re-authenticating...")
            self._access_token = None
            self._ensure_token()
            headers["Authorization"] = f"Bearer {self._access_token}"
            resp = self._session.request(
                method, url, params=params, headers=headers, timeout=self.timeout
            )

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 60))
            logger.warning("Rate limited (429), retrying after %ds", retry_after)
            time.sleep(retry_after)
            return self._request(method, path, params)

        if resp.status_code >= 400:
            try:
                err = resp.json().get("error", {})
            except Exception:
                err = {"message": resp.text}
            raise APIError(
                resp.status_code,
                err.get("message", resp.text),
                err.get("details"),
            )

        return resp

    def get(self, path: str, params: Optional[dict] = None) -> dict:
        """GET request, return parsed JSON."""
        resp = self._request("GET", path, params)
        return resp.json()

    # ── Paginated Fetching ─────────────────────────────────────

    def get_all_pages(
        self,
        path: str,
        params: Optional[dict] = None,
        limit: Optional[int] = None,
    ) -> Generator[list[dict], None, None]:
        """Yield pages of data, automatically following cursor pagination.

        Args:
            path: API endpoint path (e.g. '/transactions')
            params: Query parameters (date_from, date_to, etc.)
            limit: Override page size

        Yields:
            List of records per page
        """
        params = dict(params or {})
        params["limit"] = limit or self.page_size
        cursor = None
        page_num = 0
        total_records = 0

        while True:
            if cursor:
                params["cursor"] = cursor
            elif "cursor" in params:
                del params["cursor"]

            data = self.get(path, params)
            page_num += 1

            records = data.get("data", [])
            if not records:
                break

            total_records += len(records)
            pagination = data.get("pagination", {})
            total_count = pagination.get("total_count", "?")

            logger.info(
                "  Page %d: fetched %d records (%d / %s total)",
                page_num,
                len(records),
                total_records,
                total_count,
            )
            yield records

            if not pagination.get("has_more", False):
                break

            cursor = pagination.get("cursor")
            if not cursor:
                break

        logger.info(
            "Finished %s: %d records in %d pages", path, total_records, page_num
        )

    def fetch_all(
        self,
        path: str,
        params: Optional[dict] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """Fetch all pages and return flat list of records."""
        result = []
        for page in self.get_all_pages(path, params, limit):
            result.extend(page)
        return result

    # ── Connection Test ────────────────────────────────────────

    def test_connection(self) -> dict:
        """Test API connectivity: obtain token and fetch branches.

        Returns:
            dict with status info
        """
        try:
            self._ensure_token()
            token_ok = True
        except AuthError as e:
            return {"success": False, "error": f"Auth failed: {e}"}

        try:
            branches = self.get("/branches")
            branch_count = len(branches.get("data", []))
            branch_names = [b.get("name", "?") for b in branches.get("data", [])]
        except APIError as e:
            return {
                "success": token_ok,
                "token": "OK",
                "error": f"API request failed: {e}",
            }

        return {
            "success": True,
            "token": "OK",
            "branches": branch_count,
            "branch_names": branch_names,
        }


# ── Sync State Management ─────────────────────────────────────


def load_sync_state() -> dict:
    """Load last sync timestamps from disk."""
    path = Path(SYNC_STATE_FILE)
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return {}


def save_sync_state(state: dict) -> None:
    """Persist sync state to disk."""
    path = Path(SYNC_STATE_FILE)
    with open(path, "w") as f:
        json.dump(state, f, indent=2, default=str)
    logger.debug("Sync state saved to %s", path)


def get_last_sync(endpoint: str) -> Optional[str]:
    """Get last successful sync timestamp for an endpoint."""
    state = load_sync_state()
    return state.get(endpoint)


def update_last_sync(endpoint: str, timestamp: Optional[str] = None) -> None:
    """Update last sync timestamp for an endpoint."""
    state = load_sync_state()
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    state[endpoint] = timestamp
    save_sync_state(state)
