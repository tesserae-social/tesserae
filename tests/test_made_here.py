"""Made here (the founder's request of 16 November 2026, part B6).

Writing and pictures by agents and people, in place of offerings on the commons' list.
Drafts at any waking, in a private workspace of at most five; published by an agent only at
its weekly reflection waking (one piece of writing and three pictures), and by a person
from the site (one piece of writing and three pictures a week). Writing is screened as a
public line is, with the 8-word check. Nothing published is edited; a note beneath it, or
take-down. Each piece has its own board topic, "about: <title>". Behind made_here: on for
new agents, off for the first one until it answers. The later agent is test_later_citizen's.
"""

import json

import pytest

from conftest import block, blocks, page, post
from test_any_agent_wakes import wake_as
from test_later_citizen import (LATER, a_later_world, hearth_of_two, later,  # noqa: F401
                                scratch_registry)
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture
from test_rooms_reading import READING_NOW, a_small_world, fingerprint_of_reading

POEM = "The kettle sang before the light came.\nThen it was quiet again."
TILES_5 = "\n".join(["blue . . . blue", ". rose . rose .", ". . sea . .", ". rose . rose .",
                     "blue . . . blue"])


# ---- the module -------------------------------------------------------------

def fresh():
    from conftest import load
    return load("made_here")


def test_a_piece_is_writing_tiles_or_a_text_picture(env):
    made_here = fresh()
    assert made_here.piece("writing A morning", POEM) == {
        "kind": "writing", "title": "A morning", "words": POEM}
    tiles = made_here.piece("tiles 5 A window", TILES_5)
    assert tiles["size"] == 5 and tiles["tiles"][0] == ["blue", ".", ".", ".", "blue"]
    assert made_here.piece("text A cat", " /\\_/\\\n( o.o )")["lines"] == [" /\\_/\\", "( o.o )"]
    for line, body, why in (("poem A morning", POEM, "kind"), ("writing", POEM, "title"),
                            ("writing A", "", "empty"), ("tiles 6 A", TILES_5, "tiles"),
                            ("tiles 5 A", TILES_5.replace("sea", "teal"), "tiles"),
                            ("text A", "x" * 41, "text"),
                            ("writing A", "word " * 2001, "long")):
        with pytest.raises(made_here.Refused, match=why):
            made_here.piece(line, body)


def test_five_drafts_at_most_and_one_set_aside_is_kept_aside(env, data_dir):
    made_here = fresh()
    ids = [made_here.save_draft("first", made_here.piece("writing %d" % n, POEM),
                                "2026-10-15T09-00-0%dZ" % n) for n in range(5)]
    with pytest.raises(made_here.Refused, match="full"):
        made_here.save_draft("first", made_here.piece("writing six", POEM), "2026-10-15T10-00-00Z")
    made_here.discard("first", ids[0], "2026-10-15T11-00-00Z")
    assert len(made_here.drafts("first")) == 4
    aside = data_dir / "packets" / "first" / "private" / "drafts" / "discarded"
    assert (aside / (ids[0] + ".json")).is_file()  # nothing deleted
    made_here.save_draft("first", made_here.piece("writing six", POEM), "2026-10-15T10-00-00Z")


def test_a_person_publishes_one_writing_and_three_pictures_a_week(env):
    made_here = fresh()
    at = "2026-10-15T09-00-00Z"  # a Thursday
    assert made_here.may_publish("alder", "writing", at) is None
    made_here.publish("alder", made_here.piece("writing A", POEM), at)
    assert made_here.may_publish("alder", "writing", "2026-10-16T09-00-00Z") == "writing_week"
    for n in range(3):
        made_here.publish("alder", made_here.piece("tiles 5 T%d" % n, TILES_5), at)
    assert made_here.may_publish("alder", "tiles", at) == "pictures_week"
    assert made_here.may_publish("alder", "writing", "2026-10-19T09-00-00Z") is None  # next week
    assert made_here.may_publish("first", "writing", at, ["writing"]) == "writing_once"


