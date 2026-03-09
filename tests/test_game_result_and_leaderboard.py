import importlib

import pytest

from db import get_connection, init_db, seed_words_from_files

pytest.importorskip('flask')


def _expected_score(duration_ms: int, correct: int, wrong: int, won: bool, review_status: str = 'new') -> int:
    total = correct + wrong
    accuracy = (correct / total) if total > 0 else 0.0

    completion_score = 20 if won else 8
    accuracy_bonus = 15 if accuracy >= 0.90 else (10 if accuracy >= 0.75 else (6 if accuracy >= 0.60 else 0))
    speed_bonus = 8 if duration_ms <= 10_000 else (5 if duration_ms <= 20_000 else (2 if duration_ms <= 30_000 else 0))
    learning_bonus = {'new': 4, 'review': 6, 'difficult': 8}.get(review_status, 4)
    return max(0, min(60, completion_score + accuracy_bonus + speed_bonus + learning_bonus))


@pytest.fixture()
def seeded_client(tmp_path, monkeypatch):
    server = importlib.import_module('server')
    db_path = tmp_path / 'milestone4.db'
    words_dir = tmp_path / 'words'
    words_dir.mkdir()
    (words_dir / 'ket.txt').write_text('cat\ndog\n', encoding='utf-8')

    init_db(str(db_path))
    seed_words_from_files(str(db_path), source_dirs=[str(words_dir)])

    monkeypatch.setattr(server, 'DB_PATH', str(db_path))
    server.app.config['TESTING'] = True
    server.app.config['SECRET_KEY'] = 'test-secret'
    with server.app.test_client() as client:
        yield client, str(db_path)


def _theme_and_word(db_path: str) -> tuple[int, int]:
    conn = get_connection(db_path)
    try:
        theme_id = conn.execute("SELECT id FROM themes WHERE name='KET'").fetchone()['id']
        word_id = conn.execute("SELECT id FROM words WHERE theme_id = ? ORDER BY id LIMIT 1", (theme_id,)).fetchone()['id']
        return theme_id, word_id
    finally:
        conn.close()


def test_game_result_scoring_server_side_for_authenticated_user(seeded_client):
    client, db_path = seeded_client
    signup = client.post('/api/auth/signup', json={'username': 'sara', 'password': 'secret123'})
    assert signup.status_code == 201

    theme_id, word_id = _theme_and_word(db_path)

    payload = {
        'word_id': word_id,
        'theme_id': theme_id,
        'duration_ms': 10_000,
        'guesses': {'correct': 5, 'wrong': 1},
        'won': True,
        'review_status': 'new',
    }
    response = client.post('/api/game/result', json=payload)
    assert response.status_code == 201

    body = response.get_json()
    assert body['score'] == _expected_score(10_000, 5, 1, True, 'new')
    assert body['leaderboard_entry_id'] is not None
    assert body['progress']['times_seen'] == 1
    assert body['progress']['times_correct'] == 1

    conn = get_connection(db_path)
    try:
        game_row = conn.execute(
            'SELECT user_id, theme_id, word_id, status, wrong_guesses, correct_guesses, duration_ms, score FROM games WHERE id = ?',
            (body['game_id'],),
        ).fetchone()
        assert game_row is not None
        assert game_row['status'] == 'won'
        assert game_row['score'] == body['score']

        leaderboard_count = conn.execute('SELECT COUNT(*) AS c FROM leaderboard_entries').fetchone()['c']
        assert leaderboard_count == 1

        progress_row = conn.execute(
            'SELECT correct_count, wrong_count, interval, next_review FROM user_word_progress WHERE user_id = ? AND word_id = ?',
            (game_row['user_id'], game_row['word_id']),
        ).fetchone()
        assert progress_row is not None
        assert progress_row['correct_count'] == 1
        assert progress_row['wrong_count'] == 0
        assert progress_row['interval'] >= 2
    finally:
        conn.close()


def test_game_result_guest_does_not_create_leaderboard_entry(seeded_client):
    client, db_path = seeded_client
    theme_id, word_id = _theme_and_word(db_path)

    response = client.post(
        '/api/game/result',
        json={
            'word_id': word_id,
            'theme_id': theme_id,
            'duration_ms': 30_000,
            'guesses': {'correct': 2, 'wrong': 4},
            'won': False,
            'review_status': 'review',
        },
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body['leaderboard_entry_id'] is None
    assert body['progress'] is None

    conn = get_connection(db_path)
    try:
        leaderboard_count = conn.execute('SELECT COUNT(*) AS c FROM leaderboard_entries').fetchone()['c']
        assert leaderboard_count == 0
    finally:
        conn.close()


def test_global_leaderboard_orders_by_score_desc(seeded_client):
    client, db_path = seeded_client
    theme_id, word_id = _theme_and_word(db_path)

    signup_one = client.post('/api/auth/signup', json={'username': 'alice', 'password': 'secret123'})
    assert signup_one.status_code == 201
    r1 = client.post(
        '/api/game/result',
        json={
            'word_id': word_id,
            'theme_id': theme_id,
            'duration_ms': 50_000,
            'guesses': {'correct': 3, 'wrong': 3},
            'won': True,
            'review_status': 'new',
        },
    )
    assert r1.status_code == 201
    score_one = r1.get_json()['score']

    client2 = importlib.import_module('server').app.test_client()
    signup_two = client2.post('/api/auth/signup', json={'username': 'bob', 'password': 'secret123'})
    assert signup_two.status_code == 201
    r2 = client2.post(
        '/api/game/result',
        json={
            'word_id': word_id,
            'theme_id': theme_id,
            'duration_ms': 5_000,
            'guesses': {'correct': 5, 'wrong': 0},
            'won': True,
            'review_status': 'difficult',
        },
    )
    assert r2.status_code == 201
    score_two = r2.get_json()['score']

    assert score_two > score_one

    lb = client.get('/api/leaderboard/global?period=all&limit=50')
    assert lb.status_code == 200
    data = lb.get_json()
    entries = data['entries']
    assert data['period'] == 'all'
    assert len(entries) == 2
    assert entries[0]['leaderboard_score'] >= entries[1]['leaderboard_score']
    assert entries[0]['rank'] == 1
    assert entries[1]['rank'] == 2
    assert 'username' in entries[0]
    assert 'current_streak_days' in entries[0]

    guest_client = importlib.import_module('server').app.test_client()
    guest_restricted = guest_client.post('/api/leaderboard_entries', json={'score': 99})
    assert guest_restricted.status_code == 401


def test_game_score_is_clamped_to_lightweight_range(seeded_client):
    client, db_path = seeded_client
    signup = client.post('/api/auth/signup', json={'username': 'range_user', 'password': 'secret123'})
    assert signup.status_code == 201

    theme_id, word_id = _theme_and_word(db_path)

    high = client.post('/api/game/result', json={
        'word_id': word_id,
        'theme_id': theme_id,
        'duration_ms': 1,
        'guesses': {'correct': 10, 'wrong': 0},
        'won': True,
        'review_status': 'difficult',
    })
    assert high.status_code == 201
    assert 0 <= high.get_json()['score'] <= 60

    low = client.post('/api/game/result', json={
        'word_id': word_id,
        'theme_id': theme_id,
        'duration_ms': 120_000,
        'guesses': {'correct': 0, 'wrong': 6},
        'won': False,
        'review_status': 'new',
    })
    assert low.status_code == 201
    assert 0 <= low.get_json()['score'] <= 60
