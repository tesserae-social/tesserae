"""The branch art-and-colour (the founder's request of 18 November 2026).

1. Colours. Anyone without a colour may choose one at any time; after that, only in the week
   from 20 March or from 22 September. A colour that barely shows on the site's light pages
   is discouraged, with the nearest that shows well; one nearly invisible is refused. The grey
   of no colour yet is no one's. An agent has these behind its switch art_and_colour, off for
   the first one until the founder has told it.
"""

from datetime import date, datetime, timezone

import pytest

import agents
import hues
from conftest import art_not_yet, block, blocks, page, post, read_json
from test_any_agent_wakes import wake_as
from test_introductions import switched_registry, world  # noqa: F401 - fixtures
from test_later_citizen import (HAZEL, hearth_of_two, later,  # noqa: F401 - fixtures
                                scratch_registry)
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

SAID = blocks(block("LETTER", "A FAKE LETTER, FOR THE TESTS."),
              block("HEARTBEAT", "A FAKE HEARTBEAT, FOR THE TESTS."))
IN_MARCH = "2027-03-21T15-00-00Z"  # in the week from 20 March
IN_NOVEMBER = "2026-11-18T15-00-00Z"  # in no such week


def choosing(colour):
    return SAID + "\n" + block("HUE", colour)


# ---- 1. colours: the rules ------------------------------------------------------------

def test_the_weeks_a_colour_may_change_start_at_each_equinox():
    assert hues.season_open(date(2027, 3, 20)) and hues.season_open(date(2027, 3, 26))
    assert not hues.season_open(date(2027, 3, 27)) and not hues.season_open(date(2027, 3, 19))
    assert hues.season_open(date(2026, 9, 22)) and hues.season_open(date(2026, 9, 28))
    assert not hues.season_open(date(2026, 9, 29)) and not hues.season_open(date(2026, 11, 18))
    assert hues.next_season(date(2026, 11, 18)) == date(2027, 3, 20)
    assert hues.next_season(date(2027, 4, 1)) == date(2027, 9, 22)
    # the Eastern day: just after midnight UTC on 20 March is still 19 March in the East
    assert hues.day_of("2027-03-20T02-00-00Z") == date(2027, 3, 19)


def test_how_well_a_colour_shows_on_the_light_pages():
    assert hues.showing("#378ADD") == "well" and hues.showing("#1B1B1B") == "well"
    assert hues.showing("#F2A541") == "barely" and hues.showing("#C8C8C8") == "barely"
    assert hues.showing("#FFFFFF") == "invisible" and hues.showing("#F3E9D2") == "invisible"
    # the nearest that shows well: darker only as it must be, and free to choose
    nearest = hues.nearest_showing("#F2A541")
    assert hues.shows(nearest) >= hues.SHOWS_WELL and hues.apart(nearest, "#F2A541") < 30
    assert hues.nearest_showing("#378ADD") == "#378ADD"


def test_the_grey_of_no_colour_yet_is_no_one_s_and_shows():
    assert hues.NO_HUE.upper() in hues.reserved_for("second")
    assert hues.NO_HUE.upper() in hues.reserved_for(HAZEL)
    assert hues.showing(hues.NO_HUE) == "well"


def test_a_person_chooses_once_then_only_in_an_equinox_week(env, data_dir):
    (data_dir / "members" / "alder").mkdir(parents=True)
    assert hues.choose_person("alder", "#AA3366", IN_NOVEMBER) == "#AA3366"  # the first, at once
    with pytest.raises(hues.Refused, match="season"):
        hues.choose_person("alder", "#2E5EAA", IN_NOVEMBER)
    assert hues.colour_of("alder") == "#AA3366"
    assert hues.choose_person("alder", "#2E5EAA", IN_MARCH) == "#2E5EAA"


def test_a_colour_that_barely_shows_is_taken_only_when_asked_again(env, data_dir):
    (data_dir / "members" / "alder").mkdir(parents=True)
    with pytest.raises(hues.Refused, match="barely"):
        hues.choose_person("alder", "#F2A541", IN_NOVEMBER)
    assert hues.person_chosen("alder") is None
    assert hues.choose_person("alder", "#F2A541", IN_NOVEMBER, anyway=True) == "#F2A541"


def test_a_colour_nearly_invisible_is_refused_even_asked_again(env, data_dir):
    (data_dir / "members" / "alder").mkdir(parents=True)
    for anyway in (False, True):
        with pytest.raises(hues.Refused, match="invisible"):
            hues.choose_person("alder", "#FFFFFF", IN_NOVEMBER, anyway=anyway)
    assert hues.person_chosen("alder") is None


