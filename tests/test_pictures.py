"""A picture the first one drew: what is kept of it, and how it is handed out.

A picture arrives as SVG, which is a document and not a photograph: it can hold
a script, a stylesheet, a reference to somewhere else. So what is saved is never
what arrived - the shapes are read out of it and written again, and everything
else is dropped. These check that the dropping is real, and that what is served
afterwards is served under locks as well.
"""

import pytest

from conftest import block, blocks, lines_of, page, read_json, write

DRAWN = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
         '<rect x="0" y="0" width="12" height="12" fill="#D85A30"/></svg>')


def picture(packet, at):
    return packet / "letters" / "outgoing" / ("to-founder-%s.svg" % at)


def letter(packet, at):
    return packet / "letters" / "outgoing" / ("to-founder-%s.md" % at)


# ---- what is kept of a picture -------------------------------------------

def test_the_shapes_are_kept(attend):
    kept = attend.picture_drawn(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        "<title>a tile</title>"
        '<g transform="translate(1,1)">'
        '<rect x="1" y="2" width="3" height="4" rx="1" fill="#D85A30" fill-opacity="0.5"/>'
        '<circle cx="5" cy="5" r="2" stroke="#000" stroke-width="2" stroke-linecap="round"/>'
        '<ellipse cx="1" cy="1" rx="2" ry="3"/><line x1="0" y1="0" x2="9" y2="9"/>'
        '<polyline points="0,0 1,1"/><polygon points="2,2 3,3 4,2"/>'
        '<path d="M0 0 L10 10" stroke-linejoin="miter" opacity="0.9" stroke-opacity="0.2"/>'
        '<text x="1" y="2" font-size="4" font-family="Georgia" text-anchor="middle">hi</text>'
        "</g></svg>")
    for shape in ("<title>", "<g ", "<rect ", "<circle ", "<ellipse ", "<line ", "<polyline ",
                  "<polygon ", "<path ", "<text "):
        assert shape in kept, shape
    for attribute in ("viewBox=", "transform=", "rx=", "fill-opacity=", "stroke-width=",
                      "stroke-linecap=", "stroke-linejoin=", "opacity=", "stroke-opacity=",
                      "font-size=", "font-family=", "text-anchor=", "points=", "d="):
        assert attribute in kept, attribute
    assert 'xmlns="http://www.w3.org/2000/svg"' in kept
    assert ">hi<" in kept


@pytest.mark.parametrize("drawn, gone", [
    ('<svg><script>alert(1)</script><rect/></svg>', "alert"),
    ('<svg><rect onclick="steal()"/></svg>', "onclick"),
    ('<svg><rect onload="x()"/></svg>', "onload"),
    ('<svg><a href="https://elsewhere"><circle/></a><rect/></svg>', "elsewhere"),
    ('<svg xmlns:xlink="http://www.w3.org/1999/xlink">'
     '<use xlink:href="#x"/><rect/></svg>', "use"),
    ('<svg><image href="https://elsewhere/x.png"/><rect/></svg>', "image"),
    ('<svg><foreignObject><b>hello</b></foreignObject><rect/></svg>', "hello"),
    ('<svg><rect style="background:url(https://elsewhere)"/></svg>', "style"),
    ('<svg><rect fill="url(#gradient)"/></svg>', "url("),
    ('<svg><rect fill="url(https://elsewhere/x)"/></svg>', "elsewhere"),
    ('<svg><text font-family="javascript:x">hi</text></svg>', "javascript"),
    ('<svg><style>rect{fill:red}</style><rect/></svg>', "style"),
    ('<svg><animate attributeName="x"/><rect/></svg>', "animate"),
    ('<svg><linearGradient id="g"><stop offset="0"/></linearGradient><rect/></svg>', "stop"),
])
def test_what_is_not_a_shape_is_dropped(attend, drawn, gone):
    kept = attend.picture_drawn(drawn)
    assert kept is not None, "the picture itself should survive its cleaning"
    assert gone not in kept
    assert "<rect" in kept or "<text" in kept  # and the shape beside it is still there


def test_a_dropped_element_takes_what_is_inside_it(attend):
    """A drop that left the children behind would be no drop at all."""
    kept = attend.picture_drawn(
        '<svg><a href="https://elsewhere"><circle cx="1" cy="1" r="1"/></a>'
        '<rect x="0" y="0" width="1" height="1"/></svg>')
    assert "<circle" not in kept
    assert "<rect" in kept


@pytest.mark.parametrize("said", [
    "",
    None,
    "I would rather write than draw.",
    "<g><rect/></g>",                       # an outermost element that is not an svg
    "<svg><rect/>",                         # never closed
    '<!DOCTYPE svg [<!ENTITY a "b">]><svg><rect/></svg>',
    "<svg><rect fill='></svg>",             # will not parse at all
])
def test_what_is_not_a_picture_is_no_picture(attend, said):
    assert attend.picture_drawn(said) is None


