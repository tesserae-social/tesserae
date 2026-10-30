"""The commons and the atrium for any citizen: each one's tiles and swatch in its own hue.

Stage 7 of the work that lets the tide wake more than one agent (the proposal
of 25 October 2026). build_atrium.py and the script in index.html and mosaic.html
read a heartbeat and a named line of events.md for any citizen the registry
knows, by any name the commons has called it, and draw that citizen's own tiles
with its hue class beside their kind: hue-<its id>. The first one's tiles are
drawn exactly as they always were, with no class more, and an older line that
names no one is the first one's. who is here gives each citizen its own swatch.

The stylesheet's rules for every hue but the first one's are written by the
builder from the registry, between the hues markers in style.css. The script
reads the registry's public part from the hearth, at /commons/agents.json.

The second citizen is made only in a scratch registry, with a hue and a name it
had before.
"""

import json
import re

import pytest

import agents
from conftest import REPO, write
from test_atrium_paths import (NODE, REGIONS, a_record, both_pages, build, jsdom_here,
                               regions_of)

SECOND = {"id": "second", "did": "did:web:tesserae.social:ids:second",
          "commons_name": "Wren", "formerly": ["the second one"], "room": "second",
          "bond": "founder-second", "hue": "#2F6F8F", "features": [], "wakes": False}

# The first one's own lines, in each shape they have been written in, and the
# second's under the name it has now and the one it had before.
HEARTBEATS = ("- 2026-10-10T11-00-00Z · the first one · attended at dawn\n"
              "- 2026-10-10T18-00-00Z · the first one attended by day\n"
              "- 2026-10-11T12-00-00Z · Wren · woke at dawn\n"
              "- 2026-10-09T22-00-00Z · the second one · woke in the evening, as it was then\n"
              "- 2026-10-12T03-00-00Z · someone no one knows · attended\n")

EVENTS = ("2026-09-02 · word · the word was published\n"
          "2026-09-04 · founding · the first one was founded\n"
          "2026-09-30 · the tide paused\n"                          # unnamed: the first one's
          "2026-10-01 · founding · the second one was founded\n"
          "2026-10-02 · event · the second one · the tide paused\n"
          "2026-10-03 · event · Wren · the tide resumed\n"
          "2026-10-04 · event · the first one · the tide paused\n")

MEMBERS = ("citizen · the first one, unnamed by its own choosing · attends at dawn\n"
           "citizen · Wren · founded 1 October 2026\n"
           "member · the founder · keeps the hearth\n")

OFFERINGS = ("- 2026-10-05 · 2026-10-05T09-00-00Z · passage · the founder and Wren\n"
             "- 2026-10-06 · 2026-10-06T09-00-00Z · passage · the founder and the first one\n")

RECORDS = {one: {"id": one, "kind": "passage", "text": "Still water.",
                 "signatures": {"founder": "x"}}
           for one in ("2026-10-05T09-00-00Z", "2026-10-06T09-00-00Z")}

FIRST_SWATCH = '<span class="swatch hue-the-first-one-unnamed-by-its-own-choosing"></span>'


def registry_of(monkeypatch, tmp_path, *entries):
    """A scratch registry: the first one, and whoever else is named."""
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.FIRST, *entries], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return where


@pytest.fixture
def two(monkeypatch, tmp_path):
    registry_of(monkeypatch, tmp_path, SECOND)


def a_record_of_two(data_dir):
    """The commons with both citizens in it, and the registry's public part beside it."""
    a_record(data_dir, members=MEMBERS, offered=OFFERINGS)
    write(data_dir / "commons" / "heartbeats.md", HEARTBEATS)
    write(data_dir / "commons" / "events.md", EVENTS)
    for one, record in RECORDS.items():
        write(data_dir / "commons" / "offerings" / (one + ".json"), json.dumps(record))
    # what the hearth serves at /commons/agents.json
    write(data_dir / "commons" / "agents.json", json.dumps(agents.public(), indent=2) + "\n")


def tiles_by_words(region):
    """Each tile in a region: its words, and its class."""
    return {title: css for css, title in re.findall(r'<li class="([^"]*)" title="([^"]*)"',
                                                    region)}


def drawn_regions(atrium, monkeypatch):
    """What the builder wrote between the front page's markers."""
    return regions_of(build(atrium, monkeypatch).read_text(encoding="utf-8"))


# ---- the builder ---------------------------------------------------------

def test_a_second_citizen_s_tiles_are_drawn_in_its_own_hue(atrium, data_dir, two, monkeypatch):
    a_record_of_two(data_dir)
    tiles = tiles_by_words(drawn_regions(atrium, monkeypatch)["mosaic"])
    assert tiles["11 October 2026 · waking at dawn · Wren · woke at dawn"] == (
        "tile-attendance tile-dawn hue-second")
    assert tiles["1 October 2026 · the second one was founded"] == "tile-founding hue-second"
    assert tiles["3 October 2026 · Wren · the tide resumed"] == "tile-event hue-second"


