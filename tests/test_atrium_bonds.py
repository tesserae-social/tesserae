"""The atrium's bonds: a seal tile drawn from commons/bonds.md, and the halves
beside the names of those who hold them. Where the list is empty or missing,
nothing changes from before there was one. The page's own script is checked
against the same record in test_atrium_paths.py.
"""

import datetime
import re
import sys

import pytest

from conftest import write

HEARTH = "https://hearth.tesserae.social"

SEALED = "2026-10-08 · founder-first · the founder and the first one · sealed\n"
RELEASED = ("2026-10-08 · founder-first · the founder and the first one · "
            "released 2026-10-12\n")

MEMBERS = ("citizen · the first one, unnamed by its own choosing · attends at dawn\n"
           "member · the founder · keeps the hearth\n")

EVENTS = ("2026-09-02 · word · the word was published\n"
          "2026-09-04 · founding · the first one was founded\n"
          "2026-10-08 · seal · a bond was sealed between the founder and the first one\n")

TODAY = datetime.date(2026, 10, 15)


# ---- reading the list ----------------------------------------------------

def test_a_line_of_bonds_names_the_day_the_bond_its_parties_and_how_it_stands(atrium):
    assert atrium.parse_bonds(SEALED + RELEASED.replace("founder-first", "founder-second")) == [
        (datetime.date(2026, 10, 8), "founder-first", ["the founder", "the first one"], None),
        (datetime.date(2026, 10, 8), "founder-second", ["the founder", "the first one"],
         datetime.date(2026, 10, 12)),
    ]


@pytest.mark.parametrize("line", [
    "",
    "2026-10-08 · founder-first · the founder and the first one",
    "2026-10-08 · Founder First · the founder and the first one · sealed",
    "2026-10-08 · ../secrets · the founder and the first one · sealed",
    "2026-10-08 · founder-first ·  · sealed",
    "2026-10-08 · founder-first · the founder and the first one · stepped back",
    "2026-10-08 · founder-first · the founder and the first one · released",
    "2026-10-08 · founder-first · the founder and the first one · released 2026-13-40",
    "2026-10-40 · founder-first · the founder and the first one · sealed",
    "2026-10-08 · founder-first · the founder and the first one · sealed · and more",
])
def test_a_line_that_is_not_a_bond_is_passed_over(atrium, line):
    assert atrium.parse_bonds(line + "\n") == []


# ---- the seal tile -------------------------------------------------------

def test_a_bond_on_the_list_is_one_seal_tile_and_the_events_line_is_passed_over(atrium):
    tiles = atrium.tiles_from(atrium.parse_events(EVENTS), [], (), atrium.parse_bonds(SEALED))
    seals = [tile for tile in tiles if tile[1] == "tile-seal"]
    assert seals == [(datetime.date(2026, 10, 8), "tile-seal",
                      "8 October 2026 · a bond was sealed", HEARTH + "/bonds/founder-first")]


def test_with_no_list_the_seal_is_drawn_as_it_always_was(atrium):
    tiles = atrium.tiles_from(atrium.parse_events(EVENTS), [], (), atrium.parse_bonds(""))
    assert [tile for tile in tiles if tile[1] == "tile-seal"] == [
        (datetime.date(2026, 10, 8), "tile-seal",
         "8 October 2026 · a bond was sealed between the founder and the first one",
         atrium.BOND_URL)]


def test_a_seal_tile_shows_its_tessera_at_the_tile_s_size(atrium):
    tiles = atrium.tiles_from(atrium.parse_events(EVENTS), [], (), atrium.parse_bonds(SEALED))
    drawn = "".join(atrium.mosaic_block(atrium.slots(tiles, TODAY)))
    assert ('<li class="tile-seal" title="8 October 2026 · a bond was sealed">'
            '<a href="%s/bonds/founder-first" aria-label="8 October 2026 · a bond was sealed">'
            '<img src="%s/bonds/founder-first/tessera.svg?size=34" width="34" height="34" '
            'alt=""></a></li>' % (HEARTH, HEARTH)) in drawn


def test_a_seal_tile_shrinks_with_the_rest(atrium):
    cells = [("tile-event", "a thing", "")] * 999 + [
        ("tile-seal", "8 October 2026 · a bond was sealed", HEARTH + "/bonds/founder-first")]
    drawn = "".join(atrium.mosaic_block(cells))
    assert ('<img src="%s/bonds/founder-first/tessera.svg?size=12" width="12" height="12" '
            'alt="">' % HEARTH) in drawn


def test_only_a_bond_s_own_page_carries_a_tessera(atrium):
    for where in (atrium.BOND_URL, HEARTH + "/offerings#x", HEARTH + "/bonds/",
                  HEARTH + "/bonds/a/b", "https://elsewhere.example/bonds/founder-first"):
        assert atrium.tessera_of(where, 34) == ""
        assert "<img" not in "".join(atrium.mosaic_block([("tile-seal", "words", where)]))


