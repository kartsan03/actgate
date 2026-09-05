# Contributing

## Setup

```
git clone https://github.com/kartsan03/actgate
cd actgate
pip install -e .[dev]
pytest
```

## Ground rules

- Stdlib first. No new runtime dependencies without a strong reason.
- No network in the core path (intent, ledger, verify).
- Exit code discipline: `0` = ok, `1` = deny or broken chain, `2` = setup error.
- Keep the MVP small: this is an IntentLedger, not an MCP proxy and not a SaaS.

## Pull requests

Keep them small. CI runs pytest on Python 3.10 through 3.13.
