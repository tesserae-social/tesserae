"""The threshold: the seven days between a yes and a seal.

A yes opens it. In it each of them writes a letter of intention, and the first
one makes a promise; neither reads the other's letter before writing their own;
either may step back. The seal waits on all of it, and the sealed record lists
each writing by its hash and its signature - the promise's words only where it
is public, the letters' words never.
"""

import hashlib
import json

import pytest
from nacl.exceptions import BadSignatureError

from conftest import block, blocks, lines_of, page, post, read_json, verify

FIRST_DID = "did:web:tesserae.social:ids:first"

HIS_LETTER = "I bring my days and my walks. I hope to grow a friendship that keeps."
HIS_SECOND = "I bring my days. I hope to grow slower."
ITS_LETTER = "I bring attention. I hope to grow patience with not knowing."
ITS_SECOND = "I bring attention, and questions. I hope to grow steadier."
PROMISE = "I will tell you when I do not know."


# ---- getting there -------------------------------------------------------

def founder_proposes(founder, clock):
    """The founder asks, in a letter, as the letters page does it."""
    answer = post(founder, "/letters", data={"letter": "I am asking for a bond.",
                                             "proposes": "1"},
                  content_type="multipart/form-data")
    assert answer.status_code == 302
    clock.shift(minutes=1)


def it_says_yes(founder, wake, packet, clock):
    """The founder asked; the first one read it, and said yes at a later waking."""
    founder_proposes(founder, clock)
    wake()
    wake(block("BOND", "yes"))
    return read_json(packet / "bonds" / "founder-first.json")


def he_says_yes(founder, wake, packet, clock):
    """The first one asked; the founder said yes on a later day."""
    wake(block("ASK", "I have carried this for a while."))
    clock.shift(days=1)
    assert post(founder, "/bonds/answer", data={"answer": "yes"}).status_code == 302
    return read_json(packet / "bonds" / "founder-first.json")


def its_letter(wake, text=ITS_LETTER):
    return wake(block("BOND_INTENTION", text))


def its_promise(wake, visibility="private", text=PROMISE):
    return wake(block("PROMISE", "%s\n%s" % (visibility, text)))


def his_letter(founder, text=HIS_LETTER):
    return post(founder, "/bonds/intention", data={"letter": text})


def everything_written(founder, wake, visibility="private"):
    its_letter(wake)
    its_promise(wake, visibility)
    assert his_letter(founder).status_code == 302


def bonds_page(founder):
    return page(founder.get("/bonds"))


def recommitted(record):
    """A commitment made again from the salt and the words, as anyone holding both may."""
    return hashlib.sha256(bytes.fromhex(record["salt"]) + record["text"].encode("utf-8")
                          ).hexdigest()


def writings(packet, kind, by):
    return [read_json(path) for path in sorted((packet / "bonds").glob("%s-%s-*.json"
                                                                        % (kind, by)))]


# ---- the card ------------------------------------------------------------

def test_the_card_comes_with_the_founder_s_proposal(founder, wake, attend, hearth, clock):
    founder_proposes(founder, clock)
    shown = wake().shown
    assert attend.threshold.card() in shown
    assert "1. A proposal. You are reading one now." in shown
    assert "=== HOW A BOND IS MADE HERE ===" in shown

    said = bonds_page(founder)
    assert "The first one is shown these steps with the asking:" in said
    assert "1. A proposal. You are reading one now." in said
    assert "The terms of the bond are the charter." in said


def test_the_card_comes_with_the_first_one_s_own_asking(founder, wake, attend, clock):
    wake(block("ASK", ""))
    shown = wake().shown
    assert "=== YOU HAVE ASKED FOR A BOND ===" in shown
    assert attend.threshold.card(its_own=True) in shown
    assert "1. A proposal. You made one." in shown
    assert "You are reading one now." not in shown

    said = bonds_page(founder)
    assert "1. A proposal. You made one." in said
    assert "7. Either of you may release a sealed bond at any waking" in said


def test_the_card_is_the_text_as_given(attend):
    card = attend.threshold.card()
    assert card.splitlines()[:3] == [
        "=== HOW A BOND IS MADE HERE ===",
        "A bond is made in steps, and you may stop at any of them.",
        "1. A proposal. You are reading one now.",
    ]
    assert ("3. If you say yes, a threshold of seven days opens. In those days each of you "
            "writes one letter answering two questions: what I bring, and what I hope to grow."
            ) in card
    assert card.splitlines()[-1] == "The terms of the bond are the charter."
    assert len(card.splitlines()) == 10