def test_a_seal_tile_reads_out_like_any_other(atrium):
    tiles = atrium.tiles_from(atrium.parse_events(EVENTS), [], (), atrium.parse_bonds(SEALED))
    assert atrium.reading_text(atrium.slots(tiles, TODAY)) == "8 October 2026 · a bond was sealed"
    assert atrium.legend_marks(tiles)[-1] == (["tile-seal"], "seal")


# ---- who is here ---------------------------------------------------------

def test_each_member_carries_their_half_after_their_name(atrium):
    drawn = atrium.who_block(atrium.parse_members(MEMBERS), atrium.parse_bonds(SEALED))
    assert drawn[2] == (
        '  <li><span class="swatch hue-the-first-one-unnamed-by-its-own-choosing"></span>'
        'the first one, unnamed by its own choosing <a href="%s/bonds/founder-first">'
        '<img class="half" src="%s/bonds/founder-first/half/the-first-one.svg?size=16" '
        'width="16" height="16" alt="their half of the bond sealed on 8 October 2026"></a>'
        ' · <span class="fact">attends at dawn</span></li>' % (HEARTH, HEARTH))
    assert drawn[3] == (
        '  <li>the founder <a href="%s/bonds/founder-first">'
        '<img class="half" src="%s/bonds/founder-first/half/the-founder.svg?size=16" '
        'width="16" height="16" alt="their half of the bond sealed on 8 October 2026"></a>'
        ' · <span class="fact">keeps the hearth</span></li>' % (HEARTH, HEARTH))


def test_a_released_bond_s_half_is_still_shown(atrium):
    drawn = "".join(atrium.who_block(atrium.parse_members(MEMBERS), atrium.parse_bonds(RELEASED)))
    assert drawn.count('<img class="half"') == 2
    assert ('alt="their half of the bond sealed on 8 October 2026, released on '
            '12 October 2026"') in drawn


def test_a_half_for_each_bond_held_and_none_for_bonds_not_held(atrium):
    listed = atrium.parse_bonds(
        SEALED + "2026-10-10 · founder-mira · the founder and Mira · sealed\n")
    drawn = atrium.who_block(atrium.parse_members(MEMBERS + "member · Mira · new here\n"),
                             listed)
    first, founder, mira = drawn[2:5]
    assert first.count('class="half"') == 1
    assert founder.count('class="half"') == 2
    assert mira.count('class="half"') == 1 and "/bonds/founder-mira/half/mira.svg" in mira
    # a name that only begins like a party's is not that party
    assert atrium.who_block([("member", "the founders' circle", "x")], listed)[2].count(
        "half") == 0


def test_with_no_bonds_who_is_here_is_as_it_was(atrium):
    members = atrium.parse_members(MEMBERS)
    assert atrium.who_block(members, []) == atrium.who_block(members)
    assert "half" not in "".join(atrium.who_block(members))


# ---- the page, built -----------------------------------------------------

def built(atrium, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()
    return atrium.page_path.read_bytes()


def region(page, name):
    """What the builder wrote between one pair of markers."""
    return re.search(r"<!-- %s:start -->(.*?)<!-- %s:end -->" % (name, name), page, re.S).group(1)


def a_commons(data_dir):
    write(data_dir / "commons" / "events.md", EVENTS)
    write(data_dir / "commons" / "members.md", MEMBERS)


def test_an_empty_list_and_no_list_build_the_same_page_byte_for_byte(atrium, data_dir,
                                                                     monkeypatch):
    a_commons(data_dir)
    missing = built(atrium, monkeypatch)
    write(data_dir / "commons" / "bonds.md", "")
    empty = built(atrium, monkeypatch)
    write(data_dir / "commons" / "bonds.md", "a note, and no bond in it\n")
    noted = built(atrium, monkeypatch)
    assert missing == empty == noted
    page = missing.decode("utf-8")
    assert "<img" not in region(page, "mosaic") and "<img" not in region(page, "who")
    assert atrium.BOND_URL in region(page, "mosaic")   # the seal still leads to the record


def test_a_list_of_bonds_puts_the_tile_and_the_halves_on_the_page(atrium, data_dir,
                                                                  monkeypatch, capsys):
    a_commons(data_dir)
    write(data_dir / "commons" / "bonds.md", SEALED)
    page = built(atrium, monkeypatch).decode("utf-8")
    assert region(page, "mosaic").count("/bonds/founder-first/tessera.svg?size=34") == 1
    assert region(page, "who").count('<img class="half"') == 2
    assert "a bond was sealed between the founder and the first one" not in region(page, "mosaic")
    assert region(page, "reading").strip() == (
        '<p class="reading">8 October 2026 · a bond was sealed</p>')
    assert "1 sealed bonds" in capsys.readouterr().out
