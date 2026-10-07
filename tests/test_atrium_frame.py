"""The frame of tiles round the atrium's words, measured in a real browser.

The front page lays the last year of the mosaic round its column of words: two
rows of tiles above, tiles down either side where the window has room for them,
and rows below until the tiles end. Where each tile stands is worked out by the
browser's own grid, with a small step in the page's script to say which cells
the column stands on, so only a browser laying the page out can say whether the
tiles run in the order they should, or whether any of it pushes the page
sideways. The whole mosaic's own page is measured the same way.

So these are the tests here that need Chrome: it is run headless on copies of
the pages with a scrollbar that takes up room down the side, and asked what it
measured. A headless window will not go as narrow as a phone, so each copy is
shown in a frame of each width instead, which is a window of exactly that width
to the page inside it.

Chrome is looked for where it is usually installed, or where CHROME says it is.
Without it these tests skip and the rest of the suite runs as it did.

Nothing goes out to the network: the copies are baked here from a record made
up for the purpose, and the one thing the page's script would ask the hearth
for is refused before it is asked, so what is measured is what was baked in.
"""

import datetime
import json
import os
import re
import shutil
import subprocess

import pytest

import build_atrium as atrium
from conftest import REPO, write

PLACES = [
    os.environ.get("CHROME", ""),
    shutil.which("chrome") or "",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]
CHROME = next((place for place in PLACES if place and os.path.exists(place)), None)

pytestmark = pytest.mark.skipif(CHROME is None, reason="Chrome is not installed here")

WIDTHS = [1920, 1280, 768, 360, 320]
BESIDE = [1920, 1280, 768]   # the windows with room for tiles beside the column
PHONES = [360, 320]          # and the ones with none

MARGIN = 16      # the page's own, at either side and above the first tile
SCROLLBAR = 17   # the room a scrollbar takes down the side of a window on Windows
TILE, GAP = 24, 3
PITCH = TILE + GAP
MEASURE_OF_WORDS = 600
NEAR = 0.51      # a grid centred in an odd number of pixels stands on the half

TODAY = datetime.date(2026, 10, 15)

# A scrollbar that is always there and always takes its room, whatever the
# browser would have drawn left to itself: the case 100vw gets wrong.
FORCED = ("<style>html { overflow-y: scroll; } "
          "html::-webkit-scrollbar { width: %dpx; height: %dpx; }</style>"
          % (SCROLLBAR, SCROLLBAR))

# the hearth, refused before it is asked: what was baked into the page stands
QUIET = '<script>window.fetch = () => Promise.reject(new Error("no hearth here"));</script>'

# What a page is asked once it is laid out and its script has had its say.
MEASURE = """<script>
addEventListener("load", () => setTimeout(() => {
  const root = document.documentElement, one = s => document.querySelector(s);
  const box = el => { if (!el) return null; const r = el.getBoundingClientRect();
    return { left: r.left, right: r.right, top: r.top + scrollY, bottom: r.bottom + scrollY,
             width: r.width, height: r.height }; };
  let right = 0, left = 0;
  for (const el of document.body.querySelectorAll("*")) {
    const r = el.getBoundingClientRect();
    if (!r.width && !r.height) continue;
    right = Math.max(right, r.right); left = Math.min(left, r.left);
  }
  const line = one(".reading"), tiles = [...document.querySelectorAll(".mosaic li:not(.year)")];
  const said = {
    inner: innerWidth, client: root.clientWidth, scroll: root.scrollWidth,
    bodyScroll: document.body.scrollWidth, left, right,
    cells: ["--from", "--to", "--down"].map(name => root.style.getPropertyValue(name)),
    frame: box(one(".frame")), band: box(one(".band")), column: box(one(".column")),
    columns: document.querySelectorAll(".column").length,
    words: ["header", ".menu", ".intro", ".reading", ".caption", ".legend", ".who",
            ".calendar", "footer", ".home"].map(s => box(one(s))),
    intro: box(one(".intro")), reading: box(line), caption: box(one(".caption")),
    legend: box(one(".legend")), rest: box(one(".rest")), home: box(one(".home")),
    restSays: one(".rest") ? one(".rest").innerHTML : "",
    tiles: tiles.map(el => Object.assign(box(el), { title: el.title, kind: el.className })),
    years: [...document.querySelectorAll(".mosaic .year")].map(el =>
      Object.assign(box(el), { year: el.textContent, size: getComputedStyle(el).fontSize,
                               ink: getComputedStyle(el).color })),
    quiet: getComputedStyle(one(".caption")).color,
    list: one(".mosaic").getAttribute("style"),
    atRest: line.textContent,
    marked: [...document.querySelectorAll("main [style]")]
      .filter(el => !el.matches("ul.mosaic")).map(el => el.tagName).join(" "),
  };
  // the reading line: onto a tile, across a gap to the next, and away altogether
  const worded = [...document.querySelectorAll(".mosaic li[title]")];
  const tile = worded[Math.floor(worded.length / 2)], gap = one(".frame") || one(".mosaic");
  const move = (kind, from, to) => from.dispatchEvent(
    new MouseEvent(kind, { bubbles: true, relatedTarget: to }));
  move("mouseover", tile, gap);
  said.onto = [tile.title, line.textContent];
  move("mouseout", tile, gap);
  said.acrossGap = line.textContent;
  move("mouseout", gap, document.body);
  said.away = line.textContent;
  said.newest = [worded[0].title, worded[worded.length - 1].title];
  // and where the reading line is once the page has been scrolled under it
  const held = one(".said");
  said.tall = root.scrollHeight - innerHeight;
  if (held && said.tall > 250) { scrollTo(0, 250); said.stuck = held.getBoundingClientRect().top; }
  parent.postMessage(JSON.stringify([NAME + ":" + innerWidth, said]), "*");
}, 300));
</script>"""

