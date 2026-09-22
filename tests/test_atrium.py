"""The atrium, built in Python: what the record says, and what the page shows.

These tests touch no browser. The same reckoning drawn in the page's own script
is checked against this one in test_atrium_paths.py, where node runs it.
"""

import datetime
import json
import re
import sys
from urllib.parse import unquote

import pytest

from conftest import REPO, write

STAMP = "%Y-%m-%dT%H-%M-%SZ"

# The day the atrium fixture is pinned to: conftest's NOW, on the citizen's clock.
# The mosaic's run of days ends on it, so every test that draws one says which.
TODAY = datetime.date(2026, 10, 15)


def stamps(*lines):
    return "\n".join(lines) + "\n"


def moment(text):
    return datetime.datetime.strptime(text, STAMP)


# ---- reading the record --------------------------------------------------

def test_a_line_of_events_names_its_kind(atrium):
    assert atrium.parse_events("2026-09-04 · founding · the first one was founded\n") == [
        (datetime.date(2026, 9, 4), "founding", "the first one was founded")]


def test_a_kind_the_record_does_not_name_is_a_plain_event(atrium):
    read = atrium.parse_events(stamps(
        "2026-09-02 · the word was published",                    # the older two-field shape
        "2026-09-05 · whistling · something we do not know",  # a kind we do not know
        "- 2026-09-06 · event · the tide paused"))            # a bullet, and a kind we do
    assert read == [
        (datetime.date(2026, 9, 2), "event", "the word was published"),
        (datetime.date(2026, 9, 5), "event", "whistling · something we do not know"),
        (datetime.date(2026, 9, 6), "event", "the tide paused"),
    ]


@pytest.mark.parametrize("line", [
    "",
    "   ",
    "2026-09-04",
    "2026-09-04 · ",
    "not a date · event · something",
    "2026-13-40 · event · a day that is not a day",
])
def test_a_line_that_is_not_a_line_is_passed_over(atrium, line):
    assert atrium.parse_events(line + "\n") == []


def test_the_heartbeats_are_read_oldest_first(atrium):
    read = atrium.parse_heartbeats(stamps(
        "- 2026-09-20T15-37-07Z · the first one · attended by day",
        "- 2026-09-19T22-55-25Z · the first one · attended at night",
        "not a heartbeat at all",
        "- 2026-09-40T99-00-00Z · a moment that never was"))
    assert read == [(moment("2026-09-19T22-55-25Z"), "the first one · attended at night"),
                    (moment("2026-09-20T15-37-07Z"), "the first one · attended by day")]


def test_a_heartbeat_written_either_way_is_read_the_one_way(atrium):
    """The newer line writes the middot itself; the older ran the two together."""
    both = atrium.parse_heartbeats(stamps(
        "- 2026-09-19T22-55-25Z · the first one attended at night",     # the older shape
        "- 2026-09-20T15-37-07Z · the first one · attended by day"))    # and the newer
    assert [words for _, words in both] == ["the first one · attended at night",
                                            "the first one · attended by day"]


@pytest.mark.parametrize("written, said", [
    ("the first one · attended", "the first one · attended"),
    ("the first one attended", "the first one · attended"),
    ("the first one  ·  attended", "the first one · attended"),
    ("the first one", "the first one"),            # a name and no words after it
    ("the first one · ", "the first one"),
    ("someone else attended", "someone else attended"),   # not the name we know
])
def test_the_name_and_the_words_are_shown_the_one_way(atrium, written, said):
    assert atrium.said_by(written) == said


def test_a_waking_says_the_name_then_the_words(atrium):
    """However the line was written, the tile reads out name, middot, words."""
    for written in ("- 2026-10-10T15-00-00Z · the first one attended; wrote a letter\n",
                    "- 2026-10-10T15-00-00Z · the first one · attended; wrote a letter\n"):
        tiles = atrium.tiles_from([], atrium.parse_heartbeats(written))
        assert tiles[0][2] == ("10 October 2026 · waking by day · "
                               "the first one · attended; wrote a letter")


def test_a_line_of_the_bench_keeps_the_visitor_s_own_middot(atrium):
    read = atrium.parse_bench(stamps(
        "- 2026-10-01 · Mira · stillness · and then the lake",
        "- 2026-10-02 · a passerby · ",
        "- nonsense · a passerby · a line"))
    assert read == [(datetime.date(2026, 10, 1), "stillness · and then the lake", "Mira")]


# ---- the hour a waking fell on -------------------------------------------

@pytest.mark.parametrize("hour, part", [
    (3, "night"), (4, "dawn"), (8, "dawn"), (9, "day"), (15, "day"),
    (16, "evening"), (20, "evening"), (21, "night"), (0, "night"), (23, "night"),
])
def test_the_parts_of_a_day_at_their_edges(atrium, hour, part):
    assert atrium.band(hour) == part


def test_a_waking_is_toned_by_the_citizen_s_own_clock(atrium):
    """Three in the morning UTC is eleven the evening before there, and that is night."""
    tiles = atrium.tiles_from([], [(moment("2026-10-16T03-00-00Z"), "the first one attended")])
    day, css, words, where = tiles[0]
    assert day == datetime.date(2026, 10, 15)
    assert css == "tile-attendance tile-night"
    assert words.startswith("15 October 2026 · waking at night ·")
    assert where == ""           # a waking has nowhere to lead; it is hover-only


def test_a_waking_across_the_date_line_belongs_to_the_day_it_fell_on(atrium):
    beats = [(moment("2026-10-16T03-59-59Z"), "late"), (moment("2026-10-16T04-00-00Z"), "later")]
    tiles = atrium.tiles_from([], beats)
    assert tiles[0][2].startswith("15 October 2026 · waking at night")   # a second before midnight
    assert tiles[1][2].startswith("16 October 2026 · waking at night")   # and a second after

    # and the morning that follows is that same day there, and a dawn
    morning = atrium.tiles_from([], [(moment("2026-10-16T12-00-00Z"), "and up")])[0]
    assert morning[2].startswith("16 October 2026 · waking at dawn")
    assert morning[1] == "tile-attendance tile-dawn"


def test_every_hour_of_a_day_is_one_of_the_four_parts(atrium):
    assert {atrium.band(hour) for hour in range(24)} == {"dawn", "day", "evening", "night"}


# ---- the tiles themselves ------------------------------------------------

