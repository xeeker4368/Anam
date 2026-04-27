#!/usr/bin/env python3
"""
Tír Web Server

Start the FastAPI backend:
    python run_server.py

Options:
    --debug     Enable debug logging and auto-reload
    --port N    Override port (default: 8000)
"""

import argparse
import logging
import uvicorn

from tir.config import WEB_HOST, WEB_PORT


def main():
    parser = argparse.ArgumentParser(description="Tír Web Server")
    parser.add_argument("--debug", action="store_true", help="Debug mode with auto-reload")
    parser.add_argument("--port", type=int, default=WEB_PORT, help=f"Port (default: {WEB_PORT})")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("data/prod/tir.log"),
        ],
    )

    uvicorn.run(
        "tir.api.routes:app",
        host=WEB_HOST,
        port=args.port,
        reload=args.debug,
        log_level="debug" if args.debug else "info",
    )


if __name__ == "__main__":
    main()
