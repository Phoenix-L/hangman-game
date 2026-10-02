import importlib

import pytest

pytest.importorskip('flask')


@pytest.fixture()
def game_client(tmp_path, monkeypatch):
    db_path = tmp_path / 'synthetic-hangman.sqlite3'
    monkeypatch.setenv('HANGMAN_DB_PATH', str(db_path))
    monkeypatch.setenv('SECRET_KEY', 'isolated-test-key-only')
    server = importlib.import_module('server')
    monkeypatch.setattr(server, 'DB_PATH', str(db_path))
    server.initialize_and_seed(str(db_path))
    server.app.config['TESTING'] = True
    return server, server.app.test_client()


def test_only_public_game_files_are_served(game_client):
    server, client = game_client
    for path in (
        '/hangman/hangman.db', '/hangman/server.py', '/hangman/db.py',
        '/hangman/admin.html', '/hangman/admin.js', '/hangman/README.md',
        '/hangman/requirements.txt', '/hangman/.env', '/hangman/.git/config',
        '/hangman/data/words/ket.txt', '/hangman/assets/missing.mp3',
    ):
        assert client.get(path).status_code == 404, path

    for path in (
        '/hangman/', '/hangman/style.css', '/hangman/game_logic.js',
        '/hangman/speech_controller.js', '/hangman/game.js',
        '/hangman/assets/correct.mp3', '/hangman/assets/lose.mp3',
        '/hangman/assets/win.mp3', '/hangman/assets/wrong.mp3',
        '/hangman/api/themes', '/hangman/api/word/next',
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        response.close()

    rules = {rule.rule for rule in server.app.url_map.iter_rules()}
    assert '/api/admin/session' not in rules
    assert client.post('/hangman/api/admin/session').status_code in (404, 405)
    assert client.get('/hangman/api/admin/themes').status_code == 403


def test_session_cookies_have_browser_security_flags(game_client):
    _, client = game_client
    response = client.post(
        '/api/auth/signup',
        json={'username': 'synthetic-boundary', 'password': 'isolated-password-123'},
    )
    assert response.status_code == 201
    cookie = response.headers['Set-Cookie'].lower()
    assert 'secure' in cookie
    assert 'httponly' in cookie
    assert 'samesite=lax' in cookie
