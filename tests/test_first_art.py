"""The branch first-art (the founder's request of 19 November 2026).

A switch of its own, made_here_art (made_here.ART_FEATURE; attend.MADE_ART), gives the SVG
drawing of art-and-colour alone: svg <title> and add to draft <id>, in <<DRAFT>> as it was
with those lines added. What may be published at a reflection waking stays as it was (one
piece of writing and up to 3 pictures), <<PUBLISH>> is as it was, an uploaded picture is
said in words, a piece gets its "about: <title>" topic in conversation where made_here_agents
is off, and the colour is still free to change at any waking. art_and_colour gives all of
the art and the rules for colour, as it did.
"""

from datetime import datetime, timezone

import pytest

import hues
from conftest import block, blocks
from test_any_agent_wakes import wake_as
from test_later_citizen import later, scratch_registry  # noqa: F401 - fixtures

SAID = blocks(block("LETTER", "A FAKE LETTER, FOR THE TESTS."),
              block("HEARTBEAT", "A FAKE HEARTBEAT, FOR THE TESTS."))
SVG = '<svg viewBox="0 0 64 64"><rect width="64" height="64" fill="#1B2F5B"/></svg>'


def choosing(colour):
    return SAID + "\n" + block("HUE", colour)


@pytest.fixture
def art_alone(later, monkeypatch, screen):
    """An agent with made here and made_here_art, without art_and_colour; every check clear."""
    monkeypatch.setattr(later, "MADE_HERE", True)
    monkeypatch.setattr(later, "ART_AND_COLOUR", False)
    monkeypatch.setattr(later, "MADE_ART", True)
    monkeypatch.setattr(later, "MADE_AGENTS_ONLY", False)  # as the first one has it
    monkeypatch.setattr(later.good_spirit, "ask", lambda words: True)
    screen.says = "NO"
    return later


def test_the_switch_is_named_apart_from_art_and_colour(later):
    import made_here
    assert made_here.ART_FEATURE == "made_here_art"
    assert made_here.ART_FEATURE != hues.SWITCH


def test_with_the_svg_drawing_alone_draft_is_the_block_it_had_with_svg_added(art_alone, monkeypatch):
    assert art_alone.new_art() and not art_alone.art_weekly()
    turn = wake_as(art_alone, monkeypatch, SAID)
    assert art_alone.DRAFT_BLOCK_SVG in turn.instructions
    assert art_alone.DRAFT_BLOCK_ART not in turn.instructions
    said = art_alone.DRAFT_BLOCK_SVG
    for added in (art_alone.SVG_KIND_LINE, art_alone.ADD_TO_DRAFT_LINE, art_alone.SVG_SAID):
        assert said.count(added) == 1
        said = said.replace(added, "", 1)
    assert said == art_alone.DRAFT_BLOCK  # only added: nothing of the block it had is gone
    assert art_alone.publish_block() == art_alone.PUBLISH_BLOCK
    assert art_alone.made_body({"kind": art_alone.made_here.PHOTO}) == art_alone.MADE_PHOTO_SAID


def test_with_the_art_alone_an_agent_drafts_an_svg_and_adds_to_it(art_alone, monkeypatch, clock):
    wake_as(art_alone, monkeypatch, blocks(SAID, block("DRAFT", "svg Night\n" + SVG)))
    (one,) = art_alone.made_here.drafts("second")
    assert one["kind"] == "svg"
    clock.shift(hours=1)
    wake_as(art_alone, monkeypatch, blocks(SAID, block(
        "DRAFT", "add to draft %s\n<circle cx=\"48\" cy=\"14\" r=\"6\" fill=\"#F3E9D2\"/>"
        % one["id"])))
    (one,) = art_alone.made_here.drafts("second")
    assert one["svg"].endswith('<circle cx="48" cy="14" r="6" fill="#F3E9D2"/></svg>')


def test_with_the_svg_drawing_alone_the_limits_are_as_they_were(art_alone):
    made_here = art_alone.made_here
    at = "2026-11-21T15-00-00Z"
    weekly = art_alone.art_weekly()
    assert weekly is False
    assert made_here.may_publish("second", made_here.SVG, at, (made_here.SVG,) * 2,
                                 weekly=weekly) is None  # a third picture at one waking
    assert made_here.may_publish("second", made_here.SVG, at, (made_here.SVG,) * 3,
                                 weekly=weekly) == "pictures_once"
    assert made_here.may_publish("second", made_here.WRITING, at, (made_here.SVG,) * 3,
                                 weekly=weekly) is None
    assert made_here.may_publish("second", made_here.WRITING, at, (made_here.WRITING,),
                                 weekly=weekly) == "writing_once"


