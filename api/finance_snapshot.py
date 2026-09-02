"""Read and validate a finance snapshot produced by masi-finance.

Django-free on purpose (same shape as youth_expenditure_import.py): the
management command and the tests both import it, and nothing here needs
settings or the ORM. The contract is api/contracts/finance-snapshot-1.0.0.json,
a verbatim copy of the publisher's schema; the loader refuses any other
schema_version, which is the mechanism that keeps the two repositories
from drifting silently.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import jsonschema

SCHEMA_VERSION = "1.0.0"
SCHEMA_PATH = Path(__file__).resolve().parent / "contracts" / f"finance-snapshot-{SCHEMA_VERSION}.json"


class FinanceSnapshotError(ValueError):
    """The file cannot safely be published to the database."""


def load_snapshot_file(path: Path | str) -> dict:
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FinanceSnapshotError(f"Snapshot file does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FinanceSnapshotError(f"Snapshot file is not valid JSON: {path} ({exc})") from exc
    if not isinstance(payload, dict):
        raise FinanceSnapshotError(f"Snapshot file is not a JSON object: {path}")
    validate_snapshot(payload)
    return payload


def validate_snapshot(payload: dict) -> None:
    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise FinanceSnapshotError(
            f"Unknown schema_version {version!r}; this loader understands {SCHEMA_VERSION!r}"
        )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.absolute_path))
    if errors:
        first = errors[0]
        where = "/".join(str(step) for step in first.absolute_path) or "<root>"
        raise FinanceSnapshotError(f"Snapshot does not match schema {SCHEMA_VERSION} at {where}: {first.message}")
    expected = payload_digest(payload)
    if payload.get("payload_sha256") != expected:
        raise FinanceSnapshotError(
            f"payload_sha256 {payload.get('payload_sha256')!r} does not match the figures ({expected}); "
            "the artifact was edited or produced by a publisher that computes it differently"
        )


PROVENANCE_KEYS = ("run_id", "published_at", "source", "payload_sha256")


def canonical_digest(obj) -> str:
    """SHA-256 of formatting-independent JSON; the contract-parity digest (overview 3.25)."""
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def payload_digest(payload: dict) -> str:
    """Digest of the figures without publication-time provenance; identical to masi-finance's."""
    return canonical_digest({key: value for key, value in payload.items() if key not in PROVENANCE_KEYS})


def parse_timestamp(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def parse_date(text: str) -> date:
    return date.fromisoformat(text)
