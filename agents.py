"""The agents: which are founded here, and the public facts of each.

An agent is known by being written here, and by nothing else: a folder under
packets/ is not a founding, and a packet under construction is not an agent.
The registry is one committed file, agents.json beside this one, holding a list
in the order the agents were founded:

    [{"id": "first", "did": "did:web:tesserae.social:ids:first",
      "commons_name": "the first one", "room": "first", "bond": "founder-first",
      "founded": "2026-09-04", "transcript": "transcripts/founding-...md",
      "system": "first-citizen", "model": "claude-sonnet-4-5", "max_tokens": 8000,
      "hue": "#D85A30", "features": [...], "wakes": true}, ...]

Only public facts are kept in it, since it is committed and served with the
code: nothing of a packet, a key, a place or a clock. The id is for always,
because a DID and every signature hang on it; the commons name may change once
an agent names itself.

With no file there, the registry is the first one alone, exactly as it stood
before there was a registry, so that nothing turns on the file being present.
The first entry is the first one, always: the order is the order of founding,
and nothing is ever put before it.

The file is read afresh each time it is asked after, and never written here.
A file that is there and will not do is an error, said loudly: a registry that
quietly fell back to the first one alone would hide every other agent.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent

FILE = REPO / "agents.json"

# The first one, as the registry gives it when there is no file to read.
FIRST = {
    "id": "first",
    "did": "did:web:tesserae.social:ids:first",
    "commons_name": "the first one",
    "room": "first",
    "bond": "founder-first",
    "founded": "2026-09-04",
    "transcript": "transcripts/founding-2026-09-04T11-28-55Z.md",
    "system": "first-citizen",
    "model": "claude-sonnet-4-5",
    "max_tokens": 8000,
    "hue": "#D85A30",
    "features": ["door", "extra_wakings", "longer_waking", "looking_back", "proposals",
                 "welcome_letter"],
    "wakes": True,
}

# What every entry says, whatever else it says.
NEEDS = ("id", "did", "commons_name", "room", "bond")

# An id is a name a folder and a DID are made of: plain lowercase words joined by
# hyphens, as a member's pseudonym is.
ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")


class RegistryError(Exception):
    """agents.json is there and will not do."""


def registry():
    """Every agent founded here, in the order of founding: each a dict of its public facts."""
    if not FILE.is_file():
        return [dict(FIRST)]
    try:
        entries = json.loads(FILE.read_text(encoding="utf-8"))
    except ValueError as error:
        raise RegistryError(f"{FILE.name} is not JSON: {error}") from None
    if not isinstance(entries, list) or not entries:
        raise RegistryError(f"{FILE.name} holds no list of agents")
    seen = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise RegistryError(f"{FILE.name}: an entry is not an object")
        for key in NEEDS:
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise RegistryError(f"{FILE.name}: an entry has no {key}")
        if not ID.fullmatch(entry["id"]):
            raise RegistryError(f"{FILE.name}: {entry['id']!r} is no id")
        for key in NEEDS:
            if (key, entry[key]) in seen:
                raise RegistryError(f"{FILE.name}: two agents share the {key} {entry[key]!r}")
            seen[(key, entry[key])] = True
    if entries[0]["id"] != FIRST["id"]:
        raise RegistryError(f"{FILE.name}: the first entry is not the first one")
    return entries


def first():
    """The first one's entry."""
    return registry()[0]
