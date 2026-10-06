"""Witnessing a sealed bond: who may, what a mark is, where the marks are kept
and published, what the bond's page says of them, and the ring a witnessed
bond's tile wears.

Every vault here is sealed at argon2id's minimum cost so the suite stays quick,
as in test_vault.py, and every key is a throwaway.
"""

import base64
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET
import zipfile

import pytest
from nacl.pwhash import argon2id
from nacl.signing import SigningKey

import vault
from conftest import REPO, lines_of, page, post, read_json, verify, write_json

from test_bond_page import FIRST_DID, FOUNDER_DID, a_bond, released

KEEPER_PASSWORD = "the password for the tests and nothing else"  # the founder fixture's own
BIRCH, BIRCH_PASSWORD = "birch", "a member's own password"
CEDAR, CEDAR_PASSWORD = "cedar", "another member's password"
ALDER, ALDER_PASSWORD = "alder", "a third member's password"
WRONG = "not anyone's password at all"

BOND = "founder-first"
PAGE = "/bonds/founder-first"
WITNESS = PAGE + "/witness"
CORRECT = PAGE + "/witness/correction"
MARKS = PAGE + "/witnesses.json"
TILE = PAGE + "/tessera.svg"

LINE = "I saw this bond stand, and I am glad of it."
LATER = "I wrote glad; I meant grateful."

NONE_YET = "No one has witnessed this bond yet."
NOT_THE_PASSWORD = "That is not the password."
NOT_A_LINE = "A witness leaves one line of plain words"
NOT_FROM_HERE = "This form was not sent from the hearth."

FIELDS = {"v", "bond_id", "bond_commitment", "witness_did", "witness_name", "at", "line",
          "signature"}

SVG = "{http://www.w3.org/2000/svg}"
RING = "#6b665f"


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


@pytest.fixture
def bond(hearth):
    """A sealed bond's public record, put where the hearth keeps them."""
    record = a_bond(hearth.threshold)
    write_json(hearth.public_bonds.PUBLIC / (BOND + ".json"), record)
    return record


@pytest.fixture
def people(hearth):
    """Three members, each with a vault of their own."""
    for name, password in ((BIRCH, BIRCH_PASSWORD), (CEDAR, CEDAR_PASSWORD),
                           (ALDER, ALDER_PASSWORD)):
        sealed, _, _ = vault.make_vault(password)
        hearth.members.create_member(name, sealed, "member", [])
    return hearth


def signed_in(hearth, name, password):
    client = hearth.app.test_client()
    answer = post(client, "/login", data={"pseudonym": name, "password": password})
    assert answer.status_code == 302, "the test member did not sign in"
    return client


@pytest.fixture
def birch(people, bond):
    return signed_in(people, BIRCH, BIRCH_PASSWORD)


@pytest.fixture
def cedar(people, bond):
    return signed_in(people, CEDAR, CEDAR_PASSWORD)


def kept(data_dir):
    path = data_dir / "bonds" / "witnesses" / (BOND + ".json")
    return read_json(path) if path.exists() else []


def sign(client, line=LINE, password=BIRCH_PASSWORD, path=WITNESS):
    return post(client, path, data={"line": line, "password": password})


def taken(answer):
    return answer.status_code == 302 and answer.headers["Location"].endswith(PAGE)


