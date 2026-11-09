"""Invitations: how a person who is not here yet is asked in.

Tesserae is open by invitation only. A member makes an invitation on their
account page, with a note of their own, and is given a link to send the person
themselves; the link works once, and lasts fourteen days. An invitation is its
own vouch: no one else approves it. Each one is one small record:

    invitations/<id>.json
        {"v": 1, "id": 16 random hex characters (not the link's token),
         "token": sha256 hex of the link's token, "by": the inviter's pseudonym,
         "note": their note, "made_at": UTC stamp, "open_until": YYYY-MM-DD,
         "withdrawn_at": UTC stamp or null, "withdrawn_by": pseudonym or null,
         "used_at": UTC stamp or null, "used_by": pseudonym or null}

The token itself is kept nowhere: the link is shown once, to its maker, when it
is made. "by" and "used_by" are the keeper's private record of who invited
whom, and are shown to no one; the inviter is told only whether an invitation
is open, used, expired or withdrawn. Records are never deleted.

An invitation is open through the whole of the Eastern day it is open until,
and expired from the next; nothing sweeps them, and it is worked out each time
one is read. A withdrawn one, a used one and an expired one are all closed, and
the page for any of them says the one same thing.

Who may invite, and when (proposals/invitations-design.md, section 8, and the
founder's decisions of 6 November 2026):
  * the keeper, without count or wait, through 3 September 2027, the last day
    of the founding period; from 4 September 2027 under the member rule;
  * a member, once thirty days have passed since the day they arrived, and then
    once in any thirty days: from the day the last invitation that counts was
    made, plus thirty. One that was made counts, used or expired or still open;
    one withdrawn does not.

Storage and rules only: no route, no page, nothing logged. The hearth holds
INVITING around making, withdrawing and joining, so that no invitation is used
twice or withdrawn while it is being used.
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from build_atrium import CITIZEN_ZONE

VERSION = 1

REPO = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", REPO))
INVITATIONS = DATA / "invitations"

ZONE = ZoneInfo(CITIZEN_ZONE)  # the day turns here as it does everywhere else here
STAMP = "%Y-%m-%dT%H:%M:%SZ"

LASTS = timedelta(days=14)
MEMBER_FIRST_WAIT = timedelta(days=30)
BETWEEN = timedelta(days=30)
FOUNDING_PERIOD_ENDS = date(2027, 9, 4)  # the first day under the ordinary rule

NOTE_LONGEST = 500
NOTE_NEEDED = "Write a note to go with it."
NOTE_TOO_LONG = "A note can be at most 500 characters."

ID = re.compile(r"[0-9a-f]{16}")
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")  # what secrets.token_urlsafe(32) gives

OPEN, USED, EXPIRED, WITHDRAWN = "open", "used", "expired", "withdrawn"

INVITING = threading.Lock()


class InvitationError(Exception):
    """An invitation would not do what was asked. The message is safe to show."""


# ---------------------------------------------------------------- small things


def _now(now):
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _stamp(at):
    return at.strftime(STAMP)


def _when(text):
    try:
        return datetime.strptime(text, STAMP).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def day_of(stamp):
    """The Eastern day a UTC stamp falls on, or None if it is no stamp."""
    when = _when(stamp)
    return when.astimezone(ZONE).date() if when else None


def today(now=None):
    """Today, on the Eastern clock."""
    return _now(now).astimezone(ZONE).date()


def _hash(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


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


def _read(path):
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(held, dict) or not isinstance(held.get("id"), str) \
            or not ID.fullmatch(held["id"]) or not isinstance(held.get("token"), str):
        return None
    return held


def _path(invitation_id):
    if not isinstance(invitation_id, str) or not ID.fullmatch(invitation_id):
        return None
    return INVITATIONS / (invitation_id + ".json")


# ---------------------------------------------------------------- reading


def every():
    """Every invitation there is, newest first."""
    if not INVITATIONS.is_dir():
        return []
    held = [one for one in (_read(path) for path in INVITATIONS.glob("*.json")) if one]
    return sorted(held, key=lambda one: (one.get("made_at") or "", one["id"]), reverse=True)


def of(name):
    """Every invitation a person has made, newest first."""
    return [one for one in every() if one.get("by") == name]


def load(invitation_id):
    path = _path(invitation_id)
    return _read(path) if path else None


def by_token(token):
    """The invitation a link's token is for, whatever its state; None for no invitation."""
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        return None
    wanted = _hash(token)
    for one in every():
        if hmac.compare_digest(one["token"], wanted):
            return one
    return None


