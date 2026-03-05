from datetime import datetime, timedelta
import random

from db import get_connection, init_db
from engine.word_selector import select_next_word, update_word_progress


def _setup_user_theme_words(db_path: str):
    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ("u1", "x"))
        user_id = conn.execute("SELECT id FROM users WHERE username='u1'").fetchone()["id"]

        conn.execute("INSERT INTO themes (name, description) VALUES (?, ?)", ("TEST", "test theme"))
        theme_id = conn.execute("SELECT id FROM themes WHERE name='TEST'").fetchone()["id"]

        for value in ["alpha", "bravo", "charlie", "delta"]:
            conn.execute("INSERT INTO words (theme_id, value) VALUES (?, ?)", (theme_id, value))

        words = conn.execute("SELECT id, value FROM words WHERE theme_id = ? ORDER BY id", (theme_id,)).fetchall()
        word_map = {row['value']: row['id'] for row in words}
        conn.commit()
        return user_id, theme_id, word_map
    finally:
        conn.close()


def test_selection_ordering_due_then_missed_then_new(tmp_path):
    db_path = str(tmp_path / 'selector.db')
    init_db(db_path)
    user_id, theme_id, word_map = _setup_user_theme_words(db_path)

    now = datetime(2025, 1, 10, 12, 0, 0)
    conn = get_connection(db_path)
    try:
        # due word
        conn.execute(
            """
            INSERT INTO word_progress (user_id, word_id, times_seen, times_correct, times_wrong, last_seen_at, interval_days, next_review_at)
            VALUES (?, ?, 3, 2, 1, ?, 2, ?)
            """,
            (user_id, word_map['alpha'], (now - timedelta(days=2)).isoformat(sep=' '), (now - timedelta(hours=1)).isoformat(sep=' ')),
        )
        # high-mistake word not due yet
        conn.execute(
            """
            INSERT INTO word_progress (user_id, word_id, times_seen, times_correct, times_wrong, last_seen_at, interval_days, next_review_at)
            VALUES (?, ?, 5, 2, 3, ?, 3, ?)
            """,
            (user_id, word_map['bravo'], (now - timedelta(days=1)).isoformat(sep=' '), (now + timedelta(days=2)).isoformat(sep=' ')),
        )
        conn.commit()

        first = select_next_word(conn, user_id=user_id, theme_id=theme_id, now=now, rng=random.Random(7))
        assert first.reason == 'due_review'
        assert first.word['id'] == word_map['alpha']

        # Remove due condition and verify high-mistake becomes next
        conn.execute(
            "UPDATE word_progress SET next_review_at = ? WHERE user_id = ? AND word_id = ?",
            ((now + timedelta(days=2)).isoformat(sep=' '), user_id, word_map['alpha']),
        )
        conn.commit()

        second = select_next_word(conn, user_id=user_id, theme_id=theme_id, now=now, rng=random.Random(7))
        assert second.reason == 'high_mistake'
        assert second.word['id'] == word_map['bravo']

        # Clear mistakes to force new word
        conn.execute("UPDATE word_progress SET times_wrong = 0 WHERE user_id = ?", (user_id,))
        conn.commit()

        third = select_next_word(conn, user_id=user_id, theme_id=theme_id, now=now, rng=random.Random(1))
        assert third.reason == 'new_word'
        assert third.word['id'] in {word_map['charlie'], word_map['delta']}
    finally:
        conn.close()


def test_spaced_repetition_progress_updates(tmp_path):
    db_path = str(tmp_path / 'progress.db')
    init_db(db_path)
    user_id, theme_id, word_map = _setup_user_theme_words(db_path)
    _ = theme_id

    conn = get_connection(db_path)
    try:
        t1 = datetime(2025, 1, 1, 8, 0, 0)
        p1 = update_word_progress(conn, user_id=user_id, word_id=word_map['alpha'], was_correct=True, now=t1)
        assert p1['times_seen'] == 1
        assert p1['times_correct'] == 1
        assert p1['times_wrong'] == 0
        assert p1['interval_days'] == 2

        t2 = datetime(2025, 1, 2, 8, 0, 0)
        p2 = update_word_progress(conn, user_id=user_id, word_id=word_map['alpha'], was_correct=True, now=t2)
        assert p2['times_seen'] == 2
        assert p2['times_correct'] == 2
        assert p2['interval_days'] == 4

        t3 = datetime(2025, 1, 3, 8, 0, 0)
        p3 = update_word_progress(conn, user_id=user_id, word_id=word_map['alpha'], was_correct=False, now=t3)
        assert p3['times_seen'] == 3
        assert p3['times_wrong'] == 1
        assert p3['interval_days'] == 1
        assert p3['next_review_at'].startswith('2025-01-04 08:00:00')
    finally:
        conn.close()


def test_recent_history_avoidance(tmp_path):
    db_path = str(tmp_path / 'recent.db')
    init_db(db_path)
    user_id, theme_id, word_map = _setup_user_theme_words(db_path)

    conn = get_connection(db_path)
    try:
        now = datetime(2025, 2, 1, 9, 0, 0)
        # mark recent games with alpha/bravo/charlie
        for w in ['alpha', 'bravo', 'charlie']:
            conn.execute(
                "INSERT INTO games (user_id, word_id, status, started_at) VALUES (?, ?, 'won', ?)",
                (user_id, word_map[w], now.isoformat(sep=' ')),
            )
        conn.commit()

        selected = select_next_word(conn, user_id=user_id, theme_id=theme_id, now=now, rng=random.Random(3))
        assert selected.word['id'] == word_map['delta']
    finally:
        conn.close()
