import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

DEFAULT_DB_PATH = "hangman.db"

# --- Leaderboard ranking algorithm (user-aggregated, time-decayed) ---
# leaderboard_score = decayed_game_sum + streak_bonus + daily_activity_bonus + challenge_bonus_hook
# - decayed_game_sum: SUM(score * POWER(decay_factor, age_in_days)) over games in period
# - Older scores diminish over time so new active users can climb; long-inactive users fall.
# - challenge_bonus_hook: reserved for future daily challenge (0 for now).
LEADERBOARD_DECAY_FACTOR = 0.94
LEADERBOARD_STREAK_BONUS_PER_DAY = 8
LEADERBOARD_STREAK_CAP_DAYS = 30
LEADERBOARD_DAILY_ACTIVITY_BONUS = 50
LEADERBOARD_CHALLENGE_BONUS_HOOK = 0  # Extension point for daily challenge
# By default, seed from top-level txt files in data/.
# Legacy sources under word/ or data/words/ are intentionally ignored.
DEFAULT_WORD_DIRS = ("data",)


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

CREATE TABLE IF NOT EXISTS user_word_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    word_id INTEGER NOT NULL,
    correct_count INTEGER NOT NULL DEFAULT 0,
    wrong_count INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT,
    next_review TEXT,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    interval INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, word_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_word_progress_next_review
ON user_word_progress(next_review);

CREATE INDEX IF NOT EXISTS idx_user_word_progress_user_id
ON user_word_progress(user_id);
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


def _ensure_user_word_progress_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_word_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            word_id INTEGER NOT NULL,
            correct_count INTEGER NOT NULL DEFAULT 0,
            wrong_count INTEGER NOT NULL DEFAULT 0,
            last_seen TEXT,
            next_review TEXT,
            ease_factor REAL NOT NULL DEFAULT 2.5,
            interval INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, word_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_word_progress_next_review
        ON user_word_progress(next_review)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_word_progress_user_id
        ON user_word_progress(user_id)
        """
    )


def _ensure_user_stats_table(conn: sqlite3.Connection) -> None:
    """User-aggregated stats for leaderboard: one row per user."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id INTEGER PRIMARY KEY,
            total_games INTEGER NOT NULL DEFAULT 0,
            total_score INTEGER NOT NULL DEFAULT 0,
            current_streak_days INTEGER NOT NULL DEFAULT 0,
            last_played_date TEXT,
            lifetime_xp REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_stats_last_played ON user_stats(last_played_date)"
    )


