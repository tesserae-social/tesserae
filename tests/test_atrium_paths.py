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

REGIONS = ["mosaic", "reading", "caption", "offering", "who", "calendar",
           "bench", "links"]

# the one moment both paths are read at: conftest's NOW, in milliseconds. The
# mosaic's run of days ends today and the calendar says what season today is, so
# a browser left on its own clock and a builder on its own would draw two atriums.
AT = int(NOW.timestamp() * 1000)

# a page that has been through jsdom and a page written by the builder differ in
# whitespace and in nothing else that matters, so both are read the same way
GAP = re.compile(r"\s+")

# the intro lies outside every marker, so neither path may touch it
INTRO = re.compile(r'<div class="intro">.*?</div>', re.S)

# The browser runs the page; this hands it the commons and prints what it drew.
# The baked page is parsed here too, with no script running, so that both come
# back through one serialiser and differ in nothing a browser would not see.
HARNESS = """
const fs = require("fs");
const { JSDOM } = require("jsdom");

// the whole commons, handed over as a folder: the page asks for files under
// commons/ by name, and one of them - an offering's own record - is asked for
// only once the index says there is one
const [page, baked, at, commons] = process.argv.slice(2);
const path = require("path");
const under = (asked) => {
  const wanted = String(asked).split("/commons/")[1];
  if (!wanted) return undefined;
  const where = path.join(commons, wanted);
  if (!where.startsWith(commons) || !fs.existsSync(where)) return undefined;
  return fs.readFileSync(where, "utf8");
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
    // the hearth, answered from disk: the one place the page reaches out to
    window.fetch = (asked) => {
      const body = under(asked);
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
        found[name] = GAP.sub(" ", cut.group(1)).strip()
    return found


def build(atrium, monkeypatch):
    """Bake the page as build_atrium.py does, and say where it put it."""
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()
    return atrium.page_path


def intro_of(page):
    """The atrium's intro, with its whitespace made even."""
    found = INTRO.search(page)
    assert found, "no intro in the page"
    return GAP.sub(" ", found.group())


