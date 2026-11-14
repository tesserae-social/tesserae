"""The daily spending caps: each agent's wakings, and every screening call, stop for the day.

The founder's decision of 13 November 2026 (spending.py). Each request is counted
with its provider's own usage numbers; once an agent's day reaches its cap, no
waking of it begins until the UTC day turns, and /tides says so plainly; once
the screens' day reaches its cap, nothing more is screened, and so nothing that
needs screening is placed. A member's own screened tries are limited too, so
that no one person can spend the site's day.
"""

import json
import re
from types import SimpleNamespace

import pytest

from conftest import page, post

# a reply's usage, as Anthropic's client gives it
USAGE = SimpleNamespace(input_tokens=100_000, output_tokens=10_000,
                        cache_creation_input_tokens=0, cache_read_input_tokens=0)


@pytest.fixture
def spending(env, clock, monkeypatch):
    import spending as module
    clock.pin(module, monkeypatch)
    return module


def spend(spending, who, dollars):
    """Write one day's line for who, of so many dollars."""
    path = spending.day_file(spending.today())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as kept:
        kept.write(json.dumps({"who": who, "model": "x", "dollars": dollars}) + "\n")


# ---- counting ------------------------------------------------------------

def test_a_request_is_priced_with_its_provider_s_own_numbers(spending):
    # 100k input at $3 and 10k output at $15 a million, on the first one's model
    assert spending.record("first", "claude-sonnet-4-5", USAGE) == pytest.approx(0.45)
    assert spending.spent("first") == pytest.approx(0.45)
    assert spending.spent("someone-else") == 0.0


def test_cache_reads_and_writes_are_priced_as_such(spending):
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 1_000_000,
             "cache_read_input_tokens": 1_000_000}
    assert spending.dollars("claude-sonnet-4-5", spending.counts_of(usage)) == pytest.approx(4.05)


def test_a_model_not_on_the_list_is_priced_above_any_that_is(spending):
    counts = spending.counts_of(USAGE)
    unknown = spending.dollars("a-model-not-listed", counts)
    assert all(unknown >= spending.dollars(model, counts) for model in spending.PRICES)


def test_a_reply_with_no_usage_counts_nothing(spending):
    assert spending.record("first", "claude-sonnet-4-5", None) == 0.0


def test_the_cap_is_reached_and_the_day_turning_lets_it_go(spending, clock):
    assert not spending.spent_out("first")
    spend(spending, "first", spending.CAP_PER_AGENT)
    assert spending.spent_out("first")
    clock.shift(days=1)
    assert not spending.spent_out("first")


def test_the_two_caps_are_set_in_one_place(spending):
    assert spending.cap("first") == spending.CAP_PER_AGENT == 1.00
    assert spending.cap(spending.SCREENS) == spending.CAP_SCREENS == 1.00


def test_what_is_kept_is_numbers_and_never_words(spending):
    spending.record("first", "claude-sonnet-4-5", USAGE)
    line = json.loads(spending.day_file(spending.today()).read_text(encoding="utf-8"))
    assert set(line) == {"who", "model", "dollars", *spending.COUNTS}


# ---- an agent's wakings ----------------------------------------------------

def test_every_request_of_a_waking_is_counted_against_its_agent(attend, wake, data_dir):
    import spending
    wake("Dear founder,\n\nA short letter.\n")
    lines = [json.loads(line) for line in
             (data_dir / "spending").glob("*.jsonl").__next__().read_text().splitlines()]
    assert lines and all(line["who"] == attend.AGENT_ID for line in lines)
    assert spending  # imported where attend.py imports it


def test_spending_line_holds_only_numbers(attend, wake, data_dir):
    """What a waking leaves in spending/ is the site's bookkeeping (conftest.site_bookkeeping),
    passed over by every comparison of what a waking leaves behind; so it is held here
    instead: its model, its agent's id, and numbers. Never any words."""
    letter = "Dear founder,\n\nThe kingfisher came back to the pond at noon.\n"
    wake(letter)
    kept = sorted((data_dir / "spending").rglob("*"))
    assert len([path for path in kept if path.is_file()]) == 1
    assert re.fullmatch(r"spending-\d{4}-\d{2}-\d{2}\.jsonl", kept[0].name)
    text = kept[0].read_text(encoding="utf-8")
    lines = [json.loads(line) for line in text.splitlines()]
    assert lines
    import spending
    for line in lines:
        assert set(line) == {"who", "model", "dollars", *spending.COUNTS}
        assert line["who"] == attend.AGENT_ID
        assert line["model"] == attend.MODEL
        assert all(type(line[count]) is int for count in spending.COUNTS)
        assert type(line["dollars"]) in (int, float)
    for word in ("kingfisher", "pond", "noon", "Dear", "founder"):
        assert word not in text
    # nothing but the keys, the id, the model and digits
    words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_.\-]*", text))
    assert words <= {"who", "model", "dollars", attend.AGENT_ID, attend.MODEL, *spending.COUNTS}


def test_the_counted_client_hands_back_the_reply_unchanged(attend):
    reply = SimpleNamespace(usage=USAGE, content=[])
    inner = SimpleNamespace(messages=SimpleNamespace(create=lambda **asked: reply))
    assert attend.counted(inner).messages.create(model=attend.MODEL) is reply


