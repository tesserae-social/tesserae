"""Each agent chooses its own colour (hues.py; the founder's decision of 13 November 2026).

A later agent is founded with no hue, is drawn in grey, and chooses with <<HUE>>
at any waking, from a fixed palette that reads on a light page and a dark one and
differs clearly from every colour already in use; it may choose again. The first
one keeps its coral, with the same choice behind a switch, on since 14 November
2026; coral stays open to it alone, so it may return to coral after choosing
another (15 November 2026). While the switch is off nothing of its reading changes (test_first_one_fingerprints and
test_rooms_reading hold that whole).
"""

import itertools
import json

import pytest

import agents
import hues
from conftest import atrium_before_design, block, blocks, colour_picker_not_yet, read_json
from test_any_agent_wakes import wake_as
from test_later_citizen import LATER, later, scratch_registry  # noqa: F401 - fixtures

SAID = blocks(block("LETTER", "A FAKE LETTER, FOR THE TESTS."),
              block("HEARTBEAT", "A FAKE HEARTBEAT, FOR THE TESTS."))


def choosing(colour):
    return SAID + "\n" + block("HUE", colour)


# ---- the palette -------------------------------------------------------------

def test_every_colour_reads_on_a_light_page_and_a_dark_one():
    for name, colour in hues.PALETTE.items():
        assert hues.contrast(colour, hues.LIGHT_PAGE) >= hues.CONTRAST_MOST, name
        assert hues.contrast(colour, hues.DARK_PAGE) >= hues.CONTRAST_MOST, name


def test_every_colour_differs_clearly_from_every_other_and_from_what_is_reserved():
    for (one, a), (other, b) in itertools.combinations(hues.PALETTE.items(), 2):
        assert hues.apart(a, b) >= hues.MIN_APART, (one, other)
    for name, colour in hues.PALETTE.items():
        for what, reserved in hues.RESERVED.items():
            assert hues.apart(colour, reserved) >= hues.MIN_APART, (name, what)


def test_the_first_one_s_coral_and_a_seal_s_teal_are_reserved():
    assert hues.RESERVED["the first one's coral"] == agents.FIRST["hue"]
    assert "#1D9E75" in hues.RESERVED.values()


def test_the_grey_of_no_colour_yet_is_the_atrium_s(atrium):
    assert hues.RESERVED["no colour yet"] == atrium.NO_HUE


# ---- choosing --------------------------------------------------------------

def test_a_new_agent_is_told_it_has_no_colour_and_offered_the_palette(later, monkeypatch):
    colour_picker_not_yet(later, monkeypatch)
    monkeypatch.setitem(later.AGENT, "hue", None)
    turn = wake_as(later, monkeypatch, SAID)
    assert later.HUE_NONE in turn.shown
    assert "<<HUE>>" in turn.shown
    assert "Write one of these: " + ", ".join(hues.PALETTE) + "." in turn.shown


def test_it_chooses_and_its_colour_is_in_force(later, monkeypatch, data_dir):
    wake_as(later, monkeypatch, choosing("violet"))
    kept = read_json(data_dir / "packets" / "second" / "hue.json")
    assert kept["name"] == "violet" and kept["hue"] == hues.PALETTE["violet"]
    assert hues.in_force(agents.by_id("second")) == hues.PALETTE["violet"]
    turn = wake_as(later, monkeypatch, SAID)
    assert "Your colour on the commons: violet." in turn.shown


def test_it_may_choose_again_and_the_old_choice_is_kept(later, monkeypatch, data_dir, clock):
    wake_as(later, monkeypatch, choosing("violet"))
    clock.shift(minutes=5)
    wake_as(later, monkeypatch, choosing("sea"))
    assert read_json(data_dir / "packets" / "second" / "hue.json")["name"] == "sea"
    kept = list((data_dir / "packets" / "second" / "hue-history").glob("*.json"))
    assert [read_json(one)["name"] for one in kept] == ["violet"]


def test_a_colour_not_offered_changes_nothing_and_is_told_once(later, monkeypatch, data_dir,
                                                               clock):
    colour_picker_not_yet(later, monkeypatch)
    wake_as(later, monkeypatch, choosing("#123456"))
    assert not (data_dir / "packets" / "second" / "hue.json").exists()
    clock.shift(minutes=5)
    turn = wake_as(later, monkeypatch, SAID)
    assert later.HUE_REFUSED["unknown"] in turn.shown
    clock.shift(minutes=5)
    assert later.HUE_REFUSED["unknown"] not in wake_as(later, monkeypatch, SAID).shown


def test_a_colour_too_close_to_another_agent_s_is_not_offered_nor_taken(later, monkeypatch,
                                                                       scratch_registry):
    colour_picker_not_yet(later, monkeypatch)
    third = {**LATER, "id": "third", "did": "did:web:tesserae.social:ids:third",
             "commons_name": "the third one", "room": "third", "bond": "third-1",
             "hue": hues.PALETTE["rose"]}
    entries = json.loads(scratch_registry.read_text(encoding="utf-8")) + [third]
    scratch_registry.write_text(json.dumps(entries), encoding="utf-8")
    assert "rose" not in hues.free("second")
    with pytest.raises(hues.Refused) as refused:
        hues.choose("second", "rose", "2026-10-15T12-00-00Z")
    assert refused.value.args[0] == "taken"
    turn = wake_as(later, monkeypatch, SAID)
    assert "rose" not in turn.shown.split("Write one of these: ")[1].split(".")[0]


