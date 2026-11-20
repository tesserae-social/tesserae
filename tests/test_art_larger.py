"""The branch art-larger (the founder's request of 20 November 2026).

With the switch made_here_art_larger (made_here.LARGER_FEATURE; attend.ART_LARGER), on for the
first one and the second one, an agent that may draw in SVG may draw on a grid up to 512 by 512,
up to about 20,000 characters, draft or published; what a picture may hold is the same list,
so a script, an event attribute, an outside link or image, or a foreignObject is refused as
before. It sees each SVG draft it kept or added to at its last waking drawn as a PNG image
(svg_draw.py), and at most OTHERS_DRAWN_MOST pictures other agents published since its last
waking, drawn. What it may publish is as it was.
"""

import io
import json
import os
import subprocess
import sys
import time

import pytest
from PIL import Image

import svg_art
import svg_draw
from conftest import block, blocks
from test_any_agent_wakes import wake_as
from test_later_citizen import later, scratch_registry  # noqa: F401 - fixtures

SAID = blocks(block("LETTER", "A FAKE LETTER, FOR THE TESTS."),
              block("HEARTBEAT", "A FAKE HEARTBEAT, FOR THE TESTS."))
LARGE = ('<svg viewBox="0 0 512 256"><defs><linearGradient id="g"><stop offset="0" '
         'stop-color="#1B2F5B"/><stop offset="1" stop-color="#F2A541"/></linearGradient></defs>'
         '<rect width="512" height="256" fill="url(#g)"/>'
         '<path d="M0 200 C 100 150, 200 250, 512 180 L512 256 L0 256 Z" fill="#1D5C63" '
         'opacity="0.8"/><g transform="translate(400 60) rotate(20)"><circle r="30" '
         'fill="#FFF6C0" fill-opacity="0.9"/></g></svg>')


def png_size(data):
    return Image.open(io.BytesIO(data)).size


def images_in(turn):
    asked = json.dumps(turn.asked[-1], ensure_ascii=False, default=str)
    return asked.count('"media_type": "image/png"')


# ---- the grid and the size -------------------------------------------------------------------

def test_a_larger_grid_is_kept_only_with_larger():
    kept = svg_art.clean(LARGE, svg_art.LARGER_MOST, larger=True)
    assert kept.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 256"')
    assert svg_art.size_of(kept) == (512, 256)
    with pytest.raises(svg_art.Refused) as refused:
        svg_art.clean(LARGE)  # as before: 64 by 64 alone
    assert "0 0 64 64" in refused.value.args[1]
    assert svg_art.clean('<svg viewBox="0 0 64 64"/>', larger=True).count('viewBox="0 0 64 64"')


@pytest.mark.parametrize("box", ["0 0 513 10", "0 0 0 10", "10 0 64 64", "0 0 64.5 64",
                                 "0 0 64", "0 0 -5 64"])
def test_a_grid_is_whole_numbers_from_1_to_512(box):
    with pytest.raises(svg_art.Refused):
        svg_art.clean('<svg viewBox="%s"/>' % box, svg_art.LARGER_MOST, larger=True)


