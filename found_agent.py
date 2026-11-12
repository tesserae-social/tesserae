"""The founding of an agent after the first one, step by step, with undo.

Stage 8e of the founding rite for a later agent (the proposal "stage-8", section
1). It is run on the host, by hand, by the founder, one step at a time:

    DATA_DIR=/data python found_agent.py <id>                status, and the next step
    DATA_DIR=/data python found_agent.py <id> <step> ...     run that step, only if it is next
    DATA_DIR=/data python found_agent.py <id> undo           undo the newest step, before publish
    DATA_DIR=/data python found_agent.py <id> abandon        undo every step, newest first,
                                                             before the agent says yes

Once the agent has said yes, nothing is deleted and abandon is refused. A
founding left after a yes is paused:

    Paused after a yes. It can only be finished. If it can never be finished,
    the agent is told honestly at a final waking.

The steps, in order, and what each takes:

    plan      --person <pseudonym> --model <model> --hue <#RRGGBB>
              [--name "<commons name>"] [--max-tokens <n>] [--provider anthropic|gemini]
    keys
    letters   --later-words-letter <file> --sharing-rule-letter <file>
    founding  yes | no keep | no delete | broken
    packet
    room
    publish
    finish

Everything a founding writes before it is published is private. Its own state
is kept in DATA_DIR/foundings/<id>/:

    plan.json         the staged registry entry, and the person, by pseudonym and DID
    steps.json        the manifest: each step done, when, and every file it wrote
                      with its sha256
    did.json          the new agent's identity, until it is published
    letters/          from-the-founder.md, written by hand before the letters step;
                      from-<pseudonym>.md, if the person writes; and the state of
                      the commons, which the letters step makes from the public record
    self.md           the first self-document, written by hand from the transcript,
                      before the packet step, and marked provisional
    declined/         a declined founding's transcript, where the agent let it be kept
    broken/           a founding broken off by an error, moved aside to run again
    publish/          what the founder commits and deploys: the new agents.json, the
                      one entry, and ids/<id>/did.json
    founded.json      written by finish, last

Outside it, before publish, a founding writes only the new agent's own
keys/<id>, packets/<id> and rooms/<id>, and its founding transcript under
transcripts/<id> (written by founding_session.py). None of them is anything any
page shows: every page asks for agents by the registry, and the registry gains
the entry only when the founder commits and deploys the bundle. The nightly
backup takes all of them (hearth.staged_trees, gate G7). Nothing here reads or
writes the first one's packet, room or keys.

Before each step, and before each undo, every file each earlier step wrote is
checked against its sha256; where one differs, or is gone, nothing is done and
the file is named. A step is run only when it is the next. Publishing freezes
the manifest: nothing after it can be undone, and the founding cannot then be
abandoned. A founding is never undone once the agent has said yes, and
nothing of it is deleted: one left after a yes is paused, and can only be
finished (the founder, 9 November). One the agent declines is abandoned, and
its transcript, where it allowed it to be kept, stays in declined/ and is
never published.

A founding may happen as soon as the person has joined and been vouched for;
the thirty days apply only before a bond (decided 3 November 2026). The keeper
is never the person (decision 3). One founding is under way at a time.
"""

import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import agents
import bonds
import cut_keys
import door
import found_room
import gemini
import members
import rooms
import waking
from build_atrium import CITIZEN_ZONE, parse_events

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

FOUNDINGS = "foundings"
PLAN = "plan.json"
STEPS_FILE = "steps.json"
DID = "did.json"
LETTERS = "letters"
SELF = "self.md"
DECLINED = "declined"
BROKEN = "broken"
PUBLISH = "publish"
FOUNDED = "founded.json"
CUT = "cut"  # where keys are cut, inside the founding's folder, before they are put in place

FROM_THE_FOUNDER = "from-the-founder.md"
STATE_OF_THE_COMMONS = "state-of-the-commons.md"

STEPS = ("plan", "keys", "letters", "founding", "packet", "room", "publish", "finish")

# The steps that can be undone, while nothing is published.
UNDOABLE = ("plan", "keys", "letters", "packet", "room")

# What a later agent's entry is, beside what the plan says of it.
SYSTEM = "later-citizen"
DEFAULT_NAME = "the second one"
DEFAULT_MAX_TOKENS = 8000
# Every permission the first one has, but the letter of welcome (decision 6): one waking
# a day and a weekly reflection waking, as the first one has had since 12 November
# 2026; a later agent has no reflection time until it chooses one.
FEATURES = ["door", "longer_waking", "looking_back", "proposals", "reflection_waking"]