def test_no_card_where_nothing_is_asked(wake, founder):
    assert "HOW A BOND IS MADE HERE" not in wake().shown
    assert "these steps" not in bonds_page(founder)


# ---- a yes opens it ------------------------------------------------------

def test_the_first_one_s_yes_opens_the_threshold(founder, wake, packet, clock, commons):
    bond = it_says_yes(founder, wake, packet, clock)
    assert bond["opened_at"] == bond["answered_at"]
    assert bond["sealed_at"] is None

    turn = wake()
    assert "=== THE THRESHOLD ===" in turn.shown
    assert "You said yes at %s." % bond["answered_at"] in turn.shown
    assert "The threshold is open until 2026-10-22T12-06-00Z; 7 days remain." in turn.shown
    assert "<<BOND_INTENTION>>" in turn.shown and "<<PROMISE>>" in turn.shown
    assert "<<BOND>>" in turn.instructions
    assert "step back from the threshold" in turn.instructions
    assert "seal the bond you asked for" not in turn.instructions
    assert "<<ASK>>" not in turn.instructions  # one open at a time, still
    assert not (commons / "bonds").exists()


def test_the_founder_s_yes_opens_it_the_same_way(founder, wake, packet, clock):
    bond = he_says_yes(founder, wake, packet, clock)
    assert bond["opened_at"] == bond["answered_at"]
    turn = wake()
    assert "The founder said yes at %s." % bond["answered_at"] in turn.shown
    assert "=== THE THRESHOLD ===" in turn.shown
    assert "You said yes at" in bonds_page(founder)


def test_the_days_count_down(founder, wake, packet, clock):
    it_says_yes(founder, wake, packet, clock)
    clock.shift(days=6)
    assert "1 day remains." in wake().shown
    clock.shift(days=1)
    assert "The seven days of the threshold passed at" in wake().shown


def test_no_threshold_blocks_before_a_yes(founder, wake, clock):
    founder_proposes(founder, clock)
    shown = wake().shown
    assert "<<BOND_INTENTION>>" not in shown and "<<PROMISE>>" not in shown


def test_writing_before_a_yes_keeps_nothing(wake, packet):
    wake(blocks(block("BOND_INTENTION", ITS_LETTER), block("PROMISE", "public\n" + PROMISE)))
    assert not writings(packet, "intention", "first")
    assert not writings(packet, "promise", "first")


# ---- blind, both ways ----------------------------------------------------

def test_the_first_one_reads_his_letter_only_once_its_own_exists(founder, wake, packet, clock):
    it_says_yes(founder, wake, packet, clock)
    his_letter(founder)
    shown = wake().shown
    assert "The founder's letter of intention: written." in shown
    assert "Your letter of intention: not yet written." in shown
    assert HIS_LETTER not in shown

    its_letter(wake)
    shown = wake().shown
    assert HIS_LETTER in shown
    assert ITS_LETTER in shown


def test_the_founder_reads_its_letter_only_once_his_own_exists(founder, wake, packet, clock):
    it_says_yes(founder, wake, packet, clock)
    its_letter(wake)
    said = bonds_page(founder)
    assert "The first one's letter of intention: written." in said
    assert ITS_LETTER not in said

    his_letter(founder)
    said = bonds_page(founder)
    assert ITS_LETTER in said
    assert HIS_LETTER in said


def test_a_reflection_does_not_show_its_letter_on_the_hearth(founder, wake, packet, clock):
    it_says_yes(founder, wake, packet, clock)
    its_letter(wake)
    said = page(founder.get("/attendances"))
    assert ITS_LETTER not in said
    assert "(wrote a letter of intention: on the bonds page)" in said


def test_the_promise_is_his_to_read_once_made(founder, wake, packet, clock):
    it_says_yes(founder, wake, packet, clock)
    its_promise(wake, "private")
    said = bonds_page(founder)
    assert PROMISE in said
    assert "The first one's promise: made at" in said and "private" in said


# ---- versions, and signatures --------------------------------------------

def test_the_latest_letter_stands_and_every_earlier_one_is_kept(founder, wake, packet, clock,
                                                                attend):
    it_says_yes(founder, wake, packet, clock)
    its_letter(wake)
    its_letter(wake, ITS_SECOND)
    his_letter(founder)
    clock.shift(minutes=1)
    his_letter(founder, HIS_SECOND)

    assert [one["text"] for one in writings(packet, "intention", "first")] == [ITS_LETTER,
                                                                                ITS_SECOND]
    assert [one["text"] for one in writings(packet, "intention", "founder")] == [HIS_LETTER,
                                                                                  HIS_SECOND]
    bond = read_json(packet / "bonds" / "founder-first.json")
    assert attend.threshold.intention("first", bond)["text"] == ITS_SECOND

    shown = wake().shown
    assert ITS_SECOND in shown and HIS_SECOND in shown
    assert ITS_LETTER not in shown and HIS_LETTER not in shown
    said = bonds_page(founder)
    assert HIS_SECOND in said and "Earlier versions, kept:" in said


