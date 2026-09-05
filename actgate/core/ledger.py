"""Append-only sha256-chained ledger.jsonl."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from actgate.core.intent import Intent, canonical_json


GENESIS = "0" * 64
LEDGER_DIR = ".actgate"
LEDGER_NAME = "ledger.jsonl"


class LedgerError(ValueError):
    """Ledger path or I/O setup error."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_ledger_path(
    root: Path | str | None = None, path: Path | str | None = None
) -> Path:
    """Resolve ledger file path; reject escapes outside the chosen root."""
    base = Path(root).resolve() if root else Path.cwd().resolve()
    if path is not None:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = (base / candidate).resolve()
        else:
            candidate = candidate.resolve()
        try:
            candidate.relative_to(base)
        except ValueError as exc:
            raise LedgerError(f"path escapes ledger root: {candidate}") from exc
        return candidate
    return (base / LEDGER_DIR / LEDGER_NAME).resolve()


def seal_key() -> bytes | None:
    raw = os.environ.get("ACTGATE_SEAL_KEY")
    if not raw:
        return None
    return raw.encode("utf-8")


def entry_payload_for_hash(entry: dict[str, Any]) -> str:
    """Canonical payload excluding entry_hash and seal."""
    payload = {k: v for k, v in entry.items() if k not in ("entry_hash", "seal")}
    return canonical_json(payload)


def compute_entry_hash(entry: dict[str, Any]) -> str:
    return hashlib.sha256(entry_payload_for_hash(entry).encode("utf-8")).hexdigest()


def compute_seal(entry_hash: str, key: bytes) -> str:
    return hmac.new(key, entry_hash.encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass
class Ledger:
    path: Path

    @classmethod
    def open(
        cls, root: Path | str | None = None, path: Path | str | None = None
    ) -> "Ledger":
        return cls(path=resolve_ledger_path(root=root, path=path))

    def ensure(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def exists(self) -> bool:
        return self.path.is_file()

    def read_entries(self) -> list[dict[str, Any]]:
        if not self.exists():
            return []
        entries: list[dict[str, Any]] = []
        text = self.path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise LedgerError(f"malformed ledger line {line_no}: {exc}") from exc
        return entries

    def iter_entries(self) -> Iterator[dict[str, Any]]:
        yield from self.read_entries()

    def last_hash(self) -> str:
        entries = self.read_entries()
        if not entries:
            return GENESIS
        return entries[-1]["entry_hash"]

    def append(
        self, action: str, intent: Intent | None = None, **extra: Any
    ) -> dict[str, Any]:
        self.ensure()
        entries = self.read_entries()
        seq = (entries[-1]["seq"] + 1) if entries else 1
        prev_hash = entries[-1]["entry_hash"] if entries else GENESIS
        entry: dict[str, Any] = {
            "seq": seq,
            "prev_hash": prev_hash,
            "action": action,
            "ts": _utc_now(),
        }
        if intent is not None:
            entry["intent_id"] = intent.id
            entry["intent"] = intent.to_dict()
        entry.update(extra)
        entry["entry_hash"] = compute_entry_hash(entry)
        key = seal_key()
        if key is not None:
            entry["seal"] = compute_seal(entry["entry_hash"], key)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + chr(10))
        return entry

    def find_intent_events(self, intent_id: str) -> list[dict[str, Any]]:
        return [e for e in self.read_entries() if e.get("intent_id") == intent_id]

    def latest_decision(self, intent_id: str) -> dict[str, Any] | None:
        events = self.find_intent_events(intent_id)
        for event in reversed(events):
            if event.get("action") in ("approve", "deny"):
                return event
        return None

    def get_proposal(self, intent_id: str) -> dict[str, Any] | None:
        for event in self.find_intent_events(intent_id):
            if event.get("action") == "propose":
                return event
        return None
