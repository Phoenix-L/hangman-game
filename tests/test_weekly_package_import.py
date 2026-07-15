from __future__ import annotations

import json
from pathlib import Path

import pytest

from db import get_connection, init_db
from scripts.import_weekly_package import (
    PackageError,
    checksum,
    import_package,
    validate_package,
)


def package(items=None):
    value = {
        "format": "hangman-weekly-v1",
        "package_id": "hangman-weekly-v1:neuroscience-90:week-1",
        "program_slug": "neuroscience-90",
        "week_number": 1,
        "items": items
        or [
            {
                "source_term_id": "learning:neuroscience-90:term:" + "a" * 24,
                "canonical_term": "synapse",
                "display_term": "Synapse",
                "pronunciation_text": "synapse",
                "definition": "a junction",
                "part_of_speech": "noun",
                "category": "NEURO_FOUNDATIONS",
                "aliases": [],
                "source_days": [1],
            }
        ],
    }
    value["payload_sha256"] = checksum(value)
    return value


def write_package(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "package.json"
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def test_schema_and_checksum_validation(tmp_path):
    value = package()
    validate_package(value)
    value["payload_sha256"] = "0" * 64
    with pytest.raises(PackageError):
        validate_package(value)


def test_dry_run_and_confirmation_gate_do_not_write(tmp_path):
    db = tmp_path / "hangman.db"
    init_db(str(db))
    path = write_package(tmp_path, package())
    result = import_package(path, str(db), dry_run=True)
    assert result["inserted"] == 1
    with get_connection(str(db)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM words").fetchone()[0] == 0
    with pytest.raises(PackageError):
        import_package(path, str(db), confirm=False)


def test_first_import_identical_second_import_preserves_word_id(tmp_path):
    db = tmp_path / "hangman.db"
    path = write_package(tmp_path, package())
    first = import_package(path, str(db), confirm=True)
    second = import_package(path, str(db), confirm=True)
    assert first["inserted"] == 1 and second["unchanged"] == 1
    assert first["mappings"] == second["mappings"]


def test_identity_conflict_and_malformed_multi_item_roll_back(tmp_path):
    db = tmp_path / "hangman.db"
    path = write_package(tmp_path, package())
    import_package(path, str(db), confirm=True)
    conflict = package()
    conflict["items"][0]["canonical_term"] = "different"
    conflict["payload_sha256"] = checksum(
        {k: v for k, v in conflict.items() if k != "payload_sha256"}
    )
    with pytest.raises(PackageError):
        import_package(write_package(tmp_path, conflict), str(db), confirm=True)
    malformed_items = [
        package()["items"][0],
        {
            **package()["items"][0],
            "source_term_id": "learning:neuroscience-90:term:" + "b" * 24,
            "canonical_term": "two",
        },
    ]
    malformed = package(malformed_items)
    malformed["items"][1]["category"] = "NOT_ALLOWED"
    malformed["payload_sha256"] = checksum(
        {k: v for k, v in malformed.items() if k != "payload_sha256"}
    )
    with pytest.raises(PackageError):
        import_package(write_package(tmp_path, malformed), str(db), confirm=True)
    with get_connection(str(db)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM words").fetchone()[0] == 1


def test_metadata_and_game_tables_are_preserved(tmp_path):
    db = tmp_path / "hangman.db"
    init_db(str(db))
    with get_connection(str(db)) as connection:
        connection.execute("INSERT INTO users (username) VALUES ('existing')")
        connection.commit()
    before = get_connection(str(db)).execute("SELECT COUNT(*) FROM users").fetchone()[0]
    path = write_package(tmp_path, package())
    import_package(path, str(db), confirm=True)
    with get_connection(str(db)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == before
        assert (
            connection.execute("SELECT COUNT(*) FROM word_metadata").fetchone()[0] == 1
        )
