"""The atrium, built in Python: what the record says, and what the page shows.

These tests touch no browser. The same reckoning drawn in the page's own script
is checked against this one in test_atrium_paths.py, where node runs it.
"""

import datetime
import sys

import pytest

from conftest import write

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
        "- 2026-09-20T15-37-07Z · the first one attended by day",
        "- 2026-09-19T22-55-25Z · the first one attended at night",
        "not a heartbeat at all",
        "- 2026-09-40T99-00-00Z · a moment that never was"))
    assert read == [(moment("2026-09-19T22-55-25Z"), "the first one attended at night"),
                    (moment("2026-09-20T15-37-07Z"), "the first one attended by day")]


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
    day, css, words = tiles[0]
    assert day == datetime.date(2026, 10, 15)
    assert css == "tile-attendance tile-night"
    assert words.startswith("15 October 2026 · waking at night ·")


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
            "8 October 2026 · a bond was sealed") in tiles
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
                        "9 October 2026 · the tide paused")
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
    cells = [("tile-event", "a thing")] * 1000
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
        ("tile-founding", "4 September 2026 · the first one was founded")]
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
    assert len(links) == 5
    assert links[3] == '<li><a href="%s">Leave a line</a></li>' % atrium.BENCH_URL


def test_a_bench_with_lines_carries_the_way_to_itself(atrium):
    lines = atrium.parse_bench("- 2026-10-01 · Mira · the lake was still\n")
    drawn = atrium.bench_block(lines)
    assert drawn[0] == '<section class="bench">'
    assert "  <h2>the visitor's bench</h2>" in drawn
    assert ('    <li><span class="when">1 October 2026</span> · the lake was still '
            "— Mira</li>") in drawn
    assert '  <p><a href="%s">Leave a line</a></p>' % atrium.BENCH_URL in drawn

    links = atrium.links_block(lines)
    assert len(links) == 4
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
    assert "the first one attended; wrote a letter" in page
    assert '<section class="bench">' in page
    assert "the lake was still" in page
    assert "the mosaic — one tile per event in our history · 3 so far" in page
    assert "as of %s" % atrium.human(TODAY) in page
    assert ("3 tiles in 44 slots at 34px (2 events, 1 attendances), "
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
