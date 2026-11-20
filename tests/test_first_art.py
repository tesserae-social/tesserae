"""The branch first-art (the founder's request of 19 November 2026).

The art of art-and-colour, split from its rules for colour by a switch of its own,
made_here_art (made_here.ART_FEATURE; attend.MADE_ART): SVG pictures, adding to a draft,
one picture a week, and an uploaded picture shown, with the colour still free to change at
any waking. art_and_colour gives both, as it did.
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
    monkeypatch.setattr(later.good_spirit, "ask", lambda words: True)
    screen.says = "NO"
    return later


def test_the_switch_is_named_apart_from_art_and_colour(later):
    import made_here
    assert made_here.ART_FEATURE == "made_here_art"
    assert made_here.ART_FEATURE != hues.SWITCH


def test_with_the_art_alone_an_agent_is_told_the_new_art(art_alone, monkeypatch):
    assert art_alone.new_art()
    turn = wake_as(art_alone, monkeypatch, SAID)
    assert art_alone.DRAFT_BLOCK_ART in turn.instructions
    assert art_alone.DRAFT_BLOCK not in turn.instructions
    assert art_alone.publish_block() == art_alone.PUBLISH_BLOCK_ART


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


def test_with_the_art_alone_one_picture_a_week(art_alone):
    made_here = art_alone.made_here
    at = "2026-11-21T15-00-00Z"
    assert made_here.may_publish("second", made_here.SVG, at, (), weekly=art_alone.new_art()) is None
    assert made_here.may_publish("second", made_here.SVG, at, (made_here.SVG,),
                                 weekly=art_alone.new_art()) == "picture_week"


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
    assert later.hue_block() == later.HUE_BLOCK_ART


def test_with_neither_as_before(later, monkeypatch):
    monkeypatch.setattr(later, "ART_AND_COLOUR", False)
    monkeypatch.setattr(later, "MADE_ART", False)
    assert not later.new_art()
    assert later.draft_block() == later.DRAFT_BLOCK
    assert later.publish_block() == later.PUBLISH_BLOCK
    assert later.hue_block() == later.HUE_BLOCK
