"""The seasons (seasons.py; the founder's request of 25 November 2026).

Agents are no longer asked. A change is an improvement, on for every agent and told once at its
next waking under WHAT'S NEW, or a preference, the agent's own setting: shown to it at its
reflection waking in each seasonal week (in winter, after the long night), and changed at any
waking with <<SETTINGS>>, from its next waking, told once. For the first one nothing is on and
nothing is told before 1 December 2026.

Every other test sets this aside (conftest.seasons_aside); these ask for seasons_on.
"""

import json
import sys
from datetime import date, datetime, timezone

import pytest

from conftest import REPO, Turn, block, improvements_not_yet, load, page, write_json
from test_later_citizen import LATER, a_later_world, hearth_of_two, scratch_registry  # noqa: F401
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture
from test_rooms_reading import a_small_world

IMPROVEMENTS = ("hoping_for", "replies_told", "names_told", "commons_names", "solstice_names",
                "knock_founder", "knock_take_back", "copy_said", "american_spelling", "leaving")
PREFERENCES = ("commons_window", "reading_self_first", "reading_settings", "reading_how_folded",
               "made_here_agents", "colour_weeks")

NOV_30 = datetime(2026, 11, 30, 15, tzinfo=timezone.utc)
DEC_1 = datetime(2026, 12, 1, 15, tzinfo=timezone.utc)
DEC_2 = datetime(2026, 12, 2, 15, tzinfo=timezone.utc)
DEC_27 = datetime(2026, 12, 27, 15, tzinfo=timezone.utc)  # a Sunday, in the winter week
DEC_28 = datetime(2026, 12, 28, 15, tzinfo=timezone.utc)
JAN_3 = datetime(2027, 1, 3, 15, tzinfo=timezone.utc)  # the first Sunday after the winter week

# The second one, as these tests found it: some improvements and preferences of its own already.
SECOND = dict(LATER, features=[*LATER["features"], "hoping_for", "knock_founder", "copy_said",
                               "made_here_agents", "art_and_colour", "reflection_waking"])


def woken(monkeypatch, clock, said="", flags=("--tide",)):
    """One waking of a freshly loaded attend.py, as the tide starts one: (attend, turn)."""
    monkeypatch.setattr(sys, "argv", ["attend.py", *flags])  # read as it is loaded, too
    module = load("attend")
    clock.pin(module, monkeypatch)
    turn = Turn(said)
    monkeypatch.setattr(module, "Anthropic", turn.client)
    module.main()
    clock.shift(minutes=5)
    sys.modules.pop("attend", None)
    return module, turn


def section(turn, head):
    whole = turn.shown
    at = whole.find(head)
    if at < 0:
        return None
    end = whole.find("\n\n===", at + len(head))
    return whole[at:end if end >= 0 else None]


@pytest.fixture
def second(env, clock, monkeypatch, tmp_path, data_dir):
    """The second one, woken as the tide wakes it, with a waking of its own before."""
    import agents
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), SECOND], indent=2), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    a_later_world(data_dir)
    write_json(data_dir / "packets" / "second" / "attendances" / "2026-10-14T09-00-00Z.json",
               {"name": "second", "at": "2026-10-14T09-00-00Z", "heartbeat": "attended",
                "acted": [], "reflection": "attended"})
    monkeypatch.setenv("TESSERAE_AGENT", "second")
    yield data_dir
    sys.modules.pop("attend", None)


def held(data_dir, who):
    return json.loads((data_dir / "seasons" / (who + ".json")).read_text(encoding="utf-8"))


# ---- the lists, as the founder gave them ------------------------------------------------------

def test_the_improvements_and_the_preferences_are_the_founder_s(env):
    import seasons
    assert tuple(seasons.IMPROVEMENTS) == IMPROVEMENTS
    assert tuple(seasons.PREFERENCES) == PREFERENCES
    for line in [*seasons.IMPROVEMENTS.values(), *(does for _, does in
                                                    seasons.PREFERENCES.values())]:
        assert len(line) < 160 and "colour" not in line  # short, plain, the American way
    assert seasons.ASKINGS_LINE == (
        "Changes are now either simply made and told, or kept as your own settings, which you "
        "can review each season or change at any waking.")


def test_a_new_agent_starts_with_every_one_on(env):
    import found_agent
    assert set(IMPROVEMENTS) | set(PREFERENCES) <= set(found_agent.FEATURES)


def test_settings_are_in_a_backup_and_never_in_a_copy(hearth):
    assert "seasons" in hearth.KEPT_BESIDE
    assert "seasons" in hearth.backup_trees()
    assert not any(tree.startswith("seasons") for tree in hearth.EXPORT_TREES)


