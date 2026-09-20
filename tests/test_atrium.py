"""The atrium, built in Python: what the record says, and what the page shows.

These tests touch no browser. The same reckoning drawn in the page's own script
is checked against this one in test_atrium_paths.py, where node runs it.
"""

import datetime
import sys

import pytest

from conftest import write

STAMP = "%Y-%m-%dT%H-%M-%SZ"


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
    css, words = tiles[0]
    assert css == "tile-attendance tile-night"
    assert words.startswith("15 October 2026 · waking at night ·")


def test_a_waking_across_the_date_line_belongs_to_the_day_it_fell_on(atrium):
    beats = [(moment("2026-10-16T03-59-59Z"), "late"), (moment("2026-10-16T04-00-00Z"), "later")]
    tiles = atrium.tiles_from([], beats)
    assert tiles[0][1].startswith("15 October 2026 · waking at night")   # a second before midnight
    assert tiles[1][1].startswith("16 October 2026 · waking at night")   # and a second after

    # and the morning that follows is that same day there, and a dawn
    morning = atrium.tiles_from([], [(moment("2026-10-16T12-00-00Z"), "and up")])[0]
    assert morning[1].startswith("16 October 2026 · waking at dawn")
    assert morning[0] == "tile-attendance tile-dawn"


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
    assert tiles[0][0] == "tile-word"
    assert tiles[1][0] == "tile-founding"
    drawn = "".join(atrium.mosaic_block(tiles))
    assert '<li class="tile-word" title="2 September 2026 · the word was published"' in drawn


def test_a_seal_has_its_own_tile_and_joins_the_legend(atrium):
    tiles = a_whole_record(atrium)
    assert ("tile-seal", "8 October 2026 · a bond was sealed") in tiles
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
    assert tiles[3] == ("tile-event", "9 October 2026 · the tide paused")
    assert tiles[4][0] == "tile-attendance tile-day"


def test_the_mosaic_is_filled_out_to_whole_rows_of_ten(atrium):
    tiles = [("tile-event", "a thing")] * 11
    assert len(atrium.padded(tiles)) == 20
    assert atrium.padded(tiles)[-1] == ("", "")
    assert len(atrium.padded([])) == 10
    rows = atrium.mosaic_block(tiles)
    assert len(rows) == 4                       # twenty cells, five to a row
    assert rows[-1] == "<li></li>" * 5


def test_the_line_under_the_mosaic_is_the_newest_tile_s_own_words(atrium):
    tiles = a_whole_record(atrium)
    assert atrium.reading_text(tiles) == tiles[-1][1]
    assert atrium.reading_text(tiles).startswith("10 October 2026 · waking by day")
    assert atrium.reading_block(tiles) == [
        '<p class="reading">%s</p>' % atrium.reading_text(tiles)]


def test_the_caption_counts_what_is_there(atrium):
    assert atrium.caption_text(len(a_whole_record(atrium))) == (
        "the mosaic — one tile per event in our history · 5 so far")


def test_a_tile_s_words_are_escaped_where_they_are_written(atrium):
    tiles = atrium.tiles_from(
        atrium.parse_events("2026-10-01 · event · a line with \"quotes\" & <marks>\n"), [])
    drawn = "".join(atrium.mosaic_block(tiles))
    assert "&quot;quotes&quot; &amp; &lt;marks&gt;" in drawn
    assert "<marks>" not in drawn


# ---- an empty record -----------------------------------------------------

def test_an_empty_record_draws_an_empty_mosaic(atrium):
    assert atrium.tiles_from([], []) == []
    assert atrium.reading_text([]) == ""
    assert atrium.reading_block([]) == ['<p class="reading"></p>']
    assert atrium.caption_text(0).endswith("0 so far")
    assert atrium.mosaic_block([]) == ["<li></li>" * 5, "<li></li>" * 5]
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
    assert "as of %s" % atrium.human(datetime.date.today()) in page
    assert "3 tiles (2 events, 1 attendances), 1 on the bench" in capsys.readouterr().out


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
