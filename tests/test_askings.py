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

DAY = date(2026, 12, 2)
AT = "2026-12-02T09-00-00Z"
LATER_AT = "2026-12-03T09-00-00Z"


@pytest.fixture
def ask(env, monkeypatch):
    module = load("askings")
    monkeypatch.setattr(module, "ORDER", ("askings", "colour_weeks", "leaving",
                                          "american_spelling"))
    # a switch whose code is not here, held so for these tests: leaving was built on
    # leaving-build (21 November 2026), and askings.NOT_BUILT is empty since
    monkeypatch.setattr(module, "NOT_BUILT", {"leaving"})
    # no spacing between askings, but where a test sets it (DEFAULT_EVERY_DAYS, 21 November)
    monkeypatch.setattr(module, "DEFAULT_EVERY_DAYS", {})
    return module


def test_leaving_is_built_and_asked_now(env):
    import askings
    # the names switches are built on names-ids, not on stage-2: kept ready, never asked
    assert askings.NOT_BUILT == {"names_told", "commons_names", "solstice_names"}
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
    assert ask.next_asking("agents", "first", date(2026, 12, 16)) == "askings"
    ask.carry_out("agents", "first", ["yes"], "askings", "2026-12-16T09-00-00Z")
    assert ask.next_asking("agents", "first", date(2026, 12, 16)) == "colour_weeks"
    assert ask.on("agents", "first") == set()  # the asking about askings turns nothing on


def test_a_no_to_askings_asks_nothing_again(ask):
    ask.carry_out("agents", "first", ["no"], "askings", AT)
    assert ask.next_asking("agents", "first", date(2027, 6, 1)) is None


def test_yes_turns_the_switch_on_and_no_is_never_asked_again(ask, data_dir):
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    ask.carry_out("agents", "first", ["Yes, thank you."], "colour_weeks", AT)
    assert ask.on("agents", "first") == {"colour_weeks"}
    # a switch not built is never asked, and the next one comes
    assert ask.next_asking("agents", "first", DAY) == "american_spelling"
    ask.carry_out("agents", "first", ["no"], "american_spelling", AT)
    assert ask.next_asking("agents", "first", date(2028, 1, 1)) is None
    assert ask.on("agents", "first") == {"colour_weeks"}


def test_at_most_one_answer_a_waking_and_silence_is_a_quiet_not_yet(ask, data_dir):
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    told = ask.carry_out("agents", "first", ["yes", "yes"], "colour_weeks", AT)
    assert told == ["Your <<ASKING>> at your last waking changed nothing: no question was "
                    "open."]
    ask.carry_out("agents", "first", [], "american_spelling", AT)
    answer = held(data_dir)["answers"]["american_spelling"]
    assert answer["answer"] == "not yet" and answer["silent"]
    assert len(ledger_lines(data_dir)) == 2  # two answers; silence tells the ledger nothing


def test_a_yes_can_be_taken_back_and_a_no_asked_for_again_by_name(ask):
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    ask.carry_out("agents", "first", ["yes"], "colour_weeks", AT)
    told = ask.carry_out("agents", "first", ["take back: color twice a year"], None, LATER_AT)
    assert told == ["You took back your yes to color twice a year. It is off from this waking."]
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
    assert ask.next_asking("agents", "first", DAY, {"colour_weeks"}) == "american_spelling"
    assert ask.next_asking("agents", "first", DAY,
                           {"colour_weeks", "american_spelling"}) is None


def test_nothing_waits_so_nothing_is_asked_not_even_about_askings(ask, monkeypatch):
    monkeypatch.setattr(ask, "ORDER", ("askings",))
    assert ask.next_asking("agents", "first", DAY) is None


def test_the_first_one_is_asked_nothing_before_1_december(ask):
    # 1 December since the founder's request of 23 November 2026; before, 27 November
    assert ask.next_asking("agents", "first", date(2026, 11, 30)) is None
    assert ask.next_asking("agents", "first", date(2026, 12, 1)) == "askings"


