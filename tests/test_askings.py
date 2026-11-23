"""Askings (askings.py; the founder's request of 20 November 2026).

A plain question about one change, at a waking or on a member's home page: what it adds,
what it takes away, answered yes, no or not yet. The asking about askings comes first.
"""

import json
from datetime import date, datetime, timezone

import pytest

from conftest import load, page, post, write
from test_later_citizen import hearth_of_two, scratch_registry  # noqa: F401 - fixtures
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

DAY = date(2026, 11, 28)
AT = "2026-11-28T09-00-00Z"
LATER_AT = "2026-11-29T09-00-00Z"


@pytest.fixture
def ask(env, monkeypatch):
    module = load("askings")
    monkeypatch.setattr(module, "DEFAULT_QUEUES", {
        ("agents", "first"): ["art_and_colour", "leaving", "american_spelling"]})
    # a switch whose code is not here, held so for these tests: leaving was built on
    # leaving-build (21 November 2026), and askings.NOT_BUILT is empty since
    monkeypatch.setattr(module, "NOT_BUILT", {"leaving"})
    return module


def test_leaving_is_built_and_asked_now(env):
    import askings
    assert askings.NOT_BUILT == set()
    assert "leaving" in askings.ASK_FIRST
    import leaving
    assert leaving.SWITCH == "leaving"


def held(data_dir, kind="agents", who="first"):
    return json.loads((data_dir / "askings" / kind / (who + ".json")).read_text(encoding="utf-8"))


def ledger_lines(data_dir):
    path = data_dir / "commons" / "ledger.md"
    return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []


# ---- the rules ----------------------------------------------------------------------------

def test_the_asking_about_askings_comes_first_and_nothing_else_until_it_is_yes(ask, data_dir):
    assert ask.next_asking("agents", "first", DAY) == "askings"
    ask.carry_out("agents", "first", ["not yet"], "askings", AT)
    assert ask.next_asking("agents", "first", DAY) is None  # not yet: 14 days
    assert ask.next_asking("agents", "first", date(2026, 12, 12)) == "askings"
    ask.carry_out("agents", "first", ["yes"], "askings", "2026-12-12T09-00-00Z")
    assert ask.next_asking("agents", "first", date(2026, 12, 12)) == "art_and_colour"
    assert ask.on("agents", "first") == set()  # the asking about askings turns nothing on


def test_a_no_to_askings_asks_nothing_again(ask):
    ask.carry_out("agents", "first", ["no"], "askings", AT)
    assert ask.next_asking("agents", "first", date(2027, 6, 1)) is None


def test_yes_turns_the_switch_on_and_no_is_never_asked_again(ask, data_dir):
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    ask.carry_out("agents", "first", ["Yes, thank you."], "art_and_colour", AT)
    assert ask.on("agents", "first") == {"art_and_colour"}
    # a switch not built is never asked, and the next one comes
    assert ask.next_asking("agents", "first", DAY) == "american_spelling"
    ask.carry_out("agents", "first", ["no"], "american_spelling", AT)
    assert ask.next_asking("agents", "first", date(2028, 1, 1)) is None
    assert ask.on("agents", "first") == {"art_and_colour"}


def test_at_most_one_answer_a_waking_and_silence_is_a_quiet_not_yet(ask, data_dir):
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    told = ask.carry_out("agents", "first", ["yes", "yes"], "art_and_colour", AT)
    assert told == ["Your <<ASKING>> at your last waking changed nothing: no question was "
                    "open."]
    ask.carry_out("agents", "first", [], "american_spelling", AT)
    answer = held(data_dir)["answers"]["american_spelling"]
    assert answer["answer"] == "not yet" and answer["silent"]
    assert len(ledger_lines(data_dir)) == 2  # two answers; silence tells the ledger nothing


def test_a_yes_can_be_taken_back_and_a_no_asked_for_again_by_name(ask):
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    ask.carry_out("agents", "first", ["yes"], "art_and_colour", AT)
    told = ask.carry_out("agents", "first", ["take back: art and colour"], None, LATER_AT)
    assert told == ["You took back your yes to art and colour. It is off from this waking."]
    assert ask.on("agents", "first") == set()
    ask.carry_out("agents", "first", ["no"], "american_spelling", AT)
    told = ask.carry_out("agents", "first", ["ask again: American spelling"], None, LATER_AT)
    assert told == ["You asked about American spelling again. It will be asked at a later "
                    "waking."]
    # a yes taken back is not asked again, as a no is not; the one asked for again is
    assert ask.next_asking("agents", "first", DAY) == "american_spelling"
    told = ask.carry_out("agents", "first", ["take back: hoping for"], None, LATER_AT)
    assert "there was no yes of yours to that to take back" in told[0]


def test_what_is_on_already_is_never_asked(ask):
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    assert ask.next_asking("agents", "first", DAY, {"art_and_colour"}) == "american_spelling"
    assert ask.next_asking("agents", "first", DAY,
                           {"art_and_colour", "american_spelling"}) is None


