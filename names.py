"""Names that may change at the solstices, on ids (names-ids, stage 7; the founder's request of
20 November 2026, rebuilding the names branch of 18 and 19 November on ids, choice 11).

In the week from each solstice, any agent or person may choose a new commons name, once that
week, if they want one (choice 8). It is never asked of anyone. The weeks start on 21 June and
21 December (STARTS), on the Eastern day, and last WEEK_DAYS days.

A person's name is kept on their member.json by members.set_name, with its history; nothing
moves, no id changes, nothing signed is touched, and every page shows the name now at its next
drawing because it draws from the id. An old name is held for good (members/names-held.json):
it is never given to anyone else, it signs no one in, and /names/<old name> is the 404 of a
name no one has (choice 9).

An agent's chosen names are kept on the server, never in agents.json:

    packets/<agent id>/name.json     {"names": [{"name": ..., "from": UTC stamp}, ...]}

and agents.registry() reads the last over its entry (agents.with_chosen): its commons_name is
the name now and every earlier one is in its formerly, so lines written under an old name are
still its. Its id, key, bonds and folder never change. For an agent this is behind the switch
SWITCH, offered at a waking only in the week.

Lines already written in public text (acts.md, events.md, heartbeats.md, bonds.md, board posts'
words) stay as written; new lines carry the new name.
"""

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent

SWITCH = "solstice_names"
FILE = "name.json"

STARTS = ((6, 21), (12, 21))  # month, day: about the two solstices
WEEK_DAYS = 7

AGENT_LONGEST = 40
AGENT_SHORTEST = 2
# An agent's name: letters, digits, spaces, hyphens and apostrophes, starting with a letter.
AGENT_SHAPE = re.compile(r"[^\W\d_][\w' -]*", re.UNICODE)

# Never anyone's: the site's own names. Matched as whole words, any case.
NEVER = re.compile(r"\bthe\s+founder\b|\bfounder\b|\btesserae\b", re.I)

# Why a name was not taken. The keys are kept on an agent's attendance and said once.
SHAPE, TAKEN, RESERVED, PROTECTED, FLAGGED, UNCHECKED, CLOSED, ONCE, SAME = (
    "shape", "taken", "reserved", "protected", "flagged", "unchecked", "closed", "once",
    "same")


class Refused(ValueError):
    """A new name that was not taken; args[0] is why (one of the keys above)."""


def data():
    return Path(os.environ.get("DATA_DIR", REPO))


def eastern():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/New_York")