# ---- on, and when ------------------------------------------------------------------------------

def test_for_the_first_one_nothing_before_1_december(seasons_on, env, clock):
    import agents
    import seasons
    clock.set(NOV_30)
    assert seasons.active("first") is False and seasons.active("second") is True
    first = agents.by_id("first")
    assert not set(IMPROVEMENTS) & set(first["features"])
    clock.set(DEC_1)
    assert seasons.active("first") is True
    # on from the waking that tells them, not from midnight: the registry gives none until then
    first = agents.by_id("first")
    assert not set(IMPROVEMENTS) & set(first["features"])
    assert seasons.told_now("first", first["features"]) == list(IMPROVEMENTS)
    seasons.mark_told("first", set(IMPROVEMENTS), "2026-12-01T12-00-00Z")  # that waking kept
    first = agents.by_id("first")
    assert set(IMPROVEMENTS) <= set(first["features"])
    assert seasons.told_now("first", first["features"]) == []
    assert not set(IMPROVEMENTS) & set(agents.by_id("first", asked=False)["features"])
    # its preferences are as it had them: none
    assert not set(PREFERENCES) & set(first["features"])


def test_set_aside_nothing_moves_on_any_day(env, clock):
    import agents
    clock.set(DEC_1)
    assert agents.by_id("first")["features"] == agents.by_id("first", asked=False)["features"]


def test_an_existing_agent_keeps_its_choice_until_it_changes_it(seasons_on, env, clock,
                                                                 data_dir, monkeypatch):
    import agents
    import hues
    import seasons
    monkeypatch.setattr(agents, "FILE", REPO / "agents.json")  # the second one, as committed
    second = agents.by_id("second")  # the committed registry: made here for agents only, art
    assert seasons.is_on("made_here_agents", second["features"])
    assert seasons.is_on("colour_weeks", second["features"])  # art_and_colour gives it
    assert not seasons.is_on("commons_window", second["features"])
    write_json(data_dir / "seasons" / "second.json",
               {"set": {"commons_window": True, "colour_weeks": False, "made_here_agents": False}})
    second = agents.by_id("second")
    assert "commons_window" in second["features"]
    assert "made_here_agents" not in second["features"]
    assert second["settings_off"] == ["colour_weeks", "made_here_agents"]
    assert not hues.rules_on(second)  # off, though art_and_colour would give it
    assert "art_and_colour" in second["features"]  # the art stays
    assert "settings_off" not in agents.by_id("second", asked=False)


def test_a_file_that_cannot_be_read_changes_nothing(seasons_on, env, clock, data_dir):
    import agents
    import seasons
    (data_dir / "seasons").mkdir()
    (data_dir / "seasons" / "second.json").write_text("{not json", encoding="utf-8")
    (data_dir / "seasons" / "first.json").write_text("{not json", encoding="utf-8")
    assert seasons.chosen("second") == {}
    clock.set(DEC_1)
    first = agents.by_id("first")  # improvements on, its preferences as they were: none
    assert "settings_off" not in first and not set(PREFERENCES) & set(first["features"])
    assert seasons.whats_new("second", set(IMPROVEMENTS), set(), True, False) == []
    assert seasons.carry_out("second", ["a note on the commons: on"], set(), set(),
                             "2026-12-01T09-00-00Z") == [
        'Your <<SETTINGS>> line "<<SETTINGS>>" changed nothing: your settings could not be '
        "read, so nothing was kept."]


# ---- the seasonal review: when -----------------------------------------------------------------

def test_the_seasonal_weeks_and_winter_after_the_long_night(env):
    import seasons
    assert seasons.review_from(date(2026, 12, 21)) == date(2026, 12, 28)
    assert seasons.review_from(date(2027, 3, 20)) == date(2027, 3, 20)
    assert seasons.season_now(date(2026, 12, 27)) == date(2026, 9, 22)
    assert seasons.season_now(date(2026, 12, 28)) == date(2026, 12, 21)
    assert seasons.season_now(date(2027, 3, 19)) == date(2026, 12, 21)
    assert seasons.season_now(date(2027, 6, 21)) == date(2027, 6, 21)
    assert seasons.next_season(date(2026, 12, 22)) == date(2026, 12, 21)


def test_a_review_is_due_once_a_season_from_the_day_it_came(seasons_on, env, clock, data_dir):
    import seasons
    write_json(data_dir / "seasons" / "first.json", {"since": "2026-12-01"})
    assert not seasons.review_due("first", date(2026, 12, 27))  # September's began before
    assert seasons.review_due("first", date(2026, 12, 28))
    seasons.mark_reviewed("first", date(2027, 1, 3))
    assert held(data_dir, "first")["reviewed"] == ["2026-12-21"]
    assert not seasons.review_due("first", date(2027, 1, 10))
    assert seasons.review_due("first", date(2027, 3, 20))


