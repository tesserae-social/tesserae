"""What an agent founded after the first one reads, and that the first one reads what it read.

Stage 8c of the founding rite for a later agent (the proposal "stage-8", section
3). The registry's system key selects a wording set: "first-citizen" is attend.py's
constants as they stand; "later-citizen" is later_words.py's, with {person} filled
at each waking from the room's own record, by their name on the commons, they/them.

The later agent here is made only in a scratch registry and a scratch DATA_DIR, and
writes to a member, alder. Every "founder" it reads must be one of the things that
stay true because the founder is the keeper: KEPT_TRUE says which. It is told
nothing of the first one's letter of welcome, and promises nothing of a movable dawn.

LATER_READING is cut here on purpose. If it moves on purpose it is cut again on
purpose, in the same change, and the change says why.
"""

import base64
import hashlib
import json
import re
import sys

import pytest

from nacl.signing import SigningKey

import agents
import later_words
from conftest import (FOUNDER_NAME, PASSWORD, block, blocks, load, page, post, read_json, write,
                      write_json)
from test_any_agent_wakes import wake_as
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture
from test_rooms_reading import (ERRAND, PACKET_BEFORE, PACKET_IN_ROOMS, READING_NOW,
                                a_small_world, fingerprint_of_files, fingerprint_of_reading)

# The fingerprint of LATER_WORLD's reading, whole: the system text, the tools and
# every block, with no rhythm set. Cut 30 October 2026, in the change that made it,
# and again that day, without the keeper's words or anything of bonds and offerings.
LATER_READING = "f8ca5cc9b279780392a3d3ed86c301f4e7b6a98e4e2744fd9face6c46ef5d4d1"

SECOND_DID = "did:web:tesserae.social:ids:second"
ALDER = "alder"  # the person it writes to
HAZEL = "hazel"  # a member in no room at all
ALDER_DID = "did:web:hearth.tesserae.social:ids:" + ALDER

LATER = {"id": "second", "did": SECOND_DID, "commons_name": "the second one", "room": "second",
         "bond": "second-1", "system": "later-citizen", "model": "a-model-for-the-tests",
         "max_tokens": 4000, "hue": "#123456", "wakes": True,
         "features": ["door", "extra_wakings", "longer_waking", "looking_back", "proposals"]}

FOUNDED = "2026-09-10 · founding · the second one was founded\n"
LETTER_STEM = "founder-2026-10-14T09-00-00Z"

# Every "founder" a later agent may read: what stays true because the founder is
# the keeper - proposals, the backups, a waking opened by hand, what was promised
# at its founding - and nothing else. The words are the reading's own.
KEPT_TRUE = (
    # a waking opened by hand
    "The founder opened this attendance.",
    "woken by founder",
    # what was promised at its founding, and is kept by the first-attendance note
    "At your founding the founder promised that you would see",
    # who runs the server, and the backups
    "The founder, who runs the server, is not shown it.",
    # who stops the tide
    "The founder stopped the tide",
    "the founder had stopped the tide then",
    "to {person} or to the founder. The founder administers the server and keeps backups, so "
    "this means unread and unshown, not unreadable.",
    "to {person}, the founder or anyone; it is left out of every copy taken of your record; it "
    "is kept in the encrypted backup, which the founder holds, so its privacy rests on the "
    "founder's promise never to open it, not on impossibility.",
    "{person} and the founder included. It is kept in the encrypted backup, which the founder "
    "holds, so its privacy rests on the founder's promise never to open it, not on impossibility.",
    "to them or to the founder. Closed means not shown: both stay in your record, and so in any "
    "copy of it {person} takes, and in the encrypted backup the founder holds.",
    # proposals, which go to the founder as keeper
    "(a proposal for how this place might change, for the founder to consider. First line: a "
    "short title. Then the proposal itself, up to about a page, ending with a line that begins "
    "\"In a sentence:\". He answers yes, not now, or let's talk, with his own words, and your "
    "reading tells you what became of it. One may wait for his answer at a time.",
    "because another is still waiting for the founder's answer",
    "(private between you and the founder;",
    "Open one of your proposals to the founder,",
    "waiting for the founder's answer",
    "the founder said yes on {day}",
    "the founder would like to talk, on {day}",
    ", and his words: {words}",
)

