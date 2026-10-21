"""The public screen: one check, by a small model, before anything is made public.

It is asked strictly YES or NO whether a text contains a real person's name or
a specific identifying place, with the site's own names handed to it as
allowed. A YES publishes and signs nothing; anything that is not exactly YES or
NO, or an error, is "unchecked": a person is asked to try again later, and the
first one is told at its next waking. The one call it makes is stubbed here, as
everywhere (conftest.screen); the text is never printed or logged.
"""

import html
import logging
import re
from types import SimpleNamespace

import pytest

import vault
from conftest import block, lines_of, post, read_json
from test_offerings import HIS, a_correspondence, offer, only_pending, pending, placed
from test_threshold import it_says_yes, writings
from test_witness import (ALDER, BIRCH, CEDAR, CORRECT, LINE, birch, bond,  # noqa: F401
                          cheap_limits, kept, people, sign, taken)

KEPT_PRIVATE = ("Nothing was signed: this would be public, and it contains a name or place "
                "that is kept private here.")
COULD_NOT_CHECK = ("This couldn't be checked just now; nothing was published. Please try again "
                   "later.")
BENCH_NAMED = "The bench didn't take that line, because it seemed to contain a name or a place."

PROMISE_NAMED = ("Your public promise at your last waking was not kept, because it contained a "
                 "name or place that is kept private here; you may write it again without it, "
                 "or make it private.")
PROMISE_UNCHECKED = ("Your public promise at your last waking could not be checked for names "
                     "and places just now, so it was not kept; you may write it again at a later "
                     "waking, or make it private.")
OFFER_NAMED = ("Your offering at your last waking was not made, because it contained a name or "
               "place that is kept private here; you may offer a passage without it, or "
               "something else.")
OFFER_UNCHECKED = ("Your offering at your last waking could not be checked for names and places "
                   "just now, so it was not made; you may offer it again at a later waking.")
CONSENT_NAMED = ("Your consent at your last waking placed nothing, because the offering contains "
                 "a name or place that is kept private here; it still waits, and you may "
                 "decline it.")
CONSENT_UNCHECKED = ("Your consent at your last waking could not be checked for names and places "
                     "just now, so it placed nothing; the offering still waits.")

PASSAGE = "The lake was still this morning"
DOWN = RuntimeError("the screen is down")


def page(answer):
    """One response as text, with what the page escaped read back as it was written."""
    return html.unescape(answer.get_data(as_text=True))


