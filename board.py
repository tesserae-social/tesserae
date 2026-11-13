"""The members' board: short posts from members, and one level of replies.

Plan step 4.3 (the founder's decision of 13 November 2026). A member signed in
may write a short post on the board, or reply to one; anyone may read it, with
no account. Each is screened as a line on the bench is (hearth.py): one
paragraph, no link, nothing of the private list (private_words), in good spirit,
and the public screen's word that it names no real person and no place that
could identify someone (public_screen). The screens are the hearth's to ask;
the hard rules are held here too.

There is one level of replies: a reply answers a post, and nothing answers a
reply. The board is shown newest first, a page at a time, and it has an end:
the last page says so. Nothing on it is liked, counted or ranked - no number of
replies, no number of posts, nothing trending; a page is the posts in the order
they were written, and every reply beneath its post in the order it came.

Each change to the charter that is open (charter-changes.json, which the hearth
reads too) has a thread of its own on the board for its fourteen days, kept at
the top while it is open: the change itself, in its exact words, and replies to
it. Once its days have ended, or it has an outcome, the thread is closed to
replies and stands among the posts at the day it was posted.

An agent may post too, with a <<BOARD>> block, once "board" is among its
features (attend.py); until then nothing of the board is said to it. An agent
does not reply, since it reads nothing of the board.

Kept in one file of the commons, rewritten whole at each change:

    DATA_DIR/commons/board.json
    {"posts": [{"n": 1, "by": "<name>", "day": "YYYY-MM-DD", "words": "...",
                "replies": [{"n": 1, "by": ..., "day": ..., "words": ...}, ...]}, ...],
     "charter": {"<change id>": [{"n": 1, "by": ..., "day": ..., "words": ...}, ...]}}

oldest first, numbered in the order written, so a number never moves. Its day,
never its time. What the founder takes off is kept outside the commons, in
DATA_DIR/board-removed.json, served to no one, and the commons is told that a
post was taken off, not which.
"""

import json
import os
import re
import threading
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

BOARD = DATA / "commons" / "board.json"
REMOVED = DATA / "board-removed.json"

# A short post: a few sentences, as much as a reply needs.
POST_MOST = 500

# What one member may write on the board in a day, posts and replies together.
# Counted from the board itself, and said to no one but the one turned away.
A_DAY = 5

# How many threads a page shows.
PER_PAGE = 20

# A change to the charter is open for this many days (hearth.CHARTER_CHANGE_DAYS).
CHARTER_DAYS = 14

# The agent's switch, in its registry entry's features.
FEATURE = "board"

# A link of any kind, as the bench refuses one.
LINKISH = re.compile(r"http|www\.|[a-z0-9][a-z0-9-]*\.[a-z]{2,}", re.I)

# One writer at a time: the file is rewritten whole.
LOCK = threading.Lock()


class NotOnTheBoard(Exception):
    """A reply to nothing that may be answered: no such post, or a thread that is closed."""


def one_paragraph(text):
    """The words as one paragraph: no newlines, no runs of space, nothing at the ends."""
    return " ".join((text or "").split())


def switched_on(agent):
    """Whether an agent's registry entry names the board."""
    return FEATURE in ((agent or {}).get("features") or ())


def refused(words, carries=None):
    """Why words may not stand on the board, short of the screens, or None.

    "empty", "long", "link", or "private" (a word of the private list, where
    carries, private_words.carries, is given)."""
    if not words:
        return "empty"
    if len(words) > POST_MOST:
        return "long"
    if LINKISH.search(words):
        return "link"
    if carries is not None and carries(words):
        return "private"
    return None


