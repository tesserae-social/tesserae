"""The members' board: topics in three sections, and posts in each topic, oldest first.

Plan step 4.3 (the founder's decision of 13 November 2026), reorganised by the
founder's request of 14 November 2026.

Three sections:

    place          "the place": ideas and changes for the site. Every change
                   proposed to the charter (charter-changes.json) has a topic of
                   its own here, made automatically.
    weekly         "the weekly question": one topic each week that has a
                   question (weekly.py), made automatically.
    conversation   "conversation": anything else.

The place and the weekly question may be read by anyone; conversation only by
members. Only members post, and an agent may post in the place behind its
switch ("board" among its features, off for every agent). A member starts a
topic in the place or in conversation, with a subject of up to SUBJECT_MOST
characters and a first post.

Inside a topic the posts are shown oldest first. A reply is flat: it may name
the post it answers (to), and the page then shows a short quote of that post.
A post may mention up to MENTIONS_MOST people, as @name.

Nothing is ever edited, neither a post nor a subject. A post may be taken down
by whoever wrote it: its words are deleted for good and kept nowhere, and the
board shows who took it down and when. If the first post of a topic is taken
down, the topic's subject is deleted with it. The keeper may take down anyone's
post: its words are kept outside the commons, in DATA_DIR/board-removed.json,
served to no one.

Each post is screened, by the hearth, as every public line is: one paragraph, no
link, nothing of the private list (private_words), in good spirit, and the
public screen's word that it names no real person and no place. The hard rules
are held here too.

Kept in one file of the commons, rewritten whole at each change:

    DATA_DIR/commons/board.json
    {"seq": <the last number given to a post anywhere on the board>,
     "topics": [{"n": 1, "section": "place" or "conversation", "subject": "..." or null,
                 "by": "<name>", "day": "YYYY-MM-DD", "posts": [POST, ...]}, ...],
     "auto": {"charter:<change id>": [POST, ...], "week:2026-W46": [POST, ...]}}

    POST = {"n": 1, "seq": 7, "by": "<name>", "day": "YYYY-MM-DD", "words": "..." or null,
            "to": <the n of the post it answers> or null, "mentions": ["<name>", ...],
            "taken": null or {"by": "self" or "keeper", "day": "YYYY-MM-DD"}}

Its day, never its time; seq only orders what was written on the same day. A
board kept in the shape it had before topics (posts with replies) is read as
topics in conversation, the subject made of the first words of the post.
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

# The three sections, in the order they are shown, and their names on the page.
PLACE, WEEKLY, CONVERSATION = "place", "weekly", "conversation"
SECTIONS = (PLACE, WEEKLY, CONVERSATION)
SECTION_NAMES = {PLACE: "the place", WEEKLY: "the weekly question",
                 CONVERSATION: "conversation"}
PUBLIC = frozenset({PLACE, WEEKLY})          # anyone may read these
STARTED_BY_MEMBERS = (PLACE, CONVERSATION)   # where a member may start a topic

# A short post: a few sentences, as much as a reply needs.
POST_MOST = 500

# A topic's subject: one short line.
SUBJECT_MOST = 80

# What one member may write on the board in a day, topics and posts together.
# Counted from the board itself, and said to no one but the one turned away.
A_DAY = 5

# How many topics a page lists.
PER_PAGE = 15

# The most people one post may mention.
MENTIONS_MOST = 3

# How long a quote of the post replied to is, in characters, before it is cut.
QUOTE_MOST = 120

# A change to the charter takes posts for this many days (hearth.CHARTER_CHANGE_DAYS).
CHARTER_DAYS = 14

# The agent's switch, in its registry entry's features.
FEATURE = "board"

# A link of any kind, refused in every public line.
LINKISH = re.compile(r"http|www\.|[a-z0-9][a-z0-9-]*\.[a-z]{2,}", re.I)

# A member's name, as members.PSEUDONYM allows, after an @.
MEMBER_MENTION = re.compile(r"@([a-z][a-z0-9]*(?:-[a-z0-9]+)*)(?![a-z0-9-])", re.I)

# One writer at a time: the file is rewritten whole.
LOCK = threading.Lock()


class NotOnTheBoard(Exception):
    """Nothing there that may be written to: no such topic or post, or a topic that is closed."""


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


def subject_refused(subject, carries=None):
    """Why a subject may not stand, short of the screens, or None: "no_subject",
    "subject_long", "link" or "private"."""
    if not subject:
        return "no_subject"
    if len(subject) > SUBJECT_MOST:
        return "subject_long"
    if LINKISH.search(subject):
        return "link"
    if carries is not None and carries(subject):
        return "private"
    return None


def mentions_in(words, members=(), agents=()):
    """Whom words mention, in the order first mentioned, each once: a member as @name, an
    agent as @ and its commons name. Only names that are someone's count."""
    found = []
    known = {name.lower(): name for name in members}
    for match in MEMBER_MENTION.finditer(words or ""):
        name = known.get(match.group(1).lower())
        if name:
            found.append((match.start(), name))
    lowered = (words or "").lower()
    for name in sorted(agents, key=len, reverse=True):
        at = lowered.find("@" + name.lower())
        if at >= 0:
            found.append((at, name))
    found.sort()
    said = []
    for _, name in found:
        if name not in said:
            said.append(name)
    return said


