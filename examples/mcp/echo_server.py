"""One-tool MCP stdio server used by the demo and by CI.

Echoes the `text` argument. Counts `tools/call` in ACTGATE_DEMO_CALLS when set,
so a test can prove the first call never reached this process.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any


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
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, value = line.decode("ascii").rstrip("\r\n").split(":", 1)
        headers[key.strip().lower()] = value.strip()
    length = int(headers["content-length"])
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))


TOOLS = [
    {
        "name": "echo",
        "description": "Return the text it was given.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    }
]


def _note_call() -> None:
    path = os.environ.get("ACTGATE_DEMO_CALLS")
    if not path:
        return
    count = 0
    if os.path.exists(path):
        raw = open(path, encoding="utf-8").read().strip()
        count = int(raw) if raw else 0
    open(path, "w", encoding="utf-8").write(str(count + 1))


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
                        "serverInfo": {"name": "actgate-echo", "version": "0.3.0"},
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
                        "error": {"code": -32602, "message": f"unknown tool {name}"},
                    }
                )
                continue
            _note_call()
            text = arguments.get("text", "")
            write_message(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": text}],
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
