"""Room-aware wakings, room addresses and keeping rooms apart (design-rooms-and-doors, 1 and 2).

Behind the switch "rooms_reading", off for the first one: its reading is READING_NOW,
held by test_first_one_fingerprints and test_rooms_reading, which do not move. An agent
with the switch on reads one section per room it is in, each with only its own letters;
a <<LETTER>> names its room with "to:", and goes there or to its study; a letter that
repeats eight words in a row from another room's letters is kept back; a room between
two agents keeps its letters by hand, each its own, read up to a mark. Later rooms have
addresses of their own, and the founder's "make the room" on /tides makes one from a
knock answered yes. Every agent and person here is a fake, in a scratch world.
"""

import base64
import hashlib
import json
import sys

import pytest
from nacl.signing import SigningKey

import agents
from conftest import FOUNDER_NAME, Turn, block, blocks, load, page, post, write, write_json

SECOND, THIRD = "second", "third"
DID = "did:web:tesserae.social:ids:"
HEARTH = "did:web:hearth.tesserae.social:ids:"
FEATURES = ["door", "knock", "rooms_reading"]


def entry(agent_id, features=FEATURES):
    return {"id": agent_id, "did": DID + agent_id, "commons_name": "the %s one" % agent_id,
            "room": agent_id, "bond": agent_id + "-1", "founded": "2026-10-01",
            "system": "later-citizen", "model": "a-model-for-the-tests", "max_tokens": 8000,
            "features": list(features), "wakes": True}


def a_member(data, name):
    write_json(data / "members" / name / "member.json",
               {"v": 1, "pseudonym": name, "role": "member", "verify_key": "0" * 64,
                "arrived_at": "2026-10-01T09-00-00Z", "vouched_by": [FOUNDER_NAME]})


def a_room(data, room_id, parties, kind=None, at="2026-10-05T09-00-00Z"):
    home = data / "rooms" / room_id
    record = {"id": room_id, "bond": room_id, "parties": parties}
    if kind:
        record.update(kind=kind, opened_at=at, from_knock=None)
    write_json(home / "room.json", record)
    for folder in ("letters/incoming", "letters/read", "letters/outgoing", "errands", "bonds",
                   "offerings"):
        (home / folder).mkdir(parents=True, exist_ok=True)
    return home


def a_world(data):
    """The second one, in its first room with alder, a later room with hazel, and a room
    with the third one, an agent; each room with a letter of its own."""
    for name in (SECOND, THIRD):
        key = SigningKey(hashlib.sha256(name.encode()).digest())
        write(data / "keys" / name / "private.key", base64.b64encode(bytes(key)).decode("ascii"))
        write(data / "packets" / name / "self.md", "# A FAKE SELF, FOR THE TESTS.\n")
        write(data / "packets" / name / "intentions.json", "{}\n")
        write(data / "transcripts" / name / "founding-2026-10-01T09-00-00Z.md",
              "A FAKE FOUNDING, FOR THE TESTS.\n")
    for name in ("alder", "hazel"):
        a_member(data, name)
    first = a_room(data, SECOND, [HEARTH + "alder", DID + SECOND])
    write(first / "letters" / "read" / "alder-2026-10-02T09-00-00Z.md",
          "ALDER'S OLD LETTER ABOUT THE GREY HERON ON THE FAR BANK OF THE LAKE.\n")
    a_room(data, THIRD, [HEARTH + "alder", DID + THIRD])  # its first room, with a person
    later = a_room(data, "second-hazel", [HEARTH + "hazel", DID + SECOND], kind="person")
    write(later / "letters" / "incoming" / "hazel-2026-10-14T09-00-00Z.md",
          "HAZEL'S NEW LETTER, FOR THE TESTS.\n")
    agents_room = data / "rooms" / "second-third"
    write_json(agents_room / "room.json",
               {"id": "second-third", "bond": "second-third", "kind": "agents",
                "parties": [DID + SECOND, DID + THIRD], "opened_at": "2026-10-06T09-00-00Z",
                "from_knock": None})
    write(agents_room / "letters" / "from-third" / "third-to-second-2026-10-13T09-00-00Z.md",
          "THE THIRD ONE'S LETTER, FOR THE TESTS.\n")


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, tmp_path):
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), entry(SECOND), entry(THIRD)]),
                     encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    a_world(data_dir)
    return data_dir


