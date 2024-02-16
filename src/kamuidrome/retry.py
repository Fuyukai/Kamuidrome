import random
from collections.abc import Iterable, Mapping
from time import sleep
from typing import override

import httpx


# https://github.com/encode/httpx/issues/108
class RetryTransport(httpx.BaseTransport):  # noqa: D101
    RETRYABLE_METHODS = frozenset(["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"])
    RETRYABLE_STATUS_CODES = frozenset([413, 429, 503, 504])

    MAX_BACKOFF_WAIT = 60

    def __init__(
        self,
        wrapped_transport: httpx.BaseTransport,
        max_attempts: int = 10,
        max_backoff_wait: float = MAX_BACKOFF_WAIT,
        backoff_factor: float = 0.1,
        jitter_ratio: float = 0.1,
        respect_retry_after_header: bool = True,
        retryable_methods: Iterable[str] | None = None,
        retry_status_codes: Iterable[int] | None = None,
    ) -> None:
        self.wrapped_transport = wrapped_transport
        if jitter_ratio < 0 or jitter_ratio > 0.5:
            raise ValueError(f"jitter ratio should be between 0 and 0.5, actual {jitter_ratio}")

        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.respect_retry_after_header = respect_retry_after_header
        self.retryable_methods = (
            frozenset(retryable_methods) if retryable_methods else self.RETRYABLE_METHODS
        )
        self.retry_status_codes = (
            frozenset(retry_status_codes) if retry_status_codes else self.RETRYABLE_STATUS_CODES
        )
        self.jitter_ratio = jitter_ratio
        self.max_backoff_wait = max_backoff_wait

    def _calculate_sleep(
        self, attempts_made: int, headers: httpx.Headers | Mapping[str, str]
    ) -> float:
        backoff = self.backoff_factor * (2 ** (attempts_made - 1))
        jitter = (backoff * self.jitter_ratio) * random.choice([1, -1])
        total_backoff = backoff + jitter
        return min(total_backoff, self.max_backoff_wait)

    @override
    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.wrapped_transport.handle_request(request)

        if request.method not in self.retryable_methods:
            return response

        remaining_attempts = self.max_attempts - 1
        attempts_made = 1

        while True:
            if remaining_attempts < 1 or response.status_code not in self.retry_status_codes:
                return response

            response.close()

            sleep_for = self._calculate_sleep(attempts_made, response.headers)
            sleep(sleep_for)

            response = self.wrapped_transport.handle_request(request)

            attempts_made += 1
            remaining_attempts -= 1
