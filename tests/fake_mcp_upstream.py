"""Minimal MCP upstream for tests: one echo tool."""

from __future__ import annotations

import json
import sys
from typing import Any

# Inline framing so the script is standalone when run as subprocess.
def write_message(message: dict[str, Any]) -> None:
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None if not headers else (_ for _ in ()).throw(RuntimeError("EOF"))
        if line in (b"\r\n", b"\n"):
            break
        text = line.decode("ascii").rstrip("\r\n")
        key, value = text.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    length = int(headers["content-length"])
    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode("utf-8"))


TOOLS = [
    {
        "name": "echo",
        "description": "Echo arguments",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    }
]


def main() -> int:
    while True:
        msg = read_message()
        if msg is None:
            return 0
        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params") or {}
        if req_id is None:
            continue
        if method == "initialize":
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "fake-upstream", "version": "0.0.1"},
                    },
                }
            )
        elif method == "tools/list":
            write_message({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments") or {}
            if name != "echo":
                write_message(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"unknown tool {name}"},
                    }
                )
            else:
                text = arguments.get("text", "")
                write_message(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": f"echo:{text}"}],
                            "isError": False,
                        },
                    }
                )
        elif method == "ping":
            write_message({"jsonrpc": "2.0", "id": req_id, "result": {}})
        else:
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"method not found: {method}"},
                }
            )


if __name__ == "__main__":
    raise SystemExit(main())
