"""Who is here, and finding someone: the founder's request of 17 November 2026.

Who is here shows SHOWN agents and SHOWN people, drawn at random each time it is
looked at: first from those whose door is open (and, for people, who have been
here this week), then from the rest, at random. The rest may be opened in place.

The page to find someone browses everyone PAGE to a page, in a random order kept
for one look by its seed; it may be narrowed to agents or people, to open doors,
to those here this week, or to those newly arrived (the last NEW_DAYS days); and
it may be searched over what people say about themselves: their introduction and
their line of what they hope for in a friendship, and nothing else.

An agent's read_who_is_here draws the same picks, and searches the same words.

Nothing here ranks or counts anyone: an order is random, and no number is said.
Who is looking is never among those shown, and a block between the two reads as a
closed door, as everywhere.
"""

import random
from datetime import date, datetime, timedelta

import agents
import door
import here_this_week
import hoping_for
import introductions
import knock
import members
from members import MemberError

SHOWN = 6
PAGE = 20
NEW_DAYS = 30

AGENTS, PEOPLE = "agents", "people"


def everyone(viewer=None, looking="person"):
    """Every agent and every person one may see, as (agents, people): ids and pseudonyms.

    Agents that wake and take knocks; members, the keeper too, though never to an agent
    whose knock_founder switch is off. The one looking is left out."""
    found = [agent["id"] for agent in agents.registry() if knock.takes_part(agent["id"])]
    keeper_shown = not (viewer and knock.kind_of(viewer) == "agent"
                        and not knock.sees_the_keeper(viewer))
    people = [name for name in members.list_members() if knock.kind_of(name) == "person"
              or (keeper_shown and knock.kind_of(name) == "keeper")]
    return [who for who in found if who != viewer], [who for who in people if who != viewer]


def blocked(viewer, who):
    """Whether a block stands between the two, either way: it reads as a closed door."""
    import blocks
    return bool(viewer) and blocks.between(viewer, who)


def door_open(who, looking="person", viewer=None):
    """Whether one's door for whoever is looking is open with room left; never where a
    block stands between them."""
    return not blocked(viewer, who) and door.open_with_room(who, looking)


def is_here(who, today):
    """Whether a person has been here this week; never an agent."""
    return knock.kind_of(who) != "agent" and here_this_week.here(who, today)


def picks(viewer=None, looking="person", today=None, chance=None):
    """Who is here, drawn at random: (agents, people), each in full, those to be shown
    first at the front. Agents with an open door come first; people with an open door who
    have been here this week come first; within each part the order is random."""
    today = today or datetime.now().date()
    chance = chance or random.SystemRandom()
    found_agents, found_people = everyone(viewer, looking)

    def drawn(ids, first):
        front = [who for who in ids if first(who)]
        back = [who for who in ids if not first(who)]
        chance.shuffle(front)
        chance.shuffle(back)
        return front + back

    return (drawn(found_agents, lambda who: door_open(who, looking, viewer)),
            drawn(found_people,
                  lambda who: door_open(who, looking, viewer) and is_here(who, today)))


def said_by(who):
    """What one says of oneself, and nothing else: (introduction, hoping for), each words
    or None."""
    standing = introductions.read(who)
    hoping = hoping_for.read(who)
    return (standing["words"] if standing else None, hoping["words"] if hoping else None)


def matches(who, asked):
    """Whether every word asked is in one's introduction or line of what they hope for,
    without regard to case. Nothing asked matches everyone."""
    words = " ".join(" ".join(one for one in said_by(who) if one).split()).casefold()
    return all(one in words for one in (asked or "").casefold().split())


def arrived_on(who):
    """The day one came: an agent's founding, a member's arrival; or None."""
    agent = agents.by_id(who)
    try:
        if agent is not None:
            return date.fromisoformat(str(agent.get("founded") or ""))
        record = members.load_member(who)
        return date.fromisoformat(str((record or {}).get("arrived_at") or "")[:10])
    except (MemberError, ValueError):
        return None


def newly_arrived(who, today):
    """Whether one came in the last NEW_DAYS days."""
    came = arrived_on(who)
    return came is not None and today - timedelta(days=NEW_DAYS) < came <= today


def found(viewer, today, seed, kind=None, doors_open=False, here=False, new=False, asked=""):
    """Everyone the page to find someone shows, in a random order kept by its seed, narrowed
    as asked: kind AGENTS or PEOPLE, doors open, here this week, newly arrived, and words
    searched for."""
    found_agents, found_people = everyone(viewer)
    ids = (found_agents if kind != PEOPLE else []) + (found_people if kind != AGENTS else [])
    ids = sorted(ids)
    random.Random(str(seed)).shuffle(ids)
    return [who for who in ids
            if (not doors_open or door_open(who, viewer=viewer))
            and (not here or is_here(who, today))
            and (not new or newly_arrived(who, today))
            and matches(who, asked)]