def both_pages(tmp_path, data_dir, baked, at=AT):
    """The two atriums entire, each as a browser holds it: the baked, and the drawn."""
    harness = write(tmp_path / "harness.js", HARNESS)
    done = subprocess.run(
        [NODE, str(harness), str(REPO / "index.html"), str(baked), str(at),
         str(data_dir / "commons")],
        capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr
    said = json.loads(done.stdout)
    return said["built"], said["drawn"]


def both_paths(tmp_path, data_dir, baked, at=AT):
    """The two atriums, each as a browser holds it: the baked one, and the drawn one."""
    built, drawn = both_pages(tmp_path, data_dir, baked, at)
    return regions_of(built), regions_of(drawn)


MEMBERS = ("citizen · the first one, unnamed by its own choosing · attends at dawn\n"
           "member · the founder · keeps the hearth\n")

# two offerings, placed on two days: one that is words, and one that is a picture
OFFERINGS = ("- 2026-10-11 · 2026-10-11T09-00-00Z · letter · the founder and the first one\n"
             "- 2026-10-13 · 2026-10-13T09-00-00Z · passage · the founder and the first one\n")

RECORDS = {
    "2026-10-11T09-00-00Z": {
        "id": "2026-10-11T09-00-00Z", "offered_by": "first", "kind": "picture",
        "source": "to-founder-2026-10-11T08-00-00Z", "text": "", "at": "2026-10-11T08-30-00Z",
        "sealed_at": "2026-10-11T09-00-00Z", "file": "2026-10-11T09-00-00Z.svg",
        "signatures": {"founder": "x", "first": "y"},
    },
    "2026-10-13T09-00-00Z": {
        "id": "2026-10-13T09-00-00Z", "offered_by": "founder", "kind": "passage",
        "source": "founder-2026-10-12T09-00-00Z",
        "text": "The lake was still this morning.\n\nAnd \"quoted\" & <marked> besides.",
        "at": "2026-10-13T08-30-00Z", "sealed_at": "2026-10-13T09-00-00Z",
        "signatures": {"founder": "x", "first": "y"},
    },
}


def offerings(data_dir, index=OFFERINGS, records=RECORDS):
    """The offerings of the commons: the index, and a record for each."""
    write(data_dir / "commons" / "offerings.md", index)
    for one, record in records.items():
        write(data_dir / "commons" / "offerings" / (one + ".json"),
              json.dumps(record, indent=2) + "\n")


def a_record(data_dir, bench="", members=MEMBERS, offered=""):
    """One commons, with a little of everything in it.

    Every file the page asks the hearth for is written, even where it is empty:
    the hearth answers each of them with what it holds, and an empty file is
    what it holds before anything has been written there. A file that answers
    nothing at all is a hearth gone quiet, which is tested on its own.
    """
    write(data_dir / "commons" / "offerings.md", offered)
    write(data_dir / "commons" / "events.md",
          "2026-09-02 · word · the word was published\n"
          "2026-09-04 · founding · the first one was founded\n"
          "2026-09-30 · the tide paused\n"                       # the older two-field shape
          "2026-10-01 · whistling · a kind we do not know\n"  # and a kind we do not
          "2026-10-08 · seal · a bond was sealed\n"
          "2026-10-09 · event · a line with \"quotes\" & <marks>\n"
          # the commons keeps a line for an offering too; both paths pass it over
          # and draw the tile from offerings.md, where the offering's name is
          "2026-10-11 · offering · an offering was placed\n"
          "2026-10-13 · offering · an offering was placed\n"
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
    offerings(data_dir)
    here, there = both_paths(tmp_path, data_dir, build(atrium, monkeypatch))
    for name in REGIONS:
        assert here[name] == there[name], name


def test_both_paths_keep_the_intro_word_for_word(atrium, data_dir, monkeypatch, tmp_path):
    """The intro is outside every marker: neither path writes it, and neither may move it."""
    a_record(data_dir)
    built, drawn = both_pages(tmp_path, data_dir, build(atrium, monkeypatch))
    assert intro_of(drawn) == intro_of(built)
    assert intro_of(built) == intro_of((REPO / "index.html").read_text(encoding="utf-8"))
    assert ("Tesserae is a small place on the internet where people and AIs become friends"
            in intro_of(built))
    # all four paragraphs, and no fifth: neither path writes any of them
    assert "It works like an old-fashioned correspondence." in intro_of(built)
    assert "AI is changing fast, and it will keep changing." in intro_of(built)
    assert "You both have to choose it, and either of you can leave." in intro_of(built)
    assert intro_of(drawn).count("<p") == 4


def test_neither_path_writes_an_em_dash(atrium, data_dir, monkeypatch, tmp_path):
    a_record(data_dir, bench="- 2026-10-01 · Mira · the lake was still\n")
    offerings(data_dir)
    built, drawn = both_pages(tmp_path, data_dir, build(atrium, monkeypatch))
    assert "—" not in built and "—" not in drawn
    assert "the visitor's bench" in drawn


@pytest.mark.parametrize("stamp, season", [
    ("2026-07-01T16-00-00Z", "summer"),
    ("2026-09-23T16-00-00Z", "autumn"),
    ("2027-01-05T16-00-00Z", "winter"),
    ("2027-04-01T16-00-00Z", "spring"),
])
def test_both_paths_reckon_the_season_from_today(atrium, data_dir, clock, monkeypatch,
                                                 tmp_path, stamp, season):
    """The season line is worked out on the day, by the builder and by the browser alike."""
    a_record(data_dir)
    clock.set(stamp)
    at = int(clock.at.timestamp() * 1000)
    here, there = both_paths(tmp_path, data_dir, build(atrium, monkeypatch), at)
    assert here["calendar"] == there["calendar"]
    assert there["calendar"].startswith('<p class="calendar">it is %s · ' % season)


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
    for name in ("events.md", "heartbeats.md", "bench.md", "members.md", "offerings.md"):
        write(data_dir / "commons" / name, "")
    here, there = both_paths(tmp_path, data_dir, build(atrium, monkeypatch))

    assert "one tile for every event in our history" in here["caption"]
    assert "<li" not in here["mosaic"]        # no days, so no slots and no holes
    assert here["who"] == "" and here["calendar"].startswith('<p class="calendar">')
    assert there == regions_of((REPO / "index.html").read_text(encoding="utf-8"))


def test_the_browser_path_leaves_the_page_alone_when_the_hearth_is_quiet(tmp_path, data_dir):
    """A hearth that cannot be reached changes nothing: what was baked in stands."""
    for name in ("events.md", "heartbeats.md", "bench.md", "members.md", "offerings.md"):
        (data_dir / "commons" / name).unlink(missing_ok=True)
    harness = write(tmp_path / "harness.js", HARNESS.replace(
        "ok: body !== undefined", "ok: false"))  # a hearth that answers nothing at all
    done = subprocess.run(
        [NODE, str(harness), str(REPO / "index.html"), str(REPO / "index.html"), str(AT),
         str(data_dir / "commons")],
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
        assert "Ask to join. The door opens slowly." in said["links"]
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


# ---- the offerings, on both paths ----------------------------------------

def test_both_paths_show_the_newest_offering_and_no_other(atrium, data_dir, monkeypatch,
                                                          tmp_path):
    a_record(data_dir)
    offerings(data_dir)
    here, there = both_paths(tmp_path, data_dir, build(atrium, monkeypatch))
    assert here["offering"] == there["offering"]
    for said in (here, there):
        assert "<h2>offered from the hearth</h2>" in said["offering"]
        assert "13 October 2026 · a passage · the founder and the first one" in said["offering"]
        assert "The lake was still this morning." in said["offering"]
        # two paragraphs inside the quotation, and what was quoted in them
        # escaped the one way on both paths
        quoted = said["offering"].split("<blockquote>")[1].split("</blockquote>")[0]
        assert "&amp; &lt;marked&gt; besides." in quoted
        assert quoted.count("<p>") == 2
        assert ('<a href="https://hearth.tesserae.social/offerings#2026-10-13T09-00-00Z">'
                "all offerings</a>") in said["offering"]
        assert "2026-10-11T09-00-00Z.svg" not in said["offering"]   # the older one is past


def test_both_paths_draw_an_offering_as_a_tile_that_leads_to_it(atrium, data_dir, monkeypatch,
                                                                tmp_path):
    a_record(data_dir)
    offerings(data_dir)
    here, there = both_paths(tmp_path, data_dir, build(atrium, monkeypatch))
    for said in (here, there):
        # one tile per offering, and no second tile from the commons' own line
        assert said["mosaic"].count('class="tile-offering"') == 2
        assert said["mosaic"].count("an offering was placed") == 0
        assert ('<a href="https://hearth.tesserae.social/offerings#2026-10-13T09-00-00Z"'
                in said["mosaic"])
        assert ('<a href="https://hearth.tesserae.social/bonds/founder-first.json"'
                in said["mosaic"])
        # the tiles with nowhere to lead are still hover-only
        assert said["mosaic"].count("<a href=") == 3
        assert '<span class="key tile-offering"></span>offering' in said["caption"]


def test_both_paths_show_a_picture_offering_from_the_hearth(atrium, data_dir, monkeypatch,
                                                            tmp_path):
    a_record(data_dir)
    offerings(data_dir, index=OFFERINGS.splitlines(True)[0])
    here, there = both_paths(tmp_path, data_dir, build(atrium, monkeypatch))
    assert here["offering"] == there["offering"]
    for said in (here, there):
        assert ('<img class="offering" src="https://hearth.tesserae.social/commons/offerings/'
                '2026-10-11T09-00-00Z.svg" alt="an offering from the founder and the first '
                'one">') in said["offering"]
        assert "<blockquote>" not in said["offering"]


def test_both_paths_leave_the_section_off_where_nothing_was_offered(atrium, data_dir,
                                                                    monkeypatch, tmp_path):
    a_record(data_dir)
    write(data_dir / "commons" / "offerings.md", "")
    here, there = both_paths(tmp_path, data_dir, build(atrium, monkeypatch))
    assert here["offering"] == there["offering"] == ""
    assert "tile-offering" not in here["mosaic"] + there["mosaic"]
    assert "offering" not in here["caption"] and "offering" not in there["caption"]
