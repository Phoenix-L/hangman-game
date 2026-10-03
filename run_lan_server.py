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

    print("\nHangman server starting...\n")
    print("Local: http://localhost:5000")
    print(f"LAN:   http://{ip}:5000\n")

    # The regular server binds only to loopback. This explicit opt-in helper is
    # the only supported path that exposes it to other devices on the LAN.
    os.environ["HOST"] = "0.0.0.0"
    subprocess.run([sys.executable, "server.py"])