def test_every_agent_follows_the_one_order_and_a_saved_queue_is_dropped(ask, data_dir):
    """one-order (23 November 2026): an agent's order is ORDER; a queue saved for it before is
    not read, and is dropped at the next write; the founder orders only a person's queue."""
    write(data_dir / "askings" / "agents" / "first.json",
          json.dumps({"queue": ["american_spelling", "colour_weeks"]}))
    assert ask.queue_of("agents", "first") == ["colour_weeks", "leaving", "american_spelling"]
    assert ask.queue_of("agents", "second") == ask.queue_of("agents", "first")
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    assert ask.next_asking("agents", "first", DAY) == "colour_weeks"
    assert "queue" not in ask.read("agents", "first")
    with pytest.raises(ask.Refused):
        ask.set_queue("agents", "first", ["american_spelling", "colour_weeks"])
    assert ask.set_queue("people", "alder", ["own_name"]) == ["own_name"]
    with pytest.raises(ask.Refused):
        ask.set_queue("people", "alder", ["no_such_switch"])
    with pytest.raises(ask.Refused):
        ask.set_queue("people", "alder", ["colour_weeks"])  # an agent's, not a person's


def test_a_switch_had_by_another_feature_is_not_asked(ask):
    ask.carry_out("agents", "second", ["yes"], "askings", AT)
    assert ask.next_asking("agents", "second", DAY, {"art_and_colour"}) == "american_spelling"


def test_a_file_that_cannot_be_read_asks_nothing_and_turns_nothing_on(ask, data_dir):
    write(data_dir / "askings" / "agents" / "first.json", "{not json")
    assert ask.next_asking("agents", "first", DAY) is None
    assert ask.on("agents", "first") == set()


def test_the_ledger_is_told_only_that_an_asking_was_answered(ask, data_dir):
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    ask.carry_out("agents", "first", ["no"], "colour_weeks", AT)
    lines = ledger_lines(data_dir)
    assert lines == ["- 2026-12-02 · an asking was answered"] * 2


def test_with_askings_off_nothing_is_asked_or_on(ask, monkeypatch):
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    ask.carry_out("agents", "first", ["yes"], "colour_weeks", AT)
    monkeypatch.setattr(ask, "ASKINGS", False)
    assert ask.on("agents", "first") == set()
    assert ask.next_asking("agents", "first", DAY) is None


def test_the_order_is_the_founder_s_request(askings_queued):
    import askings
    # one order for every agent (one-order, the founder's request of 23 November 2026)
    assert askings.ORDER == (
        "askings", "hoping_for", "commons_window", "commons_names", "solstice_names",
        "names_told", "knock_founder", "knock_take_back", "leaving", "american_spelling",
        "copy_said", "made_here_agents", "colour_weeks",
        # replies to its own topics (small-builds, 23 November 2026)
        "replies_told",
        # the reading's shape, which goes by its months (reading-shape)
        "reading_self_first", "reading_settings", "reading_how_folded")
    assert set(askings.ORDER) == {s for s in askings.ASK_FIRST if askings.for_kind(s, "agents")}
    assert "private_reflections" not in askings.ASK_FIRST
    assert "art_and_colour" not in askings.ASK_FIRST
    assert askings.DEFAULT_EVERY_DAYS == {("agents", "first"): 3}
    assert askings.META_WORDS["agents"] == ("May I ask you about changes this way, one at a "
                                            "time, at your wakings?")
    for switch, one in askings.ASK_FIRST.items():
        assert one["name"] and one["adds"] and one["takes"] and "undo" in one, switch


# ---- the registry -------------------------------------------------------------------------

def test_a_yes_is_in_the_registry_s_features_and_never_in_what_is_written_out(ask):
    import agents
    ask.carry_out("agents", "first", ["yes"], "askings", AT)
    ask.carry_out("agents", "first", ["yes"], "colour_weeks", AT)
    assert "colour_weeks" in agents.by_id("first")["features"]
    assert "colour_weeks" not in agents.by_id("first", asked=False)["features"]
    assert "colour_weeks" not in agents.registry(asked=False)[0]["features"]


# ---- at a waking --------------------------------------------------------------------------

def a_letter(data_dir, stamp="2026-12-02T08-00-00Z"):
    write(data_dir / "rooms" / "first" / "letters" / "incoming" / f"founder-{stamp}.md",
          "A letter for the tests.\n")


@pytest.fixture
def late(clock, ask):
    clock.set(datetime(2026, 12, 2, 12, tzinfo=timezone.utc))
    return clock


