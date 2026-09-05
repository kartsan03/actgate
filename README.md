# ActGate

[![ci](https://github.com/kartsan03/actgate/actions/workflows/ci.yml/badge.svg)](https://github.com/kartsan03/actgate/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Local IntentLedger: propose a tool action, record approve or deny in an
append-only hash-chained ledger, verify the chain before you trust it.

This is not an MCP proxy yet. This is not a SaaS. Everything runs offline
against files on disk.

dry-run and approve record decisions only; they do not execute tools.

## Install

```
pip install -e .[dev]
```

## Quickstart

```
actgate init
actgate propose --tool shell.exec --args '{"cmd":"ls"}' --blast-tags fs.read
actgate dry-run <intent_id>
actgate approve <intent_id>
actgate verify
actgate list
```

Deny path:

```
actgate deny <intent_id> --reason "too broad"
# exits 1
```

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

Provide either `args` or `args_hash` (sha256 of canonical JSON args). Optional
`blast_tags` and `requested_mode`.

## Ledger

`.actgate/ledger.jsonl` is append-only. Each line has `prev_hash` / `entry_hash`
(sha256). Bare `verify` checks chain integrity only: a rewritten but
internally consistent chain still passes. It is not a signature check unless
you opt in.

Optional authenticity: set `ACTGATE_SEAL_KEY` when writing so entries get an
HMAC seal. Then `verify` (with the key set) requires matching seals, or pass
`verify --require-seal` to fail when seals are missing.

Path escapes outside the ledger root are rejected (exit 2).

## What this is not

- Not an MCP proxy (yet)
- Not a hosted approval product
- No network calls in the core path

## Development

```
pip install -e .[dev]
pytest
```
