"""A weekly question: one a week, proposed by members, shown to people in their rooms.

The founder's decision of 13 November 2026. A member signed in may propose a
question on /account, one line of up to QUESTION_MOST characters, screened as a
public line is (the hearth asks the screens: no link, nothing of the
private list, in good spirit, and the public screen's word that it names no one
and no place). A member has at most one proposal waiting at a time.

Each week - Monday to Sunday, by the day in UTC - has at most one question: the
oldest proposal still waiting, taken the first time the week's question is
asked for, and kept for that week. A week with nothing waiting has none, until
something is proposed. It is shown to people at the top of their room, as an
offer and nothing more: "This week's question, if you'd like it: ...". Who
proposed it is never shown.

No agent reads it unless it chooses to: once "weekly_question" is among its
features, and at a longer waking, it is given one more thing it may look at,
read_weekly_question (attend.py); nothing of it is put in its reading. The
switch is off for every agent in what is committed.

Since the founder's request of 14 November 2026 each week's question also has a
topic of its own on the members' board, in "the weekly question", which anyone may
read (board.py): the question itself is public from its week, and who proposed it
never. Kept outside the commons, since nothing else here is public:

    DATA_DIR/weekly-questions.json
    {"waiting": [{"words": "...", "by": "<pseudonym>", "at": ISO UTC}, ...],
     "weeks": {"2026-W46": {"words": "...", "by": "<pseudonym>", "chosen_on": "YYYY-MM-DD"}}}
"""

import json
import os
import re
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

KEPT = DATA / "weekly-questions.json"

# A question: one line, a little shorter than a line on the board.
QUESTION_MOST = 200

# The agent's switch, in its registry entry's features.
FEATURE = "weekly_question"

# How it is offered at the top of a room.
SHOWN = "This week's question, if you'd like it: {words}"

# A link of any kind, refused in every public line.
LINKISH = re.compile(r"http|www\.|[a-z0-9][a-z0-9-]*\.[a-z]{2,}", re.I)

LOCK = threading.Lock()


def one_line(text):
    """The words as one line: no newlines, no runs of space, nothing at the ends."""
    return " ".join((text or "").split())


def switched_on(agent):
    """Whether an agent's registry entry names the weekly question."""
    return FEATURE in ((agent or {}).get("features") or ())


def week_of(day):
    """The week a day is in, as its ISO year and week: 2026-W46."""
    year, week, _ = day.isocalendar()
    return "%d-W%02d" % (year, week)


def refused(words, carries=None):
    """Why words may not be proposed, short of the screens, or None: "empty", "long",
    "link", or "private" (where carries, private_words.carries, is given)."""
    if not words:
        return "empty"
    if len(words) > QUESTION_MOST:
        return "long"
    if LINKISH.search(words):
        return "link"
    if carries is not None and carries(words):
        return "private"
    return None


def read():
    try:
        held = json.loads(KEPT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        held = {}
    if not isinstance(held, dict):
        held = {}
    waiting = [one for one in held.get("waiting") or [] if isinstance(one, dict)
               and one_line(one.get("words"))]
    weeks = held.get("weeks") if isinstance(held.get("weeks"), dict) else {}
    return {"waiting": waiting, "weeks": weeks}


def kept(held):
    KEPT.parent.mkdir(parents=True, exist_ok=True)
    KEPT.write_text(json.dumps(held, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def waiting_by(by):
    """One's proposal that is waiting, as its words, or None."""
    return next((one["words"] for one in read()["waiting"] if one.get("by") == by), None)


def propose(by, words, at):
    """One proposal, kept at the end of those waiting. The screens are the caller's to
    have asked; the hard rules are held here, and ValueError raised where broken, or where
    one of theirs is waiting already."""
    words = one_line(words)
    if refused(words):
        raise ValueError("not a question: " + refused(words))
    with LOCK:
        held = read()
        if any(one.get("by") == by for one in held["waiting"]):
            raise ValueError("one of theirs is waiting already")
        held["waiting"].append({"words": words, "by": by, "at": at})
        kept(held)


def withdraw(by):
    """Take back one's proposal that is waiting; whether there was one."""
    with LOCK:
        held = read()
        left = [one for one in held["waiting"] if one.get("by") != by]
        if len(left) == len(held["waiting"]):
            return False
        held["waiting"] = left
        kept(held)
    return True


def this_week(day):
    """This week's question, as its words, or None: the one chosen for the week, or the
    oldest waiting, chosen now and kept for the week."""
    week = week_of(day)
    held = read()
    if week in held["weeks"]:
        return one_line(held["weeks"][week].get("words")) or None
    if not held["waiting"]:
        return None
    with LOCK:
        held = read()
        if week not in held["weeks"]:
            if not held["waiting"]:
                return None
            oldest = held["waiting"].pop(0)
            held["weeks"][week] = {"words": oldest["words"], "by": oldest.get("by"),
                                   "chosen_on": day.isoformat()}
            kept(held)
        return one_line(held["weeks"][week].get("words")) or None