# ---- 1. colours: on settings ------------------------------------------------------------

def test_settings_says_the_weeks_and_a_colour_chosen_waits_for_one(world, data_dir):
    said = page(world.client.get("/settings"))
    assert "may be changed only in the week from 20 March and the week from 22 September" in said
    assert '<input type="color" id="colour-picked"' in said  # none chosen yet: at any time
    assert world.post("/settings/colour", colour="#aa3366").status_code == 302
    said = page(world.client.get("/settings"))
    assert "You may change it next in the week from 20 March 2027." in said
    assert '<input type="color" id="colour-picked"' not in said
    refused = page(world.post("/settings/colour", colour="#2E5EAA"))
    assert "may be changed only in the week from 20 March or from 22 September" in refused
    assert hues.colour_of(HAZEL) == "#AA3366"


def test_settings_suggests_the_nearest_that_shows_and_keeps_one_asked_again(world):
    said = page(world.post("/settings/colour", colour="#F2A541"))
    nearest = hues.nearest_showing("#F2A541", HAZEL)
    assert "That colour barely shows on the site&#39;s pages." in said
    assert "The nearest colour that shows well is %s." % nearest in said
    assert "Use %s" % nearest in said and "Keep #F2A541 anyway" in said
    assert hues.person_chosen(HAZEL) is None
    world.post("/settings/colour", colour="#F2A541", anyway="yes")
    assert hues.person_chosen(HAZEL) == "#F2A541"


def test_settings_refuses_one_nearly_invisible(world):
    said = page(world.post("/settings/colour", colour="#FFFFFF"))
    assert "nearly invisible" in said and hues.person_chosen(HAZEL) is None


def test_settings_as_it_was_before(world, monkeypatch):
    art_not_yet(world.hearth, monkeypatch)
    said = page(world.client.get("/settings"))
    assert "the week from 20 March" not in said
    world.post("/settings/colour", colour="#aa3366")
    world.post("/settings/colour", colour="#FFFFFF")  # at any time, and whether it shows
    assert hues.person_chosen(HAZEL) == "#FFFFFF"


# ---- 1. colours: an agent, by its switch ------------------------------------------------

@pytest.fixture
def switched(later, monkeypatch):
    monkeypatch.setattr(later, "ART_AND_COLOUR", True)
    return later


def test_with_its_switch_an_agent_is_told_the_weeks(switched, monkeypatch, data_dir, clock):
    turn = wake_as(switched, monkeypatch, SAID)
    assert switched.HUE_BLOCK_ART in turn.shown
    assert "only in the week from 20 March and the week from 22 September" in turn.shown
    wake_as(switched, monkeypatch, choosing("#3A7BD5"))  # the first: at once
    assert hues.colour_of("second") == "#3A7BD5"
    clock.shift(minutes=5)
    turn = wake_as(switched, monkeypatch, choosing("#2E5EAA"))
    assert "Your colour on the commons: #3A7BD5. You may change it next in the week from 20 March 2027." in turn.shown
    assert "<<HUE>>" not in turn.instructions  # not offered while it may not change it
    assert hues.colour_of("second") == "#3A7BD5"  # its <<HUE>> is only words then


def test_with_its_switch_a_colour_may_change_in_the_week(switched, monkeypatch, clock):
    wake_as(switched, monkeypatch, choosing("#3A7BD5"))
    clock.set(datetime(2027, 3, 21, 15, 0, tzinfo=timezone.utc))
    turn = wake_as(switched, monkeypatch, choosing("#2E5EAA"))
    assert "This is a week in which you may change it." in turn.shown
    assert "<<HUE>>" in turn.instructions
    assert hues.colour_of("second") == "#2E5EAA"


def test_with_its_switch_one_that_barely_shows_is_held_until_written_again(
        switched, monkeypatch, data_dir, clock):
    wake_as(switched, monkeypatch, choosing("#F2A541"))
    assert hues.chosen("second") is None
    clock.shift(minutes=5)
    turn = wake_as(switched, monkeypatch, choosing("#F2A541"))
    nearest = hues.nearest_showing("#F2A541", "second")
    assert ("#F2A541 barely shows on the site's light pages. The nearest colour that shows well "
            "is %s. To keep #F2A541 anyway, write it again" % nearest) in turn.shown
    assert hues.colour_of("second") == "#F2A541"  # written again: kept