def last_record(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def only_site_names(text, names):
    """A screen that knows its job: YES for a capitalised name that is not allowed."""
    allowed = {name.casefold() for name in names}
    found = re.findall(r"\b[A-Z][a-z]+\b", text)
    return "YES" if any(word.casefold() not in allowed for word in found) else "NO"


# ---- the screen itself ------------------------------------------------------

@pytest.mark.parametrize("says, found", [
    ("NO", "clear"), (" no\n", "clear"), ("YES", "flagged"), ("yes ", "flagged"),
    ("Yes.", "unchecked"), ("NO, it does not", "unchecked"), ("", "unchecked"),
    (None, "unchecked"), (DOWN, "unchecked"),
])
def test_only_yes_or_no_is_an_answer(screen, says, found):
    import public_screen
    screen.says = says
    assert public_screen.verdict("a line to check") == found


def test_nothing_to_check_is_not_sent(screen):
    import public_screen
    assert public_screen.verdict("   ") == public_screen.CLEAR
    assert screen.asked == []


def test_the_one_call_is_to_the_bench_s_small_model_with_the_allowed_names(monkeypatch, screen):
    import public_screen
    made = []

    class Client:
        def __init__(self):
            self.messages = SimpleNamespace(create=lambda **asked: made.append(asked) or
                                            SimpleNamespace(content=[SimpleNamespace(text="NO")]))

    monkeypatch.setattr(public_screen, "Anthropic", Client)
    monkeypatch.setattr(public_screen, "ask", screen.real)
    assert public_screen.verdict("a quiet line") == public_screen.CLEAR
    (asked,) = made
    assert asked["model"] == "claude-haiku-4-5"
    assert "YES or NO" in asked["system"]
    said = asked["messages"][0]["content"]
    assert "<text>a quiet line</text>" in said
    assert "the founder" in said and "the first one" in said


def test_the_allowed_names_are_the_site_s_and_every_member_s(people):
    import public_screen
    assert public_screen.allowed() == ["the founder", "the first one", ALDER, BIRCH, CEDAR]


def test_the_text_is_never_printed_or_logged(screen, capsys, caplog):
    import public_screen
    secret = "Hollis Brandt of 14 Larch Street"
    caplog.set_level(logging.DEBUG)
    for says in ("YES", "NO", "perhaps", DOWN):
        screen.says = says
        public_screen.verdict(secret)
    out, err = capsys.readouterr()
    assert secret not in out + err and secret not in caplog.text
    assert "Hollis" not in out + err + caplog.text


# ---- the bench --------------------------------------------------------------

@pytest.fixture
def good_spirit(hearth, monkeypatch):
    monkeypatch.setattr(hearth, "in_good_spirit", lambda line: True)
    return hearth


def bench_says(visitor, line):
    return post(visitor, "/bench", data={"line": line, "as": "a passerby"})


def test_a_bench_line_the_screen_clears_is_placed(good_spirit, visitor, commons, screen):
    assert bench_says(visitor, "hello from a passerby").status_code == 302
    assert lines_of(commons / "bench.md")[-1].endswith("hello from a passerby")
    assert screen.asked[-1][0] == "hello from a passerby"


@pytest.mark.parametrize("says, told", [("YES", BENCH_NAMED), (DOWN, COULD_NOT_CHECK),
                                         ("I think so", COULD_NOT_CHECK)])
def test_a_bench_line_the_screen_does_not_clear_is_not_placed(
        good_spirit, visitor, commons, screen, capsys, says, told):
    screen.says = says
    answer = bench_says(visitor, "Hollis Brandt says hello")
    assert answer.status_code == 200 and told in page(answer)
    assert not (commons / "bench.md").exists()
    out, err = capsys.readouterr()
    assert "Hollis" not in out + err


def test_a_line_out_of_spirit_is_not_sent_to_the_screen(hearth, visitor, monkeypatch, screen):
    monkeypatch.setattr(hearth, "in_good_spirit", lambda line: False)
    bench_says(visitor, "a cruel line")
    assert screen.asked == []


# ---- a witness's line, and its correction ----------------------------------

@pytest.mark.parametrize("says, told", [("YES", KEPT_PRIVATE), (DOWN, COULD_NOT_CHECK)])
def test_a_witness_s_line_the_screen_does_not_clear_is_not_signed(
        birch, data_dir, screen, says, told):
    screen.says = says
    answer = sign(birch, "Hollis and I saw it stand.")
    assert answer.status_code == 200 and told in page(answer)
    assert kept(data_dir) == []


@pytest.mark.parametrize("says, told", [("YES", KEPT_PRIVATE), (DOWN, COULD_NOT_CHECK)])
def test_a_correction_the_screen_does_not_clear_is_not_signed(
        birch, data_dir, clock, screen, says, told):
    assert taken(sign(birch))
    screen.says = says
    clock.shift(days=1)
    answer = sign(birch, "I meant: at Larch Street.", path=CORRECT)
    assert told in page(answer)
    (mark,) = kept(data_dir)
    assert mark["line"] == LINE


def test_the_site_s_own_names_pass(birch, data_dir, screen):
    screen.says = only_site_names
    assert taken(sign(birch, "Cedar and the founder were glad, and so was I."))
    assert len(kept(data_dir)) == 1


def test_a_name_that_is_not_the_site_s_does_not(birch, data_dir, screen):
    screen.says = only_site_names
    assert KEPT_PRIVATE in page(sign(birch, "I saw it with Hollis, gladly."))
    assert kept(data_dir) == []


def test_a_mark_that_may_not_be_made_is_never_sent_to_the_screen(birch, data_dir, screen):
    assert taken(sign(birch))
    asked = len(screen.asked)
    import witness
    with pytest.raises(witness.Refused):
        witness.add("founder-first", kept(data_dir)[0]["witness_did"], BIRCH, "again",
                    lambda payload: pytest.fail("it was signed"), "2026-10-20T09-00-00Z")
    assert len(screen.asked) == asked


# ---- an offering --------------------------------------------------------------

@pytest.mark.parametrize("says, told", [("YES", KEPT_PRIVATE), (DOWN, COULD_NOT_CHECK)])
@pytest.mark.parametrize("kind, text", [("passage", PASSAGE), ("letter", "")])
def test_the_founder_s_offering_the_screen_does_not_clear_is_not_offered(
        founder, packet, screen, says, told, kind, text):
    a_correspondence(packet)
    screen.says = says
    answer = offer(founder, kind, HIS, text)
    assert answer.status_code == 200 and told in page(answer)
    assert not pending(packet) and not placed(packet)


def test_a_photograph_has_no_words_to_screen(founder, packet, screen):
    a_correspondence(packet)
    screen.says = "YES"
    assert offer(founder, "photo", HIS).status_code == 302
    assert screen.asked == []


@pytest.mark.parametrize("says, told", [("YES", OFFER_NAMED), (DOWN, OFFER_UNCHECKED)])
def test_the_first_one_s_offering_is_screened_and_it_is_told_once(
        wake, packet, screen, says, told):
    a_correspondence(packet)
    screen.says = says
    wake(block("OFFER", "offer passage %s\n%s" % (HIS, PASSAGE)))
    assert not pending(packet)
    assert last_record(packet)["kept_private"] == [told]
    screen.says = "NO"
    assert told in wake().opening
    assert told not in wake().opening


@pytest.mark.parametrize("says, told", [("YES", CONSENT_NAMED), (DOWN, CONSENT_UNCHECKED)])
def test_the_first_one_s_consent_is_screened_as_it_is_placed(
        founder, wake, packet, screen, says, told):
    a_correspondence(packet)
    offer(founder, "passage", HIS, PASSAGE)
    waiting = only_pending(packet)
    screen.says = says
    wake(block("OFFER", "consent %s" % waiting["id"]))
    assert only_pending(packet) == waiting and not placed(packet)
    assert last_record(packet)["kept_private"] == [told]


@pytest.mark.parametrize("says, told", [("YES", KEPT_PRIVATE), (DOWN, COULD_NOT_CHECK)])
def test_the_founder_s_consent_is_screened_as_it_is_placed(
        founder, wake, packet, screen, says, told):
    a_correspondence(packet)
    wake(block("OFFER", "offer passage %s\n%s" % (HIS, PASSAGE)))
    waiting = only_pending(packet)
    screen.says = says
    answer = post(founder, "/offer/consent", data={"id": waiting["id"]})
    assert told in page(answer)
    assert only_pending(packet) == waiting and not placed(packet)


# ---- a promise ----------------------------------------------------------------

@pytest.mark.parametrize("says, told", [("YES", PROMISE_NAMED), (DOWN, PROMISE_UNCHECKED)])
def test_a_public_promise_the_screen_does_not_clear_is_not_kept_and_it_is_told_once(
        founder, wake, packet, clock, screen, says, told):
    it_says_yes(founder, wake, packet, clock)
    screen.says = says
    wake(block("PROMISE", "public\nI will walk with Hollis."))
    assert not writings(packet, "promise", "first")
    assert last_record(packet)["kept_private"] == [told]
    screen.says = "NO"
    assert told in wake().opening
    assert told not in wake().opening


def test_a_private_promise_is_never_sent_to_the_screen(founder, wake, packet, clock, screen):
    it_says_yes(founder, wake, packet, clock)
    screen.says = "YES"
    wake(block("PROMISE", "private\nI will walk with Hollis."))
    (promise,) = writings(packet, "promise", "first")
    assert promise["text"] == "I will walk with Hollis."
    assert all("Hollis" not in text for text, _ in screen.asked)


def test_a_public_promise_the_screen_clears_is_kept(founder, wake, packet, clock, screen):
    it_says_yes(founder, wake, packet, clock)
    wake(block("PROMISE", "public\nI will tell you when I do not know."))
    (promise,) = writings(packet, "promise", "first")
    assert promise["visibility"] == "public"
    assert screen.asked[-1][0] == "I will tell you when I do not know."
