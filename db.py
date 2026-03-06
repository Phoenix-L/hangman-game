import sqlite3
from pathlib import Path
from typing import Iterable

DEFAULT_DB_PATH = "hangman.db"
DEFAULT_WORD_DIRS = ("data/words", "word")


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS themes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    theme_id INTEGER NOT NULL,
    value TEXT NOT NULL,
    difficulty TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(theme_id, value),
    FOREIGN KEY(theme_id) REFERENCES themes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    word_id INTEGER,
    theme_id INTEGER,
    status TEXT NOT NULL CHECK(status IN ('in_progress', 'won', 'lost')) DEFAULT 'in_progress',
    wrong_guesses INTEGER NOT NULL DEFAULT 0,
    correct_guesses INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER,
    accuracy REAL,
    score INTEGER,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE SET NULL,
    FOREIGN KEY(theme_id) REFERENCES themes(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS word_progress (
    user_id INTEGER NOT NULL,
    word_id INTEGER NOT NULL,
    times_seen INTEGER NOT NULL DEFAULT 0,
    times_correct INTEGER NOT NULL DEFAULT 0,
    times_wrong INTEGER NOT NULL DEFAULT 0,
    last_seen_at TEXT,
    interval_days INTEGER NOT NULL DEFAULT 1,
    next_review_at TEXT,
    PRIMARY KEY (user_id, word_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS leaderboard_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    game_id INTEGER,
    score INTEGER NOT NULL,
    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE SET NULL
);
"""


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _ensure_users_password_hash_column(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(users)").fetchall()
    names = {col[1] for col in columns}
    if "password_hash" not in names:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")


def _migrate_legacy_word_progress(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(word_progress)").fetchall()
    if not columns:
        return
    names = {col[1] for col in columns}
    legacy_columns = {"game_id", "guessed_letter", "was_correct", "guessed_at"}
    if legacy_columns.intersection(names):
        conn.execute("DROP TABLE IF EXISTS word_progress")
        conn.execute(
            """
            CREATE TABLE word_progress (
                user_id INTEGER NOT NULL,
                word_id INTEGER NOT NULL,
                times_seen INTEGER NOT NULL DEFAULT 0,
                times_correct INTEGER NOT NULL DEFAULT 0,
                times_wrong INTEGER NOT NULL DEFAULT 0,
                last_seen_at TEXT,
                interval_days INTEGER NOT NULL DEFAULT 1,
                next_review_at TEXT,
                PRIMARY KEY (user_id, word_id),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE
            )
            """
        )


def _ensure_games_columns(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(games)").fetchall()
    names = {col[1] for col in columns}

    additions = [
        ("theme_id", "INTEGER REFERENCES themes(id) ON DELETE SET NULL"),
        ("correct_guesses", "INTEGER NOT NULL DEFAULT 0"),
        ("duration_ms", "INTEGER"),
        ("accuracy", "REAL"),
        ("score", "INTEGER"),
    ]
    for column_name, column_type in additions:
        if column_name not in names:
            conn.execute(f"ALTER TABLE games ADD COLUMN {column_name} {column_type}")


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        _ensure_users_password_hash_column(conn)
        _migrate_legacy_word_progress(conn)
        _ensure_games_columns(conn)
        conn.commit()
    finally:
        conn.close()


def _collect_word_files(source_dirs: Iterable[str] | None = None) -> list[Path]:
    dirs = source_dirs or DEFAULT_WORD_DIRS
    files: list[Path] = []
    for directory in dirs:
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            continue
        files.extend(sorted(path.glob("*.txt")))
    return files


def seed_words_from_files(db_path: str = DEFAULT_DB_PATH, source_dirs: Iterable[str] | None = None) -> int:
    files = _collect_word_files(source_dirs)
    if not files:
        return 0

    conn = get_connection(db_path)
    inserted_words = 0
    try:
        for file_path in files:
            theme_name = file_path.stem.upper()
            conn.execute(
                "INSERT OR IGNORE INTO themes (name, description) VALUES (?, ?)",
                (theme_name, f"Seeded from {file_path}"),
            )
            theme_id_row = conn.execute(
                "SELECT id FROM themes WHERE name = ?",
                (theme_name,),
            ).fetchone()
            if not theme_id_row:
                continue
            theme_id = theme_id_row["id"]

            for raw in file_path.read_text(encoding="utf-8").splitlines():
                word = raw.strip().lower()
                if not word:
                    continue
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO words (theme_id, value) VALUES (?, ?)",
                    (theme_id, word),
                )
                inserted_words += cursor.rowcount

        conn.commit()
        return inserted_words
    finally:
        conn.close()


def list_themes(db_path: str = DEFAULT_DB_PATH) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT t.id, t.name, t.description, COUNT(w.id) AS word_count
            FROM themes t
            LEFT JOIN words w ON w.theme_id = t.id
            GROUP BY t.id, t.name, t.description
            ORDER BY t.name
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def create_user(db_path: str, username: str, password_hash: str) -> int | None:
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_user_by_username(db_path: str, username: str) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(db_path: str, user_id: int) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT id, username, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_leaderboard_entry(db_path: str, user_id: int, score: int, game_id: int | None = None) -> int:
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO leaderboard_entries (user_id, game_id, score) VALUES (?, ?, ?)",
            (user_id, game_id, score),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def list_global_leaderboard(db_path: str, *, theme_id: int | None = None, limit: int = 50) -> list[dict]:
    conn = get_connection(db_path)
    try:
        bounded_limit = max(1, min(50, int(limit)))

        base = """
            SELECT le.id,
                   le.user_id,
                   u.username,
                   le.score,
                   le.recorded_at,
                   le.game_id,
                   g.theme_id,
                   g.word_id,
                   g.duration_ms,
                   g.correct_guesses,
                   g.wrong_guesses,
                   g.accuracy
            FROM leaderboard_entries le
            JOIN games g ON g.id = le.game_id
            LEFT JOIN users u ON u.id = le.user_id
        """
        params: list[int] = []
        if theme_id is not None:
            base += " WHERE g.theme_id = ?"
            params.append(theme_id)
        base += " ORDER BY le.score DESC, le.recorded_at ASC, le.id ASC LIMIT ?"
        params.append(bounded_limit)

        rows = conn.execute(base, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_progress_summary(db_path: str, *, user_id: int) -> dict:
    conn = get_connection(db_path)
    try:
        mastery_min_correct = 3
        mastery_min_interval_days = 7

        words_seen = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM word_progress
            WHERE user_id = ? AND times_seen > 0
            """,
            (user_id,),
        ).fetchone()["c"]

        words_mastered = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM word_progress
            WHERE user_id = ?
              AND times_correct >= ?
              AND interval_days >= ?
            """,
            (user_id, mastery_min_correct, mastery_min_interval_days),
        ).fetchone()["c"]

        seven_day = conn.execute(
            """
            SELECT COALESCE(SUM(correct_guesses), 0) AS correct_total,
                   COALESCE(SUM(correct_guesses + wrong_guesses), 0) AS attempts_total
            FROM games
            WHERE user_id = ?
              AND ended_at IS NOT NULL
              AND ended_at >= datetime('now', '-7 days')
            """,
            (user_id,),
        ).fetchone()

        attempts_total = int(seven_day["attempts_total"] or 0)
        correct_total = int(seven_day["correct_total"] or 0)
        accuracy_7d = (correct_total / attempts_total) if attempts_total > 0 else None

        theme_rows = conn.execute(
            """
            SELECT t.id AS theme_id,
                   t.name AS theme_name,
                   COUNT(CASE WHEN wp.times_seen > 0 THEN 1 END) AS words_seen,
                   COUNT(CASE WHEN wp.times_correct >= ? AND wp.interval_days >= ? THEN 1 END) AS words_mastered
            FROM themes t
            JOIN words w ON w.theme_id = t.id
            LEFT JOIN word_progress wp ON wp.word_id = w.id AND wp.user_id = ?
            GROUP BY t.id, t.name
            HAVING words_seen > 0
            ORDER BY t.name
            """,
            (mastery_min_correct, mastery_min_interval_days, user_id),
        ).fetchall()

        theme_accuracy_rows = conn.execute(
            """
            SELECT theme_id,
                   COALESCE(SUM(correct_guesses), 0) AS correct_total,
                   COALESCE(SUM(correct_guesses + wrong_guesses), 0) AS attempts_total
            FROM games
            WHERE user_id = ?
              AND ended_at IS NOT NULL
              AND ended_at >= datetime('now', '-7 days')
            GROUP BY theme_id
            """,
            (user_id,),
        ).fetchall()
        accuracy_by_theme = {
            int(row["theme_id"]): (
                (int(row["correct_total"]) / int(row["attempts_total"]))
                if int(row["attempts_total"]) > 0
                else None
            )
            for row in theme_accuracy_rows
            if row["theme_id"] is not None
        }

        themes = [
            {
                "theme_id": int(row["theme_id"]),
                "theme_name": row["theme_name"],
                "words_seen": int(row["words_seen"]),
                "words_mastered": int(row["words_mastered"]),
                "accuracy_7d": accuracy_by_theme.get(int(row["theme_id"])),
            }
            for row in theme_rows
        ]

        played_dates = [
            row["played_on"]
            for row in conn.execute(
                """
                SELECT DISTINCT DATE(ended_at) AS played_on
                FROM games
                WHERE user_id = ? AND ended_at IS NOT NULL
                ORDER BY played_on DESC
                """,
                (user_id,),
            ).fetchall()
            if row["played_on"]
        ]

        streak_days = 0
        if played_dates:
            from datetime import date, timedelta

            parsed = {date.fromisoformat(value) for value in played_dates}
            cursor = date.today()
            while cursor in parsed:
                streak_days += 1
                cursor = cursor - timedelta(days=1)

        return {
            "words_seen": int(words_seen),
            "words_mastered": int(words_mastered),
            "accuracy_7d": accuracy_7d,
            "themes": themes,
            "streak_days": streak_days,
            "mastery_rule": {
                "times_correct_gte": mastery_min_correct,
                "interval_days_gte": mastery_min_interval_days,
            },
        }
    finally:
        conn.close()


def initialize_and_seed(db_path: str = DEFAULT_DB_PATH, source_dirs: Iterable[str] | None = None) -> int:
    init_db(db_path)
    return seed_words_from_files(db_path=db_path, source_dirs=source_dirs)