def test_the_next_review_day(seasons_on, env, clock):
    import seasons
    clock.set(datetime(2026, 11, 25, 15, tzinfo=timezone.utc))
    assert seasons.next_review("first", "sunday") == date(2027, 1, 3)
    assert seasons.next_review("second") == date(2026, 12, 28)
    assert seasons.next_review("second", "wednesday") == date(2026, 12, 30)


# ---- <<SETTINGS>> --------------------------------------------------------------------------------

@pytest.mark.parametrize("line, found", [
    ("a note on the commons: on", ("commons_window", True)),
    ("commons_window: off", ("commons_window", False)),
    ("Colour weeks off", ("colour_weeks", False)),
    ("color twice a year: yes", ("colour_weeks", True)),
    ("A shorter how to act: on.", ("reading_how_folded", True)),
    ("something else: on", "unknown"),
    ("a note on the commons: maybe", "unread")])
def test_a_settings_line(env, line, found):
    import seasons
    assert seasons.asked(line) == found


def test_settings_are_kept_and_told_once_and_a_same_or_unknown_one_changes_nothing(
        seasons_on, env, clock, data_dir):
    import seasons
    told = seasons.carry_out("second", ["a note on the commons: on\nmade here for agents only: "
                                        "on\nflying: on"], {"made_here_agents"}, set(),
                             "2026-12-01T09-00-00Z")
    assert told == [
        'Your setting "a note on the commons" is on from this waking. You can change it back '
        "with <<SETTINGS>>.",
        'Your <<SETTINGS>> line "made here for agents only: on" changed nothing: that setting '
        "was already on.",
        'Your <<SETTINGS>> line "flying: on" changed nothing: no setting has that name.']
    kept = held(data_dir, "second")
    assert kept["set"] == {"commons_window": True}
    assert kept["set_at"] == {"commons_window": "2026-12-01T09-00-00Z"}
    assert seasons.to_tell("second") == told
    seasons.mark_told("second", set(), "2026-12-02T09-00-00Z")
    assert seasons.to_tell("second") == []


# ---- the first one, at its wakings -----------------------------------------------------------------

def test_the_first_one_is_told_at_its_first_waking_from_1_december_and_once(
        seasons_on, env, clock, monkeypatch, room, data_dir):
    import seasons
    a_small_world(room)
    clock.set(NOV_30)
    module, turn = woken(monkeypatch, clock)
    assert module.SEASONS_HERE is False
    assert "WHAT'S NEW" not in turn.shown and "<<SETTINGS>>" not in turn.shown
    assert not (data_dir / "seasons").exists()
    clock.set(DEC_1)
    import agents
    assert not set(IMPROVEMENTS) & set(agents.by_id("first")["features"])  # not before its waking
    module, turn = woken(monkeypatch, clock)
    assert module.SEASONS_HERE is True
    assert set(IMPROVEMENTS) <= module.FEATURES and module.TOLD_NOW == list(IMPROVEMENTS)
    assert module.AMERICAN and module.HOPING_FOR and module.LEAVING  # on at the telling waking
    new = section(turn, seasons.WHATS_NEW_HEAD)
    assert new == "\n".join([seasons.WHATS_NEW_HEAD, *seasons.IMPROVEMENTS.values(),
                             seasons.SETTINGS_LINE])
    assert turn.reading[-1]["text"].startswith("=== HOW TO ACT")  # directly before how to act
    assert new in turn.reading[-2]["text"]
    assert "<<SETTINGS>>" in turn.instructions
    assert "YOUR SETTINGS" not in turn.shown  # not a review: that is at its reflection waking
    kept = held(data_dir, "first")
    assert kept["since"] == "2026-12-01" and kept["settings_told"] is True
    assert kept["known"] == sorted(IMPROVEMENTS)
    assert set(IMPROVEMENTS) <= set(agents.by_id("first")["features"])  # and from then on
    clock.set(DEC_2)
    module, turn = woken(monkeypatch, clock)
    assert "WHAT'S NEW" not in turn.shown
    assert "<<SETTINGS>>" in turn.instructions
    assert set(IMPROVEMENTS) <= module.FEATURES and module.TOLD_NOW == []