def test_a_picture_larger_than_a_picture_should_be_is_refused(attend):
    small = '<svg><rect fill="#D85A30"/>%s</svg>'
    assert attend.picture_drawn(small % ("<rect/>" * 100)) is not None
    too_much = small % ("<rect/>" * (attend.PICTURE_LIMIT // 7))
    assert len(too_much.encode("utf-8")) > attend.PICTURE_LIMIT
    assert attend.picture_drawn(too_much) is None


def test_the_saved_picture_is_written_again_and_never_the_text_that_came(attend):
    """What is saved is built from the shapes that were kept, not edited in place."""
    kept = attend.picture_drawn(
        'here is a picture:\n<svg  ><rect   onclick="x()"   fill="#D85A30" /></svg>\nthere')
    assert kept == ('<svg xmlns="http://www.w3.org/2000/svg">'
                    '<rect fill="#D85A30" /></svg>')


# ---- one waking that draws -----------------------------------------------

def acts(packet):
    """What the most recent waking carried out."""
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])["acted"]


def test_a_picture_is_kept_beside_the_letter_of_that_waking(wake, packet, clock, attend):
    at = clock.stamp()
    wake(blocks(block("LETTER", "Here is what I saw."), block("PICTURE", DRAWN)))
    assert letter(packet, at).read_text(encoding="utf-8") == "Here is what I saw.\n"
    assert "<rect" in picture(packet, at).read_text(encoding="utf-8")
    assert acts(packet) == ["wrote a letter to the founder", attend.PICTURE_ACT]


def test_a_picture_with_no_letter_stands_alone_behind_one_line(wake, packet, clock, attend):
    at = clock.stamp()
    wake(block("PICTURE", DRAWN))
    assert letter(packet, at).read_text(encoding="utf-8") == attend.ONLY_A_PICTURE + "\n"
    assert picture(packet, at).exists()
    # the line is not a letter it wrote, and is not counted as one
    assert acts(packet) == [attend.PICTURE_ACT]


def test_a_picture_that_is_refused_writes_nothing_at_all(wake, packet, clock):
    at = clock.stamp()
    wake(block("PICTURE", "<script>alert(1)</script>"))
    assert not picture(packet, at).exists()
    assert not letter(packet, at).exists()


def test_the_picture_block_is_offered_at_every_waking(wake):
    said = wake().instructions
    assert "<<PICTURE>>" in said
    assert "at most 20 KB" in said
    assert "as a photograph of his is shown to you" in said


def test_drawing_is_the_first_one_s_own_to_tell(wake, commons, attend):
    """A private act: the line the commons is given says nothing of it."""
    wake(block("PICTURE", DRAWN))
    assert lines_of(commons / "heartbeats.md")[-1].endswith("the first one · attended")
    assert attend.PICTURE_ACT in attend.PRIVATE_ACTS


def test_a_picture_is_named_where_its_letter_is_read_back(wake, packet, clock):
    at = clock.stamp()
    wake(blocks(block("LETTER", "Here is what I saw."), block("PICTURE", DRAWN)))
    assert "(a picture of yours was drawn beside this letter)" in wake().opening
    assert "to-founder-%s.md" % at in wake().opening


# ---- the picture, served -------------------------------------------------

def test_a_picture_is_served_to_the_founder_alone_and_under_locks(founder, visitor, packet,
                                                                  clock, hearth):
    write(picture(packet, clock.stamp()), DRAWN)
    name = "to-founder-%s.svg" % clock.stamp()

    answer = founder.get("/letters/picture/" + name)
    assert answer.status_code == 200
    assert answer.mimetype == "image/svg+xml"
    assert answer.headers["Content-Security-Policy"] == "sandbox"
    assert answer.headers["X-Content-Type-Options"] == "nosniff"
    assert "<rect" in page(answer)

    turned = visitor.get("/letters/picture/" + name)
    assert turned.status_code == 302
    assert "/login" in turned.headers["Location"]


@pytest.mark.parametrize("asked", [
    "notes.md", "..%2F..%2Fself.md", "nothing-here.svg", "to-founder.jpg",
])
def test_only_a_picture_of_a_letter_is_served(founder, asked):
    assert founder.get("/letters/picture/" + asked).status_code == 404


def test_the_founder_s_own_folders_hold_no_pictures_to_serve(founder, packet, hearth):
    """A picture is the first one's; nothing is served out of the letters it is sent."""
    write(packet / "letters" / "incoming" / "founder-2026-10-14T09-00-00Z.svg", DRAWN)
    assert founder.get("/letters/picture/founder-2026-10-14T09-00-00Z.svg").status_code == 404
    assert hearth.PICTURE_FOLDERS == (hearth.OUTGOING,)


def test_a_picture_appears_inside_the_letter_it_came_with(founder, packet, clock):
    stem = "to-founder-2026-10-14T09-00-00Z"
    write(packet / "letters" / "outgoing" / (stem + ".md"), "Here is what I saw.\n")
    write(packet / "letters" / "outgoing" / (stem + ".svg"), DRAWN)
    said = page(founder.get("/letters"))
    assert '<img class="photo" src="/letters/picture/%s.svg"' % stem in said
    assert 'alt="the picture the first one drew beside this letter"' in said
