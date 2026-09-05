"""MCP proxy: pending until approve, then execute once."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from actgate.cli import main
from actgate.core.ledger import Ledger
from actgate.core.mcp_rpc import read_message, write_message
from actgate.core.verify import verify_ledger


FAKE = Path(__file__).resolve().parent / "fake_mcp_upstream.py"


def _rpc(proc: subprocess.Popen[bytes], method: str, params: dict | None, req_id: int) -> dict:
    assert proc.stdin and proc.stdout
    msg: dict = {"jsonrpc": "2.0", "method": method, "id": req_id}
    if params is not None:
        msg["params"] = params
    write_message(proc.stdin, msg)
    reply = read_message(proc.stdout)
    assert reply is not None
    return reply


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ACTGATE_SEAL_KEY", raising=False)
    assert main(["init"]) == 0
    return tmp_path


def test_tools_call_pending_then_approve_executes_once(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = root / "fake_calls.txt"
    monkeypatch.setenv("ACTGATE_FAKE_CALLS", str(calls))
    upstream = [sys.executable, str(FAKE)]
    proc = subprocess.Popen(
        [sys.executable, "-m", "actgate", "mcp", "--upstream", *upstream],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=root,
        bufsize=0,
    )
    try:
        init = _rpc(
            proc,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
            1,
        )
        assert "result" in init
        listed = _rpc(proc, "tools/list", {}, 2)
        assert listed["result"]["tools"][0]["name"] == "echo"

        pending = _rpc(proc, "tools/call", {"name": "echo", "arguments": {"text": "hi"}}, 3)
        body = pending["result"]
        assert body.get("isError") is True
        assert "ACTGATE_PENDING" in body["content"][0]["text"]
        intent_id = body["_actgate"]["intent_id"]

        # Upstream must not have been called yet: ledger has propose only
        entries = Ledger.open(root=root).read_entries()
        assert [e["action"] for e in entries] == ["propose"]

        assert main(["approve", intent_id]) == 0

        done = _rpc(proc, "tools/call", {"name": "echo", "arguments": {"text": "hi"}}, 4)
        assert done["result"]["content"][0]["text"] == "echo:hi"
        assert done["result"].get("isError") is False

        again = _rpc(proc, "tools/call", {"name": "echo", "arguments": {"text": "hi"}}, 5)
        assert again["result"].get("isError") is True
        assert "ACTGATE_ALREADY_EXECUTED" in again["result"]["content"][0]["text"]

        actions = [e["action"] for e in Ledger.open(root=root).read_entries()]
        assert actions.count("execute") == 1
        assert calls.read_text(encoding="utf-8") == "1"
        assert verify_ledger(Ledger.open(root=root)).ok
    finally:
        proc.terminate()
        proc.wait(timeout=3)


def test_unapproved_never_hits_upstream(root: Path) -> None:
    upstream = [sys.executable, str(FAKE)]
    proc = subprocess.Popen(
        [sys.executable, "-m", "actgate", "mcp", "--upstream", *upstream],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=root,
        bufsize=0,
    )
    try:
        _rpc(
            proc,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
            1,
        )
        pending = _rpc(proc, "tools/call", {"name": "echo", "arguments": {"text": "x"}}, 2)
        iid = pending["result"]["_actgate"]["intent_id"]
        assert main(["deny", iid, "--reason", "nope"]) == 1
        denied = _rpc(proc, "tools/call", {"name": "echo", "arguments": {"text": "x"}}, 3)
        assert denied["result"].get("isError") is True
        assert "ACTGATE_DENIED" in denied["result"]["content"][0]["text"]
        actions = [e["action"] for e in Ledger.open(root=root).read_entries()]
        assert "execute" not in actions
    finally:
        proc.terminate()
        proc.wait(timeout=3)


def test_approval_does_not_cover_different_args(root: Path) -> None:
    upstream = [sys.executable, str(FAKE)]
    proc = subprocess.Popen(
        [sys.executable, "-m", "actgate", "mcp", "--upstream", *upstream],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=root,
        bufsize=0,
    )
    try:
        _rpc(
            proc,
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
            1,
        )
        pending = _rpc(proc, "tools/call", {"name": "echo", "arguments": {"text": "hi"}}, 2)
        iid = pending["result"]["_actgate"]["intent_id"]
        assert main(["approve", iid]) == 0

        other = _rpc(proc, "tools/call", {"name": "echo", "arguments": {"text": "bye"}}, 3)
        assert other["result"].get("isError") is True
        assert "ACTGATE_PENDING" in other["result"]["content"][0]["text"]
        assert other["result"]["_actgate"]["intent_id"] != iid

        other_tool = _rpc(proc, "tools/call", {"name": "other", "arguments": {"text": "hi"}}, 4)
        assert other_tool["result"].get("isError") is True
        assert "ACTGATE_PENDING" in other_tool["result"]["content"][0]["text"]

        actions = [e["action"] for e in Ledger.open(root=root).read_entries()]
        assert "execute" not in actions
    finally:
        proc.terminate()
        proc.wait(timeout=3)
