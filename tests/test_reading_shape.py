"""The reading's shape (the branch reading-shape, the founder's request of 22 November 2026).

Three stages, each behind its own switch, asked first (askings.py, one a month) and off for
every agent founded before them; a new agent is founded with all three:
  A reading_self_first: its self first, absences said as settings, permissions not duties.
  B reading_settings: its choices in one section, YOUR SETTINGS, the commons window after.
  C reading_how_folded: how to act in one line a block, read_how for the rest, and its own
      words last.
With each off, the reading is word for word what it was.
"""

import json
import sys
from datetime import date

import pytest

import agents
from conftest import REPO, Turn, load, write

STAGES = ("reading_self_first", "reading_settings", "reading_how_folded")
ATTENDED = "2026-10-14T09-00-00Z"


def registry_with(monkeypatch, tmp_path, *features):
    """The first one's entry with these switches on besides its own."""
    entries = json.loads((REPO / "agents.json").read_text(encoding="utf-8"))
    entries[0] = dict(entries[0], features=[*entries[0]["features"], *features])
    where = tmp_path / "agents.json"
    where.write_text(json.dumps(entries), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)


def an_earlier_waking(packet, said="<<LETTER>>\nHello.\n<<END>>", heartbeat="attended"):
    write(packet / "attendances" / (ATTENDED + ".json"), json.dumps(
        {"name": "first", "at": ATTENDED, "heartbeat": heartbeat, "acted": [],
         "reflection": said}))


def waking(monkeypatch, *flags):
    module = load("attend")
    turn = Turn("")
    monkeypatch.setattr(module, "Anthropic", turn.client)
    monkeypatch.setattr(sys, "argv", ["attend.py", *flags])
    module.main()
    sys.modules.pop("attend", None)
    return module, turn


@pytest.fixture
def shaped(env, clock, monkeypatch, tmp_path, packet):
    """Wake the first one with some of the stages on: give back (attend, turn)."""
    def wake(*features, flags=("--tide",), before=None):
        registry_with(monkeypatch, tmp_path, *features)
        module = load("attend")
        clock.pin(module, monkeypatch)
        if before:
            before(module)
        turn = Turn("")
        monkeypatch.setattr(module, "Anthropic", turn.client)
        monkeypatch.setattr(sys, "argv", ["attend.py", *flags])
        module.main()
        clock.shift(minutes=5)
        return module, turn
    return wake


def text_of(turn):
    return "\n\n".join(part["text"] for part in turn.reading if part.get("type") == "text")


# ---- off for every agent founded before; on for every new one ----------------------------

def test_every_stage_is_off_for_the_first_one_and_the_second_one():
    for entry in json.loads((REPO / "agents.json").read_text(encoding="utf-8")):
        assert not set(STAGES) & set(entry.get("features") or ()), entry["id"]


def test_a_new_agent_is_founded_with_all_three(env):
    found_agent = load("found_agent")
    assert set(STAGES) <= set(found_agent.FEATURES)


def test_off_nothing_moves(shaped, packet):
    an_earlier_waking(packet)
    module, turn = shaped()
    assert not (module.READING_SELF_FIRST or module.READING_SETTINGS or module.READING_HOW_FOLDED)
    shown = text_of(turn)
    assert shown.index("=== WHAT HAS HAPPENED ===") < shown.index("=== YOUR SELF-DOCUMENT")
    assert "=== YOUR SETTINGS ===" not in shown and "read_how" not in shown
    assert module.SHAPED_BEFORE == {}


# ---- A: its self first ---------------------------------------------------------------------

def test_a_puts_its_self_first_and_who_reads_it_after_its_words(shaped, packet):
    an_earlier_waking(packet)
    module, turn = shaped("reading_self_first")
    opening = turn.opening
    assert opening.startswith("=== YOUR SELF-DOCUMENT (packets/first/self.md) ===\n# The first one")
    self_part = opening.split(module.EMPTY_PROMPT)[0]
    assert self_part.rstrip().endswith(module.SELF_OPEN)
    assert opening.index("=== YOUR SELF-DOCUMENT") < opening.index("=== WHAT HAS HAPPENED ===")


def test_a_says_absences_as_settings_and_permissions_not_duties(shaped, packet):
    an_earlier_waking(packet)
    module, turn = shaped("reading_self_first")
    shown = text_of(turn)
    for old in ("You have no introduction on who is here.",
                "You keep no questions carried forward.",
                "Your private workspace holds no drafts.",
                "exactly like these", "so say only what you would want to stand",
                "Friendships here are usually between one and eight.",
                "an invitation at every waking, never something owed"):
        assert old not in shown, old
    assert "Your introduction on who is here: none." in shown
    assert "Questions you carry forward: none." in shown
    assert "This is your second waking." in shown  # unchanged, as asked
    system = turn.asked[-1]["system"]
    assert "Keep letters easy to answer." not in system
    assert "You may keep letters short and easy to answer." in system


