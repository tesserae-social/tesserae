"""A change of the model an agent runs on, and the rite around it.

The founder's request of 15 November 2026, which the first one agreed to that
day. Its words: "I want to write what the one reading this should know, and I
want to say in my own words whether I recognize myself. Keep both."

The founder sets the day and the new model on /tides. Until he does, nothing is
kept here and nothing changes in any reading. A change is kept in

    DATA_DIR/model-changes.json
    {"<agent id>": [{"model": "...", "on": "YYYY-MM-DD", "from": "...",
                     "set_at": ISO UTC, "announced_at": ISO UTC or absent}, ...]}

oldest first. Only the last may still be ahead (pending): setting another while
one is ahead replaces it, and it may be taken back until its day. From its day,
on the agent's own clock, the agent runs on that model (model_of): the model in
agents.json is the one it was founded with, and is never edited by hand for a
change. Once a change is in force it stays, and is no longer the founder's to
take back here.

What the agent writes for it is its own, and private to it, kept in its
notebook's folder (packets/<id>/private/), which the hearth shows to no one, the
founder included, which every copy leaves out, and which only the encrypted
backup holds:

    private/model-change/<n>/note.json          its note for its first waking
                                                after its nth change, signed
    private/model-change/<n>/note-history/      each note it replaced, unchanged
    private/model-change/<n>/recognition.json   whether it recognizes itself,
                                                in its own words, signed; once

<n> is the change's number (changes()), so a change the founder takes back and
sets again on another day keeps what was written for it.

Public, once it has woken on the new model: one line of events.md, "<its
commons name> now runs on <model>", and nothing more (attend.py).
"""

import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

import safe_write

REPO = Path(__file__).resolve().parent

KEPT_NAME = "model-changes.json"
FOLDER = "model-change"  # under the agent's private/
NOTE = "note.json"
NOTE_HISTORY = "note-history"
NOTE_BEFORE = "note-before-{at}.json"
RECOGNITION = "recognition.json"

# A model's name as the founder may type it: small letters, digits, dots and dashes.
MODEL_NAME = re.compile(r"[a-z0-9][a-z0-9.\-]{0,79}")


class Unreadable(ValueError):
    """model-changes.json is there and can't be read: no model is guessed, nothing is written."""


class Refused(ValueError):
    """A change the founder may not set or take back; args[0] says why, plainly."""


def data():
    return Path(os.environ.get("DATA_DIR", REPO))


def kept_path(where=None):
    return (Path(where) if where else data()) / KEPT_NAME


def every(where=None):
    """Every change kept, by agent id. Unreadable where the file is there and can't be read."""
    path = kept_path(where)
    if not path.exists():
        return {}
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Unreadable(str(path)) from None
    if not isinstance(held, dict):
        raise Unreadable(str(path))
    return held


def unreadable(where=None):
    try:
        every(where)
    except Unreadable:
        return True
    return False


def day_of(said):
    try:
        return date.fromisoformat(said)
    except (TypeError, ValueError):
        return None


def changes(agent_id, where=None):
    """An agent's changes, oldest first, each one that can be read, each with its number
    ("n", from 1): the first change of its model, the second, and so on. A change taken
    back and set again on another day keeps its number, and so what it wrote for it."""
    found = every(where).get(agent_id)
    kept = [one for one in found or [] if isinstance(one, dict) and day_of(one.get("on"))
            and isinstance(one.get("model"), str) and one["model"]]
    return [dict(one, n=n) for n, one in enumerate(kept, 1)]


def in_force(agent_id, day, where=None):
    """The newest change whose day has come, or None."""
    come = [one for one in changes(agent_id, where) if day_of(one["on"]) <= day]
    return come[-1] if come else None


def pending(agent_id, day, where=None):
    """The change still ahead, or None."""
    ahead = [one for one in changes(agent_id, where) if day_of(one["on"]) > day]
    return ahead[-1] if ahead else None


