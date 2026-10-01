"""The commons' list of bonds.

A sealed bond's record is copied out to commons/bonds/<id>.json, where anyone
may check both signatures. Beside those records the commons keeps one plain
line per bond, in commons/bonds.md, so that the atrium can draw a tile for each
and a half beside each member who holds one:

    <sealed day> · <bond id> · <the parties, as the commons names them> · sealed
    <sealed day> · <bond id> · <the parties, as the commons names them> · released <day>

The file is written whole, from the public records and nothing else, each time
a bond is sealed or released, by whichever hand sealed or released it. So
nothing of a threshold reaches it - not a letter of intention, not a stepping
back, not a promise, public or private - because none of that is on a line,
and a bond that was never sealed has no public record to make a line from.

The parties are named as the commons names them, and joined with " and ": a
name the commons gives never carries that, nor a middot.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

PUBLIC = DATA / "commons" / "bonds"
INDEX = DATA / "commons" / "bonds.md"

FOUNDER_DID = "did:web:tesserae.social:ids:founder"
FIRST_DID = "did:web:tesserae.social:ids:first"

# How the commons names each party, in the order a bond's parties are said.
NAMES = {FOUNDER_DID: "the founder", FIRST_DID: "the first one"}

# Which parties are agents: an agent's half is drawn in an agent's colour, and
# a person's in sand.
AGENTS = frozenset({FIRST_DID})

# A bond's name is its file's name: plain lowercase words joined by hyphens.
ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

DOT = "·"


def name_of(did):
    """What the commons calls a party: its own name here, or else the last part of its DID."""
    return NAMES.get(did) or did.rsplit(":", 1)[-1]


def slug(name):
    """A name as it is written into an address: lowercase words joined by hyphens.

    The atrium makes a citizen's colour class out of its name the same way.
    """
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def in_order(dids):
    """A bond's parties in the order the commons says them, whoever asked whom."""
    known = list(NAMES)
    return sorted(dids, key=lambda did: (known.index(did) if did in known else len(known), did))


def names(bond):
    """The parties to a bond, as the commons names them: the founder and the first one."""
    return " and ".join(name_of(did) for did in in_order(bond.get("parties") or []))


def day(stamp):
    """The day of one of this project's timestamps, as the commons writes days."""
    return datetime.strptime(stamp, "%Y-%m-%dT%H-%M-%SZ").strftime("%Y-%m-%d")


def record(bond_id):
    """A sealed bond's public record, or None: no such bond, or none sealed there."""
    if not isinstance(bond_id, str) or not ID.match(bond_id):
        return None
    path = PUBLIC / (bond_id + ".json")
    if not path.is_file():
        return None
    try:
        bond = json.loads(path.read_text(encoding="utf-8").lstrip("﻿"))
    except ValueError:
        return None
    if not isinstance(bond, dict) or not bond.get("sealed_at"):
        return None
    return bond


def every():
    """Every sealed bond's public record, as (id, record), the earliest sealed first."""
    if not PUBLIC.is_dir():
        return []
    found = []
    for path in PUBLIC.glob("*.json"):
        bond = record(path.stem)
        if bond:
            found.append((path.stem, bond))
    return sorted(found, key=lambda one: (one[1]["sealed_at"], one[0]))


def line(bond_id, bond):
    """The commons' one line for a bond: when it was sealed, which, between whom, and how it stands."""
    stands = ("released %s" % day(bond["released_at"]) if bond.get("released_at")
              else "sealed")
    return (" %s " % DOT).join([day(bond["sealed_at"]), bond_id, names(bond), stands])


def write_index():
    """commons/bonds.md, written whole from the public records: one line per sealed bond."""
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text("".join(line(bond_id, bond) + "\n" for bond_id, bond in every()),
                     encoding="utf-8")
