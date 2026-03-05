import importlib

import pytest

from db import get_connection, init_db

pytest.importorskip('flask')


@pytest.fixture()
def client_with_temp_db(tmp_path, monkeypatch):
    server = importlib.import_module('server')
    db_path = tmp_path / 'auth.db'
    init_db(str(db_path))
    monkeypatch.setattr(server, 'DB_PATH', str(db_path))
    server.app.config['TESTING'] = True
    server.app.config['SECRET_KEY'] = 'test-secret'
    with server.app.test_client() as client:
        yield client, str(db_path)


def test_signup_and_login_happy_path(client_with_temp_db):
    client, db_path = client_with_temp_db

    signup = client.post('/api/auth/signup', json={'username': 'alice', 'password': 'secret123'})
    assert signup.status_code == 201
    assert signup.get_json()['username'] == 'alice'

    me = client.get('/api/me')
    assert me.status_code == 200
    assert me.get_json()['guest'] is False

    conn = get_connection(db_path)
    try:
        row = conn.execute('SELECT username, password_hash FROM users WHERE username = ?', ('alice',)).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row['username'] == 'alice'
    assert row['password_hash'] != 'secret123'

    client2 = importlib.import_module('server').app.test_client()
    login = client2.post('/api/auth/login', json={'username': 'alice', 'password': 'secret123'})
    assert login.status_code == 200
    assert login.get_json()['username'] == 'alice'


def test_invalid_credentials_and_duplicate_signup(client_with_temp_db):
    client, _ = client_with_temp_db

    first = client.post('/api/auth/signup', json={'username': 'bob', 'password': 'secret123'})
    assert first.status_code == 201

    dup = client.post('/api/auth/signup', json={'username': 'bob', 'password': 'otherpass'})
    assert dup.status_code == 409

    bad_login = client.post('/api/auth/login', json={'username': 'bob', 'password': 'wrongpass'})
    assert bad_login.status_code == 401

    invalid_payload = client.post('/api/auth/signup', json={'username': 'ab', 'password': '123'})
    assert invalid_payload.status_code == 400


def test_auth_required_leaderboard_route(client_with_temp_db):
    client, _ = client_with_temp_db

    unauth = client.post('/api/leaderboard_entries', json={'score': 5})
    assert unauth.status_code == 401

    client.post('/api/auth/signup', json={'username': 'charlie', 'password': 'secret123'})
    auth = client.post('/api/leaderboard_entries', json={'score': 10})
    assert auth.status_code == 201
    assert auth.get_json()['score'] == 10