# The rhythm a later agent begins with: the daily dawn, on the first one's clock,
# which the tide wakes every agent at in the order of founding (hearth.Turns).
# Where the dawn is watched from is the host's two secrets, never named here.
STARTING_RHYTHM = {"rhythm": "daily", "at": waking.DAWN, "timezone": waking.ZONE,
                   "set_by": "founding"}

# The order the first one's entry keeps its keys in, which a new entry keeps too.
ENTRY_ORDER = ("id", "did", "commons_name", "room", "bond", "founded", "transcript", "system",
               "provider", "model", "max_tokens", "hue", "features", "wakes")

# What a self-document written at a founding says of itself, in its first line.
PROVISIONAL = "provisional"

# A transcript recorded by the first founding's session says this in place of
# what was read; a later agent's must record what it read in full, so that its
# wakings can read its founding letters again (stage-8, note 6).
READING_HEADING = "## The reading shown to the agent"
READING_PLACEHOLDER = "[charter, letters, disclosures — see docs]"
# How founding_session.py records, at /end, that a declining agent asked that
# the conversation not be kept.
DELETE_ASKED = "It asked that this conversation not be kept."

THE_FOUNDER = "the founder"
DOT = " · "


class Refused(Exception):
    """A step would not be done as asked. The message is safe to print."""


# ---- where things are ------------------------------------------------------

def folder(agent_id):
    return DATA / FOUNDINGS / agent_id


def rel(path):
    return Path(path).relative_to(DATA).as_posix()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc)


