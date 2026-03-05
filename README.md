# Hangman Game

A classic Hangman word guessing game built with HTML, CSS, JavaScript, and a Python Flask backend.

## Features

- Classic hangman gameplay
- Word guessing mechanics
- Visual hangman drawing
- Score tracking
- Web interface with sound effects

## Setup

1. Create a virtual environment (recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

## Run the application

1. Start the Flask server:

   ```bash
   python server.py
   ```

2. Open your browser and go to `http://localhost:5000`.

## Run tests

```bash
pytest -q
```

## How to Play

1. Guess letters to reveal the hidden word.
2. You have 6 incorrect attempts before the hangman is complete.
3. Win by guessing all letters in the word.

## Project Structure

```text
hangman-game/
├── AGENTS.md          # Instructions for Codex agents
├── index.html         # Main HTML file
├── style.css          # Styling
├── game.js            # Game logic
├── server.py          # Flask backend
├── requirements.txt   # Python dependencies
├── tests/             # Pytest test files
├── word/              # Word lists
├── assets/            # Sounds
└── README.md          # Project docs
```