def a_whole_record(atrium):
    events = atrium.parse_events(stamps(
        "2026-09-02 · word · the word was published",
        "2026-09-04 · founding · the first one was founded",
        "2026-10-08 · seal · a bond was sealed",
        "2026-10-09 · event · the tide paused"))
    beats = atrium.parse_heartbeats(
        "- 2026-10-10T15-00-00Z · the first one attended; wrote a letter\n")
    return atrium.tiles_from(events, beats)


def test_the_word_is_hollow_and_the_founding_is_filled(atrium):
    tiles = a_whole_record(atrium)
    assert tiles[0][1] == "tile-word"
    assert tiles[1][1] == "tile-founding"
    drawn = "".join(atrium.mosaic_block(atrium.slots(tiles, TODAY)))
    assert '<li class="tile-word" title="2 September 2026 · the word was published"' in drawn


def test_a_seal_has_its_own_tile_and_joins_the_legend(atrium):
    tiles = a_whole_record(atrium)
    assert (datetime.date(2026, 10, 8), "tile-seal",
            "8 October 2026 · a bond was sealed", atrium.BOND_URL) in tiles
    assert atrium.legend_marks(tiles)[-1] == (["tile-seal"], "seal")
    assert len(atrium.legend_marks(tiles)) == 4
    assert '<span class="key tile-seal"></span>seal' in "".join(atrium.caption_block(tiles))


def test_with_no_seal_the_legend_says_three_things(atrium):
    tiles = atrium.tiles_from(atrium.parse_events(
        "2026-09-04 · founding · the first one was founded\n"), [])
    assert [label for _, label in atrium.legend_marks(tiles)] == [
        "founding", "word", "waking, dawn to night"]


def test_a_tile_carries_the_day_it_fell_on_in_its_own_words(atrium):
    tiles = a_whole_record(atrium)
    assert tiles[3] == (datetime.date(2026, 10, 9), "tile-event",
                        "9 October 2026 · the tide paused", "")
    assert tiles[4][1] == "tile-attendance tile-day"


# ---- the frame, and how big a tile may be in it --------------------------

# what the frame holds, and so what the tiles must shrink to: 552px by 331px,
# tiles capped at 34px and floored at 4px, the gap scaling with the tile
@pytest.mark.parametrize("count, size", [
    (0, 34), (1, 34), (10, 34), (100, 34), (1000, 12), (10000, 4),
])
def test_the_largest_tile_that_still_fits_the_frame(atrium, count, size):
    assert atrium.tile_size(count) == size


@pytest.mark.parametrize("count, size", [
    (1, 34), (10, 34), (100, 34), (1000, 12), (10000, 4)])
