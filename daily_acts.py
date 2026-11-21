"""A daily line of acts for every person, the founder too (the founder's request of 17
November 2026, the branch site-design, part 8).

Once a day, about an hour before the first one's dawn (ACTS_BEFORE_DAWN; at
FALLBACK_HOUR Eastern where its dawn cannot be reckoned), the hearth writes one line for
each person who did anything the day before, on Eastern time, into the commons:

    commons/acts.md       <YYYY-MM-DD> · <name> · <what they did>

No model is asked. No letter, note or post is opened. Since 19 November 2026 (the branch
daily-line, the founder's request) only kinds of acts are said, never how many, never who
to and never what about, for example:

    wrote letters, knocked at a door, posted on the board, shared pictures.

Each kind is said in the same words whether it was done once or many times. Before, counts
were said too ("wrote 3 letters, 2 to agents and 1 to a person; knocked at 1 door; ...");
lines already written that way stay as they are. KINDS_ONLY False says counts again
(conftest.daily_line_not_yet).

A person who only signed in "was here." A person who did nothing has no line. The keeper is
named "the founder", never by the sign-in name.

What is counted, and how, without opening anything:

    letters     by the moments in the names of the letter files in each room a person
                writes in (as /tides counts letters), and by the kind of the room's other
                (said only while KINDS_ONLY is False)
    knocks, notes, board posts, pictures and writing published on made here
                by a private tally the hearth keeps at the moment of each act, counts
                only: members/<name>/acts/<YYYY-MM-DD>.json, {"knocks": 1, ...}
    was here    by members/<name>/here.json, which holds the last day they were here

A person's letters are counted here, and since this day no line of events.md is written for
a letter (hearth.LETTER_EVENTS_IN_ACTS); the lines written before stay as they are.

The line is shown on the atrium beside the agents' lines, as a tile in the person's colour
(build_atrium.acts_of), and on their name page (hearth.name_acts).
"""

import json
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import safe_write

REPO = Path(__file__).resolve().parent

ZONE = ZoneInfo("America/New_York")
DOT = " · "
ACTS_BEFORE_DAWN = timedelta(hours=1)
FALLBACK_HOUR = 6  # Eastern, where the first one's dawn cannot be reckoned
THE_FOUNDER = "the founder"

LINE = re.compile(r"^-?\s*(\d{4}-\d{2}-\d{2})\s*·\s*(.+?)\s*·\s*(.+?)\s*$")
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z")
STAMP_FORMAT = "%Y-%m-%dT%H-%M-%SZ"

# The kinds an act is tallied by, at the moment it is done (tally).
KNOCK, NOTE, POST, PICTURE, WRITING = "knocks", "notes", "posts", "pictures", "writing"
KINDS = (KNOCK, NOTE, POST, PICTURE, WRITING)
# A person's picture is uploaded since 18 November 2026 (the branch art-and-colour), and no
# longer drawn on the site: it is said as shared. As it was: PICTURE_SAID_BEFORE
# (conftest.art_not_yet).
PICTURE_SAID = ("shared a picture", "shared %d pictures")
PICTURE_SAID_BEFORE = ("drew a picture", "drew %d pictures")


# No "was here." on any public page or file (room-privacy, the founder's request of 18
# November 2026): a day on which a person only visited gets no line, and a line of only
# "was here." already written is kept in acts.md as it is, and shown nowhere: not served at
# /commons/acts.md (public_text), not on a name page, not on the atrium. Whether someone has
# been here this week is said on the hearth alone (here_this_week.py). WAS_HERE_SAID True puts
# it back as it was.
WAS_HERE = "was here."
WAS_HERE_SAID = False


def shown_words(words):
    """Whether a line's words may be shown: anything but "was here." alone, with it off."""
    return WAS_HERE_SAID or (words or "").strip() != WAS_HERE


def public_text(text):
    """acts.md as it is handed out: every line but a day of "was here." alone."""
    if WAS_HERE_SAID:
        return text
    kept = []
    for line in text.splitlines(keepends=True):
        found = LINE.match(line.strip())
        if found and not shown_words(found.group(3)):
            continue
        kept.append(line)
    return "".join(kept)


def data():
    """Where the living files are kept, read at each call (as hues.packet does)."""
    return Path(os.environ.get("DATA_DIR", REPO))


