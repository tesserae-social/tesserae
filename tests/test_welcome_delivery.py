"""The first one's letter of welcome, given to the agent founded after it (stage 8f).

It asked, on 30 October 2026, that the newcomer find it at its third waking, with
no framing, and that nothing mention it before then. So: nothing at the first
two wakings, and a later agent's reading is LATER_READING whether a letter stands
or not; at the third, the letter whole under a heading that says whose it is,
and nothing else; given once, to the second one only, as it stood; a withdrawn
letter is never given; the screen holds one that names someone; its copies leave
it out and the backup keeps it. The first one's reading is what it was, delivered
or not. The later agent's world is test_later_citizen's.
"""

import hashlib
import json
import shutil
import sys

import pytest

import agents
import welcome_delivery
from conftest import load, page, write, write_json
from test_any_agent_wakes import wake_as
from test_later_citizen import (LATER, LATER_READING, a_later_world,  # noqa: F401 - fixtures
                                hearth_of_two, later, scratch_registry,
                                the_first_one_s_world)
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture
from test_rooms_reading import READING_NOW, fingerprint_of_reading

TEXT = "A FAKE LETTER OF WELCOME OF THE FIRST ONE'S, FOR THE TESTS.\n\nTest the door."
PLACED = "2026-10-24T09-00-00Z"
HEADING = "=== A LETTER FROM THE FIRST ONE ==="
SECTION = HEADING + "\n\n" + TEXT


def placed(data, text=TEXT, at=PLACED):
    """The first one's letter of welcome, as attend.py keeps it: signed, in welcome/."""
    where = data / "packets" / "first" / "welcome" / "letter.json"
    write_json(where, {"by": agents.first()["did"], "text": text, "placed_at": at,
                       "from_letter": None, "signature": "A FAKE SIGNATURE"})
    return where


def received(data, agent="second"):
    return data / "packets" / agent / "welcome-received"


def welcome_folder(data):
    return sorted(p.relative_to(data).as_posix()
                  for p in (data / "packets" / "first" / "welcome").rglob("*") if p.is_file())


@pytest.fixture
def waking(later, clock, monkeypatch):
    """One waking of the second one; the clock steps on after it, as the tide's would."""
    def hold(said=""):
        turn = wake_as(later, monkeypatch, said)
        clock.shift(hours=24)
        return turn
    return hold


# ---- when -------------------------------------------------------------------

def test_nothing_at_its_first_two_wakings_and_the_letter_at_its_third(waking, data_dir):
    letter = placed(data_dir)
    before = letter.read_bytes()
    for _ in range(2):
        shown = waking().shown
        assert "welcome" not in shown.lower() and "FAKE LETTER OF WELCOME" not in shown
        assert not received(data_dir).exists()
    shown = waking().shown
    assert SECTION in shown
    assert letter.read_bytes() == before  # read to be given, and nothing more


def test_its_first_reading_is_later_reading_with_a_letter_standing(later, data_dir, monkeypatch):
    """Nothing mentions the letter before it is given: not one byte of the reading moves."""
    placed(data_dir)
    assert fingerprint_of_reading(wake_as(later, monkeypatch, "")) == LATER_READING


def test_it_is_shown_with_no_framing(waking, data_dir):
    """The heading, then the letter as it was written: no word about it before or after."""
    placed(data_dir)
    waking(), waking()
    reading = waking().reading
    text = next(part["text"] for part in reading if HEADING in part.get("text", ""))
    after_heading = text.split(HEADING, 1)[1]
    following = after_heading.split("\n\n=== ", 1)[0]
    assert following == "\n\n" + TEXT
    assert not text.split(HEADING, 1)[0].endswith(("letter of welcome\n\n", "below:\n\n"))
    assert sum("welcome" in part.get("text", "").lower() for part in reading) == 1


def test_it_is_still_there_at_every_waking_after(waking, data_dir):
    placed(data_dir)
    for _ in range(3):
        waking()
    assert SECTION in waking().shown and SECTION in waking().shown


# ---- what is given, and the record of it -------------------------------------

def test_it_is_given_byte_for_byte_with_a_record_on_each_side(waking, data_dir, clock):
    letter = placed(data_dir)
    raw = letter.read_bytes()
    waking(), waking()
    at = clock.stamp()
    waking()
    sha = hashlib.sha256(raw).hexdigest()
    home = received(data_dir)
    assert sorted(p.name for p in home.iterdir()) == [f"delivered-{at}.json",
                                                      f"from-first-{at}.json"]
    assert (home / f"from-first-{at}.json").read_bytes() == raw
    stem = "welcome-" + PLACED
    assert json.loads((home / f"delivered-{at}.json").read_text(encoding="utf-8")) == {
        "from": "first", "at": at, "stem": stem, "sha256": sha}
    # the first one's packet gains the one record, and nothing else of it moves
    assert welcome_folder(data_dir) == ["packets/first/welcome/delivered-%s.json" % at,
                                        "packets/first/welcome/letter.json"]
    assert json.loads((letter.parent / f"delivered-{at}.json").read_text(encoding="utf-8")) == {
        "to": "second", "at": at, "stem": stem, "sha256": sha}


