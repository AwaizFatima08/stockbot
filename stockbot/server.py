"""Tiny read-mostly HTTP API for the phone app (stdlib only).

    GET  /api/summary               -> data/app/summary.json
    GET  /api/stock/<SYM>           -> data/app/stocks/<SYM>.json
    GET  /api/history/<SYM>         -> data/app/history/<SYM>.json
    GET  /api/chart/<SYM>.png       -> data/app/charts/<SYM>.png
    GET  /api/symbols               -> data/app/symbols.json
    GET  /api/scorecard             -> data/app/scorecard.json
    GET  /api/watchlist             -> current watchlist
    PUT  /api/watchlist             -> {"symbols": [10 symbols]} ; rewrites config/watchlist.toml
                                       and regenerates note + bundle in the background
    GET  /api/status                -> {"busy": bool, "last_job": ...}

Auth: header  X-Token: <STOCKBOT_API_TOKEN>  (set in secrets.env). Binds to all
interfaces on the LAN port; nothing here places orders or holds credentials."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from stockbot import config

log = logging.getLogger(__name__)
_state = {"busy": False, "last_job": None}
_lock = threading.Lock()


def _write_watchlist(root: Path, symbols: list[str], names: dict[str, str], sectors: dict[str, str]) -> None:
    lines = ["# Watchlist managed from the Stock Guru app. Edit here or in the app.", ""]
    for s in symbols:
        lines += ["[[stocks]]", f'symbol = "{s}"', f'name = "{names.get(s, s)}"', f'sector = "{sectors.get(s, "")}"', ""]
    (root / "config" / "watchlist.toml").write_text("\n".join(lines), encoding="utf-8")


def _regenerate(root: Path) -> None:
    with _lock:
        _state["busy"] = True
    try:
        r = subprocess.run([sys.executable, "-m", "stockbot", "note", "--no-ai"], cwd=root, capture_output=True, text=True, timeout=1800)
        subprocess.run([sys.executable, "-m", "stockbot", "export"], cwd=root, capture_output=True, text=True, timeout=600)
        _state["last_job"] = {"rc": r.returncode, "tail": (r.stdout + r.stderr)[-600:]}
    except Exception as e:  # noqa: BLE001
        _state["last_job"] = {"rc": -1, "tail": str(e)}
    finally:
        with _lock:
            _state["busy"] = False


class Handler(BaseHTTPRequestHandler):
    root: Path = config.ROOT
    app_dir: Path = config.ROOT / "data" / "app"
    token: str = ""

    def log_message(self, fmt, *args):  # quieter
        log.info("%s %s", self.address_string(), fmt % args)

    def _send(self, code: int, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj).encode())

    def _file(self, path: Path, ctype: str):
        if not path.exists():
            return self._json(404, {"error": "not found", "path": path.name})
        self._send(200, path.read_bytes(), ctype)

    def _auth(self) -> bool:
        if not self.token or self.headers.get("X-Token", "") == self.token:
            return True
        self._json(401, {"error": "bad token"})
        return False

    def do_GET(self):
        if not self._auth():
            return
        p = self.path.split("?")[0].rstrip("/")
        if p == "/api/summary":
            return self._file(self.app_dir / "summary.json", "application/json")
        if p == "/api/symbols":
            return self._file(self.app_dir / "symbols.json", "application/json")
        if p == "/api/scorecard":
            return self._file(self.app_dir / "scorecard.json", "application/json")
        if p == "/api/status":
            return self._json(200, _state)
        if p == "/api/watchlist":
            cfg = config.load(self.root)
            return self._json(200, {"symbols": [s.symbol for s in cfg.watchlist]})
        if p.startswith("/api/stock/"):
            return self._file(self.app_dir / "stocks" / (p.rsplit("/", 1)[1].upper() + ".json"), "application/json")
        if p.startswith("/api/history/"):
            return self._file(self.app_dir / "history" / (p.rsplit("/", 1)[1].upper() + ".json"), "application/json")
        if p.startswith("/api/chart/"):
            return self._file(self.app_dir / "charts" / p.rsplit("/", 1)[1], "image/png")
        self._json(404, {"error": "unknown endpoint"})

    def do_PUT(self):
        if not self._auth():
            return
        if self.path.rstrip("/") != "/api/watchlist":
            return self._json(404, {"error": "unknown endpoint"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
            syms = [str(s).strip().upper() for s in body.get("symbols", [])]
        except (ValueError, AttributeError):
            return self._json(400, {"error": "bad json"})
        if len(syms) != 10 or len(set(syms)) != 10:
            return self._json(400, {"error": "exactly 10 distinct symbols required"})
        known = {}
        symfile = self.app_dir / "symbols.json"
        if symfile.exists():
            known = {s["symbol"]: s for s in json.loads(symfile.read_text())["symbols"]}
        unknown = [s for s in syms if s not in known]
        if unknown:
            return self._json(400, {"error": "unknown symbols", "symbols": unknown})
        if _state["busy"]:
            return self._json(409, {"error": "regeneration already running"})
        _write_watchlist(self.root, syms, {s: known[s]["name"] for s in syms}, {s: known[s].get("sector_code", "") for s in syms})
        threading.Thread(target=_regenerate, args=(self.root,), daemon=True).start()
        self._json(202, {"ok": True, "symbols": syms, "message": "watchlist saved; regenerating (about 1-2 minutes)"})


def serve(root: Path, port: int) -> None:
    Handler.root = root
    Handler.app_dir = root / "data" / "app"
    Handler.token = os.environ.get("STOCKBOT_API_TOKEN", "").strip()
    if not Handler.token:
        log.warning("STOCKBOT_API_TOKEN not set: API is open to anyone on the network")
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    log.info("Stock Guru API on port %d, serving %s", port, Handler.app_dir)
    httpd.serve_forever()
