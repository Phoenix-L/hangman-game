import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from db import get_connection, initialize_and_seed, init_db, reset_and_seed_database


ROOT = Path(__file__).resolve().parents[1]


def _make_populated_db(path: Path) -> dict[str, int]:
    init_db(str(path))
    conn = get_connection(str(path))
    try:
        user_id = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES ('preserved', 'hash')"
        ).lastrowid
        theme_id = conn.execute(
            "INSERT INTO themes (name, description, is_active) VALUES ('LEGACY', 'legacy', 1)"
        ).lastrowid
        word_id = conn.execute(
            "INSERT INTO words (theme_id, value, difficulty) VALUES (?, 'keepme', 'review')",
            (theme_id,),
        ).lastrowid
        game_id = conn.execute(
            "INSERT INTO games (user_id, word_id, theme_id, status, score) VALUES (?, ?, ?, 'won', 42)",
            (user_id, word_id, theme_id),
        ).lastrowid
        conn.execute(
            "INSERT INTO word_progress (user_id, word_id, times_seen, times_correct) VALUES (?, ?, 3, 2)",
            (user_id, word_id),
        )
        conn.execute(
            "INSERT INTO user_word_progress (user_id, word_id, correct_count, wrong_count) VALUES (?, ?, 2, 1)",
            (user_id, word_id),
        )
        conn.execute(
            "INSERT INTO leaderboard_entries (user_id, game_id, score) VALUES (?, ?, 42)",
            (user_id, game_id),
        )
        conn.execute(
            "INSERT INTO user_stats (user_id, total_games, total_score) VALUES (?, 1, 42)",
            (user_id,),
        )
        conn.execute(
            """
            INSERT INTO word_metadata (
                word_id, source_term_id, display_term, pronunciation_text,
                chinese, definition_simple, detailed_category, part_of_speech, theme_key
            ) VALUES (?, 'legacy-term', 'keepme', 'keepme', '保留', 'Keep this row', 'Clinical terminology', 'noun', 'LEGACY')
            """,
            (word_id,),
        )
        conn.commit()
        return {"user_id": user_id, "theme_id": theme_id, "word_id": word_id, "game_id": game_id}
    finally:
        conn.close()


def _snapshot(path: Path) -> dict[str, list[tuple]]:
    conn = sqlite3.connect(path)
    try:
        tables = [
            "users",
            "themes",
            "words",
            "games",
            "word_progress",
            "user_word_progress",
            "leaderboard_entries",
            "user_stats",
            "word_metadata",
        ]
        return {
            table: conn.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in tables
        }
    finally:
        conn.close()


def test_normal_startup_preserves_every_production_table_and_is_idempotent(tmp_path):
    db_path = tmp_path / "preserve.db"
    ids = _make_populated_db(db_path)
    source = tmp_path / "words"
    source.mkdir()
    (source / "legacy.txt").write_text("keepme\nnewword\n", encoding="utf-8")
    before = _snapshot(db_path)

    assert initialize_and_seed(str(db_path), [str(source)]) == 1
    after_first = _snapshot(db_path)
    assert initialize_and_seed(str(db_path), [str(source)]) == 0
    after_second = _snapshot(db_path)

    for table in before:
        assert before[table] == [row for row in after_first[table] if row in before[table]]
        assert after_first[table] == after_second[table]
    assert ids["user_id"] in [row[0] for row in after_second["users"]]
    assert ids["theme_id"] in [row[0] for row in after_second["themes"]]
    assert ids["word_id"] in [row[0] for row in after_second["words"]]
    assert ids["game_id"] in [row[0] for row in after_second["games"]]
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT is_active FROM themes WHERE id=?", (ids["theme_id"],)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM words WHERE value='newword'").fetchone()[0] == 1
    finally:
        conn.close()


def test_server_module_import_preserves_existing_rows(tmp_path):
    db_path = tmp_path / "server-import.db"
    ids = _make_populated_db(db_path)
    env = os.environ.copy()
    env["HANGMAN_DB_PATH"] = str(db_path)
    subprocess.run([sys.executable, "-c", "import server"], cwd=ROOT, env=env, check=True)
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM leaderboard_entries").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM word_metadata").fetchone()[0] == 1
        assert conn.execute("SELECT id FROM users WHERE id=?", (ids["user_id"],)).fetchone()
    finally:
        conn.close()


def test_init_script_is_safe_when_run_twice_on_populated_database(tmp_path):
    db_path = tmp_path / "init-script.db"
    ids = _make_populated_db(db_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "legacy.txt").write_text("keepme\nnewword\n", encoding="utf-8")
    command = [sys.executable, "scripts/init_db.py", "--db-path", str(db_path), "--data-dir", str(source)]
    subprocess.run(command, cwd=ROOT, check=True)
    subprocess.run(command, cwd=ROOT, check=True)
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM user_word_progress").fetchone()[0] == 1
        assert conn.execute("SELECT id FROM words WHERE id=?", (ids["word_id"],)).fetchone()
        assert conn.execute("SELECT COUNT(*) FROM words WHERE value='newword'").fetchone()[0] == 1
    finally:
        conn.close()


def test_destructive_reset_requires_explicit_function_and_is_test_only(tmp_path):
    db_path = tmp_path / "reset.db"
    _make_populated_db(db_path)
    source = tmp_path / "source"
    source.mkdir()
    (source / "fresh.txt").write_text("fresh\n", encoding="utf-8")
    assert reset_and_seed_database(str(db_path), [str(source)]) == 1
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0
        assert conn.execute("SELECT value FROM words").fetchall() == [('fresh',)]
    finally:
        conn.close()


def test_init_script_rejects_unconfirmed_destructive_flag(tmp_path):
    db_path = tmp_path / "guard.db"
    _make_populated_db(db_path)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/init_db.py",
            "--db-path",
            str(db_path),
            "--reset-destructive",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "requires --confirm-destructive-reset" in result.stderr
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    finally:
        conn.close()


def test_legacy_word_progress_is_archived_without_drop(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE word_progress (
                id INTEGER PRIMARY KEY,
                game_id INTEGER,
                guessed_letter TEXT,
                was_correct INTEGER,
                guessed_at TEXT
            );
            INSERT INTO word_progress (id, game_id, guessed_letter, was_correct, guessed_at)
            VALUES (7, 99, 'a', 1, '2026-01-01');
            """
        )
        conn.commit()
    finally:
        conn.close()
    init_db(str(db_path))
    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT game_id, guessed_letter FROM word_progress_legacy").fetchone() == (99, "a")
        assert conn.execute("SELECT COUNT(*) FROM word_progress").fetchone()[0] == 0
    finally:
        conn.close()
