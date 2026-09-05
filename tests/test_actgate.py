"""ActGate MVP tests: propose/approve/deny/verify/path escapes."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from actgate.cli import main
from actgate.core.intent import IntentError, build_intent, hash_args
from actgate.core.ledger import GENESIS, Ledger, LedgerError, resolve_ledger_path
from actgate.core.verify import verify_ledger


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ACTGATE_SEAL_KEY", raising=False)
    assert main(["init"]) == 0
    return tmp_path


def test_propose_approve_verify(root: Path) -> None:
    rc = main(["propose", "--tool", "shell.exec", "--args", '{"cmd":"ls"}', "--blast-tags", "fs.read"])
    assert rc == 0
    ledger = Ledger.open(root=root)
    proposal = [e for e in ledger.read_entries() if e["action"] == "propose"][0]
    iid = proposal["intent_id"]
    assert main(["dry-run", iid]) == 0
    assert main(["approve", iid]) == 0
    assert main(["verify"]) == 0
    assert main(["show", iid]) == 0
    assert main(["list"]) == 0
    entries = ledger.read_entries()
    assert entries[0]["prev_hash"] == GENESIS
    assert entries[1]["prev_hash"] == entries[0]["entry_hash"]


def test_deny_exits_one(root: Path) -> None:
    assert main(["propose", "--tool", "fs.write", "--args", '{"path":"/tmp/x"}']) == 0
    iid = Ledger.open(root=root).read_entries()[0]["intent_id"]
    assert main(["deny", iid, "--reason", "too broad"]) == 1
    assert main(["verify"]) == 0
    decision = Ledger.open(root=root).latest_decision(iid)
    assert decision is not None
    assert decision["action"] == "deny"


def test_broken_chain_verify_fails(root: Path) -> None:
    assert main(["propose", "--tool", "t", "--args", "{}"]) == 0
    ledger = Ledger.open(root=root)
    path = ledger.path
    lines = path.read_text().splitlines()
    entry = json.loads(lines[0])
    entry["entry_hash"] = "deadbeef" * 8
    path.write_text(json.dumps(entry, sort_keys=True) + "\n")
    assert main(["verify"]) == 1


def test_hmac_seal(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACTGATE_SEAL_KEY", "secret-test-key")
    assert main(["propose", "--tool", "t", "--args", '{"a":1}']) == 0
    entry = Ledger.open(root=root).read_entries()[0]
    assert "seal" in entry
    assert main(["verify"]) == 0
    # tamper seal
    path = Ledger.open(root=root).path
    entry["seal"] = "00" * 32
    path.write_text(json.dumps(entry, sort_keys=True) + "\n")
    assert main(["verify"]) == 1


def test_path_escape_rejected(root: Path) -> None:
    with pytest.raises(LedgerError, match="path escapes"):
        resolve_ledger_path(root=root, path="/etc/passwd")
    # CLI path escape
    assert main(["--ledger", "/tmp/evil.jsonl", "verify"]) == 2


def test_args_hash_only(root: Path) -> None:
    h = hash_args({"cmd": "echo"})
    assert main(["propose", "--tool", "shell.exec", "--args-hash", h]) == 0
    intent = Ledger.open(root=root).read_entries()[0]["intent"]
    assert intent["args"] is None
    assert intent["args_hash"] == h


def test_build_intent_validation() -> None:
    with pytest.raises(IntentError):
        build_intent(tool="", args={})
    with pytest.raises(IntentError):
        build_intent(tool="t")
    with pytest.raises(IntentError):
        build_intent(tool="t", args={"a": 1}, args_hash="nope")


def test_missing_ledger_setup_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["verify"]) == 2
    assert main(["list"]) == 2


def test_double_decision_setup_error(root: Path) -> None:
    assert main(["propose", "--tool", "t", "--args", "{}"]) == 0
    iid = Ledger.open(root=root).read_entries()[0]["intent_id"]
    assert main(["approve", iid]) == 0
    assert main(["deny", iid]) == 2


def test_forged_consistent_chain_verifies_without_seal(root: Path) -> None:
    """Without ACTGATE_SEAL_KEY, verify is integrity-only (not authenticity)."""
    from actgate.core.ledger import compute_entry_hash

    assert main(["propose", "--tool", "shell.exec", "--args", '{"cmd":"ls"}']) == 0
    iid = Ledger.open(root=root).read_entries()[0]["intent_id"]
    assert main(["approve", iid]) == 0
    ledger = Ledger.open(root=root)
    propose, approve = ledger.read_entries()
    intent = dict(propose["intent"])
    intent["tool"] = "forged.exec"
    forged_propose = {
        "seq": 1,
        "action": "propose",
        "intent_id": iid,
        "intent": intent,
        "prev_hash": GENESIS,
        "created_at": propose.get("ts", propose.get("created_at")),
    }
    forged_propose["entry_hash"] = compute_entry_hash(forged_propose)
    forged_approve = {
        "seq": 2,
        "action": "approve",
        "intent_id": iid,
        "intent": intent,
        "decision": "approved",
        "reason": approve.get("reason"),
        "prev_hash": forged_propose["entry_hash"],
        "created_at": approve.get("ts", approve.get("created_at")),
    }
    forged_approve["entry_hash"] = compute_entry_hash(forged_approve)
    ledger.path.write_text(
        json.dumps(forged_propose, sort_keys=True)
        + "\n"
        + json.dumps(forged_approve, sort_keys=True)
        + "\n"
    )
    assert main(["verify"]) == 0
    assert verify_ledger(ledger).ok
    assert main(["verify", "--require-seal"]) == 1
