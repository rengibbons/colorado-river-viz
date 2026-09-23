import pytest
import requests
from pydantic import SecretStr

from colorado_river_viz.errors import SourceUnavailableError
from colorado_river_viz.http_session import DataSource, build_client, get_json
from colorado_river_viz.settings import Settings
from tests.conftest import ScriptedResponse, ScriptedServer


def test_retries_transient_failures_then_succeeds(
    scripted_server: ScriptedServer, fast_settings: Settings
) -> None:
    scripted_server.script = [
        ScriptedResponse(status=503),
        ScriptedResponse(status=429),
        ScriptedResponse(body={"ok": True}),
    ]
    client = build_client(DataSource.RISE, fast_settings)

    assert get_json(client, f"{scripted_server.base_url}/data") == {"ok": True}
    assert len(scripted_server.received) == 3


def test_raises_source_unavailable_when_every_retry_fails(
    scripted_server: ScriptedServer, fast_settings: Settings
) -> None:
    scripted_server.script = [ScriptedResponse(status=503)]
    client = build_client(DataSource.RISE, fast_settings)

    with pytest.raises(SourceUnavailableError):
        get_json(client, f"{scripted_server.base_url}/data")
    assert len(scripted_server.received) == fast_settings.max_retries + 1


def test_retries_read_timeouts(scripted_server: ScriptedServer) -> None:
    settings = Settings(
        request_timeout_seconds=0.2, max_retries=1, retry_backoff_factor=0.0
    )
    scripted_server.script = [ScriptedResponse(body={}, delay_seconds=1.0)]
    client = build_client(DataSource.RISE, settings)

    with pytest.raises(SourceUnavailableError):
        get_json(client, f"{scripted_server.base_url}/slow")
    assert len(scripted_server.received) == 2


def test_client_errors_are_not_retried(
    scripted_server: ScriptedServer, fast_settings: Settings
) -> None:
    scripted_server.script = [ScriptedResponse(status=404)]
    client = build_client(DataSource.RISE, fast_settings)

    with pytest.raises(requests.HTTPError):
        get_json(client, f"{scripted_server.base_url}/missing")
    assert len(scripted_server.received) == 1


@pytest.mark.parametrize(
    ("source", "sends_key"),
    [
        (DataSource.USGS, True),
        (DataSource.RISE, False),
        (DataSource.SNOTEL, False),
        (DataSource.PUBLISHED, False),
    ],
)
def test_usgs_api_key_is_sent_only_to_usgs(
    scripted_server: ScriptedServer,
    fast_settings: Settings,
    source: DataSource,
    sends_key: bool,
) -> None:
    settings = fast_settings.model_copy(update={"usgs_api_key": SecretStr("k3y")})
    scripted_server.script = [ScriptedResponse(body={})]

    get_json(build_client(source, settings), f"{scripted_server.base_url}/x")

    headers = scripted_server.received[0].headers
    assert (headers.get("X-Api-Key") == "k3y") is sends_key
