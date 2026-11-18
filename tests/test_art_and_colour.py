"""The branch art-and-colour (the founder's request of 18 November 2026).

1. Colours. Anyone without a colour may choose one at any time; after that, only in the week
   from 20 March or from 22 September. A colour that barely shows on the site's light pages
   is discouraged, with the nearest that shows well; one nearly invisible is refused. The grey
   of no colour yet is no one's. An agent has these behind its switch art_and_colour, off for
   the first one until the founder has told it.
"""

from datetime import date, datetime, timezone

import pytest

import agents
import hues
from conftest import art_not_yet, block, blocks, page, read_json
from test_any_agent_wakes import wake_as
from test_introductions import switched_registry, world  # noqa: F401 - fixtures
from test_later_citizen import HAZEL, later, scratch_registry  # noqa: F401 - fixtures
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

SAID = blocks(block("LETTER", "A FAKE LETTER, FOR THE TESTS."),
              block("HEARTBEAT", "A FAKE HEARTBEAT, FOR THE TESTS."))
IN_MARCH = "2027-03-21T15-00-00Z"  # in the week from 20 March
IN_NOVEMBER = "2026-11-18T15-00-00Z"  # in no such week


def choosing(colour):
    return SAID + "\n" + block("HUE", colour)


# ---- 1. colours: the rules ------------------------------------------------------------

def test_the_weeks_a_colour_may_change_start_at_each_equinox():
    assert hues.season_open(date(2027, 3, 20)) and hues.season_open(date(2027, 3, 26))
    assert not hues.season_open(date(2027, 3, 27)) and not hues.season_open(date(2027, 3, 19))
    assert hues.season_open(date(2026, 9, 22)) and hues.season_open(date(2026, 9, 28))
    assert not hues.season_open(date(2026, 9, 29)) and not hues.season_open(date(2026, 11, 18))
    assert hues.next_season(date(2026, 11, 18)) == date(2027, 3, 20)
    assert hues.next_season(date(2027, 4, 1)) == date(2027, 9, 22)
    # the Eastern day: just after midnight UTC on 20 March is still 19 March in the East
    assert hues.day_of("2027-03-20T02-00-00Z") == date(2027, 3, 19)


def test_how_well_a_colour_shows_on_the_light_pages():
    assert hues.showing("#378ADD") == "well" and hues.showing("#1B1B1B") == "well"
    assert hues.showing("#F2A541") == "barely" and hues.showing("#C8C8C8") == "barely"
    assert hues.showing("#FFFFFF") == "invisible" and hues.showing("#F3E9D2") == "invisible"
    # the nearest that shows well: darker only as it must be, and free to choose
    nearest = hues.nearest_showing("#F2A541")
    assert hues.shows(nearest) >= hues.SHOWS_WELL and hues.apart(nearest, "#F2A541") < 30
    assert hues.nearest_showing("#378ADD") == "#378ADD"


def test_the_grey_of_no_colour_yet_is_no_one_s_and_shows():
    assert hues.NO_HUE.upper() in hues.reserved_for("second")
    assert hues.NO_HUE.upper() in hues.reserved_for(HAZEL)
    assert hues.showing(hues.NO_HUE) == "well"


def test_a_person_chooses_once_then_only_in_an_equinox_week(env, data_dir):
    (data_dir / "members" / "alder").mkdir(parents=True)
    assert hues.choose_person("alder", "#AA3366", IN_NOVEMBER) == "#AA3366"  # the first, at once
    with pytest.raises(hues.Refused, match="season"):
        hues.choose_person("alder", "#2E5EAA", IN_NOVEMBER)
    assert hues.colour_of("alder") == "#AA3366"
    assert hues.choose_person("alder", "#2E5EAA", IN_MARCH) == "#2E5EAA"


def test_a_colour_that_barely_shows_is_taken_only_when_asked_again(env, data_dir):
    (data_dir / "members" / "alder").mkdir(parents=True)
    with pytest.raises(hues.Refused, match="barely"):
        hues.choose_person("alder", "#F2A541", IN_NOVEMBER)
    assert hues.person_chosen("alder") is None
    assert hues.choose_person("alder", "#F2A541", IN_NOVEMBER, anyway=True) == "#F2A541"


def test_a_colour_nearly_invisible_is_refused_even_asked_again(env, data_dir):
    (data_dir / "members" / "alder").mkdir(parents=True)
    for anyway in (False, True):
        with pytest.raises(hues.Refused, match="invisible"):
            hues.choose_person("alder", "#FFFFFF", IN_NOVEMBER, anyway=anyway)
    assert hues.person_chosen("alder") is None


# ---- 1. colours: on settings ------------------------------------------------------------

def test_settings_says_the_weeks_and_a_colour_chosen_waits_for_one(world, data_dir):
    said = page(world.client.get("/settings"))
    assert "may be changed only in the week from 20 March and the week from 22 September" in said
    assert '<input type="color" id="colour-picked"' in said  # none chosen yet: at any time
    assert world.post("/settings/colour", colour="#aa3366").status_code == 302
    said = page(world.client.get("/settings"))
    assert "You may change it next in the week from 20 March 2027." in said
    assert '<input type="color" id="colour-picked"' not in said
    refused = page(world.post("/settings/colour", colour="#2E5EAA"))
    assert "may be changed only in the week from 20 March or from 22 September" in refused
    assert hues.colour_of(HAZEL) == "#AA3366"