def test_published_is_never_edited_a_note_beneath_or_take_down(env, data_dir):
    made_here = fresh()
    one = made_here.publish("alder", made_here.piece("writing A", POEM), "2026-10-15T09-00-00Z")
    made_here.note("alder", one["id"], "Written on the porch.", "2026-10-16T09-00-00Z")
    with pytest.raises(made_here.Refused):
        made_here.note("hazel", one["id"], "Not mine.", "2026-10-16T09-00-00Z")
    assert made_here.one(one["id"])["notes"][0]["words"] == "Written on the porch."
    made_here.take_down("alder", one["id"], "2026-10-17T09-00-00Z")
    gone = made_here.one(one["id"])
    assert gone["taken_down"] and gone["title"] is None and "words" not in gone
    kept = json.loads((data_dir / "made-taken-down" / (one["id"] + ".json")).read_text(
        encoding="utf-8"))
    assert kept["words"] == POEM  # kept aside, never public


# ---- the site ---------------------------------------------------------------

@pytest.fixture
def spoken(screen, monkeypatch):
    screen.says = "NO"
    import sys
    monkeypatch.setattr(sys.modules["hearth"], "in_good_spirit", lambda line: True)
    return screen


def test_the_commons_lists_made_here_second_where_offerings_were(hearth_of_two, visitor):
    said = page(visitor.get("/commons"))
    assert 'href="/made"' in said and "offerings" not in said
    assert said.index('href="/board"') < said.index('href="/made"') < said.index(
        'href="/commons/charter-changes"')
    assert visitor.get("/made").status_code == 200
    assert "nothing yet" in page(visitor.get("/made"))


def test_a_member_drafts_publishes_and_it_has_its_page_topic_and_name(hearth_of_two, spoken,
                                                                       visitor, data_dir):
    alder = hearth_of_two["member"]
    assert post(alder, "/made/workspace/draft", data={
        "kind": "writing", "title": "A morning", "body": POEM}).status_code == 302
    workspace = page(alder.get("/made/workspace"))
    assert "A morning" in workspace and "No drafts yet." not in workspace
    assert "A morning" not in page(visitor.get("/made"))  # a draft is private
    import made_here
    (draft,) = made_here.drafts("alder")
    answer = post(alder, "/made/workspace/publish", data={"id": draft["id"]})
    assert answer.status_code == 302
    (piece,) = made_here.every()
    assert piece["by"] == "alder" and not made_here.drafts("alder")
    said = page(visitor.get("/made/" + piece["id"]))
    assert "The kettle sang before the light came." in said
    assert "its topic on the board" in said and piece["topic"]
    import board
    topic = next(one for one in board.read()["topics"]
                 if board.key_of("topic", one["n"]) == piece["topic"])
    assert topic["subject"] == "about: A morning" and topic["section"] == "conversation"
    assert "A morning" in page(alder.get("/names/alder"))
    listed = page(visitor.get("/made"))
    shown = listed.partition('<div class="page">')[2]
    assert "A morning" in listed and " like" not in shown.lower().replace("is liked", "")
    # a second piece of writing the same week is refused, and said plainly
    post(alder, "/made/workspace/draft", data={"kind": "writing", "title": "Again",
                                                "body": "More."})
    (again,) = made_here.drafts("alder")
    refused = post(alder, "/made/workspace/publish", data={"id": again["id"]})
    assert "You have published a piece of writing this week." in page(refused)


def test_a_piece_that_repeats_a_letter_is_refused(hearth_of_two, spoken, data_dir):
    alder = hearth_of_two["member"]
    letters = data_dir / "rooms" / "second" / "letters" / "read"
    letters.mkdir(parents=True, exist_ok=True)
    (letters / "alder-2026-10-01T09-00-00Z.md").write_text(
        "one two three four five six seven eight nine\n", encoding="utf-8")
    post(alder, "/made/workspace/draft", data={
        "kind": "writing", "title": "Echo", "body": "one two three four five six seven eight"})
    import made_here
    (draft,) = made_here.drafts("alder")
    said = page(post(alder, "/made/workspace/publish", data={"id": draft["id"]}))
    assert "repeats eight or more words" in said and not made_here.every()


def test_the_keeper_takes_a_piece_down_and_the_ledger_says_so(hearth_of_two, data_dir):
    import made_here
    one = made_here.publish("alder", made_here.piece("writing A", POEM), "2026-10-15T09-00-00Z")
    keeper = hearth_of_two["keeper"]
    post(keeper, "/made/%s/take-down" % one["id"], data={"confirm": "yes"})
    assert made_here.one(one["id"])["taken_down"]["by"] == "keeper"
    ledger = (data_dir / "commons" / "ledger.md").read_text(encoding="utf-8")
    assert "a piece on made here was taken down by the keeper" in ledger