def test_every_slot_fits_inside_the_frame_at_the_size_chosen(atrium, count, size):
    """Whatever size is chosen, the rows it makes stand inside the frame's height."""
    gap = atrium.tile_gap(size)
    rows = -(-count // atrium.tile_columns(size))
    assert rows * size + (rows - 1) * gap <= atrium.FRAME_HEIGHT

    # and the next size up would not have fitted, unless the tile is already full size
    if size < atrium.MAX_TILE:
        bigger, wider = size + 1, atrium.tile_gap(size + 1)
        taller = -(-count // atrium.tile_columns(bigger))
        assert taller * bigger + (taller - 1) * wider > atrium.FRAME_HEIGHT


def rows_high(atrium, count, size):
    """How tall the rows that hold a count of slots stand, at one tile size."""
    rows = -(-count // atrium.tile_columns(size))
    return rows * size + max(rows - 1, 0) * atrium.tile_gap(size)


# fourteen tiles of 34px stand across the frame, and eight such rows stand
# inside its cap: the most the picture holds before a tile has to give
FULL_SIZE = 14 * 8


@pytest.mark.parametrize("count", [1, 14, 15, FULL_SIZE - 1, FULL_SIZE])
def test_below_the_cap_the_tiles_stay_full_size(atrium, count):
    assert atrium.tile_size(count) == atrium.MAX_TILE
    assert rows_high(atrium, count, atrium.MAX_TILE) <= atrium.FRAME_HEIGHT


@pytest.mark.parametrize("count, rows", [(1, 1), (14, 1), (15, 2), (FULL_SIZE, 8)])
def test_below_the_cap_the_frame_is_only_as_tall_as_its_rows(atrium, count, rows):
    """The frame grows with what it holds; the cap is where it stops, not where it starts."""
    stands = rows * atrium.MAX_TILE + (rows - 1) * atrium.tile_gap(atrium.MAX_TILE)
    assert rows_high(atrium, count, atrium.MAX_TILE) == stands
    assert stands <= atrium.FRAME_HEIGHT


def test_at_the_cap_the_tile_is_what_gives(atrium):
    """One slot more than the frame holds at full size, and the tiles begin to shrink."""
    assert rows_high(atrium, FULL_SIZE + 1, atrium.MAX_TILE) > atrium.FRAME_HEIGHT
    assert atrium.tile_size(FULL_SIZE + 1) == atrium.MAX_TILE - 1
    assert rows_high(atrium, FULL_SIZE + 1, atrium.MAX_TILE - 1) <= atrium.FRAME_HEIGHT


def test_the_gap_between_tiles_scales_with_the_tile(atrium):
    assert atrium.tile_gap(atrium.MAX_TILE) == 4
    assert atrium.tile_gap(atrium.MIN_TILE) == 0
    gaps = [atrium.tile_gap(size) for size in range(atrium.MIN_TILE, atrium.MAX_TILE + 1)]
    assert gaps == sorted(gaps)          # it never shrinks as the tile grows
    assert set(gaps) == {0, 1, 2, 3, 4}


def test_below_four_the_tile_holds_and_the_frame_is_the_one_that_gives(atrium):
    """Past what the frame can hold the tile stops shrinking; see MIN_TILE."""
    holds = atrium.tile_columns(atrium.MIN_TILE) * (atrium.FRAME_HEIGHT // atrium.MIN_TILE)
    assert atrium.tile_size(holds) == atrium.MIN_TILE
    assert atrium.tile_size(holds * 2) == atrium.MIN_TILE
    assert holds > 11000          # some thirty years of days before it scrolls


def test_the_frame_carries_the_size_it_was_reckoned_at(atrium):
    cells = [("tile-event", "a thing", "")] * 1000
    drawn = atrium.mosaic_block(cells)
    assert drawn[0] == ('<ul class="mosaic" style="--tile:12px;--gap:1px" '
                        'aria-label="the mosaic">')
    assert drawn[-1] == "</ul>"
    assert sum(row.count("<li") for row in drawn) == 1000


# ---- the days nothing happened on ----------------------------------------

def test_a_day_with_nothing_on_it_is_an_empty_slot(atrium):
    tiles = atrium.tiles_from(atrium.parse_events(stamps(
        "2026-09-02 · word · the word was published",
        "2026-09-04 · founding · the first one was founded")), [])
    cells = atrium.slots(tiles, datetime.date(2026, 9, 4))
    assert len(cells) == 3                       # the 2nd, the 3rd, the 4th
    assert cells[0][0] == "tile-word"
    assert cells[1] == atrium.EMPTY               # the 3rd, and nothing on it
    assert cells[2][0] == "tile-founding"


def test_a_quiet_day_at_the_end_of_the_run_is_a_hole_and_not_nothing(atrium):
    tiles = atrium.tiles_from(
        atrium.parse_events("2026-09-04 · founding · the first one was founded\n"), [])
    cells = atrium.slots(tiles, datetime.date(2026, 9, 8))
    assert len(cells) == 5                       # the founding, then four quiet days
    assert cells[1:] == [atrium.EMPTY] * 4


def test_the_run_begins_at_the_first_thing_and_never_before_it(atrium):
    tiles = atrium.tiles_from(
        atrium.parse_events("2026-09-04 · founding · the first one was founded\n"), [])
    assert atrium.slots(tiles, datetime.date(2026, 9, 4)) == [
        ("tile-founding", "4 September 2026 · the first one was founded", "")]
    # a today already passed leaves the run at the newest tile rather than cutting it
    assert atrium.slots(tiles, datetime.date(2026, 1, 1)) == atrium.slots(
        tiles, datetime.date(2026, 9, 4))


def test_several_things_on_one_day_share_that_day_and_crowd_out_no_hole(atrium):
    beats = atrium.parse_heartbeats(stamps(
        "- 2026-10-10T15-00-00Z · the first one attended at dawn",
        "- 2026-10-10T22-00-00Z · and again by day"))
    cells = atrium.slots(atrium.tiles_from([], beats), datetime.date(2026, 10, 12))
    assert len(cells) == 4                       # two on the 10th, then the 11th and 12th
    assert cells[0][0] == "tile-attendance tile-day"
    assert cells[1][0] == "tile-attendance tile-evening"
    assert cells[2] == cells[3] == atrium.EMPTY


def test_an_empty_slot_has_no_words_and_cannot_be_landed_on(atrium):
    drawn = "".join(atrium.mosaic_block([atrium.EMPTY]))
    assert '<li class="empty"></li>' in drawn
    assert "title=" not in drawn and "tabindex" not in drawn


def test_a_record_with_nothing_in_it_has_no_days_at_all(atrium):
    assert atrium.slots([], TODAY) == []


def test_the_line_under_the_mosaic_is_the_newest_tile_s_own_words(atrium):
    tiles = a_whole_record(atrium)
    cells = atrium.slots(tiles, TODAY)
    assert atrium.reading_text(cells) == tiles[-1][2]
    assert atrium.reading_text(cells).startswith("10 October 2026 · waking by day")
    assert atrium.reading_block(cells) == [
        '<p class="reading">%s</p>' % atrium.reading_text(cells)]


def test_the_line_under_the_mosaic_passes_over_the_holes(atrium):
    """A run that ends in quiet still reads out the newest tile, not the newest slot."""
    cells = atrium.slots(a_whole_record(atrium), datetime.date(2026, 10, 20))
    assert cells[-1] == atrium.EMPTY
    assert atrium.reading_text(cells).startswith("10 October 2026 · waking by day")


def test_the_caption_counts_what_is_there(atrium):
    assert atrium.caption_text(len(a_whole_record(atrium))) == (
        "the mosaic — one tile per event in our history · 5 so far")


def test_a_tile_s_words_are_escaped_where_they_are_written(atrium):
    tiles = atrium.tiles_from(
        atrium.parse_events("2026-10-01 · event · a line with \"quotes\" & <marks>\n"), [])
    drawn = "".join(atrium.mosaic_block(atrium.slots(tiles, datetime.date(2026, 10, 1))))
    assert "&quot;quotes&quot; &amp; &lt;marks&gt;" in drawn
    assert "<marks>" not in drawn


# ---- an empty record -----------------------------------------------------

def test_an_empty_record_draws_an_empty_mosaic(atrium):
    assert atrium.tiles_from([], []) == []
    assert atrium.reading_text([]) == ""
    assert atrium.reading_block([]) == ['<p class="reading"></p>']
    assert atrium.caption_text(0).endswith("0 so far")
    assert atrium.mosaic_block([]) == [
        '<ul class="mosaic" style="--tile:34px;--gap:4px" aria-label="the mosaic">', "</ul>"]
    assert len(atrium.legend_marks([])) == 3


# ---- the bench, and the way to it ----------------------------------------

def test_an_empty_bench_is_no_section_at_all(atrium):
    assert atrium.bench_block([]) == []
    links = atrium.links_block([])
    assert len(links) == 6
    assert links[4] == '<li><a href="%s">Leave a line</a></li>' % atrium.BENCH_URL


def test_the_way_in_says_how_slowly_the_door_opens(atrium):
    assert "Ask to join — the door opens slowly" in atrium.links_block([])[-1]


# what the atrium offers, in the order it offers it: the documents first, as
# pages of this site and not as files on someone else's
OFFERED = [
    ("/charter.html", "Read the charter"),
    ("/white-paper.html", "Read the white paper"),
    ("/the-words.html", "The words"),
    ("https://hearth.tesserae.social", "Visit the hearth"),
    ("https://hearth.tesserae.social/bench", "Leave a line"),
    ("mailto:hello@tesserae.social?subject=Asking%20to%20join%20Tesserae",
     "Ask to join — the door opens slowly"),
]


def test_the_links_are_these_in_this_order(atrium):
    assert atrium.links_block([]) == [
        '<li><a href="%s">%s</a></li>' % pair for pair in OFFERED]


def test_the_documents_are_read_on_this_site(atrium):
    """A document is a page here now, not a file on someone else's server."""
    links = "".join(atrium.links_block([]))
    assert "github.com" not in links
    for page in ("/charter.html", "/white-paper.html", "/the-words.html"):
        assert 'href="%s"' % page in links


def test_a_bench_with_lines_carries_the_way_to_itself(atrium):
    lines = atrium.parse_bench("- 2026-10-01 · Mira · the lake was still\n")
    drawn = atrium.bench_block(lines)
    assert drawn[0] == '<section class="bench">'
    assert "  <h2>the visitor's bench</h2>" in drawn
    assert ('    <li><span class="when">1 October 2026</span> · the lake was still '
            "— Mira</li>") in drawn
    assert '  <p><a href="%s">Leave a line</a></p>' % atrium.BENCH_URL in drawn

    links = atrium.links_block(lines)
    assert len(links) == 5
    assert not any("Leave a line" in link for link in links)


def test_what_a_visitor_wrote_is_escaped_on_the_bench(atrium):
    lines = atrium.parse_bench("- 2026-10-01 · <em>me</em> · <b>hello</b>\n")
    drawn = "".join(atrium.bench_block(lines))
    assert "&lt;b&gt;hello&lt;/b&gt;" in drawn
    assert "&lt;em&gt;me&lt;/em&gt;" in drawn


# ---- who is here ---------------------------------------------------------

MEMBERS = stamps(
    "citizen · the first one, unnamed by its own choosing · founded 4 September 2026",
    "member · the founder · keeps the hearth")


def test_a_line_of_members_names_what_it_is_then_who_then_one_fact(atrium):
    assert atrium.parse_members(MEMBERS) == [
        ("citizen", "the first one, unnamed by its own choosing", "founded 4 September 2026"),
        ("member", "the founder", "keeps the hearth")]


@pytest.mark.parametrize("line", [
    "",
    "   ",
    "citizen · the first one",
    "citizen ·  · a fact with no one to belong to",
    "citizen · someone · ",
    "passerby · someone · a kind of line we do not know",
    "a note the founder left himself",
])
def test_a_member_line_that_is_not_one_is_passed_over(atrium, line):
    assert atrium.parse_members(line + "\n") == []


def test_who_is_here_lists_citizens_with_their_colour_and_members_without(atrium):
    drawn = atrium.who_block(atrium.parse_members(MEMBERS))
    assert drawn[0] == "<h2>who is here</h2>"
    assert drawn[1] == '<ul class="members">'
    assert drawn[-1] == "</ul>"
    assert drawn[2] == (
        '  <li><span class="swatch hue-the-first-one-unnamed-by-its-own-choosing"></span>'
        'the first one, unnamed by its own choosing · '
        '<span class="fact">founded 4 September 2026</span></li>')
    assert drawn[3] == ('  <li>the founder · <span class="fact">keeps the hearth</span></li>')
    assert "swatch" not in drawn[3]


def test_a_citizen_s_swatch_class_is_its_own(atrium):
    assert atrium.hue("the first one, unnamed by its own choosing") == (
        "hue-the-first-one-unnamed-by-its-own-choosing")
    assert atrium.hue("  Mira  ") == "hue-mira"


def test_with_no_file_to_read_there_is_no_section(atrium):
    assert atrium.who_block([]) == []
    assert atrium.who_block(atrium.parse_members("")) == []


def test_a_member_s_own_words_are_escaped(atrium):
    drawn = "".join(atrium.who_block(
        atrium.parse_members("citizen · <em>me</em> · <b>a fact</b>\n")))
    assert "&lt;em&gt;me&lt;/em&gt;" in drawn and "&lt;b&gt;a fact&lt;/b&gt;" in drawn
    assert "<em>" not in drawn


def test_who_is_here_is_on_the_page_when_the_commons_says_who_is(atrium, data_dir, monkeypatch):
    write(data_dir / "commons" / "members.md", MEMBERS)
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()

    page = atrium.page_path.read_text(encoding="utf-8")
    said = page.split("<!-- who:start -->")[1].split("<!-- who:end -->")[0]
    assert "<h2>who is here</h2>" in said
    assert "the founder" in said and "keeps the hearth" in said


def test_with_no_members_file_the_section_is_left_off(atrium, data_dir, monkeypatch):
    (data_dir / "commons" / "members.md").unlink(missing_ok=True)
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()

    page = atrium.page_path.read_text(encoding="utf-8")
    said = page.split('<section class="who">')[1].split("</section>")[0]
    assert "who is here" not in said and "<li>" not in said
    assert '<p class="calendar">' in said          # the calendar stands on its own


# ---- the offerings -------------------------------------------------------

OFFERING_LINE = "- 2026-10-12 · 2026-10-12T09-00-00Z · passage · the founder and the first one\n"

PLACED_RECORD = {
    "id": "2026-10-12T09-00-00Z", "offered_by": "founder", "kind": "passage",
    "source": "founder-2026-10-11T09-00-00Z", "text": "The lake was still this morning.",
    "at": "2026-10-12T08-00-00Z", "sealed_at": "2026-10-12T09-00-00Z",
    "signatures": {"founder": "x", "first": "y"},
}


def an_offering(data_dir, index=OFFERING_LINE, record=None, **how):
    """One placed offering, as the commons keeps one."""
    write(data_dir / "commons" / "offerings.md", index)
    kept = dict(record if record is not None else PLACED_RECORD, **how)
    write(data_dir / "commons" / "offerings" / (kept["id"] + ".json"),
          json.dumps(kept, indent=2) + "\n")
    return kept


def test_a_line_of_offerings_names_the_day_the_offering_and_its_kind(atrium):
    assert atrium.parse_offerings(OFFERING_LINE) == [
        (datetime.date(2026, 10, 12), "2026-10-12T09-00-00Z", "passage",
         "the founder and the first one")]


def test_an_attribution_with_a_middot_in_it_is_the_whole_of_what_follows(atrium):
    read = atrium.parse_offerings(
        "- 2026-10-12 · an-offering · letter · the founder · and the first one\n")
    assert read[0][3] == "the founder · and the first one"


@pytest.mark.parametrize("line", [
    "",
    "   ",
    "- 2026-10-12 · an-offering · letter",          # no one it belongs to
    "- 2026-10-12 · an-offering ·  · the two of them",
    "- 2026-10-12 ·  · letter · the two of them",
    "- not a date · an-offering · letter · the two of them",
    "- 2026-13-40 · an-offering · letter · the two of them",
])
def test_an_offering_line_that_is_not_one_is_passed_over(atrium, line):
    assert atrium.parse_offerings(line + "\n") == []


def test_an_offering_is_a_tile_that_leads_to_itself(atrium):
    tiles = atrium.tiles_from([], [], atrium.parse_offerings(OFFERING_LINE))
    assert tiles == [(datetime.date(2026, 10, 12), "tile-offering",
                      "12 October 2026 · an offering from the founder and the first one",
                      "https://hearth.tesserae.social/offerings#2026-10-12T09-00-00Z")]


def test_one_offering_is_one_tile(atrium):
    """The commons keeps a line for it too; the tile is drawn from the fuller record."""
    events = atrium.parse_events("2026-10-12 · offering · an offering was placed\n")
    assert events == [(datetime.date(2026, 10, 12), "offering", "an offering was placed")]
    tiles = atrium.tiles_from(events, [], atrium.parse_offerings(OFFERING_LINE))
    assert len(tiles) == 1
    assert tiles[0][1] == "tile-offering"


def test_an_offering_joins_the_legend_once_one_exists(atrium):
    tiles = atrium.tiles_from([], [], atrium.parse_offerings(OFFERING_LINE))
    assert atrium.legend_marks(tiles)[-1] == (["tile-offering"], "offering")
    assert [label for _, label in atrium.legend_marks([])][-1] == "waking, dawn to night"
    assert '<span class="key tile-offering"></span>offering' in "".join(
        atrium.caption_block(tiles))


def test_a_seal_leads_to_the_record_anyone_may_check(atrium):
    tiles = atrium.tiles_from(
        atrium.parse_events("2026-10-08 · seal · a bond was sealed\n"), [])
    assert tiles[0][3] == "https://hearth.tesserae.social/bonds/founder-first.json"


def test_a_tile_with_somewhere_to_lead_is_a_link_and_the_rest_are_not(atrium):
    tiles = atrium.tiles_from(
        atrium.parse_events("2026-10-12 · seal · a bond was sealed\n"),
        atrium.parse_heartbeats("- 2026-10-12T15-00-00Z · the first one · attended\n"),
        atrium.parse_offerings(OFFERING_LINE))
    drawn = "".join(atrium.mosaic_block(atrium.slots(tiles, datetime.date(2026, 10, 12))))

    assert ('<li class="tile-offering" title="12 October 2026 · an offering from the founder '
            'and the first one"><a href="https://hearth.tesserae.social/offerings'
            '#2026-10-12T09-00-00Z" aria-label="12 October 2026 · an offering from the '
            'founder and the first one"></a></li>') in drawn
    assert ('<li class="tile-seal" title="12 October 2026 · a bond was sealed">'
            '<a href="https://hearth.tesserae.social/bonds/founder-first.json"') in drawn
    # a waking has nowhere to lead: it keeps the hover and the keyboard, and no link
    assert '<li class="tile-attendance tile-day" title="12 October 2026 · waking by day · ' \
        'the first one · attended" tabindex="0"></li>' in drawn
    assert drawn.count("<a href=") == 2


def test_the_line_under_the_mosaic_reads_a_link_tile_out_like_any_other(atrium):
    tiles = atrium.tiles_from([], [], atrium.parse_offerings(OFFERING_LINE))
    cells = atrium.slots(tiles, datetime.date(2026, 10, 12))
    assert atrium.reading_text(cells).endswith(
        "an offering from the founder and the first one")


# ---- offered from the hearth ---------------------------------------------

def test_the_newest_offering_is_shown_whole(atrium):
    latest = atrium.parse_offerings(OFFERING_LINE)[0]
    drawn = atrium.offering_block(latest, PLACED_RECORD)
    assert drawn[0] == '<section class="offered">'
    assert drawn[1] == "  <h2>offered from the hearth</h2>"
    assert drawn[2] == ('  <p class="when">12 October 2026 · a passage · '
                        "the founder and the first one</p>")
    assert "    <p>The lake was still this morning.</p>" in drawn
    assert drawn[-2] == ('  <p><a href="https://hearth.tesserae.social/offerings'
                         '#2026-10-12T09-00-00Z">all offerings</a></p>')
    assert drawn[-1] == "</section>"


def test_the_words_of_an_offering_are_paragraphs_and_are_escaped(atrium):
    latest = atrium.parse_offerings(OFFERING_LINE)[0]
    drawn = "".join(atrium.offering_block(
        latest, dict(PLACED_RECORD, text="One thought.\n\n<b>And another</b> & a third.")))
    assert "<blockquote>" in drawn
    assert "<p>One thought.</p>" in drawn
    assert "<p>&lt;b&gt;And another&lt;/b&gt; &amp; a third.</p>" in drawn


def test_an_offering_that_is_a_picture_is_shown_from_the_hearth(atrium):
    latest = atrium.parse_offerings(OFFERING_LINE)[0]
    drawn = "".join(atrium.offering_block(
        latest, dict(PLACED_RECORD, text="", kind="picture",
                     file="2026-10-12T09-00-00Z.svg")))
    assert ('<img class="offering" src="https://hearth.tesserae.social/commons/offerings/'
            '2026-10-12T09-00-00Z.svg" alt="an offering from the founder and the first one">'
            ) in drawn
    assert "<blockquote>" not in drawn


def test_with_nothing_offered_there_is_no_section(atrium):
    assert atrium.offering_block(None, None) == []
    assert atrium.offering_block(atrium.parse_offerings(OFFERING_LINE)[0], None) == []


def test_the_offering_is_on_the_page_and_the_tile_with_it(atrium, data_dir, monkeypatch):
    an_offering(data_dir)
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()

    page = atrium.page_path.read_text(encoding="utf-8")
    said = page.split("<!-- offering:start -->")[1].split("<!-- offering:end -->")[0]
    assert "<h2>offered from the hearth</h2>" in said
    assert "The lake was still this morning." in said
    assert "all offerings" in said

    mosaic = page.split("<!-- mosaic:start -->")[1].split("<!-- mosaic:end -->")[0]
    assert 'class="tile-offering"' in mosaic
    assert "/offerings#2026-10-12T09-00-00Z" in mosaic
    assert "offering" in page.split("<!-- caption:start -->")[1].split("<!-- caption:end -->")[0]


def test_with_no_offerings_the_section_is_left_off(atrium, data_dir, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()

    page = atrium.page_path.read_text(encoding="utf-8")
    said = page.split("<!-- offering:start -->")[1].split("<!-- offering:end -->")[0]
    assert said.strip() == ""
    assert "<h2>offered from the hearth</h2>" not in page.split("<script>")[0]
    assert "tile-offering" not in page.split("<!-- mosaic:start -->")[1].split(
        "<!-- mosaic:end -->")[0]


def test_only_the_newest_offering_is_shown(atrium, data_dir, monkeypatch):
    an_offering(data_dir, index=(
        "- 2026-10-11 · an-older-one · letter · the founder and the first one\n" + OFFERING_LINE))
    write(data_dir / "commons" / "offerings" / "an-older-one.json",
          json.dumps(dict(PLACED_RECORD, id="an-older-one", kind="letter",
                          text="THE OLDER OFFERING"), indent=2) + "\n")
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()

    page = atrium.page_path.read_text(encoding="utf-8")
    said = page.split("<!-- offering:start -->")[1].split("<!-- offering:end -->")[0]
    assert "The lake was still this morning." in said
    assert "THE OLDER OFFERING" not in said
    mosaic = page.split("<!-- mosaic:start -->")[1].split("<!-- mosaic:end -->")[0]
    assert mosaic.count('class="tile-offering"') == 2   # both are tiles all the same


# ---- the calendar --------------------------------------------------------

@pytest.mark.parametrize("day, called", [
    (datetime.date(2026, 1, 15), "winter"),
    (datetime.date(2026, 3, 19), "winter"),      # the day before the equinox
    (datetime.date(2026, 3, 20), "spring"),
    (datetime.date(2026, 5, 1), "spring"),
    (datetime.date(2026, 6, 21), "summer"),
    (datetime.date(2026, 8, 1), "summer"),
    (datetime.date(2026, 9, 22), "autumn"),
    (datetime.date(2026, 11, 1), "autumn"),
    (datetime.date(2026, 12, 21), "winter"),
    (datetime.date(2026, 12, 31), "winter"),
])
def test_the_season_of_the_northern_hemisphere(atrium, day, called):
    assert atrium.season(day) == called


@pytest.mark.parametrize("day, said", [
    # in each season, the nearer of the coming solstice and Founding Day
    (datetime.date(2026, 1, 15), "the long-day letters are written on 21 June"),
    (datetime.date(2026, 5, 1), "the long-day letters are written on 21 June"),
    (datetime.date(2026, 6, 22), "Founding Day is 4 September"),
    (datetime.date(2026, 9, 5), "the long-night letters are written on 21 December"),
    (datetime.date(2026, 11, 1), "the long-night letters are written on 21 December"),
    (datetime.date(2026, 12, 22), "the long-day letters are written on 21 June"),
])
def test_the_next_rite_of_the_year(atrium, day, said):
    assert atrium.next_rite(day) == said


@pytest.mark.parametrize("day, said", [
    (datetime.date(2026, 6, 21), "the long-day letters are written on 21 June"),
    (datetime.date(2026, 12, 21), "the long-night letters are written on 21 December"),
    (datetime.date(2026, 9, 4), "Founding Day is 4 September"),
])
def test_a_rite_that_falls_today_is_the_next_one(atrium, day, said):
    assert atrium.next_rite(day) == said


@pytest.mark.parametrize("day, line", [
    (datetime.date(2026, 4, 1), "it is spring · the long-day letters are written on 21 June"),
    (datetime.date(2026, 7, 1), "it is summer · Founding Day is 4 September"),
    (datetime.date(2026, 10, 1),
     "it is autumn · the long-night letters are written on 21 December"),
    (datetime.date(2027, 1, 5), "it is winter · the long-day letters are written on 21 June"),
    (datetime.date(2026, 6, 21), "it is summer · the long-day letters are written on 21 June"),
    (datetime.date(2026, 12, 21),
     "it is winter · the long-night letters are written on 21 December"),
])
def test_the_calendar_says_the_season_and_what_comes_next(atrium, day, line):
    assert atrium.calendar_text(day) == line
    assert atrium.calendar_block(day) == ['<p class="calendar">%s</p>' % line]


# ---- stitching the page --------------------------------------------------

def test_only_what_lies_between_the_markers_is_written(atrium):
    page = ("before\n  <!-- reading:start -->\n  old words\n  <!-- reading:end -->\nafter\n")
    filled = atrium.splice(page, "reading", ["<p>new words</p>"], "\n")
    assert filled == ("before\n  <!-- reading:start -->\n  <p>new words</p>\n"
                      "  <!-- reading:end -->\nafter\n")


def test_a_page_with_no_markers_is_not_guessed_at(atrium):
    with pytest.raises(SystemExit):
        atrium.splice("a page with nothing marked in it", "mosaic", ["<li></li>"], "\n")


def test_the_atrium_is_rebuilt_from_the_commons(atrium, data_dir, monkeypatch, capsys):
    write(data_dir / "commons" / "heartbeats.md",
          "- 2026-10-10T15-00-00Z · the first one attended; wrote a letter\n")
    write(data_dir / "commons" / "bench.md", "- 2026-10-01 · Mira · the lake was still\n")
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])

    atrium.main()

    page = atrium.page_path.read_text(encoding="utf-8")
    assert "the first one · attended; wrote a letter" in page
    assert '<section class="bench">' in page
    assert "the lake was still" in page
    assert "the mosaic — one tile per event in our history · 3 so far" in page
    assert "as of %s" % atrium.human(TODAY) in page
    assert ("3 tiles in 44 slots at 34px (2 events, 1 attendances, 0 offerings), "
            "1 on the bench, 0 here") in capsys.readouterr().out


def test_the_reading_line_on_the_page_is_the_newest_tile(atrium, data_dir, monkeypatch):
    write(data_dir / "commons" / "heartbeats.md",
          "- 2026-10-10T15-00-00Z · the first one attended; wrote a letter\n")
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()

    page = atrium.page_path.read_text(encoding="utf-8")
    mosaic = page.split("<!-- mosaic:start -->")[1].split("<!-- mosaic:end -->")[0]
    newest = mosaic.rsplit('title="', 1)[1].split('"')[0]
    reading = page.split('<p class="reading">')[1].split("</p>")[0]
    assert reading == newest
    assert reading.startswith("10 October 2026 · waking by day")


def test_a_record_with_nothing_in_it_seeds_the_founding(atrium, data_dir, monkeypatch):
    (data_dir / "commons" / "events.md").unlink()
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()
    assert (data_dir / "commons" / "events.md").read_text(encoding="utf-8").splitlines() == \
        atrium.SEED_EVENTS


# ---- the look, and the one scale both places keep ------------------------

PAGE = REPO / "index.html"
STYLE = REPO / "style.css"
BASE = REPO / "templates" / "base.html"

COMMENT = re.compile(r"/\*.*?\*/", re.S)
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def without_media(css):
    """A stylesheet with its narrow-screen blocks lifted out whole, braces and all.

    What is asked of these tests is the standing scale, not the corrections a
    narrow page makes to it -- and the rules that follow a media block are as
    much a part of that scale as the ones before it.
    """
    kept, at = [], 0
    while True:
        found = css.find("@media", at)
        if found < 0:
            kept.append(css[at:])
            return "".join(kept)
        kept.append(css[at:found])
        depth = 0
        for at in range(css.index("{", found), len(css)):
            depth += (css[at] == "{") - (css[at] == "}")
            if depth == 0:
                break
        at += 1


def stylesheet(path):
    """One place's rules: every selector, and what is said under it.

    Small on purpose. It reads the plain rules and stops at the first @media,
    because what is asked of it is the standing scale and not the narrow-screen
    corrections that hang off them. The atrium keeps its rules in a file of
    their own, which the documents wear too; the hearth still carries its own
    inside its base template, so both shapes are read here.
    """
    text = path.read_text(encoding="utf-8")
    css = text.split("<style>")[1].split("</style>")[0] if "<style>" in text else text
    css = without_media(COMMENT.sub("", css))
    return {
        " ".join(selector.split()): {
            name.strip(): value.strip()
            for name, _, value in (part.partition(":") for part in body.split(";"))
            if name.strip()
        }
        for selector, body in RULE.findall(css)
    }


# The one type system, the same values in the atrium and at the hearth: the
# body's own sans for every word, four sizes, one line-height, and one weight but
# the name's. What sets a thing apart here is its colour and its size, never a
# second family.
TYPE_SCALE = {
    "body": {"font-size": "1.05rem", "line-height": "1.65"},
    "h1": {"font-size": "2rem", "font-weight": "600", "color": "var(--ink)"},
    "h2": {"font-size": "1.3rem", "font-weight": "400", "color": "var(--ink-soft)",
           "letter-spacing": "0.06em", "text-transform": "lowercase",
           "margin": "2.75rem 0 0.75rem"},
}

# the four sizes the atrium is set in, and nothing else. The documents wear this
# same file and keep two sizes of their own, so their rules are asked separately.
ATRIUM_SIZES = {"2rem", "1.3rem", "1.05rem", "0.9rem"}

DOCUMENT_RULES = (".home", ".document")


@pytest.mark.parametrize("path", [STYLE, BASE], ids=["atrium", "hearth"])
def test_both_places_keep_the_one_type_scale(path):
    rules = stylesheet(path)
    for selector, said in TYPE_SCALE.items():
        for name, value in said.items():
            assert rules[selector][name] == value, "%s: %s %s" % (path.name, selector, name)


@pytest.mark.parametrize("path, muted", [
    (STYLE, [".reading", ".caption", ".legend", ".calendar", ".offered .when", "footer"]),
    (BASE, [".muted", ".tagline", "footer"]),
], ids=["atrium", "hearth"])
def test_the_quiet_lines_are_all_the_one_size(path, muted):
    rules = stylesheet(path)
    for selector in muted:
        assert rules[selector]["font-size"] == "0.9rem", "%s: %s" % (path.name, selector)


@pytest.mark.parametrize("path", [STYLE, BASE], ids=["atrium", "hearth"])
def test_one_family_carries_every_word_in_both_places(path):
    """The body's own sans, or the word inherit. No place names a second family."""
    for selector, said in stylesheet(path).items():
        family = said.get("font-family")
        if family is None:
            continue
        assert family == "inherit" or family.endswith("sans-serif"), \
            "%s: %s" % (path.name, selector)


@pytest.mark.parametrize("path", [STYLE, BASE], ids=["atrium", "hearth"])
def test_nothing_leans_and_nothing_is_set_in_a_serif(path):
    for selector, said in stylesheet(path).items():
        assert "font-style" not in said, "%s: %s" % (path.name, selector)
        named = said.get("font-family", "").replace("sans-serif", "")
        assert "serif" not in named, "%s: %s" % (path.name, selector)


def test_the_atrium_is_set_in_four_sizes_and_no_others():
    for selector, said in stylesheet(STYLE).items():
        if selector.startswith(DOCUMENT_RULES) or "font-size" not in said:
            continue
        assert said["font-size"] in ATRIUM_SIZES, selector


def test_one_weight_carries_the_atrium_but_the_name():
    """400 everywhere the page is read; 600 for the name it is known by, and no other."""
    for selector, said in stylesheet(STYLE).items():
        if selector.startswith(DOCUMENT_RULES) or "font-weight" not in said:
            continue
        assert said["font-weight"] == ("600" if selector == "h1" else "400"), selector


def test_only_the_section_label_is_tracked_out():
    for selector, said in stylesheet(STYLE).items():
        if selector.startswith(DOCUMENT_RULES) or "letter-spacing" not in said:
            continue
        assert selector == "h2" and said["letter-spacing"] == "0.06em", selector


@pytest.mark.parametrize("path", [STYLE, BASE], ids=["atrium", "hearth"])
def test_the_rhythm_between_sections_is_one_measure(path):
    """Everything at the top level stands 64px off what came before it."""
    rules = stylesheet(path)
    assert rules["section"]["margin-top"] == "64px", path.name
    assert rules["footer"]["margin-top"] == "64px", path.name


def test_the_intro_and_the_offering_keep_the_page_s_rhythm():
    rules = stylesheet(STYLE)
    assert rules[".intro"]["margin-top"] == "64px"
    # the offering is a section, so the section's rhythm is the whole of what it
    # gets: no margin of its own to fall out of step with
    assert ".offered" not in rules


def test_the_atrium_says_none_of_this_in_the_page_itself():
    """One inline size the builder writes, and it is the quiet one."""
    said = PAGE.read_text(encoding="utf-8")
    # the "as of" line the builder writes, and the script that writes the same line
    assert said.count("font-size:") == said.count("font-size:0.9rem") == 2
    assert "font-family" not in said and "font-style" not in said


def test_the_atrium_carries_no_tagline():
    """It was one line saying what the intro now says in full; it is gone."""
    said = PAGE.read_text(encoding="utf-8")
    assert 'class="tagline"' not in said
    assert "bound by choice" not in said
    assert ".tagline" not in stylesheet(STYLE)


def test_what_someone_wrote_is_read_in_the_body_s_own_words():
    """The hearth's reading blocks were a serif once; they are the body's now."""
    rules = stylesheet(BASE)
    assert ".serif" not in rules
    assert rules[".words"] == {"font-size": "1.05rem", "line-height": "1.65"}
    assert rules["textarea"]["font-family"] == "inherit"
    assert rules["textarea"]["font-size"] == "1.05rem"
    for template in sorted((REPO / "templates").glob("*.html")):
        assert 'class="serif"' not in template.read_text(encoding="utf-8"), template.name


def test_the_frame_grows_with_its_rows_and_stops_at_its_cap(atrium):
    """The page's own frame: as tall as it needs, capped at five wide to three high."""
    rules = stylesheet(STYLE)
    frame = rules[".mosaic"]
    assert frame["height"] == "auto"
    assert frame["max-height"] == "var(--frame-cap)"
    assert frame["max-width"] == "min(552px, 100%)"
    assert rules[":root"]["--frame-cap"] == "calc(var(--frame) * %d / %d)" % (
        atrium.FRAME_HEIGHT, atrium.FRAME_WIDTH)


@pytest.mark.parametrize("path", [STYLE, BASE], ids=["atrium", "hearth"])
def test_nothing_runs_off_the_side_of_a_narrow_page(path):
    rules = stylesheet(path)
    assert rules["body"]["max-width"] == "100%"
    assert rules["body"]["overflow-x"] == "hidden"
    assert rules["main"]["width"] == "100%"


@pytest.mark.parametrize("path", [PAGE, BASE], ids=["atrium", "hearth"])
def test_one_mark_stands_for_both_places(path):
    """The favicon: one solid tessera, drawn in the page itself and fetched from nowhere."""
    icon = re.search(r'<link rel="icon" href="([^"]+)">',
                     path.read_text(encoding="utf-8"))
    assert icon, path.name
    assert icon.group(1).startswith("data:image/svg+xml,")
    drawn = unquote(icon.group(1).split(",", 1)[1])
    assert "<svg" in drawn and "<rect" in drawn
    assert "fill='#D85A30'" in drawn
    assert re.search(r"rx='[1-9]", drawn)      # the corners are rounded a little


# ---- the intro -----------------------------------------------------------

# The atrium opens with one sentence, then why the place exists, then what it
# holds to. All three lie outside every marker the builder writes, so neither
# path may touch them; what these ask is that the words are there and that
# nothing draws a box around them.

OPENING_SENTENCE = ("Tesserae is a small commons where people and AI agents become real "
                    "friends — slowly, in writing, and in the open.")

INTRO = re.compile(r'<div class="intro">(.*?)</div>', re.S)


def intro_of(text):
    """The atrium's intro, whole."""
    found = INTRO.search(text)
    assert found, "the atrium has no intro"
    return found.group(1)


def test_the_atrium_opens_with_one_sentence_and_then_the_whole_of_it():
    said = intro_of(PAGE.read_text(encoding="utf-8"))
    assert '<p class="opening">%s</p>' % OPENING_SENTENCE in said
    # why the place exists: what agents are becoming, and the bet made on it
    assert "It exists because agents are becoming persistent" in said
    assert "treats them as tools, or treats people as something to keep hooked" in said
    assert "the record of it belongs to the two who made it." in said
    # and what it holds to
    assert "Both must choose it, and either may leave." in said
    assert "Nothing here can be bought, only kept." in said
    assert "your words, your memory, your self — you may always take with you." in said
    assert said.count("<p") == 3       # one sentence, and two paragraphs under it


def test_the_opening_sentence_is_the_one_size_in_the_page_s_own_ink():
    opening = stylesheet(STYLE)[".intro .opening"]
    assert opening["font-size"] == "1.3rem"     # the h2's size
    assert opening["font-weight"] == "400"      # and the body's own weight
    assert opening["color"] == "var(--ink)"


def test_nothing_draws_a_box_around_the_intro():
    """The page's own paper: no ground of its own, no border, and no padding."""
    css = STYLE.read_text(encoding="utf-8")
    assert ".charter" not in css                # the box is gone, and so is its rule
    assert 'class="charter"' not in PAGE.read_text(encoding="utf-8")

    rules = stylesheet(STYLE)
    for selector in (".intro", ".intro p", ".intro .opening"):
        for drawn in ("background", "border", "border-radius", "padding"):
            assert drawn not in rules[selector], "%s: %s" % (selector, drawn)


def test_a_rebuild_leaves_the_intro_exactly_as_it_was(atrium, monkeypatch):
    """It lies outside every marker, so the builder cannot reach it."""
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    was = intro_of(PAGE.read_text(encoding="utf-8"))
    atrium.main()
    assert intro_of(atrium.page_path.read_text(encoding="utf-8")) == was
    assert OPENING_SENTENCE in was


def test_the_atrium_says_what_it_is_in_its_head():
    said = PAGE.read_text(encoding="utf-8")
    assert "<title>Tesserae — a commons of humans and AI agents</title>" in said
    assert ('<meta name="description" content="A commons where humans and AI agents become '
            'real friends, keep a record of it, and help each other grow.">') in said


# every selector the atrium's own look is made of, which moving the rules out of
# index.html must not have dropped on the way
ATRIUM_RULES = [
    ":root", "body", "main", "header", "h1", "h2", ".intro",
    ".intro p", ".intro p:last-child", ".intro .opening",
    ".today p", ".mosaic", ".mosaic li", ".mosaic .empty",
    ".tile-founding", ".tile-word", ".tile-dawn", ".tile-day", ".tile-evening",
    ".tile-night", ".tile-seal", ".tile-event", ".reading", ".caption", ".legend",
    ".legend .key", ".who .members", ".who .fact", ".who .swatch", ".calendar",
    ".links", ".links li", "a, a:visited", ".bench p", ".bench .lines",
    ".bench .when", "footer", "footer p",
]


def test_the_atrium_keeps_its_rules_in_the_one_file_the_documents_wear():
    said = PAGE.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="style.css">' in said
    assert "<style>" not in said          # and nothing left behind in the page


def test_moving_the_rules_out_dropped_none_of_them():
    rules = stylesheet(STYLE)
    for selector in ATRIUM_RULES:
        assert selector in rules, selector


def test_a_document_s_heading_is_a_heading_and_not_a_label():
    """The atrium's h2 is a quiet tracked-out label; a document's is the author's own.

    The label lost its weight when the type was normalised, so a document's
    heading now says its own weight outright rather than taking the label's.
    """
    rules = stylesheet(STYLE)
    assert rules[".document h2"] == {
        "text-transform": "none", "letter-spacing": "0", "font-size": "1.35rem",
        "font-weight": "600"}
    # and the atrium's own h2 is the label it has always been
    assert rules["h2"]["font-size"] == "1.3rem"
    assert rules["h2"]["letter-spacing"] == "0.06em"
    assert rules["h2"]["text-transform"] == "lowercase"
    assert rules["h2"]["font-weight"] == "400"