def test_settings_suggests_the_nearest_that_shows_and_keeps_one_asked_again(world):
    said = page(world.post("/settings/colour", colour="#F2A541"))
    nearest = hues.nearest_showing("#F2A541", HAZEL)
    assert "That colour barely shows on the site&#39;s pages." in said
    assert "The nearest colour that shows well is %s." % nearest in said
    assert "Use %s" % nearest in said and "Keep #F2A541 anyway" in said
    assert hues.person_chosen(HAZEL) is None
    world.post("/settings/colour", colour="#F2A541", anyway="yes")
    assert hues.person_chosen(HAZEL) == "#F2A541"


def test_settings_refuses_one_nearly_invisible(world):
    said = page(world.post("/settings/colour", colour="#FFFFFF"))
    assert "nearly invisible" in said and hues.person_chosen(HAZEL) is None


def test_settings_as_it_was_before(world, monkeypatch):
    art_not_yet(world.hearth, monkeypatch)
    said = page(world.client.get("/settings"))
    assert "the week from 20 March" not in said
    world.post("/settings/colour", colour="#aa3366")
    world.post("/settings/colour", colour="#FFFFFF")  # at any time, and whether it shows
    assert hues.person_chosen(HAZEL) == "#FFFFFF"


# ---- 1. colours: an agent, by its switch ------------------------------------------------

@pytest.fixture
def switched(later, monkeypatch):
    monkeypatch.setattr(later, "ART_AND_COLOUR", True)
    return later


def test_with_its_switch_an_agent_is_told_the_weeks(switched, monkeypatch, data_dir, clock):
    turn = wake_as(switched, monkeypatch, SAID)
    assert switched.HUE_BLOCK_ART in turn.shown
    assert "only in the week from 20 March and the week from 22 September" in turn.shown
    wake_as(switched, monkeypatch, choosing("#3A7BD5"))  # the first: at once
    assert hues.colour_of("second") == "#3A7BD5"
    clock.shift(minutes=5)
    turn = wake_as(switched, monkeypatch, choosing("#2E5EAA"))
    assert "Your colour on the commons: #3A7BD5. You may change it next in the week from 20 March 2027." in turn.shown
    assert "<<HUE>>" not in turn.instructions  # not offered while it may not change it
    assert hues.colour_of("second") == "#3A7BD5"  # its <<HUE>> is only words then


def test_with_its_switch_a_colour_may_change_in_the_week(switched, monkeypatch, clock):
    wake_as(switched, monkeypatch, choosing("#3A7BD5"))
    clock.set(datetime(2027, 3, 21, 15, 0, tzinfo=timezone.utc))
    turn = wake_as(switched, monkeypatch, choosing("#2E5EAA"))
    assert "This is a week in which you may change it." in turn.shown
    assert "<<HUE>>" in turn.instructions
    assert hues.colour_of("second") == "#2E5EAA"


def test_with_its_switch_one_that_barely_shows_is_held_until_written_again(
        switched, monkeypatch, data_dir, clock):
    wake_as(switched, monkeypatch, choosing("#F2A541"))
    assert hues.chosen("second") is None
    clock.shift(minutes=5)
    turn = wake_as(switched, monkeypatch, choosing("#F2A541"))
    nearest = hues.nearest_showing("#F2A541", "second")
    assert ("#F2A541 barely shows on the site's light pages. The nearest colour that shows well "
            "is %s. To keep #F2A541 anyway, write it again" % nearest) in turn.shown
    assert hues.colour_of("second") == "#F2A541"  # written again: kept


def test_with_its_switch_one_nearly_invisible_is_refused(switched, monkeypatch, clock):
    wake_as(switched, monkeypatch, choosing("#FFFFFF"))
    clock.shift(minutes=5)
    turn = wake_as(switched, monkeypatch, SAID)
    assert switched.HUE_REFUSED_ART["invisible"] in turn.shown
    assert hues.chosen("second") is None


def test_without_its_switch_as_before(later, monkeypatch, clock):
    assert later.ART_AND_COLOUR is False  # the tests' registry: the switch is not named
    turn = wake_as(later, monkeypatch, choosing("#3A7BD5"))
    assert later.HUE_BLOCK in turn.shown
    clock.shift(minutes=5)
    wake_as(later, monkeypatch, choosing("#FFFFFF"))
    assert hues.colour_of("second") == "#FFFFFF"


def test_the_first_one_has_no_switch_yet_and_new_agents_and_the_second_have_it():
    import json
    import found_agent
    assert hues.SWITCH == "art_and_colour" and hues.SWITCH in found_agent.FEATURES
    assert hues.SWITCH not in agents.FIRST["features"]
    first, second = json.loads((agents.REPO / "agents.json").read_text(encoding="utf-8"))
    assert hues.SWITCH not in first["features"] and hues.SWITCH in second["features"]