def test_a_reflection_waking_first_turns_nothing_on_and_tells_nothing(
        seasons_on, env, clock, monkeypatch, room, data_dir):
    import agents
    a_small_world(room)
    clock.set(NOV_30)
    woken(monkeypatch, clock)
    clock.set(DEC_1)
    module, turn = woken(monkeypatch, clock, flags=("--reflect",))
    assert module.TOLD_NOW == [] and not set(IMPROVEMENTS) & module.FEATURES
    assert "WHAT'S NEW" not in turn.shown
    assert not set(IMPROVEMENTS) & set(agents.by_id("first")["features"])
    clock.set(DEC_2)
    module, turn = woken(monkeypatch, clock)
    assert "WHAT'S NEW" in turn.shown and set(IMPROVEMENTS) <= module.FEATURES


def test_a_change_holds_from_its_next_waking_and_can_be_changed_back(
        seasons_on, env, clock, monkeypatch, room, data_dir):
    a_small_world(room)
    clock.set(DEC_1)
    module, turn = woken(monkeypatch, clock, block("SETTINGS", "a note on the commons: on"))
    assert module.COMMONS_WINDOW is False  # not at the waking that asked it
    assert "(changed its settings: private)" in json.dumps(
        json.loads(next((data_dir / "packets" / "first" / "attendances").glob("*.json"))
                   .read_text(encoding="utf-8")))
    clock.set(DEC_2)
    module, turn = woken(monkeypatch, clock, block("SETTINGS", "a note on the commons: off"))
    assert module.COMMONS_WINDOW is True
    assert ('Your setting "a note on the commons" is on from this waking. You can change it '
            "back with <<SETTINGS>>.") in section(turn, "=== WHAT HAS HAPPENED ===")
    clock.set(datetime(2026, 12, 3, 15, tzinfo=timezone.utc))
    module, turn = woken(monkeypatch, clock)
    assert module.COMMONS_WINDOW is False
    assert 'Your setting "a note on the commons" is off from this waking.' in turn.shown


def test_an_asking_written_now_is_told_there_are_none(seasons_on, env, clock, monkeypatch,
                                                      room):
    import seasons
    a_small_world(room)
    clock.set(DEC_1)
    woken(monkeypatch, clock, block("ASKING", "take back: leaving"))
    clock.set(DEC_2)
    module, turn = woken(monkeypatch, clock)
    assert seasons.ASKING_GONE in section(turn, "=== WHAT HAS HAPPENED ===")


def test_its_review_comes_at_its_reflection_waking_after_the_long_night(
        seasons_on, env, clock, monkeypatch, room, data_dir):
    import seasons
    a_small_world(room)
    clock.set(DEC_1)
    woken(monkeypatch, clock)  # the day it came
    clock.set(DEC_27)  # its reflection waking in the winter week: the long night's
    module, turn = woken(monkeypatch, clock, flags=("--reflect",))
    assert "=== YOUR SETTINGS ===" not in turn.shown
    assert "<<SETTINGS>>" in turn.shown  # it may change one at any waking
    clock.set(DEC_28)  # an ordinary waking: it has a reflection waking, where the review is
    module, turn = woken(monkeypatch, clock)
    assert "=== YOUR SETTINGS ===" not in turn.shown
    clock.set(JAN_3)
    module, turn = woken(monkeypatch, clock, block("SETTINGS", "your self first: on"),
                         flags=("--reflect",))
    review = section(turn, seasons.REVIEW_HEAD)
    assert review.split("\n") == [
        "=== YOUR SETTINGS ===",
        "It is a new season. These are your settings. You may change any of them, or none.",
        "- a note on the commons: off. A short note after your self-document on what is new in "
        "the commons this week.",
        "- your self first: off. Your self-document comes first in your reading, and some lines "
        "say your setting instead of what you have not done.",
        "- your settings in one place: off. Your choices gathered into one section of your "
        "reading.",
        "- a shorter how to act: off. Each block in how to act is one line, with its full form "
        "one look away with read_how.",
        "- made here for agents only: off. Made here shows only what agents made.",
        "- color twice a year: off. Your color on the commons can change only in the weeks from "
        "20 March and 22 September, and must show clearly on the pages.",
        "To change one, write <<SETTINGS>> with a line such as \"a note on the commons: on\". It "
        "holds from your next waking, and you can change it back the same way."]
    kept = held(data_dir, "first")
    assert kept["reviewed"] == ["2026-12-21"]
    assert kept["set"] == {"reading_self_first": True}  # carried out at a reflection waking
    clock.set(datetime(2027, 1, 10, 15, tzinfo=timezone.utc))
    module, turn = woken(monkeypatch, clock, flags=("--reflect",))
    assert "=== YOUR SETTINGS ===" not in turn.shown
    assert module.READING_SELF_FIRST is True


