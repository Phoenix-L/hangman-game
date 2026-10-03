import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Test-only signing key; production startup deliberately fails without one.
os.environ.setdefault('SECRET_KEY', 'isolated-test-signing-key')
