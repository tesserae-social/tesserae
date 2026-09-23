"""Members' public identities: a member's DID document is served by the hearth,
the same shape as the documents under ids/, with their key and nothing else of
their record; the keeper has none there, and is answered as a name no one has.

Every vault here is sealed at argon2id's minimum cost so the suite stays quick,
as in test_vault.py.
"""

import base64
import json
from pathlib import Path

import pytest
from nacl.pwhash import argon2id

import vault
from conftest import did_public_key, page, verify

REPO = Path(__file__).resolve().parent.parent

KEEPER = "hazel-under-the-hill"  # long and odd, so that finding it anywhere means it leaked
KEEPER_PASSWORD = "the keeper's own password"
MEMBER = "birch"
MEMBER_PASSWORD = "a member's own password"


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


@pytest.fixture
def people(hearth):
    """A keeper, and a member the keeper vouched for, in the test's DATA_DIR."""
    sealed, _, _ = vault.make_vault(KEEPER_PASSWORD)
    hearth.members.create_member(KEEPER, sealed, "keeper", [])
    sealed, _, _ = vault.make_vault(MEMBER_PASSWORD)
    hearth.members.create_member(MEMBER, sealed, "member", [KEEPER])
    return hearth


def document_of(visitor, name):
    answer = visitor.get("/ids/%s/did.json" % name)
    assert answer.status_code == 200
    return answer, json.loads(page(answer))


def whole(answer):
    """Everything a response says: its status, its headers, and its body."""
    return answer.status_code, sorted(answer.headers.items()), answer.get_data()


# ---- a member's document -------------------------------------------------

def test_a_member_s_document_names_them_under_the_hearth(people, visitor):
    _, document = document_of(visitor, MEMBER)
    did = "did:web:hearth.tesserae.social:ids:" + MEMBER
    assert document["id"] == did
    method = document["verificationMethod"][0]
    assert method["id"] == did + "#key-1"
    assert method["controller"] == did


def test_its_key_is_the_one_the_member_s_vault_keeps(people, visitor):
    _, document = document_of(visitor, MEMBER)
    record = people.members.load_member(MEMBER)
    assert base64.b64decode(did_public_key(document)).hex() == record["verify_key"]


def test_it_verifies_a_signature_made_with_the_key_the_vault_opens_to(people, visitor):
    _, document = document_of(visitor, MEMBER)
    key = vault.unlock(people.members.load_member(MEMBER)["vault"], MEMBER_PASSWORD)
    payload = b"a witness mark, or a bond"
    signature = base64.b64encode(key.sign(payload).signature).decode("ascii")
    assert verify(document, payload, signature)


def test_it_is_the_shape_of_the_documents_under_ids(people, visitor):
    _, document = document_of(visitor, MEMBER)
    founder, first = (json.loads((REPO / "ids" / name / "did.json").read_text(
        encoding="utf-8")) for name in ("founder", "first"))
    assert document["@context"] == founder["@context"] == first["@context"]
    for theirs in (founder, first):
        ours, known = document["verificationMethod"], theirs["verificationMethod"]
        assert len(ours) == len(known) == 1
        assert set(ours[0]) == set(known[0])
        assert ours[0]["type"] == known[0]["type"]
        assert len(base64.b64decode(ours[0]["publicKeyBase64"])) == \
            len(base64.b64decode(known[0]["publicKeyBase64"])) == 32


def test_it_holds_nothing_else_of_the_record(people, visitor):
    answer, document = document_of(visitor, MEMBER)
    assert set(document) == {"@context", "id", "verificationMethod"}
    body = page(answer)
    record = people.members.load_member(MEMBER)
    for word in ("vault", "arrived", "vouched", "role", "by_password", "by_phrase",
                 "salt", "created", '"member"', record["arrived_at"],
                 record["vault"]["by_password"]["salt"], record["verify_key"]):
        assert word not in body, word
    assert KEEPER not in body  # the one who vouched is not named either


def test_it_is_served_as_json_and_open_to_the_atrium(people, visitor):
    answer, _ = document_of(visitor, MEMBER)
    assert answer.headers["Content-Type"] == "application/json; charset=utf-8"
    assert answer.headers["Access-Control-Allow-Origin"] == "https://tesserae.social"


