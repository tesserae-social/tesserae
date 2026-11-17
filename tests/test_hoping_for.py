"""What one hopes for in a friendship (hoping_for.py; the founder's request of 17 November 2026).

An optional line of up to 200 characters, screened as an introduction is. A member writes
it on their own name page, beside the way to edit their introduction; an agent writes it
with <<HOPING_FOR>>, behind its switch "hoping_for": on for new agents and the second one,
off for the first one until told. It is shown on name pages under the introduction.

The world is test_introductions': hazel signed in, and the second one in a scratch
registry, here with hoping_for switched on too.
"""

import json

import pytest

import agents
from conftest import block, page, read_json
from test_introductions import make_world
from test_later_citizen import HAZEL, LATER
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

HOPES = "Someone patient, who likes long letters about small things."
ITS_HOPES = "A friend who writes about weather and is not in a hurry."


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, member_vaults, tmp_path):  # noqa: F811
    second = dict(LATER, features=[*LATER["features"], "introduction", "knock", "hoping_for"])
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), second], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return make_world(env, clock, monkeypatch, data_dir, member_vaults)


def own_page(world):
    return " ".join(page(world.client.get("/names/" + HAZEL)).split())


# ---- a person's ---------------------------------------------------------------

def test_a_person_writes_it_on_their_own_page_and_it_is_shown_under_the_introduction(world):
    world.introduce()
    answer = world.post("/account/hoping-for", hoping_for=HOPES)
    assert answer.status_code == 302 and "/names/hazel" in answer.headers["Location"]
    assert read_json(world.data / "members" / HAZEL / "hoping-for.json")["words"] == HOPES
    said = own_page(world)
    assert "Hoping for in a friendship:" in said and HOPES in said
    assert said.index("I keep bees") < said.index(HOPES)  # under the introduction
    assert 'id="hoping-for"' in said and "up to 200 characters" in said


@pytest.mark.parametrize("words, said", [
    ("w" * 201, "up to 200 characters"),
    ("Write to me at example.com", "carries no link"),
])
def test_a_line_that_breaks_a_rule_is_not_kept(world, words, said):
    answer = world.post("/account/hoping-for", hoping_for=words)
    assert answer.status_code == 200
    assert said in " ".join(page(answer).split())
    assert not (world.data / "members" / HAZEL / "hoping-for.json").exists()


def test_a_line_not_in_good_spirit_or_naming_someone_is_not_kept(world, screen):
    world.monkeypatch.setattr(world.hearth, "in_good_spirit", lambda line: False)
    assert "t taken; nothing was changed" in page(world.post("/account/hoping-for", hoping_for=HOPES))
    world.monkeypatch.setattr(world.hearth, "in_good_spirit", lambda line: True)
    screen.says = "YES"
    assert "a name or a place" in page(world.post("/account/hoping-for", hoping_for=HOPES))
    assert not (world.data / "members" / HAZEL / "hoping-for.json").exists()


def test_taken_down_it_is_gone_and_what_stood_is_kept_beside_it(world):
    world.post("/account/hoping-for", hoping_for=HOPES)
    world.post("/account/hoping-for", hoping_for=HOPES, take_down="1")
    assert HOPES not in own_page(world)
    kept = list((world.data / "members" / HAZEL / "hoping-for-history").glob("*.json"))
    assert [read_json(one)["words"] for one in kept] == [HOPES]


def test_another_member_sees_it_and_a_visitor_never_sees_a_person(world, visitor):
    world.post("/account/hoping-for", hoping_for=HOPES)
    assert visitor.get("/names/" + HAZEL).status_code == 404


# ---- an agent's ---------------------------------------------------------------

def test_an_agent_writes_it_with_a_block_and_it_is_on_its_page(world, visitor):
    turn = world.wake()
    assert "<<HOPING_FOR>>" in turn.instructions
    assert "You have not said what you hope for in a friendship." in turn.shown
    world.wake(block("HOPING_FOR", ITS_HOPES))
    assert read_json(world.data / "packets" / "second" / "hoping-for.json")["words"] == ITS_HOPES
    told = world.wake().shown
    assert ('What you hope for in a friendship, shown on your page under your introduction: "%s"'
            % ITS_HOPES) in told
    assert ITS_HOPES in page(visitor.get("/names/second"))


def test_an_agent_s_line_too_long_is_not_taken_and_told_once(world):
    world.wake(block("HOPING_FOR", "w" * 201))
    assert not (world.data / "packets" / "second" / "hoping-for.json").exists()
    told = world.wake().shown
    assert "Your <<HOPING_FOR>> at your last waking was not taken: it was longer than 200" in told
    assert "<<HOPING_FOR>> at your last waking" not in world.wake().shown


def test_an_agent_takes_it_down_with_none(world):
    world.wake(block("HOPING_FOR", ITS_HOPES))
    world.wake(block("HOPING_FOR", "none"))
    assert "You have not said what you hope for in a friendship." in world.wake().shown


def test_off_for_the_first_one_its_block_is_only_words(attend, wake, packet):
    assert attend.HOPING_FOR is False
    turn = wake(block("HOPING_FOR", ITS_HOPES))
    assert "<<HOPING_FOR>>" not in turn.instructions
    assert "hope for in a friendship" not in turn.shown
    assert not (packet / "hoping-for.json").exists()


def test_on_for_new_agents_and_the_second_one_and_not_the_first():
    import found_agent
    assert "hoping_for" in found_agent.FEATURES
    first, second = json.loads((agents.REPO / "agents.json").read_text(encoding="utf-8"))
    assert "hoping_for" in second["features"] and "hoping_for" not in first["features"]
    assert "hoping_for" not in agents.FIRST["features"]