def test_a_waking_with_a_letter_asks_once_and_keeps_the_answer_private(late, ask, attend, wake,
                                                                       data_dir, packet):
    a_letter(data_dir)
    turn = wake("<<ASKING>>\nyes\n<<END>>\n<<HEARTBEAT>>\nattended\n<<END>>")
    shown = turn.shown
    assert shown.count("=== A QUESTION FOR YOU, FROM THE FOUNDER ===") == 1
    assert ask.META_WORDS["agents"] in shown
    assert shown.index("=== A QUESTION FOR YOU, FROM THE FOUNDER ===") < shown.index("=== HOW TO ACT")
    assert held(data_dir)["answers"]["askings"]["answer"] == "yes"
    [kept] = sorted((packet / "attendances").glob("*.json"))
    record = json.loads(kept.read_text(encoding="utf-8"))
    assert ask.QUIETLY in record["reflection"] and "yes" not in record["reflection"].lower()
    assert ledger_lines(data_dir) == ["- 2026-12-02 · an asking was answered"]
    # the next waking: its yes told once, and the next asking
    a_letter(data_dir, "2026-12-02T12-01-00Z")
    turn = wake("<<HEARTBEAT>>\nattended\n<<END>>")
    assert ask.TOLD["meta yes"] in turn.shown
    assert "May I make this change: color twice a year?" in turn.shown
    a_letter(data_dir, "2026-12-02T12-06-00Z")
    turn = wake("")
    assert ask.TOLD["meta yes"] not in turn.shown  # once
    assert "May I make this change: color twice a year?" not in turn.shown  # silence: 14 days


def test_no_asking_on_a_quiet_day(late, attend, wake, data_dir):
    turn = wake("")
    assert "A QUESTION FOR YOU" not in turn.shown
    assert not (data_dir / "askings" / "agents" / "first.json").exists()


