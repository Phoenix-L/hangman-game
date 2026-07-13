#!/usr/bin/env python3
"""Idempotently import the approved neurobiology glossary into SQLite."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import DEFAULT_DB_PATH, get_connection, init_db
from scripts.validate_neurobiology_glossary import DEFAULT_PATH, THEME_BY_CATEGORY, validate


THEME_DESCRIPTIONS = {
    "NEURO_FOUNDATIONS": "Neurobiology foundations and cellular neuroscience",
    "NEURO_ANATOMY": "Neuroanatomy and related general anatomy",
    "NEURO_FUNCTION": "Sensory and motor neuroscience",
    "NEURO_CLINICAL": "Clinical neurobiology and neurological disorders",
}


def import_glossary(db_path: str, csv_path: Path) -> dict[str, int]:
    rows = validate(csv_path)
    init_db(db_path)
    summary = {"inserted": 0, "updated": 0, "unchanged": 0, "skipped": 0, "errors": 0}
    conn = get_connection(db_path)
    try:
        for row in rows:
            if row["status"].strip().lower() != "approved" or row["hangman_enabled"].strip().lower() != "yes":
                summary["skipped"] += 1
                continue
            theme_key = THEME_BY_CATEGORY[row["category"].strip()]
            conn.execute(
                "INSERT OR IGNORE INTO themes (name, description) VALUES (?, ?)",
                (theme_key, THEME_DESCRIPTIONS[theme_key]),
            )
            theme_id = conn.execute(
                "SELECT id FROM themes WHERE name = ?", (theme_key,)
            ).fetchone()["id"]
            answer = row["answer"].strip().casefold()
            existing_word = conn.execute(
                "SELECT id, difficulty FROM words WHERE theme_id = ? AND value = ?",
                (theme_id, answer),
            ).fetchone()
            if existing_word is None:
                cursor = conn.execute(
                    "INSERT INTO words (theme_id, value, difficulty) VALUES (?, ?, ?)",
                    (theme_id, answer, row["difficulty"].strip() or None),
                )
                word_id = int(cursor.lastrowid)
                summary["inserted"] += 1
            else:
                word_id = int(existing_word["id"])
                if existing_word["difficulty"] != (row["difficulty"].strip() or None):
                    conn.execute(
                        "UPDATE words SET difficulty = ? WHERE id = ?",
                        (row["difficulty"].strip() or None, word_id),
                    )
                    changed = True
                else:
                    changed = False

            values = {
                "source_term_id": row["term_id"].strip(),
                "display_term": row["display_term"].strip(),
                "pronunciation_text": row["pronunciation_text"].strip() or row["answer"].strip(),
                "chinese": row["Chinese"].strip(),
                "definition_simple": row["definition_simple"].strip(),
                "detailed_category": row["category"].strip(),
                "part_of_speech": row["part_of_speech"].strip(),
                "theme_key": theme_key,
            }
            metadata = conn.execute(
                "SELECT source_term_id, display_term, pronunciation_text, chinese, definition_simple, detailed_category, part_of_speech, theme_key, word_id FROM word_metadata WHERE source_term_id = ?",
                (values["source_term_id"],),
            ).fetchone()
            if metadata is not None and int(metadata["word_id"]) != word_id:
                raise ValueError(f"source term {values['source_term_id']} is linked to another word")
            if metadata is None:
                conn.execute(
                    """
                    INSERT INTO word_metadata (
                        word_id, source_term_id, display_term, pronunciation_text,
                        chinese, definition_simple, detailed_category, part_of_speech, theme_key
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (word_id, *values.values()),
                )
                changed = True
            else:
                current = dict(metadata)
                changed = changed or any(current[key] != value for key, value in values.items())
                if changed:
                    conn.execute(
                        """
                        UPDATE word_metadata
                        SET word_id = ?, display_term = ?, pronunciation_text = ?, chinese = ?,
                            definition_simple = ?, detailed_category = ?, part_of_speech = ?, theme_key = ?
                        WHERE source_term_id = ?
                        """,
                        (
                            word_id,
                            values["display_term"],
                            values["pronunciation_text"],
                            values["chinese"],
                            values["definition_simple"],
                            values["detailed_category"],
                            values["part_of_speech"],
                            values["theme_key"],
                            values["source_term_id"],
                        ),
                    )
            if existing_word is not None and not changed:
                summary["unchanged"] += 1
            elif existing_word is not None:
                summary["updated"] += 1
        conn.commit()
    except Exception:
        conn.rollback()
        summary["errors"] += 1
        raise
    finally:
        conn.close()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH)
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    try:
        summary = import_glossary(args.db_path, args.csv_path)
    except (OSError, ValueError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    print("Neurobiology glossary import summary:")
    for key in ("inserted", "updated", "unchanged", "skipped", "errors"):
        print(f"  {key}: {summary[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