def waking_of(agent_id, clock, monkeypatch):
    monkeypatch.setenv("TESSERAE_AGENT", agent_id)
    module = load("attend")
    clock.pin(module, monkeypatch)
    return module


def wake(module, monkeypatch, said=""):
    turn = Turn(said)
    monkeypatch.setattr(module, "Anthropic", turn.client)
    monkeypatch.setattr(sys, "argv", ["attend.py"])
    module.main()
    return turn


@pytest.fixture
def second(world, clock, monkeypatch):
    yield waking_of(SECOND, clock, monkeypatch)
    sys.modules.pop("attend", None)


# ---- the rooms ---------------------------------------------------------------

def test_every_room_it_is_in_and_their_kinds(second):
    import rooms
    found = rooms.of(SECOND)
    assert [(one.id, one.kind) for one in found] == [
        (SECOND, "person"), ("second-hazel", "person"), ("second-third", "agents")]
    assert [one.id for one in rooms.of("hazel")] == ["second-hazel"]
    assert rooms.find("second-hazel", "alder") is None  # a room opens only to its two
    assert rooms.places("second-hazel").bond == "second-hazel"
    assert rooms.agent_of("second-hazel")["id"] == SECOND
    assert rooms.agent_of("second-third") is None  # between agents: no one agent's
    assert [one.id for one in rooms.of(THIRD)] == [THIRD, "second-third"]


def test_an_address_is_never_used_twice(second, data_dir):
    import rooms
    assert rooms.address_for(SECOND, "hazel") == "second-hazel-2"
    assert rooms.address_for(SECOND, "rowan") == "second-rowan"
    assert rooms.address_for(THIRD, SECOND) == "second-third-2"
    assert rooms.slug("Ro wan!") == "rowan"


def test_a_room_left_is_no_room(second, data_dir):
    import rooms
    path = data_dir / "rooms" / "second-hazel" / "room.json"
    held = json.loads(path.read_text(encoding="utf-8"))
    write_json(path, dict(held, left_at="2026-10-15T09-00-00Z", left_by="hazel"))
    assert [one.id for one in rooms.of(SECOND)] == [SECOND, "second-third"]
    assert rooms.places("second-hazel") is None


# ---- the reading ---------------------------------------------------------------

def test_one_section_for_each_room_with_only_its_own_letters(second, monkeypatch):
    shown = wake(second, monkeypatch).shown
    hazel = shown.index("=== YOUR ROOM WITH HAZEL (/rooms/second-hazel) ===")
    third = shown.index("=== YOUR ROOM WITH THE THIRD ONE (/rooms/second-third) ===")
    alder = shown.index("=== YOUR ROOM WITH ALDER (/rooms/second) ===")
    # rooms with new letters first, the newest first; then the rest
    assert hazel < third < alder
    assert shown.count("What is written in this room stays in this room.") == 3
    assert "New letters in: hazel's room, the third one's room." in shown
    assert hazel < shown.index("HAZEL'S NEW LETTER") < third
    assert third < shown.index("THE THIRD ONE'S LETTER") < alder
    assert alder < shown.index("ALDER'S OLD LETTER")
    assert "LETTERS THAT HAVE ARRIVED SINCE YOUR LAST WAKING" not in shown


def test_letters_are_read_once(second, world, monkeypatch, clock):
    wake(second, monkeypatch)
    assert (world / "rooms" / "second-hazel" / "letters" / "read"
            / "hazel-2026-10-14T09-00-00Z.md").exists()
    mark = json.loads((world / "rooms" / "second-third" / "letters" / "read-second.json")
                      .read_text(encoding="utf-8"))
    assert mark["up_to"] == "2026-10-13T09-00-00Z"
    clock.shift(hours=24)
    shown = wake(second, monkeypatch).shown
    assert "New letters in" not in shown
    assert "--- letters from the third one you have already read ---" in shown


