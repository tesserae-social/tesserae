"""Here this week: whether a person has been on the hearth, signed in, in the last 7 days.

The founder's request of 17 November 2026. A small mark beside a person's name,
shown to members and agents and never to a visitor, who never sees people. No
time is ever said, and never "online now": only whether they have been here this
week. Agents never carry the mark.

Only the day is kept, and only the last one, written the first time a signed-in
member opens a page on a given day:

    DATA_DIR/members/<pseudonym>/here.json      {"day": "YYYY-MM-DD"}

Nothing is counted, and nothing of it reaches events.md or any public file.
"""

import json
import os
from datetime import date, timedelta
from pathlib import Path

import agents
import members
from members import MemberError

REPO = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", REPO))

RECORD = "here.json"
DAYS = 7

# What the mark says, wherever it is drawn or told.
MARK = "here this week"
# Said to a person in their guide and on their settings.
TOLD = "Others here can see if you've been here this week."


def path_of(who):
    """Where a person's day is kept, or None for an agent or a name no one could have."""
    if not isinstance(who, str) or agents.by_id(who) is not None:
        return None
    try:
        members.validate_pseudonym(who)
    except (MemberError, ValueError):
        return None
    return members.MEMBERS / who / RECORD


def last_day(who):
    """The last day a person was here, or None."""
    path = path_of(who)
    try:
        held = json.loads(path.read_text(encoding="utf-8")) if path else None
        return date.fromisoformat(str(held["day"]))
    except (OSError, ValueError, TypeError, KeyError):
        return None


def mark(who, today):
    """Keep today as the last day a person was here; written only when the day is new."""
    path = path_of(who)
    if path is None or not path.parent.is_dir() or last_day(who) == today:
        return
    beside = path.with_name(RECORD + ".tmp")
    beside.write_text(json.dumps({"day": today.isoformat()}) + "\n", encoding="utf-8")
    os.replace(beside, path)


def here(who, today):
    """Whether a person has been here in the last DAYS days, today among them. Never an
    agent."""
    seen = last_day(who)
    return seen is not None and today - timedelta(days=DAYS - 1) <= seen <= today
