import importlib

import pytest

from db import get_connection, init_db, seed_words_from_files

pytest.importorskip('flask')


@pytest.fixture()
def client_with_seeded_db(tmp_path, monkeypatch):
    server = importlib.import_module('server')
    db_path = tmp_path / 'admin.db'
    words_dir = tmp_path / 'words'
    words_dir.mkdir()
    (words_dir / 'ket.txt').write_text('cat\ndog\n', encoding='utf-8')
    (words_dir / 'science.txt').write_text('atom\ncell\n', encoding='utf-8')

    init_db(str(db_path))
    seed_words_from_files(str(db_path), source_dirs=[str(words_dir)])

    monkeypatch.setattr(server, 'DB_PATH', str(db_path))
    server.app.config['TESTING'] = True
    server.app.config['SECRET_KEY'] = 'test-secret'
    with server.app.test_client() as client:
        yield client, str(db_path)


def test_admin_themes_requires_admin(client_with_seeded_db):
    client, _ = client_with_seeded_db

    response = client.get('/api/admin/themes')
    assert response.status_code == 403


def test_admin_theme_select_updates_active_theme(client_with_seeded_db):
    client, db_path = client_with_seeded_db

    with client.session_transaction() as sess:
        sess['is_admin'] = True

    themes_resp = client.get('/api/admin/themes')
    assert themes_resp.status_code == 200
    themes = themes_resp.get_json()['themes']
    assert len(themes) >= 2

    selected = next(theme for theme in themes if theme['is_active'] == 0)

    select_resp = client.post('/api/admin/themes/select', json={'theme_id': selected['id']})
    assert select_resp.status_code == 200

    conn = get_connection(db_path)
    try:
        rows = conn.execute('SELECT id, is_active FROM themes ORDER BY id').fetchall()
    finally:
        conn.close()

    active_ids = [row['id'] for row in rows if row['is_active'] == 1]
    assert active_ids == [selected['id']]


def test_word_next_uses_active_theme(client_with_seeded_db):
    client, _ = client_with_seeded_db

    with client.session_transaction() as sess:
        sess['is_admin'] = True

    themes_resp = client.get('/api/admin/themes')
    themes = themes_resp.get_json()['themes']
    target = next(theme for theme in themes if theme['is_active'] == 0)

    select_resp = client.post('/api/admin/themes/select', json={'theme_id': target['id']})
    assert select_resp.status_code == 200

    word_resp = client.get('/api/word/next')
    assert word_resp.status_code == 200
    payload = word_resp.get_json()
    assert payload['word']['theme_id'] == target['id']
