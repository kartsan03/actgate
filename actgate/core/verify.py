"""Ledger chain verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from actgate.core.ledger import (
    GENESIS,
    LedgerError,
    Ledger,
    compute_entry_hash,
    compute_seal,
    seal_key,
)


@dataclass
class VerifyResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    entries: int = 0

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1


def verify_ledger(ledger: Ledger, require_seal: bool | None = None) -> VerifyResult:
    """Verify hash chain and optional HMAC seals.

    Returns ok=False (exit 1) on broken chain or bad/missing seal when required.
    """
    errors: list[str] = []
    try:
        entries = ledger.read_entries()
    except LedgerError as exc:
        return VerifyResult(ok=False, errors=[str(exc)])

    key = seal_key()
    if require_seal is None:
        require_seal = key is not None

    prev = GENESIS
    for i, entry in enumerate(entries):
        seq = entry.get("seq")
        if seq != i + 1:
            errors.append(f"seq mismatch at index {i}: expected {i + 1}, got {seq}")
        if entry.get("prev_hash") != prev:
            errors.append(
                f"prev_hash mismatch at seq {seq}: expected {prev}, got {entry.get('prev_hash')}"
            )
        expected_hash = compute_entry_hash(entry)
        if entry.get("entry_hash") != expected_hash:
            errors.append(
                f"entry_hash mismatch at seq {seq}: expected {expected_hash}, got {entry.get('entry_hash')}"
            )
        if require_seal:
            if key is None:
                errors.append(f"seal required but ACTGATE_SEAL_KEY unset at seq {seq}")
            else:
                seal = entry.get("seal")
                if not seal:
                    errors.append(f"missing seal at seq {seq}")
                else:
                    expected_seal = compute_seal(entry["entry_hash"], key)
                    if not (seal == expected_seal):
                        errors.append(f"bad seal at seq {seq}")
        prev = entry.get("entry_hash", "")

    return VerifyResult(ok=not errors, errors=errors, entries=len(entries))