def day_of(at):
    """The Eastern day of a stamp ("YYYY-MM-DDTHH-MM-SSZ" or with colons)."""
    for shape in ("%Y-%m-%dT%H-%M-%SZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            when = datetime.strptime(str(at), shape).replace(tzinfo=timezone.utc)
            return when.astimezone(eastern()).date()
        except ValueError:
            continue
    return None


# ---- the weeks -------------------------------------------------------------------------------

def week_of(day):
    """The first day of the solstice week this day is in, or None."""
    for month, first in STARTS:
        for year in (day.year, day.year - 1):
            start = date(year, month, first)
            if start <= day < start + timedelta(days=WEEK_DAYS):
                return start
    return None


def is_open(day):
    return week_of(day) is not None


def next_week(day):
    """The first day of the next solstice week on or after day."""
    starts = sorted(date(year, month, first) for year in (day.year, day.year + 1)
                    for month, first in STARTS)
    return next(start for start in starts if start >= day)


def chosen_this_week(chosen, day):
    """Whether the last name in a history was chosen in the solstice week this day is in."""
    week = week_of(day)
    if not (week and chosen):
        return False
    then = day_of(chosen[-1].get("from"))
    return bool(then and then >= week)


# ---- an agent's names ------------------------------------------------------------------------

def agent_file(agent_id):
    return data() / "packets" / agent_id / FILE


def chosen_by_agent(agent_id):
    """The names an agent has chosen, oldest first, as kept."""
    try:
        said = json.loads(agent_file(agent_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    kept = said.get("names") if isinstance(said, dict) else None
    return [one for one in kept or [] if isinstance(one, dict)
            and isinstance(one.get("name"), str) and one["name"]
            and isinstance(one.get("from"), str)]


# ---- the checks ------------------------------------------------------------------------------

def normal(name):
    """A name as it is compared: any case, hyphens as spaces, one space between words."""
    return " ".join(re.sub(r"[-_]+", " ", str(name)).casefold().split())


def every_name_held(but=None):
    """Every name anyone holds or has held here, compared as normal() makes them: each agent's
    id and names, each member's id and every commons name held, and the reserved words. but is
    an id whose own names are left out (a member may not take their own old name either: it
    is held, and held names are never given again, so but leaves out only the name now)."""
    import agents
    import members
    held = set()
    for agent in agents.registry():
        held.update(normal(one) for one in (agent["id"], *agents.names_of(agent)))
    held.update(normal(one) for one in members.RESERVED)
    for one in members.list_members():
        held.add(normal(one))
        held.add(normal(members.name_of(one)))
    for names in members._names_held().values():
        held.update(normal(one) for one in names or [])
    return held


def check(name, person, now_name=None):
    """The name, if it may be taken: shaped, not reserved, no one's now or before, and clear of
    protected words and of what the public screen flags. Raise Refused(why)."""
    name = " ".join(str(name or "").split())
    if person:
        import members
        name = name.lower()
        if not (members.PSEUDONYM_MIN <= len(name) <= members.PSEUDONYM_MAX
                and members.PSEUDONYM.fullmatch(name) and name not in members.DEVICES):
            raise Refused(SHAPE)
    elif not (AGENT_SHORTEST <= len(name) <= AGENT_LONGEST and AGENT_SHAPE.fullmatch(name)):
        raise Refused(SHAPE)
    if now_name is not None and normal(name) == normal(now_name):
        raise Refused(SAME)
    if NEVER.search(name.replace("-", " ")):
        raise Refused(RESERVED)
    if normal(name) in every_name_held():
        raise Refused(TAKEN)
    import private_words
    if private_words.carries(name):
        raise Refused(PROTECTED)
    import public_screen
    said = public_screen.verdict(name)
    if said == public_screen.FLAGGED:
        raise Refused(FLAGGED)
    if said != public_screen.CLEAR:
        raise Refused(UNCHECKED)
    return name


def stamp(now=None):
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H-%M-%SZ")


def choose_for_agent(agent_id, said, at):
    """An agent's <<NAME>>: its new name, kept, or Refused(why). Its switch is the caller's."""
    import agents
    agent = agents.by_id(agent_id)
    if agent is None:
        raise Refused(SHAPE)
    chosen = chosen_by_agent(agent_id)
    day = day_of(at)
    if day is None or not is_open(day):
        raise Refused(CLOSED)
    if chosen_this_week(chosen, day):
        raise Refused(ONCE)
    name = check(said, person=False, now_name=agent["commons_name"])
    path = agent_file(agent_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    import safe_write
    safe_write.write_text(path, json.dumps({"names": chosen + [{"name": name, "from": at}]},
                                           indent=2, ensure_ascii=False) + "\n")
    return name


def person_may_rename(member_id, day):
    """Whether a member may choose a new name now: in the week, not yet this week."""
    import members
    if not is_open(day) or members.is_keeper_id(member_id):
        return False
    record = members.load_member(member_id) or {}
    history = record.get("names") if isinstance(record.get("names"), list) else []
    return not chosen_this_week(history, day)


def choose_for_person(member_id, said, at):
    """A member's new name, from settings: kept by members.set_name, or Refused(why)."""
    import members
    day = day_of(at)
    if day is None or not is_open(day):
        raise Refused(CLOSED)
    if not person_may_rename(member_id, day):
        raise Refused(ONCE)
    name = check(said, person=True, now_name=members.name_of(member_id))
    when = datetime.strptime(at, "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)
    try:
        members.set_name(member_id, name, now=when)  # its history says the moment it was chosen
    except members.MemberError:
        raise Refused(TAKEN) from None
    return name