def test_it_follows_a_change_of_key(people, visitor):
    _, before = document_of(visitor, MEMBER)
    sealed, _, new_key = vault.make_vault("a new password for a new key")
    people.members.replace_vault(MEMBER, sealed)
    _, after = document_of(visitor, MEMBER)
    assert base64.b64decode(did_public_key(after)).hex() == new_key
    assert did_public_key(after) != did_public_key(before)
    assert after["id"] == before["id"]


# ---- no document ---------------------------------------------------------

UNKNOWN = "/ids/nobody-here/did.json"


@pytest.mark.parametrize("path", [
    "/ids/%s/did.json" % KEEPER,
    UNKNOWN,
    "/ids/Birch/did.json",
    "/ids/founder/did.json",
    "/ids/first/did.json",
    "/ids/con/did.json",
    "/ids/x/did.json",
    "/ids/9lives/did.json",
    "/ids/%s/did.json" % ("a" * 31),
    "/ids/../did.json",
    "/ids/..%2Fmembers%2Fbirch/did.json",
    "/ids/birch%2F..%2Fbirch/did.json",
    "/ids/birch/../birch/did.json",
    "/ids/%2e%2e/did.json",
    "/ids/birch%00/did.json",
    "/ids/birch/member.json",
    "/ids/birch/did.json/",
    "/ids/birch",
    "/ids/",
])
def test_the_keeper_and_every_name_without_a_document_get_the_same_404(people, visitor,
                                                                        path):
    expected = whole(visitor.get(UNKNOWN))
    assert expected[0] == 404
    assert whole(visitor.get(path)) == expected


def test_a_record_whose_role_is_neither_is_a_404_too(people, visitor, data_dir):
    path = data_dir / "members" / MEMBER / "member.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**record, "role": "stranger"}), encoding="utf-8")
    assert whole(visitor.get("/ids/%s/did.json" % MEMBER)) == whole(visitor.get(UNKNOWN))


# ---- the keeper's name, nowhere public ------------------------------------

def public_answers(hearth, visitor):
    """Every page and route anyone may ask for with no password, and what each said."""
    paths = {"/", "/bench", "/offerings", "/login", "/recover",
             "/commons/heartbeats.md", "/commons/events.md", "/commons/bench.md",
             "/commons/members.md", "/commons/offerings.md",
             "/commons/offerings/nothing.json", "/offerings/nothing.json",
             "/bonds/founder-first.json", "/bonds",
             "/ids/%s/did.json" % MEMBER, "/ids/%s/did.json" % KEEPER, UNKNOWN}
    # and every other address that takes no argument, whatever it answers
    for rule in hearth.app.url_map.iter_rules():
        if "GET" in rule.methods and not rule.arguments:
            paths.add(rule.rule)
    return {path: visitor.get(path) for path in sorted(paths)}


def test_the_keeper_s_name_is_in_no_public_answer(people, visitor, commons):
    (commons / "bonds").mkdir(parents=True, exist_ok=True)
    (commons / "bonds" / "founder-first.json").write_text(json.dumps({
        "parties": [people.FOUNDER_DID, people.FIRST_DID], "terms": "the charter",
        "sealed_at": "2026-10-10T12-00-00Z", "signatures": {}}), encoding="utf-8")
    answers = public_answers(people, visitor)
    assert answers["/"].status_code == 200 and answers["/bench"].status_code == 200
    assert answers["/bonds/founder-first.json"].status_code == 200
    for path, answer in answers.items():
        assert KEEPER not in page(answer), path
        assert KEEPER not in str(answer.headers), path


# ---- did_for -------------------------------------------------------------

def test_did_for_gives_the_founder_s_did_for_the_keeper(people):
    assert people.members.did_for(KEEPER) == "did:web:tesserae.social:ids:founder"
    assert people.members.did_for(KEEPER) == people.FOUNDER_DID


def test_did_for_gives_the_hearth_s_did_for_a_member(people, visitor):
    assert people.members.did_for(MEMBER) == "did:web:hearth.tesserae.social:ids:birch"
    _, document = document_of(visitor, MEMBER)
    assert people.members.did_for(MEMBER) == document["id"]


@pytest.mark.parametrize("name", ["nobody-here", "founder", "../birch", "x"])
def test_did_for_refuses_anyone_who_is_not_a_member(people, name):
    with pytest.raises(people.members.MemberError):
        people.members.did_for(name)