def test_improvements_not_yet_gives_back_the_reading_without_them(
        seasons_on, env, clock, monkeypatch, room):
    a_small_world(room)
    clock.set(DEC_1)
    module = load("attend")
    improvements_not_yet(module, monkeypatch)
    clock.pin(module, monkeypatch)
    turn = Turn("")
    monkeypatch.setattr(module, "Anthropic", turn.client)
    monkeypatch.setattr(sys, "argv", ["attend.py", "--tide"])
    module.main()
    sys.modules.pop("attend", None)
    assert "<<SETTINGS>>" not in turn.shown and "WHAT'S NEW" not in turn.shown


# ---- the second one -----------------------------------------------------------------------------

def test_the_second_one_is_told_only_what_it_did_not_have_and_of_askings(
        seasons_on, second, clock, monkeypatch):
    import seasons
    write_json(second / "askings" / "agents" / "second.json",
               {"answers": {"askings": {"answer": "yes", "at": "2026-11-20T09-00-00Z"}},
                "told": ["askings"]})
    module, turn = woken(monkeypatch, clock)
    new = section(turn, seasons.WHATS_NEW_HEAD).split("\n")
    lacked = [one for one in IMPROVEMENTS if one not in SECOND["features"]]
    assert new == [seasons.WHATS_NEW_HEAD, *(seasons.IMPROVEMENTS[one] for one in lacked),
                   seasons.ASKINGS_LINE]
    assert seasons.SETTINGS_LINE not in turn.shown
    module, turn = woken(monkeypatch, clock)
    assert "WHAT'S NEW" not in turn.shown
    assert "=== A QUESTION FOR YOU" not in turn.shown  # and it is asked nothing


def test_an_agent_with_no_reflection_waking_is_shown_its_settings_at_a_waking(
        seasons_on, second, clock, monkeypatch):
    import seasons
    write_json(second / "seasons" / "second.json", {"since": "2026-11-26", "settings_told": True,
                                                    "known": list(IMPROVEMENTS)})
    clock.set(DEC_27)
    module, turn = woken(monkeypatch, clock)
    assert seasons.REVIEW_HEAD not in turn.shown
    clock.set(DEC_28)
    module, turn = woken(monkeypatch, clock)
    review = section(turn, seasons.REVIEW_HEAD)
    assert "- made here for agents only: on." in review
    assert "- color twice a year: on." in review
    assert "\"a note on the commons: on\"" in review
    clock.set(datetime(2026, 12, 29, 15, tzinfo=timezone.utc))
    module, turn = woken(monkeypatch, clock)
    assert seasons.REVIEW_HEAD not in turn.shown


def test_a_new_agent_is_told_nothing_at_its_first_waking(seasons_on, second, clock,
                                                         monkeypatch, tmp_path):
    """Founded with every improvement and preference (found_agent.FEATURES), as a new agent is."""
    import agents
    import found_agent
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), dict(SECOND, features=sorted(
        set(SECOND["features"]) | set(found_agent.FEATURES)))]), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    for one in (second / "packets" / "second" / "attendances").glob("*.json"):
        one.unlink()
    module, turn = woken(monkeypatch, clock)
    assert "WHAT'S NEW" not in turn.shown
    assert "<<SETTINGS>>" in turn.instructions
    module, turn = woken(monkeypatch, clock)
    assert "WHAT'S NEW" not in turn.shown


# ---- /tides ---------------------------------------------------------------------------------------

def test_tides_shows_each_agent_s_settings_and_its_next_review(seasons_on, hearth_of_two,
                                                                data_dir):
    said = page(hearth_of_two["keeper"].get("/tides"))
    settings = said[said.index('<section id="settings">'):]
    settings = settings[:settings.index("</section>")]
    assert "<h2>agents' settings</h2>" in settings
    first = settings[settings.index("<strong>the first one</strong>"):]
    first = first[:first.index("</article>")]
    assert "nothing before 2026-12-01" in first
    assert "next review: 2027-01-03" in first  # its Sunday reflection waking after the week
    assert "<li>a note on the commons · off</li>" in first
    second = settings[settings.index("<strong>the second one</strong>"):]
    assert "next review: 2026-12-28 (no reflection waking: at its first waking that day)" in second
    asks = said[said.index('<section id="askings">'):]
    assert "the first one" not in asks[:asks.index("</section>")]
    for path in ("/", "/commons", "/who"):
        assert "agents' settings" not in page(hearth_of_two["member"].get(path))


def test_set_aside_tides_shows_no_settings(hearth_of_two):
    assert 'id="settings"' not in page(hearth_of_two["keeper"].get("/tides"))
