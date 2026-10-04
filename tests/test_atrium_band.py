"""The mosaic's band, measured in a real browser.

The mosaic stands in a band across the whole window, 16px in from either edge,
while the words keep their narrow column. Whether that pushes the page sideways
is something only a browser laying the page out can say, so this is the one
test here that needs Chrome: it is run headless on a copy of the page with a
scrollbar that takes up room down its side, and asked what it measured. A
headless window will not go as narrow as a phone, so the copy is shown in a
frame of each width instead, which is a window of exactly that width to the
page inside it.

Chrome is looked for where it is usually installed, or where CHROME says it is.
Without it these tests skip and the rest of the suite runs as it did.

Nothing goes out to the network: the copy has the page's own scripts taken out,
so what is measured is what was baked in.
"""

import json
import os
import re
import shutil
import subprocess

import pytest

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

MARGIN = 16      # the band's own, at either side
SCROLLBAR = 17   # the room a scrollbar takes down the side of a window on Windows
NEAR = 0.05      # a browser lays out in sixty-fourths of a pixel, and a third is not one

# A scrollbar that is always there and always takes its room, whatever the
# browser would have drawn left to itself: the case 100vw gets wrong.
FORCED = ("<style>html { overflow-y: scroll; } "
          "html::-webkit-scrollbar { width: %dpx; height: %dpx; }</style>"
          % (SCROLLBAR, SCROLLBAR))

# What the page is asked once it is laid out. The last of it fills the frame
# with far more tiles than it can hold, to see where its height stops.
MEASURE = """<script>
addEventListener("load", () => {
  const root = document.documentElement, frame = document.querySelector(".mosaic");
  const box = el => { const r = el.getBoundingClientRect();
    return { left: r.left, right: r.right, top: r.top, width: r.width, height: r.height }; };
  let right = 0, left = 0;
  for (const el of document.body.querySelectorAll("*")) {
    const r = el.getBoundingClientRect();
    if (!r.width && !r.height) continue;
    right = Math.max(right, r.right); left = Math.min(left, r.left);
  }
  const said = {
    inner: innerWidth, client: root.clientWidth, scroll: root.scrollWidth,
    bodyScroll: document.body.scrollWidth, left, right,
    band: box(document.querySelector(".band")), frame: box(frame),
    inside: frame.clientWidth,
    cap: getComputedStyle(frame).maxHeight,
    columns: [...document.querySelectorAll(".column")].map(box),
    under: [".reading", ".caption", ".legend"].map(s => box(document.querySelector(s))),
    words: ["header", ".menu", ".intro", ".who", ".calendar", "footer"]
      .map(s => box(document.querySelector(s))),
    tiles: [...frame.children].map(box),
    tile: getComputedStyle(frame.children[0]).width,
  };
  for (let n = 0; n < 2000; n++) frame.appendChild(frame.children[0].cloneNode());
  said.full = box(frame);
  said.fullScroll = root.scrollWidth;
  parent.postMessage(JSON.stringify([innerWidth, said]), "*");
});
</script>"""

# The page that holds the frames, one for each width, and writes down what
# each of them says it measured.
FRAMES = """<!DOCTYPE html>
<html><body>
%s
<script>
const heard = {};
addEventListener("message", event => {
  const [width, said] = JSON.parse(event.data);
  heard[width] = said;
  let out = document.getElementById("measured");
  if (!out) { out = document.createElement("pre"); out.id = "measured";
              document.body.appendChild(out); }
  out.textContent = JSON.stringify(heard);
});
</script>
</body></html>
"""

SCRIPT = re.compile(r"<script>.*?</script>", re.S)


@pytest.fixture(scope="module")
def measured(tmp_path_factory):
    """The page as Chrome lays it out, at each width: asked once, and kept."""
    yard = tmp_path_factory.mktemp("band")
    page = (REPO / "index.html").read_text(encoding="utf-8")
    page = SCRIPT.sub("", page).replace("</head>", FORCED + "</head>")
    page = page.replace("</body>", MEASURE + "</body>")
    write(yard / "index.html", page)
    shutil.copy(REPO / "style.css", yard / "style.css")

    write(yard / "frames.html", FRAMES % "\n".join(
        '<iframe src="index.html" style="width:%dpx;height:900px;border:0"></iframe>' % width
        for width in WIDTHS))

    done = subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
         "--user-data-dir=%s" % (yard / "profile"), "--window-size=2000,1000",
         "--virtual-time-budget=5000", "--dump-dom", (yard / "frames.html").as_uri()],
        capture_output=True, text=True, encoding="utf-8", timeout=120)
    said = re.search(r'<pre id="measured">(.*?)</pre>', done.stdout, re.S)
    assert said, "Chrome measured nothing: %s" % done.stderr[-500:]
    found = json.loads(said.group(1).replace("&quot;", '"').replace("&amp;", "&"))
    return {int(width): what for width, what in found.items()}