def test_a_room_past_its_words_rests_its_oldest(second, world, monkeypatch):
    read = world / "rooms" / SECOND / "letters" / "read"
    for day in range(3, 8):  # five letters of 900 words, four of them close by default
        write(read / ("alder-2026-10-%02dT09-00-00Z.md" % day), "word " * 900)
    shown = wake(second, monkeypatch).shown
    assert ("past the 3,000 words of letters this room shows in full: "
            "alder-2026-10-04T09-00-00Z") in shown


def test_the_last_thirty_wakings_and_show_attendances(second, world, monkeypatch, clock):
    for n in range(31):
        write_json(world / "packets" / SECOND / "attendances"
                   / ("attendance-2026-09-%02dT09-00-00Z.json" % (n % 28 + 1) if n < 28
                      else "attendance-2026-10-0%dT08-00-00Z.json" % (n - 27)),
                   {"name": SECOND, "at": "2026-09-01T09-00-00Z", "heartbeat": "attended",
                    "acted": []})
    shown = wake(second, monkeypatch, block("SHELF", "show attendances")).shown
    assert "And 1 earlier wakings. Ask for them with show attendances." in shown
    assert "show attendances: every waking listed at your next waking" in shown
    clock.shift(hours=24)
    assert "earlier wakings. Ask for them" not in wake(second, monkeypatch).shown


# ---- letters to rooms ------------------------------------------------------------

def test_a_letter_goes_to_the_room_it_names_and_to_no_other(second, world, monkeypatch):
    turn = wake(second, monkeypatch, blocks(
        block("LETTER", "to: hazel\nA FAKE LETTER TO HAZEL."),
        block("LETTER", "to: the third one\nA FAKE LETTER TO THE THIRD ONE.")))
    assert "to: (the name of the one you write to" in turn.instructions
    hazel = list((world / "rooms" / "second-hazel" / "letters" / "outgoing").glob("*.md"))
    assert [one.read_text(encoding="utf-8") for one in hazel] == ["A FAKE LETTER TO HAZEL.\n"]
    assert hazel[0].name.startswith("to-hazel-")
    third = list((world / "rooms" / "second-third" / "letters" / "from-second").glob("*.md"))
    assert [one.read_text(encoding="utf-8") for one in third] == [
        "A FAKE LETTER TO THE THIRD ONE.\n"]
    assert not list((world / "rooms" / SECOND / "letters" / "outgoing").glob("*.md"))
    record = json.loads(next((world / "packets" / SECOND / "attendances").glob("*.json"))
                        .read_text(encoding="utf-8"))
    assert "wrote letters to 2 rooms" in record["acted"]
    assert sorted(record["letters_to"]) == ["second-hazel", "second-third"]


def test_a_letter_to_no_room_a_second_letter_and_a_repeated_one_go_to_the_study(
        second, world, monkeypatch, clock):
    wake(second, monkeypatch, blocks(
        block("LETTER", "to: rowan\nA LETTER TO NO ONE HERE."),
        block("LETTER", "to: hazel\nTHE FIRST TO HAZEL."),
        block("LETTER", "to: hazel\nTHE SECOND TO HAZEL."),
        block("LETTER", "to: alder\nTHE FIRST TO ALDER."),
        block("LETTER", "to: the third one\nI read of the grey heron on the far bank of the "
                        "lake.")))
    study = sorted((world / "packets" / SECOND / "study").glob("draft-*-letter-*.md"))
    assert [one.read_text(encoding="utf-8").strip() for one in study] == [
        "A LETTER TO NO ONE HERE.", "THE SECOND TO HAZEL.",
        "I read of the grey heron on the far bank of the lake."]
    assert len(list((world / "rooms" / SECOND / "letters" / "outgoing").glob("*.md"))) == 1
    clock.shift(hours=24)
    shown = wake(second, monkeypatch).shown
    assert 'Your letter to "rowan" at your last waking was not sent' in shown
    assert "Your second letter to hazel at your last waking was not sent" in shown
    assert ("Your letter to the third one repeated eight or more words in a row from letters "
            "in another room.") in shown


