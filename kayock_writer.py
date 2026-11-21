#!/usr/bin/env python3
"""Kayock Writer — standalone creative writing suite (entrypoint).

Extracted and upgraded from FOXAI (https://github.com/kayock/FOXAI_, commit
b510e5c). Runs a LAN-reachable web app with Novel Forge, Poetry Forge,
Short Story Forge, Story Forge, The Weaver, and shared settings — no FOXAI
installation, services, or paths required.

Usage:
    python kayock_writer.py                     # serve on 0.0.0.0:8765
    python kayock_writer.py --host 127.0.0.1 --port 9000
    python kayock_writer.py --data-dir D:/Writing/KayockData
    python kayock_writer.py --base-url http://127.0.0.1:8080 --model local-model
    python kayock_writer.py --check             # config + model health probe

Configuration precedence: CLI flags > environment variables > config.json
> defaults. See docs/INSTALL.md for the full reference.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_ROOT))

from app import __version__, APP_NAME  # noqa: E402
from app.config import apply_cli_overrides, load_config  # noqa: E402
from app.server import serve  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kayock_writer",
        description=f"{APP_NAME} {__version__} — standalone LAN writing suite "
                    "extracted from FOXAI.",
    )
    p.add_argument("--host", default=None,
                   help="Bind address (default 0.0.0.0 = reachable from the LAN; "
                        "use 127.0.0.1 for this machine only).")
    p.add_argument("--port", type=int, default=None, help="Port (default 8765).")
    p.add_argument("--data-dir", default=None,
                   help="Folder for all writing data (projects, archives, exports).")
    p.add_argument("--config", default=None, help="Path to config.json.")
    p.add_argument("--base-url", default=None,
                   help="OpenAI-compatible model base URL, e.g. http://127.0.0.1:8080.")
    p.add_argument("--model", default=None,
                   help="Model name sent to the endpoint (default: local-model).")
    p.add_argument("--check", action="store_true",
                   help="Print resolved configuration and model health, then exit.")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = apply_cli_overrides(load_config(args.config), vars(args))

    if args.check:
        from app.provider import Provider
        health = Provider(cfg).health(timeout=5.0)
        print(f"{APP_NAME} {__version__}")
        print(f"  host/port : {cfg.host}:{cfg.port}")
        print(f"  data dir  : {cfg.data_dir()}")
        print(f"  model     : {cfg.get('model.model')} @ {cfg.get('model.base_url')}")
        print(f"  health    : {'online' if health.get('online') else 'OFFLINE'}"
              f" (via {health.get('via') or 'none'})")
        for checked in health.get("checked", []):
            print(f"    - {checked['endpoint']} -> "
                  f"{'ok' if checked['ok'] else checked['error']}")
        return 0 if health.get("online") else 1

    server = serve(cfg)
    host, port = server.server_address[:2]
    print(f"{APP_NAME} {__version__}")
    print(f"  Serving on http://{host}:{port}  (LAN: use this machine's IP)")
    print(f"  Data dir : {cfg.data_dir()}")
    print(f"  Model    : {cfg.get('model.model')} @ {cfg.get('model.base_url')}")
    if str(cfg.get('model.api_key') or ''):
        print("  API key  : configured (kept secret)")
    elif cfg.api_key():
        print("  API key  : from KAYOCK_MODEL_API_KEY (kept secret)")
    print("  Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
