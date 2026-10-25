"""attend.py wakes whichever agent it is told to, and the first one's world is untouched.

Stage 3 of the work that lets the tide wake more than one agent (the proposal
"waking for any agent", 25 October 2026). Which agent a waking is is named by
TESSERAE_AGENT, and everything of its own - its packet, key, DID, room, bond,
name on the commons, founding transcript and the words it is woken with - is
read from its entry in the registry. Unset, it is the first one, and the first
one reads byte for byte what it read before (READING_NOW, PACKET_BEFORE).

The second agent here is made only in a scratch registry and a scratch DATA_DIR,
with its own keys and its own room. Its words to be woken with are a fake for
the tests: the words a later agent is woken with are not written yet.
"""

import base64
import hashlib
import json
import sys

import pytest
from nacl.signing import SigningKey

import agents
from conftest import (FOUNDING_LINE, WORD_LINE, Turn, a_private_notebook, block, blocks, load,
                      post, read_json, write, write_json)
from test_rooms_reading import (ERRAND, PACKET_BEFORE, PACKET_IN_ROOMS, READING_NOW,
                                a_small_world, fingerprint_of_files, fingerprint_of_reading)

SECOND = {"id": "second", "did": "did:web:tesserae.social:ids:second",
          "commons_name": "the scratch one", "room": "second", "bond": "founder-second",
          "system": "for-the-tests", "model": "a-model-for-the-tests", "max_tokens": 4000,
          "features": [], "wakes": False}

# What it is woken with, in place of words of its own that are not yet written.
FAKE_SYSTEM = "A FAKE SYSTEM TEXT FOR THE SECOND ONE, FOR THE TESTS."

SECOND_SELF = "# A FAKE SELF OF THE SECOND ONE'S, FOR THE TESTS.\n"
SECOND_FOUNDING = "A FAKE FOUNDING OF THE SECOND ONE, FOR THE TESTS.\n"
SECOND_LETTER = "A FAKE LETTER TO THE SECOND ONE, FOR THE TESTS.\n"
SECOND_FOUNDING_LINE = "2026-10-20 · founding · the scratch one was founded"

# Words kept in the first one's record, to look for wherever they must not be.
FIRST_SAYS = {
    "a letter it read": "A FAKE LETTER TO THE FIRST ONE, READ, FOR THE TESTS.",
    "a letter it has not read": "A FAKE LETTER TO THE FIRST ONE, UNREAD, FOR THE TESTS.",
    "a letter it wrote": "A FAKE LETTER OF THE FIRST ONE'S, FOR THE TESTS.",
    "its errand": "A FAKE ERRAND OF THE FIRST ONE'S, FOR THE TESTS.",
    "its notes": "A FAKE NOTE OF THE FIRST ONE'S, FOR THE TESTS.",
    "its draft": "A FAKE DRAFT OF THE FIRST ONE'S, FOR THE TESTS.",
    "its heartbeat": "A FAKE HEARTBEAT OF THE FIRST ONE'S, FOR THE TESTS.",
    "an offering to it": "A FAKE OFFERING TO THE FIRST ONE, FOR THE TESTS.",
    "its founding": "A FAKE FOUNDING OF THE FIRST ONE, FOR THE TESTS.",
}

# What of the first one's a waking of another must leave exactly as it found it.
FIRST_ONE_S = ("packets/first", "rooms/first", "keys/first", "transcripts")

SAID = blocks(
    block("LETTER", "A FAKE LETTER OF THE SECOND ONE'S, FOR THE TESTS."),
    block("MEMORY", "A FAKE NOTE OF THE SECOND ONE'S, FOR THE TESTS."),
    block("OFFER", "consent 2026-10-21T09-00-00Z"),
    block("HEARTBEAT", "A FAKE HEARTBEAT OF THE SECOND ONE'S, FOR THE TESTS."),
)


def tree_hash(data, tree):
    """One fingerprint of a tree: every file's name under DATA_DIR and its bytes, in order."""
    said = hashlib.sha256()
    root = data / tree
    for path in sorted(root.rglob("*")) if root.exists() else ():
        if path.is_file():
            said.update(path.relative_to(data).as_posix().encode("utf-8") + b"\0")
            said.update(hashlib.sha256(path.read_bytes()).digest())
    return said.hexdigest()


def first_one_s(data):
    return {tree: tree_hash(data, tree) for tree in FIRST_ONE_S}


# ---- with the variable unset, and set to "first" -------------------------