def open_until(one):
    try:
        return date.fromisoformat(one.get("open_until"))
    except (TypeError, ValueError):
        return None


def state(one, now=None):
    """open, used, withdrawn or expired."""
    if one.get("used_at"):
        return USED
    if one.get("withdrawn_at"):
        return WITHDRAWN
    until = open_until(one)
    if until is None or today(now) > until:
        return EXPIRED
    return OPEN


def is_open(one, now=None):
    return bool(one) and state(one, now) == OPEN


def open_one(token, now=None):
    """The invitation a link's token is for, while it is open; None for any other."""
    one = by_token(token)
    return one if is_open(one, now) else None


def all_open(now=None):
    """Every invitation still open, by anyone, newest first."""
    return [one for one in every() if is_open(one, now)]


# ---------------------------------------------------------------- the rules


def counts(one):
    """Whether an invitation counts against its maker's thirty days: made, and not withdrawn."""
    return not one.get("withdrawn_at")


def may_invite(name, role, arrived_at, now=None):
    """(True, None) if this person may make an invitation today; else (False, the day
    from which they may)."""
    on = today(now)
    if role == "keeper" and on < FOUNDING_PERIOD_ENDS:
        return True, None
    arrived = day_of(arrived_at)
    if arrived is None:  # no arrival that can be read is no invitation
        return False, None
    from_day = arrived + MEMBER_FIRST_WAIT
    made = [day_of(one.get("made_at")) for one in of(name) if counts(one)]
    made = [day for day in made if day is not None]
    if made:
        from_day = max(from_day, max(made) + BETWEEN)
    return (True, None) if on >= from_day else (False, from_day)


def note_kept(text):
    """A note as it is kept: as written, its line breaks made plain. InvitationError if
    there is none, or it is too long."""
    if not isinstance(text, str):
        raise InvitationError(NOTE_NEEDED)
    note = text.replace("\r\n", "\n").replace("\r", "\n")
    if not note.strip():
        raise InvitationError(NOTE_NEEDED)
    if len(note) > NOTE_LONGEST:
        raise InvitationError(NOTE_TOO_LONG)
    return note


# ---------------------------------------------------------------- writing


def make(by, note, now=None):
    """Make an invitation, and give back (its record, its link's token). The token is
    kept only as its hash; the caller shows it once and forgets it.

    Whether the maker may invite is the caller's to ask, inside INVITING.
    """
    note = note_kept(note)
    now = _now(now)
    token = secrets.token_urlsafe(32)
    while True:
        invitation_id = secrets.token_hex(8)
        if not _path(invitation_id).exists():
            break
    record = {"v": VERSION, "id": invitation_id, "token": _hash(token), "by": by,
              "note": note, "made_at": _stamp(now),
              "open_until": (today(now) + LASTS).isoformat(),
              "withdrawn_at": None, "withdrawn_by": None, "used_at": None, "used_by": None}
    _write(_path(invitation_id), record)
    return record, token


def withdraw(invitation_id, who, keeper=False, now=None):
    """Withdraw an open invitation: its maker may, and the keeper. Gives back the record,
    or None where it is not theirs to withdraw, or not open."""
    one = load(invitation_id)
    if not one or not is_open(one, now) or not (keeper or one.get("by") == who):
        return None
    one = dict(one, withdrawn_at=_stamp(_now(now)), withdrawn_by=who)
    _write(_path(one["id"]), one)
    return one


def mark_used(invitation_id, used_by, now=None):
    """Mark an open invitation used by the person who joined by it. None if it is not open."""
    one = load(invitation_id)
    if not is_open(one, now):
        return None
    one = dict(one, used_at=_stamp(_now(now)), used_by=used_by)
    _write(_path(one["id"]), one)
    return one
