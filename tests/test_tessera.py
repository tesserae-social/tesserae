"""The tessera: a break drawn from a bond's two signatures, and the pictures of it.

Everything here is pure, so nothing here touches a data directory or a clock.
"""

import base64
import hashlib
import xml.etree.ElementTree as ET

import pytest

import tessera

FOUNDER_DID = "did:web:tesserae.social:ids:founder"
FIRST_DID = "did:web:tesserae.social:ids:first"

# A fixed pair of signatures, in the form a bond keeps them: base64 text of 64
# bytes. They are not real signatures over anything; the recipe does not care.
FOUNDER_SIG = ("k/tPQmboeXu6PD8NSTKzphJI/GTEBySQ8M2jhpIUQFk5PaKcwgKslzXCWFx07z/"
               "NuheqnxKtYw/zf3buA8GElA==")
FIRST_SIG = ("yHK4123e1P7wUImcOw0q2IXxnRa9Qni7i5w4FWOCSKXa0+ufKTIkxGHlEdu1GDIwqwp"
             "II/58zy6vGSY96mHKeQ==")

PARTIES = ((FOUNDER_DID, FOUNDER_SIG), (FIRST_DID, FIRST_SIG))
SWAPPED = ((FIRST_DID, FIRST_SIG), (FOUNDER_DID, FOUNDER_SIG))

# The break the pinned pair gives under tessera-v1. If this changes, the recipe
# has changed, and every tile already drawn would be drawn differently: a new
# recipe is a new version, beside this one, never an edit to it.
PINNED = [(0.3777, 0.0), (0.3238, 0.125), (0.4865, 0.25), (0.418, 0.375), (0.432, 0.5),
          (0.4282, 0.625), (0.3548, 0.75), (0.4533, 0.875), (0.4076, 1.0)]

ALLOWED = {"svg", "polygon", "rect"}
SVG_NS = "{http://www.w3.org/2000/svg}"


def sig(text):
    """A made-up signature, as a bond would keep it."""
    return base64.b64encode(hashlib.sha512(text.encode()).digest()).decode("ascii")


def pictures(parties, size, seam_fill=None):
    """Every picture the module draws, for one pair at one size."""
    return {
        "rejoined": tessera.svg_rejoined(parties, size, "#b5651d", "#2e5e4e", seam_fill),
        "left": tessera.svg_half(parties, "left", size, "#b5651d"),
        "right": tessera.svg_half(parties, "right", size, "#2e5e4e"),
        "apart": tessera.svg_apart(parties, size, "#b5651d", "#2e5e4e"),
    }


def polygons(picture):
    """Each polygon of a picture, as its fill and its list of points."""
    root = ET.fromstring(picture)
    found = []
    for element in root.iter(SVG_NS + "polygon"):
        points = [tuple(float(n) for n in pair.split(","))
                  for pair in element.get("points").split()]
        found.append((element.get("fill"), points))
    return found


# ---- the recipe ----------------------------------------------------------

def test_the_pinned_pair_gives_the_pinned_break():
    assert tessera.break_line(PARTIES) == PINNED


def test_the_seed_is_the_version_and_both_signatures_left_first():
    # "did:...:first" sorts before "did:...:founder", so the first one is left
    expected = hashlib.sha256(b"tessera-v1" + base64.b64decode(FIRST_SIG)
                              + base64.b64decode(FOUNDER_SIG)).digest()
    assert tessera.seed(PARTIES) == expected
    assert tessera.ordered(PARTIES)[0][0] == FIRST_DID


def test_the_same_inputs_give_the_same_output():
    assert tessera.break_line(PARTIES) == tessera.break_line(PARTIES)
    assert pictures(PARTIES, 240, "#f4ecd8") == pictures(PARTIES, 240, "#f4ecd8")
    assert tessera.verify_text(PARTIES) == tessera.verify_text(PARTIES)


def test_swapping_the_parties_gives_the_same_tile():
    assert tessera.break_line(SWAPPED) == tessera.break_line(PARTIES)
    for size in (8, 240):
        assert pictures(SWAPPED, size, "#f4ecd8") == pictures(PARTIES, size, "#f4ecd8")
    assert tessera.verify_text(SWAPPED) == tessera.verify_text(PARTIES)


def test_different_signatures_give_different_breaks():
    lines = {tuple(tessera.break_line(((FOUNDER_DID, sig("founder %d" % i)),
                                       (FIRST_DID, sig("first %d" % i)))))
             for i in range(50)}
    assert len(lines) == 50
    # one signature changed is enough
    assert (tessera.break_line(((FOUNDER_DID, FOUNDER_SIG), (FIRST_DID, sig("other"))))
            != PINNED)


def test_which_signature_is_whose_matters():
    crossed = ((FOUNDER_DID, FIRST_SIG), (FIRST_DID, FOUNDER_SIG))
    assert tessera.break_line(crossed) != PINNED