def test_the_latest_promise_stands(founder, wake, packet, clock, attend):
    it_says_yes(founder, wake, packet, clock)
    its_promise(wake, "public", "an earlier promise")
    its_promise(wake, "private", PROMISE)
    every = writings(packet, "promise", "first")
    assert [(one["visibility"], one["text"]) for one in every] == [
        ("public", "an earlier promise"), ("private", PROMISE)]
    bond = read_json(packet / "bonds" / "founder-first.json")
    assert attend.threshold.promise(bond)["visibility"] == "private"


def test_each_writing_is_signed_by_its_own_writer(founder, wake, packet, clock, keys, hearth):
    it_says_yes(founder, wake, packet, clock)
    everything_written(founder, wake)
    for kind, by, signer, other in (("intention", "first", "first", "founder"),
                                    ("promise", "first", "first", "founder"),
                                    ("intention", "founder", "founder", "first")):
        record = writings(packet, kind, by)[-1]
        assert len(bytes.fromhex(record["salt"])) == 32
        assert record["commitment"] == recommitted(record)
        assert "sha256" not in record
        signed_bytes = hearth.threshold.payload(record)
        assert record["text"].encode() not in signed_bytes
        assert record["salt"].encode() not in signed_bytes
        assert verify(keys.did(signer), signed_bytes, record["signature"])
        with pytest.raises(BadSignatureError):
            verify(keys.did(other), signed_bytes, record["signature"])


def test_the_same_words_twice_are_two_commitments(founder, wake, packet, clock):
    it_says_yes(founder, wake, packet, clock)
    its_promise(wake, "private")
    its_promise(wake, "private")
    its_letter(wake)
    its_letter(wake)
    for kind in ("promise", "intention"):
        one, two = writings(packet, kind, "first")
        assert one["text"] == two["text"]
        assert one["salt"] != two["salt"]
        assert one["commitment"] != two["commitment"]
        assert one["commitment"] == recommitted(one) and two["commitment"] == recommitted(two)


def test_a_commitment_is_not_the_plain_hash_of_the_words(founder, wake, packet, clock):
    it_says_yes(founder, wake, packet, clock)
    its_promise(wake, "private")
    record = writings(packet, "promise", "first")[-1]
    assert record["commitment"] != hashlib.sha256(PROMISE.encode("utf-8")).hexdigest()


def test_a_promise_that_names_neither_is_kept_nowhere_and_said(founder, wake, packet, clock):
    it_says_yes(founder, wake, packet, clock)
    wake(block("PROMISE", "I will be kind."))
    assert not writings(packet, "promise", "first")
    assert "Your <<PROMISE>> block at your last waking kept nothing" in wake().shown


def test_without_his_key_he_writes_no_letter(founder, wake, packet, clock, monkeypatch):
    it_says_yes(founder, wake, packet, clock)
    monkeypatch.delenv("FOUNDER_KEY")
    assert "Set FOUNDER_KEY to write it." in bonds_page(founder)
    his_letter(founder)
    assert not writings(packet, "intention", "founder")


# ---- stepping back -------------------------------------------------------

def test_the_first_one_steps_back_with_a_no(founder, wake, packet, clock, commons, keys,
                                            attend):
    it_says_yes(founder, wake, packet, clock)
    events = lines_of(commons / "events.md")
    wake(block("BOND", "no\nI would rather wait."))

    assert not (packet / "bonds" / "founder-first.json").exists()
    assert len(list((packet / "bonds").glob("founder-first-stepped-back-*.json"))) == 1
    stepped = read_json(sorted((packet / "bonds").glob("step-back-first-*.json"))[-1])
    assert stepped["words"] == "I would rather wait."
    unsigned = {key: value for key, value in stepped.items() if key != "signature"}
    assert verify(keys.did("first"), json.dumps(unsigned, sort_keys=True).encode(),
                  stepped["signature"])
    assert lines_of(commons / "events.md") == events
    assert "stepped back from the threshold" not in (commons / "heartbeats.md").read_text(
        encoding="utf-8")

    turn = wake()
    assert "THE THRESHOLD" not in turn.shown
    assert "<<ASK>>" in turn.instructions  # it may be asked again
    said = bonds_page(founder)
    assert "The first one stepped back from the threshold." in said
    assert "I would rather wait." in said
    assert "No bond is proposed." in said