@pytest.mark.parametrize("width", WIDTHS)
def test_the_window_is_the_width_asked_for_and_has_its_scrollbar(measured, width):
    """What is measured is the case that matters: a scrollbar that takes its room."""
    assert sorted(measured) == sorted(WIDTHS)
    said = measured[width]
    assert said["inner"] == width
    assert said["client"] == width - SCROLLBAR


@pytest.mark.parametrize("width", WIDTHS)
def test_nothing_scrolls_sideways(measured, width):
    said = measured[width]
    assert said["scroll"] == said["client"]
    assert said["bodyScroll"] <= said["client"]
    # and not merely hidden: nothing on the page stands past either edge of it
    assert said["left"] >= 0
    assert said["right"] <= said["client"]


@pytest.mark.parametrize("width", WIDTHS)
def test_the_band_runs_edge_to_edge_with_an_even_margin(measured, width):
    said = measured[width]
    assert said["band"]["left"] == MARGIN
    assert said["band"]["right"] == said["client"] - MARGIN
    assert said["frame"]["left"] == said["band"]["left"]
    assert said["frame"]["width"] == said["band"]["width"] == width - SCROLLBAR - 2 * MARGIN


@pytest.mark.parametrize("width", WIDTHS)
def test_the_words_keep_their_narrow_column(measured, width):
    said = measured[width]
    middle = said["client"] / 2
    gutter = 20 if width <= 480 else 24
    assert len(said["columns"]) == 3
    for column in said["columns"]:
        assert column["width"] == min(600, said["client"])
        assert abs((column["left"] + column["right"]) / 2 - middle) <= 0.5
    # everything that is read stands inside the column's own gutters
    for words in said["words"] + said["under"]:
        assert words["left"] >= said["columns"][0]["left"] + gutter - 0.5
        assert words["right"] <= said["columns"][0]["right"] - gutter + 0.5


@pytest.mark.parametrize("width", WIDTHS)
def test_the_line_the_caption_and_the_legend_stand_under_the_band(measured, width):
    said = measured[width]
    reading, caption, legend = said["under"]
    assert reading["top"] >= said["frame"]["top"] + said["frame"]["height"]
    assert reading["top"] < caption["top"] < legend["top"]
    # centred under it: the column they are in shares the band's own middle
    band = (said["band"]["left"] + said["band"]["right"]) / 2
    for line in said["under"]:
        assert abs((line["left"] + line["right"]) / 2 - band) <= 0.5


@pytest.mark.parametrize("width", WIDTHS)
def test_the_band_is_no_taller_than_a_third_of_its_width(measured, width):
    said = measured[width]
    cap = said["band"]["width"] / 3
    assert abs(float(said["cap"].rstrip("px")) - cap) <= NEAR
    assert said["frame"]["height"] <= cap + NEAR
    # filled far past what it holds, the frame stops at its cap and the page
    # still does not move sideways
    assert abs(said["full"]["height"] - cap) <= NEAR
    assert said["full"]["width"] == said["band"]["width"]
    assert said["fullScroll"] == said["client"]


@pytest.mark.parametrize("width", WIDTHS)
def test_the_tiles_run_left_to_right_and_row_by_row(measured, width):
    """Oldest at the top left, newest last: each tile stands after the one before it."""
    said = measured[width]
    tiles = said["tiles"]
    assert len(tiles) > 1
    assert said["tile"] == "34px"
    assert tiles[0]["left"] == said["band"]["left"]
    assert tiles[0]["top"] == said["frame"]["top"]
    for before, after in zip(tiles, tiles[1:]):
        same_row = after["top"] == before["top"] and after["left"] > before["left"]
        next_row = after["top"] > before["top"] and after["left"] == said["band"]["left"]
        assert same_row or next_row
        assert after["right"] <= said["band"]["right"]
    # as many to a row as the frame has room for, less whatever its own
    # scrollbar takes where the rows stand taller than the cap
    rows = len({tile["top"] for tile in tiles})
    across = (said["inside"] + 4) // 38               # 34px tiles, 4px between
    assert rows == -(-len(tiles) // across)