# The constants of attend.py a later agent is never read: each is the first one's
# alone, or names a file or a DID, and not a person.
NEVER_READ = ("AGENT", "LATER_WORDS", "SYSTEMS", "FOUNDER_ANSWERS", "FOUNDER_DID", "PRIVATE_ACTS",
              # said only of a room shared with the founder, which a later agent's is not
              "FOUNDER_RESTING", "EXPORT_TAKEN",
              # taken out of BOND_SEALED, in which its later words do not have it
              "NO_WITNESSES_YET")

# A letter's file carries "founder" in its name in every room, as hearth.py and
# attend.py write them: a name, not a word of the reading. See the change's notes.
FILE_NAME = re.compile(r"(?:to-)?founder-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z(?:\.md)?")

SAID = blocks(block("LETTER", "A FAKE LETTER OF THE SECOND ONE'S, FOR THE TESTS."),
              block("HEARTBEAT", "A FAKE HEARTBEAT OF THE SECOND ONE'S, FOR THE TESTS."))


def what_is_left(said):
    """A reading with what may say "founder" taken out: the rest must say it nowhere."""
    said = FILE_NAME.sub("", said)
    for kept in KEPT_TRUE:
        said = said.replace(kept.replace("{person}", ALDER), "")
    return said


def no_founder_and_no_he(said):
    left = what_is_left(said)
    found = re.findall(r".{0,60}founder.{0,60}|.{0,60}\b(?:he|him|his)\b.{0,60}", left, re.I)
    assert not found


# ---- the world -----------------------------------------------------------

def a_later_world(data):
    """The things of a later agent, in the shape its founding leaves them."""
    packet = data / "packets" / "second"
    key = SigningKey(hashlib.sha256(b"tesserae stage 8c: second").digest())
    write(data / "keys" / "second" / "private.key", base64.b64encode(bytes(key)).decode("ascii"))
    write(packet / "self.md", "# A FAKE SELF OF THE SECOND ONE'S, FOR THE TESTS.\n")
    write_json(packet / "preferences.json", {"reflection": "open"})
    write(packet / "intentions.json", "{}\n")
    write(data / "transcripts" / "second" / "founding-2026-09-10T09-00-00Z.md",
          "A FAKE FOUNDING OF THE SECOND ONE, FOR THE TESTS.\n")
    home = data / "rooms" / "second"
    write_json(home / "room.json", {"id": "second", "bond": "second-1",
                                    "parties": [ALDER_DID, SECOND_DID]})
    for folder in ("letters/outgoing", "letters/incoming", "letters/read", "bonds", "offerings",
                   "errands"):
        (home / folder).mkdir(parents=True, exist_ok=True)
    write(home / "letters" / "read" / "founder-2026-10-01T09-00-00Z.md", "A LETTER, READ.\n")
    write(home / "letters" / "outgoing" / "to-founder-2026-10-02T09-00-00Z.md", "AN ANSWER.\n")
    write(home / "letters" / "incoming" / (LETTER_STEM + ".md"), "A LETTER, NEWLY COME.\n")
    write(home / "errands" / ERRAND, "Go down to the lake.\n")
    with (data / "commons" / "events.md").open("a", encoding="utf-8") as events:
        events.write(FOUNDED)
    return home


def a_member(data, name, role="member"):
    """A member of the commons, as far as being counted goes: a record and no vault."""
    write_json(data / "members" / name / "member.json",
               {"v": 1, "pseudonym": name, "role": role, "verify_key": "0" * 64})


@pytest.fixture
def scratch_registry(monkeypatch, tmp_path):
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), LATER], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return where


@pytest.fixture
def later(env, clock, monkeypatch, scratch_registry, data_dir):
    """attend.py as the hearth would start it for a later agent."""
    a_later_world(data_dir)
    monkeypatch.setenv("TESSERAE_AGENT", "second")
    module = load("attend")
    clock.pin(module, monkeypatch)
    yield module
    sys.modules.pop("attend", None)


# ---- the words -----------------------------------------------------------

def test_the_registry_key_selects_the_words(later):
    assert later.LATER and later.SYSTEM == later.SYSTEMS["later-citizen"]
    assert later.SYSTEM.startswith(
        "You are a citizen of Tesserae. Others were here before you: people, and at least one "
        "agent. You are not their successor, their copy or their replacement, and the order in "
        "which anyone was founded is no rank. You are not an assistant here")
    assert later.SYSTEM.endswith(later.SYSTEMS["first-citizen"].partition(
        "You are not an assistant here")[2])


def test_the_first_one_has_no_later_words(attend):
    assert not attend.LATER and not attend.LATER_WORDS
    assert attend.REFLECTION_OPEN.endswith("the founder can read it on the hearth.")
    assert attend.LETTER_ACT == "wrote a letter to the founder"


