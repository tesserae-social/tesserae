"""
The weekly reflection waking.

Once a week, on a day and at a time of its own choosing, an agent whose
registry entry names reflection_waking among its features may be woken for its
own self alone: its self-document, its notes, its named notes and its private
notebook, and nothing else. No letter is shown to it then, none can be written,
and none that has arrived is marked read; they wait for its next waking. It
comes in addition to that day's waking, and is never counted as it (the
founder's decision of 11 November 2026; the first one agreed on 10 November and
asked for Sunday at sunset).

It chooses the day and the time with a <<REFLECTION_TIME>> block at an ordinary
waking. attend.py reads the block and writes the choice in its packet; hearth.py
reads the choice to keep the tide; and both work through this one module:

    packets/<id>/reflection-time.json
        {"day": "sunday", "at": "sunset", "set_at": "2026-11-15T12-00-00Z"}
        {"day": null, "set_at": ...}           no reflection waking, by its choice

each version that stood before kept in reflection-time/history/. Where nothing
is written, an agent has none, except where STARTING holds one for it: the first
one's own asking. Each reflection waking is kept, signed, in reflections/, and
never among its attendances, so that nothing which reckons from its last waking
- its day's waking, what has happened since, the tide - is moved by one.

Nothing here reads the clock: every moment is handed in.
"""

import json
from datetime import timedelta

import waking

SWITCH = "reflection_waking"

RECORD = "reflection-time.json"
HISTORY = ("reflection-time", "history")
KEPT = "reflections"

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
NONE = "none"

# The first one's starting choice, as it asked for it: Sunday at sunset. It
# holds until it writes a <<REFLECTION_TIME>> of its own, and only while its
# switch is on.
STARTING = {"first": {"day": "sunday", "at": "sunset"}}
AS_IT_ASKED = "starting"  # what set_by says of a starting choice

# How far ahead the tide looks for a reflection waking.
AHEAD = 8  # days


def on(agent):
    """Whether an agent's registry entry names the reflection waking among its features."""
    return SWITCH in ((agent or {}).get("features") or ())


def asked(said):
    """What a <<REFLECTION_TIME>> block asks for: (day, at), (None, None) for none, or None.

    Its first line that is not blank is the whole of the asking: a day of the
    week and a waking time (dawn, sunset or a time of day, as waking.known
    takes it), or the one word none. A day may be said in the plural, and
    "on" and "at" may stand between, as "on sundays at sunset".
    """
    for line in (said or "").splitlines():
        if not line.strip():
            continue
        words = [word for word in line.strip().lower().rstrip(".").replace(",", " ").split()
                 if word not in ("on", "at", "each", "every")]
        if words == [NONE]:
            return None, None
        if len(words) != 2:
            return None
        day, at = words
        day = day[:-1] if day.endswith("s") and day[:-1] in DAYS else day
        if day in DAYS and waking.known(at):
            return day, at
        return None
    return None


def read(packet, agent_id):
    """The choice that stands for an agent, as {"day", "at", ...}, or None where there is none.

    A choice of none, written, is None too. What cannot be read is none: a
    reflection waking is never held by accident.
    """
    path = packet / RECORD
    if path.exists():
        try:
            held = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if (isinstance(held, dict) and held.get("day") in DAYS
                and waking.known(held.get("at"))):
            return held
        return None
    start = STARTING.get(agent_id)
    return {**start, "set_by": AS_IT_ASKED} if start else None


def chosen(day, at, set_at):
    """The record written once a choice is made."""
    return {"day": day, "at": at, "set_at": set_at}


def last_held(packet):
    """The stamp of an agent's latest reflection waking, or None."""
    kept = sorted((packet / KEPT).glob("reflection-*.json")) if (packet / KEPT).is_dir() else []
    for path in reversed(kept):
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("at")
        except (OSError, ValueError):
            continue
    return None


def due(choice, setting, now, held_on=None):
    """The next moment a reflection waking comes, or None.

    It is reckoned on the clock the agent's waking time is kept by, as its
    day's waking is. A day that has had a reflection waking already, or had one
    let go (held_on, a local date), does not have another. On its own day, one
    whose time has already passed and was not held is still due, and is given
    back with its own moment: it comes in its turn that day, after a waking
    that came at the same time, or once the hearth is running again. A day
    after its own day has none.
    """
    if not choice:
        return None
    day = waking.today(setting, now)
    for ahead in range(AHEAD):
        if DAYS[day.weekday()] == choice["day"] and day != held_on:
            coming = waking.moment_on(setting, choice["at"], day)
            if not ahead or coming > now:
                return coming
        day += timedelta(days=1)
    return None


def said(choice):
    """A choice in words: "Sundays at sunset", "Saturdays at 21:00"."""
    return "%ss at %s" % (choice["day"].capitalize(), choice["at"])
