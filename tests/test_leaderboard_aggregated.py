"""Tests for user-aggregated leaderboard: one row per user, time decay, streak, periods."""
from datetime import date, datetime, timedelta

import pytest

from db import (
    get_connection,
    init_db,
    _streak_after_play,
    _compute_decayed_sum,
    _streak_bonus,
    _daily_activity_bonus,
    upsert_user_stats_after_game,
    list_leaderboard_aggregated,
    get_user_leaderboard_rank,
    LEADERBOARD_DECAY_FACTOR,
)


def test_streak_after_play_first_play():
    assert _streak_after_play(None, 0, date(2025, 1, 10)) == 1


def test_streak_after_play_consecutive_day():
    assert _streak_after_play(date(2025, 1, 9), 2, date(2025, 1, 10)) == 3


def test_streak_after_play_same_day_no_increment():
    assert _streak_after_play(date(2025, 1, 10), 2, date(2025, 1, 10)) == 2


def test_streak_after_play_gap_reset():
    assert _streak_after_play(date(2025, 1, 5), 5, date(2025, 1, 10)) == 1


def test_compute_decayed_sum():
    # one score today: 100 * 0.94^0 = 100
    assert _compute_decayed_sum([(100, date(2025, 1, 10))], date(2025, 1, 10)) == 100.0
    # one score 1 day ago: 100 * 0.94^1
    assert abs(_compute_decayed_sum([(100, date(2025, 1, 9))], date(2025, 1, 10)) - 94.0) < 0.01


def test_streak_bonus_capped():
    assert _streak_bonus(10) == 10 * 8
    assert _streak_bonus(40) == 30 * 8  # cap at 30


def test_daily_activity_bonus_played_today():
    assert _daily_activity_bonus(date(2025, 1, 10), date(2025, 1, 10)) == 50.0


def test_daily_activity_bonus_not_today():
    assert _daily_activity_bonus(date(2025, 1, 9), date(2025, 1, 10)) == 0.0


def test_upsert_user_stats_creates_row(tmp_path):
    db_path = str(tmp_path / "stats.db")
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO users (username, password_hash) VALUES ('u1', 'x')")
        user_id = conn.execute("SELECT id FROM users WHERE username='u1'").fetchone()[0]
        conn.commit()
        out = upsert_user_stats_after_game(conn, user_id, 100, played_dt=datetime(2025, 1, 10, 12, 0))
        conn.commit()
        assert out["total_games"] == 1
        assert out["total_score"] == 100
        assert out["current_streak_days"] == 1
        assert out["last_played_date"] == "2025-01-10"
    finally:
        conn.close()


def test_upsert_user_stats_streak_increment(tmp_path):
    db_path = str(tmp_path / "streak.db")
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO users (username, password_hash) VALUES ('u1', 'x')")
        user_id = conn.execute("SELECT id FROM users WHERE username='u1'").fetchone()[0]
        conn.commit()
        upsert_user_stats_after_game(conn, user_id, 50, played_dt=datetime(2025, 1, 9, 12, 0))
        conn.commit()
        out = upsert_user_stats_after_game(conn, user_id, 80, played_dt=datetime(2025, 1, 10, 12, 0))
        conn.commit()
        assert out["current_streak_days"] == 2
    finally:
        conn.close()


def test_list_leaderboard_aggregated_one_per_user(tmp_path):
    db_path = str(tmp_path / "agg.db")
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO users (username, password_hash) VALUES ('alice', 'x')")
        conn.execute("INSERT INTO users (username, password_hash) VALUES ('bob', 'y')")
        a_id = conn.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
        b_id = conn.execute("SELECT id FROM users WHERE username='bob'").fetchone()[0]
        conn.execute(
            "INSERT INTO themes (name, description) VALUES ('T', 't')"
        )
        theme_id = conn.execute("SELECT id FROM themes WHERE name='T'").fetchone()[0]
        conn.execute("INSERT INTO words (theme_id, value) VALUES (?, ?)", (theme_id, "cat"))
        word_id = conn.execute("SELECT id FROM words WHERE value='cat'").fetchone()[0]
        for uid, score in [(a_id, 100), (a_id, 200), (b_id, 150)]:
            conn.execute(
                "INSERT INTO games (user_id, word_id, theme_id, status, score, ended_at) VALUES (?, ?, ?, 'won', ?, ?)",
                (uid, word_id, theme_id, score, "2025-01-10 12:00:00"),
            )
        conn.commit()
        # Backfill will run on next init; we need user_stats. Run backfill manually or insert.
        from db import _backfill_user_stats
        _backfill_user_stats(conn)
        conn.commit()
    finally:
        conn.close()

    entries = list_leaderboard_aggregated(db_path, period="all", limit=10, ref_date=date(2025, 1, 10))
    assert len(entries) == 2
    usernames = {e["username"] for e in entries}
    assert usernames == {"alice", "bob"}
    assert all("leaderboard_score" in e for e in entries)
    assert all(e["rank"] in (1, 2) for e in entries)


def test_leaderboard_period_filter(tmp_path):
    db_path = str(tmp_path / "period.db")
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO users (username, password_hash) VALUES ('u1', 'x')")
        user_id = conn.execute("SELECT id FROM users WHERE username='u1'").fetchone()[0]
        conn.execute("INSERT INTO themes (name, description) VALUES ('T', 't')")
        theme_id = conn.execute("SELECT id FROM themes WHERE name='T'").fetchone()[0]
        conn.execute("INSERT INTO words (theme_id, value) VALUES (?, ?)", (theme_id, "cat"))
        word_id = conn.execute("SELECT id FROM words WHERE value='cat'").fetchone()[0]
        conn.execute(
            "INSERT INTO games (user_id, word_id, theme_id, status, score, ended_at) VALUES (?, ?, ?, 'won', 100, ?)",
            (user_id, word_id, theme_id, "2025-01-10 12:00:00"),
        )
        conn.commit()
        from db import _backfill_user_stats
        _backfill_user_stats(conn)
        conn.commit()
    finally:
        conn.close()

    ref = date(2025, 1, 10)
    all_entries = list_leaderboard_aggregated(db_path, period="all", limit=10, ref_date=ref)
    today_entries = list_leaderboard_aggregated(db_path, period="today", limit=10, ref_date=ref)
    assert len(all_entries) == 1
    assert len(today_entries) == 1
    assert today_entries[0]["leaderboard_score"] >= 100  # includes daily bonus