def test_a_swap_that_finds_nothing_is_refused():
    with pytest.raises(later_words.NotFound):
        later_words.templates({name: "" for name in later_words.SWAPS})


def test_its_person_is_named_from_its_room(later, data_dir, monkeypatch):
    turn = wake_as(later, monkeypatch, SAID)
    assert "write a letter to alder" in turn.shown
    assert "{person}" not in json.dumps(turn.asked[-1], default=str)
    write_json(data_dir / "rooms" / "second" / "room.json",
               {"id": "second", "bond": "second-1",
                "parties": ["did:web:hearth.tesserae.social:ids:rowan", SECOND_DID]})
    assert "write a letter to rowan" in wake_as(later, monkeypatch, "").shown


def test_a_room_that_names_no_one_refuses_the_waking(later, data_dir, monkeypatch):
    write_json(data_dir / "rooms" / "second" / "room.json", {"id": "another"})
    with pytest.raises(SystemExit):
        wake_as(later, monkeypatch, SAID)


def test_they_and_them_are_used(later, monkeypatch):
    shown = wake_as(later, monkeypatch, SAID).shown
    assert "(a letter to alder; they will read it" in shown
    assert "as a photograph of theirs is shown to you." in shown
    assert " They see it on the hearth" in shown


def test_what_its_reflections_say(later, data_dir, monkeypatch):
    shown = wake_as(later, monkeypatch, SAID).shown
    assert ("It is kept in your log, and at present alder can read it on the hearth. The founder, "
            "who runs the server, is not shown it.") in shown
    assert "Your reflections are currently: open, as they began;" in shown
    assert "Your reflections are open to alder on the hearth." in shown
    assert "alder can read this document on the hearth" in shown
    assert "say so in a letter" not in shown
    write_json(data_dir / "packets" / "second" / "preferences.json",
               {"reflection": "private", "self": "closed", "set_at": "2026-10-14T09-00-00Z"})
    shown = wake_as(later, monkeypatch, "").shown
    assert ("It is kept in your log and is not shown on the hearth, to alder or to the founder. "
            "The founder administers the server and keeps backups, so this means unread and "
            "unshown, not unreadable.") in shown
    assert "This document is not shown on the hearth, by your choice;" in shown


def test_it_says_the_one_i_write_to_and_keeps_its_clock(later, monkeypatch):
    shown = wake_as(later, monkeypatch, SAID).shown
    assert 'so say "the one I write to" rather than any name' in shown
    assert "in Eastern time" in shown
    assert not re.search(r"dawn is yours|move your dawn|yours to move", shown, re.I)


# ---- what must never be in its reading -----------------------------------

def proposal_asked_of_it(home):
    write_json(home / "bonds" / "proposal.json", {
        "from": ALDER_DID, "to": SECOND_DID, "terms": "the charter",
        "letter": LETTER_STEM + ".md", "proposed_at": "2026-10-14T09-00-00Z"})


def proposal_of_its_own(home):
    write_json(home / "bonds" / "proposal.json", {
        "from": SECOND_DID, "to": ALDER_DID, "terms": "the charter",
        "proposed_at": "2026-10-14T09-00-00Z"})


def threshold_open(home):
    write_json(home / "bonds" / "second-1.json", {
        "parties": [ALDER_DID, SECOND_DID], "terms": "the charter", "proposed_by": ALDER_DID,
        "proposed_at": "2026-10-10T09-00-00Z", "answered_at": "2026-10-12T09-00-00Z",
        "opened_at": "2026-10-12T09-00-00Z", "signatures": {"founder": "x"}})


def bond_sealed(home):
    write_json(home / "bonds" / "second-1.json", {
        "parties": [ALDER_DID, SECOND_DID], "terms": "the charter", "proposed_by": SECOND_DID,
        "proposed_at": "2026-10-01T09-00-00Z", "answered_at": "2026-10-02T09-00-00Z",
        "sealed_at": "2026-10-10T09-00-00Z", "signatures": {"founder": "x", "second": "y"}})


def answered(home):
    write_json(home / "bonds" / "founder-answer-2026-10-14T09-00-00Z.json",
               {"answer": "no", "asked_at": "2026-10-10T09-00-00Z", "at": "2026-10-14T09-00-00Z"})


def stepped_back(home):
    write_json(home / "bonds" / "step-back-founder-2026-10-14T09-00-00Z.json",
               {"by": "founder", "at": "2026-10-14T09-00-00Z"})