# The page that holds the frames, one for each page at each width, and writes
# down what each of them says it measured.
FRAMES = """<!DOCTYPE html>
<html><body>
%s
<script>
const heard = {};
addEventListener("message", event => {
  const [which, said] = JSON.parse(event.data);
  heard[which] = said;
  let out = document.getElementById("measured");
  if (!out) { out = document.createElement("pre"); out.id = "measured";
              document.body.appendChild(out); }
  out.textContent = JSON.stringify(heard);
});
</script>
</body></html>
"""

SCRIPT = re.compile(r"<script>.*?</script>", re.S)


def a_long_record():
    """Some four hundred days, ending today: a quiet day in every seven, and two
    things on one day in every five, so the year shown is days and not tiles."""
    lines = []
    for back in range(399, -1, -1):
        day = TODAY - datetime.timedelta(days=back)
        if back % 7 == 3:
            continue
        lines.append("%s · event · day %s" % (day, day))
        if back % 5 == 0:
            lines.append("%s · seal · day %s again" % (day, day))
    return atrium.tiles_from(atrium.parse_events("\n".join(lines)), [])


def baked(tiles):
    """Both pages, baked from one record as the builder bakes them, and written nowhere."""
    front = atrium.slots(tiles, TODAY, atrium.FRONT_SPAN_DAYS)
    page = (REPO / "index.html").read_text(encoding="utf-8").replace("\r\n", "\n")
    page = atrium.splice(page, "mosaic", atrium.frame_block(front), "\n")
    page = atrium.splice(page, "reading", atrium.reading_block(front), "\n")
    whole = atrium.whole_page(page, "\n")
    whole = atrium.splice(whole, "whole", atrium.whole_block(atrium.days(tiles, TODAY)), "\n")
    whole = atrium.splice(whole, "reading", atrium.reading_block(atrium.slots(tiles, TODAY)), "\n")
    whole = atrium.splice(whole, "caption", atrium.caption_block(tiles), "\n")
    return page, whole


def shown(page, name, scripted=True, forced=True):
    """A page ready to be measured: its scrollbar forced, the hearth refused, or no script at all."""
    if not scripted:
        page = SCRIPT.sub("", page)
    page = page.replace("</head>", (FORCED if forced else "") + (QUIET if scripted else "")
                        + "</head>")
    return page.replace("</body>", "<script>const NAME = %s;</script>%s</body>"
                        % (json.dumps(name), MEASURE))


RECORD = a_long_record()
YEAR = atrium.slots(RECORD, TODAY, atrium.FRONT_SPAN_DAYS)


