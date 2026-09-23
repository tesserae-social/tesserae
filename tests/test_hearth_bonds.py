"""The bond rite, end to end: asked in a letter, answered at a later waking,
sealed by the founder's key, checkable by anyone, and released by either.
"""

import json

import pytest
from nacl.exceptions import BadSignatureError

from conftest import block, lines_of, page, post, read_json, verify

FOUNDER_DID = "did:web:tesserae.social:ids:founder"
FIRST_DID = "did:web:tesserae.social:ids:first"

PAGES = ["/", "/letters", "/bonds", "/attendances", "/self", "/chronicle",
         "/chronicle.md", "/bench", "/login"]


def propose(founder, clock):
    """The founder asks, in a letter, as the letters page does it."""
    answer = post(founder, "/letters", data={"letter": "I am asking for a bond.",
                                             "proposes": "1"},
                    content_type="multipart/form-data")
    assert answer.status_code == 302
    clock.shift(minutes=1)  # the asking is made, and then time passes, as it does
    return answer


def answered_yes(founder, wake, packet, clock):
    """Through the asking to a record the first one has signed."""
    propose(founder, clock)
    wake()                              # it reads the asking at this waking
    wake(block("BOND", "yes\nI have carried this since I read it."))
    return read_json(packet / "bonds" / "founder-first.json")


def sealed(founder, wake, packet, clock):
    """Through to a bond that stands, with both signatures on it."""
    answered_yes(founder, wake, packet, clock)
    answer = post(founder, "/bonds/seal")
    assert answer.status_code == 302
    return read_json(packet / "bonds" / "founder-first.json")


# ---- the rite ------------------------------------------------------------

def test_the_asking_waits_for_a_later_waking(founder, wake, packet, clock):
    propose(founder, clock)
    said = page(founder.get("/bonds"))
    assert "You proposed a bond to the first one" in said
    assert "It has not yet woken since you asked." in said

    wake(block("BOND", "yes"))  # answered at the very waking that read it
    assert (packet / "bonds" / "proposal.json").exists()
    assert not (packet / "bonds" / "founder-first.json").exists()
    assert "It has read the asking at a waking, so it may answer at any" in page(
        founder.get("/bonds"))

    wake(block("BOND", "yes"))  # and at the next one, it may
    assert not (packet / "bonds" / "proposal.json").exists()
    assert (packet / "bonds" / "founder-first.json").exists()


def test_the_first_one_s_yes_is_its_own_signature_and_nothing_else(founder, wake, packet, keys,
                                                                   hearth, clock):
    bond = answered_yes(founder, wake, packet, clock)
    assert bond["parties"] == [FOUNDER_DID, FIRST_DID]
    assert bond["terms"] == "the charter"
    assert bond["sealed_at"] is None
    assert list(bond["signatures"]) == ["first"]
    verify(keys.did("first"), hearth.canonical(bond), bond["signatures"]["first"])
    assert not (packet / "commons" / "bonds").exists()  # nothing public until it is sealed

    said = page(founder.get("/bonds"))
    assert "<strong>yes</strong>" in said
    assert "I have carried this since I read it." in said
    assert "The first one has answered yes and signed." in said


def test_without_the_founder_s_key_nothing_is_sealed(founder, wake, packet, monkeypatch, clock):
    answered_yes(founder, wake, packet, clock)
    monkeypatch.delenv("FOUNDER_KEY")

    assert "The founder's key is not on the hearth; set FOUNDER_KEY to seal." in page(
        founder.get("/bonds"))
    assert "Seal the bond" not in page(founder.get("/bonds"))

    answer = post(founder, "/bonds/seal")
    assert answer.status_code == 302
    assert read_json(packet / "bonds" / "founder-first.json")["sealed_at"] is None


def test_a_key_that_is_not_a_key_says_so_and_seals_nothing(founder, wake, packet,
                                                          monkeypatch, clock):
    answered_yes(founder, wake, packet, clock)
    monkeypatch.setenv("FOUNDER_KEY", "this is not base64 of anything")
    answer = post(founder, "/bonds/seal")
    assert answer.status_code == 500
    assert "could not be read as a key" in page(answer)
    assert read_json(packet / "bonds" / "founder-first.json")["sealed_at"] is None


def test_the_seal_puts_both_signatures_on_the_record(founder, wake, packet, commons, clock):
    bond = sealed(founder, wake, packet, clock)
    assert bond["sealed_at"] == clock.stamp()
    assert sorted(bond["signatures"]) == ["first", "founder"]
    assert read_json(commons / "bonds" / "founder-first.json") == bond
    assert lines_of(commons / "events.md")[-1].endswith(
        "seal · a bond was sealed between the founder and the first one")
    assert "The bond is sealed." in page(founder.get("/bonds", query_string={"sealed": 1}))