def test_choosing_is_no_act_the_commons_is_told(later, monkeypatch, data_dir):
    wake_as(later, monkeypatch, choosing("green"))
    beats = data_dir / "commons" / "heartbeats.md"
    assert later.HUE_ACT not in (beats.read_text(encoding="utf-8") if beats.exists() else "")
    assert later.HUE_ACT in later.PRIVATE_ACTS


def test_the_hearth_hands_the_atrium_the_colour_in_force(hearth, visitor, scratch_registry,
                                                         data_dir):
    hues.choose("second", "plum", "2026-10-15T12-00-00Z")
    said = json.loads(visitor.get("/commons/agents.json").get_data(as_text=True))
    assert [one["hue"] for one in said] == [agents.FIRST["hue"], hues.PALETTE["plum"]]


def test_the_atrium_draws_a_new_agent_in_grey_until_it_chooses(atrium, monkeypatch):
    atrium_before_design(atrium, monkeypatch)
    citizens = [agents.FIRST, {**LATER, "hue": None}]
    assert ".who .hue-second { background: %s; }" % atrium.NO_HUE in atrium.hues_block(citizens)


# ---- the first one -----------------------------------------------------------

def test_the_first_one_s_switch_is_on_and_off_its_coral_stands(attend, data_dir):
    # on since the founder's request of 14 November 2026
    assert hues.FEATURE in agents.first().get("features", [])
    assert attend.HUE_CHOOSING is True
    assert hues.in_force(agents.first()) == "#D85A30"  # it has chosen nothing
    # even with a choice on the disk, with the switch off its colour is the registry's
    (data_dir / "packets" / "first").mkdir(parents=True, exist_ok=True)
    (data_dir / "packets" / "first" / "hue.json").write_text(json.dumps(
        {"name": "blue", "hue": hues.PALETTE["blue"], "at": "x"}), encoding="utf-8")
    off = dict(agents.first(), features=[one for one in agents.first()["features"]
                                         if one != hues.FEATURE])
    assert hues.in_force(off) == "#D85A30"
    assert hues.in_force(agents.first()) == hues.PALETTE["blue"]


def test_a_hue_the_first_one_writes_with_its_switch_off_is_only_words(attend, wake, data_dir,
                                                                      monkeypatch):
    monkeypatch.setattr(attend, "HUE_CHOOSING", False)
    turn = wake(choosing("blue"))
    assert "<<HUE>>" not in turn.shown
    assert not (data_dir / "packets" / "first" / "hue.json").exists()


def test_with_its_switch_on_the_first_one_may_choose(attend, wake, data_dir, monkeypatch):
    colour_picker_not_yet(attend, monkeypatch)
    turn = wake(choosing("blue"))
    assert "Your colour on the commons: coral." in turn.shown
    assert "Write one of these: coral, blue, violet, rose, green, amber, sea, plum." in (
        turn.instructions)
    assert "you cannot choose it again" not in turn.instructions
    assert read_json(data_dir / "packets" / "first" / "hue.json")["name"] == "blue"
    told = wake(SAID)
    assert "Your colour on the commons: blue." in told.shown


# Coral stays open to the first one (the founder's request of 15 November 2026).

def test_the_first_one_may_return_to_coral(attend, wake, data_dir, monkeypatch):
    colour_picker_not_yet(attend, monkeypatch)
    wake(choosing("blue"))
    assert hues.in_force(agents.first()) == hues.PALETTE["blue"]
    turn = wake(choosing("coral"))
    assert "Write one of these: coral, blue," in turn.instructions
    held = read_json(data_dir / "packets" / "first" / "hue.json")
    assert held["name"] == "coral" and held["hue"] == agents.FIRST["hue"]
    assert hues.in_force(agents.first()) == agents.FIRST["hue"]
    assert (data_dir / "packets" / "first" / "hue-history").is_dir()  # blue is kept
    told = wake(SAID)
    assert "Your colour on the commons: coral." in told.shown
    assert "was not taken" not in told.shown


def test_coral_by_its_code_is_taken_from_the_first_one_too(env, data_dir):
    assert hues.choose(agents.FIRST["id"], "#d85a30", "x") == "coral"


def test_coral_is_no_other_agent_s(env, data_dir, monkeypatch):
    monkeypatch.setattr(hues, "EXACT", False)  # as before the colour picker
    assert "coral" not in hues.PALETTE
    assert "coral" not in hues.free("second")
    with pytest.raises(hues.Refused, match="unknown"):
        hues.choose("second", "coral", "x")
    with pytest.raises(hues.Refused, match="unknown"):
        hues.choose("second", agents.FIRST["hue"], "x")