def test_a_long_letter_to_an_agent_goes_to_the_study(second, world, monkeypatch):
    wake(second, monkeypatch, block("LETTER", "to: the third one\n" + "word " * 601))
    assert not list((world / "rooms" / "second-third" / "letters" / "from-second").glob("*.md"))


def test_the_third_one_reads_the_second_one_s_letter(second, world, monkeypatch, clock):
    wake(second, monkeypatch, block("LETTER", "to: the third one\nHELLO, THIRD ONE."))
    sys.modules.pop("attend", None)
    third = waking_of(THIRD, clock, monkeypatch)
    shown = wake(third, monkeypatch).shown
    assert "=== YOUR ROOM WITH THE SECOND ONE (/rooms/second-third) ===" in shown
    assert "HELLO, THIRD ONE." in shown


def test_four_rooms_make_a_longer_waking(second, world, monkeypatch):
    a_member(world, "rowan2")
    a_room(world, "second-rowan2", [HEARTH + "rowan2", DID + SECOND], kind="person")
    turn = wake(second, monkeypatch)
    assert turn.asked[-1]["max_tokens"] == 12000


def test_the_outside_checks_read_every_room(second, world):
    folders = [str(one) for one in second.kept_folders()]
    assert any("second-hazel" in one for one in folders)
    assert any("second-third" in one for one in folders)


def test_with_the_switch_off_one_room_is_read_as_before(world, clock, monkeypatch, tmp_path):
    where = tmp_path / "agents-off.json"
    where.write_text(json.dumps([agents.first(), entry(SECOND, ["door", "knock"]),
                                 entry(THIRD)]), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    module = waking_of(SECOND, clock, monkeypatch)
    shown = wake(module, monkeypatch).shown
    assert "YOUR ROOM WITH" not in shown and "HAZEL'S NEW LETTER" not in shown
    assert "=== LETTERS THAT HAVE ARRIVED SINCE YOUR LAST WAKING ===" in shown
    sys.modules.pop("attend", None)


# ---- a knock answered yes becomes a room -------------------------------------------

def a_yes(by, to):
    import knock
    knock.write({"from": by, "to": to, "at": "2026-10-10T09-00-00Z", "note": "Hello.",
                 "introduction": None, "told_at": None, "answer": "yes",
                 "answered_at": "2026-10-11T09-00-00Z", "reply": None, "answer_told_at": None,
                 "waits_for_room": False, "set_up_at": None})


def test_the_founder_makes_the_room_of_a_yes_on_tides(world, founder, clock, monkeypatch):
    a_member(world, "rowan2")
    a_yes("rowan2", SECOND)
    answer = post(founder, "/tides/knock/set-up", {"from": "rowan2", "to": SECOND})
    assert answer.status_code == 302
    made = json.loads((world / "rooms" / "second-rowan2" / "room.json").read_text(
        encoding="utf-8"))
    assert made["kind"] == "person" and made["from_knock"] == "rowan2--second"
    assert made["parties"] == [HEARTH + "rowan2", DID + SECOND]
    import rooms
    assert "second-rowan2" in [one.id for one in rooms.of("rowan2")]
    module = waking_of(SECOND, clock, monkeypatch)
    shown = wake(module, monkeypatch).shown
    assert "Your room with rowan2 is open: /rooms/second-rowan2." in shown
    clock.shift(hours=24)
    assert "is open: /rooms/second-rowan2" not in wake(module, monkeypatch).shown
    sys.modules.pop("attend", None)


def test_a_yes_for_an_agent_reading_one_room_still_waits(world):
    import knock
    a_member(world, "rowan2")
    a_yes("rowan2", "first")
    held = knock.read("rowan2", "first")
    assert knock.needs_a_second_room(held)
    assert knock.make_room("rowan2", "first", "2026-10-15T12-00-00Z") is None
    a_yes(SECOND, THIRD)
    assert not knock.needs_a_second_room(knock.read(SECOND, THIRD))