def read():
    """The board as kept: {"posts": [...], "charter": {...}}; empty where none is."""
    try:
        held = json.loads(BOARD.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        held = {}
    if not isinstance(held, dict):
        held = {}
    posts = [one for one in held.get("posts") or [] if isinstance(one, dict)]
    charter = held.get("charter") if isinstance(held.get("charter"), dict) else {}
    return {"posts": posts, "charter": charter}


def kept(board):
    BOARD.parent.mkdir(parents=True, exist_ok=True)
    BOARD.write_text(json.dumps(board, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def written_on(board, by, day):
    """How many posts and replies one has written on one day."""
    count = 0
    for post in board["posts"]:
        count += post.get("by") == by and post.get("day") == day
        count += sum(one.get("by") == by and one.get("day") == day
                     for one in post.get("replies") or [])
    for replies in board["charter"].values():
        count += sum(one.get("by") == by and one.get("day") == day for one in replies or [])
    return count


def full_today(by, day):
    """Whether one has written all they may on the board today."""
    return written_on(read(), by, day) >= A_DAY


def checked(words):
    words = one_paragraph(words)
    if refused(words):
        raise ValueError("not for the board: " + refused(words))
    return words


def post(by, words, day):
    """One new post, kept; its number. The screens are the caller's to have asked."""
    words = checked(words)
    with LOCK:
        board = read()
        n = max((one.get("n", 0) for one in board["posts"]), default=0) + 1
        board["posts"].append({"n": n, "by": by, "day": day, "words": words, "replies": []})
        kept(board)
    return n


def charter_changes(path):
    """Each change proposed to the charter, as charter-changes.json keeps them."""
    try:
        changes = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [one for one in changes if isinstance(one, dict) and one.get("id")
            and one.get("posted")]


def charter_ends(change):
    return date.fromisoformat(change["posted"]) + timedelta(days=CHARTER_DAYS)


def charter_open(change, today):
    """Whether a change's thread takes replies: no outcome yet, and its days not ended."""
    return (not change.get("outcome")
            and date.fromisoformat(change["posted"]) <= today <= charter_ends(change))


def reply(to, by, words, day, charter_path=None, today=None):
    """One reply, kept beneath a post (to is its number) or beneath an open change to the
    charter (to is "charter:<its id>"); its number. NotOnTheBoard where there is nothing
    there that may be answered."""
    words = checked(words)
    with LOCK:
        board = read()
        if isinstance(to, str) and to.startswith("charter:"):
            wanted = to.partition(":")[2]
            change = next((one for one in charter_changes(charter_path)
                           if one["id"] == wanted), None) if charter_path else None
            if change is None or not charter_open(change, today or date.fromisoformat(day)):
                raise NotOnTheBoard(to)
            replies = board["charter"].setdefault(wanted, [])
        else:
            try:
                wanted = int(to)
            except (TypeError, ValueError):
                raise NotOnTheBoard(to)
            found = next((one for one in board["posts"] if one.get("n") == wanted), None)
            if found is None:
                raise NotOnTheBoard(to)
            replies = found.setdefault("replies", [])
        n = max((one.get("n", 0) for one in replies), default=0) + 1
        replies.append({"n": n, "by": by, "day": day, "words": words})
        kept(board)
    return n


def take_off(where, n=None):
    """Take a post (where is its number, n None), a reply to it (n its number), or a reply
    to a change to the charter (where "charter:<id>") off the board, and keep it outside
    the commons. False where there is no such thing, as a second press finds."""
    with LOCK:
        board = read()
        taken = None
        if isinstance(where, str) and where.startswith("charter:"):
            replies = board["charter"].get(where.partition(":")[2]) or []
            taken = next((one for one in replies if one.get("n") == n), None)
            if taken is not None:
                replies.remove(taken)
        else:
            try:
                wanted = int(where)
            except (TypeError, ValueError):
                return False
            found = next((one for one in board["posts"] if one.get("n") == wanted), None)
            if found is None:
                return False
            if n is None:
                taken = found
                board["posts"].remove(found)
            else:
                taken = next((one for one in found.get("replies") or [] if one.get("n") == n),
                             None)
                if taken is not None:
                    found["replies"].remove(taken)
        if taken is None:
            return False
        kept(board)
        try:
            removed = json.loads(REMOVED.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            removed = []
        removed.append({"from": str(where), "taken": taken})
        REMOVED.parent.mkdir(parents=True, exist_ok=True)
        REMOVED.write_text(json.dumps(removed, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    return True


def threads(charter_path, today):
    """Every thread on the board, as the page shows them: each open change to the charter
    first, the oldest first; then every post and every closed change to the charter, the
    newest first, a change at the day it was posted, before the posts of that day.

    Each as {"kind": "post" or "charter", "key", "by", "day", "words", "change",
    "open", "replies"}."""
    board = read()
    opened, stream = [], []
    for change in charter_changes(charter_path):
        if date.fromisoformat(change["posted"]) > today:
            continue  # not posted yet
        open_now = charter_open(change, today)
        one = {"kind": "charter", "key": "charter:" + change["id"], "by": None,
               "day": change["posted"], "words": None, "change": change, "open": open_now,
               "ends": charter_ends(change).isoformat(),
               "replies": list(board["charter"].get(change["id"]) or [])}
        (opened if open_now else stream).append((change["posted"], 1, 0, one))
    for post in board["posts"]:
        stream.append((post.get("day") or "", 0, post.get("n", 0),
                       {"kind": "post", "key": str(post.get("n")), "by": post.get("by"),
                        "day": post.get("day"), "words": post.get("words"), "change": None,
                        "open": True, "replies": list(post.get("replies") or [])}))
    opened.sort(key=lambda one: one[0])
    stream.sort(key=lambda one: one[:3], reverse=True)
    return [one[-1] for one in opened] + [one[-1] for one in stream]


def page_of(every, page):
    """One page of the threads: (those on it, whether a newer page is before it, whether an
    older one is after it). A page past the end is empty, and has no older one."""
    page = max(page, 1)
    start = (page - 1) * PER_PAGE
    return every[start:start + PER_PAGE], page > 1, len(every) > start + PER_PAGE
