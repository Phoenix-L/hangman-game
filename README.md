# Hangman Game

A classic Hangman word guessing game built with HTML, CSS, JavaScript, and Python Flask backend.

## Features

- Classic hangman gameplay
- Word guessing mechanics
- Visual hangman drawing
- Score tracking
- Web interface

## How to Play

1. Start the Flask server:
   ```bash
   python server.py
   ```
2. Open your browser and go to `http://localhost:5000`
3. Guess letters to reveal the hidden word
4. You have 6 attempts before the hangman is complete

## Game Rules

- Guess one letter at a time
- Correct guesses reveal the letter in the word
- Incorrect guesses add a body part to the hangman
- You lose when the hangman is complete
- You win when you guess the complete word

## Project Structure

```
hangman/
├── index.html       # Main HTML file
├── style.css        # Styling
├── game.js          # Game logic
├── server.py        # Flask backend
├── word/            # Word lists
├── assets/          # Images and sounds
├── .gitignore       # Git ignore rules
└── README.md        # This file
```

## Installation

1. Install Python dependencies (if any)
2. Run the server:
   ```bash
   python server.py
   ```
3. Open `http://localhost:5000` in your browser 