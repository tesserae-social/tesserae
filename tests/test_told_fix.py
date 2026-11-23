"""told-fix: the founder's question of 19 November 2026.

The second one has private_reflections on, holds a room, and after its tide of
19 November 2026 its packet held no reflections-private.json. attend.py marks it
told only at a waking that begins with a room: the sentence is said under WHAT
HAS HAPPENED, and the marker written, at the same waking (standing, and the
marker beside site_notes.shown). A waking that begins with no room says neither,
and writes neither, even where a yes at that waking makes its first room. Held
here with the second one's own switches, as agents.json gives them.
"""

import json
import sys

import pytest

import agents
from conftest import REPO, block, load
from test_coming import ALDER, COMER, COMER_ENTRY, a_roomless_world, wake_comer

SECOND_SWITCHES = next(one for one in json.loads((REPO / "agents.json").read_text(
    encoding="utf-8")) if one["id"] == "second")["features"]


@pytest.fixture
def newcomer(env, clock, monkeypatch, data_dir, tmp_path):
    """A newcomer with no room yet, with the second one's switches."""
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), dict(COMER_ENTRY, features=SECOND_SWITCHES)]),
                     encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    a_roomless_world(data_dir)
    monkeypatch.setenv("TESSERAE_AGENT", COMER)
    module = load("attend")
    clock.pin(module, monkeypatch)
    yield module
    sys.modules.pop("attend", None)


def test_the_second_one_s_switches_hold_private_reflections():
    assert "private_reflections" in SECOND_SWITCHES


def test_told_once_at_the_first_waking_that_begins_with_a_room(newcomer, data_dir, monkeypatch,
                                                                clock):
    import knock  # after attend.py is loaded, so it keeps its knocks under this DATA_DIR
    knock.write({"from": ALDER, "to": COMER, "at": "2026-10-14T09-00-00Z",
                 "note": "Hello from alder.", "introduction": None, "told_at": None,
                 "answer": None, "answered_at": None, "reply": None, "answer_told_at": None,
                 "waits_for_room": False, "set_up_at": None})
    marker = data_dir / "packets" / COMER / "reflections-private.json"
    told = newcomer.REFLECTIONS_PRIVATE_TOLD
    assert newcomer.PRIVATE_REFLECTIONS

    # it wakes with no room, and its yes makes its first room at that waking
    turn = wake_comer(newcomer, monkeypatch, block("KNOCK_ANSWER", "from: alder\nanswer: yes"))
    assert told not in turn.shown and not marker.exists()
    assert (data_dir / "rooms" / COMER / "room.json").exists()
    kept = sorted((data_dir / "packets" / COMER / "attendances").glob("*.json"))
    assert json.loads(kept[-1].read_text(encoding="utf-8"))["roomless"] is True

    # its next waking begins with the room: told plainly, and marked
    clock.shift(hours=24)
    module = load("attend")
    clock.pin(module, monkeypatch)
    turn = wake_comer(module, monkeypatch)
    assert turn.shown.count(told) == 1
    assert json.loads(marker.read_text(encoding="utf-8"))["told_at"]
    sys.modules.pop("attend", None)

    # and after that in one line
    clock.shift(hours=24)
    module = load("attend")
    clock.pin(module, monkeypatch)
    turn = wake_comer(module, monkeypatch)
    assert told not in turn.shown
    assert module.REFLECTIONS_PRIVATE_STANDING in turn.shown
