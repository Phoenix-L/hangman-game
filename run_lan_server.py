#!/usr/bin/env python3
"""Start the Hangman Flask server for LAN access. Prints local and LAN URLs."""

import os
import socket
import subprocess
import sys


def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"  # fallback when network unreachable
    finally:
        s.close()
    return ip


if __name__ == "__main__":
    ip = get_lan_ip()
    port = int(os.environ.get("PORT", "5000"))

    print("\nHangman server starting...\n")
    print(f"Local: http://localhost:{port}")
    print(f"LAN:   http://{ip}:{port}\n")

    subprocess.run([sys.executable, "server.py"], env=os.environ.copy())
