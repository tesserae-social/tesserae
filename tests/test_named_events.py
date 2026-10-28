"""Lines of the record named for an agent, read before any is written.

Stage 6a-i of the work that lets the tide wake more than one agent (the stage 6
proposal, 27 October 2026). From 6a-ii on, a pause, a stop, a release, an
offering and a seal will carry the commons name of the agent they are for,
first, with a middot after it:

    2026-11-02 · event · the first one · the tide paused

Here the readers learn that shape: agents.named(), and each agent's book
(hearth.commons_lines). In 6a-ii the writers name the agent too
(agents.event_words): attend.py at a rest of its own and at a release, the
hearth at a stop, its lifting and a rest ended, and offering.py at a placing. A
seal names both parties in its words already, so nothing goes before them. The
word, a founding, the founder's letters and the bench are never named. The
first one's reading is the reading it was, held by READING_NOW; the tide's
fingerprint was cut again for its three named lines.

The second agent is made only in a scratch registry.
"""

import json
from datetime import date

import pytest

import agents
import bonds
from conftest import block, blocks, lines_of, page, post, read_json, write, write_json
from test_any_agent_wakes import SAID, scratch_registry, second, wake_as  # noqa: F401
from test_hearth_bonds import sealed

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
    for words in ("the first one was founded", "the first one", "the first ones · paused"):
        assert agents.named("event", words) is None
        assert agents.named("seal", words) is None
    # a seal's own sentence names its agent at the end, and only a seal's
    assert agents.named("event", "a bond was sealed between the founder and the first one") is None


# ---- a seal, named by its own words ----------------------------------------

def test_a_seal_is_the_agents_whose_name_ends_it(two):
    for words, whose in [("a bond was sealed between the founder and the first one", "first"),
                         ("a bond was sealed between the founder and the scratch one", "second"),
                         ("a bond was sealed between Mira and the scratch one", "second")]:
        found, rest = agents.named("seal", words)
        assert (found["id"], rest) == (whose, words)  # the sentence whole: the name is in it


def test_a_seal_is_read_only_as_a_seal(two):
    for words in ("a bond was sealed between the founder and the scratch one and more",
                  "a bond was sealed between the scratch one and the founder",
                  "a bond was sealed between the founder andthe scratch one",
                  "a bond was made between the founder and the scratch one",
                  "the bond with the scratch one"):
        assert agents.named("seal", words) is None, words
    for kind in ("event", "offering", "word", "founding", "letter"):
        assert agents.named(kind, "a bond was sealed between the founder and the scratch one") \
            is None


def test_a_seal_under_a_name_from_before_stays_its(monkeypatch, tmp_path):
    registry_of(monkeypatch, tmp_path,
                {**SECOND, "commons_name": "Wren", "formerly": ["the scratch one"]})
    found, _ = agents.named("seal", "a bond was sealed between the founder and the scratch one")
    assert found["id"] == "second"


def test_the_longest_name_ends_a_seal_first(monkeypatch, tmp_path):
    registry_of(monkeypatch, tmp_path, {**SECOND, "commons_name": "the other first one"})
    found, _ = agents.named("seal", "a bond was sealed between the founder and the other first one")
    assert found["id"] == "second"
    found, _ = agents.named("seal", "a bond was sealed between the founder and the first one")
    assert found["id"] == "first"


SEALS = ("2026-10-08 · seal · a bond was sealed between the founder and the first one\n"
         "2026-11-08 · seal · a bond was sealed between the founder and the scratch one\n")


def test_another_agents_seal_is_in_its_book_and_not_the_first_ones(hearth, commons, two):
    write(commons / "events.md", RECORD + SEALS)
    first, second = book(hearth), book(hearth, "second")
    assert first[-1] == ("2026-10-08", "a bond was sealed between the founder and the first one")
    assert not any("scratch one" in words for day, words in first if day == "2026-11-08")
    assert second[-1] == ("2026-11-08",
                          "a bond was sealed between the founder and the scratch one")
    assert not any(day == "2026-10-08" for day, _ in second)


def test_the_first_ones_seal_reads_in_its_book_as_it_always_has(hearth, commons):
    """With the first one alone, as today, the book is the record word for word."""
    write(commons / "events.md", RECORD.split("2026-10-20")[0] + SEALS.splitlines(True)[0])
    events = hearth.parse_events((commons / "events.md").read_text(encoding="utf-8"))
    assert [one["words"] for one in hearth.commons_lines()] == [words for _, _, words in events]
    assert book(hearth)[-1] == ("2026-10-08",
                                "a bond was sealed between the founder and the first one")


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


# ---- the writers name the agent --------------------------------------------