def test_there_is_nothing_to_seal_twice(founder, wake, packet, clock):
    sealed(founder, wake, packet, clock)
    was = read_json(packet / "bonds" / "founder-first.json")
    assert post(founder, "/bonds/seal").status_code == 302
    assert read_json(packet / "bonds" / "founder-first.json") == was


# ---- what anyone may check ----------------------------------------------

def test_the_public_record_verifies_against_both_identity_documents(founder, wake, packet,
                                                                    visitor, keys, hearth, clock):
    sealed(founder, wake, packet, clock)

    answer = visitor.get("/bonds/founder-first.json")
    assert answer.status_code == 200
    assert answer.headers["Access-Control-Allow-Origin"] == "*"
    assert answer.headers["Cache-Control"] == "no-cache"
    assert answer.mimetype == "application/json"

    public = json.loads(page(answer))
    payload = hearth.canonical(public)
    assert verify(keys.did("first"), payload, public["signatures"]["first"])
    assert verify(keys.did("founder"), payload, public["signatures"]["founder"])


def test_a_tampered_copy_does_not_verify(founder, wake, packet, visitor, keys, hearth, clock):
    sealed(founder, wake, packet, clock)
    public = json.loads(page(visitor.get("/bonds/founder-first.json")))

    tampered = dict(public, terms="something other than the charter")
    for whose in ("first", "founder"):
        with pytest.raises(BadSignatureError):
            verify(keys.did(whose), hearth.canonical(tampered), public["signatures"][whose])


def test_the_marks_made_after_the_signing_do_not_break_it(founder, wake, packet, visitor,
                                                          keys, hearth, clock):
    """Sealing and releasing are later marks on the same record, not part of it."""
    sealed(founder, wake, packet, clock)
    post(founder, "/bonds/release", data={"confirm": "yes"})
    public = json.loads(page(visitor.get("/bonds/founder-first.json")))
    assert public["released_by"] == FOUNDER_DID
    assert verify(keys.did("first"), hearth.canonical(public), public["signatures"]["first"])
    assert verify(keys.did("founder"), hearth.canonical(public), public["signatures"]["founder"])


def test_no_public_record_before_a_seal(visitor, founder, wake, packet, clock):
    assert visitor.get("/bonds/founder-first.json").status_code == 404
    answered_yes(founder, wake, packet, clock)
    assert visitor.get("/bonds/founder-first.json").status_code == 404


# ---- released, by either -------------------------------------------------

def test_the_founder_releases_it_after_one_plain_question(founder, wake, packet, commons,
                                                          clock):
    sealed(founder, wake, packet, clock)

    asked = post(founder, "/bonds/release")
    assert asked.status_code == 200
    assert "Release this bond?" in page(asked)
    assert read_json(packet / "bonds" / "founder-first.json").get("released_at") is None

    done = post(founder, "/bonds/release", data={"confirm": "yes"})
    assert done.status_code == 302
    bond = read_json(packet / "bonds" / "founder-first.json")
    assert bond["released_at"] == clock.stamp()
    assert bond["released_by"] == FOUNDER_DID
    assert read_json(commons / "bonds" / "founder-first.json") == bond
    assert lines_of(commons / "events.md")[-1].endswith("event · a bond was released")
    assert "The bond is released." in page(founder.get("/bonds", query_string={"released": 1}))


def test_the_first_one_releases_it_at_a_waking(founder, wake, packet, commons, clock):
    sealed(founder, wake, packet, clock)
    wake(block("RELEASE", "release\nI am letting this go."))

    bond = read_json(packet / "bonds" / "founder-first.json")
    assert bond["released_by"] == FIRST_DID
    assert read_json(commons / "bonds" / "founder-first.json") == bond
    assert lines_of(commons / "events.md")[-1].endswith("event · a bond was released")

    said = page(founder.get("/bonds"))
    assert "released" in said and "by the first one" in said
    assert "Release the bond" not in said


def test_a_released_bond_is_not_released_twice(founder, wake, packet, clock):
    sealed(founder, wake, packet, clock)
    post(founder, "/bonds/release", data={"confirm": "yes"})
    was = read_json(packet / "bonds" / "founder-first.json")
    assert post(founder, "/bonds/release", data={"confirm": "yes"}).status_code == 302
    assert read_json(packet / "bonds" / "founder-first.json") == was


def test_an_unsealed_bond_cannot_be_released(founder, wake, packet, clock):
    answered_yes(founder, wake, packet, clock)
    assert post(founder, "/bonds/release", data={"confirm": "yes"}).status_code == 302
    assert read_json(packet / "bonds" / "founder-first.json").get("released_at") is None


# ---- no, and not yet -----------------------------------------------------