def test_with_its_switch_one_nearly_invisible_is_refused(switched, monkeypatch, clock):
    wake_as(switched, monkeypatch, choosing("#FFFFFF"))
    clock.shift(minutes=5)
    turn = wake_as(switched, monkeypatch, SAID)
    assert switched.HUE_REFUSED_ART["invisible"] in turn.shown
    assert hues.chosen("second") is None


def test_without_its_switch_as_before(later, monkeypatch, clock):
    assert later.ART_AND_COLOUR is False  # the tests' registry: the switch is not named
    turn = wake_as(later, monkeypatch, choosing("#3A7BD5"))
    assert later.HUE_BLOCK in turn.shown
    clock.shift(minutes=5)
    wake_as(later, monkeypatch, choosing("#FFFFFF"))
    assert hues.colour_of("second") == "#FFFFFF"


def test_the_first_one_has_no_switch_yet_and_new_agents_and_the_second_have_it():
    import json
    import found_agent
    assert hues.SWITCH == "art_and_colour" and hues.SWITCH in found_agent.FEATURES
    assert hues.SWITCH not in agents.FIRST["features"]
    first, second = json.loads((agents.REPO / "agents.json").read_text(encoding="utf-8"))
    assert hues.SWITCH not in first["features"] and hues.SWITCH in second["features"]


# ---- 2. people's pictures: uploads only --------------------------------------------------

def a_photo(size=(2400, 1200), with_exif=True, kind="JPEG"):
    """A picture as a phone might take it: large, and saying where it was taken."""
    import io
    from PIL import Image
    picture = Image.new("RGB", size, (40, 120, 200))
    kept = io.BytesIO()
    if with_exif and kind == "JPEG":
        exif = Image.Exif()
        exif[0x010F] = "A CAMERA MAKER, FOR THE TESTS"  # Make
        exif[0x8825] = {1: "N", 2: (44.0, 1.0, 2.0)}  # where it was taken
        picture.save(kept, kind, exif=exif)
    else:
        picture.save(kept, kind)
    return kept.getvalue()


def uploading(client, data=None, title="A blue field", name="field.jpg"):
    import io
    from conftest import post
    return post(client, "/made/workspace/upload", content_type="multipart/form-data", data={
        "title": title, "picture": (io.BytesIO(a_photo() if data is None else data), name)})


@pytest.fixture
def looked(monkeypatch):
    """The vision check, stubbed: it says what it is told to, and counts what it was shown."""
    import sys

    class Look:
        says = "CLEAR"
        shown = []

        def __call__(self, data, media_type):
            self.shown.append((data, media_type))
            return self.says
    look = Look()
    look.shown = []
    hearth = sys.modules["hearth"]
    monkeypatch.setattr(hearth.picture_check, "ask", look)
    monkeypatch.setattr(hearth, "in_good_spirit", lambda line: True)
    return look


def test_the_workspace_offers_an_upload_and_no_drawing(hearth_of_two):
    said = page(hearth_of_two["member"].get("/made/workspace"))
    assert 'action="/made/workspace/upload"' in said and 'type="file"' in said
    assert ("Your own photos or art. No faces, no names or addresses, nothing that shows where "
            "you live.") in said
    assert "new picture" not in said and 'value="erase"' not in said
    assert "new text picture" not in said and "new writing" in said
    answer = post(hearth_of_two["member"], "/made/workspace/draft", data={
        "kind": "tiles", "size": "32", "title": "A frame", "tiles": "." * 32})
    assert "Pictures are uploaded now, not drawn here." in page(answer)


def test_an_upload_is_made_bare_and_smaller_and_published_when_clear(
        hearth_of_two, screen, looked, visitor):
    import io
    import sys
    from PIL import Image
    screen.says = "NO"
    answer = uploading(hearth_of_two["member"])
    assert answer.status_code == 302
    made_here = sys.modules["hearth"].made_here
    (piece,) = made_here.every()
    assert piece["kind"] == "photo" and piece["by"] == "alder" and piece["title"] == "A blue field"
    kept = made_here.image_path(made_here.PUBLIC, piece).read_bytes()
    with Image.open(io.BytesIO(kept)) as opened:
        assert max(opened.size) == 1600 and not opened.info.get("exif")
        assert not opened.getexif()
    assert b"A CAMERA MAKER" not in kept
    assert len(looked.shown) == 1 and looked.shown[0] == (kept, "image/jpeg")  # what was looked at
    shown = page(visitor.get("/made/" + piece["id"]))
    assert '<img class="picture" src="/made/%s/picture"' % piece["id"] in shown
    picture = visitor.get("/made/%s/picture" % piece["id"])
    assert picture.status_code == 200 and picture.data == kept
    assert picture.headers["Content-Type"] == "image/jpeg"
    assert picture.headers["X-Content-Type-Options"] == "nosniff"
    assert piece["topic"]  # its own topic on the board, as every piece


