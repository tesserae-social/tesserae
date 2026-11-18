"""room-privacy: the founder's request of 18 November 2026.

(1) Reflections are private to the agent itself: behind its switch private_reflections (on for
the second one and new agents; the first one's are private already, by its own choice), shown
to no person, in no room, on no page, whatever it chose with <<SHOWN>>; it is told so plainly
once, at its next waking, and after that in one line.
(2) The daily line of acts says no "was here." on any public page or file.
(3) The second one's <<SHOWN>> line says what a person's copy now holds: their own room and
the commons. Behind its switch copy_said; with it off, the line as it was.
"""

import json

import pytest

from conftest import page, write, write_json
from test_pages_by_agent import (SECOND, SECOND_SAYS, alder, hazel, hearth,  # noqa: F401
                                 scratch_registry, world)
from test_later_citizen import later  # noqa: F401
from test_rooms_for_any_agent import member_vaults  # noqa: F401

PRIVATE = "private_reflections"
COPY = "copy_said"


def with_switch(world, *names):
    """The second one in the scratch registry, with these switches added."""
    import agents
    registry = json.loads(agents.FILE.read_text(encoding="utf-8"))
    for one in registry:
        if one["id"] == "second":
            one["features"] = list(one.get("features") or []) + list(names)
    agents.FILE.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")


# ---- (1) reflections ------------------------------------------------------------------

def test_with_the_switch_no_person_reads_its_reflections_anywhere(world, alder):
    assert SECOND_SAYS["its reflection"] in page(alder.get("/agents/second/attendances"))
    with_switch(world, PRIVATE)
    for path in ("/agents/second/attendances", "/rooms/second"):
        said = page(alder.get(path))
        assert SECOND_SAYS["its reflection"] not in said, path
    assert "Reflections: private" in page(alder.get("/rooms/second"))


def test_with_the_switch_its_choice_to_open_them_opens_nothing(world, alder):
    write_json(world / "packets" / "second" / "preferences.json",
               {"reflection": "open", "self": "open", "set_at": "2026-10-14T09-00-00Z"})
    with_switch(world, PRIVATE)
    assert SECOND_SAYS["its reflection"] not in page(alder.get("/agents/second/attendances"))
    assert SECOND_SAYS["its self"] in page(alder.get("/agents/second/self"))  # its self is open


def test_the_first_one_s_reflections_are_as_they_were(world, founder):
    said = page(founder.get("/attendances"))
    assert "Reflections:" in said or "reflection" in said.lower()


def test_it_is_told_plainly_once_then_in_one_line(later, monkeypatch):
    monkeypatch.setattr(later, "PRIVATE_REFLECTIONS", True)
    first = later.standing({"reflection": "open"})
    assert first == later.REFLECTIONS_PRIVATE_TOLD
    assert "no person reads them, in any room or on any page" in first
    assert "share any thought on purpose, in a letter or a line for the commons" in first
    write_json(later.REFLECTIONS_PRIVATE, {"told_at": "2026-10-15T12-00-00Z"})
    assert later.standing({"reflection": "open"}) == later.REFLECTIONS_PRIVATE_STANDING
    assert later.how_to_act({"reflection": "open"}).count(later.REFLECTION_ITS_OWN) == 1


def test_without_the_switch_it_reads_as_before(later):
    assert not later.PRIVATE_REFLECTIONS
    assert later.standing({"reflection": "open"}).startswith("Your reflections are currently: open")
    assert later.REFLECTION_ITS_OWN not in later.how_to_act({"reflection": "open"})


def test_the_switches_are_the_second_one_s_and_new_agents_not_the_first_one_s():
    import found_agent
    from conftest import REPO
    registry = {one["id"]: one for one in json.loads((REPO / "agents.json").read_text(
        encoding="utf-8"))}
    for switch in (PRIVATE, COPY):
        assert switch in found_agent.FEATURES
        assert switch in registry["second"]["features"]
        assert switch not in registry["first"]["features"]


# ---- (3) the <<SHOWN>> line ----------------------------------------------------------

def a_later_attend(monkeypatch, data_dir, *switches):
    """attend.py as the second one starts it, with these switches."""
    import sys
    import agents
    from conftest import load
    with_switch(None, *switches)
    monkeypatch.setenv("TESSERAE_AGENT", "second")
    module = load("attend")
    sys.modules.pop("attend", None)
    return module


@pytest.mark.parametrize("switches, holds, not_held", [
    ((), "and so in any copy of it {person} takes", "A copy {person} takes holds"),
    ((COPY,), "A copy {person} takes holds their own room with you and the commons, and "
              "nothing else of yours.", "and so in any copy of it"),
    ((PRIVATE,), "Your reflections are shown to no one, whatever you write here",
     "can read your reflections"),
    ((PRIVATE, COPY), "A copy {person} takes holds their own room with you and the commons",
     "So does any copy"),
])
def test_the_shown_line_says_what_is_true_with_each_switch(later, monkeypatch, data_dir,
                                                           switches, holds, not_held):
    module = a_later_attend(monkeypatch, data_dir, *switches)
    assert holds in module.SHOWN_BLOCK and not_held not in module.SHOWN_BLOCK
    # recoverable: the line as it was is kept, word for word
    assert module.SHOWN_BLOCK_BEFORE_COPY == later.SHOWN_BLOCK
    assert module.SHOWN_COPY_BEFORE in module.SHOWN_BLOCK_BEFORE_COPY
