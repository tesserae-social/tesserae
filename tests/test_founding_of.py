"""Each agent's founding, found in the record by its name (stage 8b, gate G3).

attend.founding_day and hearth.commons_lines once took the founding line at an
agent's place in the registry. Now agents.founding_of finds it by name: the
line "<name> was founded", for any name the agent has had, the earliest where
there are two. With today's record the days and the books are what they were;
a missing line, a stray one or two foundings on one day move no one else's.
"""

from pathlib import Path

import pytest

import agents
from conftest import load, write
from test_named_events import RECORD, SECOND, THIRD, THREE_FOUNDINGS, book, registry_of

REPO = Path(__file__).resolve().parent.parent

# The record as it stands today, as kept in the repository and as the commons copy has it.
TODAY = [REPO / "record" / "commons" / "events.md", REPO / "commons" / "events.md"]


def by_place(hearth, agent_id=None):
    """One agent's book as commons_lines made it before 8b: its founding by place."""
    agent = agents.by_id(agent_id) if agent_id else agents.first()
    events = hearth.parse_events(hearth.read_text(hearth.EVENTS))
    founded = sorted((one for one in events if one[1] == "founding"), key=lambda one: one[0])
    place = [one["id"] for one in agents.registry()].index(agent["id"])
    lines = []
    for when, kind, words in events:
        found = agents.named(kind, words)
        if found:
            whose, words = found
            if whose["id"] != agent["id"]:
                continue
        elif agent["id"] != "first" and (when, kind, words) not in founded[place:]:
            continue
        lines.append((when.isoformat(), words))
    return lines


def day_by_place(attend):
    """attend.founding_day as it was before 8b."""
    events = attend.parse_events(attend.read(attend.COMMONS / "events.md"))
    founded = sorted(when for when, kind, _ in events if kind == "founding")
    place = [agent["id"] for agent in agents.registry()].index(attend.NAME)
    return founded[place] if place < len(founded) else None


def as_agent(monkeypatch, agent_id):
    """attend.py as the hearth starts it for one agent."""
    monkeypatch.setenv("TESSERAE_AGENT", agent_id)
    return load("attend")


@pytest.fixture
def first_again(monkeypatch):
    """Leave attend.py imported as the first one's, as other tests expect it."""
    yield
    monkeypatch.delenv("TESSERAE_AGENT", raising=False)
    load("attend")


# ---- agents.founding_of ----------------------------------------------------

def test_a_founding_is_found_by_name_earliest_first():
    events = [(1, "founding", "the scratch one was founded"),
              (0, "founding", "the scratch one was founded"),
              (0, "event", "the scratch one was founded"),      # not a founding line
              (0, "founding", "the scratch ones was founded")]  # not its name
    assert agents.founding_of(SECOND, events) == (0, "founding", "the scratch one was founded")
    assert agents.founding_of(agents.FIRST, events) is None


def test_a_renamed_agent_is_found_through_formerly():
    renamed = {**SECOND, "commons_name": "Wren", "formerly": ["the scratch one"]}
    line = (5, "founding", "the scratch one was founded")
    assert agents.founding_of(renamed, [line]) == line
    assert agents.founding_of(SECOND, [(5, "founding", "Wren was founded")]) is None


# ---- today's record --------------------------------------------------------

@pytest.mark.parametrize("record", TODAY, ids=["record", "commons"])
def test_today_s_record_gives_the_same_day_and_book(record, hearth, attend, commons):
    write(commons / "events.md", record.read_text(encoding="utf-8"))
    assert attend.founding_day() == day_by_place(attend)
    assert attend.founding_day().isoformat() == "2026-09-04"
    assert book(hearth) == by_place(hearth)
    assert book(hearth, "first") == by_place(hearth, "first")


@pytest.mark.parametrize("record, who", [(RECORD, (SECOND,)), (THREE_FOUNDINGS, (SECOND, THIRD))],
                         ids=["two", "three"])
def test_a_whole_record_gives_every_agent_the_same_day_and_book(
        record, who, hearth, commons, env, clock, monkeypatch, tmp_path, first_again):
    registry_of(monkeypatch, tmp_path, *who)
    write(commons / "events.md", record)
    for agent in agents.registry():
        assert book(hearth, agent["id"]) == by_place(hearth, agent["id"])
        module = as_agent(monkeypatch, agent["id"])
        assert module.founding_day() == day_by_place(module)


# ---- what by place got wrong -----------------------------------------------

@pytest.fixture
def three(monkeypatch, tmp_path, env, clock, first_again):
    registry_of(monkeypatch, tmp_path, SECOND, THIRD)


def days(monkeypatch):
    found = {agent["id"]: as_agent(monkeypatch, agent["id"]).founding_day()
             for agent in agents.registry()}
    return {who: day and day.isoformat() for who, day in found.items()}


def test_two_foundings_on_one_day(hearth, commons, three, monkeypatch):
    # the third written first, on the same day as the second
    write(commons / "events.md",
          "2026-09-04 · founding · the first one was founded\n"
          "2026-10-20 · founding · the scratch third was founded\n"
          "2026-10-20 · founding · the scratch one was founded\n")
    assert days(monkeypatch) == {"first": "2026-09-04", "second": "2026-10-20",
                                 "third": "2026-10-20"}
    assert book(hearth, "second") == [("2026-10-20", "the scratch third was founded"),
                                      ("2026-10-20", "the scratch one was founded")]
    assert book(hearth, "third") == [("2026-10-20", "the scratch third was founded")]


def test_a_missing_line_shifts_nothing(hearth, commons, three, monkeypatch):
    write(commons / "events.md", "".join(line + "\n" for line in THREE_FOUNDINGS.splitlines()
                                         if "scratch one was founded" not in line))
    # by place, the second had the third's day, and the third had none
    assert days(monkeypatch) == {"first": "2026-09-04", "second": None,
                                 "third": "2026-10-25"}
    assert book(hearth, "third") == [("2026-10-25", "the scratch third was founded"),
                                     ("2026-11-03", "the tide paused")]
    assert book(hearth, "second") == [("2026-10-25", "the scratch third was founded")]


def test_a_stray_founding_line_is_no_one_s_but_the_first_one_s(hearth, commons, three,
                                                                 monkeypatch):
    write(commons / "events.md",
          "2026-09-04 · founding · the first one was founded\n"
          "2026-09-10 · founding · something else was founded\n"
          "2026-10-20 · founding · the scratch one was founded\n"
          "2026-10-25 · founding · the scratch third was founded\n")
    # by place, the second had the stray line's day, and the third the second's
    assert days(monkeypatch) == {"first": "2026-09-04", "second": "2026-10-20",
                                 "third": "2026-10-25"}
    assert ("2026-09-10", "something else was founded") in book(hearth)
    assert book(hearth, "second") == [("2026-10-20", "the scratch one was founded"),
                                      ("2026-10-25", "the scratch third was founded")]
    assert book(hearth, "third") == [("2026-10-25", "the scratch third was founded")]


def test_a_renamed_agent_keeps_its_day_and_book(hearth, commons, monkeypatch, tmp_path, env,
                                               clock, first_again):
    registry_of(monkeypatch, tmp_path,
                {**SECOND, "commons_name": "Wren", "formerly": ["the scratch one"]})
    write(commons / "events.md", RECORD)
    assert as_agent(monkeypatch, "second").founding_day().isoformat() == "2026-10-20"
    assert book(hearth, "second")[0] == ("2026-10-20", "the scratch one was founded")
