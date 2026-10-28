"""Lines of the record named for an agent, read before any is written.

Stage 6a-i of the work that lets the tide wake more than one agent (the stage 6
proposal, 27 October 2026). From 6a-ii on, a pause, a stop, a release, an
offering and a seal will carry the commons name of the agent they are for,
first, with a middot after it:

    2026-11-02 · event · the first one · the tide paused

Here only the readers learn that shape: agents.named(), and each agent's book
(hearth.commons_lines). Nothing writes a named line yet, so the first one's
world is the world it was, held by test_first_one_fingerprints and READING_NOW.

The second agent is made only in a scratch registry.
"""

import json
from datetime import date

import pytest

import agents
from conftest import write, write_json

SECOND = {"id": "second", "did": "did:web:tesserae.social:ids:second",
          "commons_name": "the scratch one", "room": "second", "bond": "founder-second",
          "wakes": False}

# The record as it stands, in every shape it has been written in, and then
# lines named for each of the two agents.
RECORD = ("2026-09-02 · word · the word was published\n"
          "2026-09-04 · founding · the first one was founded\n"
          "2026-09-30 · the tide paused\n"                          # the older two-field shape
          "2026-10-01 · event · the tide resumed\n"                 # unnamed, as before names
          "2026-10-15 · letter · the founder wrote a letter at dawn\n"
          "2026-10-20 · founding · the scratch one was founded\n"
          "2026-11-02 · event · the first one · the tide paused\n"
          "2026-11-03 · event · the scratch one · the tide paused\n"
          "2026-11-04 · offering · the scratch one · an offering was placed\n"
          "2026-11-05 · event · the first one · the tide resumed\n")


