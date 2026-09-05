# ActGate

[![ci](https://github.com/kartsan03/actgate/actions/workflows/ci.yml/badge.svg)](https://github.com/kartsan03/actgate/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Local IntentLedger and MCP stdio proxy: propose a tool action, approve or deny
in an append-only hash-chained ledger, then let an identical tools/call reach
one upstream MCP server.

This is not a SaaS. The ledger path stays on disk. dry-run and approve record
decisions only; they do not execute tools. The MCP proxy is what executes, and
only after approve.

## Install

```
pip install -e .[dev]
```

## CLI quickstart

```
actgate init
actgate propose --tool shell.exec --args '{"cmd":"ls"}' --blast-tags fs.read
actgate dry-run <intent_id>
actgate approve <intent_id>
actgate verify
actgate list
```

## MCP proxy

Point your MCP client at ActGate instead of the upstream server:

```
actgate init
actgate mcp --upstream python -m some_mcp_server
```

Flow:

1. Client `tools/list` is forwarded to upstream. Only `tools/call` is gated;
   other methods are forwarded.
2. First `tools/call` for a tool+args writes a propose event and returns
   `ACTGATE_PENDING intent_id=...` (upstream is not called).
3. Human: `actgate approve <intent_id>` (or `actgate deny <intent_id>`).
4. Identical subsequent `tools/call` (same tool and args) runs upstream once
   and appends an `execute` event. A third call returns already-executed.
5. Denied intents never hit upstream.

Bare `verify` checks hash-chain integrity only. Set `ACTGATE_SEAL_KEY` for
optional HMAC seals, or pass `verify --require-seal`.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | ok (propose, approve, verify clean, show/list) |
| 1 | deny recorded, or verify found a broken chain / bad seal |
| 2 | setup error (missing ledger, bad path, invalid args) |

## Intent shape

```json
{
  "tool": "shell.exec",
  "args": {"cmd": "ls"},
  "args_hash": null,
  "blast_tags": ["fs.read"],
  "requested_mode": "execute",
  "created_at": "2026-09-06T00:00:00+00:00"
}
```

## What this is not

- Not a hosted approval product
- Not a policy DSL
- No network calls in the ledger core path (the MCP proxy talks to a local upstream process)

## Development

```
pip install -e .[dev]
pytest
```
