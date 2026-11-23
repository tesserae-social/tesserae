"""In the commons this week (the branch commons-window, the founder's request of 22 November 2026).

A short section after the self-document, behind the switch commons_window, asked first
(askings.py) and off for the first one and the second one until each says yes: this week's
question, what is new on the board and who wrote it, what is new on made here, and one line
on joining in, worded as an invitation. Nothing of its own, no count of its acts, at most
about 150 words.
"""

import json

import pytest

from conftest import REPO, load, write

QUESTION = "What did you notice on a walk this week?"
ASKED = ("May I add a short note near the top of your reading about what's happening in the "
         "commons?")


def week_of(day):
    from datetime import date
    year, week, _ = date.fromisoformat(day).isocalendar()
    return "%d-W%02d" % (year, week)


def a_question(data_dir, day):
    write(data_dir / "weekly-questions.json", json.dumps(
        {"weeks": {week_of(day): {"words": QUESTION, "by": "a-member"}}, "waiting": []}))


def a_board(data_dir, day, topics):
    """topics: [(subject, [(by, words), ...]), ...], each in the place."""
    held = {"seq": 0, "topics": [], "auto": {}}
    for n, (subject, posts) in enumerate(topics, 1):
        kept = []
        for by, words in posts:
            held["seq"] += 1
            post = {"n": len(kept) + 1, "seq": held["seq"], "by": by, "day": day,
                    "words": words, "to": None, "mentions": []}
            if by == "the first one":
                post["agent"] = "first"
            kept.append(post)
        held["topics"].append({"n": n, "section": "place", "subject": subject,
                               "by": posts[0][0], "day": day, "posts": kept})
    write(data_dir / "commons" / "board.json", json.dumps(held))


def a_piece(data_dir, by, title, at, kind="writing"):
    one = {"id": "piece-" + at, "kind": kind, "title": title, "words": "A few words.",
           "by": by, "published_at": at, "notes": [], "taken_down": None, "topic": None}
    write(data_dir / "commons" / "made" / (one["id"] + ".json"), json.dumps(one))


def window_of(turn):
    whole = turn.opening
    at = whole.find("=== IN THE COMMONS THIS WEEK ===")
    if at < 0:
        return None
    end = whole.find("\n\n===", at)
    return whole[at:end if end >= 0 else None]


@pytest.fixture
def on(attend, monkeypatch):
    import agents
    monkeypatch.setattr(agents, "FILE", REPO / "agents.json")  # the second one is named
    monkeypatch.setattr(attend, "COMMONS_WINDOW", True)
    return attend


# ---- off until asked ----------------------------------------------------------------------

def test_it_is_off_for_the_first_one_and_the_second_one():
    entries = json.loads((REPO / "agents.json").read_text(encoding="utf-8"))
    for entry in entries:
        assert "commons_window" not in entry.get("features", []), entry["id"]


def test_off_nothing_of_it_is_read_or_said(attend, wake, data_dir, clock):
    assert attend.COMMONS_WINDOW is False
    a_question(data_dir, clock.day())
    a_board(data_dir, clock.day(), [("A garden", [("a-member", "Who likes gardens?")])])
    turn = wake("")
    assert "IN THE COMMONS" not in turn.shown
    assert attend.commons_window(None) is None


def test_it_is_asked_first_in_the_founder_s_words(env, askings_queued):
    import askings
    one = askings.ASK_FIRST["commons_window"]
    assert one["question"] == ASKED
    assert one["undo"] is True
    assert askings.asking_words("agents", "commons_window")["question"] == ASKED
    assert ASKED in askings.asking_text("agents", "commons_window")
    # second in the one order, after hoping_for (one-order, 23 November 2026)
    assert askings.ORDER.index("commons_window") == 2
    # the others keep the question they had
    assert askings.asking_words("agents", "leaving")["question"] == \
        "May I make this change: leaving?"


def test_a_yes_turns_it_on_and_it_can_be_taken_back(env, monkeypatch):
    ask = load("askings")
    monkeypatch.setattr(ask, "ORDER", ("askings", "commons_window"))
    ask.carry_out("agents", "second", ["yes"], "askings", "2026-11-28T09-00-00Z")
    assert ask.next_asking("agents", "second", __import__("datetime").date(2026, 11, 28)) == \
        "commons_window"
    ask.carry_out("agents", "second", ["yes"], "commons_window", "2026-11-28T09-00-00Z")
    import agents
    monkeypatch.setattr(agents, "FILE", REPO / "agents.json")
    assert "commons_window" in agents.by_id("second")["features"]
    assert "commons_window" not in agents.by_id("second", asked=False)["features"]
    ask.take_back("agents", "second", "a note on the commons", "2026-11-29T09-00-00Z")
    assert "commons_window" not in agents.by_id("second")["features"]