def registry_of(monkeypatch, tmp_path, *entries):
    """A scratch registry: the first one, and whoever else is named."""
    where = tmp_path / "agents.json"
    # the first one as the registry gives it with no file, since the file may be one
    # a test has just made unreadable
    where.write_text(json.dumps([agents.FIRST, *entries], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return where


@pytest.fixture
def two(monkeypatch, tmp_path):
    registry_of(monkeypatch, tmp_path, SECOND)


def book(hearth, agent_id=None):
    """One agent's commons lines, as (day, words)."""
    agent = agents.by_id(agent_id) if agent_id else None
    return [(one["stamp"][:10], one["words"]) for one in hearth.commons_lines(agent)]


# ---- reading a line -------------------------------------------------------

def test_every_shape_of_line_is_read(hearth, two):
    events = hearth.parse_events(RECORD)
    said = [(when.isoformat(), kind, agents.named(kind, words)) for when, kind, words in events]
    whose = [(when, kind, found and (found[0]["id"], found[1])) for when, kind, found in said]
    assert whose == [
        ("2026-09-02", "word", None),
        ("2026-09-04", "founding", None),
        ("2026-09-30", "event", None),
        ("2026-10-01", "event", None),
        ("2026-10-15", "letter", None),
        ("2026-10-20", "founding", None),
        ("2026-11-02", "event", ("first", "the tide paused")),
        ("2026-11-03", "event", ("second", "the tide paused")),
        ("2026-11-04", "offering", ("second", "an offering was placed")),
        ("2026-11-05", "event", ("first", "the tide resumed")),
    ]


def test_a_name_is_read_only_where_a_name_may_be(two):
    for kind in ("word", "founding", "letter", "a kind no one knows"):
        assert agents.named(kind, "the first one · the tide paused") is None
        assert agents.named(kind, "the scratch one · the tide paused") is None
    assert agents.named("seal", "the scratch one · a bond was sealed")[1] == "a bond was sealed"


def test_a_name_without_its_middot_is_no_name(two):
    for words in ("the first one was founded", "the first one", "the first ones · paused",
                  "a bond was sealed between the founder and the first one"):
        assert agents.named("event", words) is None
        assert agents.named("seal", words) is None


def test_the_longest_name_is_tried_first(monkeypatch, tmp_path):
    registry_of(monkeypatch, tmp_path, {**SECOND, "commons_name": "the first one again"})
    found, rest = agents.named("event", "the first one again · the tide paused")
    assert (found["id"], rest) == ("second", "the tide paused")
    found, rest = agents.named("event", "the first one · again · the tide paused")
    assert (found["id"], rest) == ("first", "again · the tide paused")


def test_with_the_first_one_alone_its_name_is_its_own():
    found, rest = agents.named("event", "the first one · the tide paused")
    assert (found["id"], rest) == ("first", "the tide paused")


# ---- a name the commons called it before -----------------------------------

def test_a_renamed_agents_old_lines_stay_its_own(hearth, commons, monkeypatch, tmp_path):
    registry_of(monkeypatch, tmp_path,
                {**SECOND, "commons_name": "Wren", "formerly": ["the scratch one"]})
    write(commons / "events.md", RECORD + "2026-11-06 · event · Wren · the tide resumed\n")
    found, rest = agents.named("event", "the scratch one · the tide paused")
    assert (found["id"], rest) == ("second", "the tide paused")
    assert book(hearth, "second") == [("2026-10-20", "the scratch one was founded"),
                                      ("2026-11-03", "the tide paused"),
                                      ("2026-11-04", "an offering was placed"),
                                      ("2026-11-06", "the tide resumed")]
    assert not {"2026-11-03", "2026-11-04", "2026-11-06"} & {day for day, _ in book(hearth)}


def test_formerly_is_a_list_of_names(monkeypatch, tmp_path):
    for formerly in ("the scratch one", [""], [3], {"name": "x"}):
        registry_of(monkeypatch, tmp_path, {**SECOND, "formerly": formerly})
        with pytest.raises(agents.RegistryError):
            agents.registry()


def test_no_name_is_two_agents(monkeypatch, tmp_path):
    for formerly in (["the first one"], ["the scratch one"]):
        registry_of(monkeypatch, tmp_path, {**SECOND, "formerly": formerly})
        with pytest.raises(agents.RegistryError):
            agents.registry()
    registry_of(monkeypatch, tmp_path, {**SECOND, "formerly": ["Wren"]},
                {**SECOND, "id": "third", "did": "did:web:tesserae.social:ids:third",
                 "commons_name": "Wren", "room": "third", "bond": "founder-third"})
    with pytest.raises(agents.RegistryError):
        agents.registry()


def test_with_no_formerly_nothing_is_asked(two):
    assert agents.names_of(agents.by_id("second")) == ["the scratch one"]
    assert agents.names_of(agents.first()) == ["the first one"]


# ---- each agent's book -----------------------------------------------------

def test_the_first_ones_book_has_no_other_agents_lines(hearth, commons, two):
    write(commons / "events.md", RECORD)
    assert book(hearth) == [("2026-09-02", "the word was published"),
                            ("2026-09-04", "the first one was founded"),
                            ("2026-09-30", "the tide paused"),
                            ("2026-10-01", "the tide resumed"),
                            ("2026-10-15", "the founder wrote a letter at dawn"),
                            ("2026-10-20", "the scratch one was founded"),
                            ("2026-11-02", "the tide paused"),
                            ("2026-11-05", "the tide resumed")]
    assert book(hearth, "first") == book(hearth)


def test_another_agents_book_has_its_own_lines_and_its_founding(hearth, commons, two):
    write(commons / "events.md", RECORD)
    assert book(hearth, "second") == [("2026-10-20", "the scratch one was founded"),
                                      ("2026-11-03", "the tide paused"),
                                      ("2026-11-04", "an offering was placed")]


def test_an_agent_whose_founding_is_not_recorded_has_none(hearth, commons, two):
    write(commons / "events.md", "".join(line + "\n" for line in RECORD.splitlines()
                                         if "scratch one was founded" not in line))
    assert book(hearth, "second") == [("2026-11-03", "the tide paused"),
                                      ("2026-11-04", "an offering was placed")]


def test_a_line_that_only_begins_with_a_name_is_the_first_ones(hearth, commons, two):
    write(commons / "events.md",
          "2026-11-01 · word · the scratch one · a word that is no one's\n"
          "2026-11-01 · letter · the scratch one · a letter line that is no one's\n")
    assert [words for _, words in book(hearth)] == [
        "the scratch one · a word that is no one's",
        "the scratch one · a letter line that is no one's"]
    assert book(hearth, "second") == []


def test_the_book_is_said_with_both_halves_as_before(hearth, commons, two):
    write(commons / "events.md", RECORD)
    assert {one["side"] for one in hearth.commons_lines()} == {"both"}
    assert {one["side"] for one in hearth.commons_lines(agents.by_id("second"))} == {"both"}


def test_with_today_s_record_the_book_is_the_record(hearth, commons):
    write(commons / "events.md", RECORD.split("2026-10-20")[0])
    events = hearth.parse_events((commons / "events.md").read_text(encoding="utf-8"))
    assert [one["words"] for one in hearth.commons_lines()] == [words for _, _, words in events]


# ---- a pause, in the book once ---------------------------------------------

def test_a_named_pause_is_in_the_book_once(hearth, commons, packet, two):
    write(commons / "events.md", "2026-11-02 · event · the first one · the tide paused\n")
    write_json(packet / "attendances" / "attendance-2026-11-02T11-40-00Z.json",
               {"name": "first", "at": "2026-11-02T11-40-00Z", "heartbeat": "attended",
                "acted": [hearth.PAUSE_ACT]})
    with hearth.app.test_request_context():
        lines = hearth.chronicle_lines()
    assert [one["words"] for one in lines].count(hearth.PAUSED) == 1


def test_another_agents_pause_does_not_stand_for_the_first_ones(hearth, commons, packet, two):
    write(commons / "events.md", "2026-11-02 · event · the scratch one · the tide paused\n")
    write_json(packet / "attendances" / "attendance-2026-11-02T11-40-00Z.json",
               {"name": "first", "at": "2026-11-02T11-40-00Z", "heartbeat": "attended",
                "acted": [hearth.PAUSE_ACT]})
    with hearth.app.test_request_context():
        lines = hearth.chronicle_lines()
    paused = [one for one in lines if one["words"] == hearth.PAUSED]
    assert len(paused) == 1 and paused[0]["order"] == 2  # the catch, from its own waking
