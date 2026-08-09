"""Deterministic JSON and hashing helpers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from openmacrostate.api.v1.errors import CaseValidationError

MAX_JSON_BYTES = 32 * 1024 * 1024
MAX_JSONL_LINE_BYTES = 1024 * 1024
MAX_JSONL_RECORDS = 100_000


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _decode_json(data: bytes, *, source: str) -> Any:
    if len(data) > MAX_JSON_BYTES:
        raise CaseValidationError(f"JSON input exceeds {MAX_JSON_BYTES} bytes: {source}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CaseValidationError(f"JSON input is not UTF-8: {source}: {exc}") from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise CaseValidationError(f"cannot decode JSON {source}: {exc}") from exc


def load_json_bytes(data: bytes, *, source: str = "<bytes>") -> Any:
    return _decode_json(data, source=source)


def load_jsonl_bytes(data: bytes, *, source: str = "<bytes>") -> list[dict[str, Any]]:
    if len(data) > MAX_JSON_BYTES:
        raise CaseValidationError(f"JSONL input exceeds {MAX_JSON_BYTES} bytes: {source}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.splitlines(), start=1):
        if not line.strip():
            continue
        if len(line) > MAX_JSONL_LINE_BYTES:
            raise CaseValidationError(
                f"JSONL line exceeds {MAX_JSONL_LINE_BYTES} bytes: {source}:{line_number}"
            )
        if len(records) >= MAX_JSONL_RECORDS:
            raise CaseValidationError(f"JSONL input exceeds {MAX_JSONL_RECORDS} records: {source}")
        record = _decode_json(line, source=f"{source}:{line_number}")
        if not isinstance(record, dict):
            raise CaseValidationError(f"JSONL record must be an object: {source}:{line_number}")
        records.append(record)
    return records


def load_json(path: Path) -> Any:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise CaseValidationError(f"cannot read JSON {path}: {exc}") from exc
    return load_json_bytes(data, source=str(path))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise CaseValidationError(f"cannot read JSONL {path}: {exc}") from exc
    return load_jsonl_bytes(data, source=str(path))


def normalize_json_value(value: Any) -> Any:
    """Convert immutable mappings/tuples into plain JSON containers."""
    if isinstance(value, dict) or hasattr(value, "items"):
        return {str(key): normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_json_value(item) for item in value]
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        normalize_json_value(value),
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    body = (
        json.dumps(normalize_json_value(value), allow_nan=False, ensure_ascii=False, indent=2)
        + "\n"
    )
    write_bytes_atomic(path, body.encode("utf-8"))


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    body = "".join(
        json.dumps(
            normalize_json_value(record),
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
        for record in records
    )
    write_bytes_atomic(path, body.encode("utf-8"))


def write_text_atomic(path: Path, value: str) -> None:
    write_bytes_atomic(path, value.encode("utf-8"))


def write_bytes_atomic(path: Path, value: bytes) -> None:
    """Write a regular file atomically without following an existing symlink."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        stat = path.lstat()
        if path.is_symlink() or not path.is_file():
            raise CaseValidationError(f"refusing to replace non-regular output file: {path}")
        if stat.st_nlink != 1:
            raise CaseValidationError(f"refusing to replace hard-linked output file: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        finally:
            raise
