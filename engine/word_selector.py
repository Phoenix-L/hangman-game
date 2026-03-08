from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import random
import sqlite3
from typing import Any


@dataclass
class SelectionResult:
    word: dict[str, Any] | None
    reason: str


def _to_db_ts(value: datetime | None = None) -> str:
    return (value or datetime.utcnow()).replace(microsecond=0).isoformat(sep=' ')


def _recent_word_ids(conn: sqlite3.Connection, user_id: int, limit: int) -> list[int]:
    rows = conn.execute(
        """
        SELECT word_id
        FROM games
        WHERE user_id = ? AND word_id IS NOT NULL
        ORDER BY started_at DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return [int(row['word_id']) for row in rows]


def _excluded_clause(excluded_word_ids: list[int]) -> tuple[str, list[int]]:
    if not excluded_word_ids:
        return "", []
    placeholders = ','.join('?' for _ in excluded_word_ids)
    return f" AND w.id NOT IN ({placeholders})", excluded_word_ids


def select_due_review_words(
    conn: sqlite3.Connection,
    user_id: int,
    theme_id: int,
    *,
    excluded_word_ids: list[int] | None = None,
    now: datetime | None = None,
    limit: int = 50,
) -> list[sqlite3.Row]:
    excluded_word_ids = excluded_word_ids or []
    excluded_sql, excluded_params = _excluded_clause(excluded_word_ids)
    now_text = _to_db_ts(now)
    return conn.execute(
        f"""
        SELECT w.id, w.theme_id, w.value,
               p.correct_count, p.wrong_count,
               p.last_seen, p.next_review, p.ease_factor, p.interval
        FROM words w
        JOIN user_word_progress p ON p.word_id = w.id AND p.user_id = ?
        WHERE w.theme_id = ?
          AND p.next_review IS NOT NULL
          AND p.next_review <= ?
          {excluded_sql}
        ORDER BY p.next_review ASC,
                 (p.wrong_count - p.correct_count) DESC,
                 w.id ASC
        LIMIT ?
        """,
        (user_id, theme_id, now_text, *excluded_params, limit),
    ).fetchall()


def select_difficult_words(
    conn: sqlite3.Connection,
    user_id: int,
    theme_id: int,
    *,
    excluded_word_ids: list[int] | None = None,
    now: datetime | None = None,
    limit: int = 50,
) -> list[sqlite3.Row]:
    """Words with poor history that are not due yet become secondary priority."""
    excluded_word_ids = excluded_word_ids or []
    excluded_sql, excluded_params = _excluded_clause(excluded_word_ids)
    now_text = _to_db_ts(now)
    return conn.execute(
        f"""
        SELECT w.id, w.theme_id, w.value,
               p.correct_count, p.wrong_count,
               p.last_seen, p.next_review, p.ease_factor, p.interval,
               CASE
                   WHEN (p.correct_count + p.wrong_count) = 0 THEN 0.0
                   ELSE (p.wrong_count * 1.0) / (p.correct_count + p.wrong_count)
               END AS fail_rate
        FROM words w
        JOIN user_word_progress p ON p.word_id = w.id AND p.user_id = ?
        WHERE w.theme_id = ?
          AND p.wrong_count > 0
          AND (p.next_review IS NULL OR p.next_review > ?)
          {excluded_sql}
        ORDER BY fail_rate DESC,
                 p.wrong_count DESC,
                 p.last_seen ASC,
                 w.id ASC
        LIMIT ?
        """,
        (user_id, theme_id, now_text, *excluded_params, limit),
    ).fetchall()


def select_new_words(
    conn: sqlite3.Connection,
    user_id: int,
    theme_id: int,
    *,
    excluded_word_ids: list[int] | None = None,
) -> list[sqlite3.Row]:
    excluded_word_ids = excluded_word_ids or []
    excluded_sql, excluded_params = _excluded_clause(excluded_word_ids)
    return conn.execute(
        f"""
        SELECT w.id, w.theme_id, w.value
        FROM words w
        LEFT JOIN user_word_progress p ON p.word_id = w.id AND p.user_id = ?
        WHERE w.theme_id = ?
          AND p.word_id IS NULL
          {excluded_sql}
        ORDER BY w.id ASC
        """,
        (user_id, theme_id, *excluded_params),
    ).fetchall()


def _pick_random(rows: list[sqlite3.Row], rng: random.Random) -> sqlite3.Row | None:
    if not rows:
        return None
    return rows[rng.randrange(len(rows))]


def select_next_word(
    conn: sqlite3.Connection,
    user_id: int,
    theme_id: int,
    *,
    recent_games_limit: int = 3,
    now: datetime | None = None,
    rng: random.Random | None = None,
) -> SelectionResult:
    """
    Selection priority:
    1) due review 2) difficult 3) unseen/new 4) random fallback.
    """
    rng = rng or random.Random()
    excluded_word_ids = _recent_word_ids(conn, user_id, recent_games_limit)

    due = select_due_review_words(conn, user_id, theme_id, excluded_word_ids=excluded_word_ids, now=now, limit=1)
    if due:
        return SelectionResult(word=dict(due[0]), reason='review')

    difficult = select_difficult_words(conn, user_id, theme_id, excluded_word_ids=excluded_word_ids, now=now, limit=1)
    if difficult:
        return SelectionResult(word=dict(difficult[0]), reason='difficult')

    new_words = select_new_words(conn, user_id, theme_id, excluded_word_ids=excluded_word_ids)
    picked_new = _pick_random(new_words, rng)
    if picked_new:
        return SelectionResult(word=dict(picked_new), reason='new')

    excluded_sql, excluded_params = _excluded_clause(excluded_word_ids)
    fallback_rows = conn.execute(
        f"SELECT w.id, w.theme_id, w.value FROM words w WHERE w.theme_id = ? {excluded_sql}",
        (theme_id, *excluded_params),
    ).fetchall()
    fallback = _pick_random(fallback_rows, rng)
    if fallback:
        return SelectionResult(word=dict(fallback), reason='random_fallback')
    return SelectionResult(word=None, reason='no_words')


def select_guest_word(conn: sqlite3.Connection, theme_id: int, rng: random.Random | None = None) -> SelectionResult:
    rng = rng or random.Random()
    rows = conn.execute(
        "SELECT id, theme_id, value FROM words WHERE theme_id = ?",
        (theme_id,),
    ).fetchall()
    picked = _pick_random(rows, rng)
    if not picked:
        return SelectionResult(word=None, reason='no_words')
    return SelectionResult(word=dict(picked), reason='guest_random')


def update_word_progress(
    conn: sqlite3.Connection,
    user_id: int,
    word_id: int,
    *,
    was_correct: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Simplified SM-2-like scheduling:
    - correct: interval grows by ease_factor; ease_factor nudges up (+0.05)
    - incorrect: interval resets to 1 day; ease_factor nudges down (-0.2)
    - ease_factor is clamped to [1.3, 3.0]
    """
    now_dt = (now or datetime.utcnow()).replace(microsecond=0)

    row = conn.execute(
        """
        SELECT correct_count, wrong_count, ease_factor, interval
        FROM user_word_progress
        WHERE user_id = ? AND word_id = ?
        """,
        (user_id, word_id),
    ).fetchone()

    if row is None:
        correct_count = 0
        wrong_count = 0
        ease_factor = 2.5
        interval_days = 1
        conn.execute(
            "INSERT INTO user_word_progress (user_id, word_id) VALUES (?, ?)",
            (user_id, word_id),
        )
    else:
        correct_count = int(row['correct_count'])
        wrong_count = int(row['wrong_count'])
        ease_factor = float(row['ease_factor'] or 2.5)
        interval_days = int(row['interval'] or 1)

    if was_correct:
        correct_count += 1
        ease_factor = min(3.0, ease_factor + 0.05)
        interval_days = max(1, int(round(interval_days * ease_factor)))
    else:
        wrong_count += 1
        ease_factor = max(1.3, ease_factor - 0.2)
        interval_days = 1

    last_seen = _to_db_ts(now_dt)
    next_review = _to_db_ts(now_dt + timedelta(days=interval_days))

    conn.execute(
        """
        UPDATE user_word_progress
        SET correct_count = ?,
            wrong_count = ?,
            last_seen = ?,
            next_review = ?,
            ease_factor = ?,
            interval = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND word_id = ?
        """,
        (correct_count, wrong_count, last_seen, next_review, ease_factor, interval_days, user_id, word_id),
    )

    # Keep legacy summary/dashboard behavior working for now.
    legacy = conn.execute(
        """
        SELECT times_seen, times_correct, times_wrong
        FROM word_progress
        WHERE user_id = ? AND word_id = ?
        """,
        (user_id, word_id),
    ).fetchone()
    if legacy is None:
        times_seen = 1
        times_correct = 1 if was_correct else 0
        times_wrong = 0 if was_correct else 1
    else:
        times_seen = int(legacy['times_seen']) + 1
        times_correct = int(legacy['times_correct']) + (1 if was_correct else 0)
        times_wrong = int(legacy['times_wrong']) + (0 if was_correct else 1)

    conn.execute(
        """
        INSERT INTO word_progress (
            user_id, word_id, times_seen, times_correct, times_wrong,
            last_seen_at, interval_days, next_review_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, word_id) DO UPDATE SET
            times_seen = excluded.times_seen,
            times_correct = excluded.times_correct,
            times_wrong = excluded.times_wrong,
            last_seen_at = excluded.last_seen_at,
            interval_days = excluded.interval_days,
            next_review_at = excluded.next_review_at
        """,
        (user_id, word_id, times_seen, times_correct, times_wrong, last_seen, interval_days, next_review),
    )

    return {
        'user_id': user_id,
        'word_id': word_id,
        'correct_count': correct_count,
        'wrong_count': wrong_count,
        'last_seen': last_seen,
        'next_review': next_review,
        'ease_factor': round(ease_factor, 4),
        'interval': interval_days,
        # legacy mirrors
        'times_seen': times_seen,
        'times_correct': times_correct,
        'times_wrong': times_wrong,
        'interval_days': interval_days,
        'next_review_at': next_review,
    }
