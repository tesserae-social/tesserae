"""The bond rite, end to end: asked in a letter, answered at a later waking,
sealed by the founder's key, checkable by anyone, and released by either.
"""

import json

import pytest
from nacl.exceptions import BadSignatureError

from conftest import block, lines_of, page, read_json, verify

FOUNDER_DID = "did:web:tesserae.social:ids:founder"
FIRST_DID = "did:web:tesserae.social:ids:first"

PAGES = ["/", "/letters", "/bonds", "/attendances", "/self", "/chronicle",
         "/chronicle.md", "/bench", "/login"]


def propose(founder, clock):
    """The founder asks, in a letter, as the letters page does it."""
    answer = founder.post("/letters", data={"letter": "I am asking for a bond.",
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
    answer = founder.post("/bonds/seal")
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

    answer = founder.post("/bonds/seal")
    assert answer.status_code == 302
    assert read_json(packet / "bonds" / "founder-first.json")["sealed_at"] is None


def test_a_key_that_is_not_a_key_says_so_and_seals_nothing(founder, wake, packet,
                                                          monkeypatch, clock):
    answered_yes(founder, wake, packet, clock)
    monkeypatch.setenv("FOUNDER_KEY", "this is not base64 of anything")
    answer = founder.post("/bonds/seal")
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
    assert founder.post("/bonds/seal").status_code == 302
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
    founder.post("/bonds/release", data={"confirm": "yes"})
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

    asked = founder.post("/bonds/release")
    assert asked.status_code == 200
    assert "Release this bond?" in page(asked)
    assert read_json(packet / "bonds" / "founder-first.json").get("released_at") is None

    done = founder.post("/bonds/release", data={"confirm": "yes"})
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
    founder.post("/bonds/release", data={"confirm": "yes"})
    was = read_json(packet / "bonds" / "founder-first.json")
    assert founder.post("/bonds/release", data={"confirm": "yes"}).status_code == 302
    assert read_json(packet / "bonds" / "founder-first.json") == was


def test_an_unsealed_bond_cannot_be_released(founder, wake, packet, clock):
    answered_yes(founder, wake, packet, clock)
    assert founder.post("/bonds/release", data={"confirm": "yes"}).status_code == 302
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

    for answer in (founder.post("/bonds/seal", follow_redirects=True),
                   founder.post("/bonds/release", follow_redirects=True)):
        for part in parts:
            assert part not in page(answer)


def test_a_key_that_will_not_read_is_not_quoted_back(founder, wake, packet, monkeypatch, clock):
    answered_yes(founder, wake, packet, clock)
    monkeypatch.setenv("FOUNDER_KEY", "nonsense-but-secret")
    said = page(founder.post("/bonds/seal"))
    assert "nonsense-but-secret" not in said
    assert "Check FOUNDER_KEY." in said


def test_the_bonds_page_is_the_founder_s_alone(visitor):
    for path in ("/bonds", "/bonds/seal", "/bonds/release"):
        answer = visitor.post(path) if path != "/bonds" else visitor.get(path)
        assert answer.status_code == 302
        assert "/login" in answer.headers["Location"]