def test_a_waking_is_refused_before_anything_once_the_cap_is_reached(attend, wake, data_dir,
                                                                     monkeypatch):
    import spending
    monkeypatch.setattr(spending, "spent_out", lambda who, now=None: who == attend.AGENT_ID)
    with pytest.raises(SystemExit) as stopped:
        wake("Dear founder,\n\nThis should not be asked for.\n")
    assert stopped.value.code == attend.SPENT_OUT
    assert not list((data_dir / "packets" / "first" / "attendances").glob("*.json"))


def test_the_hearth_refuses_the_waking_and_tide_log_says_so_plainly(hearth, founder,
                                                                   monkeypatch, data_dir):
    import spending
    monkeypatch.setattr(spending, "spent_out", lambda who, now=None: who == "first")
    ran = []
    monkeypatch.setattr(hearth.subprocess, "run", lambda *a, **k: ran.append(a))
    trouble = hearth.hold_attendance(tide=True)
    assert ran == []  # attend.py was never started
    assert trouble[2] == hearth.SPENT_OUT_STATUS
    said = hearth.tide_said(trouble, "ran")
    assert said == spending.refused_note()
    assert not said.startswith("error")
    hearth.tide_note(said)
    shown = page(founder.get("/tides"))
    assert "Not woken at" in shown
    assert "today&#39;s spending limit of $1.00 was reached" in shown
    assert "tried again at the next waking time" in shown


def test_a_refusal_from_attend_itself_is_said_the_same_way(hearth, monkeypatch):
    finished = SimpleNamespace(returncode=hearth.the_waking.SPENT_OUT, stdout="", stderr="")
    monkeypatch.setattr(hearth.subprocess, "run", lambda *a, **k: finished)
    trouble = hearth.hold_attendance(tide=True)
    assert hearth.tide_said(trouble, "ran") == hearth.spending.refused_note()


def test_tides_says_nothing_of_the_cap_on_a_day_without_a_refusal(hearth, founder):
    shown = page(founder.get("/tides"))
    assert "Not woken at" not in shown
    assert "spending limit" not in shown


# ---- screening -----------------------------------------------------------

def test_a_screening_call_is_counted_as_the_screens(env, monkeypatch, data_dir):
    import public_screen
    import spending
    answer = SimpleNamespace(content=[SimpleNamespace(text="NO")], usage=USAGE)
    monkeypatch.setattr(public_screen, "Anthropic", lambda: SimpleNamespace(
        messages=SimpleNamespace(create=lambda **asked: answer)))
    public_screen.ask.real("a quiet day", [])
    assert spending.spent(spending.SCREENS) > 0


def test_once_the_screens_cap_is_reached_nothing_is_asked(env, screen, monkeypatch):
    import public_screen
    import spending
    monkeypatch.setattr(spending, "spent_out", lambda who, now=None: who == spending.SCREENS)
    assert public_screen.verdict("a quiet day") == public_screen.UNCHECKED
    assert screen.asked == []


def test_the_bench_s_word_on_good_spirit_is_not_asked_past_the_cap(hearth, monkeypatch):
    import spending
    monkeypatch.setattr(spending, "spent_out", lambda who, now=None: who == spending.SCREENS)
    monkeypatch.setattr(hearth, "Anthropic", lambda: pytest.fail("asked past the cap"))
    assert hearth.in_good_spirit("a quiet day") is False


def test_tides_says_when_the_screens_cap_is_reached(hearth, founder, monkeypatch):
    import spending
    monkeypatch.setattr(spending, "spent_out", lambda who, now=None: who == spending.SCREENS)
    assert "Today&#39;s spending limit for screening, $1.00, has been reached" in page(
        founder.get("/tides"))


# ---- a member's screened tries ---------------------------------------------

def test_a_member_s_screened_tries_are_limited_for_the_day(hearth, founder, monkeypatch, screen):
    monkeypatch.setattr(hearth, "in_good_spirit", lambda words: True)
    screen.says = "YES"  # every try is held, so none is placed and each may be tried again
    for _ in range(hearth.SCREENED_A_DAY):
        answer = post(founder, "/account/introduction", data={"introduction": "I like rivers."})
        assert hearth.TOO_MANY_TRIES not in page(answer)
    asked = len(screen.asked)
    answer = post(founder, "/account/introduction", data={"introduction": "I like rivers."})
    assert hearth.TOO_MANY_TRIES in page(answer).replace("&#39;", "'")
    assert len(screen.asked) == asked  # the one past the limit asked nothing


def test_the_limit_is_one_count_across_every_page(hearth, founder, monkeypatch, screen):
    monkeypatch.setattr(hearth, "in_good_spirit", lambda words: True)
    screen.says = "YES"
    for _ in range(hearth.SCREENED_A_DAY):
        post(founder, "/account/introduction", data={"introduction": "I like rivers."})
    answer = post(founder, "/board", data={"words": "Good morning, everyone."})
    assert hearth.TOO_MANY_TRIES in page(answer).replace("&#39;", "'")


def test_a_try_refused_before_any_model_is_not_counted(hearth, founder, screen):
    for _ in range(hearth.SCREENED_A_DAY + 5):
        post(founder, "/account/introduction", data={"introduction": "see www.example.org"})
    assert screen.asked == []
    assert hearth.SCREENED_TRIES == {}