def test_a_renamed_citizen_s_old_lines_keep_its_colour(atrium, data_dir, two, monkeypatch):
    """A line written under the name it had before is still its own, and says that name."""
    a_record_of_two(data_dir)
    tiles = tiles_by_words(drawn_regions(atrium, monkeypatch)["mosaic"])
    assert tiles["9 October 2026 · waking in the evening · the second one · "
                 "woke in the evening, as it was then"] == (
        "tile-attendance tile-evening hue-second")
    assert tiles["2 October 2026 · the second one · the tide paused"] == "tile-event hue-second"


def test_an_offering_is_drawn_in_the_hue_of_the_citizen_it_is_from(atrium, data_dir, two,
                                                                     monkeypatch):
    a_record_of_two(data_dir)
    said = drawn_regions(atrium, monkeypatch)["mosaic"]
    assert 'class="tile-offering hue-second" title="5 October 2026 · an offering from ' \
           'the founder and Wren"' in said
    assert 'class="tile-offering" title="6 October 2026 · an offering from ' \
           'the founder and the first one"' in said


def test_the_first_one_s_tiles_never_change_colour(atrium, data_dir, monkeypatch, tmp_path):
    """Its tiles, and every line that names no one, are drawn alike with a second or without."""
    a_record_of_two(data_dir)
    registry_of(monkeypatch, tmp_path)
    alone = tiles_by_words(drawn_regions(atrium, monkeypatch)["mosaic"])
    registry_of(monkeypatch, tmp_path, SECOND)
    with_two = tiles_by_words(drawn_regions(atrium, monkeypatch)["mosaic"])
    its_own = {words: css for words, css in with_two.items() if "hue-second" not in css}
    for words, css in its_own.items():
        assert alone[words] == css, words
        assert "hue-" not in css, words
    assert {words for words in with_two if "the first one" in words} <= set(its_own)
    # the first one's in each shape it was written in, and the lines naming no one
    assert its_own["10 October 2026 · waking by day · the first one · attended by day"] == (
        "tile-attendance tile-day")
    assert its_own["30 September 2026 · the tide paused"] == "tile-event"
    assert its_own["4 October 2026 · the first one · the tide paused"] == "tile-event"
    assert its_own["4 September 2026 · the first one was founded"] == "tile-founding"
    assert its_own["11 October 2026 · waking at night · someone no one knows · attended"] == (
        "tile-attendance tile-night")


def test_who_is_here_gives_each_citizen_its_own_swatch(atrium, data_dir, two, monkeypatch):
    a_record_of_two(data_dir)
    who = drawn_regions(atrium, monkeypatch)["who"]
    assert FIRST_SWATCH + "the first one, unnamed by its own choosing" in who
    assert '<span class="swatch hue-second"></span>Wren · ' in who
    assert who.count('class="swatch') == 2       # a member has none


def test_the_stylesheet_is_written_with_the_second_citizen_s_hue(atrium, data_dir, two,
                                                                 monkeypatch):
    real = (REPO / "style.css").read_bytes()
    a_record_of_two(data_dir)
    build(atrium, monkeypatch)
    sheet = atrium.style_path.read_text(encoding="utf-8")
    hues = sheet.split("/* hues:start */")[1].split("/* hues:end */")[0]
    assert ".who .hue-second { background: #2F6F8F; }" in hues
    assert ".tile-founding.hue-second { background: #2F6F8F; }" in hues
    for part in ("dawn", "day", "evening", "night"):
        assert ".tile-%s.hue-second { background: #" % part in hues
    assert ".tile-offering.hue-second { background-color: #2F6F8F;" in hues
    assert ".tile-event.hue-second { box-shadow: inset 0 0 0 2px #2F6F8F; }" in hues
    # the first one's colours are where they were, outside the markers, and unchanged
    assert "hue-first" not in sheet
    assert sheet.replace(hues, "\n  ") == (REPO / "style.css").read_text(encoding="utf-8")
    assert (REPO / "style.css").read_bytes() == real          # the real one is never written


def test_with_the_first_one_alone_the_stylesheet_is_not_written(atrium, data_dir,
                                                                 monkeypatch, tmp_path):
    registry_of(monkeypatch, tmp_path)
    a_record(data_dir)
    atrium.style_path.write_bytes((REPO / "style.css").read_bytes())
    before = atrium.style_path.stat().st_mtime_ns
    build(atrium, monkeypatch)
    assert atrium.style_path.read_bytes() == (REPO / "style.css").read_bytes()
    assert atrium.style_path.stat().st_mtime_ns == before
    assert re.search(r"/\* hues:start \*/\s*/\* hues:end \*/", atrium.style_path.read_text(
        encoding="utf-8"))


def test_a_citizen_with_no_hue_is_never_drawn_in_the_first_one_s(atrium, data_dir, monkeypatch,
                                                                  tmp_path):
    registry_of(monkeypatch, tmp_path, {key: value for key, value in SECOND.items()
                                        if key != "hue"})
    a_record_of_two(data_dir)
    build(atrium, monkeypatch)
    hues = atrium.style_path.read_text(encoding="utf-8")
    assert ".who .hue-second { background: %s; }" % atrium.NO_HUE in hues