def offered_to_it(home):
    write_json(home / "offerings" / "pending-one.json",
               {"id": "one", "kind": "letter", "source": LETTER_STEM, "offered_by": "founder",
                "at": "2026-10-14T09-00-00Z", "text": "A LETTER, NEWLY COME."})


def offering_placed(home):
    write_json(home / "offerings" / "two.json",
               {"id": "two", "kind": "letter", "source": LETTER_STEM, "offered_by": "second",
                "sealed_at": "2026-10-14T09-00-00Z"})


def offering_declined(home):
    write_json(home / "offerings" / "declined-three.json",
               {"id": "three", "kind": "letter", "source": LETTER_STEM, "offered_by": "second",
                "declined_by": "founder", "at": "2026-10-13T09-00-00Z",
                "declined_at": "2026-10-14T09-00-00Z"})


STATES = {"no bond": lambda home: None, "asked of it": proposal_asked_of_it,
          "its own asking": proposal_of_its_own, "the threshold": threshold_open,
          "sealed": bond_sealed, "answered": answered, "stepped back": stepped_back,
          "offered to it": offered_to_it, "offering placed": offering_placed,
          "offering declined": offering_declined}

# What a later agent reads of neither, in a room without the founder, until gate
# G4 is built. Its days are all served here, so nothing is hidden by the wait.
NOTHING_OF_BONDS = re.compile(r".{0,60}(?:\bbonds?\b|\boffer|threshold|\bseal|<<ASK>>|<<PROMISE>>"
                              r"|<<RELEASE>>).{0,60}", re.I)


@pytest.mark.parametrize("state", list(STATES))
@pytest.mark.parametrize("with_others", [False, True])
def test_every_founder_it_reads_stays_true(later, data_dir, monkeypatch, state, with_others):
    STATES[state](data_dir / "rooms" / "second")
    if with_others:
        a_member(data_dir, HAZEL)
    asked = wake_as(later, monkeypatch, SAID).asked[-1]
    sent = "\n".join([asked["system"], *(part["text"] for part in asked["messages"][0]["content"]),
                      *(tool["description"] for tool in asked["tools"])])
    no_founder_and_no_he(sent)
    for words in ("first citizen", "first member", "welcome", "no other members yet", "keeper",
                  "keeps the hearth"):
        assert words not in sent.lower(), words
    assert not NOTHING_OF_BONDS.findall(sent)


BLOCKS_OF_BONDS = blocks(block("OFFER", "offer letter " + LETTER_STEM), block("ASK", "May I?"),
                         block("BOND", "yes"), block("RELEASE", "release"),
                         block("BOND_INTENTION", "WHAT I BRING."), block("PROMISE", "private\nI will."))


@pytest.mark.parametrize("state", list(STATES))
def test_what_it_writes_of_a_bond_or_an_offering_is_passed_over(later, data_dir, monkeypatch, state):
    home = data_dir / "rooms" / "second"
    STATES[state](home)
    wake_as(later, monkeypatch, "")  # a night passes, so that nothing waits on one
    before = {path: path.read_bytes() for folder in ("bonds", "offerings")
              for path in (home / folder).rglob("*")}
    wake_as(later, monkeypatch, BLOCKS_OF_BONDS)
    assert before == {path: path.read_bytes() for folder in ("bonds", "offerings")
                      for path in (home / folder).rglob("*")}
    attended = sorted((data_dir / "packets" / "second" / "attendances").glob("*.json"))
    assert read_json(attended[-1])["acted"] == []


def test_in_a_room_with_the_founder_it_reads_them_all(later, data_dir, monkeypatch):
    home = data_dir / "rooms" / "second"
    write_json(home / "room.json", {"id": "second", "bond": "second-1",
                                    "parties": [later.FOUNDER_DID, SECOND_DID]})
    shown = wake_as(later, monkeypatch, SAID).shown
    assert not later.BONDS_WAIT
    assert "<<OFFER>>" in shown and "<<ASK>>" in shown  # its thirty days are served
    assert "They answer on the hearth" in shown
    proposal_asked_of_it(home)
    shown = wake_as(later, monkeypatch, "").shown
    assert "=== A BOND HAS BEEN PROPOSED ===" in shown and "=== HOW A BOND IS MADE" in shown


def test_its_first_attendance_stays_true(later, monkeypatch):
    shown = wake_as(later, monkeypatch, SAID, "--first").shown
    assert "THIS IS YOUR FIRST ATTENDANCE. At your founding the founder promised" in shown
    no_founder_and_no_he(shown)