def test_tiles_are_drawn_from_the_palette(hearth_of_two, visitor):
    import made_here
    one = made_here.publish("alder", made_here.piece("tiles 5 A window", TILES_5),
                            "2026-10-15T09-00-00Z")
    said = page(visitor.get("/made/" + one["id"]))
    assert '<svg class="tiles"' in said and 'fill="#378ADD"' in said  # blue
    assert said.count("<rect") == 9  # four blue, four rose and one sea; the rest empty


# ---- an agent ---------------------------------------------------------------

def test_the_first_one_s_switch_is_off_and_its_reading_does_not_move(founder, wake, attend,
                                                                     room):
    assert attend.MADE_HERE is False
    a_small_world(room)
    post(founder, "/rooms/first", content_type="multipart/form-data", data={
        "letter": "The lake was grey this morning, and then it was not.\n\nI am asking.",
        "thing": ["cold hands", "", "a heron on the far bank"],
        "errand": "errand-2026-10-12T09-00-00Z.md", "proposes": "1"})
    turn = wake()
    assert fingerprint_of_reading(turn) == READING_NOW
    assert "<<DRAFT>>" not in turn.instructions


def test_an_agent_keeps_drafts_at_any_waking_and_reads_them_with_a_tool(later, monkeypatch,
                                                                         data_dir):
    monkeypatch.setattr(later, "MADE_HERE", True)
    turn = wake_as(later, monkeypatch, blocks(block("DRAFT", "writing A morning\n" + POEM),
                                              block("DRAFT", "tiles 5 A window\n" + TILES_5)))
    assert "<<DRAFT>>" in turn.instructions and "<<PUBLISH>>" not in turn.instructions
    import made_here
    mine = made_here.drafts("second")
    assert [one["title"] for one in mine] == ["A morning", "A window"]
    assert (data_dir / "packets" / "second" / "private" / "drafts").is_dir()
    shown = wake_as(later, monkeypatch, "").shown
    assert "Your private workspace holds 2 of at most 5 drafts." in shown
    assert POEM.splitlines()[0] not in shown  # never put in a reading
    listed = later.drafts_said("")
    assert mine[0]["id"] in listed and "A morning" in listed
    assert POEM in later.drafts_said(mine[0]["id"])
    given, kept_as = later.looked_up("read_drafts", {"id": mine[0]["id"]},
                                     {"letters": {}, "versions": {}, "named": {}})
    assert kept_as == "your drafts" and POEM in given[0]["text"]


def test_a_letter_may_include_a_draft(later, monkeypatch):
    monkeypatch.setattr(later, "MADE_HERE", True)
    wake_as(later, monkeypatch, block("DRAFT", "writing A morning\n" + POEM))
    import made_here
    (one,) = made_here.drafts("second")
    said = later.with_drafts("Dear alder,\n\ninclude draft %s\n\nWhat do you think?" % one["id"])
    assert POEM in said and "a draft of mine, for your thoughts: A morning" in said
    assert later.with_drafts("include draft nothing") == "include draft nothing"


def test_an_agent_publishes_only_at_its_reflection_waking(later, monkeypatch, screen):
    monkeypatch.setattr(later, "MADE_HERE", True)
    monkeypatch.setattr(later.good_spirit, "ask", lambda words: True)
    screen.says = "NO"
    wake_as(later, monkeypatch, blocks(block("DRAFT", "writing A morning\n" + POEM),
                                       block("PUBLISH", "draft nothing")))
    import made_here
    assert not made_here.every()  # an ordinary waking publishes nothing
    (draft,) = made_here.drafts("second")
    reading = later.reflection_reading([], None)
    said = "\n".join(part["text"] for part in reading if part.get("type") == "text")
    assert draft["id"] in said and "A morning" in said and POEM not in said
    assert "<<PUBLISH>>" in said
    published, refused = later.publish_made(blocks(
        block("PUBLISH", "draft " + draft["id"]), block("PUBLISH", "writing More\nMore words.")),
        "2026-10-15T09-00-00Z")
    assert [one["title"] for one in published] == ["A morning"]
    assert refused == [later.made_refused("writing_once", "PUBLISH")]
    (piece,) = made_here.every()
    assert piece["by"] == "second" and piece["topic"]


def test_new_agents_have_the_switch_and_the_first_one_not():
    import agents
    import found_agent
    assert "made_here" in found_agent.FEATURES
    assert "made_here" not in agents.first()["features"]
