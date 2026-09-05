"""MCP stdio proxy gated by IntentLedger."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from actgate.core.intent import Intent, build_intent, hash_args
from actgate.core.ledger import Ledger
from actgate.core.mcp_rpc import RpcError, read_message, write_message


def _args_match(intent: dict[str, Any], tool: str, arguments: dict[str, Any] | None) -> bool:
    if intent.get("tool") != tool:
        return False
    args = intent.get("args")
    if args is not None:
        return args == (arguments or {})
    args_hash = intent.get("args_hash")
    if args_hash and arguments is not None:
        return args_hash == hash_args(arguments)
    return arguments in (None, {})


def _find_proposal(ledger: Ledger, tool: str, arguments: dict[str, Any] | None) -> dict[str, Any] | None:
    for entry in ledger.read_entries():
        if entry.get("action") != "propose":
            continue
        intent = entry.get("intent") or {}
        if _args_match(intent, tool, arguments):
            return entry
    return None


def _was_executed(ledger: Ledger, intent_id: str) -> bool:
    for entry in ledger.read_entries():
        if entry.get("intent_id") == intent_id and entry.get("action") == "execute":
            return True
    return False


def _pending_result(intent_id: str) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": f"ACTGATE_PENDING intent_id={intent_id}",
            }
        ],
        "isError": True,
        "_actgate": {"status": "pending", "intent_id": intent_id},
    }


def _denied_result(intent_id: str, reason: str | None) -> dict[str, Any]:
    why = reason or "denied"
    return {
        "content": [{"type": "text", "text": f"ACTGATE_DENIED intent_id={intent_id}: {why}"}],
        "isError": True,
        "_actgate": {"status": "denied", "intent_id": intent_id},
    }


class McpProxy:
    def __init__(self, ledger: Ledger, upstream_cmd: list[str]) -> None:
        self.ledger = ledger
        self.upstream_cmd = upstream_cmd
        self._proc: subprocess.Popen[bytes] | None = None
        self._client_in = sys.stdin.buffer
        self._client_out = sys.stdout.buffer

    def start_upstream(self) -> None:
        self._proc = subprocess.Popen(
            self.upstream_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            bufsize=0,
        )

    def close(self) -> None:
        if self._proc is None:
            return
        if self._proc.stdin:
            self._proc.stdin.close()
        self._proc.terminate()
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc = None

    def _upstream_request(self, method: str, params: dict[str, Any] | None, req_id: Any) -> dict[str, Any]:
        assert self._proc and self._proc.stdin and self._proc.stdout
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "id": req_id}
        if params is not None:
            msg["params"] = params
        write_message(self._proc.stdin, msg)
        reply = read_message(self._proc.stdout)
        if reply is None:
            raise RpcError("upstream closed")
        return reply

    def _upstream_notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        assert self._proc and self._proc.stdin
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        write_message(self._proc.stdin, msg)

    def _handle_tools_call(self, req_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        tool = params.get("name") or ""
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": "arguments must be an object"},
            }

        self.ledger.ensure()
        proposal = _find_proposal(self.ledger, tool, arguments)
        if proposal is None:
            intent = build_intent(tool=tool, args=arguments, requested_mode="execute")
            self.ledger.append("propose", intent=intent)
            return {"jsonrpc": "2.0", "id": req_id, "result": _pending_result(intent.id)}

        intent_id = proposal["intent_id"]
        decision = self.ledger.latest_decision(intent_id)
        if decision is None:
            return {"jsonrpc": "2.0", "id": req_id, "result": _pending_result(intent_id)}
        if decision.get("action") == "deny":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": _denied_result(intent_id, decision.get("reason")),
            }
        if _was_executed(self.ledger, intent_id):
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"ACTGATE_ALREADY_EXECUTED intent_id={intent_id}",
                        }
                    ],
                    "isError": True,
                    "_actgate": {"status": "already_executed", "intent_id": intent_id},
                },
            }

        # Record execute before upstream so a crash after success cannot double-call.
        intent_obj = Intent.from_dict(proposal["intent"])
        self.ledger.append("execute", intent=intent_obj, outcome="started")
        upstream = self._upstream_request("tools/call", params, req_id)
        return upstream

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one client message. Returns response or None for notifications."""
        if "method" not in message:
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {"code": -32600, "message": "invalid request"},
            }
        method = message["method"]
        req_id = message.get("id")
        params = message.get("params") or {}
        if not isinstance(params, dict):
            params = {}

        # notifications (no id)
        if req_id is None:
            if method == "notifications/initialized":
                self._upstream_notify(method, params or None)
            return None

        if method == "tools/call":
            return self._handle_tools_call(req_id, params)

        # forward initialize, tools/list, ping, etc.
        return self._upstream_request(method, params if params else None, req_id)

    def run(self) -> int:
        self.ledger.ensure()
        self.start_upstream()
        try:
            while True:
                msg = read_message(self._client_in)
                if msg is None:
                    return 0
                try:
                    reply = self.handle(msg)
                except RpcError as exc:
                    if "id" in msg:
                        write_message(
                            self._client_out,
                            {
                                "jsonrpc": "2.0",
                                "id": msg.get("id"),
                                "error": {"code": -32000, "message": str(exc)},
                            },
                        )
                    return 1
                if reply is not None:
                    write_message(self._client_out, reply)
        finally:
            self.close()


def run_proxy(root: Path, upstream_cmd: list[str], ledger_path: Path | str | None = None) -> int:
    ledger = Ledger.open(root=root, path=ledger_path)
    return McpProxy(ledger, upstream_cmd).run()