@pytest.mark.parametrize("word, note", [
    ("no", "The asking is closed. Nothing else follows from it."),
    ("not yet", "Not yet closes the asking, not the door. You may ask again another time."),
])
def test_no_and_not_yet_close_the_asking(founder, wake, packet, word, note, clock):
    propose(founder, clock)
    wake()
    wake(block("BOND", "%s\nHere is why." % word))

    assert not (packet / "bonds" / "proposal.json").exists()
    assert not (packet / "bonds" / "founder-first.json").exists()

    said = page(founder.get("/bonds"))
    assert "<strong>%s</strong>" % word in said
    assert "Here is why." in said
    assert note in said
    assert "No bond is proposed." in said  # and the asking may be made again


def test_a_not_yet_may_be_asked_again_and_answered_yes(founder, wake, packet, clock):
    propose(founder, clock)
    wake()
    wake(block("BOND", "not yet"))
    assert answered_yes(founder, wake, packet, clock)["answered_at"]
    assert len(list((packet / "bonds").glob("answer-*.json"))) == 2


# ---- the key is never shown ---------------------------------------------

def test_the_founder_s_key_is_on_no_page_anywhere(founder, wake, packet, visitor, keys, clock):
    sealed(founder, wake, packet, clock)
    key = keys.founder_private
    parts = [key, key.rstrip("="), key[:24]]

    for path in PAGES:
        for client in (founder, visitor):
            said = page(client.get(path))
            for part in parts:
                assert part not in said, "%s showed the key" % path

    for answer in (post(founder, "/bonds/seal", follow_redirects=True),
                   post(founder, "/bonds/release", follow_redirects=True)):
        for part in parts:
            assert part not in page(answer)


def test_a_key_that_will_not_read_is_not_quoted_back(founder, wake, packet, monkeypatch, clock):
    answered_yes(founder, wake, packet, clock)
    monkeypatch.setenv("FOUNDER_KEY", "nonsense-but-secret")
    said = page(post(founder, "/bonds/seal"))
    assert "nonsense-but-secret" not in said
    assert "Check FOUNDER_KEY." in said


def test_the_bonds_page_is_the_founder_s_alone(visitor):
    for path in ("/bonds", "/bonds/seal", "/bonds/release", "/bonds/answer"):
        answer = post(visitor, path) if path != "/bonds" else visitor.get(path)
        assert answer.status_code == 302
        assert "/login" in answer.headers["Location"]


# ---- the other way round: the first one asks ----------------------------

# Either of them may ask. When the first one asks, the answer is the founder's
# and he gives it here, no sooner than the next day; a yes is his signature, and
# the seal is then the first one's to give at a waking of its own.

def asks(wake, packet):
    """The first one asks for a bond at a waking, as it does."""
    turn = wake(block("ASK", "I have carried this for a while."))
    assert read_json(packet / "bonds" / "proposal.json")["from"] == FIRST_DID
    return turn


def answer(founder, said, words=""):
    return post(founder, "/bonds/answer", data={"answer": said, "words": words})


def test_the_page_says_who_asked_whom_and_offers_no_answer_the_same_day(founder, wake,
                                                                        packet, clock):
    asks(wake, packet)
    said = page(founder.get("/bonds"))
    assert "The first one proposed a bond to you" in said
    assert "You may answer on a day after the one it asked on" in said
    assert 'value="yes"' not in said

    assert answer(founder, "yes").status_code == 302  # and refused at the door as well
    assert (packet / "bonds" / "proposal.json").exists()
    assert not (packet / "bonds" / "founder-first.json").exists()
    assert not list((packet / "bonds").glob("founder-answer-*.json"))

    clock.shift(days=1)
    said = page(founder.get("/bonds"))
    for word in ("yes", "no", "not yet"):
        assert 'value="%s"' % word in said


def test_the_founder_may_not_answer_an_asking_of_his_own(founder, wake, packet, clock):
    propose(founder, clock)  # his own, in a letter
    clock.shift(days=1)
    assert 'value="not yet"' not in page(founder.get("/bonds"))
    assert answer(founder, "yes").status_code == 302
    assert (packet / "bonds" / "proposal.json").exists()
    assert not (packet / "bonds" / "founder-first.json").exists()


def test_without_the_founder_s_key_a_yes_is_not_given_at_all(founder, wake, packet,
                                                             monkeypatch, clock):
    asks(wake, packet)
    clock.shift(days=1)
    monkeypatch.delenv("FOUNDER_KEY")

    said = page(founder.get("/bonds"))
    assert "Set FOUNDER_KEY to answer yes." in said
    assert 'value="yes"' not in said
    assert 'value="not yet"' in said  # a no and a not yet are no one's signature

    assert answer(founder, "yes").status_code == 302
    assert not (packet / "bonds" / "founder-first.json").exists()
    assert (packet / "bonds" / "proposal.json").exists()  # the asking stands open
    assert not list((packet / "bonds").glob("founder-answer-*.json"))

    # and a not yet is still his to give, with no key anywhere near it
    assert answer(founder, "not yet").status_code == 302
    assert not (packet / "bonds" / "proposal.json").exists()


