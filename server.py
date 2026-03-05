from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash
import os
import random

from db import (
    DEFAULT_DB_PATH,
    create_leaderboard_entry,
    create_user,
    get_user_by_id,
    get_user_by_username,
    initialize_and_seed,
    list_themes,
)

app = Flask(__name__, static_folder='.', static_url_path='')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-change-me')

WORD_DIR = 'word'
DB_PATH = os.environ.get('HANGMAN_DB_PATH', DEFAULT_DB_PATH)

initialize_and_seed(DB_PATH)


def _current_user_id() -> int | None:
    user_id = session.get('user_id')
    return int(user_id) if user_id is not None else None


@app.route('/')
def serve_index():
    return app.send_static_file('index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)


@app.route('/api/random_word')
def random_word():
    # List all .txt files in the word directory
    files = [f for f in os.listdir(WORD_DIR) if f.endswith('.txt')]
    if not files:
        return jsonify({'error': 'No word files found'}), 404

    # Pick a random file
    chosen_file = random.choice(files)
    with open(os.path.join(WORD_DIR, chosen_file), 'r', encoding='utf-8') as f:
        words = [line.strip() for line in f if line.strip()]
    if not words:
        return jsonify({'error': 'No words found in file'}), 404

    # Pick a random word
    word = random.choice(words)
    return jsonify({'word': word})


@app.route('/api/themes')
def get_themes():
    return jsonify({'themes': list_themes(DB_PATH)})


@app.route('/api/auth/signup', methods=['POST'])
def signup():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get('username', '')).strip()
    password = str(payload.get('password', ''))

    if len(username) < 3 or len(password) < 6:
        return jsonify({'error': 'Invalid username or password'}), 400

    password_hash = generate_password_hash(password)
    user_id = create_user(DB_PATH, username, password_hash)
    if user_id is None:
        return jsonify({'error': 'Username already exists'}), 409

    session['user_id'] = user_id
    return jsonify({'id': user_id, 'username': username}), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get('username', '')).strip()
    password = str(payload.get('password', ''))

    user = get_user_by_username(DB_PATH, username)
    if not user or not user.get('password_hash'):
        return jsonify({'error': 'Invalid credentials'}), 401

    if not check_password_hash(user['password_hash'], password):
        return jsonify({'error': 'Invalid credentials'}), 401

    session['user_id'] = user['id']
    return jsonify({'id': user['id'], 'username': user['username']}), 200


@app.route('/api/me')
def me():
    user_id = _current_user_id()
    if not user_id:
        return jsonify({'guest': True}), 200

    user = get_user_by_id(DB_PATH, user_id)
    if not user:
        session.pop('user_id', None)
        return jsonify({'guest': True}), 200

    return jsonify({'guest': False, 'user': user}), 200


@app.route('/api/leaderboard_entries', methods=['POST'])
def create_entry():
    user_id = _current_user_id()
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    payload = request.get_json(silent=True) or {}
    score = payload.get('score')
    game_id = payload.get('game_id')

    if not isinstance(score, int):
        return jsonify({'error': 'score must be an integer'}), 400

    entry_id = create_leaderboard_entry(DB_PATH, user_id=user_id, score=score, game_id=game_id)
    return jsonify({'id': entry_id, 'user_id': user_id, 'score': score, 'game_id': game_id}), 201


if __name__ == '__main__':
    app.run(debug=True)