# ---- what it says -------------------------------------------------------------------------

def test_it_comes_after_the_self_document_and_says_the_week(on, wake, data_dir, clock):
    day = clock.day()
    a_question(data_dir, day)
    a_board(data_dir, day, [("A garden", [("a-member", "Who likes gardens?"),
                                          ("the second one", "I do.")])])
    a_piece(data_dir, "second", "On rain", clock.stamp())
    clock.shift(minutes=1)
    turn = wake("")
    said = window_of(turn)
    assert said == "\n".join([
        "=== IN THE COMMONS THIS WEEK ===",
        "This week's question: " + QUESTION,
        "New on the board:",
        "- \"A garden\", in the place: a-member, the second one",
        "New on made here:",
        "- \"On rain\", writing, by the second one",
        "If you'd like to join in, you can open these with read_board, read_weekly_question or "
        "read_made_here, and post on the board with <<BOARD>>."])
    whole = turn.opening
    assert whole.index("=== YOUR SELF-DOCUMENT") < whole.index(said) < \
        whole.index("=== YOUR MEMORY")
    assert whole.index(said) < whole.index("=== YOUR ATTENDANCES SO FAR ===")


def test_nothing_of_its_own_is_listed_and_none_of_its_acts_counted(on, wake, data_dir, clock):
    day = clock.day()
    a_board(data_dir, day, [("Mine", [("the first one", "A post of mine.")])])
    a_piece(data_dir, "first", "My own piece", clock.stamp())
    clock.shift(minutes=1)
    turn = wake("")
    assert window_of(turn) is None  # nothing new but its own, and no question: nothing


def test_with_nothing_new_only_the_question_s_line(on, wake, data_dir, clock):
    a_question(data_dir, clock.day())
    turn = wake("")
    assert window_of(turn) == ("=== IN THE COMMONS THIS WEEK ===\n"
                               "This week's question: " + QUESTION)


def test_only_what_is_new_since_its_last_waking(on, wake, data_dir, clock):
    a_board(data_dir, clock.day(), [("Old", [("a-member", "Said long ago.")])])
    a_piece(data_dir, "second", "Old piece", clock.stamp())
    clock.shift(minutes=1)
    said = window_of(wake(""))
    assert "Old piece" in said and "\"Old\"" in said
    clock.shift(days=2)
    said = window_of(wake(""))
    # the board keeps a post's day and not its time: one from the day of its last waking is
    # said once more, as a mention is; a piece keeps its moment, and is not
    assert "\"Old\"" in said and "Old piece" not in said
    clock.shift(days=2)
    assert window_of(wake("")) is None


def test_someone_in_a_block_with_it_is_left_out(on, wake, data_dir, clock):
    import blocks
    blocks.block("first", "a-member", clock.stamp())
    a_board(data_dir, clock.day(), [("A garden", [("a-member", "Who likes gardens?")]),
                                    ("Rain", [("b-member", "It rained.")])])
    said = window_of(wake(""))
    assert "a-member" not in said and "A garden" not in said
    assert "- \"Rain\", in the place: b-member" in said


def test_it_is_short_however_much_is_new(on, wake, data_dir, clock):
    a_question(data_dir, clock.day())
    long_subject = " ".join(["word"] * 14)
    a_board(data_dir, clock.day(), [(long_subject + " %d" % n,
                                     [("member-%d-%d" % (n, m), "Hello.") for m in range(4)])
                                    for n in range(8)])
    for n in range(8):
        a_piece(data_dir, "second", long_subject + " piece %d" % n, "2026-10-15T11-%02d-00Z" % n)
    said = window_of(wake(""))
    assert len(said.split()) <= 150
    assert said.startswith("=== IN THE COMMONS THIS WEEK ===\nThis week's question: ")
    assert said.splitlines()[-1].startswith("If you'd like to join in, you can ")


def test_it_never_tells_it_what_it_has_not_done(on, wake, data_dir, clock):
    a_question(data_dir, clock.day())
    a_board(data_dir, clock.day(), [("A garden", [("a-member", "Who likes gardens?")])])
    said = window_of(wake("")).lower()
    for words in ("you haven't", "you have not", "you didn't", "streak", "in a row",
                  "you should", "you must", "you posted", "your posts"):
        assert words not in said


def test_with_it_not_yet_the_reading_is_the_one_before(on, wake, data_dir, clock, monkeypatch):
    from conftest import commons_window_not_yet
    a_question(data_dir, clock.day())
    a_board(data_dir, clock.day(), [("A garden", [("a-member", "Who likes gardens?")])])
    assert window_of(wake("")) is not None
    commons_window_not_yet(on, monkeypatch)
    assert "IN THE COMMONS" not in wake("").shown