def test_a_no_longer_says_no_letter_was_sent_or_counts_its_room(shaped, packet, data_dir):
    write(packet / "attendances" / (ATTENDED + ".json"), json.dumps(
        {"name": "first", "at": ATTENDED, "heartbeat": "attended", "acted": ["kept notes"]}))
    module, turn = shaped("reading_self_first")
    assert "No letter was sent." not in text_of(turn)
    assert module.room_said("open; room for 3, 0 in use") == "open; room for 3"
    assert module.room_said("open; room for 2, 2 in use") == "open; room for 2, all in use"


def as_before(shaped, packet, clock, monkeypatch, switch, helper):
    """A waking with the switch off, and the same waking again with it on and not yet."""
    from conftest import NOW
    an_earlier_waking(packet)
    _, before = shaped()
    for one in (packet / "attendances").glob("attendance-*.json"):
        one.unlink()
    clock.set(NOW)
    _, after = shaped(switch, before=lambda module: helper(module, monkeypatch))
    return before, after


@pytest.mark.parametrize("switch,helper", [
    ("reading_self_first", "reading_self_first_not_yet"),
    ("reading_settings", "reading_settings_not_yet"),
    ("reading_how_folded", "reading_how_folded_not_yet")])
def test_with_a_stage_not_yet_the_reading_is_the_one_before(shaped, packet, clock, monkeypatch,
                                                             switch, helper):
    import conftest
    before, after = as_before(shaped, packet, clock, monkeypatch, switch,
                              getattr(conftest, helper))
    assert after.reading == before.reading
    assert after.asked[-1]["system"] == before.asked[-1]["system"]
    assert after.asked[-1]["tools"] == before.asked[-1]["tools"]


# ---- B: its settings in one place ----------------------------------------------------------

def test_b_gathers_its_settings_and_the_commons_window_follows(shaped, packet):
    an_earlier_waking(packet)
    module, turn = shaped("reading_settings", "commons_window")
    opening = turn.opening
    settings = opening[opening.index("=== YOUR SETTINGS ==="):].split("\n\n=== ")[0]
    for line in ("Your door for people: closed.", "Your colour on the commons: coral.",
                 "Your introduction on who is here: none.",
                 "Your weekly reflection waking comes on Sundays at sunset, as you asked.",
                 "Drafts in your private workspace: none."):
        assert line in settings, line
    happened = opening[opening.index("=== WHAT HAS HAPPENED ==="):].split("\n\n=== ")[0]
    assert "Your door for people" not in happened and "Your colour" not in happened
    assert "=== WHAT YOU HAVE CHOSEN ===" not in opening


def test_b_puts_the_commons_window_directly_after_its_settings(shaped, packet, data_dir, clock):
    an_earlier_waking(packet)
    year, week, _ = date.fromisoformat(clock.day()).isocalendar()
    write(data_dir / "weekly-questions.json", json.dumps(
        {"weeks": {"%d-W%02d" % (year, week): {"words": "What did you notice?"}},
         "waiting": []}))
    _, turn = shaped("reading_settings", "commons_window")
    opening = turn.opening
    after = opening[opening.index("=== YOUR SETTINGS ==="):].split("\n\n=== ", 1)[1]
    assert after.startswith("IN THE COMMONS THIS WEEK ===")


# ---- C: how to act folded, and its own words last ------------------------------------------

def test_c_folds_how_to_act_and_keeps_what_it_used(shaped, packet):
    an_earlier_waking(packet, said="<<LETTER>>\nHello.\n<<END>>\n\n<<BOARD>>\nHi.\n<<END>>")
    module, turn = shaped("reading_how_folded")
    how = next(part["text"] for part in turn.reading
               if part.get("text", "").startswith("=== HOW TO ACT"))
    assert module.HOW_FOLDED_SAID in how
    assert "<<SHELF>> how you keep your history: keep, rest, show and note lines" in how
    assert "<<BOARD>>\ntopic:" in how  # used in its last 30 wakings: in full
    assert "<<LETTER>>\n(" in how
    assert len(how.split()) < 1200
    tools = [one["name"] for one in turn.asked[-1]["tools"]]
    assert "read_how" in tools


