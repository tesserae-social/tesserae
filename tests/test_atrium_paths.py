"""The atrium's two paths, drawn from one record and compared.

The atrium is built twice from the same commons: once by build_atrium.py, which
bakes the page, and once by the script inside index.html, which redraws it in the
browser from the hearth's own copy. The two must agree, or a reader gets one
atrium and a crawler another.

This is the only test here that needs anything but Python: node, and jsdom for a
browser to run the page's script in. To run it:

    mkdir /tmp/jsdom && cd /tmp/jsdom && npm i jsdom
    NODE_PATH=/tmp/jsdom/node_modules python -m pytest tests/test_atrium_paths.py

On Windows, from PowerShell (forward slashes are fine there too):

    mkdir $env:TEMP/jsdom; cd $env:TEMP/jsdom; npm i jsdom
    $env:NODE_PATH = "$env:TEMP/jsdom/node_modules"
    python -m pytest tests/test_atrium_paths.py

Nothing is installed into this repository, and nothing goes out to the network
while the tests run: the page's one fetch is answered from the temporary commons.

Without node, or without jsdom, these tests skip and the rest of the suite runs
on Python alone.
"""

import json
import re
import shutil
import subprocess
import sys
from functools import lru_cache

import pytest

from conftest import NOW, REPO, write

NODE = shutil.which("node")

REGIONS = ["commons", "mosaic", "reading", "caption", "who", "calendar", "bench", "links"]

# the one moment both paths are read at: conftest's NOW, in milliseconds. The
# mosaic's run of days ends today and the calendar says what season today is, so
# a browser left on its own clock and a builder on its own would draw two atriums.
AT = int(NOW.timestamp() * 1000)

# a page that has been through jsdom and a page written by the builder differ in
# whitespace and in nothing else that matters, so both are read the same way
GAP = re.compile(r"\s+")
AS_OF = re.compile(r"as of [0-9]+ [A-Za-z]+ [0-9]{4}")

# The browser runs the page; this hands it the commons and prints what it drew.
# The baked page is parsed here too, with no script running, so that both come
# back through one serialiser and differ in nothing a browser would not see.
HARNESS = """
const fs = require("fs");
const { JSDOM } = require("jsdom");

const [page, baked, at, events, beats, bench, members] = process.argv.slice(2);
const said = (path) => fs.existsSync(path) ? fs.readFileSync(path, "utf8") : "";
const files = {
  "events.md": said(events),
  "heartbeats.md": said(beats),
  "bench.md": said(bench),
  "members.md": said(members),
};

const dom = new JSDOM(fs.readFileSync(page, "utf8"), {
  runScripts: "dangerously",
  url: "https://tesserae.social/",
  beforeParse(window) {
    // one moment, the same one the builder was given: the page asks what day it
    // is to end the mosaic's run and to say what season it is
    const Real = window.Date;
    class Frozen extends Real {
      constructor(...args) { super(...(args.length ? args : [Number(at)])); }
      static now() { return Number(at); }
    }
    window.Date = Frozen;
    // the hearth, answered from disk: the one thing the page reaches out for
    window.fetch = (asked) => {
      const name = String(asked).split("/").pop();
      const body = files[name];
      return Promise.resolve({
        ok: body !== undefined,
        text: () => Promise.resolve(body),
      });
    };
  },
});

const built = new JSDOM(fs.readFileSync(baked, "utf8"));

setTimeout(() => process.stdout.write(JSON.stringify({
  drawn: dom.window.document.body.innerHTML,
  built: built.window.document.body.innerHTML,
})), 100);
"""


@lru_cache(maxsize=1)
def jsdom_here():
    """Whether node can find jsdom, and so whether the page can be run at all."""
    if not NODE:
        return False
    done = subprocess.run([NODE, "-e", "require.resolve('jsdom')"],
                          capture_output=True, text=True)
    return done.returncode == 0


pytestmark = [
    pytest.mark.skipif(NODE is None, reason="node is not on the path"),
    pytest.mark.skipif(not jsdom_here(),
                       reason="jsdom is not where node can find it; see this file's docstring"),
]


def regions_of(page):
    """What lies between each pair of markers, with its whitespace made even."""
    found = {}
    for name in REGIONS:
        cut = re.search(r"<!-- %s:start -->(.*?)<!-- %s:end -->" % (name, name), page, re.S)
        assert cut, "no %s markers in the page" % name
        # the day a page was drawn is the day it was drawn on; both say today,
        # and only a midnight between the two runs could make them differ
        found[name] = AS_OF.sub("as of today", GAP.sub(" ", cut.group(1)).strip())
    return found


def build(atrium, monkeypatch):
    """Bake the page as build_atrium.py does, and say where it put it."""
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()
    return atrium.page_path


