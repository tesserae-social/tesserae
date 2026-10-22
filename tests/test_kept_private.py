"""What is public and signed is held to the private list before it is signed.

A signature is never changed, and so a protected word in something public and
signed could never be taken out of it again: an offering's words, a witness's
line and its correction, and a promise made public are refused instead, in one
plain sentence, with nothing signed and nothing kept. The first one is told
once, at its next waking, in words that never say the word. A private promise
is never read for them. The names here are made up, as in test_private_words.py.
"""

import json

import pytest

import vault
from conftest import block, page, post, read_json, write
from test_offerings import (HIS, HERS, a_correspondence, offer, only_pending, pending,
                            placed)
from test_threshold import it_says_yes, writings
from test_witness import (CORRECT, LINE, birch, bond, cheap_limits, kept,  # noqa: F401
                          people, sign, taken)

KEPT_PRIVATE = ("Nothing was signed: this would be public, and it contains a name or place "
                "that is kept private here.")
PROMISE_TOLD = ("Your public promise at your last waking was not kept, because it contained a "
                "name or place that is kept private here; you may write it again without it, "
                "or make it private.")
OFFER_TOLD = ("Your offering at your last waking was not made, because it contained a name or "
              "place that is kept private here; you may offer a passage without it, or "
              "something else.")
CONSENT_TOLD = ("Your consent at your last waking placed nothing, because the offering contains "
                "a name or place that is kept private here; it still waits, and you may "
                "decline it.")

# His letter says "The lake was still this morning": here the lake is a protected place.
LAKE = "Quillon => the founder\nthe lake\n"
PASSAGE = "The lake was still this morning"


@pytest.fixture
def lake(data_dir):
    return write(data_dir / "private-words.txt", LAKE)


