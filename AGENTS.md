# AGENTS.md

## Project quickstart

1. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. Run the web server:
   ```bash
   python server.py
   ```
4. Open the app at `http://localhost:5000`.

## Test commands

Run the test suite with:

```bash
pytest -q
```

## Scope and constraints

- Do not change gameplay logic unless explicitly requested.
- Keep backend changes minimal and focused on server/runtime reliability.