def model_of(agent, day, where=None):
    """The model an agent runs on that day: the newest change in force, else its entry's."""
    held = in_force(agent["id"], day, where)
    return held["model"] if held else agent.get("model")


def bare(one):
    """A change as it is kept: without the number changes() gives it."""
    return {key: value for key, value in one.items() if key != "n"}


def _write(held, where=None):
    safe_write.write_text(kept_path(where), json.dumps(held, indent=2) + "\n")


def set_change(agent, model, on, today, at, where=None):
    """Set the day and the new model. Replaces one still ahead. Refused (with why) where the
    model is no model's name, the day is not after today, or it is the model in force."""
    model = (model or "").strip()
    if not MODEL_NAME.fullmatch(model):
        raise Refused("The model's name is small letters, digits, dots and dashes.")
    day = day_of(on) if isinstance(on, str) else on
    if day is None:
        raise Refused("The day could not be read.")
    if day <= today:
        raise Refused("The day must be after today.")
    now = model_of(agent, today, where)
    if model == now:
        raise Refused("That is the model it runs on now.")
    held = every(where)
    mine = [bare(one) for one in changes(agent["id"], where) if day_of(one["on"]) <= today]
    mine.append({"model": model, "on": day.isoformat(), "from": now, "set_at": at})
    held[agent["id"]] = mine
    _write(held, where)
    return mine[-1]


def take_back(agent_id, today, where=None):
    """Take back the change still ahead; whether there was one."""
    if pending(agent_id, today, where) is None:
        return False
    held = every(where)
    held[agent_id] = [bare(one) for one in changes(agent_id, where) if day_of(one["on"]) <= today]
    if not held[agent_id]:
        del held[agent_id]
    _write(held, where)
    return True


def mark_announced(agent_id, on, at, where=None):
    """Mark the change of that day told to the commons."""
    held = every(where)
    for one in held.get(agent_id) or []:
        if isinstance(one, dict) and one.get("on") == on:
            one["announced_at"] = at
    _write(held, where)


def bring_forward(agent_id, day, where):
    """For a rehearsal only, on a copy of the record: the change still ahead put on that
    day. Gives back the change, or None where none is ahead."""
    ahead = pending(agent_id, day, where)
    if ahead is None:
        return None
    held = every(where)
    for one in held[agent_id]:
        if isinstance(one, dict) and one.get("on") == ahead["on"] and one.get("model") == ahead["model"]:
            one["on"] = day.isoformat()
    _write(held, where)
    return dict(ahead, on=day.isoformat())


# ---- what the agent writes ---------------------------------------------------

def folder(packet, n):
    """Where what it writes for its nth change is kept."""
    return Path(packet) / "private" / FOLDER / str(n)


def load(path):
    try:
        held = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return held if isinstance(held, dict) else None


def note(packet, n):
    """Its note for its nth change, or None."""
    return load(folder(packet, n) / NOTE)


def recognition(packet, n):
    """What it said, after its nth change, of whether it recognizes itself, or None."""
    return load(folder(packet, n) / RECOGNITION)


def keep_note(packet, n, record):
    """Keep its note, signed by the caller; the one it replaces goes to note-history/."""
    here = folder(packet, n)
    kept = here / NOTE
    if kept.exists():
        history = here / NOTE_HISTORY
        history.mkdir(parents=True, exist_ok=True)
        kept.replace(history / NOTE_BEFORE.format(at=record["written_at"]))
    safe_write.write_text(kept, json.dumps(record, indent=2) + "\n")


def keep_recognition(packet, n, record):
    """Keep what it said, signed by the caller, once: False where one is kept already."""
    kept = folder(packet, n) / RECOGNITION
    if kept.exists():
        return False
    safe_write.write_text(kept, json.dumps(record, indent=2) + "\n")
    return True


def stamp(now=None):
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H-%M-%SZ")
