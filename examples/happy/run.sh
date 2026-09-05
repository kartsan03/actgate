#!/usr/bin/env bash
set -euo pipefail
ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT
cd "$ROOT"
actgate init
OUT=$(actgate propose --tool shell.exec --args '{"cmd":"ls"}' --blast-tags fs.read)
IID=$(python -c 'import json,sys; print(json.load(sys.stdin)["intent_id"])' <<<"$OUT")
actgate dry-run "$IID"
actgate approve "$IID"
actgate verify
actgate list
echo "happy path ok"