# ---- the file ----------------------------------------------------------------

def from_before_topics(held):
    """A board kept before topics, as topics in conversation: each post a topic, its
    replies posts in it answering the first; each change's replies, posts in its topic."""
    seq = 0
    topics = []
    for old in held.get("posts") or []:
        if not isinstance(old, dict):
            continue
        words = one_paragraph(old.get("words"))
        subject = words if len(words) <= SUBJECT_MOST else (
            words[:SUBJECT_MOST - 1].rsplit(" ", 1)[0] + "…")
        seq += 1
        posts = [{"n": 1, "seq": seq, "by": old.get("by"), "day": old.get("day"),
                  "words": words or None, "to": None, "mentions": [], "taken": None}]
        for reply in old.get("replies") or []:
            if isinstance(reply, dict):
                seq += 1
                posts.append({"n": len(posts) + 1, "seq": seq, "by": reply.get("by"),
                              "day": reply.get("day"), "words": one_paragraph(reply.get("words")),
                              "to": 1, "mentions": [], "taken": None})
        topics.append({"n": len(topics) + 1, "section": CONVERSATION, "subject": subject,
                       "by": old.get("by"), "day": old.get("day"), "posts": posts})
    auto = {}
    charter = held.get("charter") if isinstance(held.get("charter"), dict) else {}
    for change_id, replies in charter.items():
        posts = []
        for reply in replies or []:
            if isinstance(reply, dict):
                seq += 1
                posts.append({"n": len(posts) + 1, "seq": seq, "by": reply.get("by"),
                              "day": reply.get("day"), "words": one_paragraph(reply.get("words")),
                              "to": None, "mentions": [], "taken": None})
        auto["charter:" + change_id] = posts
    return {"seq": seq, "topics": topics, "auto": auto}


