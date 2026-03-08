from datetime import datetime, timedelta
import random

from db import get_connection, init_db
from engine.word_selector import (
    select_due_review_words,
    select_difficult_words,
    select_guest_word,
    select_new_words,
    select_next_word,
    update_word_progress,
)


def _setup_user_theme_words(db_path: str):
    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ("u1", "x"))
        user_id = conn.execute("SELECT id FROM users WHERE username='u1'").fetchone()["id"]

        conn.execute("INSERT INTO themes (name, description) VALUES (?, ?)", ("TEST", "test theme"))
        conn.execute("INSERT INTO themes (name, description) VALUES (?, ?)", ("OTHER", "other theme"))
        theme_id = conn.execute("SELECT id FROM themes WHERE name='TEST'").fetchone()["id"]
        other_theme_id = conn.execute("SELECT id FROM themes WHERE name='OTHER'").fetchone()["id"]

        for value in ["alpha", "bravo", "charlie", "delta"]:
            conn.execute("INSERT INTO words (theme_id, value) VALUES (?, ?)", (theme_id, value))
        conn.execute("INSERT INTO words (theme_id, value) VALUES (?, ?)", (other_theme_id, "zebra"))

        words = conn.execute("SELECT id, value FROM words WHERE theme_id = ? ORDER BY id", (theme_id,)).fetchall()
        word_map = {row['value']: row['id'] for row in words}
        conn.commit()
        return user_id, theme_id, other_theme_id, word_map
    finally:
        conn.close()


def test_selection_ordering_review_then_difficult_then_new(tmp_path):
    db_path = str(tmp_path / 'selector.db')
    init_db(db_path)
    user_id, theme_id, _other_theme_id, word_map = _setup_user_theme_words(db_path)

    now = datetime(2025, 1, 10, 12, 0, 0)
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO user_word_progress (user_id, word_id, correct_count, wrong_count, last_seen, next_review, ease_factor, interval)
            VALUES (?, ?, 2, 1, ?, ?, 2.5, 2)
            """,
            (user_id, word_map['alpha'], (now - timedelta(days=2)).isoformat(sep=' '), (now - timedelta(hours=1)).isoformat(sep=' ')),
        )
        conn.execute(
            """
            INSERT INTO user_word_progress (user_id, word_id, correct_count, wrong_count, last_seen, next_review, ease_factor, interval)
            VALUES (?, ?, 1, 4, ?, ?, 2.1, 3)
            """,
            (user_id, word_map['bravo'], (now - timedelta(days=1)).isoformat(sep=' '), (now + timedelta(days=2)).isoformat(sep=' ')),
        )
        conn.commit()

        first = select_next_word(conn, user_id=user_id, theme_id=theme_id, now=now, rng=random.Random(7))
        assert first.reason == 'review'
        assert first.word['id'] == word_map['alpha']

        conn.execute(
            "UPDATE user_word_progress SET next_review = ? WHERE user_id = ? AND word_id = ?",
            ((now + timedelta(days=2)).isoformat(sep=' '), user_id, word_map['alpha']),
        )
        conn.commit()

        second = select_next_word(conn, user_id=user_id, theme_id=theme_id, now=now, rng=random.Random(7))
        assert second.reason == 'difficult'
        assert second.word['id'] == word_map['bravo']

        conn.execute("UPDATE user_word_progress SET wrong_count = 0 WHERE user_id = ?", (user_id,))
        conn.commit()

        third = select_next_word(conn, user_id=user_id, theme_id=theme_id, now=now, rng=random.Random(1))
        assert third.reason == 'new'
        assert third.word['id'] in {word_map['charlie'], word_map['delta']}
    finally:
        conn.close()


def test_spaced_repetition_progress_updates(tmp_path):
    db_path = str(tmp_path / 'progress.db')
    init_db(db_path)
    user_id, _theme_id, _other_theme_id, word_map = _setup_user_theme_words(db_path)

    conn = get_connection(db_path)
    try:
        t1 = datetime(2025, 1, 1, 8, 0, 0)
        p1 = update_word_progress(conn, user_id=user_id, word_id=word_map['alpha'], was_correct=True, now=t1)
        assert p1['correct_count'] == 1
        assert p1['wrong_count'] == 0
        assert p1['interval'] >= 2
        assert p1['ease_factor'] >= 2.5

        t2 = datetime(2025, 1, 2, 8, 0, 0)
        p2 = update_word_progress(conn, user_id=user_id, word_id=word_map['alpha'], was_correct=True, now=t2)
        assert p2['correct_count'] == 2
        assert p2['interval'] > p1['interval']

        t3 = datetime(2025, 1, 3, 8, 0, 0)
        p3 = update_word_progress(conn, user_id=user_id, word_id=word_map['alpha'], was_correct=False, now=t3)
        assert p3['wrong_count'] == 1
        assert p3['interval'] == 1
        assert p3['next_review'].startswith('2025-01-04 08:00:00')

        row = conn.execute(
            "SELECT times_seen, times_correct, times_wrong FROM word_progress WHERE user_id = ? AND word_id = ?",
            (user_id, word_map['alpha']),
        ).fetchone()
        assert row['times_seen'] == 3
        assert row['times_correct'] == 2
        assert row['times_wrong'] == 1
    finally:
        conn.close()


def test_theme_filter_and_guest_mode(tmp_path):
    db_path = str(tmp_path / 'theme_and_guest.db')
    init_db(db_path)
    user_id, theme_id, other_theme_id, word_map = _setup_user_theme_words(db_path)

    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO user_word_progress (user_id, word_id, wrong_count, next_review)
            VALUES (?, ?, 5, ?)
            """,
            (user_id, word_map['alpha'], (datetime.utcnow() - timedelta(days=1)).replace(microsecond=0).isoformat(sep=' ')),
        )
        conn.commit()

        due = select_due_review_words(conn, user_id, theme_id)
        assert due and due[0]['id'] == word_map['alpha']

        difficult = select_difficult_words(conn, user_id, theme_id)
        assert difficult == []

        new_words = select_new_words(conn, user_id, theme_id)
        assert all(row['theme_id'] == theme_id for row in new_words)

        # Other theme should not leak
        other_pick = select_next_word(conn, user_id=user_id, theme_id=other_theme_id, rng=random.Random(2))
        assert other_pick.word['theme_id'] == other_theme_id

        guest_pick = select_guest_word(conn, theme_id=theme_id, rng=random.Random(5))
        assert guest_pick.reason == 'guest_random'
        assert guest_pick.word['theme_id'] == theme_id
    finally:
        conn.close()


def test_recent_history_avoidance(tmp_path):
    db_path = str(tmp_path / 'recent.db')
    init_db(db_path)
    user_id, theme_id, _other_theme_id, word_map = _setup_user_theme_words(db_path)

    conn = get_connection(db_path)
    try:
        now = datetime(2025, 2, 1, 9, 0, 0)
        for w in ['alpha', 'bravo', 'charlie']:
            conn.execute(
                "INSERT INTO games (user_id, word_id, theme_id, status, started_at) VALUES (?, ?, ?, 'won', ?)",
                (user_id, word_map[w], theme_id, now.isoformat(sep=' ')),
            )
        conn.commit()

        selected = select_next_word(conn, user_id=user_id, theme_id=theme_id, now=now, rng=random.Random(3))
        assert selected.word['id'] == word_map['delta']
    finally:
        conn.close()
