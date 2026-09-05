"""ActGate CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from actgate import __version__
from actgate.core.intent import Intent, IntentError, build_intent
from actgate.core.ledger import Ledger, LedgerError, resolve_ledger_path
from actgate.core.verify import verify_ledger


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def _ledger_from_args(args: argparse.Namespace) -> Ledger:
    root = Path(args.root).resolve() if getattr(args, "root", None) else Path.cwd()
    path = getattr(args, "ledger", None)
    return Ledger.open(root=root, path=path)


def cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.directory).resolve() if args.directory else Path.cwd()
    ledger = Ledger.open(root=target)
    ledger.ensure()
    print(f"initialized {ledger.path}")
    return 0


def _parse_args_json(raw: str | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise IntentError(f"invalid --args JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise IntentError("--args must be a JSON object")
    return data


def cmd_propose(args: argparse.Namespace) -> int:
    try:
        intent = build_intent(
            tool=args.tool,
            args=_parse_args_json(args.args),
            args_hash=args.args_hash,
            blast_tags=[t for t in (args.blast_tags or "").split(",") if t],
            requested_mode=args.mode,
        )
        ledger = _ledger_from_args(args)
        if not ledger.exists():
            ledger.ensure()
        entry = ledger.append("propose", intent=intent)
    except (IntentError, LedgerError) as exc:
        _eprint(str(exc))
        return 2
    print(json.dumps({"intent_id": intent.id, "entry_hash": entry["entry_hash"]}, indent=2))
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    try:
        ledger = _ledger_from_args(args)
        if not ledger.exists():
            raise LedgerError(f"ledger not found: {ledger.path}")
        proposal = ledger.get_proposal(args.intent_id)
        if proposal is None:
            raise LedgerError(f"no propose event for intent_id={args.intent_id}")
        decision = ledger.latest_decision(args.intent_id)
    except LedgerError as exc:
        _eprint(str(exc))
        return 2
    out = {
        "intent_id": args.intent_id,
        "intent": proposal.get("intent"),
        "decision": None if decision is None else decision.get("action"),
        "would_execute": decision is not None and decision.get("action") == "approve",
    }
    print(json.dumps(out, indent=2))
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    try:
        ledger = _ledger_from_args(args)
        if not ledger.exists():
            raise LedgerError(f"ledger not found: {ledger.path}")
        proposal = ledger.get_proposal(args.intent_id)
        if proposal is None:
            raise LedgerError(f"no propose event for intent_id={args.intent_id}")
        intent = Intent.from_dict(proposal["intent"])
        existing = ledger.latest_decision(args.intent_id)
        if existing is not None:
            raise LedgerError(
                f"intent already decided: {existing.get('action')} ({existing.get('entry_hash')})"
            )
        entry = ledger.append(
            "approve",
            intent=intent,
            decision="approved",
            reason=args.reason,
        )
    except (IntentError, LedgerError) as exc:
        _eprint(str(exc))
        return 2
    print(json.dumps({"intent_id": intent.id, "action": "approve", "entry_hash": entry["entry_hash"]}, indent=2))
    return 0


def cmd_deny(args: argparse.Namespace) -> int:
    try:
        ledger = _ledger_from_args(args)
        if not ledger.exists():
            raise LedgerError(f"ledger not found: {ledger.path}")
        proposal = ledger.get_proposal(args.intent_id)
        if proposal is None:
            raise LedgerError(f"no propose event for intent_id={args.intent_id}")
        intent = Intent.from_dict(proposal["intent"])
        existing = ledger.latest_decision(args.intent_id)
        if existing is not None:
            raise LedgerError(
                f"intent already decided: {existing.get('action')} ({existing.get('entry_hash')})"
            )
        entry = ledger.append(
            "deny",
            intent=intent,
            decision="denied",
            reason=args.reason or "denied",
        )
    except (IntentError, LedgerError) as exc:
        _eprint(str(exc))
        return 2
    print(json.dumps({"intent_id": intent.id, "action": "deny", "entry_hash": entry["entry_hash"]}, indent=2))
    return 1


def cmd_verify(args: argparse.Namespace) -> int:
    try:
        ledger = _ledger_from_args(args)
        if not ledger.exists():
            raise LedgerError(f"ledger not found: {ledger.path}")
        result = verify_ledger(
            ledger, require_seal=True if getattr(args, "require_seal", False) else None
        )
    except LedgerError as exc:
        _eprint(str(exc))
        return 2
    if result.ok:
        print(json.dumps({"ok": True, "entries": result.entries}, indent=2))
        return 0
    _eprint("verify failed:")
    for err in result.errors:
        _eprint(f"  - {err}")
    return 1


def cmd_show(args: argparse.Namespace) -> int:
    try:
        ledger = _ledger_from_args(args)
        if not ledger.exists():
            raise LedgerError(f"ledger not found: {ledger.path}")
        events = ledger.find_intent_events(args.intent_id)
        if not events:
            raise LedgerError(f"unknown intent_id={args.intent_id}")
    except LedgerError as exc:
        _eprint(str(exc))
        return 2
    print(json.dumps({"intent_id": args.intent_id, "events": events}, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    try:
        ledger = _ledger_from_args(args)
        if not ledger.exists():
            raise LedgerError(f"ledger not found: {ledger.path}")
        seen: dict[str, dict[str, Any]] = {}
        for entry in ledger.read_entries():
            iid = entry.get("intent_id")
            if not iid:
                continue
            row = seen.setdefault(
                iid,
                {"intent_id": iid, "tool": None, "status": "proposed", "seq": entry["seq"]},
            )
            if entry.get("action") == "propose":
                intent = entry.get("intent") or {}
                row["tool"] = intent.get("tool")
                row["seq"] = entry["seq"]
            elif entry.get("action") in ("approve", "deny"):
                row["status"] = "approved" if entry["action"] == "approve" else "denied"
    except LedgerError as exc:
        _eprint(str(exc))
        return 2
    rows = sorted(seen.values(), key=lambda r: r["seq"])
    print(json.dumps(rows, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="actgate",
        description="Local IntentLedger: propose, approve, deny, verify tool intents.",
    )
    parser.add_argument("--version", action="version", version=f"actgate {__version__}")
    parser.add_argument("--root", default=None, help="project root containing .actgate/")
    parser.add_argument("--ledger", default=None, help="explicit ledger.jsonl path (must stay under root)")

    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create .actgate/ledger.jsonl")
    p_init.add_argument("directory", nargs="?", default=None)
    p_init.set_defaults(func=cmd_init)

    p_prop = sub.add_parser("propose", help="append a propose event")
    p_prop.add_argument("--tool", required=True)
    p_prop.add_argument("--args", default=None, help="JSON object of tool args")
    p_prop.add_argument("--args-hash", dest="args_hash", default=None)
    p_prop.add_argument("--blast-tags", dest="blast_tags", default="", help="comma-separated tags")
    p_prop.add_argument("--mode", dest="mode", default="execute", help="requested_mode")
    p_prop.set_defaults(func=cmd_propose)

    p_dry = sub.add_parser("dry-run", help="show intent and whether it would execute")
    p_dry.add_argument("intent_id")
    p_dry.set_defaults(func=cmd_dry_run)

    p_ok = sub.add_parser("approve", help="append an approve event")
    p_ok.add_argument("intent_id")
    p_ok.add_argument("--reason", default=None)
    p_ok.set_defaults(func=cmd_approve)

    p_no = sub.add_parser("deny", help="append a deny event (exit 1)")
    p_no.add_argument("intent_id")
    p_no.add_argument("--reason", default=None)
    p_no.set_defaults(func=cmd_deny)

    p_ver = sub.add_parser("verify", help="verify ledger hash chain (exit 0/1/2)")
    p_ver.add_argument(
        "--require-seal",
        action="store_true",
        help="fail if entries lack HMAC seals (use with ACTGATE_SEAL_KEY)",
    )
    p_ver.set_defaults(func=cmd_verify)

    p_show = sub.add_parser("show", help="show events for an intent")
    p_show.add_argument("intent_id")
    p_show.set_defaults(func=cmd_show)

    p_list = sub.add_parser("list", help="list intents and status")
    p_list.set_defaults(func=cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except LedgerError as exc:
        _eprint(str(exc))
        return 2
