#!/usr/bin/env python3
"""Validate the repository-owned neurobiology glossary CSV."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data/source/neurobiology_glossary.csv"
REQUIRED_FIELDS = {
    "term_id",
    "term",
    "display_term",
    "answer",
    "Chinese",
    "part_of_speech",
    "definition_simple",
    "definition_precise",
    "domain",
    "category",
    "subcategory",
    "related_terms",
    "singular",
    "plural",
    "pronunciation_text",
    "ipa",
    "difficulty",
    "source_day",
    "source_lesson",
    "date_added",
    "notes",
    "hangman_enabled",
    "status",
}
SUPPORTED_CATEGORIES = {
    "Neuroanatomy",
    "Cellular neuroscience",
    "Neural signaling",
    "Sensory systems",
    "Motor systems",
    "Cognitive neuroscience",
    "Development and plasticity",
    "Neurological disorders",
    "Research methods",
    "General anatomy and physiology",
    "Biochemistry and molecular biology",
    "Clinical terminology",
}
THEME_BY_CATEGORY = {
    "Cellular neuroscience": "NEURO_FOUNDATIONS",
    "Neuroanatomy": "NEURO_ANATOMY",
    "General anatomy and physiology": "NEURO_ANATOMY",
    "Sensory systems": "NEURO_FUNCTION",
    "Motor systems": "NEURO_FUNCTION",
    "Neurological disorders": "NEURO_CLINICAL",
}
TERM_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ASCII_LETTER_RE = re.compile(r"[a-z]", re.IGNORECASE)


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header")
        missing = REQUIRED_FIELDS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")
        return list(reader)


def validate_rows(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_answers: dict[str, str] = {}
    for number, row in enumerate(rows, start=2):
        for field in REQUIRED_FIELDS:
            if not row.get(field, "").strip() and field not in {
                "plural",
                "ipa",
                "source_day",
                "source_lesson",
                "date_added",
            }:
                errors.append(f"row {number}: missing {field}")
        term_id = row.get("term_id", "").strip()
        if term_id in seen_ids:
            errors.append(f"row {number}: duplicate term_id {term_id!r}")
        seen_ids.add(term_id)
        if term_id and not TERM_ID_RE.fullmatch(term_id):
            errors.append(f"row {number}: invalid term_id {term_id!r}")
        category = row.get("category", "").strip()
        if category not in SUPPORTED_CATEGORIES:
            errors.append(f"row {number}: unsupported category {category!r}")
        if category not in THEME_BY_CATEGORY:
            errors.append(f"row {number}: no deterministic theme mapping for {category!r}")
        enabled = row.get("hangman_enabled", "").strip().lower()
        if enabled not in {"yes", "no"}:
            errors.append(f"row {number}: invalid hangman_enabled {enabled!r}")
        status = row.get("status", "").strip().lower()
        if status not in {"approved", "draft", "retired"}:
            errors.append(f"row {number}: invalid status {status!r}")
        answer = row.get("answer", "").strip()
        normalized = answer.casefold()
        if " / " in answer or "/" in answer and answer != "stimulus":
            errors.append(f"row {number}: combined answer {answer!r}")
        if not ASCII_LETTER_RE.search(answer):
            errors.append(f"row {number}: answer has no ASCII letters")
        theme = THEME_BY_CATEGORY.get(category)
        if theme and normalized in seen_answers:
            errors.append(
                f"row {number}: duplicate normalized answer {answer!r} in {theme}"
            )
        if theme:
            seen_answers[normalized] = theme
        if row.get("term", "").strip() == "stimulus / stimuli":
            errors.append(f"row {number}: source combined term was not normalized")
        if answer.casefold() == "stimulus" and row.get("plural", "").strip() != "stimuli":
            errors.append(f"row {number}: stimulus plural metadata must be stimuli")
    return errors


def validate(path: Path = DEFAULT_PATH) -> list[dict[str, str]]:
    rows = load_rows(path)
    errors = validate_rows(rows)
    if errors:
        raise ValueError("\n".join(errors))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    try:
        rows = validate(args.csv_path)
    except (OSError, ValueError) as exc:
        print(f"Glossary validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Glossary valid: {len(rows)} approved source rows in {args.csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