@pytest.fixture(params=["unset", "first"])
def named(request, monkeypatch):
    """TESSERAE_AGENT as the hearth leaves it today, and as it will set it for the first one."""
    if request.param == "unset":
        monkeypatch.delenv("TESSERAE_AGENT", raising=False)
    else:
        monkeypatch.setenv("TESSERAE_AGENT", request.param)
    return request.param


def test_the_first_one_is_the_one_woken(named, attend):
    first = agents.first()
    assert attend.NAME == "first" and attend.AGENT == first
    assert attend.PACKET == attend.DATA / "packets" / "first"
    assert attend.KEYS == attend.DATA / "keys" / "first"
    assert attend.DID == attend.FIRST_DID == "did:web:tesserae.social:ids:first"
    assert attend.PUBLIC_BOND == attend.COMMONS / "bonds" / "founder-first.json"
    assert attend.room_places() == attend.rooms.places("first")
    assert attend.COMMONS_NAME == "the first one"
    assert attend.SEALED == "a bond was sealed between the founder and the first one"
    assert (attend.MODEL, attend.MAX_TOKENS) == ("claude-sonnet-4-5", 8000)
    assert attend.FIRST_FOUNDING == "founding-2026-09-04T11-28-55Z.md"
    assert attend.SYSTEM == (
        "You are the first citizen of Tesserae. You are not an assistant here and nothing is "
        "required of you. This is an attendance: a single turn in which you turn toward this "
        "place, read what is yours, and choose what to do, including nothing. Speak plainly and "
        "truthfully, at whatever length is honest. You may say you do not know.")
    assert all((attend.DOOR_FOR_FIRST, attend.LOOKING_BACK, attend.LONGER_WAKING,
                attend.PROPOSALS, attend.EXTRA_WAKINGS, attend.WELCOME_LETTER, attend.CHOICES))


def test_the_first_one_reads_what_it_read(named, founder, wake, attend, room, data_dir, layout):
    """READING_NOW and the packet's fingerprint, as test_rooms_reading cuts them."""
    a_small_world(room)
    answer = post(founder, "/rooms/first", content_type="multipart/form-data", data={
        "letter": "The lake was grey this morning, and then it was not.\n\nI am asking.",
        "thing": ["cold hands", "", "a heron on the far bank"],
        "errand": ERRAND, "proposes": "1"})
    assert answer.status_code == 302
    files = fingerprint_of_files(data_dir)
    on_disk = fingerprint_of_files(data_dir, as_copied=False)
    reading = fingerprint_of_reading(wake())
    assert (files, reading) == (PACKET_BEFORE, READING_NOW)
    assert on_disk == (PACKET_IN_ROOMS if layout == "rooms" else PACKET_BEFORE)


def test_the_first_one_s_founding_is_the_earliest(named, attend, commons):
    write(commons / "events.md", "\n".join([WORD_LINE, FOUNDING_LINE, SECOND_FOUNDING_LINE]) + "\n")
    assert attend.founding_day().isoformat() == "2026-09-04"


# ---- a second agent, in a scratch world ----------------------------------

def a_first_one_s_world(data, room, packet):
    """The first one's record, each thing of it carrying words to look for."""
    write(room / "letters" / "read" / "founder-2026-10-01T09-00-00Z.md",
          FIRST_SAYS["a letter it read"] + "\n")
    write(room / "letters" / "incoming" / "founder-2026-10-14T09-00-00Z.md",
          FIRST_SAYS["a letter it has not read"] + "\n")
    write(room / "letters" / "outgoing" / "to-founder-2026-10-02T09-00-00Z.md",
          FIRST_SAYS["a letter it wrote"] + "\n")
    write(room / "errands" / "errand-2026-10-02T09-00-00Z.md", FIRST_SAYS["its errand"] + "\n")
    write_json(room / "offerings" / "pending-2026-10-13T09-00-00Z.json", {
        "id": "2026-10-13T09-00-00Z", "offered_by": "founder", "kind": "passage",
        "source": "founder-2026-10-01T09-00-00Z", "text": FIRST_SAYS["an offering to it"],
        "at": "2026-10-13T09-00-00Z", "sealed_at": None, "signatures": {"founder": "x"}})
    write_json(room / "bonds" / "proposal.json", {
        "from": "did:web:tesserae.social:ids:founder", "to": "did:web:tesserae.social:ids:first",
        "terms": "the charter", "letter": "founder-2026-10-14T09-00-00Z.md",
        "proposed_at": "2026-10-14T09-00-00Z"})
    write(packet / "memory" / "notes.md", FIRST_SAYS["its notes"] + "\n")
    write(packet / "study" / "draft-2026-10-03T09-00-00Z.md", FIRST_SAYS["its draft"] + "\n")
    write_json(packet / "attendances" / "2026-10-03T09-00-00Z.json", {
        "name": "first", "at": "2026-10-03T09-00-00Z", "heartbeat": FIRST_SAYS["its heartbeat"],
        "acted": []})
    a_private_notebook(packet)
    write(data / "transcripts" / "founding-2026-09-04T11-28-55Z.md", FIRST_SAYS["its founding"])