@pytest.mark.parametrize("i", range(200))
def test_every_point_is_in_bounds(i):
    points = tessera.break_line(((FOUNDER_DID, sig("a%d" % i)), (FIRST_DID, sig("b%d" % i))))
    assert len(points) == 9
    ys = [y for _, y in points]
    assert ys == [round(k / 8, 4) for k in range(9)]
    assert all(a < b for a, b in zip(ys, ys[1:]))
    assert 0.3 <= points[0][0] <= 0.7 and points[0][1] == 0.0
    assert 0.3 <= points[-1][0] <= 0.7 and points[-1][1] == 1.0
    assert all(0.1 <= x <= 0.9 for x, _ in points[1:-1])
    assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in points)
    assert all(round(x, 4) == x for x, _ in points)


def test_the_stream_extends_by_hashing_the_seed_with_a_counter():
    start = hashlib.sha256(b"x").digest()
    got = tessera.stream(start, 80)
    assert got[:32] == start
    assert got[32:64] == hashlib.sha256(start + b"\x01").digest()
    assert got[64:80] == hashlib.sha256(start + b"\x02").digest()[:16]


@pytest.mark.parametrize("i", range(50))
def test_the_two_halves_cover_the_square(i):
    parties = ((FOUNDER_DID, sig("c%d" % i)), (FIRST_DID, sig("d%d" % i)))
    for small in (False, True):
        left, right = tessera.halves(parties, small)
        assert tessera.area(left) > 0.1 and tessera.area(right) > 0.1
        assert tessera.area(left) + tessera.area(right) == pytest.approx(1.0, abs=1e-9)


def test_the_parties_are_read_off_a_bond_record():
    bond = {"parties": [FOUNDER_DID, FIRST_DID], "terms": "the charter",
            "signatures": {"first": FIRST_SIG, "founder": FOUNDER_SIG}}
    assert tessera.break_line(tessera.parties_of(bond)) == PINNED
    with pytest.raises(ValueError):
        tessera.parties_of({"parties": [FOUNDER_DID, FIRST_DID],
                            "signatures": {"founder": FOUNDER_SIG}})


@pytest.mark.parametrize("parties", [
    ((FOUNDER_DID, FOUNDER_SIG),),
    ((FOUNDER_DID, FOUNDER_SIG), (FOUNDER_DID, FIRST_SIG)),
    ((FOUNDER_DID, FOUNDER_SIG), (FIRST_DID, "not base64!")),
    ((FOUNDER_DID, FOUNDER_SIG), (FIRST_DID, "")),
    ((FOUNDER_DID, FOUNDER_SIG), (FIRST_DID, base64.b64decode(FIRST_SIG))),
])
def test_what_is_not_two_signed_parties_is_refused(parties):
    with pytest.raises(ValueError):
        tessera.break_line(parties)


# ---- the pictures --------------------------------------------------------

@pytest.mark.parametrize("size", [4, 15, 16, 48, 240, 1000.5])
@pytest.mark.parametrize("seam", [None, "#f4ecd8"])
def test_every_picture_is_plain_svg_and_reaches_nowhere(size, seam):
    for name, picture in pictures(PARTIES, size, seam).items():
        root = ET.fromstring(picture)
        assert root.tag == SVG_NS + "svg"
        assert root.get("viewBox")
        for element in root.iter():
            assert element.tag.startswith(SVG_NS), name
            assert element.tag[len(SVG_NS):] in ALLOWED, name
            assert "style" not in element.attrib
            assert not any("href" in key for key in element.attrib)
            assert not any("url(" in value or "http" in value for value in element.attrib.values())
        lowered = picture.lower()
        assert "script" not in lowered and "href" not in lowered and "url(" not in lowered
        # the one address in it is the namespace, which is a name and not a fetch
        assert lowered.count("http") == 1


def test_coordinates_have_two_decimals_at_most():
    for picture in pictures(PARTIES, 333.333, "#f4ecd8").values():
        for _, points in polygons(picture):
            for x, y in points:
                assert round(x, 2) == x and round(y, 2) == y


def test_the_viewbox_is_square_except_when_apart():
    for name, picture in pictures(PARTIES, 240).items():
        root = ET.fromstring(picture)
        expected = "0 0 288 240" if name == "apart" else "0 0 240 240"
        assert root.get("viewBox") == expected


