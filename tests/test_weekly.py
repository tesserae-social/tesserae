"""A weekly question (the founder's decision of 13 November 2026).

Proposed by members on /account, screened as the bench is; one a week, the oldest
proposed first; shown to people at the top of their room as "This week's
question, if you'd like it: ..."; never with who proposed it. No agent reads it
unless it chooses to, with read_weekly_question at a longer waking, behind
"weekly_question" in its features, off for every agent in what is committed.
"""

import json
from datetime import datetime, timezone

import pytest

import agents
from conftest import page, post, read_json
from test_board import signed_in
from test_bench import Reader
from test_longer_waking import longer, look  # noqa: F401 - a fixture

MONDAY = datetime(2026, 11, 16, 15, tzinfo=timezone.utc)
ASKS = "What is one small thing that went well this week?"
LATER = "What sound do you like best in the morning?"


@pytest.fixture
def world(hearth, clock, monkeypatch):
    clock.set(MONDAY)
    reader = Reader()
    monkeypatch.setattr(hearth, "Anthropic", reader)
    hearth.reader = reader
    return hearth


@pytest.fixture
def birch(world, monkeypatch):
    return signed_in(world, monkeypatch, "birch")


@pytest.fixture
def alder(world, monkeypatch):
    return signed_in(world, monkeypatch, "alder")


def top_of_room(client):
    shown = page(client.get("/rooms/first"))
    return shown.partition("<main")[2]


def shown_line(words):
    return "This week&#39;s question, if you&#39;d like it: " + words


def test_with_none_proposed_a_room_is_as_it_was(world, founder):
    assert "This week" not in page(founder.get("/rooms/first"))


def test_the_oldest_proposed_is_this_week_s_and_the_next_waits(world, founder, birch, alder,
                                                                clock, data_dir):
    assert post(birch, "/account/weekly-question", data={"question": ASKS}).status_code == 302
    clock.shift(minutes=1)
    assert post(alder, "/account/weekly-question", data={"question": LATER}).status_code == 302
    shown = top_of_room(founder)
    assert shown.count(shown_line(ASKS)) == 1 and LATER not in shown
    assert "birch" not in shown  # never who proposed it
    clock.shift(days=3)  # the same week: the same question
    assert shown_line(ASKS) in top_of_room(founder)
    clock.shift(days=4)  # the next Monday: the next one
    shown = top_of_room(founder)
    assert shown_line(LATER) in shown and ASKS not in shown
    clock.shift(days=7)  # nothing left waiting: no question
    assert "This week" not in top_of_room(founder)
    kept = read_json(data_dir / "weekly-questions.json")
    assert [one["words"] for one in kept["weeks"].values()] == [ASKS, LATER]


def test_one_waiting_at_a_time_and_it_may_be_taken_back(world, birch, data_dir):
    post(birch, "/account/weekly-question", data={"question": ASKS})
    answer = post(birch, "/account/weekly-question", data={"question": LATER})
    assert "One of your questions is waiting already" in page(answer)
    assert "Your question waits its turn" in page(birch.get("/account"))
    post(birch, "/account/weekly-question", data={"withdraw": "1"})
    assert read_json(data_dir / "weekly-questions.json")["waiting"] == []
    assert post(birch, "/account/weekly-question", data={"question": LATER}).status_code == 302


@pytest.mark.parametrize("words, why", [
    ("x" * 201, "A question is up to 200 characters"),
    ("What do you think of example.com?", "A question carries no link"),
])
def test_what_is_turned_away_is_said(world, birch, data_dir, words, why):
    answer = post(birch, "/account/weekly-question", data={"question": words})
    assert why in page(answer)
    assert not (data_dir / "weekly-questions.json").exists()


def test_a_question_not_in_good_spirit_or_naming_someone_is_not_proposed(world, birch, data_dir,
                                                                         screen):
    world.reader.says = "NO"
    assert "wasn&#39;t taken" in page(post(birch, "/account/weekly-question",
                                           data={"question": ASKS}))
    world.reader.says = "YES"
    screen.says = "YES"
    assert "seemed to contain a name or a place" in page(
        post(birch, "/account/weekly-question", data={"question": ASKS}))
    assert not (data_dir / "weekly-questions.json").exists()


def test_a_visitor_proposes_nothing(world, visitor, data_dir):
    post(visitor, "/account/weekly-question", data={"question": ASKS})
    assert not (data_dir / "weekly-questions.json").exists()


# ---- an agent reads it only if it chooses to -------------------------------------

def test_the_switch_is_off_for_every_agent(attend):
    assert attend.WEEKLY_QUESTION is False
    assert all("weekly_question" not in (one.get("features") or ())
               for one in agents.registry())


def a_question_this_week(data_dir):
    (data_dir / "weekly-questions.json").write_text(json.dumps(
        {"waiting": [], "weeks": {"2026-W42": {"words": ASKS, "by": "birch",
                                               "chosen_on": "2026-10-12"}}}), encoding="utf-8")


def test_switched_off_no_tool_is_offered_and_nothing_is_read(attend, longer, data_dir):
    a_question_this_week(data_dir)
    exchange = longer()
    asked = exchange.asked[-1]
    assert "read_weekly_question" not in [tool["name"] for tool in asked["tools"]]
    assert ASKS not in json.dumps(asked, default=str)


def test_switched_on_it_is_offered_and_never_put_in_the_reading(attend, longer, data_dir,
                                                                monkeypatch):
    monkeypatch.setattr(attend, "WEEKLY_QUESTION", True)
    a_question_this_week(data_dir)
    exchange = longer()
    asked = exchange.asked[-1]
    assert "read_weekly_question" in [tool["name"] for tool in asked["tools"]]
    assert ASKS not in json.dumps(asked["messages"], default=str)  # unless it looks


def test_switched_on_looking_gives_this_week_s_question(attend, longer, data_dir, monkeypatch):
    monkeypatch.setattr(attend, "WEEKLY_QUESTION", True)
    a_question_this_week(data_dir)
    exchange = longer(look(("read_weekly_question", {})), "")
    assert exchange.given == [attend.WEEKLY_SAID.format(words=ASKS)]


def test_switched_on_with_none_this_week_it_is_told_so(attend, longer, monkeypatch):
    monkeypatch.setattr(attend, "WEEKLY_QUESTION", True)
    exchange = longer(look(("read_weekly_question", {})), "")
    assert exchange.given == [attend.NO_WEEKLY_QUESTION]