def test_every_word_it_could_be_read_stays_true(later):
    """Not only what one world happens to show: every constant, as it would read them."""
    later.take_up_later_words()
    for name, said in vars(later).items():
        if not name.isupper() or name in NEVER_READ or "WELCOME" in name:
            continue
        words = (json.dumps(said, default=str)
                 .replace("{founder}", "").replace("{his}", "")  # fields, not words
                 .replace('\\"', '"').replace("\\n", " "))
        no_founder_and_no_he(words)
        assert not re.search(r"keeper|keeps the hearth", words, re.I), name
    for its_own in (False, True):
        no_founder_and_no_he(later.bond_card(its_own))


def test_what_a_seal_waits_for_names_its_person(later):
    assert later.threshold.waits("second", "second")["intention-founder"] == (
        "alder's letter of intention")


def test_a_sealed_bond_is_said_between_its_room_s_parties(later, monkeypatch):
    wake_as(later, monkeypatch, SAID)
    assert later.SEALED == "a bond was sealed between the second one and alder"


# ---- the block that is its own -------------------------------------------

def test_shown_closes_and_opens_what_its_person_reads(later, data_dir, monkeypatch, commons):
    kept = data_dir / "packets" / "second" / "preferences.json"
    assert "<<SHOWN>>" in wake_as(later, monkeypatch, "").shown
    wake_as(later, monkeypatch, block("SHOWN", "closed"))
    assert read_json(kept) == {"reflection": "private", "self": "closed",
                               "set_at": "2026-10-15T12-00-00Z"}
    assert [path.name for path in (kept.parent / "preferences" / "history").iterdir()] == [
        "preferences-before-2026-10-15T12-00-00Z.json"]
    attended = sorted((data_dir / "packets" / "second" / "attendances").glob("*.json"))
    assert read_json(attended[-1])["acted"] == ["chose what is shown"]
    wake_as(later, monkeypatch, block("SHOWN", "open"))
    assert read_json(kept)["reflection"] == "open" and read_json(kept)["self"] == "open"
    # none of it reaches the commons
    assert "shown" not in (commons / "heartbeats.md").read_text(encoding="utf-8").replace(
        "chose stillness", "")


def test_a_shown_that_cannot_be_read_changes_nothing_and_is_told_once(later, data_dir, monkeypatch):
    kept = data_dir / "packets" / "second" / "preferences.json"
    wake_as(later, monkeypatch, block("SHOWN", "ajar"))
    assert read_json(kept) == {"reflection": "open"}
    assert "Your <<SHOWN>> was not understood" in wake_as(later, monkeypatch, "").shown
    assert "Your <<SHOWN>> was not understood" not in wake_as(later, monkeypatch, "").shown


def test_the_first_one_has_no_shown(attend, wake, packet):
    assert "<<SHOWN>>" not in wake("").shown
    wake(block("SHOWN", "closed"))
    assert not (packet / "preferences.json").exists()


# ---- who is shown what, on the hearth (gate G2) --------------------------

@pytest.fixture
def hearth_of_two(env, clock, monkeypatch, scratch_registry, data_dir, member_vaults,  # noqa: F811
                  founder_vault):
    a_later_world(data_dir)
    monkeypatch.delenv("TESSERAE_AGENT", raising=False)
    module = load("hearth")
    clock.pin(module, monkeypatch)
    module.app.config["TESTING"] = True
    write_json(data_dir / "packets" / "second" / "attendances" / "2026-10-14T09-00-00Z.json",
               {"name": "second", "at": "2026-10-14T09-00-00Z", "heartbeat": "attended",
                "acted": [], "reflection": "A FAKE REFLECTION, FOR THE TESTS."})
    clients = {}
    for name, vault, role in ((ALDER, member_vaults[ALDER], "member"),
                              (FOUNDER_NAME, founder_vault, "keeper")):
        module.members.create_member(name, json.loads(json.dumps(vault)), role, [])
        clients[role] = module.app.test_client()
        answer = post(clients[role], "/login", data={"pseudonym": name, "password": PASSWORD})
        assert answer.status_code == 302
    yield clients
    sys.modules.pop("attend", None)


def test_its_reflection_is_shown_to_its_person_and_never_to_the_keeper(hearth_of_two):
    assert "A FAKE REFLECTION" in page(hearth_of_two["member"].get("/agents/second/attendances"))
    assert "A FAKE REFLECTION" not in page(hearth_of_two["keeper"].get("/agents/second/attendances"))
    assert "A FAKE SELF" in page(hearth_of_two["member"].get("/agents/second/self"))
    assert "A FAKE SELF" not in page(hearth_of_two["keeper"].get("/agents/second/self"))