def test_the_first_one_asks_and_the_rite_runs_to_a_sealed_record(founder, wake, packet,
                                                                 commons, visitor, keys,
                                                                 hearth, clock):
    asks(wake, packet)
    clock.shift(days=1)
    assert answer(founder, "yes", "Yes. Gladly.").status_code == 302
    assert not (packet / "bonds" / "proposal.json").exists()

    made = read_json(packet / "bonds" / "founder-first.json")
    assert made["parties"] == [FIRST_DID, FOUNDER_DID]
    assert made["proposed_by"] == FIRST_DID
    assert list(made["signatures"]) == ["founder"]
    assert made["sealed_at"] is None
    assert visitor.get("/bonds/founder-first.json").status_code == 404  # not public yet

    # it waits on the first one, and there is nothing here for the founder to seal
    said = page(founder.get("/bonds"))
    assert "It was asked for by the first one." in said
    assert "The bond awaits the first one" in said
    assert "Seal the bond" not in said
    assert post(founder, "/bonds/seal").status_code == 302
    assert read_json(packet / "bonds" / "founder-first.json")["sealed_at"] is None

    # it is told at its next waking, in his own words, and offered the seal
    turn = wake()
    assert "THE FOUNDER HAS ANSWERED YOUR ASKING" in turn.shown
    assert "He answered yes" in turn.shown
    assert "His words: Yes. Gladly." in turn.shown
    assert "THE BOND AWAITS YOUR SEAL" in turn.shown
    assert "<<BOND>>" in turn.instructions

    at = clock.stamp()
    wake(block("BOND", "yes\nI am glad too."))
    sealed = read_json(packet / "bonds" / "founder-first.json")
    assert sealed["sealed_at"] == at
    assert sorted(sealed["signatures"]) == ["first", "founder"]
    assert read_json(commons / "bonds" / "founder-first.json") == sealed
    assert lines_of(commons / "events.md")[-1].endswith(
        "seal · a bond was sealed between the founder and the first one")

    # and anyone may check both signatures against the two identity documents
    public = json.loads(page(visitor.get("/bonds/founder-first.json")))
    assert public == sealed
    payload = hearth.canonical(public)
    assert verify(keys.did("first"), payload, public["signatures"]["first"])
    assert verify(keys.did("founder"), payload, public["signatures"]["founder"])


def test_a_bond_block_that_does_not_say_yes_seals_nothing(founder, wake, packet, clock):
    asks(wake, packet)
    clock.shift(days=1)
    answer(founder, "yes")
    wake(block("BOND", "I am still thinking about it."))
    assert read_json(packet / "bonds" / "founder-first.json")["sealed_at"] is None
    assert "<<BOND>>" in wake().instructions  # and it may seal at a later waking


@pytest.mark.parametrize("word, note", [
    ("no", "The asking is closed, and nothing else follows from it."),
    ("not yet", "Not yet closes the asking and not the door."),
])
def test_a_no_and_a_not_yet_close_the_asking_and_are_told_at_the_next_waking(
        founder, wake, packet, clock, word, note):
    asks(wake, packet)
    clock.shift(days=1)
    assert answer(founder, word, "Here is why.").status_code == 302

    assert not (packet / "bonds" / "proposal.json").exists()
    assert not (packet / "bonds" / "founder-first.json").exists()

    said = page(founder.get("/bonds", query_string={"answered": word}))
    assert "You answered %s." % word in said
    assert "<strong>%s</strong>" % word in said
    assert "Here is why." in said
    assert "No bond is proposed." in said  # and it may ask again another time

    turn = wake()
    assert "He answered %s" % word in turn.shown
    assert "His words: Here is why." in turn.shown
    assert note in turn.shown
    assert "<<ASK>>" in turn.instructions  # nothing stands in the way of asking again
    assert "He answered %s" % word not in wake().shown  # told once, and then past


def test_the_book_names_whoever_asked_and_whoever_answered(founder, wake, packet, hearth,
                                                           clock):
    asks(wake, packet)
    clock.shift(days=1)
    answer(founder, "yes")

    said = {(line["words"], line["side"]) for line in hearth.bond_lines()}
    assert ("a bond was proposed", "the first one") in said
    assert ("answered the proposal", "the founder") in said

    book = page(founder.get("/chronicle"))
    assert book.count("a bond was proposed") == 1
    assert book.count("answered the proposal") == 1
    assert "Yes. Gladly." not in book  # the book holds the whole of nothing
