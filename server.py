from flask import Flask, jsonify, send_from_directory
import os
import random

app = Flask(__name__, static_folder='.', static_url_path='')

WORD_DIR = 'word'

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
    with open(os.path.join(WORD_DIR, chosen_file), 'r') as f:
        words = [line.strip() for line in f if line.strip()]
    if not words:
        return jsonify({'error': 'No words found in file'}), 404

    # Pick a random word
    word = random.choice(words)
    return jsonify({'word': word})

if __name__ == '__main__':
    app.run(debug=True)