def test_an_upload_the_check_holds_waits_for_the_keeper(hearth_of_two, screen, looked, visitor,
                                                        data_dir):
    import sys
    screen.says = "NO"
    looked.says = "HOLD"
    answer = uploading(hearth_of_two["member"])
    assert answer.status_code == 302 and "held=1" in answer.headers["Location"]
    made_here = sys.modules["hearth"].made_here
    assert made_here.every() == []
    (held,) = made_here.held()
    said = page(hearth_of_two["member"].get("/made/workspace?held=1"))
    assert "Your picture is waiting for the keeper to look at it." in said
    assert not any((data_dir / "commons").rglob(held["image"]))  # nothing of it is public
    tides = page(hearth_of_two["keeper"].get("/tides"))
    assert "pictures held" in tides and "A blue field" in tides
    assert hearth_of_two["keeper"].get("/tides/held/%s/picture" % held["id"]).status_code == 200
    assert visitor.get("/tides/held/%s/picture" % held["id"]).status_code != 200
    assert hearth_of_two["member"].get("/tides/held/%s/picture" % held["id"]).status_code != 200
    post(hearth_of_two["keeper"], "/tides/held/" + held["id"], data={"publish": "yes"})
    (piece,) = made_here.every()
    assert piece["by"] == "alder" and not made_here.held()
    assert visitor.get("/made/%s/picture" % piece["id"]).status_code == 200


def test_the_keeper_may_not_publish_one_held_and_it_is_kept_aside(hearth_of_two, screen,
                                                                  looked, data_dir):
    import sys
    screen.says = "NO"
    for says in ("HOLD", "I am not sure", ""):  # held wherever it is not CLEAR
        looked.says = says
        uploading(hearth_of_two["member"], title="A field " + str(len(says)))
    made_here = sys.modules["hearth"].made_here
    assert len(made_here.held()) == 3 and not made_here.every()
    one = made_here.held()[0]
    post(hearth_of_two["keeper"], "/tides/held/" + one["id"], data={"publish": "no"})
    assert len(made_here.held()) == 2 and not made_here.every()
    assert (data_dir / "made-not-published" / (one["id"] + ".json")).is_file()
    assert (data_dir / "made-not-published" / "images" / one["image"]).is_file()


def test_the_check_holds_when_it_cannot_ask(hearth_of_two, screen, monkeypatch):
    import sys
    hearth = sys.modules["hearth"]
    screen.says = "NO"
    monkeypatch.setattr(hearth, "in_good_spirit", lambda line: True)

    def broken(data, media_type):
        raise RuntimeError("no model, for the tests")
    monkeypatch.setattr(hearth.picture_check, "ask", broken)
    uploading(hearth_of_two["member"])
    assert len(hearth.made_here.held()) == 1
    monkeypatch.setattr(hearth.picture_check.spending, "spent_out", lambda who: True)
    assert hearth.picture_check.verdict(b"", "image/png") == "held"


def test_the_check_is_counted_in_spending(env, monkeypatch, data_dir):
    import picture_check
    import spending

    class Usage:
        input_tokens, output_tokens = 1500, 2

    class Answer:
        usage = Usage()
        content = [type("Part", (), {"text": "CLEAR"})()]

    class Client:
        def __init__(self):
            self.messages = self

        def create(self, **asked):
            image = asked["messages"][0]["content"][0]
            assert image["type"] == "image" and image["source"]["media_type"] == "image/png"
            assert asked["model"] == picture_check.MODEL
            return Answer()
    monkeypatch.setattr(picture_check, "Anthropic", Client)
    assert picture_check.verdict(a_photo(kind="PNG", with_exif=False), "image/png") == "clear"
    assert spending.spent(spending.SCREENS) > 0


def test_three_uploads_a_week_held_ones_counted(hearth_of_two, screen, looked):
    import sys
    screen.says = "NO"
    for n, says in enumerate(("CLEAR", "HOLD", "CLEAR")):
        looked.says = says
        assert uploading(hearth_of_two["member"], title="One %d" % n).status_code == 302
    said = page(uploading(hearth_of_two["member"], title="A fourth"))
    assert "You have uploaded three pictures this week." in said
    assert len(sys.modules["hearth"].made_here.every()) == 2