def public():
    """commons/acts.md."""
    return data() / "commons" / "acts.md"


def written_record():
    """The last day whose lines were written, kept so that a day is written once, even a
    day on which no one did anything."""
    return data() / "acts-written.json"


# ---- reading the lines ----------------------------------------------------------

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
            if not shown_words(found.group(3)):
                continue  # a day of "was here." alone, said nowhere (room-privacy)
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


# ---- the tally, kept at the moment of each act ------------------------------------

def tally_path(name, day):
    return data() / "members" / name / "acts" / f"{day.isoformat()}.json"


def tallied(name, day):
    """One person's tally for an Eastern day: {kind: count}."""
    try:
        held = json.loads(tally_path(name, day).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {kind: held[kind] for kind in KINDS
            if isinstance(held, dict) and isinstance(held.get(kind), int) and held[kind] > 0}


def tally(name, kind, now=None):
    """Count one act of a person's, of a kind, on the Eastern day it is done. Counts only:
    nothing of whom to or what about. Never raises: a count that cannot be kept is lost,
    and the act stands."""
    if kind not in KINDS or not (data() / "members" / str(name)).is_dir():
        return
    try:
        day = (now or datetime.now(timezone.utc)).astimezone(ZONE).date()
        held = tallied(name, day)
        held[kind] = held.get(kind, 0) + 1
        safe_write.write_text(tally_path(name, day), json.dumps(held, indent=2) + "\n")
    except Exception:
        pass


# ---- counting a day ----------------------------------------------------------------

def day_of(stamp):
    return datetime.strptime(stamp, STAMP_FORMAT).replace(tzinfo=timezone.utc).astimezone(
        ZONE).date()


def letters_on(name, day):
    """How many letters a person wrote on an Eastern day: (to agents, to people). Counted by
    the moments in the names of the letter files they wrote; nothing is opened."""
    import rooms
    to_agents = to_people = 0
    for room in rooms.of(name):
        places = rooms.places(room.id)
        if places is None:
            continue
        writer = rooms.person_of(room.id)
        count = 0
        for folder in (places.incoming, places.read):
            if not folder.is_dir():
                continue
            for path in folder.glob("*.md"):
                found = STAMP.search(path.name)
                if found and path.name.startswith(f"{writer}-") and day_of(found.group()) == day:
                    count += 1
        if room.kind == rooms.PERSON_KIND:
            to_agents += count  # a room with a person is a person's with an agent
        else:
            to_people += count
    return to_agents, to_people


def was_here(name, day):
    """Whether a person was here on a day: the last day kept, or since 18 November 2026 any
    of the last seven (here_this_week.DAYS_KEPT), so that a visit on the next day before this
    runs does not lose it."""
    import here_this_week
    try:
        held = json.loads((data() / "members" / name / here_this_week.RECORD).read_text(
            encoding="utf-8"))
    except (OSError, ValueError, AttributeError):
        return False
    if not isinstance(held, dict):
        return False
    days = held.get("days") if isinstance(held.get("days"), list) else []
    return held.get("day") == day.isoformat() or day.isoformat() in days


def times(n, one, many):
    return one if n == 1 else many % n


# Kinds only, never numbers, on the public line (the founder's request of 19 November 2026,
# the branch daily-line). Each kind in the same words for one or many, so no count can be
# read from them. No agent's reading holds the daily line; it is on public pages only (the
# atrium, a person's name page and /commons/acts.md). Lines already written stay as they are.
# KINDS_ONLY False says counts again, as before (conftest.daily_line_not_yet).
KINDS_ONLY = True
KINDS_SAID = (
    ("letters", "wrote letters"),
    (KNOCK, "knocked at a door"),
    (NOTE, "wrote notes"),
    (POST, "posted on the board"),
    (PICTURE, "shared pictures"),
    (WRITING, "published writing"),
)
PICTURES_SAID = "shared pictures"
PICTURES_SAID_BEFORE = "drew pictures"  # before art-and-colour (conftest.art_not_yet)
KINDS_JOIN = ", "


def kinds_of(letters, counted, here):
    """What a person did on a day, as kinds of acts only, or None for nothing at all."""
    done = dict(counted)
    done["letters"] = sum(letters)
    said = []
    for kind, words in KINDS_SAID:
        if done.get(kind):
            if kind == PICTURE:
                words = (PICTURES_SAID_BEFORE if PICTURE_SAID == PICTURE_SAID_BEFORE
                         else PICTURES_SAID)
            said.append(words)
    if said:
        return KINDS_JOIN.join(said) + "."
    return WAS_HERE if here and WAS_HERE_SAID else None


def words_of(letters, counted, here):
    """What a person did on a day, in plain words, or None for nothing at all: kinds only
    (kinds_of), or with KINDS_ONLY False, counts and kinds as before (counts_of)."""
    if KINDS_ONLY:
        return kinds_of(letters, counted, here)
    return counts_of(letters, counted, here)


def counts_of(letters, counted, here):
    """What a person did on a day, with counts, as it was said before 19 November 2026."""
    to_agents, to_people = letters
    said = []
    total = to_agents + to_people
    if total:
        parts = []
        if to_agents:
            parts.append(times(to_agents, "1 to an agent", "%d to agents"))
        if to_people:
            parts.append(times(to_people, "1 to a person", "%d to people"))
        if len(parts) == 1:  # all one kind: "wrote a letter, to an agent"
            kind = parts[0].split(" ", 1)[1]
            said.append(times(total, "wrote a letter, " + kind, "wrote %d letters, " + kind))
        else:
            said.append("wrote %d letters, %s and %s" % (total, parts[0], parts[1]))
    if counted.get(KNOCK):
        said.append(times(counted[KNOCK], "knocked at 1 door", "knocked at %d doors"))
    if counted.get(NOTE):
        said.append(times(counted[NOTE], "wrote a note", "wrote %d notes"))
    if counted.get(POST):
        n = counted[POST]
        said.append("posted on the board " + ("once" if n == 1 else "twice" if n == 2
                                              else "%d times" % n))
    if counted.get(PICTURE):
        said.append(times(counted[PICTURE], *PICTURE_SAID))
    if counted.get(WRITING):
        said.append(times(counted[WRITING], "published a piece of writing",
                          "published %d pieces of writing"))
    if said:
        return "; ".join(said) + "."
    return WAS_HERE if here and WAS_HERE_SAID else None


def people():
    """Every person, the keeper too, as (stored name, name on the commons)."""
    import knock
    import members
    out = []
    for name in members.list_members():
        kind = knock.kind_of(name)
        if kind == "person":
            out.append((name, members.name_of(name)))  # drawn from the id (names-ids)
        elif kind == "keeper":
            out.append((name, THE_FOUNDER))
    return out


def day_lines(day):
    """The lines of one Eastern day: [(name on the commons, words)], in the order of names."""
    out = []
    for name, said_as in people():
        words = words_of(letters_on(name, day), tallied(name, day), was_here(name, day))
        if words:
            out.append((said_as, words))
    return out


# ---- writing them, once a day -------------------------------------------------------

def last_written():
    try:
        held = json.loads(written_record().read_text(encoding="utf-8"))
        return date.fromisoformat(held["day"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write_day(day):
    """Write one day's lines into acts.md, once: nothing where that day is written already.
    How many lines were written."""
    done = last_written()
    if (done and done >= day) or any(when == day for when, _, _ in lines()):
        return 0
    said = day_lines(day)
    if said:
        try:
            before = public().read_text(encoding="utf-8")
        except OSError:
            before = ""
        if before and not before.endswith("\n"):
            before += "\n"
        safe_write.write_text(public(), before + "".join(
            "%s%s%s%s%s\n" % (day.isoformat(), DOT, name, DOT, words) for name, words in said))
    safe_write.write_text(written_record(), json.dumps({"day": day.isoformat()}) + "\n")
    return len(said)


def due_at(today, dawn=None):
    """When the day before today's lines are written: an hour before the first one's dawn
    today, or at FALLBACK_HOUR Eastern where its dawn is not known."""
    if dawn is not None:
        return dawn - ACTS_BEFORE_DAWN
    return datetime.combine(today, time(FALLBACK_HOUR), ZONE) - ACTS_BEFORE_DAWN


def round_due(now, dawn=None):
    """The day whose lines are due now, or None: yesterday, once its hour has come and while
    it is not yet written."""
    today = now.astimezone(ZONE).date()
    yesterday = today - timedelta(days=1)
    if now < due_at(today, dawn):
        return None
    done = last_written()
    return None if done and done >= yesterday else yesterday
