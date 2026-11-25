#!/usr/bin/env python3
"""Reverse proxy for Claude Code to the Zhipu GLM Anthropic API."""

from __future__ import annotations

import json
import logging
import os
import ssl
from http.client import HTTPSConnection, HTTPResponse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


HOST = os.environ.get("GLM_PROXY_HOST", "0.0.0.0")
PORT = int(os.environ.get("GLM_PROXY_PORT", "18768"))
UPSTREAM = os.environ.get("GLM_ANTHROPIC_UPSTREAM", "https://open.bigmodel.cn/api/anthropic").rstrip("/")
REQUEST_TIMEOUT = int(os.environ.get("GLM_PROXY_TIMEOUT_SECONDS", "3600"))
LOG_LEVEL = os.environ.get("GLM_PROXY_LOG_LEVEL", "INFO").upper()

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("glm-anthropic-proxy")


def load_api_key() -> str:
    value = os.environ.get("GLM_API_KEY")
    if value:
        return value
    settings_path = Path.home() / ".claude" / "settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        value = settings.get("env", {}).get("ANTHROPIC_AUTH_TOKEN", "")
        if value:
            return value
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("could not read Claude settings for GLM API key: %s", exc)
    raise RuntimeError("GLM_API_KEY is not set and no Claude GLM token was found")


API_KEY = load_api_key()
UPSTREAM_URL = urlsplit(UPSTREAM)
UPSTREAM_PREFIX = UPSTREAM_URL.path.rstrip("/")
SSL_CONTEXT = ssl.create_default_context()


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "glm-anthropic-proxy/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        log.info("%s %s", self.client_address[0], fmt % args)

    def _read_body(self) -> bytes:
        length = self.headers.get("Content-Length")
        if length is not None:
            return self.rfile.read(int(length))
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            chunks = []
            while True:
                size_line = self.rfile.readline(65537).strip()
                size = int(size_line.split(b";", 1)[0], 16)
                if size == 0:
                    while True:
                        trailer = self.rfile.readline(65537)
                        if trailer in (b"\r\n", b"\n", b""):
                            break
                    break
                chunks.append(self.rfile.read(size))
                self.rfile.read(2)
            return b"".join(chunks)
        return b""

    def _send_json(self, status: int, value: dict) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)
        self.close_connection = True

    def _request_headers(self, payload: bytes) -> dict[str, str]:
        headers = {
            "Host": UPSTREAM_URL.netloc,
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": self.headers.get("Content-Type", "application/json"),
            "Content-Length": str(len(payload)),
            "Connection": "close",
            "Accept-Encoding": "identity",
        }
        for name in ("accept", "anthropic-version", "anthropic-beta", "user-agent"):
            value = self.headers.get(name)
            if value:
                headers[name] = value
        return headers

    def _copy_response_headers(self, response: HTTPResponse) -> None:
        for name in ("Content-Type", "Cache-Control", "X-Request-Id", "Anthropic-Version"):
            value = response.getheader(name)
            if value:
                self.send_header(name, value)
        self.send_header("Connection", "close")

    def _stream_upstream(self, response: HTTPResponse) -> None:
        while True:
            chunk = response.read1(65536)
            if not chunk:
                break
            self.wfile.write(chunk)
            self.wfile.flush()

    def _proxy(self) -> None:
        if self.path.split("?", 1)[0] == "/health":
            self._send_json(200, {"status": "ok"})
            return
        payload = self._read_body()
        target = UPSTREAM_PREFIX + self.path
        connection = HTTPSConnection(UPSTREAM_URL.netloc, timeout=REQUEST_TIMEOUT, context=SSL_CONTEXT)
        response = None
        response_started = False
        try:
            connection.request(self.command, target, body=payload, headers=self._request_headers(payload))
            response = connection.getresponse()
            response_started = True
            self.send_response(response.status)
            self._copy_response_headers(response)
            self.end_headers()
            self._stream_upstream(response)
            self.close_connection = True
        except (OSError, ssl.SSLError) as exc:
            log.error("upstream failed: %s", exc)
            if not response_started:
                self._send_json(502, {"error": {"type": "api_error", "message": f"GLM upstream failed: {exc}"}})
            self.close_connection = True
        finally:
            if response is not None:
                response.close()
            connection.close()

    def do_GET(self) -> None:
        self._proxy()

    def do_POST(self) -> None:
        self._proxy()

    def do_PUT(self) -> None:
        self._proxy()

    def do_PATCH(self) -> None:
        self._proxy()

    def do_DELETE(self) -> None:
        self._proxy()

    def do_HEAD(self) -> None:
        self._proxy()

    def do_OPTIONS(self) -> None:
        self._proxy()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    server = Server((HOST, PORT), ProxyHandler)
    log.info("listening on http://%s:%d; upstream %s", HOST, PORT, UPSTREAM)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