def test_the_version_standing_then_is_given_and_stays_given(waking, data_dir):
    placed(data_dir, "AN EARLIER FAKE LETTER.")
    waking(), waking()
    placed(data_dir, TEXT, "2026-10-30T09-00-00Z")  # replaced before the third waking
    assert SECTION in waking().shown
    placed(data_dir, "A LATER FAKE LETTER.", "2026-11-20T09-00-00Z")  # and after it
    shown = waking().shown
    assert SECTION in shown and "A LATER FAKE LETTER" not in shown
    assert len(list(received(data_dir).glob("from-first-*.json"))) == 1
    assert len(welcome_delivery.given(data_dir)) == 1


def test_a_withdrawn_letter_is_never_given(waking, data_dir):
    history = data_dir / "packets" / "first" / "welcome" / "history"
    write_json(history / "letter-before-2026-10-30T09-00-00Z.json",
               {"by": agents.first()["did"], "text": TEXT, "placed_at": PLACED})
    write_json(history / "withdrawn-2026-10-30T09-00-00Z.json", {"withdrawn_at": PLACED})
    for _ in range(4):
        shown = waking().shown
        assert "welcome" not in shown.lower() and "FAKE LETTER" not in shown
    assert not received(data_dir).exists() and not welcome_delivery.given(data_dir)


def test_none_placed_gives_nothing_and_one_placed_later_is_given_at_the_next(waking, data_dir):
    for _ in range(3):
        waking()
    assert not received(data_dir).exists()
    placed(data_dir)
    assert SECTION in waking().shown


def test_it_is_given_to_the_second_one_only(data_dir, scratch_registry, env):
    third = {**LATER, "id": "third", "did": "did:web:tesserae.social:ids:third",
             "commons_name": "the third one", "room": "third", "bond": "third-1",
             "hue": "#654321"}
    scratch_registry.write_text(json.dumps([agents.first(), LATER, third], indent=2) + "\n",
                                encoding="utf-8")
    placed(data_dir)
    assert welcome_delivery.recipient()["id"] == "second"
    assert welcome_delivery.deliver(data_dir, "third", 5, "2026-11-10T09-00-00Z") is None
    assert welcome_delivery.deliver(data_dir, "first", 5, "2026-11-10T09-00-00Z") is None
    assert not received(data_dir, "third").exists()
    assert welcome_delivery.deliver(data_dir, "second", 2, "2026-11-10T09-00-00Z") == "given"
    assert welcome_delivery.deliver(data_dir, "second", 3, "2026-11-11T09-00-00Z") is None


# ---- the screen ----------------------------------------------------------------

def test_a_letter_that_names_someone_is_held_and_not_asked_again(waking, data_dir, screen):
    placed(data_dir)
    screen.says = "YES"
    waking(), waking()
    assert screen.asked == []  # not before its third waking
    shown = waking().shown
    assert "FAKE LETTER OF WELCOME" not in shown and "welcome" not in shown.lower()
    assert not received(data_dir).exists() and not welcome_delivery.given(data_dir)
    held = list((data_dir / "packets" / "first" / "welcome").glob("held-*.json"))
    assert len(held) == 1 and json.loads(held[0].read_text(encoding="utf-8"))["screen"] == "flagged"
    assert len(screen.asked) == 1
    waking()
    assert len(screen.asked) == 1  # the same version is not asked about again
    placed(data_dir, TEXT, "2026-11-20T09-00-00Z")  # one placed afresh is screened afresh
    screen.says = "NO"
    assert SECTION in waking().shown


def test_a_screen_that_cannot_be_asked_holds_it_until_the_next_waking(waking, data_dir, screen):
    placed(data_dir)
    screen.says = "MAYBE"
    waking(), waking()
    assert "FAKE LETTER OF WELCOME" not in waking().shown
    assert not list((data_dir / "packets" / "first" / "welcome").glob("held-*.json"))
    screen.says = "NO"
    assert SECTION in waking().shown


