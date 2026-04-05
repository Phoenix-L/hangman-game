# 🎮 Hangman Vocabulary Trainer

<p align="center">
<img src="docs/banner.png" width="800">
</p>

<p align="center">

![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-success)

</p>

An open-source **Hangman + Vocabulary Learning** game.

Play Hangman while building vocabulary with:

- 🧠 **Spaced Repetition**
- 📊 **Learning Progress Tracking**
- 🏆 **Leaderboard Ranking**

Designed for:

- language learners
- students preparing for **KET / PET**
- parents teaching vocabulary to kids
- developers learning **Flask full-stack apps**

---

# 🎬 Demo

### Gameplay

<img src="docs/demo_gameplay.png" width="700">

Example gameplay features:

- word guessing gameplay
- theme hint system
- accuracy tracking
- score system
- leaderboard ranking

*(Recommended: replace with GIF for better GitHub visibility)*

---

# 🚀 Features

## 🎮 Gameplay

- Classic Hangman mechanics
- Theme hint for each word
- Accuracy-based scoring
- Keyboard-friendly input

---

## 📚 Vocabulary Learning

- Theme-based vocabulary datasets
- Word learning progress tracking
- Difficulty evolution

Example themes:

- animals
- food
- school
- travel
- environment

---

## 🧠 Spaced Repetition Engine

Inspired by **Anki / Duolingo**.

The engine:

- tracks word learning history
- schedules difficult words to reappear
- reinforces weak vocabulary

---

## 🏆 Leaderboard System

Dynamic leaderboard ranking:

- time-decayed scores
- streak bonus
- daily activity reward

Encourages **daily practice**.

---

## 🌐 Deployment Modes

Three ways to run the game.

| Mode | Description |
|-----|-------------|
| Offline | Single-file browser version |
| Local Dev | Flask server on localhost |
| LAN Mode | Family multiplayer on same WiFi |

---

# 🧩 System Architecture



	Browser UI
	│
	▼
	Flask API Server
	│
	▼
	Word Engine
	(spaced repetition + word selection)
	│
	▼
	SQLite Database

---

## Main modules:

| Component | Purpose |
|---|---|
| `server.py` | Flask API server |
| `engine/` | word selection logic |
| `data/` | vocabulary datasets |
| `game.js` | gameplay frontend |
| `db.py` | database access |
| `scripts/` | seeding tools |

---

# 🛠 Installation

Clone the repository and enter the project directory:
```bash
git clone https://github.com/<owner>/hangman-game.git
cd hangman-game
```

### One-command setup (recommended)

Creates a `.venv`, installs dependencies, runs `pytest`, and initializes/seeds the SQLite database:

```bash
bash scripts/bootstrap_local.sh
```

Then start the server:
```bash
source .venv/bin/activate
python server.py
```

Open the app at [http://localhost:5000](http://localhost:5000).

**Browser never finishes loading?** On Windows, port **5000** is often used by system features (e.g. AirPlay). Use another port, then open that URL:

```bash
PORT=5001 python server.py
```

### Makefile shortcuts

After cloning, you can use:

```bash
make bootstrap   # same as bash scripts/bootstrap_local.sh
make setup       # venv + pip install only
make test        # pytest (runs setup first)
make db          # initialize/seed database (runs setup first)
make run         # Flask dev server (runs setup first)
```

### Manual setup

If you prefer not to use the bootstrap script:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts/init_db.py
python server.py
```


---

# 🏠 LAN Mode (Play with Family)

With the virtual environment active, run:
```bash
python run_lan_server.py
```

(If you used the bootstrap script, run `source .venv/bin/activate` first.)


Console output example:
```Local:
http://localhost:5000

LAN:
http://192.168.x.x:5000
```


Anyone connected to the same WiFi can play.

---

# 📦 Vocabulary Dataset

Vocabulary files are stored in:
```data/*.txt```


Each file represents a **theme**.

Example:
```
data/ket_animals.txt
data/ket_food.txt
data/ket_environment.txt
```


Each line contains one word.
```
cat
dog
elephant
lizard
horse
```

---

# 🧪 Testing

With the virtual environment active:

```bash
pytest -q
```

Or from a fresh shell:

```bash
make test
```


---

# 🗺 Roadmap

Planned improvements:

- XP progression system
- daily vocabulary challenges
- multiplayer leaderboard
- teacher dashboard
- mobile UI optimization

---

# 🤝 Contributing

Contributions are welcome.

Possible areas:

- new vocabulary datasets
- UI improvements
- learning engine optimization
- multiplayer features

---

# 📄 License

MIT License

---

# ⭐ Support the Project

If you find this project useful:

⭐ Star the repository  
🍴 Fork it  
🧑‍💻 Contribute improvements  

This helps the project grow.
