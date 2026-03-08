import importlib

import pytest

from db import get_connection, init_db, seed_words_from_files

pytest.importorskip('flask')


@pytest.fixture()
def client_with_seeded_db(tmp_path, monkeypatch):
    server = importlib.import_module('server')
    db_path = tmp_path / 'api.db'
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


def test_get_word_next_guest_mode(client_with_seeded_db):
    client, db_path = client_with_seeded_db

    conn = get_connection(db_path)
    try:
        theme_id = conn.execute("SELECT id FROM themes WHERE name='KET'").fetchone()['id']
    finally:
        conn.close()

    response = client.get(f'/api/word/next?theme={theme_id}')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['review_status'] == 'guest_random'
    assert payload['word']['theme_id'] == theme_id
    assert payload['theme'] == 'KET'


def test_get_word_next_authenticated_uses_engine(client_with_seeded_db):
    client, db_path = client_with_seeded_db
    signup = client.post('/api/auth/signup', json={'username': 'worduser', 'password': 'secret123'})
    assert signup.status_code == 201

    conn = get_connection(db_path)
    try:
        theme_id = conn.execute("SELECT id FROM themes WHERE name='KET'").fetchone()['id']
    finally:
        conn.close()

    response = client.get(f'/api/word/next?theme={theme_id}')
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['review_status'] in {'new', 'random_fallback'}
    assert payload['word']['theme_id'] == theme_id
    assert payload['theme'] == 'KET'


def test_get_word_next_requires_theme_query(client_with_seeded_db):
    client, _ = client_with_seeded_db

    response = client.get('/api/word/next')
    assert response.status_code == 400


def test_random_word_returns_word_and_theme(client_with_seeded_db):
    """GET /api/random_word returns both word and theme for theme awareness."""
    client, _ = client_with_seeded_db

    response = client.get('/api/random_word')
    assert response.status_code == 200
    payload = response.get_json()
    assert 'word' in payload
    assert 'theme' in payload
    assert isinstance(payload['word'], str)
    assert isinstance(payload['theme'], str)
    assert payload['word'] in ('cat', 'dog')
    assert payload['theme'] == 'KET'
