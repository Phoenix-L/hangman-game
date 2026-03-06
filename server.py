from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash
import os

from db import (
    DEFAULT_DB_PATH,
    create_leaderboard_entry,
    create_user,
    get_connection,
    get_theme_name_by_id,
    get_user_by_id,
    get_user_by_username,
    get_progress_summary,
    get_random_word,
    initialize_and_seed,
    list_global_leaderboard,
    list_themes,
    theme_display_name,
)
from engine.word_selector import select_guest_word, select_next_word, update_word_progress

app = Flask(__name__, static_folder='.', static_url_path='')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-change-me')

DB_PATH = os.environ.get('HANGMAN_DB_PATH', DEFAULT_DB_PATH)

initialize_and_seed(DB_PATH)


def _compute_accuracy_and_score(duration_ms: int, correct_guesses: int, wrong_guesses: int, won: bool) -> tuple[float, int]:
    total_guesses = correct_guesses + wrong_guesses
    accuracy = (correct_guesses / total_guesses) if total_guesses > 0 else 0.0

    clamped_duration = min(max(duration_ms, 0), 120_000)
    speed_factor = 1.0 - (clamped_duration / 120_000)
    won_bonus = 100 if won else 0
    score = int(round((accuracy * 700) + (speed_factor * 300) + won_bonus))
    return accuracy, score


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
    result = get_random_word(DB_PATH)
    if not result:
        return jsonify({'error': 'No words found in database'}), 404

    theme_name = result.get('theme') or 'Vocabulary'
    response = jsonify({
        'word': result['value'],
        'theme': theme_name,
        'theme_display': theme_display_name(theme_name),
    })
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    return response


@app.route('/api/themes')
def get_themes():
    return jsonify({'themes': list_themes(DB_PATH)})


@app.route('/api/word/next')
def get_next_word():
    theme_id = request.args.get('theme', type=int)
    if theme_id is None:
        return jsonify({'error': 'theme query parameter is required'}), 400

    user_id = _current_user_id()
    conn = get_connection(DB_PATH)
    try:
        if user_id:
            selection = select_next_word(conn, user_id=user_id, theme_id=theme_id)
            if selection.word:
                conn.execute(
                    "INSERT INTO games (user_id, word_id, status) VALUES (?, ?, 'in_progress')",
                    (user_id, selection.word['id']),
                )
                conn.commit()
        else:
            selection = select_guest_word(conn, theme_id=theme_id)

        if not selection.word:
            return jsonify({'error': 'No words found for theme'}), 404

        theme_name = get_theme_name_by_id(DB_PATH, selection.word['theme_id']) or 'Vocabulary'
        return jsonify({
            'word': selection.word,
            'theme': theme_name,
            'theme_display': theme_display_name(theme_name),
            'reason': selection.reason,
        })
    finally:
        conn.close()


@app.route('/api/word/progress', methods=['POST'])
def record_progress():
    user_id = _current_user_id()
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401

    payload = request.get_json(silent=True) or {}
    word_id = payload.get('word_id')
    was_correct = payload.get('was_correct')

    if not isinstance(word_id, int) or not isinstance(was_correct, bool):
        return jsonify({'error': 'word_id(int) and was_correct(bool) are required'}), 400

    conn = get_connection(DB_PATH)
    try:
        progress = update_word_progress(conn, user_id=user_id, word_id=word_id, was_correct=was_correct)
        return jsonify({'progress': progress}), 200
    finally:
        conn.close()


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


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'ok': True}), 200


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


@app.route('/api/game/result', methods=['POST'])
def submit_game_result():
    payload = request.get_json(silent=True) or {}
    word_id = payload.get('word_id')
    theme_id = payload.get('theme_id')
    duration_ms = payload.get('duration_ms')
    guesses = payload.get('guesses') if isinstance(payload.get('guesses'), dict) else None
    won = payload.get('won')

    if not isinstance(word_id, int) or not isinstance(theme_id, int) or not isinstance(duration_ms, int) or not isinstance(won, bool):
        return jsonify({'error': 'word_id, theme_id, duration_ms(int) and won(bool) are required'}), 400
    if duration_ms < 0:
        return jsonify({'error': 'duration_ms must be >= 0'}), 400

    if not guesses:
        return jsonify({'error': 'guesses object is required'}), 400
    correct_guesses = guesses.get('correct')
    wrong_guesses = guesses.get('wrong')
    if not isinstance(correct_guesses, int) or not isinstance(wrong_guesses, int):
        return jsonify({'error': 'guesses.correct and guesses.wrong must be integers'}), 400
    if correct_guesses < 0 or wrong_guesses < 0:
        return jsonify({'error': 'guesses.correct and guesses.wrong must be >= 0'}), 400

    conn = get_connection(DB_PATH)
    user_id = _current_user_id()
    try:
        word_row = conn.execute(
            "SELECT id, theme_id FROM words WHERE id = ? AND theme_id = ?",
            (word_id, theme_id),
        ).fetchone()
        if not word_row:
            return jsonify({'error': 'word_id does not belong to theme_id'}), 400

        accuracy, score = _compute_accuracy_and_score(duration_ms, correct_guesses, wrong_guesses, won)
        status = 'won' if won else 'lost'

        cursor = conn.execute(
            """
            INSERT INTO games (
                user_id,
                word_id,
                theme_id,
                status,
                wrong_guesses,
                correct_guesses,
                duration_ms,
                accuracy,
                score,
                ended_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                word_id,
                theme_id,
                status,
                wrong_guesses,
                correct_guesses,
                duration_ms,
                accuracy,
                score,
            ),
        )
        game_id = int(cursor.lastrowid)

        progress = None
        leaderboard_entry_id = None
        if user_id:
            progress = update_word_progress(conn, user_id=user_id, word_id=word_id, was_correct=won)
            leaderboard_cursor = conn.execute(
                "INSERT INTO leaderboard_entries (user_id, game_id, score) VALUES (?, ?, ?)",
                (user_id, game_id, score),
            )
            leaderboard_entry_id = int(leaderboard_cursor.lastrowid)
            conn.commit()
        else:
            conn.commit()

        return jsonify(
            {
                'game_id': game_id,
                'score': score,
                'accuracy': accuracy,
                'leaderboard_entry_id': leaderboard_entry_id,
                'progress': progress,
            }
        ), 201
    finally:
        conn.close()


@app.route('/api/progress/summary')
def get_progress_summary_route():
    user_id = _current_user_id()
    if not user_id:
        return jsonify({'error': 'Authentication required'}), 401
    summary = get_progress_summary(DB_PATH, user_id)
    return jsonify(summary), 200


@app.route('/api/leaderboard/global')
def get_global_leaderboard():
    theme_id = request.args.get('theme', type=int)
    limit = request.args.get('limit', default=50, type=int)

    entries = list_global_leaderboard(DB_PATH, theme_id=theme_id, limit=limit)
    ranked = [
        {
            'rank': index,
            **entry,
        }
        for index, entry in enumerate(entries, start=1)
    ]
    return jsonify({'entries': ranked}), 200



if __name__ == '__main__':
    app.run(debug=True)
