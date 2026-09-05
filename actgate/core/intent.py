"""Intent model: tool action proposals."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


class IntentError(ValueError):
    """Invalid intent input (setup error)."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_args(args: Any) -> str:
    return hashlib.sha256(canonical_json(args).encode("utf-8")).hexdigest()


@dataclass
class Intent:
    tool: str
    created_at: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    args: dict[str, Any] | None = None
    args_hash: str | None = None
    blast_tags: list[str] = field(default_factory=list)
    requested_mode: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Intent":
        return cls(
            id=data["id"],
            tool=data["tool"],
            created_at=data["created_at"],
            args=data.get("args"),
            args_hash=data.get("args_hash"),
            blast_tags=list(data.get("blast_tags") or []),
            requested_mode=data.get("requested_mode"),
        )


def build_intent(
    tool: str,
    args: dict[str, Any] | None = None,
    args_hash: str | None = None,
    blast_tags: list[str] | None = None,
    requested_mode: str | None = None,
    created_at: str | None = None,
    intent_id: str | None = None,
) -> Intent:
    tool = (tool or "").strip()
    if not tool:
        raise IntentError("tool is required")
    if args is None and not args_hash:
        raise IntentError("provide args or args_hash")
    if args is not None and args_hash:
        computed = hash_args(args)
        if computed != args_hash:
            raise IntentError("args_hash does not match args")
    if args is not None and not args_hash:
        args_hash = hash_args(args)
    return Intent(
        id=intent_id or uuid.uuid4().hex,
        tool=tool,
        args=args,
        args_hash=args_hash,
        blast_tags=list(blast_tags or []),
        requested_mode=requested_mode,
        created_at=created_at or _utc_now(),
    )