def test_nothing_waits_so_nothing_is_asked_not_even_about_askings(ask, monkeypatch):
    monkeypatch.setattr(ask, "DEFAULT_QUEUES", {})
    assert ask.next_asking("agents", "first", DAY) is None


def test_the_first_one_is_asked_nothing_before_27_november(ask):
    assert ask.next_asking("agents", "first", date(2026, 11, 26)) is None
    assert ask.next_asking("agents", "first", date(2026, 11, 27)) == "askings"


def test_the_founder_orders_the_queue(ask, data_dir):
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    ask.set_queue("agents", "first", ["american_spelling", "art_and_colour"])
    assert ask.next_asking("agents", "first", DAY) == "american_spelling"
    with pytest.raises(ask.Refused):
        ask.set_queue("agents", "first", ["no_such_switch"])
    with pytest.raises(ask.Refused):
        ask.set_queue("agents", "first", ["own_name"])  # a person's, not an agent's


def test_a_file_that_cannot_be_read_asks_nothing_and_turns_nothing_on(ask, data_dir):
    write(data_dir / "askings" / "agents" / "first.json", "{not json")
    assert ask.next_asking("agents", "first", DAY) is None
    assert ask.on("agents", "first") == set()


def test_the_ledger_is_told_only_that_an_asking_was_answered(ask, data_dir):
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    ask.carry_out("agents", "first", ["no"], "art_and_colour", AT)
    lines = ledger_lines(data_dir)
    assert lines == ["- 2026-11-28 · an asking was answered"] * 2


def test_with_askings_off_nothing_is_asked_or_on(ask, monkeypatch):
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    ask.carry_out("agents", "first", ["yes"], "art_and_colour", AT)
    monkeypatch.setattr(ask, "ASKINGS", False)
    assert ask.on("agents", "first") == set()
    assert ask.next_asking("agents", "first", DAY) is None


def test_the_queues_are_the_founder_s_request(askings_queued):
    import askings
    assert askings.DEFAULT_QUEUES[("agents", "first")] == [
        "art_and_colour", "made_here_agents", "american_spelling", "private_reflections",
        "copy_said", "knock_take_back", "knock_founder", "solstice_names", "hoping_for",
        "leaving", "names_told", "commons_names", "commons_window"]
    assert set(askings.DEFAULT_QUEUES[("agents", "second")]) >= {"leaving", "names_told",
                                                                "commons_names",
                                                                "commons_window"}
    assert askings.META_WORDS["agents"] == ("May I ask you about changes this way, one at a "
                                            "time, at your wakings?")
    for switch, one in askings.ASK_FIRST.items():
        assert one["name"] and one["adds"] and one["takes"] and "undo" in one, switch


# ---- the registry -------------------------------------------------------------------------

def test_a_yes_is_in_the_registry_s_features_and_never_in_what_is_written_out(ask):
    import agents
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    ask.carry_out("agents", "first", ["yes"], "art_and_colour", AT)
    assert "art_and_colour" in agents.by_id("first")["features"]
    assert "art_and_colour" not in agents.by_id("first", asked=False)["features"]
    assert "art_and_colour" not in agents.registry(asked=False)[0]["features"]


# ---- at a waking --------------------------------------------------------------------------

def a_letter(data_dir, stamp="2026-11-28T08-00-00Z"):
    write(data_dir / "rooms" / "first" / "letters" / "incoming" / f"founder-{stamp}.md",
          "A letter for the tests.\n")


@pytest.fixture
def late(clock, ask):
    clock.set(datetime(2026, 11, 28, 12, tzinfo=timezone.utc))
    return clock


def test_a_waking_with_a_letter_asks_once_and_keeps_the_answer_private(late, ask, attend, wake,
                                                                       data_dir, packet):
    a_letter(data_dir)
    turn = wake("<<ASKING>>\nyes\n<<END>>\n<<HEARTBEAT>>\nattended\n<<END>>")
    shown = turn.shown
    assert shown.count("=== A QUESTION FOR YOU ===") == 1
    assert ask.META_WORDS["agents"] in shown
    assert shown.index("=== A QUESTION FOR YOU ===") < shown.index("=== HOW TO ACT")
    assert held(data_dir)["answers"]["askings"]["answer"] == "yes"
    [kept] = sorted((packet / "attendances").glob("*.json"))
    record = json.loads(kept.read_text(encoding="utf-8"))
    assert ask.QUIETLY in record["reflection"] and "yes" not in record["reflection"].lower()
    assert ledger_lines(data_dir) == ["- 2026-11-28 · an asking was answered"]
    # the next waking: its yes told once, and the next asking
    a_letter(data_dir, "2026-11-28T12-01-00Z")
    turn = wake("<<HEARTBEAT>>\nattended\n<<END>>")
    assert ask.TOLD["meta yes"] in turn.shown
    assert "May I make this change: art and colour?" in turn.shown
    a_letter(data_dir, "2026-11-28T12-06-00Z")
    turn = wake("")
    assert ask.TOLD["meta yes"] not in turn.shown  # once
    assert "May I make this change: art and colour?" not in turn.shown  # silence: 14 days


