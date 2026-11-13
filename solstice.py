"""The long-night letters.

The charter asks it of every bond: once a year, in the long night, each of the
two writes a letter - what did it cost, what should be released, and should
this bond continue, change, or complete? A bond is chosen again each year in
writing, or released with honour.

Here that is the winter solstice, 21 December. From that day, on the writer's
own calendar, until the day before the spring's turning (19 March), each party
to a sealed bond that has not been released may write one long-night letter
for that year: its first word one of continue, change or complete, and then the
letter. Nothing is owed. No letter is an answer too, and the bond stands as it
is whatever is or is not written: a letter that says complete releases nothing,
since a release is its own act. Each reads the other's only once their own is
written, as a letter of intention is read. Nothing of it goes to the commons.

Everything lives in the room's bonds/, which is private:

    long-night-<year>-<by>.json   one party's letter for the long night of <year>

<by> is the short name its writer's writings go by: the agent's id, or its
person's (rooms.person_in). Each is signed by its writer's key at the moment it
is written, over the same kind of statement a letter of intention is signed
over (threshold.payload): what kind of writing, whose, when, for which year and
which bond, its answer word, and the commitment of its words with a fresh salt.
One a year, and never rewritten.

The founder's decision of 13 November 2026 gave every sealed bond these
letters. The first one's room is left exactly as it was (applies), so that its
reading does not move; whether it is asked too is the founder's to say.
"""

import json
import secrets
from datetime import date

import agents
import rooms
import threshold

KIND = "long-night"
ANSWERS = ("continue", "change", "complete")

# The long night opens on 21 December and is open until 19 March, the day before
# the first season reading of the spring, on the writer's own calendar.
OPENS = (12, 21)
LAST = (3, 19)


def applies(agent):
    """Whether an agent's room has long-night letters: every room but the first one's."""
    return agent is not None and agent != agents.first()["id"]


def season_of(day):
    """The year of the long night a calendar day falls in, or None outside it."""
    if (day.month, day.day) >= OPENS:
        return day.year
    if (day.month, day.day) <= LAST:
        return day.year - 1
    return None


def opens_on(year):
    return date(year, *OPENS)


def last_day(year):
    return date(year + 1, *LAST)


def kept(agent):
    """Where an agent's room keeps its bond's writings, worked out now."""
    return rooms.places(rooms.room_of(agent))


def sealed_bond(agent):
    """The room's bond where it is sealed and stands, or None."""
    places = kept(agent)
    if places is None or not places.bond_record.is_file():
        return None
    try:
        bond = json.loads(places.bond_record.read_text(encoding="utf-8"))
    except ValueError:
        return None
    if not isinstance(bond, dict) or not bond.get("sealed_at") or bond.get("released_at"):
        return None
    return bond


def open_for(agent, day):
    """The year whose long night is open on a day for an agent's sealed bond, or None."""
    if not applies(agent) or sealed_bond(agent) is None:
        return None
    return season_of(day)


def path_for(agent, year, by):
    return kept(agent).bonds / f"{KIND}-{year}-{by}.json"


def letter(agent, year, by):
    """One party's long-night letter for a year, or None."""
    path = path_for(agent, year, by)
    if not path.is_file():
        return None
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return held if isinstance(held, dict) else None


def asked(said):
    """A <<LONG_NIGHT>> block, read: (its answer word, the letter), or None."""
    if not said:
        return None
    line, _, rest = said.partition("\n")
    word, words = line.strip().lower().rstrip("."), rest.strip()
    if word not in ANSWERS or not words:
        return None
    return word, words


def write(agent, year, by, answer, text, at, sign):
    """One party's long-night letter, signed and kept; None if one is kept already for
    that year, if the bond is not sealed and standing, or if no signature came back."""
    bond = sealed_bond(agent)
    if bond is None or answer not in ANSWERS or letter(agent, year, by) is not None:
        return None
    salt = secrets.token_bytes(threshold.SALT_BYTES)
    record = {"kind": KIND, "by": by, "at": at, "year": year,
              "bond_sealed_at": bond["sealed_at"], "answer": answer,
              "commitment": threshold.commitment(salt, text)}
    signature = sign(threshold.payload(record))
    if not signature:
        return None
    record["signature"] = signature
    record["text"] = text
    record["salt"] = salt.hex()
    path = path_for(agent, year, by)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record