def flowing(answer):
    """One page as running text, with its stylesheet and its tags taken out."""
    said = re.sub(r"<style.*?</style>", " ", page(answer), flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", said).split())


def witnessed_by(answer):
    """The 'witnessed by' section of a bond's page, as running text."""
    said = page(answer)
    section = said[said.index("<h2>witnessed by</h2>"):]
    section = section[:section.index("</section>")]
    return " ".join(re.sub(r"<[^>]+>", " ", section).split())


def form_of(said):
    """The form in the 'witnessed by' section of a bond's page."""
    section = said[said.index("<h2>witnessed by</h2>"):]
    return section[section.index("<form"):section.index("</form>")]


def key_of(hearth, name):
    """A member's public key, as base64, read off their record."""
    return base64.b64encode(bytes.fromhex(
        hearth.members.load_member(name)["verify_key"])).decode("ascii")


def signed_bytes(mark):
    """What a witness signs, made here without the module: the mark less its signature."""
    return json.dumps({key: value for key, value in mark.items() if key != "signature"},
                      sort_keys=True).encode("utf-8")


def commitment(record):
    """The bond's fingerprint, made here without the module."""
    body = {key: value for key, value in record.items()
            if key not in ("witnesses", "released_at", "released_by")}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def polygons(answer):
    assert answer.status_code == 200
    root = ET.fromstring(answer.get_data())
    assert {element.tag for element in root.iter()} <= {SVG + "svg", SVG + "polygon"}
    return [(one.get("fill"), one.get("points")) for one in root.iter(SVG + "polygon")]


# ---- a mark ---------------------------------------------------------------

def test_a_member_witnesses_and_the_mark_verifies_against_their_key(birch, people, bond,
                                                                    data_dir, clock, visitor):
    assert taken(sign(birch))
    (mark,) = kept(data_dir)
    assert set(mark) == FIELDS
    assert mark["v"] == 1
    assert mark["bond_id"] == BOND
    assert mark["bond_commitment"] == commitment(bond)
    assert mark["witness_did"] == "did:web:hearth.tesserae.social:ids:" + BIRCH
    assert mark["witness_name"] == BIRCH
    assert mark["at"] == clock.stamp()
    assert mark["line"] == LINE

    assert verify(key_of(people, BIRCH), signed_bytes(mark), mark["signature"])
    # and against the identity document the hearth serves for that witness
    document = json.loads(page(visitor.get("/ids/%s/did.json" % BIRCH)))
    assert document["id"] == mark["witness_did"]
    assert verify(document, signed_bytes(mark), mark["signature"])
    assert people.witness.holds(mark, bytes.fromhex(
        people.members.load_member(BIRCH)["verify_key"]))


def test_a_mark_does_not_verify_against_another_s_key_or_once_changed(birch, people, data_dir):
    sign(birch)
    (mark,) = kept(data_dir)
    other = bytes.fromhex(people.members.load_member(CEDAR)["verify_key"])
    own = bytes.fromhex(people.members.load_member(BIRCH)["verify_key"])
    assert not people.witness.holds(mark, other)
    assert not people.witness.holds(dict(mark, line="Something else."), own)
    assert not people.witness.holds(dict(mark, bond_commitment="0" * 64), own)


def test_the_commitment_leaves_out_witness_data_and_holds_as_witnesses_come(
        birch, cedar, people, bond, data_dir):
    sign(birch)
    sign(cedar, password=CEDAR_PASSWORD)
    first, second = kept(data_dir)
    assert first["bond_commitment"] == second["bond_commitment"] == commitment(bond)
    module = people.witness
    assert module.bond_commitment(dict(bond, witnesses=[first, second])) == commitment(bond)
    assert module.bond_commitment(dict(bond, terms="other terms")) != commitment(bond)


def test_the_key_is_kept_nowhere_once_the_mark_is_signed(birch, people, data_dir):
    before = {path for path in data_dir.rglob("*") if path.is_file()}
    sign(birch)
    after = {path for path in data_dir.rglob("*") if path.is_file()}
    assert after - before == {data_dir / "bonds" / "witnesses" / (BOND + ".json")}
    with birch.session_transaction() as held:
        assert set(held) == {"member", "role", "seal", "csrf_token", "_permanent"}
    seed = vault.unlock(people.members.load_member(BIRCH)["vault"], BIRCH_PASSWORD)
    said = page(birch.get(PAGE)) + page(birch.get(MARKS))
    for secret in (bytes(seed).hex(), base64.b64encode(bytes(seed)).decode(), BIRCH_PASSWORD):
        assert secret not in said


def test_witnessing_writes_no_line_to_the_events(birch, commons):
    before = (commons / "events.md").read_text(encoding="utf-8")
    sign(birch)
    sign(birch, LATER, path=CORRECT)
    assert (commons / "events.md").read_text(encoding="utf-8") == before


def test_nothing_of_witnessing_is_in_the_first_one_s_reading_yet():
    """No agent witness path: attend.py neither reads the marks nor signs any."""
    source = (REPO / "attend.py").read_text(encoding="utf-8")
    assert "import witness" not in source and "witness." not in source


# ---- who may witness ------------------------------------------------------

def test_a_party_is_refused_and_is_shown_no_form(founder, bond, data_dir):
    said = page(founder.get(PAGE))
    assert "Sign as witness" not in said and "<form" not in said.split("witnessed by")[1]
    assert taken(sign(founder, password=KEEPER_PASSWORD))
    assert kept(data_dir) == []
    assert taken(sign(founder, password=KEEPER_PASSWORD, path=CORRECT))
    assert kept(data_dir) == []


def test_a_visitor_sees_no_form_and_leaves_no_mark(visitor, people, bond, data_dir):
    said = page(visitor.get(PAGE))
    assert NONE_YET in said
    for shown in ("Sign as witness", "Sign the correction", 'name="password"', 'name="line"',
                  WITNESS):
        assert shown not in said
    assert taken(sign(visitor))
    assert taken(sign(visitor, path=CORRECT))
    assert kept(data_dir) == []


def test_a_member_whose_record_is_gone_sees_no_form_and_leaves_no_mark(birch, people,
                                                                       data_dir):
    assert "Sign as witness" in page(birch.get(PAGE))
    shutil.rmtree(data_dir / "members" / BIRCH)
    assert "Sign as witness" not in page(birch.get(PAGE))
    assert taken(sign(birch))
    assert kept(data_dir) == []


def test_a_session_naming_no_member_sees_no_form(people, bond, data_dir):
    client = people.app.test_client()
    with client.session_transaction() as held:
        held["member"], held["role"], held["seal"] = "nobody-here", "member", "0" * 16
    assert "Sign as witness" not in page(client.get(PAGE))
    assert taken(sign(client))
    assert kept(data_dir) == []


def test_one_mark_for_each_member(birch, cedar, data_dir):
    assert taken(sign(birch))
    assert taken(sign(birch, "A second line from the same hand."))
    assert [mark["line"] for mark in kept(data_dir)] == [LINE]
    assert taken(sign(cedar, "Seen, and wished well.", CEDAR_PASSWORD))
    assert [mark["witness_name"] for mark in kept(data_dir)] == [BIRCH, CEDAR]


def test_a_bond_that_is_not_there_takes_no_mark(birch, people, data_dir):
    for path in ("/bonds/no-such-bond/witness", "/bonds/no-such-bond/witness/correction"):
        assert post(birch, path, data={"line": LINE,
                                       "password": BIRCH_PASSWORD}).status_code == 404
    assert not (data_dir / "bonds").exists()


def test_an_unsealed_record_takes_no_mark(birch, people, bond, data_dir):
    write_json(people.public_bonds.PUBLIC / (BOND + ".json"), dict(bond, sealed_at=None))
    assert sign(birch).status_code == 404
    assert kept(data_dir) == []


# ---- a correction ---------------------------------------------------------

def test_a_correction_is_allowed_once_and_verifies(birch, people, bond, data_dir, clock):
    sign(birch)
    clock.shift(days=2)
    assert taken(sign(birch, LATER, path=CORRECT))
    mark, correction = kept(data_dir)
    assert set(correction) == FIELDS | {"corrects"}
    assert correction["corrects"] == mark["signature"]
    assert correction["line"] == LATER
    assert correction["at"] == clock.stamp() != mark["at"]
    assert correction["witness_did"] == mark["witness_did"]
    assert correction["bond_commitment"] == commitment(bond)
    assert verify(key_of(people, BIRCH), signed_bytes(correction), correction["signature"])
    # the mark it is beneath stands exactly as it was signed
    assert verify(key_of(people, BIRCH), signed_bytes(mark), mark["signature"])
    assert mark["line"] == LINE

    assert taken(sign(birch, "And a third thought.", path=CORRECT))
    assert kept(data_dir) == [mark, correction]


def test_there_is_nothing_to_correct_before_a_mark(birch, data_dir):
    assert taken(sign(birch, LATER, path=CORRECT))
    assert kept(data_dir) == []


def test_a_correction_is_its_own_witness_s_alone(birch, cedar, data_dir):
    sign(birch)
    assert taken(sign(cedar, LATER, CEDAR_PASSWORD, path=CORRECT))
    assert len(kept(data_dir)) == 1


def test_marks_are_only_ever_added_to(birch, cedar, data_dir):
    sign(birch)
    first = kept(data_dir)
    sign(cedar, "Seen, and wished well.", CEDAR_PASSWORD)
    second = kept(data_dir)
    sign(birch, LATER, path=CORRECT)
    third = kept(data_dir)
    assert second[:1] == first and third[:2] == second and len(third) == 3


# ---- a released bond ------------------------------------------------------

def test_a_released_bond_takes_no_new_marks_and_keeps_its_old_ones(birch, cedar, people, bond,
                                                                   data_dir, visitor):
    sign(birch)
    (mark,) = kept(data_dir)
    gone = released(bond)
    write_json(people.public_bonds.PUBLIC / (BOND + ".json"), gone)

    assert taken(sign(cedar, "Too late to stand by.", CEDAR_PASSWORD))
    assert taken(sign(birch, LATER, path=CORRECT))
    assert kept(data_dir) == [mark]
    for client in (birch, cedar, visitor):
        said = page(client.get(PAGE))
        assert "<form" not in said.split("witnessed by")[1]
        assert LINE in said and NONE_YET not in said
    assert json.loads(page(visitor.get(MARKS))) == [mark]
    # the mark is still a mark on this bond: a release changes nothing a witness saw
    assert mark["bond_commitment"] == people.witness.bond_commitment(gone) == commitment(bond)
    assert verify(key_of(people, BIRCH), signed_bytes(mark), mark["signature"])


# ---- the password ---------------------------------------------------------

def test_a_wrong_password_signs_nothing(birch, data_dir):
    answer = sign(birch, password=WRONG)
    assert answer.status_code == 200
    said = page(answer)
    assert NOT_THE_PASSWORD in said
    assert 'value="%s"' % LINE in said  # the line is kept in the form
    assert WRONG not in said
    assert kept(data_dir) == []


def test_wrong_passwords_are_counted_and_locked_as_at_login(birch, people, data_dir,
                                                            monkeypatch, clock):
    for _ in range(5):
        assert NOT_THE_PASSWORD in page(sign(birch, password=WRONG))
    real = vault._derive

    def refuse(*args, **kwargs):
        raise AssertionError("argon2id was run while the name was shut")

    monkeypatch.setattr(vault, "_derive", refuse)
    assert NOT_THE_PASSWORD in page(sign(birch))  # the right password, and nothing tried
    assert kept(data_dir) == []
    # the same count the login page keeps: the name is shut there too
    door = post(people.app.test_client(), "/login",
                data={"pseudonym": BIRCH, "password": BIRCH_PASSWORD})
    assert door.status_code == 200 and NOT_THE_PASSWORD in page(door)

    clock.shift(minutes=15, seconds=1)
    monkeypatch.setattr(vault, "_derive", real)
    assert taken(sign(birch))
    assert len(kept(data_dir)) == 1


def test_misses_at_the_login_page_and_at_the_form_are_one_count(birch, people, data_dir,
                                                                monkeypatch):
    door = people.app.test_client()
    for _ in range(3):
        post(door, "/login", data={"pseudonym": BIRCH, "password": WRONG})
    for _ in range(2):
        sign(birch, password=WRONG)
    monkeypatch.setattr(vault, "_derive", lambda *a, **k: pytest.fail("tried while shut"))
    assert NOT_THE_PASSWORD in page(sign(birch))
    assert kept(data_dir) == []
    assert ("name", BIRCH) in people.LOGIN_MISSES


def test_a_mark_signed_clears_that_name_s_count(birch, people, cedar):
    for _ in range(4):
        sign(birch, password=WRONG)
    assert taken(sign(birch))
    assert ("name", BIRCH) not in people.LOGIN_MISSES


def test_ten_misses_from_one_address_shut_the_form_too(birch, cedar, people, data_dir,
                                                       monkeypatch):
    for client in (birch, cedar):
        for _ in range(4):
            sign(client, password=WRONG)
    door = people.app.test_client()
    for name in ("nobody-here", "no-one-else"):
        post(door, "/login", data={"pseudonym": name, "password": WRONG})
    monkeypatch.setattr(vault, "_derive", lambda *a, **k: pytest.fail("tried while shut"))
    assert NOT_THE_PASSWORD in page(sign(birch))
    assert kept(data_dir) == []


# ---- the form is the hearth's own -----------------------------------------

@pytest.mark.parametrize("path", [WITNESS, CORRECT])
def test_a_post_without_the_token_is_refused(birch, data_dir, path):
    sign(birch) if path == CORRECT else None
    before = kept(data_dir)
    answer = birch.post(path, data={"line": LINE, "password": BIRCH_PASSWORD})
    assert answer.status_code == 400 and NOT_FROM_HERE in page(answer)
    answer = birch.post(path, data={"line": LINE, "password": BIRCH_PASSWORD,
                                    "csrf_token": "not the token"})
    assert answer.status_code == 400
    assert kept(data_dir) == before


def test_a_post_from_another_origin_is_refused(birch, data_dir):
    answer = post(birch, WITNESS, data={"line": LINE, "password": BIRCH_PASSWORD},
                  headers={"Origin": "https://elsewhere.example"})
    assert answer.status_code == 400
    assert kept(data_dir) == []


def test_the_new_routes_are_guarded_and_not_exempt(hearth):
    posts = {rule.endpoint for rule in hearth.app.url_map.iter_rules()
             if "POST" in (rule.methods or set())}
    assert {"witness_bond", "correct_witness"} <= posts
    assert not {"witness_bond", "correct_witness", "public_witnesses"} & set(hearth.CSRF_EXEMPT)


# ---- the line -------------------------------------------------------------

@pytest.mark.parametrize("line", [
    "See example.com for more.", "http://somewhere", "https://somewhere.org/a",
    "www.somewhere", "write to me at name@place.net", "a" * 201, "", "    ",
])
def test_a_line_shaped_like_a_link_or_too_long_is_refused(birch, data_dir, monkeypatch, line):
    monkeypatch.setattr(vault, "_derive", lambda *a, **k: pytest.fail("a password was tried"))
    for path in (WITNESS,):
        answer = sign(birch, line, path=path)
        assert answer.status_code == 200
        assert NOT_A_LINE in page(answer)
    assert kept(data_dir) == []


def test_a_refused_line_is_not_a_missed_password(birch, people):
    for _ in range(6):
        sign(birch, "see example.com", password=WRONG)
    assert people.LOGIN_MISSES == {}
    assert taken(sign(birch))


def test_a_correction_s_line_is_held_to_the_same_rule(birch, data_dir):
    sign(birch)
    for line in ("see example.com", "b" * 201, ""):
        assert NOT_A_LINE in page(sign(birch, line, path=CORRECT))
    assert len(kept(data_dir)) == 1


def test_a_line_of_exactly_the_limit_is_taken_and_kept_as_one_line(birch, data_dir):
    assert taken(sign(birch, "  two\nlines   of " + "a" * 186 + " "))
    (mark,) = kept(data_dir)
    assert mark["line"] == "two lines of " + "a" * 186
    assert len(mark["line"]) < 200


def test_a_line_is_plain_text_on_the_page(birch, visitor):
    sign(birch, "<b>seen</b> & <script>alert(1)</script>")
    said = page(visitor.get(PAGE))
    assert "&lt;b&gt;seen&lt;/b&gt; &amp; &lt;script&gt;" in said
    assert "<script>alert" not in said


# ---- fellowships ----------------------------------------------------------

SECOND_DID = "did:web:tesserae.social:ids:second"
THIRD_DID = "did:web:tesserae.social:ids:third"
PERSON_DID = "did:web:hearth.tesserae.social:ids:birch"


def signer(key):
    return lambda payload: base64.b64encode(key.sign(payload).signature).decode("ascii")


@pytest.fixture
def fellowship(hearth, monkeypatch):
    """A sealed bond between two agents, and a third agent who might witness it."""
    monkeypatch.setattr(hearth.public_bonds, "AGENTS",
                        frozenset({FIRST_DID, SECOND_DID, THIRD_DID}))
    record = dict(a_bond(hearth.threshold), parties=[FIRST_DID, SECOND_DID])
    write_json(hearth.public_bonds.PUBLIC / "first-second.json", record)
    return hearth.witness


def test_a_fellowship_needs_a_human_witness_before_any_agent(fellowship, clock):
    module = fellowship
    agent, person = SigningKey.generate(), SigningKey.generate()
    assert module.is_fellowship(module.bonds.record("first-second"))

    with pytest.raises(module.Refused) as refused:
        module.add("first-second", THIRD_DID, "third", LINE, signer(agent), clock.stamp())
    assert str(refused.value) == module.HUMAN_FIRST
    assert module.marks("first-second") == []

    mark = module.add("first-second", PERSON_DID, "birch", LINE, signer(person), clock.stamp())
    assert module.holds(mark, bytes(person.verify_key))
    after = module.add("first-second", THIRD_DID, "third", "Seen.", signer(agent),
                       clock.stamp())
    assert module.holds(after, bytes(agent.verify_key))
    assert [one["witness_did"] for one in module.marks("first-second")] == [PERSON_DID,
                                                                            THIRD_DID]


def test_a_human_s_correction_alone_would_not_have_opened_a_fellowship(fellowship, clock):
    """What opens it is a human's mark; an agent's own mark and correction do not."""
    module = fellowship
    bond = module.bonds.record("first-second")
    agent_mark = {"witness_did": THIRD_DID, "signature": "s"}
    assert module.refusal(bond, FOUNDER_DID, [], False) is None
    assert module.refusal(bond, THIRD_DID, [], False) == module.HUMAN_FIRST
    assert module.refusal(bond, FIRST_DID, [agent_mark], False) == module.A_PARTY
    other = "did:web:tesserae.social:ids:fourth"
    module.bonds.AGENTS = module.bonds.AGENTS | {other}
    assert module.refusal(bond, other, [agent_mark], False) == module.HUMAN_FIRST


def test_a_bond_with_a_person_in_it_is_no_fellowship(hearth, bond, fellowship, clock):
    module = fellowship
    assert not module.is_fellowship(bond)
    agent = SigningKey.generate()
    mark = module.add(BOND, THIRD_DID, "third", LINE, signer(agent), clock.stamp())
    assert module.holds(mark, bytes(agent.verify_key))


def test_the_module_refuses_what_the_rule_refuses(hearth, bond, clock):
    module = hearth.witness
    key = SigningKey.generate()
    for did, why in ((FOUNDER_DID, module.A_PARTY), (FIRST_DID, module.A_PARTY)):
        with pytest.raises(module.Refused) as refused:
            module.add(BOND, did, "x", LINE, signer(key), clock.stamp())
        assert str(refused.value) == why
    for line in ("", "two\nlines", "c" * 201, None):
        with pytest.raises(module.Refused) as refused:
            module.add(BOND, PERSON_DID, "birch", line, signer(key), clock.stamp())
        assert str(refused.value) == module.NOT_A_LINE
    with pytest.raises(module.Refused) as refused:
        module.add(BOND, PERSON_DID, "birch", LINE, lambda payload: None, clock.stamp())
    assert str(refused.value) == module.UNSIGNED
    with pytest.raises(module.Refused) as refused:
        module.add("no-such-bond", PERSON_DID, "birch", LINE, signer(key), clock.stamp())
    assert str(refused.value) == module.NOT_SEALED
    assert module.marks(BOND) == []
    assert module.path_for("../founder-first") is None


def test_a_list_that_cannot_be_read_is_never_written_over(hearth, bond, clock, data_dir):
    module = hearth.witness
    path = data_dir / "bonds" / "witnesses" / (BOND + ".json")
    path.parent.mkdir(parents=True)
    path.write_text("not a list of marks", encoding="utf-8")
    with pytest.raises(ValueError):
        module.add(BOND, PERSON_DID, "birch", LINE, signer(SigningKey.generate()),
                   clock.stamp())
    assert path.read_text(encoding="utf-8") == "not a list of marks"


# ---- the marks, published -------------------------------------------------

def test_the_marks_are_public_and_are_the_marks_kept(birch, cedar, visitor, data_dir):
    empty = visitor.get(MARKS)
    assert empty.status_code == 200 and json.loads(page(empty)) == []

    sign(birch)
    sign(cedar, "Seen, and wished well.", CEDAR_PASSWORD)
    sign(birch, LATER, path=CORRECT)
    answer = visitor.get(MARKS)
    assert answer.status_code == 200
    assert json.loads(page(answer)) == kept(data_dir)
    assert len(kept(data_dir)) == 3


def test_the_marks_are_served_as_the_bond_s_record_is(birch, visitor):
    sign(birch)
    marks, record = visitor.get(MARKS), visitor.get(PAGE + ".json")
    for header in ("Content-Type", "Access-Control-Allow-Origin", "Cache-Control"):
        assert marks.headers[header] == record.headers[header], header
    assert marks.headers["Content-Type"] == "application/json; charset=utf-8"
    assert marks.headers["Access-Control-Allow-Origin"] == "*"
    assert marks.headers["Cache-Control"] == "no-cache"


def test_the_bond_s_own_record_carries_no_witness_data(birch, visitor, bond):
    sign(birch)
    assert json.loads(page(visitor.get(PAGE + ".json"))) == bond


@pytest.mark.parametrize("path", ["/bonds/no-such-bond/witnesses.json",
                                  "/bonds/Founder-First/witnesses.json",
                                  "/bonds/founder..first/witnesses.json"])
def test_an_unknown_bond_has_no_marks_to_serve(visitor, bond, path):
    assert visitor.get(path).status_code == 404


def test_an_unsealed_record_has_no_marks_to_serve(visitor, hearth, bond):
    write_json(hearth.public_bonds.PUBLIC / (BOND + ".json"), dict(bond, sealed_at=None))
    assert visitor.get(MARKS).status_code == 404


# ---- the bond's page ------------------------------------------------------

def test_with_no_witness_the_page_says_so(visitor, bond):
    assert witnessed_by(visitor.get(PAGE)) == "witnessed by " + NONE_YET


def test_a_member_who_may_witness_is_shown_the_form(birch):
    said = page(birch.get(PAGE))
    form = form_of(said)
    assert 'action="%s"' % WITNESS in form and 'method="post"' in form
    assert 'name="csrf_token"' in form
    assert 'name="line"' in form and 'maxlength="200"' in form and "required" in form
    assert 'type="password"' in form and 'name="password"' in form
    assert form.index('name="line"') < form.index('name="password"')
    assert ">Sign as witness</button>" in form
    assert NONE_YET in said


def test_each_mark_is_shown_in_order_with_its_day_and_its_line(birch, cedar, visitor, clock):
    sign(birch)
    clock.shift(days=3)
    sign(cedar, "Seen, and wished well.", CEDAR_PASSWORD)
    said = witnessed_by(visitor.get(PAGE))
    assert NONE_YET not in said
    assert said.startswith("witnessed by birch · 15 October 2026 %s "
                           "cedar · 18 October 2026 Seen, and wished well." % LINE)
    assert "a later note" not in said


def test_a_correction_is_shown_beneath_its_mark_dated(birch, cedar, visitor, clock):
    sign(birch)
    sign(cedar, "Seen, and wished well.", CEDAR_PASSWORD)
    clock.shift(days=2)
    sign(birch, LATER, path=CORRECT)
    said = witnessed_by(visitor.get(PAGE))
    assert ("birch · 15 October 2026 %s 17 October 2026 · a later note: %s "
            "cedar · 15 October 2026 Seen, and wished well." % (LINE, LATER)) in said


def test_a_witness_is_offered_one_correction_and_then_nothing(birch, cedar):
    sign(birch)
    said = page(birch.get(PAGE))
    form = form_of(said)
    assert 'action="%s"' % CORRECT in form
    assert "add a correction" in form and ">Sign the correction</button>" in form
    assert "Sign as witness" not in said
    assert 'name="csrf_token"' in form and 'name="password"' in form

    assert "Sign as witness" in page(cedar.get(PAGE))  # another member still may witness

    sign(birch, LATER, path=CORRECT)
    said = page(birch.get(PAGE))
    assert "<form" not in said.split("witnessed by")[1]
    assert "a later note: " + LATER in said


def test_nothing_anywhere_says_how_many(birch, cedar, people, visitor, bond):
    alder = signed_in(people, ALDER, ALDER_PASSWORD)
    counting = re.compile(
        r"\b(\d+|no|one|two|three|four|both|several|many|few|some|all|only|first|second|third"
        r"|another|more|other|others|total|count|number)\s+(of\s+)?(the\s+)?"
        r"(witness|witnesses|witnessed|mark|marks|member|members|people|person)\b", re.I)
    seen = []
    for client, line, password in ((birch, LINE, BIRCH_PASSWORD),
                                   (cedar, "Seen, and wished well.", CEDAR_PASSWORD),
                                   (alder, "I stood by.", ALDER_PASSWORD)):
        sign(client, line, password)
        for reader in (visitor, birch, cedar, alder):
            answer = reader.get(PAGE)
            said = flowing(answer)
            assert not counting.search(said), counting.search(said).group()
            # in the section itself, no figure at all but the days
            section = re.sub(r"\d{1,2} October 2026", "", witnessed_by(answer))
            assert not re.search(r"\d", section.replace("maxlength", "")), section
            seen.append(page(answer))
    # the list is the marks and nothing beside them: no field that counts
    marks = json.loads(page(visitor.get(MARKS)))
    assert isinstance(marks, list) and len(marks) == 3
    assert "<ol" not in seen[-1]
    # and the other places a bond is named say nothing of its witnesses at all
    for path in ("/", "/commons/bonds.md", PAGE + ".json"):
        assert "witness" not in page(visitor.get(path)).lower(), path


# ---- the ring -------------------------------------------------------------

def test_an_unwitnessed_tile_wears_no_ring(visitor, bond):
    assert [fill for fill, _ in polygons(visitor.get(TILE))] == ["#E5906C", "#DDCDB0"]
    assert RING not in page(visitor.get(TILE))


def test_one_witness_puts_a_thin_ring_round_the_tile(birch, visitor):
    before = visitor.get(TILE)
    sign(birch)
    after = visitor.get(TILE, headers={"If-None-Match": before.headers["ETag"]})
    assert after.status_code == 200  # a new picture, under a new tag
    assert after.headers["ETag"] != before.headers["ETag"]
    assert after.headers["Cache-Control"] == "public, max-age=3600"  # seen within the hour
    drawn = polygons(after)
    assert [fill for fill, _ in drawn] == ["#E5906C", "#DDCDB0", RING]
    assert drawn[:2] == polygons(before)  # the tile itself is as it was
    assert drawn[2][1] == "0,0 240,0 240,240 0,240 0,0 3,3 3,237 237,237 237,3 3,3"


def test_the_ring_is_the_same_with_many_witnesses(birch, cedar, people, visitor):
    sign(birch)
    one = {size: visitor.get(TILE, query_string={"size": size}).get_data()
           for size in people.TESSERA_SIZES}
    tag = visitor.get(TILE).headers["ETag"]
    sign(cedar, "Seen, and wished well.", CEDAR_PASSWORD)
    sign(signed_in(people, ALDER, ALDER_PASSWORD), "I stood by.", ALDER_PASSWORD)
    sign(birch, LATER, path=CORRECT)
    for size in people.TESSERA_SIZES:
        assert visitor.get(TILE, query_string={"size": size}).get_data() == one[size], size
    assert visitor.get(TILE, headers={"If-None-Match": tag}).status_code == 304


def test_the_ring_is_on_every_size_the_mosaic_draws(birch, people, visitor):
    sign(birch)
    for size in people.TESSERA_SIZES:
        drawn = polygons(visitor.get(TILE, query_string={"size": size}))
        assert [fill for fill, _ in drawn] == ["#E5906C", "#DDCDB0", RING], size


def test_a_released_bond_keeps_its_ring_with_its_halves_apart(birch, people, bond, visitor):
    sign(birch)
    write_json(people.public_bonds.PUBLIC / (BOND + ".json"), released(bond))
    for size in people.TESSERA_SIZES:
        answer = visitor.get(TILE, query_string={"size": size})
        root = ET.fromstring(answer.get_data())
        assert float(root.get("width")) == pytest.approx(size * 1.2)
        assert [fill for fill, _ in polygons(answer)] == ["#E5906C", "#DDCDB0", RING], size
    drawn = polygons(visitor.get(TILE))
    assert drawn[2][1] == "0,0 288,0 288,240 0,240 0,0 3,3 3,237 285,237 285,3 3,3"


def test_a_released_bond_never_witnessed_wears_no_ring(people, bond, visitor):
    write_json(people.public_bonds.PUBLIC / (BOND + ".json"), released(bond))
    assert [fill for fill, _ in polygons(visitor.get(TILE))] == ["#E5906C", "#DDCDB0"]


def test_a_half_beside_a_name_wears_no_ring(birch, visitor):
    sign(birch)
    for party, colour in (("the-first-one", "#E5906C"), ("the-founder", "#DDCDB0")):
        drawn = polygons(visitor.get(PAGE + "/half/%s.svg" % party))
        assert [fill for fill, _ in drawn] == [colour]


def test_the_page_s_tile_is_the_ringed_one(birch, visitor):
    sign(birch)
    said = page(visitor.get(PAGE))
    assert '<img class="tessera" src="%s?size=240"' % TILE in said
    assert RING in page(visitor.get(TILE + "?size=240"))


# ---- kept, mirrored, written down -----------------------------------------

def test_a_copy_and_a_backup_both_hold_the_marks(birch, founder, hearth, data_dir):
    sign(birch)
    name = "bonds/witnesses/%s.json" % BOND
    written = (data_dir / name).read_bytes()

    answer = post(founder, "/export")
    assert answer.status_code == 200
    with zipfile.ZipFile(io.BytesIO(answer.get_data())) as bundle:
        assert bundle.read(name) == written
        assert not any(inside.startswith("members/") for inside in bundle.namelist())

    with tarfile.open(fileobj=io.BytesIO(hearth.backup_archive()), mode="r:gz") as bundle:
        assert bundle.extractfile(name).read() == written
        assert any(inside.startswith("members/") for inside in bundle.getnames())


def test_the_mirror_takes_down_the_marks_beside_each_bond():
    workflow = (REPO / ".github" / "workflows" / "mirror.yml").read_text(encoding="utf-8")
    lines = [line.strip() for line in workflow.splitlines()]
    for record, marks in (('fetch "/bonds/$id.json" || true',
                           'fetch "/bonds/$id/witnesses.json" || true'),
                          ("fetch /bonds/founder-first.json || true",
                           "fetch /bonds/founder-first/witnesses.json || true")):
        assert lines.count(record) == lines.count(marks) == 1
        assert lines[lines.index(record) + 1] == marks


def test_the_rites_say_how_a_bond_is_witnessed_and_the_page_is_current():
    done = subprocess.run([sys.executable, str(REPO / "build_docs.py"), "--check"],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr

    rites = (REPO / "rites.html").read_text(encoding="utf-8")
    assert (rites.index("<h2>Sealing</h2>") < rites.index("<h2>Witnessing</h2>")
            < rites.index("<h2>The tessera</h2>"))
    section = rites[rites.index("<h2>Witnessing</h2>"):rites.index("<h2>The tessera</h2>")]
    for said in ("Any member who is not a party to the bond.",
                 "witnessed by a person before any agent may sign",
                 "one line of plain words",
                 "signed with the witness's own key",
                 "A mark is never edited and never removed.",
                 "one later note beneath their mark",
                 "nowhere says how many",
                 "wears a thin ring",
                 "the same ring whether one has witnessed or many",
                 "A released bond keeps its witnesses, and gathers no new ones."):
        assert said in section, said