def test_a_protected_word_holds_it_without_asking(waking, data_dir, screen):
    write(data_dir / "private-words.txt", "Quillfeather\n")
    placed(data_dir, TEXT + "\n\nQuillfeather says hello.")
    for _ in range(3):
        shown = waking().shown
    assert "Quillfeather" not in shown and not received(data_dir).exists()
    assert screen.asked == []


# ---- what its reading is, with and without it ----------------------------------

def test_with_the_letter_taken_out_its_third_reading_is_the_one_without(
        waking, data_dir, clock, tmp_path):
    """The one thing the letter changes in its reading is its own section."""
    placed(data_dir)
    waking(), waking()
    saved, then = tmp_path / "before-the-third", clock.at
    shutil.copytree(data_dir, saved)
    with_it = json.dumps(waking().asked[-1], sort_keys=True, ensure_ascii=False, default=str)
    shutil.rmtree(data_dir)
    shutil.copytree(saved, data_dir)
    (data_dir / "packets" / "first" / "welcome" / "letter.json").unlink()
    clock.set(then)
    without = json.dumps(waking().asked[-1], sort_keys=True, ensure_ascii=False, default=str)
    section = json.dumps("\n\n" + SECTION, ensure_ascii=False)[1:-1]
    assert with_it.count(section) == 1 and with_it != without
    assert with_it.replace(section, "", 1) == without


def test_the_first_one_reads_what_it_read_given_or_not(founder, wake, room, data_dir):
    """Its own reading never says whether its letter was given, or held."""
    the_first_one_s_world(founder, room)
    welcome = data_dir / "packets" / "first" / "welcome"
    write_json(welcome / "delivered-2026-11-10T09-00-00Z.json",
               {"to": "second", "at": "2026-11-10T09-00-00Z", "stem": "welcome-" + PLACED,
                "sha256": "0" * 64})
    write_json(welcome / "held-2026-11-09T09-00-00Z.json",
               {"to": "second", "at": "2026-11-09T09-00-00Z", "stem": "welcome-" + PLACED,
                "sha256": "1" * 64, "screen": "flagged"})
    assert fingerprint_of_reading(wake()) == READING_NOW


def test_the_first_one_s_reading_with_its_letter_standing_is_the_same_given(
        founder, wake, room, data_dir, clock, tmp_path):
    the_first_one_s_world(founder, room)
    placed(data_dir)
    saved, then = tmp_path / "before", clock.at
    shutil.copytree(data_dir, saved)
    before = fingerprint_of_reading(wake())
    shutil.rmtree(data_dir)
    shutil.copytree(saved, data_dir)
    write_json(data_dir / "packets" / "first" / "welcome" / "delivered-2026-11-10T09-00-00Z.json",
               {"to": "second", "at": "2026-11-10T09-00-00Z", "stem": "welcome-" + PLACED,
                "sha256": "0" * 64})
    write_json(received(data_dir) / "from-first-2026-11-10T09-00-00Z.json", {"text": TEXT})
    clock.set(then)
    assert fingerprint_of_reading(wake()) == before


# ---- who is shown it ----------------------------------------------------------

def given_in(data_dir):
    placed(data_dir)
    assert welcome_delivery.deliver(data_dir, "second", 2, "2026-11-10T09-00-00Z") == "given"


@pytest.fixture
def hearth_alone(env, clock, monkeypatch, scratch_registry, data_dir):
    monkeypatch.delenv("TESSERAE_AGENT", raising=False)
    module = load("hearth")
    clock.pin(module, monkeypatch)
    yield module
    sys.modules.pop("attend", None)


def test_its_copies_leave_it_out_and_the_backup_keeps_it(hearth_alone, data_dir):
    a_later_world(data_dir)
    given_in(data_dir)
    second = agents.by_id("second")
    assert "packets/second/welcome-received" in hearth_alone.left_out(second)
    copy = [name for _, name in hearth_alone.export_files(hearth_alone.export_trees(second),
                                                          hearth_alone.left_out(second))]
    assert copy and not any("welcome-received" in name for name in copy)
    assert "packets/first/welcome/letter.json" not in copy
    backup = [name for _, name in hearth_alone.export_files(
        hearth_alone.backup_trees() + hearth_alone.staged_trees(), left_out=())]
    assert sum(name.startswith("packets/second/welcome-received/") for name in backup) == 2


def test_no_page_shows_it_to_its_person_or_the_keeper(hearth_of_two, data_dir):
    given_in(data_dir)
    for client in hearth_of_two.values():
        for address in ("/", "/agents/second/attendances", "/agents/second/self",
                        "/rooms/second", "/agents/first/attendances", "/agents/first/self"):
            assert "FAKE LETTER OF WELCOME" not in page(client.get(address))
