#!/usr/bin/env bash
set -euo pipefail
ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT
cd "$ROOT"
actgate init
OUT=$(actgate propose --tool fs.write --args '{"path":"/etc/passwd"}' --blast-tags fs.write)
IID=$(python -c 'import json,sys; print(json.load(sys.stdin)["intent_id"])' <<<"$OUT")
set +e
actgate deny "$IID" --reason "path too sensitive"
RC=$?
set -e
test "$RC" -eq 1
actgate verify
echo "deny path ok"
