#!/usr/bin/env python3
"""Basic path-safety checks for /hangman subpath compatibility."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
index_html = (ROOT / 'index.html').read_text(encoding='utf-8')
game_js = (ROOT / 'game.js').read_text(encoding='utf-8')

errors = []

if '/hangman/' in index_html or '/hangman/' in game_js:
    errors.append('Found forbidden hardcoded "/hangman/" path in index.html or game.js.')

# Any fetch('/api/...') or fetch("/api/...") must be converted to fetch(apiUrl(...)).
if re.search(r"fetch\(\s*['\"]/api/", game_js):
    errors.append('Found direct fetch("/api/...") in game.js; use fetch(apiUrl(...)).')

# For index assets, absolute references are forbidden.
for pattern, label in [
    (r'href\s*=\s*["\']/style\\.css["\']', 'absolute stylesheet path'),
    (r'src\s*=\s*["\']/game\\.js["\']', 'absolute game.js path'),
    (r'src\s*=\s*["\']/assets/', 'absolute assets path'),
]:
    if re.search(pattern, index_html):
        errors.append(f'Found forbidden {label} in index.html; use ./ relative paths.')

if errors:
    print('Path verification FAILED:')
    for err in errors:
        print(f'- {err}')
    sys.exit(1)

print('Path verification passed.')