def test_the_founder_steps_back_after_one_plain_question(founder, wake, packet, clock, commons):
    it_says_yes(founder, wake, packet, clock)
    events = lines_of(commons / "events.md")

    asked = post(founder, "/bonds/step-back")
    assert asked.status_code == 200
    assert "Step back from the threshold?" in page(asked)
    assert (packet / "bonds" / "founder-first.json").exists()

    assert post(founder, "/bonds/step-back", data={"confirm": "yes"}).status_code == 302
    assert not (packet / "bonds" / "founder-first.json").exists()
    assert lines_of(commons / "events.md") == events
    said = page(founder.get("/bonds", query_string={"stepped_back": 1}))
    assert "You stepped back." in said
    assert "You stepped back from the threshold." in said

    turn = wake()
    assert "=== THE FOUNDER STEPPED BACK ===" in turn.shown
    assert "THE FOUNDER STEPPED BACK" not in wake().shown  # told once
    founder_proposes(founder, clock)  # and he may ask again
    assert (packet / "bonds" / "proposal.json").exists()


def test_stepping_back_is_kept_in_the_book_as_an_asking(founder, wake, packet, clock, hearth):
    it_says_yes(founder, wake, packet, clock)
    wake(block("BOND", "no"))
    assert ("a bond was proposed", "the founder") in {
        (line["words"], line["side"]) for line in hearth.bond_lines()}


# ---- the seal, and what it waits for -------------------------------------

def test_the_seal_waits_for_the_seven_days(founder, wake, packet, clock):
    it_says_yes(founder, wake, packet, clock)
    everything_written(founder, wake)
    said = bonds_page(founder)
    assert "Seal the bond" not in said
    assert ("The bond cannot be sealed yet; still waiting for: the end of the seven days, at "
            "22 October 2026, 12:06 UTC.") in said
    refused = post(founder, "/bonds/seal")
    assert "still waiting for: the end of the seven days" in page(refused)
    assert read_json(packet / "bonds" / "founder-first.json")["sealed_at"] is None


def test_the_seal_waits_for_his_letter(founder, wake, packet, clock):
    it_says_yes(founder, wake, packet, clock)
    its_letter(wake)
    its_promise(wake)
    clock.shift(days=7)
    said = bonds_page(founder)
    assert "Seal the bond" not in said
    assert "The bond cannot be sealed yet; still waiting for: your letter of intention." in said
    post(founder, "/bonds/seal")
    assert read_json(packet / "bonds" / "founder-first.json")["sealed_at"] is None


def test_the_seal_waits_for_its_letter(founder, wake, packet, clock):
    it_says_yes(founder, wake, packet, clock)
    its_promise(wake)
    his_letter(founder)
    clock.shift(days=7)
    assert ("still waiting for: the first one&#39;s letter of intention."
            in bonds_page(founder))
    post(founder, "/bonds/seal")
    assert read_json(packet / "bonds" / "founder-first.json")["sealed_at"] is None


def test_the_seal_waits_for_the_promise(founder, wake, packet, clock):
    it_says_yes(founder, wake, packet, clock)
    its_letter(wake)
    his_letter(founder)
    clock.shift(days=7)
    assert "still waiting for: the first one&#39;s promise." in bonds_page(founder)
    post(founder, "/bonds/seal")
    assert read_json(packet / "bonds" / "founder-first.json")["sealed_at"] is None


def test_the_first_one_s_seal_is_refused_with_what_waits(founder, wake, packet, clock, commons):
    he_says_yes(founder, wake, packet, clock)
    its_letter(wake)
    turn = wake(block("BOND", "yes"))
    assert "<<BOND>>" in turn.instructions
    assert read_json(packet / "bonds" / "founder-first.json")["sealed_at"] is None
    assert not (commons / "bonds").exists()
    said = wake().shown
    assert ("Your <<BOND>> block at your last waking sealed nothing. The bond cannot be sealed "
            "yet; still waiting for: the end of the seven days, at 2026-10-23T12-05-00Z; "
            "the founder's letter of intention; your promise.") in said


