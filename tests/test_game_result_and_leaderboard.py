import importlib

import pytest

from db import get_connection, init_db, seed_words_from_files

pytest.importorskip('flask')


def _expected_score(duration_ms: int, correct: int, wrong: int, won: bool) -> int:
    total = correct + wrong
    accuracy = (correct / total) if total > 0 else 0.0
    speed_factor = 1.0 - (min(max(duration_ms, 0), 120_000) / 120_000)
    return int(round((accuracy * 700) + (speed_factor * 300) + (100 if won else 0)))


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
    }
    response = client.post('/api/game/result', json=payload)
    assert response.status_code == 201

    body = response.get_json()
    assert body['score'] == _expected_score(10_000, 5, 1, True)
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
        },
    )
    assert r2.status_code == 201
    score_two = r2.get_json()['score']

    assert score_two > score_one

    lb = client.get(f'/api/leaderboard/global?theme={theme_id}&limit=50')
    assert lb.status_code == 200
    entries = lb.get_json()['entries']
    assert len(entries) == 2
    assert entries[0]['score'] >= entries[1]['score']
    assert entries[0]['rank'] == 1
    assert entries[1]['rank'] == 2

    guest_client = importlib.import_module('server').app.test_client()
    guest_restricted = guest_client.post('/api/leaderboard_entries', json={'score': 99})
    assert guest_restricted.status_code == 401
