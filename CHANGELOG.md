# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-06

### Added

- Initial release: local IntentLedger with propose / dry-run / approve / deny / verify / show / list.
- Append-only `ledger.jsonl` with sha256 hash chain; optional HMAC seal via `ACTGATE_SEAL_KEY`.
- Exit codes: `0` ok, `1` deny or broken chain, `2` setup error.
- Stdlib-only core path (no network).
- Examples for happy path and deny/fail.
- CI on Python 3.10-3.13; Trusted Publisher publish workflow on tags `v*` (not run from this release).
