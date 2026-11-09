"""The links that work once: a token in an emailed link, and what it was made for.

Each live link is one small file under DATA_DIR/tokens, named by its kind and the
sha256 of its token, never by the token itself:

    tokens/<kind>-<sha256 hex>.json
        {"kind": ..., "name": pseudonym, "made_at": UTC stamp, "expires_at": UTC stamp,
         and whatever the kind keeps beside it: "address" for a confirmation,
         "seal" for a reset - the fingerprint of the vault it was asked against}

A token is taken when it is used, and is gone. One that has expired is let go
whenever the folder is next written, and a new one of a kind for a person lets
go of their older ones, so at most one of each is live for anyone.

tokens/ is in no copy and in no backup: a restore must never bring back a live
link, and a link lost costs only another email. Nothing here logs or prints a
token, an address, or anything a file holds, and no error raised here carries one.
"""

import hashlib
import json
import os
import re
import secrets
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent

# Where the living files are kept, as members.py reckons it.
DATA = Path(os.environ.get("DATA_DIR", REPO))
TOKENS = DATA / "tokens"

KINDS = ("confirm", "reset")
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")  # what secrets.token_urlsafe(32) gives
STAMP = "%Y-%m-%dT%H:%M:%SZ"

LOCK = threading.Lock()  # so a token is taken once, by one request


def _now(now):
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _stamp(at):
    return at.strftime(STAMP)


def _when(text):
    try:
        return datetime.strptime(text, STAMP).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _path(kind, token):
    """The file a token is kept under, or None for a kind or token no link could carry."""
    if kind not in KINDS or not isinstance(token, str) or not TOKEN.fullmatch(token):
        return None
    return TOKENS / ("%s-%s.json" % (kind, hashlib.sha256(token.encode("ascii")).hexdigest()))


def _read(path):
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return held if isinstance(held, dict) else None


def _live(held, kind, now):
    if not held or held.get("kind") != kind:
        return False
    expires = _when(held.get("expires_at"))
    return expires is not None and now < expires


def _held():
    """Every token file there is, with what it holds."""
    if not TOKENS.is_dir():
        return []
    return [(path, _read(path)) for path in TOKENS.glob("*.json")]


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".",
                                         suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(json.dumps(data, indent=2) + "\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def issue(kind, name, lifetime, now=None, **kept):
    """Cut a new token of a kind for a person, and give it back; it is kept only as its hash.

    Whatever has expired is let go first, and so is any older token of the same
    kind for the same person.
    """
    if kind not in KINDS:
        raise ValueError("no such kind of link")
    now = _now(now)
    token = secrets.token_urlsafe(32)
    with LOCK:
        for path, held in _held():
            expired = not held or _when(held.get("expires_at")) is None \
                or _when(held.get("expires_at")) <= now
            theirs = held and held.get("kind") == kind and held.get("name") == name
            if expired or theirs:
                path.unlink(missing_ok=True)
        _write(_path(kind, token), {"kind": kind, "name": name, "made_at": _stamp(now),
                                    "expires_at": _stamp(now + lifetime), **kept})
    return token


def peek(kind, token, now=None):
    """What a live token was made for, without taking it; None for any other."""
    path = _path(kind, token)
    if path is None:
        return None
    held = _read(path)
    return held if _live(held, kind, _now(now)) else None


def take(kind, token, now=None):
    """What a live token was made for, taking it so it works no more; None for any other."""
    path = _path(kind, token)
    if path is None:
        return None
    with LOCK:
        held = _read(path)
        if not _live(held, kind, _now(now)):
            return None
        try:
            path.unlink()
        except OSError:
            return None
    return held


def drop(kind, but_for, **kept):
    """Let go of every token of a kind whose kept fields are these, save the named
    person's: a link to confirm an address stops working once someone else has."""
    with LOCK:
        for path, held in _held():
            if held and held.get("kind") == kind and held.get("name") != but_for                     and all(held.get(field) == value for field, value in kept.items()):
                path.unlink(missing_ok=True)


def waiting(kind, name, now=None):
    """The live token of a kind a person has waiting, as it was kept, or None."""
    now = _now(now)
    for _, held in _held():
        if _live(held, kind, now) and held.get("name") == name:
            return held
    return None


LIFETIMES = {"confirm": timedelta(days=1), "reset": timedelta(hours=1)}