def test_with_the_svg_drawing_alone_a_reflection_publishes_three_pictures_each_with_its_topic(
        art_alone):
    import board
    pieces = [block("PUBLISH", "svg Night %d\n%s" % (n, SVG)) for n in (1, 2, 3, 4)]
    pieces.append(block("PUBLISH", "writing A week\nIt was long, and then it was not."))
    published, refused = art_alone.publish_made(blocks(*pieces), "2026-11-22T15-00-00Z")
    assert [one["kind"] for one in published] == ["svg", "svg", "svg", "writing"]
    assert refused == [art_alone.MADE_REFUSED["pictures_once"].format(tag="PUBLISH")]
    started = [topic["subject"] for topic in board.topics(
        art_alone.CHARTER_CHANGES, [], "2026-11-22", (board.CONVERSATION,))]
    for title in ("Night 1", "Night 2", "Night 3", "A week"):
        assert "about: " + title in started


def test_with_the_art_alone_the_colour_is_free_at_any_waking(art_alone, monkeypatch, clock):
    clock.set(datetime(2026, 11, 21, 15, 0, tzinfo=timezone.utc))  # in no equinox week
    turn = wake_as(art_alone, monkeypatch, choosing("#3A7BD5"))
    assert art_alone.HUE_BLOCK in turn.shown and art_alone.HUE_BLOCK_ART not in turn.shown
    assert hues.colour_of("second") == "#3A7BD5"
    clock.shift(minutes=5)
    turn = wake_as(art_alone, monkeypatch, choosing("#2E5EAA"))
    assert "<<HUE>>" in turn.instructions  # still offered, out of season
    assert "You may change it next" not in turn.shown
    assert hues.colour_of("second") == "#2E5EAA"
    clock.shift(minutes=5)
    wake_as(art_alone, monkeypatch, choosing("#F2A541"))  # barely shows: taken, as before
    assert hues.colour_of("second") == "#F2A541"


def test_art_and_colour_still_gives_both(later, monkeypatch):
    monkeypatch.setattr(later, "ART_AND_COLOUR", True)
    monkeypatch.setattr(later, "MADE_ART", False)
    assert later.new_art() and later.draft_block() == later.DRAFT_BLOCK_ART
    assert later.art_weekly() and later.publish_block() == later.PUBLISH_BLOCK_ART
    assert later.hue_block() == later.HUE_BLOCK_ART


def test_with_neither_as_before(later, monkeypatch):
    monkeypatch.setattr(later, "ART_AND_COLOUR", False)
    monkeypatch.setattr(later, "MADE_ART", False)
    assert not later.new_art()
    assert later.draft_block() == later.DRAFT_BLOCK
    assert later.publish_block() == later.PUBLISH_BLOCK
    assert later.hue_block() == later.HUE_BLOCK


# ---- the first one's switches (part 2: for if it says yes) ------------------------------

def test_the_first_one_has_the_svg_drawing_alone_and_its_colour_stays_free(attend):
    assert attend.MADE_ART is True and attend.MADE_AGENTS_ONLY is False
    assert attend.ART_AND_COLOUR is False  # no equinox weeks, no check of showing
    assert attend.new_art() and not attend.art_weekly()
    # since art-larger (20 November 2026) with the larger grid said (attend.with_larger)
    assert attend.draft_block() == attend.with_larger(attend.DRAFT_BLOCK_SVG)
    assert attend.publish_block() == attend.PUBLISH_BLOCK  # its limits as they were
    assert attend.hue_block() == attend.HUE_BLOCK
    assert "You may choose again at any later waking." in attend.hue_block()


def test_with_first_art_not_yet_the_first_one_is_as_it_was(attend, monkeypatch):
    from conftest import first_art_not_yet
    first_art_not_yet(attend, monkeypatch)
    assert not attend.new_art() and attend.MADE_AGENTS_ONLY is False
    assert attend.draft_block() == attend.DRAFT_BLOCK
    assert attend.publish_block() == attend.PUBLISH_BLOCK