def test_the_halves_follow_the_break_with_a_hair_gap():
    picture = tessera.svg_rejoined(PARTIES, 240, "#b5651d", "#2e5e4e")
    (_, left), (_, right) = polygons(picture)
    gap = 240 * tessera.GAP
    assert 1 <= gap <= 2  # a clear line at 240px
    # the break points of each half, top to bottom
    left_break = left[1:-1]
    right_break = list(reversed(right[2:]))
    assert len(left_break) == len(right_break) == 9
    for (lx, ly), (rx, ry), (x, y) in zip(left_break, right_break, PINNED):
        assert ly == ry == pytest.approx(y * 240)
        assert rx - lx == pytest.approx(gap, abs=0.011)
        assert (lx + rx) / 2 == pytest.approx(x * 240, abs=0.011)
    # and the gap fades with the tile
    small = tessera.svg_rejoined(PARTIES, 16, "#b5651d", "#2e5e4e")
    (_, left), (_, right) = polygons(small)
    assert right[-1][0] - left[1][0] <= 0.11


def test_the_seam_colour_is_there_only_when_given_and_beneath():
    without = tessera.svg_rejoined(PARTIES, 240, "#b5651d", "#2e5e4e")
    assert "#f4ecd8" not in without
    assert [fill for fill, _ in polygons(without)] == ["#b5651d", "#2e5e4e"]
    given = tessera.svg_rejoined(PARTIES, 240, "#b5651d", "#2e5e4e", seam_fill="#f4ecd8")
    assert [fill for fill, _ in polygons(given)] == ["#f4ecd8", "#b5651d", "#2e5e4e"]
    for picture in (tessera.svg_half(PARTIES, "left", 240, "#b5651d"),
                    tessera.svg_apart(PARTIES, 240, "#b5651d", "#2e5e4e")):
        assert "#f4ecd8" not in picture


def test_a_half_is_drawn_where_it_sits_in_the_whole():
    whole = polygons(tessera.svg_rejoined(PARTIES, 240, "#b5651d", "#2e5e4e"))
    left = polygons(tessera.svg_half(PARTIES, "left", 240, "#b5651d"))
    right = polygons(tessera.svg_half(PARTIES, "right", 240, "#2e5e4e"))
    assert left == [whole[0]] and right == [whole[1]]
    with pytest.raises(ValueError):
        tessera.svg_half(PARTIES, "middle", 240, "#b5651d")


def test_apart_the_halves_face_each_other_across_a_space():
    (_, left), (_, right) = polygons(tessera.svg_apart(PARTIES, 240, "#b5651d", "#2e5e4e"))
    left_break = left[1:-1]
    right_break = list(reversed(right[2:]))
    for (lx, ly), (rx, ry) in zip(left_break, right_break):
        assert ly == ry
        assert rx - lx == pytest.approx(240 * tessera.APART, abs=0.011)
    assert max(x for x, _ in right) == pytest.approx(288)


@pytest.mark.parametrize("size", [1, 8, 15, 15.99])
def test_small_tiles_draw_the_break_straight(size):
    entry, exit_ = PINNED[0], PINNED[-1]
    for name, picture in pictures(PARTIES, size, "#f4ecd8").items():
        for fill, points in polygons(picture):
            # the corners, and the break's two ends only
            assert len(points) == 4, (name, fill)
    left, right = tessera.halves(PARTIES, small=True)
    assert left[1:-1] == [entry, exit_]
    (_, drawn), _ = polygons(tessera.svg_apart(PARTIES, size, "#b5651d", "#2e5e4e"))
    assert drawn[1] == pytest.approx((entry[0] * size, 0), abs=0.006)
    assert drawn[2] == pytest.approx((exit_[0] * size, size), abs=0.006)


def test_from_sixteen_pixels_the_break_is_jagged():
    for fill, points in polygons(tessera.svg_rejoined(PARTIES, 16, "#b5651d", "#2e5e4e")):
        assert len(points) == 11


@pytest.mark.parametrize("fill", ["url(#x)", "red;", '"red"', "#12", "", None, "javascript:x"])
def test_a_fill_is_a_colour_and_nothing_more(fill):
    with pytest.raises(ValueError):
        tessera.svg_half(PARTIES, "left", 240, fill)
    if fill is None:  # no seam_fill is the ordinary clear gap, not a mistake
        return
    with pytest.raises(ValueError):
        tessera.svg_rejoined(PARTIES, 240, "#b5651d", "#2e5e4e", seam_fill=fill)


@pytest.mark.parametrize("size", [0, -5, "240", True, None])
def test_a_size_is_a_positive_number(size):
    with pytest.raises(ValueError):
        tessera.svg_apart(PARTIES, size, "#b5651d", "#2e5e4e")


# ---- the check -----------------------------------------------------------

def test_the_check_names_the_recipe_the_seed_and_every_point():
    text = tessera.verify_text(PARTIES)
    assert "tessera-v1" in text
    assert text.index(FIRST_DID) < text.index(FOUNDER_DID)
    assert tessera.seed(PARTIES).hex() in text
    for point in PINNED:
        assert "(%.4f, %.4f)" % point in text
    assert "<" not in text  # plain text, fit to be put anywhere