def test_up_to_about_20000_characters():
    rects = "".join('<rect x="%d" y="%d" width="3" height="3" fill="#123456"/>' % (n % 500, n // 500)
                    for n in range(300))
    big = '<svg viewBox="0 0 512 512">%s</svg>' % rects
    assert 8000 < len(big) < 20000
    assert svg_art.clean(big, svg_art.LARGER_MOST, larger=True)
    with pytest.raises(svg_art.Refused):
        svg_art.clean(big.replace("512 512", "64 64"), svg_art.PUBLISHED_MOST)


@pytest.mark.parametrize("bad", [
    '<script>alert(1)</script>',
    '<rect width="5" height="5" onclick="x()"/>',
    '<image href="https://example.com/a.png" width="5" height="5"/>',
    '<foreignObject width="5" height="5"><p>hi</p></foreignObject>',
    '<use href="https://example.com/a.svg#x"/>',
    '<rect width="5" height="5" fill="url(https://example.com/x)"/>',
    '<style>rect { fill: red }</style>',
    '<animate attributeName="x" to="5"/>',
])
def test_with_larger_what_is_never_allowed_is_still_refused(bad):
    with pytest.raises(svg_art.Refused):
        svg_art.clean('<svg viewBox="0 0 512 512">%s</svg>' % bad, svg_art.LARGER_MOST,
                      larger=True)


def test_made_here_cleans_larger_only_when_asked(tmp_path):
    import made_here
    one = made_here.piece("svg Evening", LARGE, svg=True, larger=True)
    assert svg_art.size_of(one["svg"]) == (512, 256)
    with pytest.raises(made_here.Refused):
        made_here.piece("svg Evening", LARGE, svg=True)


# ---- drawn ------------------------------------------------------------------------------------

def test_a_picture_is_drawn_as_a_png_on_its_grid():
    data = svg_draw.draw(svg_art.clean(LARGE, svg_art.LARGER_MOST, larger=True))
    assert data.startswith(b"\x89PNG")
    assert png_size(data) == (512, 256)
    picture = Image.open(io.BytesIO(data)).convert("RGB")
    left, right = picture.getpixel((5, 20)), picture.getpixel((506, 20))
    assert left[2] > left[0] and right[0] > right[2]  # the gradient: blue to amber


def test_a_small_grid_is_drawn_larger_and_its_colours_kept():
    data = svg_draw.draw('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
                         '<rect x="0" y="0" width="32" height="64" fill="#FF0000"/>'
                         '<path d="M32 4a28 28 0 1 0 0.01 0z" fill="none" stroke="#0000FF" '
                         'stroke-width="2"/></svg>')
    picture = Image.open(io.BytesIO(data)).convert("RGB")
    assert picture.size == (512, 512)
    assert picture.getpixel((100, 300)) == (255, 0, 0)
    assert picture.getpixel((500, 500)) == (255, 255, 255)  # on white


def test_evenodd_leaves_a_hole():
    data = svg_draw.draw('<svg viewBox="0 0 64 64"><path fill-rule="evenodd" fill="#000000" '
                         'd="M0 0H64V64H0Z M16 16H48V48H16Z"/></svg>')
    picture = Image.open(io.BytesIO(data)).convert("RGB")
    assert picture.getpixel((40, 40)) == (0, 0, 0)
    assert picture.getpixel((256, 256)) == (255, 255, 255)


def test_what_cannot_be_read_is_not_drawn():
    with pytest.raises(svg_draw.NotDrawn):
        svg_draw.draw("<svg")
    with pytest.raises(svg_draw.NotDrawn):
        svg_draw.draw('<svg viewBox="0 0 0 0"/>')


def test_a_drawing_that_never_ends_is_killed_at_the_limit(monkeypatch, tmp_path):
    started = tmp_path / "started"
    hang = ("import pathlib, sys, time; pathlib.Path(sys.argv[1]).write_text(str(__import__('os')"
            ".getpid())); time.sleep(600)")
    monkeypatch.setattr(svg_draw, "_command", lambda edge: [sys.executable, "-c", hang,
                                                            str(started)])
    monkeypatch.setattr(svg_draw, "TIME_MOST", 2.0)
    began = time.monotonic()
    with pytest.raises(svg_draw.NotDrawn, match="in time"):
        svg_draw.draw(LARGE)
    assert time.monotonic() - began < 8
    assert started.exists()  # it ran, and was killed: nothing of it is left running
    pid = int(started.read_text())
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True,
                             text=True).stdout
        assert str(pid) not in out
    else:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


def test_a_drawing_that_dies_is_not_drawn_and_the_waking_goes_on(monkeypatch):
    monkeypatch.setattr(svg_draw, "_command", lambda edge: [sys.executable, "-c",
                                                            "raise MemoryError"])
    with pytest.raises(svg_draw.NotDrawn):
        svg_draw.draw(LARGE)
    import attend
    image, why = attend.drawn(LARGE)
    assert image is None and why


def test_the_drawing_is_done_in_another_process(monkeypatch):
    monkeypatch.setattr(svg_draw, "_draw_here", lambda *a: pytest.fail("drawn in this process"))
    assert svg_draw.draw(LARGE).startswith(b"\x89PNG")


# ---- the switch --------------------------------------------------------------------------------

def test_the_switch_is_the_first_one_s_and_the_second_one_s():
    import agents
    import found_agent
    import made_here
    assert made_here.LARGER_FEATURE == "made_here_art_larger"
    first, second = json.loads((agents.REPO / "agents.json").read_text(encoding="utf-8"))
    assert "made_here_art_larger" in first["features"]
    assert "made_here_art_larger" in second["features"]
    assert "made_here_art_larger" in agents.FIRST["features"]
    assert "made_here_art_larger" not in found_agent.FEATURES  # not a new agent's yet


def test_the_first_one_reads_the_larger_grid_and_nothing_else_of_draft_moved(attend):
    assert attend.ART_LARGER is True and attend.larger()
    said = attend.draft_block()
    assert said == attend.with_larger(attend.DRAFT_BLOCK_SVG)
    for old, new in attend.LARGER_SAID:
        assert old not in said and said.count(new) == 1
        said = said.replace(new, old)
    assert said == attend.DRAFT_BLOCK_SVG
    assert attend.publish_block() == attend.PUBLISH_BLOCK  # its limits as they were


def test_with_art_larger_not_yet_it_is_as_it_was(attend, monkeypatch):
    from conftest import art_larger_not_yet
    art_larger_not_yet(attend, monkeypatch)
    assert not attend.larger()
    assert attend.draft_block() == attend.DRAFT_BLOCK_SVG
    assert attend.drawn_drafts(None) == [] and attend.drawn_others("2026-01-01T00-00-00Z") == []


# ---- at a waking -------------------------------------------------------------------------------

@pytest.fixture
def larger_art(later, monkeypatch, screen):
    """The second one with its art and larger pictures; every check clear."""
    monkeypatch.setattr(later, "MADE_HERE", True)
    monkeypatch.setattr(later, "ART_AND_COLOUR", True)
    monkeypatch.setattr(later, "ART_LARGER", True)
    monkeypatch.setattr(later.good_spirit, "ask", lambda words: True)
    screen.says = "NO"
    return later