def last_record(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


# ---- the check itself -------------------------------------------------------

@pytest.mark.parametrize("text, carries", [
    ("Quillon wrote", True), ("QUILLON wrote", True), ("quillon's letter", True),
    ("by the lake", True), ("by the  LAKE", True),
    ("Quillonia wrote", False), ("the lakes", False), ("a lake", False), ("", False),
])
def test_a_text_carries_a_word_in_any_case_and_only_whole(attend, text, carries):
    import private_words
    words = [("Quillon", "the founder"), ("the lake", None)]
    assert private_words.carries(text, words) is carries


def test_with_no_list_nothing_is_refused(attend):
    import private_words
    assert not private_words.carries("Quillon by the lake")
    private_words.refuse("Quillon by the lake")  # raises nothing


def test_the_sentence_never_says_a_word(attend):
    for said in (KEPT_PRIVATE, PROMISE_TOLD, OFFER_TOLD, CONSENT_TOLD):
        assert "Quillon" not in said and "lake" not in said
    assert attend.private_words.KEPT_PRIVATE == KEPT_PRIVATE
    assert (attend.PROMISE_KEPT_PRIVATE, attend.OFFER_KEPT_PRIVATE,
            attend.CONSENT_KEPT_PRIVATE) == (PROMISE_TOLD, OFFER_TOLD, CONSENT_TOLD)


# ---- an offering --------------------------------------------------------------

@pytest.mark.parametrize("kind, text", [("passage", PASSAGE), ("letter", "")])
def test_the_founder_s_offering_with_a_protected_word_is_refused_unsigned(
        founder, lake, kind, text, room):
    a_correspondence(room)
    answer = offer(founder, kind, HIS, text)
    assert answer.status_code == 200
    assert KEPT_PRIVATE in page(answer)
    assert not pending(room) and not placed(room)


def test_an_offering_with_no_protected_word_is_offered_as_before(founder, lake, room):
    a_correspondence(room)
    assert offer(founder, "letter", HERS).status_code == 302
    assert offer(founder, "photo", HIS).status_code == 302
    assert len(pending(room)) == 2


def test_the_first_one_s_offering_is_refused_and_it_is_told_once(wake, packet, commons, lake,
                                                                 room):
    a_correspondence(room)
    wake(block("OFFER", "offer passage %s\n%s" % (HIS, PASSAGE)))
    assert not pending(room) and not placed(room)
    assert not (commons / "offerings.md").exists()
    record = last_record(packet)
    assert record["acted"] == [] and record["kept_private"] == [OFFER_TOLD]
    assert OFFER_TOLD in wake().shown
    assert OFFER_TOLD not in wake().shown


def test_a_consent_to_an_offering_that_carries_a_word_now_listed_places_nothing(
        founder, wake, packet, commons, data_dir, room):
    a_correspondence(room)
    offer(founder, "passage", HIS, PASSAGE)  # offered before the word was on the list
    waiting = only_pending(room)
    write(data_dir / "private-words.txt", LAKE)
    wake(block("OFFER", "consent %s" % waiting["id"]))
    assert only_pending(room) == waiting  # still waiting, with his signature alone
    assert not placed(room) and not (commons / "offerings.md").exists()
    assert last_record(packet)["kept_private"] == [CONSENT_TOLD]
    assert CONSENT_TOLD in wake().shown


def test_the_founder_s_consent_is_refused_the_same_way(founder, wake, data_dir, room):
    a_correspondence(room)
    wake(block("OFFER", "offer passage %s\n%s" % (HIS, PASSAGE)))
    waiting = only_pending(room)
    write(data_dir / "private-words.txt", LAKE)
    answer = post(founder, "/offer/consent", data={"id": waiting["id"]})
    assert KEPT_PRIVATE in page(answer)
    assert only_pending(room) == waiting and not placed(room)


def test_the_module_signs_nothing_it_refuses(attend, lake, room):
    a_correspondence(room)
    with pytest.raises(attend.private_words.Protected):
        attend.offering.offer("founder", "passage", HIS, PASSAGE, "2026-10-20T09-00-00Z",
                              lambda payload: pytest.fail("it was signed"))
    assert not pending(room)


# ---- a witness's line, and its correction -------------------------------------

def test_a_witness_s_line_with_a_protected_word_is_refused_before_the_password(
        birch, data_dir, monkeypatch, lake):
    monkeypatch.setattr(vault, "_derive", lambda *a, **k: pytest.fail("a password was tried"))
    answer = sign(birch, "I saw this bond stand by the lake.")
    assert answer.status_code == 200
    assert KEPT_PRIVATE in page(answer)
    assert kept(data_dir) == []


def test_a_correction_with_a_protected_word_is_refused_and_the_mark_stands(
        birch, data_dir, clock):
    assert taken(sign(birch))
    write(data_dir / "private-words.txt", LAKE)
    clock.shift(days=1)
    answer = sign(birch, "I meant: QUILLON was glad too.", path=CORRECT)
    assert KEPT_PRIVATE in page(answer)
    (mark,) = kept(data_dir)
    assert mark["line"] == LINE
    assert taken(sign(birch, "I meant grateful.", path=CORRECT))  # and one without it is taken
    assert len(kept(data_dir)) == 2


def test_the_witness_module_refuses_it_unsigned(people, bond, data_dir, lake):
    import witness
    with pytest.raises(witness.Refused) as refused:
        witness.add("founder-first", "did:web:example:someone", "someone", "Quillon was here",
                    lambda payload: pytest.fail("it was signed"), "2026-10-20T09-00-00Z")
    assert str(refused.value) == witness.PROTECTED
    assert kept(data_dir) == []


# ---- a promise ------------------------------------------------------------------

def test_a_public_promise_with_a_protected_word_is_not_kept_and_it_is_told_once(
        founder, wake, packet, clock, lake, room):
    it_says_yes(founder, wake, room, clock)
    wake(block("PROMISE", "public\nI will walk with Quillon."))
    assert not writings(room, "promise", "first")
    record = last_record(packet)
    assert "made a promise" not in record["acted"]
    assert record["kept_private"] == [PROMISE_TOLD]
    assert PROMISE_TOLD in wake().shown
    assert PROMISE_TOLD not in wake().shown


def test_a_private_promise_is_never_checked(founder, wake, packet, clock, lake, room):
    it_says_yes(founder, wake, room, clock)
    wake(block("PROMISE", "private\nI will walk with Quillon to the lake."))
    (promise,) = writings(room, "promise", "first")
    assert promise["visibility"] == "private"
    assert promise["text"] == "I will walk with Quillon to the lake."
    assert "kept_private" not in last_record(packet)


def test_a_public_promise_without_one_is_kept_as_before(founder, wake, clock, lake, room):
    it_says_yes(founder, wake, room, clock)
    wake(block("PROMISE", "public\nI will tell you when I do not know."))
    (promise,) = writings(room, "promise", "first")
    assert promise["visibility"] == "public"


def test_the_threshold_signs_no_public_promise_it_refuses(attend, lake, room):
    bond = {"opened_at": "2026-10-01T09-00-00Z"}
    with pytest.raises(attend.private_words.Protected):
        attend.threshold.write("promise", "first", "Quillon", "2026-10-20T09-00-00Z",
                               lambda payload: pytest.fail("it was signed"), bond,
                               visibility="public")
    assert not list(room.glob("bonds/promise-*.json"))
    kept_private = attend.threshold.write("promise", "first", "Quillon", "2026-10-20T09-00-00Z",
                                          lambda payload: "signed", bond, visibility="private")
    assert kept_private["text"] == "Quillon"
    assert json.loads((room / "bonds" / "promise-first-2026-10-20T09-00-00Z.json")
                      .read_text(encoding="utf-8"))["visibility"] == "private"