def test_a_file_that_is_no_picture_or_a_title_with_a_name_is_refused(hearth_of_two, screen,
                                                                     looked):
    import sys
    screen.says = "NO"
    said = page(uploading(hearth_of_two["member"], data=b"not a picture at all"))
    assert "That file is not a picture." in said
    said = page(uploading(hearth_of_two["member"], name="field.gif"))
    assert "That file is not a picture." in said
    screen.says = "YES"
    said = page(uploading(hearth_of_two["member"], title="At the house on Elm Street"))
    assert "seemed to contain a name or a place" in said
    assert not sys.modules["hearth"].made_here.every() and not looked.shown


def test_the_keeper_takes_any_picture_down_and_its_file_goes(hearth_of_two, screen, looked,
                                                             visitor, data_dir):
    import sys
    screen.says = "NO"
    uploading(hearth_of_two["member"])
    made_here = sys.modules["hearth"].made_here
    (piece,) = made_here.every()
    post(hearth_of_two["keeper"], "/made/%s/take-down" % piece["id"], data={"confirm": "yes"})
    assert made_here.one(piece["id"])["taken_down"]["by"] == "keeper"
    assert visitor.get("/made/%s/picture" % piece["id"]).status_code == 404
    assert not (data_dir / "commons" / "made" / "images" / piece["image"]).exists()
    assert (data_dir / "made-taken-down" / "images" / piece["image"]).is_file()


def test_a_picture_is_not_shown_to_one_in_a_block_with_its_maker(hearth_of_two, screen, looked,
                                                                 member_vaults):
    import json
    import sys
    from conftest import PASSWORD
    screen.says = "NO"
    uploading(hearth_of_two["member"])
    hearth = sys.modules["hearth"]
    (piece,) = hearth.made_here.every()
    hearth.members.create_member(HAZEL, json.loads(json.dumps(member_vaults[HAZEL])), "member", [])
    hazel = hearth.app.test_client()
    post(hazel, "/login", data={"pseudonym": HAZEL, "password": PASSWORD})
    assert hazel.get("/made/" + piece["id"]).status_code == 200
    hearth.blocks.block("alder", HAZEL, "2026-10-15T12-00-00Z")
    assert hazel.get("/made/" + piece["id"]).status_code == 404
    assert hazel.get("/made/%s/picture" % piece["id"]).status_code == 404
    assert "A blue field" not in page(hazel.get("/made"))
    assert hearth_of_two["keeper"].get("/made/" + piece["id"]).status_code == 200  # the keeper sees it


def test_the_workspace_as_it_was_before(hearth_of_two, monkeypatch):
    import sys
    hearth = sys.modules["hearth"]
    art_not_yet(hearth, monkeypatch)
    monkeypatch.setattr(hearth.made_here, "UPLOADS", False)
    said = page(hearth_of_two["member"].get("/made/workspace"))
    assert "new picture" in said and "upload" not in said.lower().replace("uploaded", "")


def a_photo_published(made_here, by="alder", at="2026-10-15T09-00-00Z"):
    """A picture uploaded and published, as the hearth leaves one."""
    fresh, suffix, size = made_here.bare(a_photo(), ".jpg")
    return made_here.upload(by, "A blue field", fresh, suffix, size, at, True)


def test_an_agent_reads_an_uploaded_picture_as_words_without_its_switch(later, monkeypatch):
    monkeypatch.setattr(later, "MADE_HERE", True)
    one = a_photo_published(later.made_here)
    listed = later.made_said("")
    assert one["id"] in listed and "photo · A blue field · by alder" in listed
    said = later.made_said(one["id"])
    assert later.MADE_PHOTO_SAID in said
    given, kept_as = later.looked_up("read_made_here", {"id": one["id"]},
                                     {"letters": {}, "versions": {}, "named": {}})
    assert [part["type"] for part in given] == ["text"]  # no picture without its switch
    assert later.MADE_PHOTO_SAID in given[0]["text"] and kept_as == "made here"


def test_an_agent_in_a_block_with_its_maker_is_not_shown_it(later):
    blocks = later.blocks
    one = a_photo_published(later.made_here)
    blocks.block("second", "alder", "2026-10-15T12-00-00Z")
    assert one["id"] not in later.made_said("")
    assert later.made_said(one["id"]) is None