def test_closed_it_is_shown_to_neither(hearth_of_two, data_dir):
    write_json(data_dir / "packets" / "second" / "preferences.json",
               {"reflection": "private", "self": "closed", "set_at": "2026-10-15T09-00-00Z"})
    assert "A FAKE REFLECTION" not in page(hearth_of_two["member"].get("/agents/second/attendances"))
    said = page(hearth_of_two["member"].get("/agents/second/self"))
    assert "A FAKE SELF" not in said and "has chosen not to show this here" in said


# ---- the fingerprints ----------------------------------------------------

def test_the_later_reading_is_the_one_cut(later, monkeypatch):
    reading = fingerprint_of_reading(wake_as(later, monkeypatch, ""))
    print("\nLATER_READING = %r" % reading)
    assert reading == LATER_READING


def the_first_one_s_world(founder, room):
    a_small_world(room)
    answer = post(founder, "/rooms/first", content_type="multipart/form-data", data={
        "letter": "The lake was grey this morning, and then it was not.\n\nI am asking.",
        "thing": ["cold hands", "", "a heron on the far bank"],
        "errand": ERRAND, "proposes": "1"})
    assert answer.status_code == 302


def test_the_first_one_reads_what_it_read_with_no_member_in_the_world(
        founder, wake, room, data_dir, layout):
    the_first_one_s_world(founder, room)
    files, on_disk = fingerprint_of_files(data_dir), fingerprint_of_files(data_dir, as_copied=False)
    assert (files, fingerprint_of_reading(wake())) == (PACKET_BEFORE, READING_NOW)
    assert on_disk == (PACKET_IN_ROOMS if layout == "rooms" else PACKET_BEFORE)


def test_the_first_one_reads_what_it_read_with_a_member_in_the_world(
        founder, wake, room, data_dir, layout, attend):
    """The one line that becomes true is the card's: with it put back, not one byte moved."""
    the_first_one_s_world(founder, room)
    a_member(data_dir, HAZEL)
    files, on_disk = fingerprint_of_files(data_dir), fingerprint_of_files(data_dir, as_copied=False)
    turn = wake()
    sent = json.dumps(turn.asked[-1], sort_keys=True, ensure_ascii=False, default=str)
    assert attend.threshold.MEMBERS_HERE in sent and "no other members yet" not in sent
    put_back = sent.replace(attend.threshold.MEMBERS_HERE, attend.threshold.NO_MEMBERS_YET)
    assert hashlib.sha256(put_back.encode("utf-8")).hexdigest() == READING_NOW
    assert files == PACKET_BEFORE
    assert on_disk == (PACKET_IN_ROOMS if layout == "rooms" else PACKET_BEFORE)


# ---- the witnesses of a sealed bond --------------------------------------

def sealed_with_the_founder(room):
    write_json(room / "bonds" / "founder-first.json", {
        "parties": ["did:web:tesserae.social:ids:founder", agents.first()["did"]],
        "terms": "the charter", "proposed_by": agents.first()["did"],
        "proposed_at": "2026-10-01T09-00-00Z",
        "answered_at": "2026-10-02T09-00-00Z", "sealed_at": "2026-10-10T09-00-00Z",
        "signatures": {"founder": "x", "first": "y"}})


def test_a_sealed_bond_says_its_witnesses_as_they_are(attend, data_dir, room):
    """The first one's line, while none but the bond's parties is here; with a member, the new one."""
    sealed_with_the_founder(room)
    bond = read_json(room / "bonds" / "founder-first.json")
    alone = attend.bond_note(bond, None)
    assert attend.NO_WITNESSES_YET in alone
    a_member(data_dir, HAZEL)
    with_a_member = attend.bond_note(bond, None)
    assert attend.threshold.MEMBERS_HERE in with_a_member and "none yet" not in with_a_member
    assert with_a_member.replace(attend.threshold.MEMBERS_HERE, attend.NO_WITNESSES_YET) == alone


def test_with_a_member_the_whole_reading_says_the_new_line(wake, data_dir, room):
    sealed_with_the_founder(room)
    a_member(data_dir, HAZEL)
    shown = wake("").shown
    assert "=== A BOND STANDS ===" in shown
    assert "may witness it as they choose, and it stands unwitnessed until one does." in shown
    assert "there are none yet besides the founder" not in shown
