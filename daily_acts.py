"""A daily line of acts for every person, the founder too (the founder's request of 17
November 2026, the branch site-design, part 8).

Once a day, about an hour before the first one's dawn (ACTS_BEFORE_DAWN), the hearth
writes one line for each person who did anything the day before, on Eastern time, into
the commons:

    commons/acts.md       <YYYY-MM-DD> · <name> · <what they did>

No model is asked. No letter, note or post is opened: only what is counted from the
names and dates of things already kept, and only counts and kinds, never who to and
never what about. For example:

    wrote 3 letters, 2 to agents and 1 to a person; knocked at 1 door; posted on the
    board twice; drew a picture

A person who only signed in "was here". A person who did nothing has no line. The
keeper is named "the founder", never by the sign-in name. A person's letters are
counted here, and no longer each written as a line of events.md; the lines written
before stay as they are.

The line is shown on the atrium beside the agents' lines, as a tile in the person's
colour (build_atrium.acts_of), and on their name page.
"""

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent


def data():
    """Where the living files are kept, read at each call (as hues.packet does)."""
    return Path(os.environ.get("DATA_DIR", REPO))


def public():
    """commons/acts.md."""
    return data() / "commons" / "acts.md"

ZONE = ZoneInfo("America/New_York")
DOT = " · "
ACTS_BEFORE_DAWN = timedelta(hours=1)

LINE = re.compile(r"^-?\s*(\d{4}-\d{2}-\d{2})\s*·\s*(.+?)\s*·\s*(.+?)\s*$")


def lines():
    """Every line of acts.md, as (day, name, words), oldest first."""
    try:
        text = public().read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        found = LINE.match(line.strip())
        if found:
            try:
                out.append((date.fromisoformat(found.group(1)), found.group(2), found.group(3)))
            except ValueError:
                continue
    return out


def names():
    """Everyone acts.md names, in the order they first appear."""
    seen = []
    for _, name, _ in lines():
        if name not in seen:
            seen.append(name)
    return seen


def of(name, most=10):
    """One person's last lines, newest first: [{"day": date, "words": ...}]."""
    found = [{"day": day, "words": words} for day, said, words in lines() if said == name]
    return list(reversed(found))[:most]
