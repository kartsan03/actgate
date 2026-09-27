#!/usr/bin/env bash
# One real upstream, one ledger, three identical tools/call.
# 1. pending  — upstream is not started into the tool
# 2. approve  — ledger only, still no tool
# 3. execute  — the same call reaches upstream once
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(mktemp -d)
CALLS="$ROOT/upstream_calls"
trap 'rm -rf "$ROOT"' EXIT

cd "$ROOT"
actgate init >/dev/null

python - "$HERE" "$ROOT" "$CALLS" <<'PY'
import json
import os
import subprocess
import sys

here, root, calls = sys.argv[1:]
os.environ["ACTGATE_DEMO_CALLS"] = calls
upstream = [sys.executable, os.path.join(here, "echo_server.py")]
proc = subprocess.Popen(
    [sys.executable, "-m", "actgate", "mcp", "--upstream", *upstream],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    cwd=root,
    bufsize=0,
)


def frame(message: dict) -> None:
    body = json.dumps(message, separators=(",", ":")).encode()
    assert proc.stdin is not None
    proc.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    proc.stdin.flush()


def read() -> dict:
    assert proc.stdout is not None
    headers = {}
    while True:
        line = proc.stdout.readline()
        if line in (b"\r\n", b"\n"):
            break
        key, value = line.decode("ascii").rstrip("\r\n").split(":", 1)
        headers[key.strip().lower()] = value.strip()
    n = int(headers["content-length"])
    return json.loads(proc.stdout.read(n))


def call(req_id: int) -> dict:
    frame(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"text": "ship it"}},
        }
    )
    return read()


def text_of(reply: dict) -> str:
    return reply["result"]["content"][0]["text"]


def upstream_calls() -> int:
    if not os.path.exists(calls):
        return 0
    raw = open(calls, encoding="utf-8").read().strip()
    return int(raw) if raw else 0


try:
    frame(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "actgate-demo", "version": "0"},
            },
        }
    )
    init = read()
    assert init["result"]["serverInfo"]["name"] == "actgate-echo", init

    pending = call(2)
    body = text_of(pending)
    assert body.startswith("ACTGATE_PENDING"), body
    intent_id = pending["result"]["_actgate"]["intent_id"]
    assert upstream_calls() == 0, "pending call reached upstream"

    approved = subprocess.run(
        ["actgate", "approve", intent_id, "--reason", "human"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"action": "approve"' in approved.stdout
    assert upstream_calls() == 0, "approve reached upstream"

    done = call(3)
    assert text_of(done) == "ship it", done
    assert done["result"].get("isError") is False
    assert upstream_calls() == 1, upstream_calls()

    again = call(4)
    assert "ACTGATE_ALREADY_EXECUTED" in text_of(again), again
    assert upstream_calls() == 1, "second execute reached upstream"

    verified = subprocess.run(
        ["actgate", "verify"], cwd=root, check=True, capture_output=True, text=True
    )
    assert '"ok": true' in verified.stdout
    print(f"pending {intent_id[:8]} -> approve -> execute once")
finally:
    proc.terminate()
    proc.wait(timeout=3)
PY
