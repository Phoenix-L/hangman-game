#!/usr/bin/env python3
"""Validate and idempotently import a hangman-weekly-v1 package."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import DEFAULT_DB_PATH, get_connection, init_db  # noqa: E402

FORMAT = "hangman-weekly-v1"
RECEIPT_FORMAT = "hangman-weekly-receipt-v1"
ALLOWED_CATEGORIES = {
    "NEURO_FOUNDATIONS",
    "NEURO_ANATOMY",
    "NEURO_FUNCTION",
    "NEURO_CLINICAL",
}
THEME_DESCRIPTIONS = {
    "NEURO_FOUNDATIONS": "Neurobiology foundations and cellular neuroscience",
    "NEURO_ANATOMY": "Neuroanatomy and related anatomy",
    "NEURO_FUNCTION": "Sensory and motor neuroscience",
    "NEURO_CLINICAL": "Clinical neurobiology and neurological disorders",
}
SOURCE_ID_RE = re.compile(r"^learning:[a-z0-9-]+:term:[0-9a-f]{24}$")
ASCII_LETTER_RE = re.compile(r"[a-z]", re.IGNORECASE)
PACKAGE_FIELDS = {
    "format",
    "package_id",
    "program_slug",
    "week_number",
    "items",
    "payload_sha256",
}
ITEM_FIELDS = {
    "source_term_id",
    "canonical_term",
    "display_term",
    "pronunciation_text",
    "definition",
    "part_of_speech",
    "category",
    "aliases",
    "source_days",
}


class PackageError(ValueError):
    """Safe package validation or identity error."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def checksum(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_package(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageError("Package is not valid JSON.") from exc
    validate_package(value)
    return value


def validate_package(package: Any) -> None:
    if not isinstance(package, dict) or set(package) != PACKAGE_FIELDS:
        raise PackageError("Package fields are invalid.")
    if (
        package["format"] != FORMAT
        or not isinstance(package["package_id"], str)
        or not package["package_id"].startswith("hangman-weekly-v1:")
    ):
        raise PackageError("Package format or identifier is invalid.")
    if (
        not isinstance(package["program_slug"], str)
        or not package["program_slug"]
        or not isinstance(package["week_number"], int)
    ):
        raise PackageError("Package identity is invalid.")
    unsigned = dict(package)
    declared = unsigned.pop("payload_sha256")
    if not isinstance(declared, str) or checksum(unsigned) != declared:
        raise PackageError("Package checksum is invalid.")
    if not isinstance(package["items"], list):
        raise PackageError("Package items are invalid.")
    seen_ids: set[str] = set()
    seen_terms: set[str] = set()
    for item in package["items"]:
        if not isinstance(item, dict) or set(item) != ITEM_FIELDS:
            raise PackageError("Package item fields are invalid.")
        for field in (
            "source_term_id",
            "canonical_term",
            "display_term",
            "pronunciation_text",
            "definition",
            "part_of_speech",
            "category",
        ):
            if not isinstance(item[field], str) or not item[field].strip():
                raise PackageError("Package item contains an empty required field.")
        if item["category"] not in ALLOWED_CATEGORIES:
            raise PackageError("Package contains an unsupported category.")
        if not SOURCE_ID_RE.fullmatch(item["source_term_id"]):
            raise PackageError("Package source identity is invalid.")
        normalized = " ".join(item["canonical_term"].strip().casefold().split())
        if not ASCII_LETTER_RE.search(normalized):
            raise PackageError("Package contains an unplayable term.")
        if item["source_term_id"] in seen_ids or normalized in seen_terms:
            raise PackageError("Package contains duplicate identity or term.")
        seen_ids.add(item["source_term_id"])
        seen_terms.add(normalized)
        if not isinstance(item["aliases"], list) or not all(
            isinstance(alias, str) for alias in item["aliases"]
        ):
            raise PackageError("Package aliases are invalid.")
        if not isinstance(item["source_days"], list) or not all(
            isinstance(day, int) and 1 <= day <= 90 for day in item["source_days"]
        ):
            raise PackageError("Package source days are invalid.")


def _existing_for_source(conn, source_term_id: str):
    return conn.execute(
        "SELECT wm.*, w.value, w.theme_id, t.name AS theme_name FROM word_metadata wm JOIN words w ON w.id=wm.word_id JOIN themes t ON t.id=w.theme_id WHERE wm.source_term_id=?",
        (source_term_id,),
    ).fetchone()


