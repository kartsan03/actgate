"""Minimal MCP/JSON-RPC stdio framing (Content-Length)."""

from __future__ import annotations

import json
import sys
from typing import Any, BinaryIO, TextIO


class RpcError(RuntimeError):
    """Transport or protocol failure."""


def write_message(stream: BinaryIO, message: dict[str, Any]) -> None:
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    stream.write(header)
    stream.write(body)
    stream.flush()


def read_message(stream: BinaryIO) -> dict[str, Any] | None:
    """Read one framed message. Returns None on clean EOF before a header."""
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            if not headers:
                return None
            raise RpcError("unexpected EOF in headers")
        if line in (b"\r\n", b"\n"):
            break
        try:
            text = line.decode("ascii").rstrip("\r\n")
        except UnicodeDecodeError as exc:
            raise RpcError(f"invalid header encoding: {exc}") from exc
        if ":" not in text:
            raise RpcError(f"malformed header: {text!r}")
        key, value = text.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    if "content-length" not in headers:
        raise RpcError("missing Content-Length")
    length = int(headers["content-length"])
    body = stream.read(length)
    if len(body) != length:
        raise RpcError("unexpected EOF in body")
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RpcError(f"invalid JSON body: {exc}") from exc


def write_text_line(stream: TextIO, text: str) -> None:
    stream.write(text)
    if not text.endswith("\n"):
        stream.write("\n")
    stream.flush()
