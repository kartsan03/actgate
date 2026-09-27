# MCP: pending, then approve, then one execute

`echo_server.py` is a real stdio MCP server with a single `echo` tool.
`demo.sh` points `actgate mcp` at it and sends the same `tools/call` three times.

```
./examples/mcp/demo.sh
```

What it checks:

1. The first call returns `ACTGATE_PENDING`. The echo server's call counter stays at 0.
2. `actgate approve` writes the ledger and still does not call upstream.
3. The identical call returns `ship it` and the counter moves to 1.
4. A third identical call returns `ACTGATE_ALREADY_EXECUTED`. The counter stays at 1.
5. `actgate verify` exits 0.

CI runs this script on Python 3.12. The GIF in the root README is a drawing of
the same three steps, rendered from `demo/`; this script is the thing that
actually talks to a server.