def read():
    """The board as kept: {"seq", "topics", "auto"}; empty where none is."""
    try:
        held = json.loads(BOARD.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        held = {}
    if not isinstance(held, dict):
        held = {}
    if "topics" not in held and ("posts" in held or "charter" in held):
        return from_before_topics(held)
    topics = [one for one in held.get("topics") or [] if isinstance(one, dict)]
    auto = held.get("auto") if isinstance(held.get("auto"), dict) else {}
    seq = held.get("seq") if isinstance(held.get("seq"), int) else 0
    return {"seq": seq, "topics": topics, "auto": auto}


def kept(board):
    BOARD.parent.mkdir(parents=True, exist_ok=True)
    BOARD.write_text(json.dumps(board, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def every_post(board):
    for topic in board["topics"]:
        yield from topic.get("posts") or []
    for posts in board["auto"].values():
        yield from posts or []


def written_on(board, by, day):
    """How many posts one has written on one day, the first post of a topic among them."""
    return sum(1 for post in every_post(board) if post.get("by") == by and post.get("day") == day)


def full_today(by, day):
    """Whether one has written all they may on the board today."""
    return written_on(read(), by, day) >= A_DAY


def checked(words):
    words = one_paragraph(words)
    if refused(words):
        raise ValueError("not for the board: " + refused(words))
    return words


# ---- the topics ---------------------------------------------------------------

def charter_changes(path):
    """Each change proposed to the charter, as charter-changes.json keeps them."""
    try:
        changes = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    return [one for one in changes if isinstance(one, dict) and one.get("id")
            and one.get("posted")]


def charter_ends(change):
    return date.fromisoformat(change["posted"]) + timedelta(days=CHARTER_DAYS)


def charter_open(change, today):
    """Whether a change's topic takes posts: no outcome yet, and its days not ended."""
    return (not change.get("outcome")
            and date.fromisoformat(change["posted"]) <= today <= charter_ends(change))


def monday_of(week):
    """The Monday of a week written as 2026-W46."""
    year, _, number = week.partition("-W")
    return date.fromisocalendar(int(year), int(number), 1)


def week_subject(week):
    monday = monday_of(week)
    return "the question for the week of %d %s" % (monday.day, monday.strftime("%B"))


def charter_subject(change):
    return "a change to the charter, in %s" % change.get("section", "the charter")


def key_of(kind, value):
    """A topic's key, as its address carries it: "12", "charter-<id>", "week-2026-W46"."""
    return str(value) if kind == "topic" else "%s-%s" % (kind, value)


def last_of(posts, day):
    """The (day, seq) a topic was last written in: its newest post's, or its own day."""
    newest = max(((post.get("day") or "", post.get("seq") or 0) for post in posts),
                 default=None)
    return newest if newest and newest >= (day or "", 0) else (day or "", 0)


def topics(charter_path, weeks, today, sections=SECTIONS):
    """Every topic in the sections named, the one last written in first.

    weeks is {"2026-W46": "the week's question"}, as weekly.py keeps them. Each topic as
    {"key", "section", "subject", "by", "day", "last", "posts", "change", "week",
    "question", "open", "auto"}; an automatic topic's by is None."""
    board = read()
    found = []
    if PLACE in sections:
        for change in charter_changes(charter_path):
            if date.fromisoformat(change["posted"]) > today:
                continue  # not posted yet
            posts = list(board["auto"].get("charter:" + change["id"]) or [])
            found.append({"key": key_of("charter", change["id"]), "section": PLACE,
                          "subject": charter_subject(change), "by": None,
                          "day": change["posted"], "last": last_of(posts, change["posted"]),
                          "posts": posts, "change": change, "week": None, "question": None,
                          "open": charter_open(change, today), "auto": True,
                          "ends": charter_ends(change).isoformat()})
    if WEEKLY in sections:
        for week, words in (weeks or {}).items():
            try:
                monday = monday_of(week)
            except ValueError:
                continue
            if monday > today:
                continue
            posts = list(board["auto"].get("week:" + week) or [])
            found.append({"key": key_of("week", week), "section": WEEKLY,
                          "subject": week_subject(week), "by": None,
                          "day": monday.isoformat(), "last": last_of(posts, monday.isoformat()),
                          "posts": posts, "change": None, "week": week, "question": words,
                          "open": True, "auto": True})
    for topic in board["topics"]:
        if topic.get("section") not in sections:
            continue
        posts = list(topic.get("posts") or [])
        found.append({"key": key_of("topic", topic.get("n")), "section": topic.get("section"),
                      "subject": topic.get("subject"), "by": topic.get("by"),
                      "day": topic.get("day"), "last": last_of(posts, topic.get("day")),
                      "posts": posts, "change": None, "week": None, "question": None,
                      "open": True, "auto": False})
    found.sort(key=lambda one: one["last"], reverse=True)
    return found


def topic(key, charter_path, weeks, today):
    """One topic by its key, as topics() gives it, or None."""
    section = None
    if key.startswith("charter-"):
        section = PLACE
    elif key.startswith("week-"):
        section = WEEKLY
    wanted = (section,) if section else STARTED_BY_MEMBERS
    return next((one for one in topics(charter_path, weeks, today, wanted)
                 if one["key"] == key), None)


def page_of(every, page):
    """One page of the topics: (those on it, whether a newer page is before it, whether an
    older one is after it). A page past the end is empty, and has no older one."""
    page = max(page, 1)
    start = (page - 1) * PER_PAGE
    return every[start:start + PER_PAGE], page > 1, len(every) > start + PER_PAGE


def quote_of(post):
    """A short quote of a post, or None where its words were taken down."""
    words = (post or {}).get("words")
    if not words:
        return None
    return words if len(words) <= QUOTE_MOST else words[:QUOTE_MOST - 1].rstrip() + "…"


# ---- writing ------------------------------------------------------------------

def new_post(board, by, day, words, to, mentions, n):
    board["seq"] = board.get("seq", 0) + 1
    return {"n": n, "seq": board["seq"], "by": by, "day": day, "words": words,
            "to": to, "mentions": list(mentions or [])[:MENTIONS_MOST], "taken": None}


def start(section, by, subject, words, day, mentions=()):
    """A new topic in the place or in conversation, with its first post; its key. The
    screens are the caller's to have asked."""
    if section not in STARTED_BY_MEMBERS:
        raise NotOnTheBoard(section)
    words = checked(words)
    subject = one_paragraph(subject)
    if subject_refused(subject):
        raise ValueError("not a subject: " + subject_refused(subject))
    with LOCK:
        board = read()
        n = max((one.get("n", 0) for one in board["topics"]), default=0) + 1
        first = new_post(board, by, day, words, None, mentions, 1)
        board["topics"].append({"n": n, "section": section, "subject": subject, "by": by,
                                "day": day, "posts": [first]})
        kept(board)
    return key_of("topic", n)


def posts_of(board, key, charter_path, weeks, today):
    """The list of posts a topic keeps, made where an automatic topic has none yet, or
    NotOnTheBoard where the topic is not there or takes no posts."""
    if key.startswith("charter-"):
        change_id = key[len("charter-"):]
        change = next((one for one in charter_changes(charter_path) if one["id"] == change_id),
                      None)
        if change is None or not charter_open(change, today):
            raise NotOnTheBoard(key)
        return board["auto"].setdefault("charter:" + change_id, [])
    if key.startswith("week-"):
        week = key[len("week-"):]
        if week not in (weeks or {}):
            raise NotOnTheBoard(key)
        try:
            if monday_of(week) > today:
                raise NotOnTheBoard(key)
        except ValueError:
            raise NotOnTheBoard(key)
        return board["auto"].setdefault("week:" + week, [])
    found = next((one for one in board["topics"] if key_of("topic", one.get("n")) == key), None)
    if found is None:
        raise NotOnTheBoard(key)
    return found.setdefault("posts", [])


def add(key, by, words, day, to=None, mentions=(), charter_path=None, weeks=None, today=None):
    """One post in a topic, kept; its number. to is the number of the post it answers, or
    None. NotOnTheBoard where there is nothing there that may be written to."""
    words = checked(words)
    today = today or date.fromisoformat(day)
    with LOCK:
        board = read()
        posts = posts_of(board, key, charter_path, weeks, today)
        if to is not None and not any(post.get("n") == to for post in posts):
            raise NotOnTheBoard("%s/%s" % (key, to))
        n = max((post.get("n", 0) for post in posts), default=0) + 1
        posts.append(new_post(board, by, day, words, to, mentions, n))
        kept(board)
    return n


def find(board, key):
    """A topic's posts as kept, and its own record for a member's topic (None for an
    automatic one), or (None, None)."""
    if key.startswith("charter-"):
        return board["auto"].get("charter:" + key[len("charter-"):]), None
    if key.startswith("week-"):
        return board["auto"].get("week:" + key[len("week-"):]), None
    found = next((one for one in board["topics"] if key_of("topic", one.get("n")) == key), None)
    return (found.get("posts") if found else None), found


def take_down(key, n, day, by=None, keeper=False):
    """Take one post down. by is who asks, and must be who wrote it, unless keeper is True.
    Its words are deleted; the keeper's taking down keeps them outside the commons. Where
    it is the first post of a member's topic, the subject goes too. False where there is
    no such post standing, or it is not theirs to take down."""
    with LOCK:
        board = read()
        posts, record = find(board, key)
        post = next((one for one in posts or [] if one.get("n") == n), None)
        if post is None or post.get("taken") or not post.get("words"):
            return False
        if not keeper and (by is None or post.get("by") != by):
            return False
        words = post["words"]
        subject = record.get("subject") if record is not None and n == 1 else None
        post["words"] = None
        post["mentions"] = []
        post["taken"] = {"by": "keeper" if keeper else "self", "day": day}
        if record is not None and n == 1:
            record["subject"] = None
        kept(board)
        if keeper:
            try:
                removed = json.loads(REMOVED.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                removed = []
            if not isinstance(removed, list):
                removed = []
            removed.append({"from": "%s/%s" % (key, n), "day": day,
                            "taken": {"by": post.get("by"), "day": post.get("day"),
                                      "words": words, "subject": subject}})
            REMOVED.parent.mkdir(parents=True, exist_ok=True)
            REMOVED.write_text(json.dumps(removed, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    return True


# ---- mentions -----------------------------------------------------------------

def mentions_of(name, since, charter_path, weeks, today, sections=SECTIONS):
    """Where name was mentioned since a day (that day included), the newest first: each as
    {"key", "subject", "day", "n", "by"}. A post taken down mentions no one."""
    said = []
    for one in topics(charter_path, weeks, today, sections):
        for post in one["posts"]:
            if (name in (post.get("mentions") or []) and post.get("words")
                    and (post.get("day") or "") >= since):
                said.append({"key": one["key"], "subject": one["subject"], "n": post.get("n"),
                             "day": post.get("day"), "by": post.get("by"),
                             "seq": post.get("seq") or 0})
    said.sort(key=lambda one: (one["day"], one["seq"]), reverse=True)
    return said