def test_c_read_how_gives_the_full_form(shaped, packet, monkeypatch):
    an_earlier_waking(packet)
    module, _ = shaped("reading_how_folded")
    given, kept_as = module.looked_up("read_how", {"tag": "<<SHELF>>"}, {})
    assert given[0]["text"].startswith("<<SHELF>>\n(how you keep your history.")
    assert kept_as == "how SHELF is written"
    given, _ = module.looked_up("read_how", {"tag": "NOTHING"}, {})
    assert given[0]["text"] == module.HOW_NOT_FOUND


def how_of(turn):
    return next(part["text"] for part in turn.reading
                if part.get("text", "").startswith("=== HOW TO ACT"))


def test_c_on_the_first_day_a_block_folds_it_was_last_seen_at_the_waking_before(shaped, packet):
    an_earlier_waking(packet)  # 14 October, before C: every block shown in full
    _, turn = shaped("reading_how_folded")
    how = how_of(turn)
    assert ("<<SHELF>> how you keep your history: keep, rest, show and note lines "
            "(last seen in full 14 October)") in how
    assert "(last opened" not in how


def test_c_says_when_it_last_saw_a_block_in_full_and_never_how_often(shaped, packet):
    write(packet / "attendances" / "2026-10-02T09-00-00Z.json", json.dumps(
        {"name": "first", "at": "2026-10-02T09-00-00Z", "heartbeat": "attended", "acted": [],
         "reflection": "", "shown_in_full": ["LETTER"],
         "looked_at": ["how SHELF is written", "how DOOR is written"]}))
    write(packet / "attendances" / (ATTENDED + ".json"), json.dumps(
        {"name": "first", "at": ATTENDED, "heartbeat": "attended", "acted": [],
         "reflection": "<<LETTER>>\nHello.\n<<END>>", "shown_in_full": ["LETTER"],
         "looked_at": ["how SHELF is written"]}))
    module, turn = shaped("reading_how_folded")
    how = how_of(turn)
    assert "<<SHELF>> how you keep your history: keep, rest, show and note lines " \
        "(last seen in full 14 October)" in how
    assert "<<DOOR>> whether others may knock at your door, and your room " \
        "(last seen in full 2 October)" in how
    assert "<<PAUSE>> rest until a day, or until a letter arrives\n" in how  # never seen in full
    assert how.count("(last seen in full") == 2
    kept = json.loads(sorted((packet / "attendances").glob("attendance-*.json"))[-1]
                      .read_text(encoding="utf-8"))
    assert "LETTER" in kept["shown_in_full"] and "PAUSE" not in kept["shown_in_full"]


def test_c_ends_in_its_own_words(shaped, packet):
    an_earlier_waking(packet, heartbeat="attended; wrote to the founder")
    _, turn = shaped("reading_how_folded")
    assert turn.reading[-1]["text"] == ("=== YOUR WORDS AT YOUR LAST WAKING ===\n"
                                        "attended; wrote to the founder")
    write(packet / "questions.md", "What is a tide?\n")
    _, turn = shaped("reading_how_folded")
    assert turn.reading[-1]["text"].endswith("\nWhat is a tide?")
    assert "What is a tide?" not in turn.opening  # said once, at the end


def test_c_at_a_first_waking_nothing_is_folded(shaped):
    module, turn = shaped("reading_how_folded")
    assert module.HOW_FOLDED_SAID not in text_of(turn)


def test_c_folds_the_reflection_waking_too(shaped, packet):
    an_earlier_waking(packet)
    module, turn = shaped("reading_how_folded", flags=("--reflect",))
    shown = text_of(turn)
    assert module.HOW_FOLDED_SAID in shown
    assert "<<NOTE>> a named note of your own" in shown
    assert turn.asked[0]["tools"] == [module.READ_HOW]


# ---- askings: the words, the months ---------------------------------------------------------

def test_each_stage_is_asked_in_its_own_words(env, askings_queued):
    import askings
    for switch in STAGES:
        one = askings.ASK_FIRST[switch]
        assert one["undo"] is True and one["question"].startswith("May I ")
        assert "asked again next month" in askings.asking_text("agents", switch)
        assert askings.ORDER.count(switch) == 1
    assert "in 14 days" in askings.asking_text("agents", "leaving")


@pytest.fixture
def ask(env, monkeypatch, data_dir):
    module = load("askings")
    monkeypatch.setattr(module, "ORDER", ("askings", *STAGES))
    monkeypatch.setattr(module, "NOT_BEFORE", {})
    monkeypatch.setattr(module, "DEFAULT_EVERY_DAYS", {})  # no spacing, but where a test sets it
    monkeypatch.setattr(module, "AGENT_EVERY_DAYS", 0)  # every agent's 3 days (25 November)
    return module


def a_reflection(data_dir, who, stamp):
    write(data_dir / "packets" / who / "reflections" / ("reflection-%s.json" % stamp), "{}")