def test_no_asking_on_a_quiet_day(late, attend, wake, data_dir):
    turn = wake("")
    assert "A QUESTION FOR YOU" not in turn.shown
    assert not (data_dir / "askings" / "agents" / "first.json").exists()


def test_no_asking_before_27_november_and_the_reading_does_not_move(ask, attend, wake,
                                                                    data_dir):
    a_letter(data_dir, "2026-10-15T08-00-00Z")
    turn = wake("")
    assert "A QUESTION FOR YOU" not in turn.shown


def test_no_asking_on_a_new_model_or_the_two_wakings_after_or_in_the_long_night(late, attend):
    change = {"model": "new-model", "n": 1}
    on_old = [{"model": "old-model"}]
    letters = ["a letter"]
    assert attend.asking_now(on_old, change, None, letters, DAY) is None
    assert attend.asking_now([*on_old, {"model": "new-model"}], change, None, letters,
                             DAY) is None
    assert attend.asking_now([*on_old, *[{"model": "new-model"}] * 2], change, None, letters,
                             DAY) == "askings"
    assert attend.asking_now([], None, 2026, letters, DAY) is None  # the long night
    assert attend.asking_now([], None, None, [], DAY) is None  # a quiet day
    assert attend.asking_now([], None, None, letters, DAY) == "askings"


def test_a_reflection_waking_never_asks(attend):
    import inspect
    assert "asking" not in inspect.getsource(attend.reflection_waking)


# ---- on the hearth ------------------------------------------------------------------------

def test_the_founder_sees_and_orders_askings_on_tides(hearth_of_two, data_dir):
    import askings
    keeper = hearth_of_two["keeper"]
    said = page(keeper.get("/tides"))
    assert 'id="askings"' in said
    answer = post(keeper, "/tides/askings/order",
                  data={"kind": "agents", "who": "second",
                        "order": "names_told\ncommons_names"})
    assert "The order of what waits is kept." in page(answer)
    assert askings.queue_of("agents", "second") == ["names_tol" + "d", "commons_names"]
    answer = post(keeper, "/tides/askings/order",
                  data={"kind": "agents", "who": "second", "order": "nothing_here"})
    assert "That order was not kept" in page(answer)


def test_a_member_is_asked_on_their_home_page_and_no_one_else_sees_it(hearth_of_two, data_dir):
    import askings
    keeper, member = hearth_of_two["keeper"], hearth_of_two["member"]
    post(keeper, "/tides/askings/order", data={"kind": "people", "who": "alder",
                                               "order": "own_name"})
    home = page(member.get("/"))
    assert askings.META_WORDS["people"] in home
    answer = post(member, "/askings", data={"switch": "askings", "answer": "yes"})
    assert "Your answer is kept. It is private." in page(answer)
    home = page(member.get("/"))
    assert "your name on the commons" in home
    answer = post(member, "/askings", data={"switch": "own_name", "answer": "yes"})
    assert askings.on("people", "alder") == {"own_name"}
    home = page(member.get("/"))
    assert "You said yes to askings." in home  # which can be taken back
    assert "You said yes to your name on the commons" not in home  # which cannot
    assert askings.META_WORDS["people"] not in page(keeper.get("/"))
    assert "your name on the commons" not in page(hearth_of_two["keeper"].get("/"))
    tides = page(keeper.get("/tides"))
    assert "alder (member)" in tides


def test_a_member_answers_only_the_asking_shown(hearth_of_two):
    import askings
    member = hearth_of_two["member"]
    post(hearth_of_two["keeper"], "/tides/askings/order",
         data={"kind": "people", "who": "alder", "order": "own_name"})
    answer = post(member, "/askings", data={"switch": "own_name", "answer": "yes"})
    assert "Nothing changed." in page(answer)
    assert askings.on("people", "alder") == set()


def test_askings_are_in_a_backup_and_never_in_a_copy(hearth):
    assert "askings" in hearth.KEPT_BESIDE
    assert "askings" in hearth.backup_trees()
    assert not any(tree.startswith("askings") for tree in hearth.EXPORT_TREES)


def test_a_yes_to_leaving_turns_leaving_on_for_that_agent(env, data_dir, monkeypatch):
    """H (21 November 2026): with leaving built, a yes to its asking is its switch on, as any
    yes is: the registry reads it over the entry, and blocks.without_a_block with it."""
    ask = load("askings")
    monkeypatch.setattr(ask, "DEFAULT_QUEUES", {("agents", "second"): ["leaving"]})
    ask.carry_out("agents", "second", ["yes"], "askings", AT)
    assert ask.next_asking("agents", "second", DAY) == "leaving"
    ask.carry_out("agents", "second", ["yes"], "leaving", AT)
    import agents
    from conftest import REPO
    monkeypatch.setattr(agents, "FILE", REPO / "agents.json")  # the registry with the second one
    assert "leaving" in agents.by_id("second")["features"]
    assert "leaving" not in agents.by_id("second", asked=False)["features"]