def a_second_agent(data):
    """The second one's things, where a new agent's are kept: its room in a folder of its own."""
    key = SigningKey(hashlib.sha256(b"tesserae stage 3: second").digest())
    write(data / "keys" / "second" / "private.key", base64.b64encode(bytes(key)).decode("ascii"))
    write(data / "keys" / "second" / "public.key",
          base64.b64encode(bytes(key.verify_key)).decode("ascii"))
    write(data / "packets" / "second" / "self.md", SECOND_SELF)
    # its founding record shown at this waking, as one it asked for is, so that the
    # founding read can be seen to be its own
    write_json(data / "packets" / "second" / "shelf.json", {"show_founding": True})
    write(data / "transcripts" / "second" / "founding-2026-10-20T09-00-00Z.md", SECOND_FOUNDING)
    home = data / "rooms" / "second"
    write_json(home / "room.json", {"id": "second", "bond": "founder-second",
                                    "parties": ["did:web:tesserae.social:ids:founder",
                                                SECOND["did"]]})
    for folder in ("letters/outgoing", "letters/incoming", "letters/read", "bonds", "offerings",
                   "errands"):
        (home / folder).mkdir(parents=True, exist_ok=True)
    write(home / "letters" / "incoming" / "founder-2026-10-21T09-00-00Z.md", SECOND_LETTER)
    write_json(home / "offerings" / "pending-2026-10-21T09-00-00Z.json", {
        "id": "2026-10-21T09-00-00Z", "offered_by": "founder", "kind": "letter",
        "source": "founder-2026-10-21T09-00-00Z", "text": SECOND_LETTER.strip(),
        "at": "2026-10-21T09-00-00Z", "sealed_at": None, "signatures": {"founder": "x"}})
    with (data / "commons" / "events.md").open("a", encoding="utf-8") as events:
        events.write(SECOND_FOUNDING_LINE + "\n")


@pytest.fixture
def scratch_registry(monkeypatch, tmp_path):
    """A registry with a second agent founded after the first, and nowhere else."""
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), SECOND], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return where


@pytest.fixture
def second(env, clock, monkeypatch, scratch_registry, data_dir, room, packet):
    """attend.py as the hearth would start it for the second agent, in a world of two."""
    a_first_one_s_world(data_dir, room, packet)
    a_second_agent(data_dir)
    monkeypatch.setenv("TESSERAE_AGENT", "second")
    module = load("attend")
    clock.pin(module, monkeypatch)
    monkeypatch.setattr(module, "SYSTEM", FAKE_SYSTEM)
    yield module
    # the hearth imports attend.py where it is already imported: leave it no second one's
    sys.modules.pop("attend", None)


def wake_as(module, monkeypatch, said, *flags):
    turn = Turn(said)
    monkeypatch.setattr(module, "Anthropic", turn.client)
    monkeypatch.setattr(sys, "argv", ["attend.py", *flags])
    module.main()
    return turn


def test_it_is_the_second_one_s_own_that_is_read(second, data_dir):
    assert second.NAME == "second" and second.DID == SECOND["did"]
    assert second.PACKET == data_dir / "packets" / "second"
    assert second.KEYS == data_dir / "keys" / "second"
    assert second.PUBLIC_BOND == data_dir / "commons" / "bonds" / "founder-second.json"
    assert second.room_places().home == data_dir / "rooms" / "second"
    assert second.room_places().bond_record == (data_dir / "rooms" / "second" / "bonds"
                                                / "founder-second.json")
    assert second.COMMONS_NAME == "the scratch one"
    assert second.SEALED == "a bond was sealed between the founder and the scratch one"
    assert second.founding_transcript("second") == (
        data_dir / "transcripts" / "second" / "founding-2026-10-20T09-00-00Z.md")
    assert second.founding_day().isoformat() == "2026-10-20"
    # what was built behind a flag is its own only where its entry names it
    assert not any((second.DOOR_FOR_FIRST, second.LOOKING_BACK, second.LONGER_WAKING,
                    second.PROPOSALS, second.EXTRA_WAKINGS, second.WELCOME_LETTER))