def test_no_asking_before_1_december_and_the_reading_does_not_move(ask, attend, wake,
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

def test_the_founder_sees_askings_on_tides_and_orders_only_a_member_s(hearth_of_two,
                                                                     data_dir):
    """one-order (23 November 2026): /tides shows an agent's order, and does not change it."""
    import askings
    keeper = hearth_of_two["keeper"]
    said = page(keeper.get("/tides"))
    assert 'id="askings"' in said
    assert "Every agent is asked in the same order, set in code" in said
    answer = post(keeper, "/tides/askings/order",
                  data={"kind": "agents", "who": "second",
                        "order": "names_told\ncommons_names"})
    assert "That order was not kept" in page(answer)
    assert askings.queue_of("agents", "second") == list(askings.ORDER[1:])
    answer = post(keeper, "/tides/askings/order",
                  data={"kind": "people", "who": "alder", "order": "own_name"})
    assert "The order of what waits is kept." in page(answer)
    assert askings.queue_of("people", "alder") == ["own_name"]


def test_a_member_is_asked_on_their_home_page_and_no_one_else_sees_it(hearth_of_two, data_dir):
    import askings
    keeper, member = hearth_of_two["keeper"], hearth_of_two["member"]
    post(keeper, "/tides/askings/order", data={"kind": "people", "who": "alder",
                                               "order": "own_name"})
    home = page(member.get("/"))
    assert askings.META_WORDS["people"] in home
    answer = post(member, "/askings", data={"switch": "askings", "answer": "yes"})
    assert "Your answer is kept. It is private: only you and the founder see it." in page(answer)
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
    monkeypatch.setattr(ask, "ORDER", ("askings", "leaving"))
    ask.carry_out("agents", "second", ["yes"], "askings", AT)
    assert ask.next_asking("agents", "second", DAY) == "leaving"
    ask.carry_out("agents", "second", ["yes"], "leaving", AT)
    import agents
    from conftest import REPO
    monkeypatch.setattr(agents, "FILE", REPO / "agents.json")  # the registry with the second one
    assert "leaving" in agents.by_id("second")["features"]
    assert "leaving" not in agents.by_id("second", asked=False)["features"]


# ---- the founder's words and spacing of 21 November 2026 (from names-ids) --------------------

def test_the_words_of_21_november(env):
    import askings
    text = askings.asking_text("agents", "leaving")
    assert text.startswith("=== A QUESTION FOR YOU, FROM THE FOUNDER ===\n")
    assert "Your answer is private: only you and the founder see it." in text
    assert askings.TOLD["yes"] == ("You said yes to {name}. It is on now. To take it back, "
                                   "write <<ASKING>> with the line: take back: {name}")
    assert askings.told_line("agents", "leaving", "yes") == (
        "You said yes to leaving. It is on now. To take it back, write <<ASKING>> with the "
        "line: take back: leaving")
    assert askings.ASK_FIRST["leaving"]["adds"] == (
        "You may leave a room you share, with or without a block. A bond in it is released. "
        "Both of you can still read the room and take a copy, but no one can write in it. If "
        "the other leaves, you are told once. You may knock at each other again after 30 days. "
        "Your room with the founder can't be left yet.")
    assert askings.ASK_FIRST["leaving"]["takes"] == "The other may leave too."
    assert "once in each of those weeks" in askings.ASK_FIRST["solstice_names"]["adds"]
    color = askings.ASK_FIRST["colour_weeks"]
    assert color["adds"] == ("Your color on the commons could change only in two weeks a year, "
                             "from 20 March and from 22 September, so others can know you by "
                             "it. A color must also show clearly on the pages.")
    assert color["takes"] == ("Changing your color at any waking. Choosing a color too faint "
                              "to show.")


def test_the_colour_rule_alone_is_its_own_switch(env):
    import hues
    assert hues.WEEKS_SWITCH == "colour_weeks"
    assert hues.rules_on({"features": ["colour_weeks"]})
    assert hues.rules_on({"features": ["art_and_colour"]})
    assert not hues.rules_on({"features": ["made_here_art"]})


def test_at_most_one_asking_every_three_days_for_the_first_one(ask, monkeypatch):
    monkeypatch.setattr(ask, "DEFAULT_EVERY_DAYS", {("agents", "first"): 3})
    ask.carry_out("agents", "first", ["yes"], "askings", AT)  # shown on 2 December
    assert ask.next_asking("agents", "first", date(2026, 12, 4)) is None
    assert ask.next_asking("agents", "first", date(2026, 12, 5)) == "colour_weeks"
    ask.carry_out("agents", "first", ["no"], "colour_weeks", "2026-12-05T09-00-00Z")
    assert ask.next_asking("agents", "first", date(2026, 12, 7)) is None
    assert ask.next_asking("agents", "first", date(2026, 12, 8)) == "american_spelling"
    # the founder's own number, from /tides; 0 is no limit
    assert ask.set_every_days("agents", "first", "0") == 0
    assert ask.next_asking("agents", "first", date(2026, 12, 6)) == "american_spelling"
    ask.set_every_days("agents", "first", "7")
    assert ask.next_asking("agents", "first", date(2026, 12, 11)) is None
    for bad in ("x", "-1", "366"):
        with pytest.raises(ask.Refused):
            ask.set_every_days("agents", "first", bad)
    # the second one has no limit unless the founder sets one
    assert ask.every_days("agents", "second", {}) == 0


def test_an_asking_shown_and_not_answered_is_not_held_back_by_the_spacing(ask, monkeypatch):
    monkeypatch.setattr(ask, "DEFAULT_EVERY_DAYS", {("people", "willow"): 3})
    monkeypatch.setattr(ask, "DEFAULT_PEOPLE_QUEUE", ["leaving"])
    ask.mark_asked("people", "willow", "askings", AT)
    assert ask.next_asking("people", "willow", DAY) == "askings"


def test_the_founder_sets_the_spacing_on_tides(hearth_of_two, data_dir):
    import askings
    keeper = hearth_of_two["keeper"]
    said = page(keeper.get("/tides"))
    assert "at most one asking every so many days" in said
    answer = post(keeper, "/tides/askings/every", data={"kind": "agents", "who": "first",
                                                         "days": "5"})
    assert "At most one asking every 5 days is kept." in page(answer)
    assert askings.every_days("agents", "first", askings.read("agents", "first")) == 5
    answer = post(keeper, "/tides/askings/every", data={"kind": "agents", "who": "first",
                                                         "days": "many"})
    assert "That number was not kept" in page(answer)