@pytest.fixture(scope="module")
def measured(tmp_path_factory):
    """The pages as Chrome lays them out, at each width: asked once, and kept."""
    yard = tmp_path_factory.mktemp("frame")
    front, whole = baked(RECORD)
    pages = {
        "front": shown(front, "front"),                      # a year and more of tiles
        "noscript": shown(front, "noscript", scripted=False),
        "whole": shown(whole, "whole"),
        # the whole mosaic with the scrollbar the browser gives it: forcing one onto
        # the root changes which box the page scrolls in, and so what a line sticks to
        "unforced": shown(whole, "unforced", forced=False),
        # and the two pages as they stand in the repository today
        "today": shown((REPO / "index.html").read_text(encoding="utf-8"), "today"),
        "wholetoday": shown((REPO / "mosaic.html").read_text(encoding="utf-8"), "wholetoday"),
    }
    for name, page in pages.items():
        write(yard / (name + ".html"), page)
    shutil.copy(REPO / "style.css", yard / "style.css")

    write(yard / "frames.html", FRAMES % "\n".join(
        '<iframe src="%s.html" style="width:%dpx;height:900px;border:0"></iframe>' % (name, width)
        for name in pages for width in WIDTHS))

    done = subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
         "--user-data-dir=%s" % (yard / "profile"), "--window-size=2000,1000",
         "--virtual-time-budget=10000", "--dump-dom", (yard / "frames.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", timeout=180)
    said = re.search(r'<pre id="measured">(.*?)</pre>', done.stdout, re.S)
    assert said, "Chrome measured nothing: %s" % done.stderr[-500:]
    found = json.loads(said.group(1).replace("&quot;", '"').replace("&lt;", "<")
                       .replace("&gt;", ">").replace("&amp;", "&"))
    assert sorted(found) == sorted("%s:%d" % (name, width) for name in pages for width in WIDTHS)
    return {(which.split(":")[0], int(which.split(":")[1])): what
            for which, what in found.items()}


EVERY = [(name, width) for name in ("front", "noscript", "whole", "today", "wholetoday")
         for width in WIDTHS]
FRONTS = [(name, width) for name in ("front", "noscript", "today") for width in WIDTHS]


def across_of(said):
    """How many tiles stand side by side between the page's margins."""
    return (said["client"] - 2 * MARGIN + GAP) // PITCH


def cells_of(said):
    """The cells the script gave the column -- from, to, down -- or None where it gave none."""
    if said["cells"] == ["", "", ""]:
        return None
    return [int(one) for one in said["cells"]]


