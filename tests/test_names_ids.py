"""Ids, names and sign-in (names-design.md; the founder's request of 20 November 2026).

Each person has an id (their folder, never a name), a commons name (shown), and a sign-in
(an email address or a private sign-in name, never shown). Everything is stored by id, and a
name is drawn from it at the moment it is shown.
"""

import json
import re

import pytest

from conftest import load

SIGN_IN = "zebrasignin"
ADDRESS = "zebra@example.test"


@pytest.fixture
def store(env, founder_vault):
    module = load("members")
    return module


def a_vault(store, n=0):
    import vault
    sealed, _, _ = vault.make_vault("a password for the tests %d and nothing else" % n)
    return sealed


def test_a_new_id_is_random_and_names_no_one(store):
    made = {store.new_id() for _ in range(50)}
    assert len(made) == 50
    for one in made:
        assert re.fullmatch(r"p-[23456789abcdefghjkmnpqrstuvwxyz]{8}", one)
        store.validate_pseudonym(one)  # a folder may be made of it


def test_a_member_joining_since_ids_has_an_id_a_name_and_a_sign_in(store):
    member_id = store.new_id()
    record = store.create_member(member_id, a_vault(store), "member", [], name="willow",
                                 sign_in=SIGN_IN)
    assert record["id"] == member_id and record["name"] == "willow"
    assert record["sign_in"] == SIGN_IN
    assert store.id_of_sign_in(SIGN_IN) == member_id
    assert store.id_of_sign_in(member_id) is None  # an id is no sign-in
    assert store.id_of_sign_in("willow") is None  # nor is a commons name
    assert store.name_of(member_id) == "willow"
    assert store.id_of("willow") == member_id
    assert store.did_for(member_id).endswith(":ids:" + member_id)  # never a name in a DID


def test_sign_in_by_email(store):
    member_id = store.new_id()
    store.create_member(member_id, a_vault(store), "member", [], name="willow",
                        sign_in=ADDRESS.upper())
    assert store.id_of_sign_in(ADDRESS) == member_id
    assert store.sign_in_of(member_id) == ADDRESS


def test_a_sign_in_is_one_person_s(store):
    store.create_member(store.new_id(), a_vault(store, 1), "member", [], name="willow",
                        sign_in=SIGN_IN)
    with pytest.raises(store.MemberError):
        store.create_member(store.new_id(), a_vault(store, 2), "member", [], name="aspen",
                            sign_in=SIGN_IN)


def test_a_member_from_before_ids_is_their_id_until_they_set_a_sign_in(store):
    store.create_member("alder", a_vault(store), "member", [])
    assert store.id_of_sign_in("alder") == "alder"
    assert store.name_of("alder") == "alder" and store.id_of("alder") == "alder"
    store.set_sign_in("alder", SIGN_IN)
    assert store.id_of_sign_in("alder") is None  # their id no longer signs them in
    assert store.id_of_sign_in(SIGN_IN) == "alder"


def test_a_name_held_once_is_never_anyone_else_s(store):
    first = store.new_id()
    store.create_member(first, a_vault(store, 1), "member", [], name="willow")
    store.set_name(first, "birch")
    assert store.name_of(first) == "birch"
    assert store.id_of("willow") is None  # an old name names no one now
    with pytest.raises(store.MemberError):
        store.create_member(store.new_id(), a_vault(store, 2), "member", [], name="willow")
    record = store.load_member(first)
    assert [one["name"] for one in record["names"]] == ["willow", "birch"]


def test_a_commons_name_is_no_one_s_id(store):
    store.create_member("alder", a_vault(store, 1), "member", [])
    with pytest.raises(store.MemberError):
        store.create_member(store.new_id(), a_vault(store, 2), "member", [], name="alder")


def test_the_keeper_is_the_founder_by_name_and_may_have_founder_as_their_folder(store):
    store.create_member("founder", a_vault(store), "keeper", [], sign_in=SIGN_IN)
    assert "founder" in store.list_members()
    assert store.name_of("founder") == "the founder"
    assert store.id_of("the founder") == "founder" and store.id_of("founder") == "founder"
    assert store.id_of_sign_in(SIGN_IN) == "founder"
    assert store.id_of_sign_in("founder") is None


def test_no_member_but_the_keeper_has_founder_for_an_id(store):
    with pytest.raises(store.MemberError):
        store.create_member("founder", a_vault(store), "member", [])
    with pytest.raises(store.MemberError):
        store.create_member(store.new_id(), a_vault(store), "member", [], name="founder")


def test_the_index_and_the_names_held_are_kept_beside_the_members(store, data_dir):
    member_id = store.new_id()
    store.create_member(member_id, a_vault(store), "member", [], name="willow", sign_in=SIGN_IN)
    index = json.loads((data_dir / "members" / "sign-in.json").read_text(encoding="utf-8"))
    assert index == {SIGN_IN: member_id}
    held = json.loads((data_dir / "members" / "names-held.json").read_text(encoding="utf-8"))
    assert held == {member_id: ["willow"]}