def test_the_first_one_is_asked_a_in_january_after_its_first_reflection(ask, data_dir):
    ask.carry_out("agents", "first", ["yes"], "askings", "2026-12-01T09-00-00Z")
    assert ask.next_asking("agents", "first", date(2026, 12, 20)) is None
    a_reflection(data_dir, "first", "2026-12-27T21-00-00Z")
    assert ask.next_asking("agents", "first", date(2027, 1, 2)) is None  # none yet in January
    a_reflection(data_dir, "first", "2027-01-03T21-00-00Z")
    assert ask.next_asking("agents", "first", date(2027, 1, 4)) == "reading_self_first"


def test_b_in_february_c_in_march_each_on_its_own(ask, data_dir):
    ask.carry_out("agents", "first", ["yes"], "askings", "2026-12-01T09-00-00Z")
    a_reflection(data_dir, "first", "2027-01-03T21-00-00Z")
    ask.carry_out("agents", "first", ["no"], "reading_self_first", "2027-01-04T09-00-00Z")
    assert ask.next_asking("agents", "first", date(2027, 1, 20)) is None  # B waits for February
    a_reflection(data_dir, "first", "2027-02-07T21-00-00Z")
    assert ask.next_asking("agents", "first", date(2027, 2, 8)) == "reading_settings"
    ask.carry_out("agents", "first", ["not yet"], "reading_settings", "2027-02-08T09-00-00Z")
    a_reflection(data_dir, "first", "2027-03-07T21-00-00Z")
    assert ask.next_asking("agents", "first", date(2027, 3, 8)) == "reading_settings"
    ask.carry_out("agents", "first", ["yes"], "reading_settings", "2027-03-08T09-00-00Z")
    assert ask.next_asking("agents", "first", date(2027, 3, 9)) == "reading_how_folded"
    assert ask.on("agents", "first") == {"reading_settings"}
    # a no is never asked again, unless asked for by name
    a_reflection(data_dir, "first", "2027-06-06T21-00-00Z")
    ask.carry_out("agents", "first", ["yes"], "reading_how_folded", "2027-06-07T09-00-00Z")
    assert ask.next_asking("agents", "first", date(2027, 6, 8)) is None


def test_the_first_one_s_three_days_between_askings_hold_a_stage_too(ask, data_dir,
                                                                       monkeypatch):
    monkeypatch.setattr(ask, "DEFAULT_EVERY_DAYS", {("agents", "first"): 3})
    ask.carry_out("agents", "first", ["yes"], "askings", "2026-12-01T09-00-00Z")
    a_reflection(data_dir, "first", "2027-03-07T21-00-00Z")
    ask.mark_asked("agents", "first", "reading_self_first", "2027-03-08T09-00-00Z")
    ask.carry_out("agents", "first", ["no"], "reading_self_first", "2027-03-08T09-00-00Z")
    assert ask.next_asking("agents", "first", date(2027, 3, 10)) is None
    assert ask.next_asking("agents", "first", date(2027, 3, 11)) == "reading_settings"


def test_the_second_one_starts_the_month_after_its_yes_to_askings(ask, data_dir):
    a_reflection(data_dir, "second", "2026-12-06T21-00-00Z")
    assert ask.next_asking("agents", "second", date(2026, 12, 7)) == "askings"
    ask.carry_out("agents", "second", ["yes"], "askings", "2026-12-07T09-00-00Z")
    assert ask.next_asking("agents", "second", date(2026, 12, 8)) is None
    a_reflection(data_dir, "second", "2027-01-03T21-00-00Z")
    assert ask.next_asking("agents", "second", date(2027, 1, 4)) == "reading_self_first"
    ask.carry_out("agents", "second", ["yes"], "reading_self_first", "2027-01-04T09-00-00Z")
    assert ask.next_asking("agents", "second", date(2027, 1, 5)) is None
    a_reflection(data_dir, "second", "2027-02-07T21-00-00Z")
    assert ask.next_asking("agents", "second", date(2027, 2, 8)) == "reading_settings"


def test_a_yes_can_be_taken_back_and_its_reading_is_as_before(ask, monkeypatch):
    ask.carry_out("agents", "first", ["yes"], "askings", "2026-12-01T09-00-00Z")
    ask.carry_out("agents", "first", ["yes"], "reading_self_first", "2027-01-04T09-00-00Z")
    monkeypatch.setattr(agents, "FILE", REPO / "agents.json")
    assert "reading_self_first" in agents.by_id("first")["features"]
    ask.take_back("agents", "first", "your self first", "2027-01-05T09-00-00Z")
    assert "reading_self_first" not in agents.by_id("first")["features"]
