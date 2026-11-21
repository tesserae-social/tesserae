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


# ---- stage 3: signing in by email or a private sign-in name --------------------------------

from conftest import PASSWORD, page, post  # noqa: E402
from test_later_citizen import hearth_of_two, scratch_registry  # noqa: E402,F401 - fixtures
from test_rooms_for_any_agent import member_vaults  # noqa: E402,F401 - a fixture


def signs_in(hearth, given):
    client = hearth.app.test_client()
    answer = post(client, "/login", data={"pseudonym": given, "password": PASSWORD})
    return answer.status_code == 302


def test_a_member_chooses_a_private_sign_in_name_and_signs_in_with_it(hearth_of_two):
    import hearth
    member = hearth_of_two["member"]
    answer = post(member, "/account/sign-in", data={"sign_in": SIGN_IN,
                                                     "sign_in_password": PASSWORD})
    assert "From now on, sign in with %s." % SIGN_IN in page(answer)
    assert signs_in(hearth, SIGN_IN)
    assert not signs_in(hearth, "alder")  # the name they joined with signs in no longer
    assert SIGN_IN in page(member.get("/settings"))  # to them alone, on their own page
    assert SIGN_IN not in page(hearth_of_two["keeper"].get("/tides"))


def test_a_wrong_password_keeps_the_sign_in_as_it_was(hearth_of_two):
    import hearth
    answer = post(hearth_of_two["member"], "/account/sign-in",
                  data={"sign_in": SIGN_IN, "sign_in_password": "not it"})
    assert hearth.NOT_THE_PASSWORD in page(answer)
    assert signs_in(hearth, "alder") and not signs_in(hearth, SIGN_IN)


def test_only_a_confirmed_address_signs_one_in(hearth_of_two):
    import hearth
    import members
    member = hearth_of_two["member"]
    answer = post(member, "/account/sign-in", data={"by": "email", "sign_in_password": PASSWORD})
    assert hearth.SIGN_IN_NOT_CONFIRMED in page(answer)
    members.set_email("alder", ADDRESS, confirmed_at="2026-10-15T12:00:00Z")
    answer = post(member, "/account/sign-in", data={"by": "email", "sign_in_password": PASSWORD})
    assert "From now on, sign in with your email address." in page(answer)
    assert signs_in(hearth, ADDRESS) and not signs_in(hearth, "alder")


def test_a_forgotten_password_is_asked_by_the_sign_in(hearth_of_two):
    import hearth
    import members
    members.set_sign_in("alder", SIGN_IN)
    assert hearth.whose_asked(SIGN_IN) == "alder"
    assert hearth.whose_asked("alder") is None


# ---- stage 5: every name drawn from ids --------------------------------------------------

@pytest.fixture
def willow(hearth_of_two):
    """A member who joined since ids: an id, the name willow, and markers for a sign-in."""
    import members
    import vault
    sealed, _, _ = vault.make_vault(PASSWORD)
    member_id = members.new_id()
    members.create_member(member_id, sealed, "member", [], name="willow", sign_in=SIGN_IN)
    members.set_email(member_id, ADDRESS, confirmed_at="2026-10-15T12:00:00Z")
    import hearth
    client = hearth.app.test_client()
    answer = post(client, "/login", data={"pseudonym": SIGN_IN, "password": PASSWORD})
    assert answer.status_code == 302
    return {"id": member_id, "client": client, **hearth_of_two}


def every_plain_page(hearth):
    for rule in hearth.app.url_map.iter_rules():
        if "GET" in rule.methods and not rule.arguments and not rule.rule.startswith("/static"):
            yield rule.rule


def test_no_page_carries_a_sign_in_or_an_address(willow):
    import hearth
    lookers = {"visitor": hearth.app.test_client(), "member": willow["member"],
               "keeper": willow["keeper"], "willow": willow["client"]}
    for who, client in lookers.items():
        for path in every_plain_page(hearth):
            if who == "willow" and path in ("/settings", "/account"):
                continue  # their own settings say what signs them in, to them alone
            said = client.get(path).get_data(as_text=True).lower()
            assert SIGN_IN not in said and ADDRESS not in said, (who, path)


def test_a_person_is_named_by_their_name_now_and_kept_by_their_id(willow):
    import knock
    member_id = willow["id"]
    assert knock.name_of(member_id) == "willow"
    assert knock.who_is_named("willow") == member_id
    assert knock.address_of(member_id) == "willow"
    assert knock.from_address("willow") == member_id


def test_a_name_page_is_reached_by_the_name_now_and_an_old_name_is_no_one_s(willow):
    import members
    member = willow["member"]
    assert member.get("/names/willow").status_code == 200
    nobody = member.get("/names/nobody-here")
    assert member.get("/names/" + willow["id"]).get_data() == nobody.get_data()
    members.set_name(willow["id"], "birch")
    assert member.get("/names/birch").status_code == 200
    old = member.get("/names/willow")
    assert old.status_code == nobody.status_code == 404
    assert old.get_data() == nobody.get_data()


def test_an_agent_without_commons_names_reads_the_first_name(willow, monkeypatch):
    import knock
    import members
    members.set_name(willow["id"], "birch")
    monkeypatch.setattr(knock, "NAMES_NOW", False)
    assert knock.name_of(willow["id"]) == "willow"
    assert knock.who_is_named("willow") == willow["id"]
    monkeypatch.setattr(knock, "NAMES_NOW", True)
    assert knock.name_of(willow["id"]) == "birch"
    assert knock.who_is_named("willow") is None


def test_a_mention_is_kept_by_id_and_linked_by_the_name_written(willow):
    import hearth
    mentioned = hearth.mentioned_ids(hearth.board.mentions_in("hello @willow",
                                                              *hearth.board_names()))
    assert mentioned == [willow["id"]]