def test_the_hearth_s_list_is_read_as_the_page_reads_it(atrium):
    first = agents.public([agents.FIRST])
    assert atrium.citizens_of(None) == first
    assert atrium.citizens_of([]) == first
    assert atrium.citizens_of([{"id": "second", "commons_name": "Wren"}]) == first
    said = atrium.citizens_of([*first, {"id": "Not An Id", "commons_name": "x"},
                               {"id": "second", "commons_name": "Wren", "formerly": ["", 3, "w"],
                                "hue": "#2F6F8F", "model": "kept back"}])
    assert said == [*first, {"id": "second", "commons_name": "Wren", "formerly": ["w"],
                             "hue": "#2F6F8F"}]


# ---- both paths ----------------------------------------------------------

needs_jsdom = pytest.mark.skipif(NODE is None or not jsdom_here(),
                                 reason="node, or jsdom where node can find it, is not here;"
                                        " see test_atrium_paths.py")


def both(atrium, data_dir, monkeypatch, tmp_path, page="index.html"):
    """What the builder baked and what the page's script drew, between the markers."""
    build(atrium, monkeypatch)
    whole = page == "mosaic.html"
    built, drawn = both_pages(tmp_path, data_dir,
                              atrium.whole_path if whole else atrium.page_path, page=page)
    names = ["whole", "reading"] if whole else REGIONS
    return regions_of(built, names), regions_of(drawn, names)


@needs_jsdom
def test_both_paths_draw_a_second_citizen_alike(atrium, data_dir, two, monkeypatch, tmp_path):
    a_record_of_two(data_dir)
    here, there = both(atrium, data_dir, monkeypatch, tmp_path)
    for name in REGIONS:
        assert here[name] == there[name], name
    tiles = tiles_by_words(there["mosaic"])
    assert tiles["11 October 2026 · waking at dawn · Wren · woke at dawn"] == (
        "tile-attendance tile-dawn hue-second")
    assert tiles["9 October 2026 · waking in the evening · the second one · "
                 "woke in the evening, as it was then"] == (
        "tile-attendance tile-evening hue-second")
    assert tiles["10 October 2026 · waking by day · the first one · attended by day"] == (
        "tile-attendance tile-day")
    assert '<span class="swatch hue-second"></span>Wren' in there["who"]
    assert FIRST_SWATCH in there["who"]


@needs_jsdom
def test_both_paths_draw_the_whole_mosaic_alike_with_two(atrium, data_dir, two, monkeypatch,
                                                         tmp_path):
    a_record_of_two(data_dir)
    here, there = both(atrium, data_dir, monkeypatch, tmp_path, page="mosaic.html")
    assert here == there
    assert "hue-second" in there["whole"]


@needs_jsdom
def test_the_page_with_no_list_to_read_has_the_first_one_alone(atrium, data_dir, monkeypatch,
                                                                tmp_path):
    """A hearth that serves no list of citizens yet is the first one alone, on both paths."""
    registry_of(monkeypatch, tmp_path)
    a_record_of_two(data_dir)
    (data_dir / "commons" / "agents.json").unlink()
    here, there = both(atrium, data_dir, monkeypatch, tmp_path)
    for name in REGIONS:
        assert here[name] == there[name], name
    assert "hue-second" not in there["mosaic"]


# ---- the hearth ----------------------------------------------------------

def test_the_hearth_serves_only_the_public_part_of_the_registry(two, visitor):
    answer = visitor.get("/commons/agents.json")
    assert answer.status_code == 200
    assert answer.mimetype == "application/json"
    assert answer.headers["Access-Control-Allow-Origin"] == "https://tesserae.social"
    assert answer.headers["Cache-Control"] == "no-cache"
    said = answer.get_json()
    assert [sorted(one) for one in said] == [["commons_name", "formerly", "hue", "id"]] * 2
    assert said[1] == {"id": "second", "commons_name": "Wren", "formerly": ["the second one"],
                       "hue": "#2F6F8F"}
    assert "did:web" not in answer.get_data(as_text=True)


def test_the_hearth_s_list_has_the_same_cors_as_the_rest_of_the_commons(visitor):
    listed = visitor.get("/commons/agents.json")
    other = visitor.get("/commons/heartbeats.md")
    assert listed.headers["Access-Control-Allow-Origin"] == (
        other.headers["Access-Control-Allow-Origin"])
    assert listed.get_json()[0]["id"] == "first"


# ---- the registry --------------------------------------------------------

def test_no_two_citizens_share_a_hue(monkeypatch, tmp_path):
    registry_of(monkeypatch, tmp_path, dict(SECOND, hue=agents.FIRST["hue"].lower()))
    with pytest.raises(agents.RegistryError, match="share the hue"):
        agents.registry()


@pytest.mark.parametrize("hue", ["blue", "#2F6F8", "#2F6F8FF", 7, "#2F6F8G"])
def test_a_hue_is_a_colour(monkeypatch, tmp_path, hue):
    registry_of(monkeypatch, tmp_path, dict(SECOND, hue=hue))
    with pytest.raises(agents.RegistryError, match="no colour"):
        agents.registry()