def _plan(
    conn, package: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    operations: list[dict[str, Any]] = []
    summary = {"inserted": 0, "updated": 0, "unchanged": 0, "conflicts": 0, "errors": 0}
    errors: list[str] = []
    for item in package["items"]:
        value = " ".join(item["canonical_term"].strip().casefold().split())
        theme = conn.execute(
            "SELECT id FROM themes WHERE name=?", (item["category"],)
        ).fetchone()
        source = _existing_for_source(conn, item["source_term_id"])
        if source is not None and (
            source["value"] != value or source["theme_name"] != item["category"]
        ):
            errors.append("source identity conflict")
            summary["conflicts"] += 1
            continue
        existing_word = conn.execute(
            "SELECT w.id, w.theme_id, t.name AS theme_name FROM words w JOIN themes t ON t.id=w.theme_id WHERE w.value=?",
            (value,),
        ).fetchall()
        if any(row["theme_name"] != item["category"] for row in existing_word):
            errors.append("term exists in another category")
            summary["conflicts"] += 1
            continue
        if source is not None:
            current = dict(source)
            changed = any(
                current[key] != item_value
                for key, item_value in {
                    "display_term": item["display_term"],
                    "pronunciation_text": item["pronunciation_text"],
                    "definition_simple": item["definition"],
                    "part_of_speech": item["part_of_speech"],
                    "detailed_category": item["category"],
                    "theme_key": item["category"],
                }.items()
            )
            summary["updated" if changed else "unchanged"] += 1
            operations.append(
                {
                    "item": item,
                    "action": "update" if changed else "unchanged",
                    "word_id": int(source["word_id"]),
                    "theme_id": int(source["theme_id"]),
                }
            )
        elif existing_word:
            summary["unchanged"] += 1
            operations.append(
                {
                    "item": item,
                    "action": "metadata",
                    "word_id": int(existing_word[0]["id"]),
                    "theme_id": int(existing_word[0]["theme_id"]),
                }
            )
        else:
            summary["inserted"] += 1
            operations.append(
                {
                    "item": item,
                    "action": "insert",
                    "word_id": None,
                    "theme_id": int(theme["id"]) if theme else None,
                }
            )
    if errors:
        summary["errors"] = len(errors)
    return operations, summary, errors


def import_package(
    package_path: Path,
    db_path: str,
    *,
    dry_run: bool = False,
    confirm: bool = False,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    package = load_package(package_path)
    if not dry_run and not confirm:
        raise PackageError("Real imports require --confirm.")
    if not dry_run:
        init_db(db_path)
    conn = get_connection(db_path)
    try:
        operations, summary, errors = _plan(conn, package)
        if errors:
            raise PackageError("Package conflicts prevent import.")
        if dry_run:
            return {
                **summary,
                "categories": sorted({item["category"] for item in package["items"]}),
                "mappings": [],
            }
        mappings = []
        with conn:
            for operation in operations:
                item = operation["item"]
                value = " ".join(item["canonical_term"].strip().casefold().split())
                if operation["action"] == "insert":
                    if operation["theme_id"] is None:
                        conn.execute(
                            "INSERT INTO themes (name, description) VALUES (?, ?)",
                            (item["category"], THEME_DESCRIPTIONS[item["category"]]),
                        )
                        operation["theme_id"] = int(
                            conn.execute(
                                "SELECT id FROM themes WHERE name=?",
                                (item["category"],),
                            ).fetchone()[0]
                        )
                    cur = conn.execute(
                        "INSERT INTO words (theme_id, value) VALUES (?, ?)",
                        (operation["theme_id"], value),
                    )
                    operation["word_id"] = int(cur.lastrowid)
                    conn.execute(
                        "INSERT INTO word_metadata (word_id, source_term_id, display_term, pronunciation_text, definition_simple, detailed_category, part_of_speech, theme_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            operation["word_id"],
                            item["source_term_id"],
                            item["display_term"],
                            item["pronunciation_text"],
                            item["definition"],
                            item["category"],
                            item["part_of_speech"],
                            item["category"],
                        ),
                    )
                elif operation["action"] in {"update", "metadata"}:
                    conn.execute(
                        "INSERT OR IGNORE INTO word_metadata (word_id, source_term_id, display_term, pronunciation_text, definition_simple, detailed_category, part_of_speech, theme_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            operation["word_id"],
                            item["source_term_id"],
                            item["display_term"],
                            item["pronunciation_text"],
                            item["definition"],
                            item["category"],
                            item["part_of_speech"],
                            item["category"],
                        ),
                    )
                    if operation["action"] == "update":
                        conn.execute(
                            "UPDATE word_metadata SET display_term=?, pronunciation_text=?, definition_simple=?, detailed_category=?, part_of_speech=?, theme_key=? WHERE source_term_id=?",
                            (
                                item["display_term"],
                                item["pronunciation_text"],
                                item["definition"],
                                item["category"],
                                item["part_of_speech"],
                                item["category"],
                                item["source_term_id"],
                            ),
                        )
                mappings.append(
                    {
                        "source_term_id": item["source_term_id"],
                        "word_id": int(operation["word_id"]),
                        "category": item["category"],
                    }
                )
        receipt = {
            "format": RECEIPT_FORMAT,
            "package_id": package["package_id"],
            "payload_sha256": package["payload_sha256"],
            "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "database_id": "hangman-local-v1",
            "inserted_count": summary["inserted"],
            "updated_count": summary["updated"],
            "unchanged_count": summary["unchanged"],
            "mappings": mappings,
        }
        receipt["receipt_sha256"] = checksum(receipt)
        if receipt_path:
            receipt_path.write_text(canonical_json(receipt), encoding="utf-8")
        return {
            **summary,
            "categories": sorted({item["category"] for item in package["items"]}),
            "mappings": mappings,
            "receipt": receipt,
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--receipt-output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    try:
        result = import_package(
            args.package,
            args.db_path,
            dry_run=args.dry_run,
            confirm=args.confirm,
            receipt_path=args.receipt_output,
        )
    except (OSError, PackageError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    for key in ("inserted", "updated", "unchanged", "conflicts", "errors"):
        print(f"{key}: {result[key]}")
    print(f"categories: {', '.join(result['categories'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