def test_the_first_ones_words_are_named_for_it(attend, hearth):
    assert attend.PAUSED == "the first one · the tide paused"
    assert hearth.agent_words(hearth.PAUSED) == "the first one · the tide paused"
    assert hearth.agent_words(hearth.RESUMED, "first") == "the first one · the tide resumed"
    # a seal names both already, and is said as it always was
    assert attend.SEALED == "a bond was sealed between the founder and the first one"
    assert bonds.sealed_words({"parties": [attend.FIRST_DID, attend.FOUNDER_DID]}) == (
        attend.SEALED)


def test_what_it_is_told_of_a_release_says_its_name_is_on_it(attend):
    for told in (attend.RELEASE_BLOCK, attend.BOND_RELEASED):
        said = " ".join(told.split())
        assert "no names" not in said
        assert ("a bond was released, with your commons name and no reason, and nothing else of "
                "either of you or of the bond.") in said.replace("released -", "released,")


def test_the_founder_is_told_the_release_names_the_first_one(founder, wake, room, clock):
    sealed(founder, wake, room, clock)
    said = " ".join(page(post(founder, "/bonds/release")).split())
    assert ("the commons will say that a bond was released - naming the first one, with no "
            "reason, and nothing else of you or the bond. It cannot be undone.") in said
    assert "no names" not in said


def test_a_scratch_agents_rest_and_offering_carry_its_name(second, commons, monkeypatch):
    before = lines_of(commons / "events.md")
    wake_as(second, monkeypatch, blocks(SAID, block("PAUSE", "pause until a letter arrives\n"
                                                    "A FAKE REST, FOR THE TESTS.")))
    # offering.py's day is its own clock's, which the waking does not pin: the words are held
    written = [line.split(" · ", 1)[1] for line in lines_of(commons / "events.md")[len(before):]]
    assert written == ["offering · the scratch one · an offering was placed",
                       "event · the scratch one · the tide paused"]
    assert second.PAUSED == "the scratch one · the tide paused"
    assert second.SEALED == "a bond was sealed between the founder and the scratch one"


def test_a_scratch_agents_release_carries_its_name(second, commons, data_dir, monkeypatch):
    bond = {"parties": [second.FOUNDER_DID, second.DID], "terms": "the charter",
            "proposed_by": second.FOUNDER_DID, "proposed_at": "2026-10-01T09-00-00Z",
            "answered_at": "2026-10-02T09-00-00Z", "opened_at": "2026-10-02T09-00-00Z",
            "sealed_at": "2026-10-10T09-00-00Z", "signatures": {"founder": "x", "second": "x"}}
    write_json(data_dir / "rooms" / "second" / "bonds" / "founder-second.json", bond)
    wake_as(second, monkeypatch, block("RELEASE", "release\nA FAKE RELEASE, FOR THE TESTS."))
    assert read_json(data_dir / "rooms" / "second" / "bonds" / "founder-second.json")[
        "released_by"] == second.DID
    assert lines_of(commons / "events.md")[-1] == (
        "2026-10-15 · event · the scratch one · a bond was released")
    assert "A FAKE RELEASE" not in (commons / "events.md").read_text(encoding="utf-8")


def test_each_agents_stop_carries_its_own_name(hearth, commons, two):
    before = lines_of(commons / "events.md")
    hearth.begin_stop("A fault.", of="second")
    hearth.end_stop(of="second")
    hearth.begin_stop("A fault.")
    hearth.end_stop()
    written = lines_of(commons / "events.md")[len(before):]
    assert written == ["2026-10-15 · event · the scratch one · the tide paused",
                       "2026-10-15 · event · the scratch one · the tide resumed",
                       "2026-10-15 · event · the first one · the tide paused",
                       "2026-10-15 · event · the first one · the tide resumed"]
    # and each is read back as its own agent's
    named = [agents.named("event", line.split(" · ", 2)[2]) for line in written]
    assert [(agent["id"], words) for agent, words in named] == [
        ("second", "the tide paused"), ("second", "the tide resumed"),
        ("first", "the tide paused"), ("first", "the tide resumed")]


def test_the_word_a_founding_a_letter_and_the_bench_stay_unnamed(hearth, commons, two):
    write(commons / "events.md", "2026-09-02 · word · the word was published\n"
                                 "2026-09-04 · founding · the first one was founded\n")
    assert hearth.note_letter()
    hearth.place_line("2026-10-15", "a visitor", "A FAKE LINE, FOR THE TESTS.")
    assert hearth.take_off(hearth.bench_lines()[0]["raw"])
    written = lines_of(commons / "events.md")
    assert [line.split(" · ")[1] for line in written] == ["word", "founding", "letter", "event"]
    assert written[2].startswith("2026-10-15 · letter · the founder wrote a letter")
    assert written[3] == "2026-10-15 · event · " + hearth.TAKEN_OFF
    for line in written:
        day, kind, words = line.split(" · ", 2)
        assert agents.named(kind, words) is None, line
