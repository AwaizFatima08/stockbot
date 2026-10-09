"""Cloud carrier: publish the app bundle to Firestore and collect watchlist
requests from the phone app. Multi-user shape from day one (design decision
10 Oct 2026): one engine publishes one bundle; users are rows in
`allowed_users` keyed by email; per-user state lives under `users/{uid}`.

Firestore layout
    app/summary                       {as_of, stocks:[...], ...}
    app/symbols                       {as_of, symbols:[...]}
    app/scorecard                     {as_of, markdown}
    stocks/{SYM}                      detail document (no chart image)
    history/{SYM}                     {symbol, rows:[{d,o,h,l,c,v}...]}   (<1 MB)
    allowed_users/{email}             {added_at, role}         <- who may read
    requests/watchlist                {symbols:[..10], requested_by, requested_at, status, message}

Credentials: service-account JSON at secrets/firebase-admin.json (never in git)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)
KEY_PATH = "secrets/firebase-admin.json"
MAX_DOC_BYTES = 900_000  # stay under Firestore's 1 MiB document limit


class CloudDisabled(Exception):
    pass


def _client(root: Path):
    key = root / KEY_PATH
    if not key.exists():
        raise CloudDisabled(f"{KEY_PATH} not found; cloud publishing is off")
    import firebase_admin
    from firebase_admin import credentials, firestore
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(key)))
    return firestore.client()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _trim_history(doc: dict) -> dict:
    """Keep the history document under the size limit by dropping oldest rows."""
    rows = doc.get("rows", [])
    while rows and len(json.dumps({"symbol": doc["symbol"], "rows": rows}, separators=(",", ":")).encode()) > MAX_DOC_BYTES:
        rows = rows[len(rows) // 10:]
    doc["rows"] = rows
    return doc


def publish(root: Path, app_dir: Path) -> dict:
    """Upload data/app/* to Firestore. Returns counts."""
    db = _client(root)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary = _load(app_dir / "summary.json")
    summary.pop("holdings", None)  # personal; never leaves the NAS
    summary["published_at"] = now
    batch = db.batch()
    n = 0
    batch.set(db.collection("app").document("summary"), summary); n += 1
    batch.set(db.collection("app").document("symbols"), _load(app_dir / "symbols.json")); n += 1
    batch.set(db.collection("app").document("scorecard"), _load(app_dir / "scorecard.json")); n += 1
    for p in sorted((app_dir / "stocks").glob("*.json")):
        d = _load(p)
        d.pop("chart", None)
        batch.set(db.collection("stocks").document(p.stem), d); n += 1
    batch.commit()
    # history docs are large; commit in small batches
    hist_n = 0
    for p in sorted((app_dir / "history").glob("*.json")):
        db.collection("history").document(p.stem).set(_trim_history(_load(p)))
        hist_n += 1
    # remove stock/history docs for symbols no longer on the watchlist
    current = {p.stem for p in (app_dir / "stocks").glob("*.json")}
    removed = 0
    for coll in ("stocks", "history"):
        for doc in db.collection(coll).stream():
            if doc.id not in current:
                doc.reference.delete()
                removed += 1
    log.info("published %d docs + %d history docs, removed %d stale", n, hist_n, removed)
    return {"docs": n, "history": hist_n, "removed": removed, "as_of": summary.get("as_of")}


def allow_user(root: Path, email: str, role: str = "user") -> None:
    db = _client(root)
    db.collection("allowed_users").document(email.strip().lower()).set(
        {"added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "role": role})


def deny_user(root: Path, email: str) -> None:
    db = _client(root)
    db.collection("allowed_users").document(email.strip().lower()).delete()


def list_users(root: Path) -> list[dict]:
    db = _client(root)
    return [{"email": d.id, **d.to_dict()} for d in db.collection("allowed_users").stream()]


def pending_request(root: Path) -> dict | None:
    """The watchlist request document if one is waiting ('pending')."""
    db = _client(root)
    doc = db.collection("requests").document("watchlist").get()
    if not doc.exists:
        return None
    d = doc.to_dict() or {}
    return d if d.get("status") == "pending" else None


def set_request_status(root: Path, status: str, message: str = "") -> None:
    db = _client(root)
    db.collection("requests").document("watchlist").set(
        {"status": status, "message": message, "handled_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}, merge=True)
