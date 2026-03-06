import importlib

import pytest

from db import get_connection, init_db, seed_words_from_files

pytest.importorskip('flask')


@pytest.fixture()
def auth_client_with_progress(tmp_path, monkeypatch):
    server = importlib.import_module('server')
    db_path = tmp_path / 'progress.db'
    words_dir = tmp_path / 'words'
    words_dir.mkdir()
    (words_dir / 'ket.txt').write_text('cat\ndog\n', encoding='utf-8')
    (words_dir / 'pet.txt').write_text('planet\ntravel\n', encoding='utf-8')

    init_db(str(db_path))
    seed_words_from_files(str(db_path), data_dir=str(words_dir))

    monkeypatch.setattr(server, 'DB_PATH', str(db_path))
    server.app.config['TESTING'] = True
    server.app.config['SECRET_KEY'] = 'test-secret'

    with server.app.test_client() as client:
        signup = client.post('/api/auth/signup', json={'username': 'teacher', 'password': 'secret123'})
        assert signup.status_code == 201
        user_id = signup.get_json()['id']

        conn = get_connection(str(db_path))
        try:
            ket_id = conn.execute("SELECT id FROM themes WHERE name='ket'").fetchone()['id']
            pet_id = conn.execute("SELECT id FROM themes WHERE name='pet'").fetchone()['id']
            cat_id = conn.execute('SELECT id FROM words WHERE theme_id = ? ORDER BY id LIMIT 1', (ket_id,)).fetchone()['id']
            dog_id = conn.execute('SELECT id FROM words WHERE theme_id = ? ORDER BY id LIMIT 1 OFFSET 1', (ket_id,)).fetchone()['id']
            planet_id = conn.execute('SELECT id FROM words WHERE theme_id = ? ORDER BY id LIMIT 1', (pet_id,)).fetchone()['id']

            conn.execute(
                '''
                INSERT INTO word_progress (user_id, word_id, times_seen, times_correct, times_wrong, interval_days, next_review_at)
                VALUES (?, ?, 5, 4, 1, 8, datetime('now', '+8 days'))
                ''',
                (user_id, cat_id),
            )
            conn.execute(
                '''
                INSERT INTO word_progress (user_id, word_id, times_seen, times_correct, times_wrong, interval_days, next_review_at)
                VALUES (?, ?, 2, 1, 1, 2, datetime('now', '+2 days'))
                ''',
                (user_id, dog_id),
            )
            conn.execute(
                '''
                INSERT INTO word_progress (user_id, word_id, times_seen, times_correct, times_wrong, interval_days, next_review_at)
                VALUES (?, ?, 3, 3, 0, 7, datetime('now', '+7 days'))
                ''',
                (user_id, planet_id),
            )

            conn.execute(
                '''
                INSERT INTO games (user_id, word_id, theme_id, status, correct_guesses, wrong_guesses, ended_at)
                VALUES (?, ?, ?, 'won', 5, 1, datetime('now'))
                ''',
                (user_id, cat_id, ket_id),
            )
            conn.execute(
                '''
                INSERT INTO games (user_id, word_id, theme_id, status, correct_guesses, wrong_guesses, ended_at)
                VALUES (?, ?, ?, 'won', 3, 2, datetime('now', '-1 days'))
                ''',
                (user_id, planet_id, pet_id),
            )
            conn.commit()
        finally:
            conn.close()

        yield client


def test_progress_summary_requires_auth():
    server = importlib.import_module('server')
    server.app.config['TESTING'] = True
    with server.app.test_client() as client:
        response = client.get('/api/progress/summary')
        assert response.status_code == 401


def test_progress_summary_returns_expected_metrics(auth_client_with_progress):
    response = auth_client_with_progress.get('/api/progress/summary')
    assert response.status_code == 200
    payload = response.get_json()

    assert payload['words_seen'] == 3
    assert payload['words_mastered'] == 2
    assert payload['accuracy_7d'] == pytest.approx(0.7272, rel=1e-3)
    assert payload['streak_days'] >= 1

    assert payload['mastery_rule']['wrong_guesses_lt'] == 3

    themes = {row['theme_name']: row for row in payload['themes']}
    assert themes['KET']['words_seen'] == 2
    assert themes['KET']['words_mastered'] == 1
    assert themes['KET']['accuracy_7d'] is not None
    assert themes['KET']['accuracy_7d'] == pytest.approx(5 / 6, rel=1e-3)  # one game: 5 correct, 1 wrong
    assert themes['PET']['words_seen'] == 1
    assert themes['PET']['words_mastered'] == 1
    assert themes['PET']['accuracy_7d'] is not None
    assert themes['PET']['accuracy_7d'] == pytest.approx(3 / 5, rel=1e-3)  # one game: 3 correct, 2 wrong
