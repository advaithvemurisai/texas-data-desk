"""HTTP with retries: 429/5xx and transport errors back off exponentially, honoring Retry-After."""

import logging
import time
from collections.abc import Callable, Mapping
from pathlib import Path

import httpx

from tdd_ingest import __version__

log = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
USER_AGENT = f"texas-data-desk-ingest/{__version__} (open-data research project)"


class RetryableStatusError(Exception):
    def __init__(self, response: httpx.Response) -> None:
        super().__init__(f"HTTP {response.status_code} from {response.url}")
        self.retry_after = _parse_retry_after(response.headers.get("Retry-After"))


def _parse_retry_after(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:  # HTTP-date form; fall back to our own backoff
        return None


class Http:
    def __init__(
        self,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 60.0,
        max_attempts: int = 6,
        base_wait: float = 2.0,
        max_wait: float = 120.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT, **(headers or {})},
            timeout=timeout,
            follow_redirects=True,
        )
        self.max_attempts = max_attempts
        self.base_wait = base_wait
        self.max_wait = max_wait
        self._sleep = sleep

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "Http":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(
        self,
        url: str,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        def attempt() -> httpx.Response:
            response = self.client.get(url, params=params, headers=headers)
            if response.status_code in RETRY_STATUSES:
                raise RetryableStatusError(response)
            response.raise_for_status()
            return response

        return self._with_retries(attempt)

    def download(
        self, url: str, dest: Path, headers: Mapping[str, str] | None = None
    ) -> httpx.Response:
        """Stream url to dest. Returns the (closed) final response for its headers and URL."""
        partial = dest.with_name(dest.name + ".part")

        def attempt() -> httpx.Response:
            with self.client.stream("GET", url, headers=headers) as response:
                if response.status_code in RETRY_STATUSES:
                    raise RetryableStatusError(response)
                response.raise_for_status()
                with partial.open("wb") as fh:
                    for chunk in response.iter_bytes(1 << 20):
                        fh.write(chunk)
                return response

        try:
            response = self._with_retries(attempt)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        partial.replace(dest)
        return response

    def _with_retries(self, attempt: Callable[[], httpx.Response]) -> httpx.Response:
        for n in range(1, self.max_attempts + 1):
            try:
                return attempt()
            except (RetryableStatusError, httpx.TransportError) as exc:
                if n == self.max_attempts:
                    raise
                wait = min(self.base_wait * 2 ** (n - 1), self.max_wait)
                if isinstance(exc, RetryableStatusError) and exc.retry_after is not None:
                    wait = min(exc.retry_after, self.max_wait)
                log.warning("%s; retry %d/%d in %.1fs", exc, n, self.max_attempts - 1, wait)
                self._sleep(wait)
        raise AssertionError("unreachable")
