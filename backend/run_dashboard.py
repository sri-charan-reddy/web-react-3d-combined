"""Standalone Launcher for Team Raynex FSOC PAT Mission Control Dashboard.

Launches the multi-threaded simulation engine and HTTP/SSE dashboard server.

Usage:
    python run_dashboard.py
    python run_dashboard.py --port 8080
    python run_dashboard.py --no-browser
"""

import argparse
import os
import sys
import threading
import time
import webbrowser

# Automatically re-execute within local .venv if running with system Python
_venv_python = os.path.abspath(os.path.join(os.path.dirname(__file__), ".venv", "bin", "python3"))
if os.path.exists(_venv_python) and sys.executable != _venv_python:
    try:
        import cv2, yaml, numpy  # test if current python already has required packages
    except ImportError:
        os.execv(_venv_python, [_venv_python] + sys.argv)

from src.web.server import run_server


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Team Raynex: FSOC PAT Mission Control & Adaptive Recovery Dashboard"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to bind dashboard server (default: 8080)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind server (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not automatically open default web browser",
    )

    args = parser.parse_args()

    if not args.no_browser:
        def open_browser():
            time.sleep(1.0)
            webbrowser.open(f"http://localhost:{args.port}")

        threading.Thread(target=open_browser, daemon=True).start()

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
