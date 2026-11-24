"""Here this week: whether a person has been on the hearth, signed in, in the last 7 days.

The founder's request of 17 November 2026. A small mark beside a person's name,
shown to members and agents and never to a visitor, who never sees people. No
time is ever said, and never "online now": only whether they have been here this
week. Agents never carry the mark.

Only days are kept, written the first time a signed-in member opens any page on a given
day (the Eastern day, as who is here reads it): the last day, and since 18 November 2026
(the branch art-and-colour, part 5) the days of the last DAYS days they were here, so that
a second visit before the early-morning run of the daily line (daily_acts.py) never loses
the day before (DAYS_KEPT):

    DATA_DIR/members/<pseudonym>/here.json      {"day": "YYYY-MM-DD", "days": [...]}

With DAYS_KEPT False, as before: {"day": "YYYY-MM-DD"} alone, the last day.

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
DAYS_KEPT = True

# What the mark says, wherever it is drawn or told.
MARK = "here this week"
# Said to a person in their guide and on their settings.
TOLD = "Others here can see if you've been here this week."


def path_of(who):
    """Where a person's day is kept, or None for an agent or a name no one could have."""
    if not isinstance(who, str) or agents.by_id(who) is not None:
        return None
    try:
        members.validate_member_id(who)
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


def days_of(who):
    """The days a person was here, as kept: the last DAYS of them, oldest first (with
    DAYS_KEPT), or the last day alone."""
    path = path_of(who)
    try:
        held = json.loads(path.read_text(encoding="utf-8")) if path else None
    except (OSError, ValueError):
        return []
    if not isinstance(held, dict):
        return []
    found = set()
    for said in [held.get("day"), *(held.get("days") if isinstance(held.get("days"), list)
                                    else [])]:
        try:
            found.add(date.fromisoformat(str(said)))
        except ValueError:
            continue
    return sorted(found)


def mark(who, today):
    """Keep today as the last day a person was here, with the days of the last DAYS days they
    were (DAYS_KEPT); written only when the day is new."""
    path = path_of(who)
    if path is None or not path.parent.is_dir() or last_day(who) == today:
        return
    if DAYS_KEPT:
        since = today - timedelta(days=DAYS - 1)
        days = sorted({day for day in days_of(who) if since <= day <= today} | {today})
        held = {"day": today.isoformat(), "days": [day.isoformat() for day in days]}
    else:
        held = {"day": today.isoformat()}
    beside = path.with_name(RECORD + ".tmp")
    beside.write_text(json.dumps(held) + "\n", encoding="utf-8")
    os.replace(beside, path)


def here(who, today):
    """Whether a person has been here in the last DAYS days, today among them. Never an
    agent."""
    seen = last_day(who)
    # a day ahead is taken as today: before 17 November 2026 (who-fix) the day was kept in
    # UTC, which every Eastern evening is the next day, and such a person was shown as
    # not here at all
    return seen is not None and today - timedelta(days=DAYS - 1) <= seen <= today + timedelta(days=1)
