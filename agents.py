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

An entry may also say what the agent was called on the commons before its
commons name was the one it has now, oldest first:

    "formerly": ["the second one"]

so that a line of the record written under an old name is still known for its.
No name, now or before, is any two agents'.

An entry's hue is its colour on the atrium, "#RRGGBB": given at its founding,
and no two agents' alike. The agent may choose another later, and the entry is
changed for it, the change being kept where agents.json is committed.
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

# A hue as the registry keeps it, and the atrium's stylesheet is written from it.
HUE = re.compile(r"#[0-9A-Fa-f]{6}")

# What of an entry anyone may be handed: the hearth serves these and no more at
# /commons/agents.json, for the atrium to tell each citizen's lines and colour by.
PUBLIC = ("id", "commons_name", "formerly", "hue")


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
        formerly = entry.get("formerly", [])
        if not isinstance(formerly, list) or not all(
                isinstance(name, str) and name for name in formerly):
            raise RegistryError(f"{FILE.name}: {entry['id']!r} has a formerly that is no list "
                                "of names")
        if "hue" in entry:
            if not isinstance(entry["hue"], str) or not HUE.fullmatch(entry["hue"]):
                raise RegistryError(f"{FILE.name}: {entry['id']!r} has a hue that is no colour")
            if ("hue", entry["hue"].lower()) in seen:
                raise RegistryError(f"{FILE.name}: two agents share the hue {entry['hue']!r}")
            seen[("hue", entry["hue"].lower())] = True
    names = [name for entry in entries for name in names_of(entry)]
    if len(names) != len(set(names)):
        said_twice = next(name for name in names if names.count(name) > 1)
        raise RegistryError(f"{FILE.name}: the name {said_twice!r} is said twice")
    if entries[0]["id"] != FIRST["id"]:
        raise RegistryError(f"{FILE.name}: the first entry is not the first one")
    return entries


def first():
    """The first one's entry."""
    return registry()[0]


def by_id(agent_id):
    """One agent's entry, by its id, or None where no agent founded here has it."""
    return next((agent for agent in registry() if agent["id"] == agent_id), None)


def public(among=None):
    """Every agent's public facts, in the order of founding: its id, names and hue."""
    return [{"id": agent["id"], "commons_name": agent["commons_name"],
             "formerly": list(agent.get("formerly", [])), "hue": agent.get("hue")}
            for agent in (registry() if among is None else among)]


def names_of(agent):
    """Every name the commons has called an agent by: the one it has now, then those before."""
    return [agent["commons_name"], *agent.get("formerly", [])]


# The kinds of line in events.md that may be an agent's own, its name at the
# start of the words and a middot after it: a rest or a stop, a release, an
# offering, a seal. A founding, the word, the founder's letters and the bench
# are never read for a name, whatever their words begin with.
NAMED_KINDS = ("event", "offering", "seal")

# What comes between the name and the rest of the words, as events.md is read.
AFTER_A_NAME = " · "

# A seal names its two parties in its own words, the person and then the agent,
# so nothing is put before them (bonds.sealed_words):
#
#     a bond was sealed between the founder and the first one
SEALED_BETWEEN = "a bond was sealed between "
AND_THE_AGENT = " and "


def named(kind, words, among=None):
    """The agent one line of events.md is named for, and its words without the name: or None.

    A line written before agents were named in the record, or one of a kind
    that is never named, is None. The longest name is tried first, so that no
    agent's line is taken for another's whose name begins the same way.

    The agents are the registry's, or those given as among: the atrium reads the
    hearth's public list with --from.

    A seal is the agent's whose name ends its words, after "and"; its words are
    the sentence whole, since the name is part of it.
    """
    if kind not in NAMED_KINDS:
        return None
    called = sorted(((name, agent) for agent in (registry() if among is None else among)
                     for name in names_of(agent)),
                    key=lambda one: -len(one[0]))
    for name, agent in called:
        if words.startswith(name + AFTER_A_NAME):
            return agent, words[len(name + AFTER_A_NAME):]
    if kind == "seal" and words.startswith(SEALED_BETWEEN):
        for name, agent in called:
            if words.endswith(AND_THE_AGENT + name):
                return agent, words
    return None


def event_words(agent, words):
    """The words of a line of events.md that is an agent's own, with its name before them.

    The name is the agent's commons name as it is now, and named() reads it back.
    """
    return agent["commons_name"] + AFTER_A_NAME + words