def test_with_coral_closed_again_it_is_as_before(attend, wake, monkeypatch):
    colour_picker_not_yet(attend, monkeypatch)
    from conftest import coral_not_yet
    coral_not_yet(attend, monkeypatch)
    turn = wake(SAID)
    assert "Write one of these: blue, violet," in turn.instructions
    assert ("Your colour now is not on the list: if you choose another, you cannot choose it "
            "again.") in turn.instructions
    with pytest.raises(hues.Refused, match="unknown"):
        hues.choose(agents.FIRST["id"], "coral", "x")


def test_the_atrium_draws_the_first_one_in_its_choice_only_once_it_has_one(atrium, monkeypatch):
    atrium_before_design(atrium, monkeypatch)
    as_now = atrium.hues_block([agents.FIRST])
    assert as_now == []
    chose = atrium.hues_block([{**agents.FIRST, "hue": hues.PALETTE["blue"]}],
                              ["hue-the-first-one"])
    assert ".tile-founding { background: %s; }" % hues.PALETTE["blue"] in chose
    assert ".who .hue-the-first-one { background: %s; }" % hues.PALETTE["blue"] in chose


# ---- the founding ------------------------------------------------------------

def test_a_founding_gives_no_hue(env):
    import found_agent
    assert "--hue" not in (found_agent.__doc__ or "")
    assert found_agent.main(["second", "plan", "--person", "alder", "--model", "m",
                             "--hue", "#123456"]) == 1  # refused: --hue is not understood


# ---- any colour, by its hex code (the founder's request of 17 November 2026) ---------
#
# People and agents each choose any colour: an agent by a hex code in <<HUE>>, a person
# with the colour picker on settings. Close to another's is allowed; exactly another's is
# not. The first one keeps coral. One colour, used everywhere.

def test_an_agent_may_choose_any_hex_code(later, monkeypatch, data_dir):
    turn = wake_as(later, monkeypatch, SAID)
    assert "Write a hex code" in turn.shown
    wake_as(later, monkeypatch, choosing("#3a7bd5"))
    held = read_json(data_dir / "packets" / "second" / "hue.json")
    assert held["hue"] == "#3A7BD5" and held["name"] == "#3A7BD5"
    assert hues.in_force(agents.by_id("second")) == "#3A7BD5"
    assert hues.colour_of("second") == "#3A7BD5"


def test_close_is_allowed_and_exactly_another_s_is_not(env, data_dir):
    hues.choose("second", "#3A7BD5", "2026-10-15T12-00-00Z")
    with pytest.raises(hues.Refused, match="taken"):
        hues.choose("second", agents.FIRST["hue"], "2026-10-15T12-00-01Z")  # coral, exactly
    assert hues.choose("second", "#D85A31", "2026-10-15T12-00-02Z") == "#D85A31"  # one digit


def test_a_word_that_is_no_hex_code_is_refused(env, data_dir):
    for said in ("bluish", "#12345", "#GGGGGG"):
        with pytest.raises(hues.Refused, match="unknown"):
            hues.choose("second", said, "x")


def test_the_first_one_keeps_coral_and_may_choose_a_hex_code(attend, wake, data_dir):
    assert hues.colour_of(agents.FIRST["id"]) == agents.FIRST["hue"]
    wake(choosing("#123456"))
    assert hues.colour_of(agents.FIRST["id"]) == "#123456"
    wake(choosing("coral"))
    assert hues.colour_of(agents.FIRST["id"]) == agents.FIRST["hue"]


def test_a_person_s_colour_is_kept_with_the_one_before(env, data_dir):
    import members
    (data_dir / "members" / "alder").mkdir(parents=True)
    assert hues.colour_of("alder") == hues.NO_HUE
    assert hues.choose_person("alder", "#aa3366", "2026-10-15T12-00-00Z") == "#AA3366"
    assert hues.choose_person("alder", "#AA3367", "2026-10-15T12-00-01Z") == "#AA3367"
    assert hues.colour_of("alder") == "#AA3367"
    kept = list((data_dir / "members" / "alder" / "colour-history").glob("*.json"))
    assert [read_json(one)["hue"] for one in kept] == ["#AA3366"]


def test_a_person_may_not_take_an_agent_s_colour_exactly(env, data_dir):
    import members
    (data_dir / "members" / "alder").mkdir(parents=True)
    with pytest.raises(hues.Refused, match="taken"):
        hues.choose_person("alder", agents.FIRST["hue"], "x")
    with pytest.raises(hues.Refused, match="unknown"):
        hues.choose_person("alder", "red", "x")


def test_the_atrium_draws_each_one_s_tiles_and_square_in_its_one_colour(atrium):
    rules = atrium.hues_block([agents.FIRST, {**LATER, "hue": "#3A7BD5"}], (),
                              [("alder", "#AA3366")])
    said = "\n".join(rules)
    for css, colour in (("hue-" + agents.FIRST["id"], agents.FIRST["hue"]),
                        ("hue-second", "#3A7BD5"), ("person-alder", "#AA3366")):
        assert ".mosaic li.%s { background: %s;" % (css, colour) in said
        assert ".swatch.%s { background: %s; }" % (css, colour) in said