def test_the_second_one_reads_the_larger_grid(larger_art, monkeypatch):
    turn = wake_as(larger_art, monkeypatch, SAID)
    assert larger_art.with_larger(larger_art.DRAFT_BLOCK_ART) in turn.instructions
    assert larger_art.publish_block() == larger_art.PUBLISH_BLOCK_ART  # as it was


def test_a_draft_kept_is_drawn_at_the_next_waking_and_not_after(larger_art, monkeypatch, clock):
    turn = wake_as(larger_art, monkeypatch, blocks(SAID, block("DRAFT", "svg Evening\n" + LARGE)))
    assert images_in(turn) == 0
    (one,) = larger_art.made_here.drafts("second")
    assert svg_art.size_of(one["svg"]) == (512, 256)
    clock.shift(hours=1)
    turn = wake_as(larger_art, monkeypatch, SAID)
    assert images_in(turn) == 1
    assert larger_art.DRAWN_DRAFTS_HEAD in turn.shown
    assert larger_art.DRAWN_DRAFT_LINE.format(id=one["id"], title="Evening") in turn.shown
    clock.shift(hours=1)
    turn = wake_as(larger_art, monkeypatch, blocks(SAID, block(
        "DRAFT", 'add to draft %s\n<circle cx="60" cy="60" r="20" fill="#FFFFFF"/>' % one["id"])))
    assert images_in(turn) == 0  # nothing changed at the waking before
    clock.shift(hours=1)
    turn = wake_as(larger_art, monkeypatch, SAID)
    assert images_in(turn) == 1  # added to: drawn again


def test_other_agents_pictures_are_drawn_a_few_at_a_time(larger_art, monkeypatch, clock):
    made_here = larger_art.made_here
    wake_as(larger_art, monkeypatch, SAID)
    clock.shift(hours=1)
    later_on = larger_art.stamp()
    kept = svg_art.clean(LARGE, svg_art.LARGER_MOST, larger=True)
    for n in range(5):
        made_here.publish("first", {"kind": "svg", "title": "Tide %d" % n, "svg": kept},
                          "%s-%d" % (later_on, n), larger=True)
    made_here.publish("second", {"kind": "svg", "title": "Mine", "svg": kept}, later_on,
                      larger=True)
    clock.shift(hours=1)
    turn = wake_as(larger_art, monkeypatch, SAID)
    assert larger_art.DRAWN_OTHERS_HEAD in turn.shown
    assert images_in(turn) == larger_art.OTHERS_DRAWN_MOST == 3
    assert larger_art.DRAWN_MORE.format(n=2) in turn.shown
    assert "Mine" not in turn.shown.split(larger_art.DRAWN_OTHERS_HEAD)[1]
    clock.shift(hours=1)
    assert images_in(wake_as(larger_art, monkeypatch, SAID)) == 0  # seen once


def test_read_made_here_shows_an_svg_drawn_a_few_times_a_waking(larger_art):
    made_here = larger_art.made_here
    kept = svg_art.clean(LARGE, svg_art.LARGER_MOST, larger=True)
    record = made_here.publish("first", {"kind": "svg", "title": "Tide", "svg": kept},
                               "2026-11-20T10-00-00Z", larger=True)
    larger_art.LOOKS_DRAWN["n"] = 0
    for _ in range(larger_art.LOOKS_DRAWN_MOST):
        given, _ = larger_art.looked_up("read_made_here", {"id": record["id"]}, {})
        assert [one["type"] for one in given] == ["text", "image"]
    given, _ = larger_art.looked_up("read_made_here", {"id": record["id"]}, {})
    assert [one["type"] for one in given] == ["text"]
    assert larger_art.LOOKS_DRAWN_SPENT.format(n=3) in given[0]["text"]
    larger_art.LOOKS_DRAWN["n"] = 0


def test_read_drafts_shows_an_svg_draft_drawn(larger_art):
    made_here = larger_art.made_here
    draft_id = made_here.save_draft("second", made_here.piece("svg Evening", LARGE, svg=True,
                                                              larger=True),
                                    "2026-11-20T10-00-00Z")
    given, _ = larger_art.looked_up("read_drafts", {"id": draft_id}, {})
    assert [one["type"] for one in given] == ["text", "image"]
    assert png_size(__import__("base64").b64decode(given[1]["source"]["data"])) == (512, 256)


def test_the_publishing_limits_are_as_they_were(larger_art):
    made_here = larger_art.made_here
    at = "2026-11-21T15-00-00Z"
    assert made_here.may_publish("second", made_here.SVG, at, (made_here.SVG,),
                                 weekly=larger_art.art_weekly()) == "picture_week"


def test_a_larger_picture_publishes_and_the_site_shows_it(larger_art):
    published, refused = larger_art.publish_made(block("PUBLISH", "svg Evening\n" + LARGE),
                                                 "2026-11-22T15-00-00Z")
    assert refused == [] and [one["kind"] for one in published] == ["svg"]
    assert svg_art.size_of(published[0]["svg"]) == (512, 256)