def _backfill_user_stats(conn: sqlite3.Connection) -> None:
    """One-time backfill: compute user_stats for users who have games but no row."""
    user_ids = conn.execute(
        "SELECT DISTINCT user_id FROM games WHERE user_id IS NOT NULL AND ended_at IS NOT NULL"
    ).fetchall()
    for row in user_ids:
        uid = row[0] if hasattr(row, '__getitem__') else row['user_id']
        if uid is None:
            continue
        user_id = int(uid)
        exists = conn.execute("SELECT 1 FROM user_stats WHERE user_id = ?", (user_id,)).fetchone()
        if exists:
            continue
        rows = conn.execute(
            """
            SELECT score, date(ended_at) AS d
            FROM games WHERE user_id = ? AND ended_at IS NOT NULL AND score IS NOT NULL
            ORDER BY d
            """,
            (user_id,),
        ).fetchall()
        if not rows:
            continue
        total_games = len(rows)
        total_score = sum(int(r["score"]) for r in rows)
        dates_ordered = [date.fromisoformat(r["d"]) for r in rows]
        last_d = dates_ordered[-1]
        streak = 0
        d = last_d
        while d in set(dates_ordered):
            streak += 1
            d -= timedelta(days=1)
        lifetime_xp = _compute_decayed_sum([(int(r["score"]), date.fromisoformat(r["d"])) for r in rows], last_d)
        conn.execute(
            """
            INSERT INTO user_stats (user_id, total_games, total_score, current_streak_days, last_played_date, lifetime_xp, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, total_games, total_score, streak, last_d.isoformat(), lifetime_xp, last_d.isoformat()),
        )


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        _ensure_users_password_hash_column(conn)
        _migrate_legacy_word_progress(conn)
        _ensure_games_columns(conn)
        _ensure_user_word_progress_table(conn)
        _ensure_user_stats_table(conn)
        _backfill_user_stats(conn)
        conn.commit()
    finally:
        conn.close()


def _collect_word_files(source_dirs: Iterable[str] | None = None) -> list[Path]:
    """
    Collect word list files from the configured directories.

    Only immediate *.txt files in each directory are used. This intentionally
    ignores legacy nested locations like data/words/ and word/.
    """
    dirs = source_dirs or DEFAULT_WORD_DIRS
    files: list[Path] = []
    for directory in dirs:
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            continue
        # Only top-level txt files, no recursion into subdirectories.
        files.extend(sorted(path.glob("*.txt")))
    return files


def _theme_name_from_file_path(file_path: Path) -> str:
    """Derive theme name from vocabulary file name (e.g. ket_animals.txt -> KET_ANIMALS)."""
    return file_path.stem.upper()


def seed_words_from_files(db_path: str = DEFAULT_DB_PATH, source_dirs: Iterable[str] | None = None) -> int:
    """
    Seed themes and words from data/*.txt. Each file defines one theme (name = file stem).
    Every word from that file is bound to that theme in the DB.
    """
    files = _collect_word_files(source_dirs)
    if not files:
        return 0

    conn = get_connection(db_path)
    inserted_words = 0
    try:
        for file_path in files:
            theme_name = _theme_name_from_file_path(file_path)
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


def clear_themes_and_words(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Remove all themes and words and dependent gameplay data so that the
    vocabulary can be reseeded from the current data/*.txt files.
    """
    conn = get_connection(db_path)
    try:
        # Dependent tables first because of foreign keys.
        conn.execute("DELETE FROM word_progress")
        conn.execute("DELETE FROM leaderboard_entries")
        conn.execute("DELETE FROM games")
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM themes")
        conn.commit()
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


def get_theme_name_by_id(db_path: str, theme_id: int) -> str | None:
    """Return the theme name for the given theme id, or None if not found."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT name FROM themes WHERE id = ?",
            (theme_id,),
        ).fetchone()
        return row["name"] if row else None
    finally:
        conn.close()


def theme_display_name(theme_name: str) -> str:
    """Return a short display label (e.g. KET_ANIMALS -> Animals)."""
    if not theme_name:
        return "Vocabulary"
    parts = theme_name.strip().split("_")
    return parts[-1].title() if parts else theme_name


def get_random_word(db_path: str = DEFAULT_DB_PATH) -> dict[str, str] | None:
    """
    Return a random word with its theme name, or None if there are no words.
    Returns dict with keys: value, theme (themes.name).
    """
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT w.value, t.name AS theme
            FROM words w
            JOIN themes t ON t.id = w.theme_id
            ORDER BY RANDOM() LIMIT 1
            """,
        ).fetchone()
        return dict(row) if row else None
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


def get_user_word_progress(db_path: str, user_id: int, word_id: int) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            """
            SELECT id,
                   user_id,
                   word_id,
                   correct_count,
                   wrong_count,
                   last_seen,
                   next_review,
                   ease_factor,
                   interval,
                   created_at,
                   updated_at
            FROM user_word_progress
            WHERE user_id = ? AND word_id = ?
            """,
            (user_id, word_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_user_word_progress(db_path: str, user_id: int, word_id: int) -> dict:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO user_word_progress (user_id, word_id)
            VALUES (?, ?)
            """,
            (user_id, word_id),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT id,
                   user_id,
                   word_id,
                   correct_count,
                   wrong_count,
                   last_seen,
                   next_review,
                   ease_factor,
                   interval,
                   created_at,
                   updated_at
            FROM user_word_progress
            WHERE user_id = ? AND word_id = ?
            """,
            (user_id, word_id),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def update_user_word_progress(
    db_path: str,
    user_id: int,
    word_id: int,
    *,
    correct_count: int | None = None,
    wrong_count: int | None = None,
    last_seen: str | None = None,
    next_review: str | None = None,
    ease_factor: float | None = None,
    interval: int | None = None,
) -> dict:
    updates: dict[str, object] = {}
    if correct_count is not None:
        updates["correct_count"] = correct_count
    if wrong_count is not None:
        updates["wrong_count"] = wrong_count
    if last_seen is not None:
        updates["last_seen"] = last_seen
    if next_review is not None:
        updates["next_review"] = next_review
    if ease_factor is not None:
        updates["ease_factor"] = ease_factor
    if interval is not None:
        updates["interval"] = interval

    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO user_word_progress (user_id, word_id)
            VALUES (?, ?)
            """,
            (user_id, word_id),
        )

        if updates:
            assignments = ", ".join([f"{column} = ?" for column in updates])
            values = [*updates.values(), user_id, word_id]
            conn.execute(
                f"""
                UPDATE user_word_progress
                SET {assignments}, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND word_id = ?
                """,
                values,
            )

        conn.commit()
        row = conn.execute(
            """
            SELECT id,
                   user_id,
                   word_id,
                   correct_count,
                   wrong_count,
                   last_seen,
                   next_review,
                   ease_factor,
                   interval,
                   created_at,
                   updated_at
            FROM user_word_progress
            WHERE user_id = ? AND word_id = ?
            """,
            (user_id, word_id),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def _parse_played_date(played_dt: datetime | date | None) -> date | None:
    """Normalize to date for streak comparison. Testable."""
    if played_dt is None:
        return None
    if isinstance(played_dt, datetime):
        return played_dt.date()
    return played_dt


def _streak_after_play(
    last_played_date: date | None, current_streak_days: int, play_date: date
) -> int:
    """
    Streak rules:
    - First play ever or gap > 1 day -> 1.
    - Played yesterday -> streak + 1.
    - Already played today -> streak unchanged (no double-increment).
    """
    if last_played_date is None:
        return 1
    delta = (play_date - last_played_date).days
    if delta == 0:
        return current_streak_days
    if delta == 1:
        return current_streak_days + 1
    return 1


def _compute_decayed_sum(scores_with_dates: list[tuple[int, date]], ref_date: date) -> float:
    """Sum of score * POWER(decay_factor, age_in_days). Used for lifetime_xp and period windows."""
    total = 0.0
    for score_val, end_date in scores_with_dates:
        age_days = (ref_date - end_date).days
        if age_days < 0:
            age_days = 0
        total += score_val * (LEADERBOARD_DECAY_FACTOR ** age_days)
    return total


def _streak_bonus(streak_days: int) -> float:
    """min(current_streak_days, 30) * 8."""
    return min(streak_days, LEADERBOARD_STREAK_CAP_DAYS) * LEADERBOARD_STREAK_BONUS_PER_DAY


def _daily_activity_bonus(last_played_date: date | None, ref_date: date) -> float:
    """50 if user played on ref_date (today), else 0."""
    if last_played_date is None:
        return 0.0
    return float(LEADERBOARD_DAILY_ACTIVITY_BONUS) if last_played_date == ref_date else 0.0


def upsert_user_stats_after_game(
    conn: sqlite3.Connection,
    user_id: int,
    game_score: int,
    played_dt: datetime | date | None = None,
) -> dict:
    """
    Update user_stats after a completed game: total_games, total_score, streak, last_played_date.
    Recomputes lifetime_xp (decayed sum of all games). Uses played_dt for streak; defaults to now.
    """
    now = played_dt or datetime.utcnow()
    play_date = _parse_played_date(now)
    if play_date is None:
        play_date = date.today()
    date_str = play_date.isoformat()

    row = conn.execute(
        "SELECT total_games, total_score, current_streak_days, last_played_date FROM user_stats WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if row is None:
        conn.execute(
            """
            INSERT INTO user_stats (user_id, total_games, total_score, current_streak_days, last_played_date, lifetime_xp, updated_at)
            VALUES (?, 1, ?, 1, ?, ?, ?)
            """,
            (user_id, game_score, date_str, float(game_score), date_str),
        )
        return {
            "user_id": user_id,
            "total_games": 1,
            "total_score": game_score,
            "current_streak_days": 1,
            "last_played_date": date_str,
            "lifetime_xp": float(game_score),
        }
    total_games = int(row["total_games"]) + 1
    total_score = int(row["total_score"]) + game_score
    last_played = row["last_played_date"]
    last_date = date.fromisoformat(last_played) if last_played else None
    current_streak = int(row["current_streak_days"])
    new_streak = _streak_after_play(last_date, current_streak, play_date)

    # Recompute lifetime_xp from all games (decayed sum)
    games_rows = conn.execute(
        """
        SELECT g.score, date(g.ended_at) AS d
        FROM games g
        WHERE g.user_id = ? AND g.ended_at IS NOT NULL AND g.score IS NOT NULL
        """,
        (user_id,),
    ).fetchall()
    scores_with_dates = [(int(r["score"]), date.fromisoformat(r["d"])) for r in games_rows]
    lifetime_xp = _compute_decayed_sum(scores_with_dates, play_date)

    conn.execute(
        """
        UPDATE user_stats
        SET total_games = ?, total_score = ?, current_streak_days = ?, last_played_date = ?, lifetime_xp = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (total_games, total_score, new_streak, date_str, lifetime_xp, date_str, user_id),
    )
    return {
        "user_id": user_id,
        "total_games": total_games,
        "total_score": total_score,
        "current_streak_days": new_streak,
        "last_played_date": date_str,
        "lifetime_xp": lifetime_xp,
    }


def list_leaderboard_aggregated(
    db_path: str,
    *,
    period: str = "all",
    limit: int = 50,
    ref_date: date | None = None,
    current_user_id: int | None = None,
) -> list[dict]:
    """
    Per-user leaderboard with aggregated score. One row per user.
    leaderboard_score = decayed_sum + streak_bonus + daily_activity_bonus + challenge_bonus_hook.
    period: 'today' | 'week' | 'all'. ref_date: reference date for decay/today (default today).
    """
    ref = ref_date or date.today()
    limit = max(1, min(100, int(limit)))
    conn = get_connection(db_path)
    try:
        # All users who have user_stats (have played at least one game)
        stats_rows = conn.execute(
            """
            SELECT s.user_id, u.username,
                   s.total_games, s.total_score, s.current_streak_days, s.last_played_date, s.lifetime_xp
            FROM user_stats s
            JOIN users u ON u.id = s.user_id
            """
        ).fetchall()

        ref_ts = ref.isoformat()
        ref_week_start = (ref - timedelta(days=ref.weekday())).isoformat() if period == "week" else None
        # For week we use last 7 days from ref
        week_start_date = ref - timedelta(days=6) if period == "week" else None

        scores_list: list[tuple[int, str, float, int, str | None]] = []

        for row in stats_rows:
            user_id = int(row["user_id"])
            username = row["username"] or "Guest"
            streak_days = int(row["current_streak_days"])
            last_played = row["last_played_date"]
            last_played_date = date.fromisoformat(last_played) if last_played else None

            if period == "all":
                decayed_sum = float(row["lifetime_xp"])
            else:
                if period == "today":
                    games_sql = """
                        SELECT score, date(ended_at) AS d FROM games
                        WHERE user_id = ? AND ended_at IS NOT NULL AND score IS NOT NULL
                        AND date(ended_at) = ?
                    """
                    games_params = (user_id, ref_ts)
                else:
                    games_sql = """
                        SELECT score, date(ended_at) AS d FROM games
                        WHERE user_id = ? AND ended_at IS NOT NULL AND score IS NOT NULL
                        AND date(ended_at) >= ?
                    """
                    games_params = (user_id, week_start_date.isoformat())
                game_rows = conn.execute(games_sql, games_params).fetchall()
                scores_with_dates = [(int(r["score"]), date.fromisoformat(r["d"])) for r in game_rows]
                decayed_sum = _compute_decayed_sum(scores_with_dates, ref)

            streak_b = _streak_bonus(streak_days)
            daily_b = _daily_activity_bonus(last_played_date, ref)
            challenge_b = LEADERBOARD_CHALLENGE_BONUS_HOOK
            leaderboard_score = decayed_sum + streak_b + daily_b + challenge_b
            scores_list.append((user_id, username, leaderboard_score, streak_days, last_played))

        scores_list.sort(key=lambda x: -x[2])
        entries = []
        for rank, (uid, uname, lb_score, streak, last_active) in enumerate(scores_list[:limit], start=1):
            entries.append({
                "user_id": uid,
                "username": uname,
                "rank": rank,
                "leaderboard_score": round(lb_score, 1),
                "current_streak_days": streak,
                "last_active": last_active,
                "is_current_user": current_user_id is not None and uid == current_user_id,
            })
        return entries
    finally:
        conn.close()


def get_user_leaderboard_rank(
    db_path: str, user_id: int, *, period: str = "all", ref_date: date | None = None
) -> dict | None:
    """Return rank, leaderboard_score, current_streak_days for user in the aggregated leaderboard."""
    entries = list_leaderboard_aggregated(
        db_path, period=period, limit=500, ref_date=ref_date, current_user_id=user_id
    )
    for e in entries:
        if e["user_id"] == user_id:
            return {
                "rank": e["rank"],
                "leaderboard_score": e["leaderboard_score"],
                "current_streak_days": e["current_streak_days"],
                "last_active": e["last_active"],
            }
    return None


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


def get_progress_summary(db_path: str, user_id: int) -> dict:
    """Return progress summary for the dashboard: words_seen, words_mastered, accuracy_7d, streak_days, themes."""
    conn = get_connection(db_path)
    try:
        # Words seen: distinct words in word_progress
        row = conn.execute(
            "SELECT COUNT(DISTINCT word_id) AS words_seen FROM word_progress WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        words_seen = row["words_seen"] or 0

        # Words mastered: completed a game with fewer than 3 wrong letters (0, 1, or 2)
        mastered_row = conn.execute(
            """
            SELECT COUNT(DISTINCT word_id) AS words_mastered
            FROM games
            WHERE user_id = ? AND ended_at IS NOT NULL AND wrong_guesses < 3
            """,
            (user_id,),
        ).fetchone()
        words_mastered = int(mastered_row["words_mastered"] or 0)

        # Accuracy over last 7 days (completed games only)
        acc_row = conn.execute(
            """
            SELECT SUM(correct_guesses) AS total_correct, SUM(wrong_guesses) AS total_wrong
            FROM games
            WHERE user_id = ? AND ended_at IS NOT NULL AND ended_at >= datetime('now', '-7 days')
            """,
            (user_id,),
        ).fetchone()
        total_correct = acc_row["total_correct"] or 0
        total_wrong = acc_row["total_wrong"] or 0
        total_guesses = total_correct + total_wrong
        accuracy_7d = (total_correct / total_guesses) if total_guesses > 0 else 0.0

        # Streak: consecutive days with at least one completed game
        date_rows = conn.execute(
            """
            SELECT DISTINCT date(ended_at) AS d
            FROM games
            WHERE user_id = ? AND ended_at IS NOT NULL
            ORDER BY d DESC
            """,
            (user_id,),
        ).fetchall()
        game_dates = {date.fromisoformat(r["d"]) for r in date_rows}
        streak_days = 0
        if game_dates:
            d = max(game_dates)
            while d in game_dates:
                streak_days += 1
                d -= timedelta(days=1)

        # Per-theme breakdown: words_seen, words_mastered (wrong_guesses < 3), accuracy_7d
        theme_rows = conn.execute(
            """
            SELECT
                t.id AS theme_id,
                t.name AS theme_name,
                COUNT(DISTINCT wp.word_id) AS words_seen,
                (SELECT COUNT(DISTINCT g.word_id) FROM games g
                 WHERE g.user_id = ? AND g.ended_at IS NOT NULL AND g.wrong_guesses < 3 AND g.theme_id = t.id) AS words_mastered,
                (SELECT CASE WHEN SUM(g.correct_guesses) + SUM(g.wrong_guesses) > 0
                    THEN SUM(g.correct_guesses) * 1.0 / (SUM(g.correct_guesses) + SUM(g.wrong_guesses)) ELSE NULL END
                 FROM games g
                 WHERE g.user_id = ? AND g.ended_at IS NOT NULL AND g.ended_at >= datetime('now', '-7 days') AND g.theme_id = t.id) AS accuracy_7d
            FROM word_progress wp
            JOIN words w ON w.id = wp.word_id
            JOIN themes t ON t.id = w.theme_id
            WHERE wp.user_id = ?
            GROUP BY t.id, t.name
            ORDER BY t.name
            """,
            (user_id, user_id, user_id),
        ).fetchall()
        themes = []
        for row in theme_rows:
            acc = row["accuracy_7d"]
            themes.append({
                "theme_name": row["theme_name"],
                "words_seen": row["words_seen"],
                "words_mastered": int(row["words_mastered"] or 0),
                "accuracy_7d": round(acc, 4) if acc is not None else None,
            })

        return {
            "words_seen": words_seen,
            "words_mastered": words_mastered,
            "accuracy_7d": round(accuracy_7d, 4),
            "streak_days": streak_days,
            "mastery_rule": {"wrong_guesses_lt": 3},
            "themes": themes,
        }
    finally:
        conn.close()


def initialize_and_seed(db_path: str = DEFAULT_DB_PATH, source_dirs: Iterable[str] | None = None) -> int:
    """
    Initialize schema and reseed vocabulary words from the current data files.

    This clears themes/words and dependent gameplay tables so that legacy
    word sources (e.g. word/ or data/words/) are removed from the database.
    """
    init_db(db_path)
    clear_themes_and_words(db_path)
    return seed_words_from_files(db_path=db_path, source_dirs=source_dirs)