def cells_for(width):
    """The cells the column should stand on at a width, reckoned here a second time.

    As many across as cover its 600px, one more where that leaves the two sides
    uneven, and none at all where there is not a whole tile's room on each side.
    """
    across = (width - SCROLLBAR - 2 * MARGIN + GAP) // PITCH
    wide = -(-(MEASURE_OF_WORDS + GAP) // PITCH)
    if (across - wide) % 2:
        wide += 1
    beside = (across - wide) // 2
    return (beside + 1, beside + 1 + wide) if beside >= 1 else None


def order_of(said):
    """Where each tile should stand, in the order they are read: left to right and
    row by row from the top left corner, passing over the cells the column is on."""
    across, cells, column = across_of(said), cells_of(said), said["column"]
    left = (said["client"] - (across * PITCH - GAP)) / 2
    row, out = 0, []
    while len(out) < len(said["tiles"]):
        if cells is None and row == 2:
            row += 1              # the column has the whole of the third row
        if cells is None and row > 2:
            top = column["bottom"] + GAP + (row - 3) * PITCH
        else:
            top = MARGIN + row * PITCH
        for col in range(across):
            under = cells and 2 <= row < 2 + cells[2] and cells[0] - 1 <= col < cells[1] - 1
            if not under:
                out.append((left + col * PITCH, top))
        row += 1
    return out[:len(said["tiles"])]


def day_of(title):
    return datetime.datetime.strptime(title.split(" · ")[0], "%d %B %Y").date()


# ---- every page, at every width ------------------------------------------

@pytest.mark.parametrize("name, width", EVERY)
def test_the_window_is_the_width_asked_for_and_has_its_scrollbar(measured, name, width):
    """What is measured is the case that matters: a scrollbar that takes its room."""
    said = measured[name, width]
    assert said["inner"] == width
    assert said["client"] == width - SCROLLBAR


@pytest.mark.parametrize("name, width", EVERY)
def test_nothing_scrolls_sideways(measured, name, width):
    said = measured[name, width]
    assert said["scroll"] == said["client"]
    assert said["bodyScroll"] <= said["client"]
    # and not merely hidden: nothing on the page stands past either edge of it
    assert said["left"] >= 0
    assert said["right"] <= said["client"]
    for tile in said["tiles"]:
        assert tile["left"] >= MARGIN and tile["right"] <= said["client"] - MARGIN


# ---- the front page: the order of the tiles --------------------------------

@pytest.mark.parametrize("name, width", FRONTS)
def test_the_tiles_run_newest_first_from_the_top_left_corner_row_by_row(measured, name, width):
    """Two whole rows above the words, then the cells beside the column or none,
    then whole rows below: each tile stands exactly where the order puts it."""
    said = measured[name, width]
    tiles = said["tiles"]
    assert len(tiles) > 40
    # the corner: the page's own margin above, and the same room at either side
    assert tiles[0]["top"] == MARGIN
    assert MARGIN <= tiles[0]["left"] < MARGIN + PITCH / 2
    for tile, (left, top) in zip(tiles, order_of(said)):
        assert abs(tile["left"] - left) <= NEAR and abs(tile["top"] - top) <= NEAR, tile["title"]
        assert tile["width"] == tile["height"] == TILE
    # newest first: no tile is of a later day than the one before it
    days = [day_of(tile["title"]) for tile in tiles if tile["title"]]
    assert days == sorted(days, reverse=True)
    assert days[0] > days[-1]


@pytest.mark.parametrize("width", WIDTHS)
def test_the_first_two_rows_run_the_whole_width_above_the_words(measured, width):
    said = measured["front", width]
    across, tiles = across_of(said), said["tiles"]
    for row in (0, 1):
        held = tiles[row * across:(row + 1) * across]
        assert {tile["top"] for tile in held} == {MARGIN + row * PITCH}
        assert held[-1]["right"] > said["client"] - MARGIN - PITCH      # to the far margin
        assert held[-1]["bottom"] < said["column"]["top"]
    assert tiles[2 * across]["top"] > MARGIN + PITCH                       # and no third


@pytest.mark.parametrize("width", BESIDE)
def test_beside_the_column_the_tiles_keep_to_either_side_of_it(measured, width):
    said = measured["front", width]
    column, cells = said["column"], cells_of(said)
    start, end = cells_for(width)
    down = -(-(round(column["height"]) + GAP) // PITCH)
    assert cells == [start, end, down]
    assert column["top"] == MARGIN + 2 * PITCH
    # as many rows down as hold the column, and not one more than it needs
    assert (down - 1) * PITCH - GAP < column["height"] <= down * PITCH - GAP

    beside = [tile for tile in said["tiles"]
              if tile["bottom"] > column["top"] and tile["top"] < column["bottom"]]
    lefts = [tile for tile in beside if tile["right"] <= column["left"]]
    rights = [tile for tile in beside if tile["left"] >= column["right"]]
    assert lefts and rights and len(lefts) + len(rights) == len(beside)   # none under the words
    # each row beside the column is read left side first, then the right, then the next row
    first = [tile for tile in beside if tile["top"] == column["top"]]
    each = start - 1
    assert len(first) == 2 * each
    assert all(tile in lefts for tile in first[:each])
    assert all(tile in rights for tile in first[each:])
    at = said["tiles"].index(first[0])
    assert said["tiles"][at:at + 2 * each] == first


def test_where_the_column_is_short_of_the_tiles_whole_rows_follow_below_it(measured):
    """At 768px the year outlasts the column's sides, and runs on in whole rows under it."""
    said = measured["front", 768]
    column, across = said["column"], across_of(said)
    below = [tile for tile in said["tiles"] if tile["top"] >= column["bottom"]]
    assert len(below) > 2 * across
    assert below[0]["top"] == MARGIN + (2 + cells_of(said)[2]) * PITCH
    assert below[0]["left"] == said["tiles"][0]["left"]
    assert below[across - 1]["top"] == below[0]["top"]
    assert below[across]["top"] == below[0]["top"] + PITCH
    # and on the wider windows the same year ends beside the column
    for width in (1920, 1280):
        wide = measured["front", width]
        assert wide["tiles"][-1]["top"] < wide["column"]["bottom"]


@pytest.mark.parametrize("name, width", [("front", width) for width in PHONES]
                         + [("noscript", width) for width in WIDTHS])
def test_with_no_room_or_no_script_it_is_two_rows_then_the_words_then_the_rest(measured, name,
                                                                                width):
    """A phone, and any window where the script never ran: the same tiles, in the same order."""
    said = measured[name, width]
    assert cells_of(said) is None
    across, tiles, column = across_of(said), said["tiles"], said["column"]
    above = [tile for tile in tiles if tile["bottom"] <= column["top"]]
    below = [tile for tile in tiles if tile["top"] >= column["bottom"]]
    assert len(above) == 2 * across and above == tiles[:2 * across]
    assert below == tiles[2 * across:] and len(below) > 2 * across
    assert below[0]["top"] == column["bottom"] + GAP
    assert below[0]["left"] == tiles[0]["left"]
    # the same order as the page with its script, tile for tile
    assert [tile["title"] for tile in tiles] == [
        tile["title"] for tile in measured["front", width]["tiles"]]


@pytest.mark.parametrize("width", PHONES)
def test_a_phone_is_laid_the_same_with_the_script_as_without(measured, width):
    with_it, without = measured["front", width], measured["noscript", width]
    place = lambda tile: (tile["left"], tile["title"])
    assert [place(tile) for tile in with_it["tiles"]] == [place(tile) for tile in without["tiles"]]
    assert with_it["column"]["left"] == without["column"]["left"]
    assert with_it["column"]["width"] == without["column"]["width"]


# ---- the front page: the words, the year, and the way on -------------------

@pytest.mark.parametrize("name, width", FRONTS)
def test_the_words_keep_their_column_and_it_stays_centred(measured, name, width):
    said = measured[name, width]
    column = said["column"]
    assert said["columns"] == 1
    assert column["width"] == min(MEASURE_OF_WORDS, across_of(said) * PITCH - GAP)
    assert abs((column["left"] + column["right"]) / 2 - said["client"] / 2) <= NEAR
    # everything that is read stands inside the column's own gutters
    gutter = 20 if width <= 480 else 24
    for words in said["words"][:-1]:                 # the way back is the other page's
        assert words["left"] >= column["left"] + gutter - 0.5
        assert words["right"] <= column["right"] - gutter + 0.5
        assert column["top"] < words["top"] and words["bottom"] < column["bottom"]
    # and no tile stands under any of it
    for tile in said["tiles"]:
        apart = (tile["right"] <= column["left"] or tile["left"] >= column["right"]
                 or tile["bottom"] <= column["top"] or tile["top"] >= column["bottom"])
        assert apart, tile["title"]


@pytest.mark.parametrize("name, width", FRONTS)
def test_the_reading_line_is_under_the_sentence_and_the_legend_under_it(measured, name, width):
    said = measured[name, width]
    assert said["intro"]["bottom"] <= said["reading"]["top"] < said["intro"]["bottom"] + 20
    assert said["reading"]["bottom"] <= said["caption"]["top"] < said["legend"]["top"]
    assert said["caption"]["top"] < said["reading"]["bottom"] + 24
    assert said["reading"]["left"] == said["intro"]["left"]


@pytest.mark.parametrize("width", WIDTHS)
def test_the_reading_line_follows_the_cursor_and_returns_to_the_newest(measured, width):
    said = measured["front", width]
    newest = said["newest"][0]                        # the first tile: newest first
    assert said["atRest"] == newest == said["tiles"][0]["title"]
    title, read = said["onto"]
    assert read == title != newest
    assert said["acrossGap"] == title                 # crossing a gap is not leaving
    assert said["away"] == newest
    # and what the script laid out, it wrote nowhere in the page's own markup
    assert said["marked"] == ""


@pytest.mark.parametrize("name", ["front", "noscript"])
@pytest.mark.parametrize("width", WIDTHS)
def test_the_front_page_shows_the_last_year_and_the_way_to_the_whole(measured, name, width):
    said = measured[name, width]
    tiles = said["tiles"]
    assert len(tiles) == len(YEAR) > atrium.FRONT_SPAN_DAYS     # 365 days, some of them twice
    worded = [tile["title"] for tile in tiles if tile["title"]]
    assert day_of(worded[0]) == TODAY
    assert day_of(worded[-1]) == TODAY - datetime.timedelta(days=atrium.FRONT_SPAN_DAYS - 1)
    assert len(RECORD) > len(worded)                             # the record runs further back
    # empty days are slots among the rest, the same square
    assert sum(1 for tile in tiles if tile["kind"] == "empty") == 52

    rest, column = said["rest"], said["column"]
    assert said["restSays"] == '<a href="/mosaic.html">the whole mosaic</a>'
    assert rest["top"] >= max(tile["bottom"] for tile in tiles)     # after the last tile
    assert rest["top"] >= column["bottom"]
    # one quiet line, in the column's own measure
    assert rest["left"] == column["left"] and rest["width"] == column["width"]
    assert rest["height"] < 30


# ---- the whole mosaic's own page ------------------------------------------

@pytest.mark.parametrize("name", ["whole", "wholetoday"])
@pytest.mark.parametrize("width", WIDTHS)
def test_the_whole_mosaic_fills_the_page_s_width_between_its_margins(measured, name, width):
    said = measured[name, width]
    band = said["band"]
    assert band["left"] == MARGIN and band["right"] == said["client"] - MARGIN
    size, gap = [int(one) for one in re.findall(r"(\d+)px", said["list"])]
    assert size == atrium.tile_size(len(said["tiles"])) and gap == atrium.tile_gap(size)
    rows = {}
    for tile in said["tiles"]:
        assert tile["width"] == tile["height"] == size
        rows.setdefault(tile["top"], []).append(tile)
    fits = (band["width"] + gap) // (size + gap)
    # every row but the last of a year is as full as the band has room for
    full = [held for held in rows.values() if len(held) == fits]
    assert len(full) >= len(rows) - len(said["years"])
    assert max(len(held) for held in rows.values()) <= fits


@pytest.mark.parametrize("name", ["whole", "wholetoday"])
@pytest.mark.parametrize("width", WIDTHS)
def test_the_whole_mosaic_runs_oldest_first_left_to_right_and_row_by_row(measured, name, width):
    said = measured[name, width]
    tiles, band = said["tiles"], said["band"]
    assert tiles[0]["left"] == band["left"]
    for before, after in zip(tiles, tiles[1:]):
        same_row = after["top"] == before["top"] and after["left"] > before["left"]
        next_row = after["top"] > before["top"] and after["left"] == band["left"]
        assert same_row or next_row
    days = [day_of(tile["title"]) for tile in tiles if tile["title"]]
    assert days == sorted(days) and days[-1] > days[0]
    assert said["atRest"] == said["newest"][1]         # the last tile: oldest first


@pytest.mark.parametrize("width", WIDTHS)
def test_every_tile_since_the_first_is_on_the_whole_mosaic(measured, width):
    said = measured["whole", width]
    assert len(said["tiles"]) == len(atrium.slots(RECORD, TODAY)) > len(YEAR)
    worded = [tile["title"] for tile in said["tiles"] if tile["title"]]
    assert len(worded) == len(RECORD)
    assert day_of(worded[0]) == TODAY - datetime.timedelta(days=399)
    assert day_of(worded[-1]) == TODAY


@pytest.mark.parametrize("width", WIDTHS)
def test_each_year_of_the_whole_mosaic_begins_with_its_quiet_label(measured, width):
    said = measured["whole", width]
    years, tiles, band = said["years"], said["tiles"], said["band"]
    assert [year["year"] for year in years] == ["2025", "2026"]
    for year in years:
        # a line of its own across the band, in the page's small muted type
        assert year["left"] == band["left"] and year["width"] == band["width"]
        assert year["size"] == "14.4px" and year["ink"] == said["quiet"]
        assert year["height"] < 20
        its = [tile for tile in tiles if tile["title"] and day_of(tile["title"]).year
               == int(year["year"])]
        others = [tile for tile in tiles if tile["title"] and day_of(tile["title"]).year
                  < int(year["year"])]
        assert its[0]["top"] >= year["bottom"] and its[0]["left"] == band["left"]
        assert all(tile["bottom"] <= year["top"] for tile in others)
    assert years[0]["top"] < years[1]["top"]


@pytest.mark.parametrize("width", WIDTHS)
def test_the_whole_mosaic_has_its_menu_its_way_back_and_its_reading_line(measured, width):
    said = measured["whole", width]
    menu, home, reading = said["words"][1], said["home"], said["reading"]
    assert menu["top"] < home["top"] < reading["top"] < said["caption"]["top"]
    assert said["legend"]["bottom"] <= said["band"]["top"]
    assert said["rest"] is None and said["frame"] is None
    # the reading line follows the cursor here too, and returns to the newest
    title, read = said["onto"]
    assert read == title and said["acrossGap"] == title
    assert said["away"] == said["newest"][1] != title
    assert said["marked"] == ""


def test_the_reading_line_stays_at_the_top_as_the_whole_mosaic_scrolls(measured):
    """Fixed at the top of the window, wherever the page is long enough to scroll."""
    tall = [width for width in WIDTHS if measured["unforced", width]["tall"] > 250]
    assert 320 in tall
    for width in tall:
        assert measured["unforced", width]["stuck"] == 0
        assert measured["unforced", width]["scroll"] == measured["unforced", width]["client"]
