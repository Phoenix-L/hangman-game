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


def _iso_now(now: datetime | None = None) -> str:
    return (now or datetime.utcnow()).replace(microsecond=0).isoformat(sep=' ')


def _to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


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
    return [int(row["word_id"]) for row in rows]


def _fetch_candidates(conn: sqlite3.Connection, theme_id: int, excluded_word_ids: list[int]) -> list[sqlite3.Row]:
    if excluded_word_ids:
        placeholders = ','.join('?' for _ in excluded_word_ids)
        query = f"SELECT id, theme_id, value FROM words WHERE theme_id = ? AND id NOT IN ({placeholders})"
        return conn.execute(query, (theme_id, *excluded_word_ids)).fetchall()
    return conn.execute(
        "SELECT id, theme_id, value FROM words WHERE theme_id = ?",
        (theme_id,),
    ).fetchall()


def _pick_due(conn: sqlite3.Connection, user_id: int, theme_id: int, excluded_word_ids: list[int], now_text: str) -> sqlite3.Row | None:
    base = """
        SELECT w.id, w.theme_id, w.value, p.next_review_at, p.times_wrong
        FROM words w
        JOIN word_progress p ON p.word_id = w.id AND p.user_id = ?
        WHERE w.theme_id = ? AND p.times_seen > 0 AND p.next_review_at IS NOT NULL AND p.next_review_at <= ?
    """
    params: list[Any] = [user_id, theme_id, now_text]
    if excluded_word_ids:
        placeholders = ','.join('?' for _ in excluded_word_ids)
        base += f" AND w.id NOT IN ({placeholders})"
        params.extend(excluded_word_ids)
    base += " ORDER BY p.next_review_at ASC, p.times_wrong DESC, w.id ASC LIMIT 1"
    return conn.execute(base, params).fetchone()


def _pick_missed(conn: sqlite3.Connection, user_id: int, theme_id: int, excluded_word_ids: list[int]) -> sqlite3.Row | None:
    base = """
        SELECT w.id, w.theme_id, w.value, p.times_wrong, p.last_seen_at
        FROM words w
        JOIN word_progress p ON p.word_id = w.id AND p.user_id = ?
        WHERE w.theme_id = ? AND p.times_wrong > 0
    """
    params: list[Any] = [user_id, theme_id]
    if excluded_word_ids:
        placeholders = ','.join('?' for _ in excluded_word_ids)
        base += f" AND w.id NOT IN ({placeholders})"
        params.extend(excluded_word_ids)
    base += " ORDER BY p.times_wrong DESC, p.last_seen_at ASC, w.id ASC LIMIT 1"
    return conn.execute(base, params).fetchone()


def _pick_new(conn: sqlite3.Connection, user_id: int, theme_id: int, excluded_word_ids: list[int], rng: random.Random) -> sqlite3.Row | None:
    base = """
        SELECT w.id, w.theme_id, w.value
        FROM words w
        LEFT JOIN word_progress p ON p.word_id = w.id AND p.user_id = ?
        WHERE w.theme_id = ? AND (p.word_id IS NULL OR p.times_seen = 0)
    """
    params: list[Any] = [user_id, theme_id]
    if excluded_word_ids:
        placeholders = ','.join('?' for _ in excluded_word_ids)
        base += f" AND w.id NOT IN ({placeholders})"
        params.extend(excluded_word_ids)
    rows = conn.execute(base, params).fetchall()
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
    rng = rng or random.Random()
    now_text = _iso_now(now)

    recent_ids = _recent_word_ids(conn, user_id, recent_games_limit)

    due = _pick_due(conn, user_id, theme_id, recent_ids, now_text)
    if due:
        return SelectionResult(word=dict(due), reason='due_review')

    missed = _pick_missed(conn, user_id, theme_id, recent_ids)
    if missed:
        return SelectionResult(word=dict(missed), reason='high_mistake')

    new_word = _pick_new(conn, user_id, theme_id, recent_ids, rng)
    if new_word:
        return SelectionResult(word=dict(new_word), reason='new_word')

    fallback_candidates = _fetch_candidates(conn, theme_id, [])
    if not fallback_candidates:
        return SelectionResult(word=None, reason='no_words')
    picked = fallback_candidates[rng.randrange(len(fallback_candidates))]
    return SelectionResult(word=dict(picked), reason='fallback_random')


def select_guest_word(conn: sqlite3.Connection, theme_id: int, rng: random.Random | None = None) -> SelectionResult:
    rng = rng or random.Random()
    rows = conn.execute(
        "SELECT id, theme_id, value FROM words WHERE theme_id = ?",
        (theme_id,),
    ).fetchall()
    if not rows:
        return SelectionResult(word=None, reason='no_words')
    return SelectionResult(word=dict(rows[rng.randrange(len(rows))]), reason='guest_random')


def update_word_progress(
    conn: sqlite3.Connection,
    user_id: int,
    word_id: int,
    *,
    was_correct: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    now_dt = (now or datetime.utcnow()).replace(microsecond=0)
    now_text = now_dt.isoformat(sep=' ')

    existing = conn.execute(
        """
        SELECT user_id, word_id, times_seen, times_correct, times_wrong, last_seen_at,
               interval_days, next_review_at
        FROM word_progress
        WHERE user_id = ? AND word_id = ?
        """,
        (user_id, word_id),
    ).fetchone()

    if existing:
        times_seen = int(existing['times_seen']) + 1
        times_correct = int(existing['times_correct']) + (1 if was_correct else 0)
        times_wrong = int(existing['times_wrong']) + (0 if was_correct else 1)
        previous_interval = int(existing['interval_days'] or 1)
    else:
        times_seen = 1
        times_correct = 1 if was_correct else 0
        times_wrong = 0 if was_correct else 1
        previous_interval = 1

    interval_days = min(30, max(1, previous_interval * 2)) if was_correct else 1
    next_review_at = (now_dt + timedelta(days=interval_days)).isoformat(sep=' ')

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
        (
            user_id,
            word_id,
            times_seen,
            times_correct,
            times_wrong,
            now_text,
            interval_days,
            next_review_at,
        ),
    )
    conn.commit()

    return {
        'user_id': user_id,
        'word_id': word_id,
        'times_seen': times_seen,
        'times_correct': times_correct,
        'times_wrong': times_wrong,
        'last_seen_at': now_text,
        'interval_days': interval_days,
        'next_review_at': next_review_at,
    }