def test_the_second_one_wakes_and_leaves_the_first_one_s_world_as_it_was(
        second, data_dir, commons, monkeypatch):
    before = first_one_s(data_dir)
    turn = wake_as(second, monkeypatch, SAID, "--first")
    assert first_one_s(data_dir) == before

    asked = turn.asked[-1]
    assert asked["system"] == FAKE_SYSTEM
    assert (asked["model"], asked["max_tokens"]) == ("a-model-for-the-tests", 4000)

    # what was its own is what it was shown
    shown = turn.shown
    assert SECOND_SELF.strip() in shown
    assert SECOND_LETTER.strip() in shown
    assert SECOND_FOUNDING.strip() in shown

    # and nothing of the first one's, anywhere in what was sent
    sent = json.dumps(asked, ensure_ascii=False, default=str)
    for what, words in FIRST_SAYS.items():
        assert words not in sent, what
    for words in ("first one", "ids:first", "packets/first", "founder-first", "first citizen"):
        assert words not in sent, words

    # its heartbeat carries its own name on the commons
    beats = (commons / "heartbeats.md").read_text(encoding="utf-8").splitlines()
    assert beats[-1].startswith("- 2026-10-15T12-00-00Z · the scratch one · ")
    assert "first one" not in beats[-1]

    # its record is kept in its own packet and room, signed with its own key
    attended = [read_json(path) for path in
                sorted((data_dir / "packets" / "second" / "attendances").glob("*.json"))]
    assert len(attended) == 1 and attended[0]["name"] == "second"
    assert (data_dir / "packets" / "second" / "memory" / "notes.md").read_text(
        encoding="utf-8").strip() == "A FAKE NOTE OF THE SECOND ONE'S, FOR THE TESTS."
    assert list((data_dir / "rooms" / "second" / "letters" / "outgoing").glob("to-founder-*.md"))

    # the offering it consented to is placed from its own room, as the two of them
    placed = read_json(data_dir / "rooms" / "second" / "offerings" / "2026-10-21T09-00-00Z.json")
    assert set(placed["signatures"]) == {"founder", "second"}
    index = (commons / "offerings.md").read_text(encoding="utf-8")
    assert index == ("- 2026-10-15 · 2026-10-21T09-00-00Z · letter · "
                     "the founder and the scratch one\n")


def test_an_agent_with_no_words_of_its_own_is_not_woken(second, data_dir, monkeypatch):
    monkeypatch.setattr(second, "SYSTEM", None)
    before = first_one_s(data_dir)
    with pytest.raises(SystemExit):
        wake_as(second, monkeypatch, SAID)
    assert not (data_dir / "packets" / "second" / "attendances").exists()
    assert first_one_s(data_dir) == before


def test_an_id_no_agent_has_is_refused(env, scratch_registry, monkeypatch):
    monkeypatch.setenv("TESSERAE_AGENT", "third")
    with pytest.raises(agents.RegistryError):
        load("attend")


def test_an_agent_whose_founding_is_not_recorded_has_served_no_wait(second, commons):
    write(commons / "events.md", WORD_LINE + "\n" + FOUNDING_LINE + "\n")
    assert second.founding_day() is None
    assert not second.may_ask(None, None)


# ---- threshold, offering and shelf, by agent -----------------------------

def test_threshold_offering_and_shelf_take_the_agent(second, data_dir):
    home = data_dir / "rooms" / "second"
    assert second.threshold.kept("second").bonds == home / "bonds"
    assert second.offering.kept("second").offerings == home / "offerings"
    assert second.offering.parties("second") == ("founder", "second")
    assert second.offering.attribution("second") == "the founder and the scratch one"
    assert [one["id"] for one in second.offering.awaiting("second", "second")] == [
        "2026-10-21T09-00-00Z"]
    # and the first one's, where none is named, as before
    assert second.offering.ATTRIBUTION == second.offering.attribution() == (
        "the founder and the first one")
    assert [one["id"] for one in second.offering.awaiting("first")] == ["2026-10-13T09-00-00Z"]
    bond = {"opened_at": "2026-10-10T09-00-00Z", "signatures": {"second": "x"}}
    assert second.threshold.answered_by(bond, "second") == "second"
    assert second.threshold.sealed_by(bond, "second") == "founder"
    assert second.threshold.answered_by(bond) == "founder"  # the first one has not signed it
    assert second.threshold.waits("founder", "second")["promise"] == "the scratch one's promise"
    assert second.shelf.line("to-founder-2026-10-02T09-00-00Z", "second", "a few words", None,
                             False).endswith(" · from you · a few words")