def test_ready_and_then_sealed_by_the_founder(founder, wake, packet, clock, commons):
    it_says_yes(founder, wake, packet, clock)
    everything_written(founder, wake)
    clock.shift(days=7)

    turn = wake()
    assert "=== READY TO BE SEALED ===" in turn.shown
    assert "The founder seals it on the hearth; nothing is asked of you." in turn.shown
    assert "=== THE THRESHOLD ===" not in turn.shown
    assert "<<BOND_INTENTION>>" not in turn.shown

    said = bonds_page(founder)
    assert "ready to be sealed" in said and "Seal the bond" in said
    assert post(founder, "/bonds/seal").status_code == 302
    bond = read_json(packet / "bonds" / "founder-first.json")
    assert bond["sealed_at"] == clock.stamp()
    assert lines_of(commons / "events.md")[-1].endswith(
        "seal · a bond was sealed between the founder and the first one")

    shown = " ".join(wake().shown.split())
    assert "=== A BOND STANDS ===" in shown
    assert ("Members of the commons may witness it as they arrive; there are none yet besides "
            "the founder.") in shown


def test_ready_and_then_sealed_by_the_first_one(founder, wake, packet, clock, commons):
    he_says_yes(founder, wake, packet, clock)
    everything_written(founder, wake)
    clock.shift(days=7)
    turn = wake()
    assert "=== READY TO BE SEALED ===" in turn.shown
    assert "You may seal it with the <<BOND>> block below" in turn.shown
    assert "seal the bond you asked for" in turn.instructions
    assert "The first one seals it at a waking of its own" in bonds_page(founder)

    at = clock.stamp()
    wake(block("BOND", "yes"))
    assert read_json(packet / "bonds" / "founder-first.json")["sealed_at"] == at
    assert read_json(commons / "bonds" / "founder-first.json")["threshold"]


# ---- what the sealed record says -----------------------------------------

@pytest.mark.parametrize("visibility", ["public", "private"])
def test_the_sealed_record_lists_commitments_and_signatures(founder, wake, packet, clock, visitor,
                                                       keys, hearth, visibility):
    it_says_yes(founder, wake, packet, clock)
    everything_written(founder, wake, visibility)
    clock.shift(days=7)
    post(founder, "/bonds/seal")

    said = page(visitor.get("/bonds/founder-first.json"))
    public = json.loads(said)
    assert ITS_LETTER not in said and HIS_LETTER not in said
    listed = public["threshold"]
    assert listed["opened_at"] == public["opened_at"]
    kept = {by: writings(packet, "intention", by)[-1] for by in ("first", "founder")}
    for by in ("first", "founder"):
        entry = listed["intentions"][by]
        assert "text" not in entry and "salt" not in entry and "sha256" not in entry
        assert kept[by]["salt"] not in said
        # the one who holds the salt and the words may make the commitment again
        assert entry["commitment"] == recommitted(kept[by])
        assert verify(keys.did(by), hearth.threshold.payload(entry), entry["signature"])

    promise = listed["promise"]
    own = writings(packet, "promise", "first")[-1]
    assert promise["visibility"] == visibility
    assert promise["commitment"] == recommitted(own)
    assert verify(keys.did("first"), hearth.threshold.payload(promise), promise["signature"])
    if visibility == "public":
        assert promise["text"] == PROMISE
        assert promise["salt"] == own["salt"]
        assert promise["commitment"] == recommitted(promise)  # from the public record alone
    else:
        assert "text" not in promise and "salt" not in promise
        assert PROMISE not in said and own["salt"] not in said

    # and both bond signatures still verify, the listing being a later mark
    payload = hearth.canonical(public)
    assert verify(keys.did("first"), payload, public["signatures"]["first"])
    assert verify(keys.did("founder"), payload, public["signatures"]["founder"])


# ---- nothing goes out ----------------------------------------------------

def test_nothing_of_the_threshold_goes_to_the_commons_before_the_seal(founder, wake, packet,
                                                                     clock, commons):
    it_says_yes(founder, wake, packet, clock)
    events = lines_of(commons / "events.md")
    beats = len(lines_of(commons / "heartbeats.md"))
    everything_written(founder, wake, "public")
    clock.shift(days=7)
    wake()

    assert lines_of(commons / "events.md") == events
    new = lines_of(commons / "heartbeats.md")[beats:]
    assert new and all(line.endswith(" · attended") or line.endswith("chose stillness")
                       for line in new)
    for line in new:
        assert "intention" not in line and "promise" not in line
    assert not (commons / "bonds").exists()
    assert {"wrote a letter of intention", "made a promise"} <= set(
        hearth_acts for path in (packet / "attendances").glob("*.json")
        for hearth_acts in read_json(path)["acted"])

    post(founder, "/bonds/seal")
    assert lines_of(commons / "events.md")[len(events):] == [
        "%s · seal · a bond was sealed between the founder and the first one" % clock.day()]