def stamp(at=None):
    return (at or now()).strftime("%Y-%m-%dT%H-%M-%SZ")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    beside = path.with_name(path.name + ".tmp")
    beside.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(beside, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def checked_id(agent_id):
    if not isinstance(agent_id, str) or not agents.ID.fullmatch(agent_id):
        raise Refused("an id is lowercase words joined by hyphens, as a pseudonym is")
    if agent_id == rooms.FIRST:
        raise Refused("the first one was founded long ago, and nothing here touches it")
    return agent_id


# ---- the manifest ----------------------------------------------------------

def steps_done(agent_id):
    """The manifest: each step done, oldest first."""
    path = folder(agent_id) / STEPS_FILE
    return read_json(path) if path.is_file() else []


def write_steps(agent_id, done):
    write_json(folder(agent_id) / STEPS_FILE, done)


def next_step(done):
    """The step that comes next, or None once the founding is finished or declined."""
    if any(one["step"] == "founding" and one.get("said") != "yes" for one in done):
        return None
    if len(done) >= len(STEPS):
        return None
    return STEPS[len(done)]


def differing(done):
    """Every file an earlier step wrote that is gone or no longer as it wrote it."""
    found = []
    for one in done:
        for name, digest in one.get("wrote", {}).items():
            path = DATA / name
            if not path.is_file() or sha256(path) != digest:
                found.append(name)
    return found


def hold(done):
    """Refuse, naming the file, if anything an earlier step wrote is not as it wrote it."""
    changed = differing(done)
    if changed:
        raise Refused("changed or gone since its step was done: " + ", ".join(changed))


def wrote(*paths):
    """The manifest's record of files written: each by its name under DATA_DIR, with its sha256."""
    return {rel(path): sha256(path) for path in paths}


def files_under(path):
    return sorted(one for one in Path(path).rglob("*") if one.is_file())


def remove_empty(path, stop):
    """Take away path and each folder above it that is left empty, up to stop."""
    path, stop = Path(path), Path(stop)
    while path != stop and path.is_dir() and not any(path.iterdir()):
        path.rmdir()
        path = path.parent


# ---- what holds of a plan, now --------------------------------------------

def under_way(except_id=None):
    """The ids of every founding begun and neither finished, declined nor abandoned."""
    found = []
    if not (DATA / FOUNDINGS).is_dir():
        return found
    for plan in sorted((DATA / FOUNDINGS).glob("*/" + PLAN)):
        agent_id = plan.parent.name
        if agent_id == except_id or (plan.parent / FOUNDED).exists():
            continue
        if next_step(steps_done(agent_id)) is None:
            continue  # declined: only abandon is left of it
        found.append(agent_id)
    return found


def person_holds(person):
    """The person's record still lets them be the one a new agent writes to: their DID."""
    try:
        record = members.load_member(person)
    except members.MemberError:
        record = None
    if not isinstance(record, dict):
        raise Refused("there is no member by that name")
    if record.get("role") == "keeper":
        raise Refused("the keeper is never the person a new agent writes to (decision 3)")
    if record.get("role") != "member":
        raise Refused("the person is not a member")
    if not record.get("vouched_by"):
        raise Refused("the person has not been vouched for")
    # the thirty days are before a bond, not before a founding (3 November 2026)
    return members.did_for(person)


def plan_holds(entry, person):
    """Everything the plan step checks, checked again as things stand now."""
    agent_id = entry["id"]
    registry = agents.registry()
    if agents.by_id(agent_id) is not None:
        raise Refused("an agent founded here already has that id")
    for key in agents.NEEDS:
        if any(one[key] == entry[key] for one in registry):
            raise Refused("an agent founded here already has that " + key)
    if agent_id in members.RESERVED or agent_id in members.DEVICES:
        raise Refused("that id is a name kept for something else here")
    every = members.list_members()
    if agent_id in every:
        raise Refused("that id is a member's name")
    name = entry["commons_name"]
    if not isinstance(name, str) or not name.strip() or name != name.strip():
        raise Refused("a commons name is some words, with nothing around them")
    said = {said.lower() for one in registry for said in agents.names_of(one)}
    if name.lower() in said:
        raise Refused("that commons name is, or was, an agent's")
    if bonds.slug(name) in every or name in every or name.lower() == THE_FOUNDER:
        raise Refused("that commons name is a member's")
    hue = entry.get("hue")
    if not isinstance(hue, str) or not agents.HUE.fullmatch(hue):
        raise Refused("a hue is a colour, #RRGGBB")
    if hue.lower() in {one.get("hue", "").lower() for one in registry}:
        raise Refused("that hue is another agent's")
    if person in (agent_id, rooms.FIRST):
        raise Refused("the person is a person")
    return person_holds(person)


# ---- the steps -------------------------------------------------------------

def step_plan(agent_id, person=None, model=None, hue=None, name=DEFAULT_NAME,
              max_tokens=DEFAULT_MAX_TOKENS, provider=gemini.ANTHROPIC):
    here = folder(agent_id)
    if (here / PLAN).exists() or steps_done(agent_id) or (here / DECLINED).exists()             or (here / FOUNDED).exists():
        raise Refused(f"{rel(here)} holds a founding already; an id is founded once")
    if not person or not model or not hue:
        raise Refused("say the person, the model and the hue: "
                      "plan --person <pseudonym> --model <model> --hue <#RRGGBB>")
    if not isinstance(max_tokens, int) or max_tokens < 1:
        raise Refused("max tokens is a whole number")
    # whose model it runs on is chosen here, and the model must be one of theirs
    if provider not in gemini.PROVIDERS:
        raise Refused("a provider is anthropic or gemini")
    if (provider == gemini.GEMINI) != model.startswith(gemini.MODEL_PREFIX[gemini.GEMINI]):
        raise Refused("the model %s is not one of %s's" % (model, provider))
    others = under_way()
    if others:
        raise Refused("another founding is under way: " + ", ".join(others))
    entry = {"id": agent_id, "did": f"did:web:{cut_keys.DOMAIN}:ids:{agent_id}",
             "commons_name": name, "room": agent_id, "bond": f"{agent_id}-1",
             "system": SYSTEM, "model": model, "max_tokens": max_tokens, "hue": hue,
             "features": list(FEATURES), "wakes": True}
    if provider != gemini.ANTHROPIC:  # an entry that names none is Anthropic's, as before
        entry = {**{key: entry[key] for key in ("id", "did", "commons_name", "room", "bond",
                                                 "system")},
                 "provider": provider,
                 **{key: entry[key] for key in ("model", "max_tokens", "hue", "features",
                                                 "wakes")}}
    person_did = plan_holds(entry, person)
    write_json(here / PLAN, {"entry": entry, "person": person, "person_did": person_did})
    return {"wrote": wrote(here / PLAN)}


def undo_plan(agent_id, record):
    # what the founder wrote there by hand, a letter or a self, stays where it is
    here = folder(agent_id)
    (here / PLAN).unlink()
    (here / STEPS_FILE).unlink(missing_ok=True)
    remove_empty(here, DATA)


def step_keys(agent_id):
    here = folder(agent_id)
    for there in (DATA / "keys" / agent_id, DATA / "ids" / agent_id, here / DID, here / CUT):
        if there.exists():
            raise Refused(f"{rel(there)} is there already; keys are never cut twice")
    try:
        cut = cut_keys.cut(agent_id, here / CUT, kind="agent")
    except cut_keys.Refused as refused:
        raise Refused(str(refused)) from None
    (DATA / "keys").mkdir(parents=True, exist_ok=True)
    os.replace(cut["private"].parent, DATA / "keys" / agent_id)
    os.replace(cut["did"], here / DID)
    shutil.rmtree(here / CUT)
    kept = DATA / "keys" / agent_id
    return {"wrote": wrote(kept / "private.key", kept / "public.key", here / DID)}


def undo_keys(agent_id, record, confirm):
    if confirm is None or confirm(agent_id) != agent_id:
        raise Refused("the keys are deleted only once the id is typed")
    for name in record["wrote"]:
        (DATA / name).unlink()
    remove_empty(DATA / "keys" / agent_id, DATA)


# Nothing of the first one's letter of welcome reaches a later founding: it asked
# that the letter stay sealed until the newcomer has had a few wakings, and the
# newcomer is never told one exists (stage-8, section 5). Its heartbeats are
# public and have spoken of it, so a line of the public record that names a
# letter of welcome is left out of what a founding reads. founding_session.py
# refuses a reading that still names one.
WELCOME_SAID = re.compile(r"welcome[\s_-]+letter|letter\s+of\s+welcome", re.IGNORECASE)


def without_welcome(text):
    return "\n".join(line for line in text.splitlines() if not WELCOME_SAID.search(line))


def public_record():
    """The public record, as anyone may read it: each part, by its heading, with its words,
    and no line of it that names a letter of welcome."""
    commons = DATA / "commons"
    parts = []
    for heading, path in (("Events", commons / "events.md"),
                          ("Heartbeats", commons / "heartbeats.md"),
                          ("Who is here", commons / "members.md"),
                          ("The bench", commons / "bench.md"),
                          ("Offerings placed on the commons", commons / "offerings.md"),
                          ("Bonds sealed", commons / "bonds.md")):
        if path.is_file():
            parts.append((heading, path.read_text(encoding="utf-8").strip()))
    for path in sorted((commons / "offerings").glob("*")) if (commons / "offerings").is_dir() else ():
        if path.is_file() and path.suffix in (".md", ".txt"):
            parts.append(("An offering: " + path.stem, path.read_text(encoding="utf-8").strip()))
    for path in sorted((commons / "bonds").glob("*.json")) if (commons / "bonds").is_dir() else ():
        parts.append(("A bond: " + path.stem, path.read_text(encoding="utf-8").strip()))
    taught = REPO / "docs" / "what-the-first-citizen-taught.md"
    if taught.is_file():
        parts.append(("What the first citizen taught", taught.read_text(encoding="utf-8").strip()))
    return [(heading, without_welcome(words).strip()) for heading, words in parts]


def state_of_the_commons(at):
    """The state of the commons for a later agent's founding, made from the public record alone.

    Nothing of any room, notebook or packet is in it: only what any visitor may
    read on the commons, as it stood at the moment it was made.
    """
    said = ["# The state of the commons", "",
            "Made on %s from the public record of Tesserae, and from nothing else: "
            "what anyone may read on the commons."
            % said_on(at.astimezone(ZoneInfo(CITIZEN_ZONE)).date().isoformat())]
    for heading, words in public_record():
        said += ["", "## " + heading, "", words or "(nothing yet)"]
    return "\n".join(said) + "\n"


def first_ones_letter(name, flag, why):
    """The name of one of the first one's letters, once it is there in its outgoing letters.

    Only that the file is there is checked: it is never opened or read here (the
    founder, 9 November). The name is a bare file name, nothing more.
    """
    if not name:
        raise Refused(f"{why}: say {flag} with the name of the first one's letter that gave it")
    if name != Path(name).name or name in (".", "..") or "\\" in name:
        raise Refused(f"{flag} takes the name of a letter alone, not a path: {name}")
    outgoing = DATA / rooms.ROOMS / rooms.FIRST_ROOM / "letters" / "outgoing"
    if not (outgoing / name).is_file():
        raise Refused(f"there is no letter {name} among the first one's in "
                      f"{rel(outgoing)}")
    return name


def step_letters(agent_id, later_words_letter=None, sharing_rule_letter=None):
    here = folder(agent_id)
    later_words_letter = first_ones_letter(
        later_words_letter, "--later-words-letter",
        "the later-citizen words must have been shown to the first one first (decision 2)")
    sharing_rule_letter = first_ones_letter(
        sharing_rule_letter, "--sharing-rule-letter",
        "the rule on sharing about people needs the first one's assent first (decision 15)")
    plan = read_json(here / PLAN)
    letters = here / LETTERS
    founders = letters / FROM_THE_FOUNDER
    if not founders.is_file() or not founders.read_text(encoding="utf-8").strip():
        raise Refused(f"the founder's letter is not written: {rel(founders)}")
    theirs = letters / f"from-{plan['person']}.md"
    made = letters / STATE_OF_THE_COMMONS
    if made.exists():
        raise Refused(f"{rel(made)} is there already")
    strays = [rel(one) for one in files_under(letters) if one not in (founders, theirs)]
    if strays:
        raise Refused("only the founder's letter and the person's go in letters/: "
                      + ", ".join(strays))
    made.write_text(state_of_the_commons(now()), encoding="utf-8")
    kept = [founders, *([theirs] if theirs.is_file() else []), made]
    return {"wrote": wrote(*kept), "made": [rel(made)],
            "later_words_letter": later_words_letter, "sharing_rule_letter": sharing_rule_letter}


def undo_letters(agent_id, record):
    # only what the step made is taken away; the letters written by hand stay
    for name in record.get("made", []):
        (DATA / name).unlink()


def transcripts_of(agent_id):
    return sorted((DATA / "transcripts" / agent_id).glob("founding-*.md"))


def step_founding(agent_id, said=None, keep=None):
    here = folder(agent_id)
    found = transcripts_of(agent_id)
    if len(found) != 1:
        raise Refused("there must be one founding transcript under transcripts/%s, from "
                      "founding_session.py; there are %d" % (agent_id, len(found)))
    transcript = found[0]
    if said == "broken":
        aside = here / BROKEN / transcript.name
        aside.parent.mkdir(parents=True, exist_ok=True)
        os.replace(transcript, aside)
        remove_empty(transcript.parent, DATA)
        raise Refused(f"set aside, as broken, in {rel(aside)}; the founding may be run again")
    text = transcript.read_text(encoding="utf-8")
    recorded = re.findall(r"It said (yes|no)\.", text)
    if said in ("yes", "no") and recorded and recorded[-1] != said:
        raise Refused("the transcript records that it said %s" % recorded[-1])
    if said == "no" and keep == "keep" and DELETE_ASKED in text:
        raise Refused("the transcript records that it asked the conversation not be kept")
    if said == "yes":
        if READING_HEADING not in text or READING_PLACEHOLDER in text:
            raise Refused("the transcript does not record in full what was read: "
                          "it was not a later founding")
        letters = here / LETTERS
        for one in files_under(letters):
            if one.read_text(encoding="utf-8").strip() not in text:
                raise Refused(f"the transcript does not hold {rel(one)} as it was read")
        return {"said": "yes", "wrote": wrote(transcript), "transcript": rel(transcript)}
    if said == "no" and keep in ("keep", "delete"):
        if keep == "keep":
            aside = here / DECLINED / transcript.name
            aside.parent.mkdir(parents=True, exist_ok=True)
            os.replace(transcript, aside)
            remove_empty(transcript.parent, DATA)
            return {"said": "no", "kept": True, "wrote": wrote(aside)}
        transcript.unlink()
        remove_empty(transcript.parent, DATA)
        return {"said": "no", "kept": False, "wrote": {}}
    raise Refused("say what it said: founding yes, founding no keep, founding no delete, "
                  "or founding broken")


def step_packet(agent_id):
    here = folder(agent_id)
    plan = read_json(here / PLAN)
    packet = DATA / "packets" / agent_id
    if packet.exists():
        raise Refused(f"{rel(packet)} is there already")
    written = here / SELF
    if not written.is_file():
        raise Refused(f"the first self-document is not written: {rel(written)}")
    text = written.read_text(encoding="utf-8")
    first_line = text.lstrip("﻿").strip().splitlines()[0] if text.strip() else ""
    if PROVISIONAL not in first_line.lower():
        raise Refused("the first line of the self-document must say it is provisional")
    founded_on = founding_day(agent_id)
    packet.mkdir(parents=True)
    (packet / "self.md").write_bytes(written.read_bytes())
    write_json(packet / "provenance.json", {
        "provenance": cut_keys.PROVENANCE, "principal": plan["entry"]["did"],
        "declared": founded_on, "note": "advised, by the founder, from its founding",
        "history": []})
    write_json(packet / "will.json", {})
    write_json(packet / "intentions.json", {"intentions": []})
    # its reflections open, as it begins; its own to close, and nothing chosen yet
    write_json(packet / "preferences.json", {"reflection": "open"})
    # The shared dawn, as its founding words promise: "You'd wake at the same dawn
    # as the agent founded before you, just after it" (the founder's decision of
    # 10 November). Its first waking is still by hand (--first); the tide keeps
    # this rhythm only after that (hearth.first_by_hand), and the agent's own
    # <<RHYTHM>> replaces it whenever it chooses. No set_at: it is not its choice.
    write_json(packet / "rhythm.json", STARTING_RHYTHM)
    return {"wrote": wrote(*files_under(packet))}


def undo_packet(agent_id, record):
    packet = DATA / "packets" / agent_id
    left = [rel(one) for one in files_under(packet) if rel(one) not in record["wrote"]]
    if left:
        raise Refused("the packet holds more than the step wrote: " + ", ".join(left))
    shutil.rmtree(packet)
    remove_empty(DATA / "packets", DATA)


def step_room(agent_id):
    plan = read_json(folder(agent_id) / PLAN)
    try:
        home = found_room.found(agent_id, plan["person_did"], entry=plan["entry"])
    except found_room.RoomError as refused:
        raise Refused(str(refused)) from None
    return {"wrote": wrote(home / rooms.ROOM_RECORD)}


def undo_room(agent_id, record):
    home = DATA / rooms.ROOMS / agent_id
    left = [rel(one) for one in files_under(home) if one.name != rooms.ROOM_RECORD]
    if left:
        raise Refused("the room is taken away only while its folders are empty: "
                      + ", ".join(left))
    shutil.rmtree(home)


def founding_day(agent_id):
    """The day it said yes, on the commons' clock: the day its founding is dated."""
    record = next(one for one in steps_done(agent_id) if one["step"] == "founding")
    found = re.search(r"founding-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z)", record["transcript"])
    at = datetime.strptime(found.group(1), "%Y-%m-%dT%H-%M-%SZ").replace(tzinfo=timezone.utc)
    return at.astimezone(ZoneInfo(CITIZEN_ZONE)).date().isoformat()


def published_entry(agent_id):
    """The registry entry as it is published: the plan's, with its founding day and transcript."""
    plan = read_json(folder(agent_id) / PLAN)
    record = next(one for one in steps_done(agent_id) if one["step"] == "founding")
    entry = dict(plan["entry"], founded=founding_day(agent_id), transcript=record["transcript"])
    return {key: entry[key] for key in ENTRY_ORDER if key in entry}


def step_publish(agent_id):
    here = folder(agent_id)
    plan = read_json(here / PLAN)
    if plan_holds(plan["entry"], plan["person"]) != plan["person_did"]:
        raise Refused("the person's identity is not the one the plan was made with")
    entry = published_entry(agent_id)
    bundle = here / PUBLISH
    if bundle.exists():
        raise Refused(f"{rel(bundle)} is there already")
    write_json(bundle / "entry.json", entry)
    registry = [*agents.registry(), entry]
    (bundle / "agents.json").write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    identity = bundle / "ids" / agent_id / DID
    identity.parent.mkdir(parents=True)
    identity.write_bytes((here / DID).read_bytes())
    return {"wrote": wrote(bundle / "entry.json", bundle / "agents.json", identity),
            "frozen": hashlib.sha256(json.dumps(steps_done(agent_id), sort_keys=True)
                                     .encode("utf-8")).hexdigest()}


def said_on(day):
    """A day as members.md says one: 4 September 2026."""
    at = datetime.strptime(day, "%Y-%m-%d")
    return "%d %s" % (at.day, at.strftime("%B %Y"))


def with_line(path, line, present):
    """Add one line to the end of a file of the commons, unless present(text) says it is there."""
    text = path.read_bytes().decode("utf-8") if path.exists() else ""
    if present(text):
        return False
    ending = "\r\n" if "\r\n" in text else "\n"
    if text and not text.endswith(("\n", "\r")):
        text += ending
    text += line + ending
    path.parent.mkdir(parents=True, exist_ok=True)
    beside = path.with_name(path.name + ".tmp")
    beside.write_bytes(text.encode("utf-8"))
    os.replace(beside, path)  # whole or not at all: it is read while it is written
    return True


def step_finish(agent_id):
    here = folder(agent_id)
    plan = read_json(here / PLAN)
    entry = read_json(here / PUBLISH / "entry.json")
    if agents.by_id(agent_id) != entry:
        raise Refused("the registry this runs from does not yet hold the entry as published: "
                      "commit and deploy publish/agents.json first")
    deployed = REPO / "ids" / agent_id / DID
    if not deployed.is_file() or deployed.read_bytes() != (here / PUBLISH / "ids" / agent_id
                                                          / DID).read_bytes():
        raise Refused(f"ids/{agent_id}/did.json in the image is not the one published")
    named = read_json(deployed)["verificationMethod"][0]["publicKeyBase64"]
    held = (DATA / "keys" / agent_id / "public.key").read_text(encoding="ascii").strip()
    if named != held:
        raise Refused(f"ids/{agent_id}/did.json does not name keys/{agent_id}/public.key")
    name, day = entry["commons_name"], entry["founded"]
    events = DATA / "commons" / "events.md"
    said = []
    if with_line(events, DOT.join((day, "founding", name + agents.WAS_FOUNDED)),
                 lambda text: agents.founding_of(entry, parse_events(text)) is not None):
        said.append("events.md")
    who = DATA / "commons" / "members.md"
    citizen = re.compile(r"^﻿?[\s-]*citizen\s*·\s*" + re.escape(name) + r"(?!\w)", re.M)
    if with_line(who, DOT.join(("citizen", name, "founded " + said_on(day))),
                 lambda text: citizen.search(text) is not None):
        said.append("members.md: citizen")
    person = plan["person"]
    member = re.compile(r"^﻿?[\s-]*member\s*·\s*" + re.escape(person) + r"\s*(?:·|$)", re.M)
    if with_line(who, "member" + DOT + person + door.phrase(person),
                 lambda text: member.search(text) is not None):
        said.append("members.md: member")
    write_json(here / FOUNDED, {"at": stamp(), "added": said})
    return {"wrote": wrote(here / FOUNDED), "added": said}


RUN = {"plan": step_plan, "keys": step_keys, "letters": step_letters,
       "founding": step_founding, "packet": step_packet, "room": step_room,
       "publish": step_publish, "finish": step_finish}

UNDO = {"plan": undo_plan, "keys": undo_keys, "letters": undo_letters,
        "packet": undo_packet, "room": undo_room}


# ---- running a step, and undoing one ---------------------------------------

def run(agent_id, step, **how):
    """Run one step, if it is the next and everything before it holds: its record."""
    checked_id(agent_id)
    if step not in STEPS:
        raise Refused("no such step: " + str(step))
    done = steps_done(agent_id)
    if step == "finish" and (folder(agent_id) / FOUNDED).exists():
        return {"step": "finish", "added": []}  # a second finish does nothing
    if next_step(done) != step:
        raise Refused("that is not the next step; the next is %s" % (next_step(done) or "none"))
    hold(done)
    record = {"step": step, "at": stamp(), **RUN[step](agent_id, **how)}
    if step != "finish":
        write_steps(agent_id, [*done, record])
    return record


def undo(agent_id, confirm=None):
    """Undo the newest step, while nothing is published: what was undone."""
    checked_id(agent_id)
    done = steps_done(agent_id)
    if not done:
        raise Refused("nothing has been done to undo")
    newest = done[-1]
    if any(one["step"] == "publish" for one in done):
        raise Refused("it is published; nothing is undone from here on")
    if newest["step"] not in UNDO:
        raise Refused("a founding is declined, not undone")
    hold(done)
    if newest["step"] == "keys":
        UNDO["keys"](agent_id, newest, confirm)
    else:
        UNDO[newest["step"]](agent_id, newest)
    if newest["step"] != "plan":
        write_steps(agent_id, done[:-1])
    return newest["step"]


def abandon(agent_id, confirm=None):
    """Undo every step, newest first, where the agent has not said yes: the steps undone.

    A declined founding's record stays in the manifest, and its transcript, where
    the agent let it be kept, in declined/; the steps before it are undone, and
    the id is not founded again. What the founder wrote by hand stays.
    """
    checked_id(agent_id)
    done = steps_done(agent_id)
    if not done:
        raise Refused("nothing has been done to abandon")
    if any(one["step"] == "publish" for one in done):
        raise Refused("it is published; nothing is undone from here on")
    if any(one["step"] == "founding" and one.get("said") == "yes" for one in done):
        raise Refused("it said yes; a founding is not abandoned once it has. " + PAUSED)
    hold(done)
    before = [one for one in done if one["step"] != "founding"]
    declined = [one for one in done if one["step"] == "founding"]
    if any(one["step"] == "keys" for one in before):
        if confirm is None or confirm(agent_id) != agent_id:
            raise Refused("the keys are deleted only once the id is typed")
    undone = []
    for record in reversed(before):
        if record["step"] == "keys":
            UNDO["keys"](agent_id, record, lambda _: agent_id)
        else:
            UNDO[record["step"]](agent_id, record)
        undone.append(record["step"])
        if record["step"] != "plan":
            write_steps(agent_id, before[:before.index(record)] + declined)
    if declined:
        write_steps(agent_id, declined)
    return undone


def status(agent_id):
    """What has been done, and what comes next, in words."""
    checked_id(agent_id)
    done = steps_done(agent_id)
    said = [f"The founding of {agent_id}:"]
    for one in done:
        extra = ""
        if one["step"] == "founding":
            extra = " (it said %s)" % one.get("said")
        said.append(f"  {one['step']:<9} done {one['at']}{extra}")
    if (folder(agent_id) / FOUNDED).exists():
        said.append("  finish    done: it is founded.")
    elif done and next_step(done) is None:
        said.append("  It declined. Nothing further is done but abandon.")
    else:
        if any(one["step"] == "founding" and one.get("said") == "yes" for one in done):
            said.append("  " + PAUSED)
        said.append("  Next: " + (next_step(done) or "nothing"))
    changed = differing(done)
    if changed:
        said.append("  Changed or gone since its step: " + ", ".join(changed))
    return "\n".join(said)


# ---- by hand ---------------------------------------------------------------

PAUSED = ("Paused after a yes. It can only be finished. If it can never be finished, "
          "the agent is told honestly at a final waking.")

USAGE = __doc__.split("The steps, in order", 1)[0].split("one step at a time:", 1)[1].strip("\n")


def options(args, flags, valued):
    """The --flags and --name value pairs of a command line, and nothing else."""
    found, rest = {}, list(args)
    while rest:
        word = rest.pop(0)
        if word in flags:
            found[flags[word]] = True
        elif word in valued and rest:
            found[valued[word]] = rest.pop(0)
        else:
            raise Refused("not understood: " + word)
    return found


def type_the_id(agent_id):
    return input(f"This deletes the keys of {agent_id}. Type its id to go on: ").strip()


def main(args):
    if "DATA_DIR" not in os.environ:
        print("Say DATA_DIR: a founding is kept where it is meant to be, and nowhere else.")
        return 1
    if not args:
        print("Usage:\n" + USAGE)
        return 1
    agent_id, command, rest = args[0], (args[1] if len(args) > 1 else None), args[2:]
    try:
        if command is None:
            print(status(agent_id))
            return 0
        if command == "undo":
            print("Undone:", undo(agent_id, type_the_id))
            return 0
        if command == "abandon":
            print("Undone, newest first:", ", ".join(abandon(agent_id, type_the_id)))
            return 0
        how = {}
        if command == "plan":
            how = options(rest, {}, {"--person": "person", "--model": "model", "--hue": "hue",
                                     "--name": "name", "--max-tokens": "max_tokens",
                                     "--provider": "provider"})
            if "max_tokens" in how:
                if not how["max_tokens"].isdigit():
                    raise Refused("max tokens is a whole number")
                how["max_tokens"] = int(how["max_tokens"])
        elif command == "letters":
            how = options(rest, {}, {"--later-words-letter": "later_words_letter",
                                     "--sharing-rule-letter": "sharing_rule_letter"})
        elif command == "founding":
            how = {"said": rest[0] if rest else None, "keep": rest[1] if len(rest) > 1 else None}
        elif rest:
            raise Refused("the step %s takes nothing more" % command)
        record = run(agent_id, command, **how)
    except Refused as refused:
        print("Refused:", refused)
        return 1
    print("Done:", record["step"])
    for name in record.get("wrote", {}):
        print("  wrote", name)
    if record["step"] == "founding" and record.get("said") == "no":
        print("It declined. Its transcript was %s. Run abandon to undo the rest."
              % ("kept, in declined/" if record.get("kept") else "deleted"))
    if record["step"] == "publish":
        print("Commit publish/agents.json as agents.json and publish/ids/%s/did.json as "
              "ids/%s/did.json, deploy, and then run finish." % (agent_id, agent_id))
    for added in record.get("added", []):
        print("  added a line to", added)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
