from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from colorado_river_viz.settings import Settings


@dataclass(frozen=True, slots=True)
class ScriptedResponse:
    status: int = 200
    body: Any = None
    delay_seconds: float = 0.0


@dataclass(frozen=True, slots=True)
class ReceivedRequest:
    path: str
    headers: dict[str, str]


@dataclass
class ScriptedServer:
    """A localhost HTTP server that replays a queue of canned responses.

    Once the queue runs out, the last response repeats.
    """

    base_url: str
    script: list[ScriptedResponse] = field(default_factory=list)
    received: list[ReceivedRequest] = field(default_factory=list)

    def next_response(self) -> ScriptedResponse:
        return self.script.pop(0) if len(self.script) > 1 else self.script[0]


def _handler_for(server: ScriptedServer) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            server.received.append(
                ReceivedRequest(path=self.path, headers=dict(self.headers.items()))
            )
            response = server.next_response()
            time.sleep(response.delay_seconds)
            payload = json.dumps(response.body).encode()
            try:
                self.send_response(response.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the client timed out and hung up, which is what some tests want

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return Handler


@pytest.fixture
def scripted_server() -> Iterator[ScriptedServer]:
    scripted = ScriptedServer(base_url="")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _handler_for(scripted))
    scripted.base_url = f"http://127.0.0.1:{httpd.server_address[1]}"
    thread = threading.Thread(
        target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    yield scripted
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def fast_settings(tmp_path: Path) -> Settings:
    """Settings with tiny timeouts and no backoff, so retry tests run quickly."""
    return Settings(
        cache_dir=tmp_path / "cache",
        request_timeout_seconds=2.0,
        max_retries=3,
        retry_backoff_factor=0.0,
    )
