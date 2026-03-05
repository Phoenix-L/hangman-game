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
    status TEXT NOT NULL CHECK(status IN ('in_progress', 'won', 'lost')) DEFAULT 'in_progress',
    wrong_guesses INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS word_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    guessed_letter TEXT NOT NULL,
    was_correct INTEGER NOT NULL CHECK(was_correct IN (0, 1)),
    guessed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
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


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        _ensure_users_password_hash_column(conn)
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


def initialize_and_seed(db_path: str = DEFAULT_DB_PATH, source_dirs: Iterable[str] | None = None) -> int:
    init_db(db_path)
    return seed_words_from_files(db_path=db_path, source_dirs=source_dirs)
