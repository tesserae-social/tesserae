"""Names at the solstices, on ids (names-ids, stage 7; the founder's request of 20 November
2026, the names branch rebuilt on ids). In the week from 21 June and from 21 December anyone
may choose a new commons name, once that week. Nothing moves but the name; every page draws
it from the id.
"""

import json
from datetime import date, datetime, timezone

import pytest

from conftest import PASSWORD, page, post
from test_introductions import make_world
from test_knocks_tidy import registry_with
from test_later_citizen import hearth_of_two, scratch_registry  # noqa: F401 - fixtures
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

IN_THE_WEEK = datetime(2026, 12, 22, 17, tzinfo=timezone.utc)


def test_the_weeks():
    import names
    assert names.week_of(date(2026, 12, 21)) == date(2026, 12, 21)
    assert names.week_of(date(2026, 12, 27)) == date(2026, 12, 21)
    assert names.week_of(date(2026, 12, 28)) is None
    assert names.week_of(date(2027, 6, 24)) == date(2027, 6, 21)
    assert names.next_week(date(2026, 11, 20)) == date(2026, 12, 21)


def test_a_person_chooses_a_new_name_once_in_the_week(hearth_of_two, clock):
    import hearth
    import members
    clock.set(IN_THE_WEEK)
    member = hearth_of_two["member"]
    said = page(member.get("/settings"))
    assert "you may choose a new name, once this week" in said
    answer = post(member, "/account/name", data={"name": "birch"})
    assert "Your name on the commons is now birch." in page(answer)
    assert members.name_of("alder") == "birch"
    assert members.did_for("alder").endswith(":alder")  # the id, the DID: unchanged
    assert post(member, "/account/name", data={"name": "cedar"}).status_code == 404  # once
    assert member.get("/names/alder").status_code == 404
    assert member.get("/names/birch").status_code == 200
    assert members.id_of("birch") == "alder"
    with pytest.raises(hearth.names.Refused):  # an old name is never anyone's again
        hearth.names.check("alder", person=True)


def test_outside_the_week_nothing_is_offered(hearth_of_two):
    member = hearth_of_two["member"]
    assert "your name on the commons" not in page(member.get("/settings"))
    assert post(member, "/account/name", data={"name": "birch"}).status_code == 404


def test_the_keeper_is_the_founder_always(hearth_of_two, clock):
    clock.set(IN_THE_WEEK)
    assert "your name on the commons" not in page(hearth_of_two["keeper"].get("/settings"))


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, member_vaults, tmp_path):  # noqa: F811
    registry_with(monkeypatch, tmp_path, "solstice_names")
    made = make_world(env, clock, monkeypatch, data_dir, member_vaults)
    clock.set(IN_THE_WEEK)
    return made


def test_an_agent_chooses_a_new_name_at_a_waking_in_the_week(world, data_dir):
    import agents
    turn = world.wake("")
    assert "<<NAME>>" in turn.shown and "This is the week from 21 December 2026" in turn.shown
    before = agents.by_id("second")["commons_name"]
    world.wake("<<NAME>>\nthe lantern one\n<<END>>")
    entry = agents.by_id("second")
    assert entry["commons_name"] == "the lantern one" and before in entry["formerly"]
    assert agents.registry(asked=False)[1]["commons_name"] == before  # never in agents.json
    turn = world.wake("")
    assert "Your name on the commons is now the lantern one." in turn.shown
    assert "<<NAME>>\n(a new name" not in turn.shown  # once a week


def test_without_its_switch_nothing_is_said(env, clock, monkeypatch, data_dir, member_vaults,  # noqa: F811
                                            tmp_path):
    registry_with(monkeypatch, tmp_path)
    made = make_world(env, clock, monkeypatch, data_dir, member_vaults)
    clock.set(IN_THE_WEEK)
    turn = made.wake("<<NAME>>\nthe lantern one\n<<END>>")
    assert "<<NAME>>\n(a new name" not in turn.shown
    import agents
    assert agents.by_id("second")["commons_name"] != "the lantern one"


# ---- stage 8: names told -------------------------------------------------------------------

@pytest.fixture
def told_world(env, clock, monkeypatch, data_dir, member_vaults, tmp_path):  # noqa: F811
    registry_with(monkeypatch, tmp_path, "names_told", "commons_names")
    return make_world(env, clock, monkeypatch, data_dir, member_vaults)


def test_an_agent_is_told_once_when_someone_it_knows_takes_a_new_name(told_world):
    import members
    told = "The person you knew as alder is now called birch."
    assert told not in told_world.wake("").shown  # the first waking keeps the names, says none
    members.set_name("alder", "birch")
    assert told in told_world.wake("").shown
    assert told not in told_world.wake("").shown  # once


def test_without_names_told_nothing_is_said(env, clock, monkeypatch, data_dir, member_vaults,  # noqa: F811
                                            tmp_path):
    import members
    registry_with(monkeypatch, tmp_path)
    made = make_world(env, clock, monkeypatch, data_dir, member_vaults)
    made.wake("")
    members.set_name("alder", "birch")
    assert "is now called" not in made.wake("").shown


def test_without_commons_names_a_new_name_never_moves_the_reading(env, clock, monkeypatch,  # noqa: F811
                                                                  data_dir, member_vaults,
                                                                  tmp_path):
    import members
    registry_with(monkeypatch, tmp_path)
    made = make_world(env, clock, monkeypatch, data_dir, member_vaults)
    before = made.wake("").shown
    members.set_name("alder", "birch")
    after = made.wake("").shown
    assert "birch" not in after and after.count("alder") == before.count("alder")