def both_paths(tmp_path, data_dir, baked):
    """The two atriums, each as a browser holds it: the baked one, and the drawn one."""
    harness = write(tmp_path / "harness.js", HARNESS)
    done = subprocess.run(
        [NODE, str(harness), str(REPO / "index.html"), str(baked), str(AT),
         str(data_dir / "commons" / "events.md"),
         str(data_dir / "commons" / "heartbeats.md"),
         str(data_dir / "commons" / "bench.md"),
         str(data_dir / "commons" / "members.md")],
        capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr
    said = json.loads(done.stdout)
    return regions_of(said["built"]), regions_of(said["drawn"])


MEMBERS = ("citizen · the first one, unnamed by its own choosing · attends at dawn\n"
           "member · the founder · keeps the hearth\n")


def a_record(data_dir, bench="", members=MEMBERS):
    """One commons, with a little of everything in it."""
    write(data_dir / "commons" / "events.md",
          "2026-09-02 · word · the word was published\n"
          "2026-09-04 · founding · the first one was founded\n"
          "2026-09-30 · the tide paused\n"                       # the older two-field shape
          "2026-10-01 · whistling · a kind we do not know\n"  # and a kind we do not
          "2026-10-08 · seal · a bond was sealed\n"
          "2026-10-09 · event · a line with \"quotes\" & <marks>\n"
          "nonsense, and no date at all\n")
    # both shapes of a heartbeat line are here: the newer, which writes the
    # middot between the name and the words, and the older, which ran the two
    # straight together. Both paths must read them the one way.
    write(data_dir / "commons" / "heartbeats.md",
          "- 2026-10-10T11-00-00Z · the first one · attended at dawn\n"
          "- 2026-10-10T18-00-00Z · the first one attended by day\n"
          "- 2026-10-11T00-00-00Z · the first one · attended in the evening\n"
          "- 2026-10-16T03-59-59Z · the first one attended a second before midnight\n"
          "- 2026-10-16T04-00-00Z · the first one · attended a second after\n"
          "- 2026-10-09T09-00-00Z · the first one attended, out of order\n"
          "not a heartbeat\n")
    write(data_dir / "commons" / "bench.md", bench)
    write(data_dir / "commons" / "members.md", members)


def test_both_paths_draw_the_same_atrium(atrium, data_dir, monkeypatch, tmp_path):
    a_record(data_dir, bench="- 2026-10-01 · Mira · the lake was still · and quiet\n"
                             "- 2026-10-02 · <em>me</em> · <b>hello</b>\n")
    here, there = both_paths(tmp_path, data_dir, build(atrium, monkeypatch))
    for name in REGIONS:
        assert here[name] == there[name], name


def test_both_paths_agree_on_an_empty_bench(atrium, data_dir, monkeypatch, tmp_path):
    a_record(data_dir, bench="")
    here, there = both_paths(tmp_path, data_dir, build(atrium, monkeypatch))
    assert here["bench"] == there["bench"] == ""
    assert here["links"] == there["links"]
    assert "Leave a line" in here["links"]


def test_an_empty_record_is_where_the_two_paths_part(atrium, data_dir, monkeypatch, tmp_path):
    """A record with nothing in it is the one place they answer differently, on purpose.

    The builder is reading files beside it, so an empty record is the truth and
    it draws an empty mosaic. The page is reading a hearth over the wire, so a
    record with nothing in it is a hearth that has gone quiet, and what was baked
    into the page stands rather than the atrium emptying itself.
    """
    for name in ("events.md", "heartbeats.md", "bench.md", "members.md"):
        write(data_dir / "commons" / name, "")
    here, there = both_paths(tmp_path, data_dir, build(atrium, monkeypatch))

    assert "0 so far" in here["caption"]
    assert "<li" not in here["mosaic"]        # no days, so no slots and no holes
    assert here["who"] == "" and here["calendar"].startswith('<p class="calendar">')
    assert there == regions_of((REPO / "index.html").read_text(encoding="utf-8"))


def test_the_browser_path_leaves_the_page_alone_when_the_hearth_is_quiet(tmp_path, data_dir):
    """A hearth that cannot be reached changes nothing: what was baked in stands."""
    for name in ("events.md", "heartbeats.md", "bench.md", "members.md"):
        (data_dir / "commons" / name).unlink(missing_ok=True)
    harness = write(tmp_path / "harness.js", HARNESS.replace(
        "ok: body !== undefined", "ok: false"))  # a hearth that answers nothing at all
    done = subprocess.run(
        [NODE, str(harness), str(REPO / "index.html"), str(REPO / "index.html"), str(AT),
         *[str(REPO / "index.html")] * 4],
        capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr
    said = json.loads(done.stdout)
    assert regions_of(said["drawn"]) == regions_of(said["built"])


def test_the_harness_shows_what_it_compared(atrium, data_dir, monkeypatch, tmp_path):
    """The two paths are compared on real markup, not on nothing at all."""
    a_record(data_dir, bench="- 2026-10-01 · Mira · the lake was still\n")
    here, there = both_paths(tmp_path, data_dir, build(atrium, monkeypatch))
    for said in (here, there):
        # nine days carry the twelve tiles; the other thirty-six of the run are holes
        assert said["mosaic"].count("<li") == 48
        assert said["mosaic"].count('<li class="empty">') == 36
        assert said["mosaic"].startswith('<ul class="mosaic" style="--tile:34px;--gap:4px"')
        assert "tile-word" in said["mosaic"] and "tile-seal" in said["mosaic"]
        assert "the visitor's bench" in said["bench"]
        assert "waking at dawn" in said["mosaic"] and "waking at night" in said["mosaic"]
        # however a heartbeat line was written, it is read out the one way
        assert said["mosaic"].count("the first one · attended") == 6
        assert "Ask to join — the door opens slowly" in said["links"]
        assert "<h2>who is here</h2>" in said["who"]
        assert "hue-the-first-one-unnamed-by-its-own-choosing" in said["who"]
        assert said["calendar"] == ('<p class="calendar">it is autumn · '
                                    "the long-night letters are written on 21 December</p>")


def test_both_paths_agree_when_no_one_says_who_is_here(atrium, data_dir, monkeypatch, tmp_path):
    """No members.md is no section, and the same no section on either path."""
    a_record(data_dir, members="")
    here, there = both_paths(tmp_path, data_dir, build(atrium, monkeypatch))
    assert here["who"] == there["who"] == ""
    assert here["calendar"] == there["calendar"] != ""
