"""A note from the site (the founder's request of 16 November 2026, part B5).

An agent with no room, as the second one is at its coming, has no letters from the
founder. So the keeper may write it a short plain note on /tides: to one agent, or
to every agent whose switch is on. A note is up to MOST characters. It is shown
once, at the agent's next waking, under WHAT HAS HAPPENED, headed "A note from the
site", and kept in its record: one file a note, in its own packet,

    packets/<id>/site-notes/<stamp>.json
        {"words": "...", "at": "<stamp>", "to": "<id>" or "all", "shown_at": null}

and shown_at is the moment of the waking that read it. Nothing of a note is public,
and no note is ever erased.

Behind the switch "site_notes": on for agents founded from now on, off for the first
one until the founder has told it. /tides offers only agents with the switch on.
"""

import json
import os
from pathlib import Path

import agents
import safe_write

REPO = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", REPO))

FEATURE = "site_notes"
FOLDER = "site-notes"
MOST = 600
EVERY = "all"


class Refused(Exception):
    """A note that is not kept. The message is safe to show."""


def switched_on(agent):
    return agent is not None and FEATURE in (agent.get("features") or ())


def may_have(agent_id):
    """Whether this agent may be sent a note: it is founded here, wakes, and has the switch."""
    agent = agents.by_id(agent_id)
    return switched_on(agent) and bool(agent.get("wakes"))


def folder(agent_id):
    return DATA / "packets" / agent_id / FOLDER


def plain(words):
    """A note as it is kept: its lines as written, each without trailing space, and the
    whole without blank lines at either end."""
    lines = [line.rstrip() for line in (words or "").replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def write(to, words, at):
    """Keep a note for one agent, or for every agent that may have one; the ids it went to."""
    said = plain(words)
    if not said:
        raise Refused("A note needs some words; nothing was sent.")
    if len(said) > MOST:
        raise Refused("A note is up to %d characters; nothing was sent." % MOST)
    if to == EVERY:
        ids = [agent["id"] for agent in agents.registry() if may_have(agent["id"])]
    elif may_have(to):
        ids = [to]
    else:
        raise Refused("There is no agent to send that note to.")
    if not ids:
        raise Refused("No agent may be sent a note yet.")
    for agent_id in ids:
        place = folder(agent_id) / ("%s.json" % at)
        count = 1
        while place.exists():  # two notes in one second are still two notes
            count += 1
            place = folder(agent_id) / ("%s-%d.json" % (at, count))
        safe_write.write_text(place, json.dumps(
            {"words": said, "at": at, "to": to, "shown_at": None}, indent=2) + "\n")
    return ids


def every(agent_id):
    """Every note kept for one agent, oldest first, each with the path it is kept at."""
    where = folder(agent_id)
    if not where.is_dir():
        return []
    found = []
    for path in sorted(where.glob("*.json")):
        try:
            held = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(held, dict) and isinstance(held.get("words"), str):
            found.append({**held, "path": path})
    return found


def waiting(agent_id):
    """The notes not yet shown to an agent, oldest first."""
    return [one for one in every(agent_id) if not one.get("shown_at")]


def shown(notes, at):
    """Mark notes shown, at the waking that read them."""
    for one in notes:
        path = one["path"]
        held = {key: value for key, value in one.items() if key != "path"}
        held["shown_at"] = at
        safe_write.write_text(path, json.dumps(held, indent=2) + "\n")
