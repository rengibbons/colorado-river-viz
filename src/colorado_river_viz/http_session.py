"""One retrying HTTP client shared by every fetcher."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from colorado_river_viz.errors import SourceUnavailableError
from colorado_river_viz.settings import Settings

RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)


class DataSource(StrEnum):
    """Where a series comes from; also the cache's per-source folder name."""

    USGS = "usgs"
    RISE = "rise"
    SNOTEL = "snotel"
    PUBLISHED = "published"


@dataclass(frozen=True, slots=True)
class HttpClient:
    """A retrying session plus the per-request timeout it should use."""

    session: requests.Session
    timeout_seconds: float


def build_client(source: DataSource, settings: Settings) -> HttpClient:
    """Build a client that retries connection errors, read timeouts, 429 and 5xx.

    Retries back off exponentially and honor ``Retry-After``. The USGS API key, if
    configured, is attached only to USGS clients so it never reaches other hosts.
    """
    retry = Retry(
        total=settings.max_retries,
        connect=settings.max_retries,
        read=settings.max_retries,
        status=settings.max_retries,
        status_forcelist=RETRYABLE_STATUS_CODES,
        allowed_methods=frozenset({"GET"}),
        backoff_factor=settings.retry_backoff_factor,
        respect_retry_after_header=True,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    if source is DataSource.USGS and settings.usgs_api_key is not None:
        session.headers["X-Api-Key"] = settings.usgs_api_key.get_secret_value()
    return HttpClient(session=session, timeout_seconds=settings.request_timeout_seconds)


def get_response(
    client: HttpClient, url: str, params: dict[str, str | int] | None = None
) -> requests.Response:
    """GET ``url``, raising ``SourceUnavailableError`` once retries are exhausted.

    Non-retryable HTTP errors (e.g. 400, 404) raise ``requests.HTTPError``
    immediately, since retrying won't fix a bad request.
    """
    try:
        response = client.session.get(
            url, params=params, timeout=client.timeout_seconds
        )
    except (
        requests.ConnectionError,
        requests.Timeout,
        requests.exceptions.RetryError,
    ) as error:
        raise SourceUnavailableError(f"{url} failed after retries: {error}") from error
    response.raise_for_status()
    return response


def get_json(
    client: HttpClient, url: str, params: dict[str, str | int] | None = None
) -> Any:
    """GET ``url`` and decode its JSON body (see ``get_response`` for errors)."""
    return get_response(client, url, params).json()
