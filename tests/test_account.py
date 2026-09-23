"""The account page: a signed-in member gives the password they have and a new
one twice, and the same key is sealed again under the new one. This session
stays signed in; every other session of that member is signed out at its next
request. The current password is counted with the login page's tries.

Vaults are sealed at argon2id's minimum cost, as in test_member_login.py.
"""

import pytest
from markupsafe import escape
from nacl.pwhash import argon2id

import vault
from conftest import page, post, read_json, token

KEEPER = "ash"
KEEPER_PASSWORD = "the keeper's own password"
MEMBER = "birch"
MEMBER_PASSWORD = "a member's own password"
NEW_PASSWORD = "a new password, chosen at home"
WRONG = "not anyone's password at all"

NOT_THE_PASSWORD = "That is not the password."
CHANGED = "Your password is changed."
DIFFER = "The two new passwords are not the same."
CSRF_REFUSAL = "This form was not sent from the hearth. Go back, refresh, and try again."


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


@pytest.fixture
def people(hearth):
    """A keeper and a member, each with a vault of their own."""
    for name, password, role in ((KEEPER, KEEPER_PASSWORD, "keeper"),
                                 (MEMBER, MEMBER_PASSWORD, "member")):
        sealed, _, _ = vault.make_vault(password)
        hearth.members.create_member(name, sealed, role, [])
    return hearth


@pytest.fixture
def derivations(hearth, monkeypatch):
    counted = []
    real = vault._derive

    def counting(*args, **kwargs):
        counted.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(vault, "_derive", counting)
    return counted


def sign_in(client, name, password):
    return post(client, "/login", data={"pseudonym": name, "password": password})


def signed_in(hearth, name, password):
    client = hearth.app.test_client()
    assert sign_in(client, name, password).status_code == 302
    return client


@pytest.fixture
def member(people):
    return signed_in(people, MEMBER, MEMBER_PASSWORD)


@pytest.fixture
def keeper(people):
    return signed_in(people, KEEPER, KEEPER_PASSWORD)


def change(client, current, password=NEW_PASSWORD, again=None, **how):
    return post(client, "/account", data={
        "current_password": current, "password": password,
        "password_again": password if again is None else again}, **how)


def said(answer, words):
    assert answer.status_code == 200
    text = page(answer)
    assert escape(words) in text
    return text


def to_login(answer):
    return answer.status_code == 302 and answer.headers["Location"].endswith("/login")


def record_of(data_dir, name):
    return read_json(data_dir / "members" / name / "member.json")


def still_member(client, name):
    with client.session_transaction() as held:
        return held.get("member") == name


# ---- the page ------------------------------------------------------------

def test_the_page_asks_for_the_current_password_and_the_new_one_twice(member):
    text = page(member.get("/account"))
    for field in ('name="current_password"', 'name="password"', 'name="password_again"'):
        assert field in text, field
    assert "Your key stays the same" in text
    assert "Anywhere else you are signed in will be signed out." in text


def test_the_account_form_carries_the_token(member):
    assert f'name="csrf_token" value="{token(member)}"' in page(member.get("/account"))


def test_the_keeper_has_an_account_page_too(keeper):
    assert keeper.get("/account").status_code == 200


def test_visitors_are_sent_to_login(visitor, people):
    assert to_login(visitor.get("/account"))
    assert to_login(change(visitor, KEEPER_PASSWORD))


def test_an_old_founder_session_is_sent_to_login(people, hearth, data_dir):
    before = record_of(data_dir, KEEPER)
    old = hearth.app.test_client()
    with old.session_transaction() as held:
        held["founder"] = True
    assert to_login(old.get("/account"))
    assert to_login(change(old, KEEPER_PASSWORD))
    assert record_of(data_dir, KEEPER) == before


# ---- the nav -------------------------------------------------------------

def test_the_nav_names_the_account_to_a_member(member):
    assert '<a href="/account">account</a>' in page(member.get("/"))


def test_the_nav_names_the_account_to_the_keeper(keeper):
    text = page(keeper.get("/letters"))
    assert '<a href="/account">account</a>' in text and 'href="/export"' in text


def test_the_nav_does_not_name_it_to_a_visitor(visitor):
    assert 'href="/account"' not in page(visitor.get("/"))


def test_on_the_account_page_the_nav_marks_it_as_here(member):
    assert '<span class="here">account</span>' in page(member.get("/account"))


# ---- changing ------------------------------------------------------------

def test_the_password_is_changed(member):
    said(change(member, MEMBER_PASSWORD), CHANGED)


def test_the_new_password_opens_login_and_the_old_does_not(member, people):
    change(member, MEMBER_PASSWORD)
    old, new = people.app.test_client(), people.app.test_client()
    said(sign_in(old, MEMBER, MEMBER_PASSWORD), NOT_THE_PASSWORD)
    assert sign_in(new, MEMBER, NEW_PASSWORD).status_code == 302


def test_the_key_is_unchanged(member, data_dir):
    before = record_of(data_dir, MEMBER)
    change(member, MEMBER_PASSWORD)
    after = record_of(data_dir, MEMBER)
    assert after["verify_key"] == before["verify_key"] == after["vault"]["verify_key"]
    assert after["vault"]["by_phrase"] == before["vault"]["by_phrase"]
    assert after["vault"]["by_password"] != before["vault"]["by_password"]
    assert vault.unlock(after["vault"], NEW_PASSWORD).verify_key.encode().hex() \
        == before["verify_key"]
    assert not (data_dir / "members" / MEMBER / "key-history.json").exists()


def test_this_session_stays_signed_in_by_the_new_seal(member, data_dir):
    change(member, MEMBER_PASSWORD)
    assert still_member(member, MEMBER)
    assert "You are logged in" in page(member.get("/"))
    with member.session_transaction() as held:
        assert held["seal"] == vault.fingerprint(record_of(data_dir, MEMBER)["vault"])
    assert member.get("/account").status_code == 200


def test_the_token_is_cut_afresh_and_the_new_one_works(member):
    before = token(member)
    change(member, MEMBER_PASSWORD)
    after = token(member)
    assert after != before
    said(change(member, NEW_PASSWORD, password="and a third password"), CHANGED)


def test_a_second_session_is_signed_out_at_its_next_request(member, people):
    elsewhere = signed_in(people, MEMBER, MEMBER_PASSWORD)
    said(change(member, MEMBER_PASSWORD), CHANGED)
    assert "You are logged in" not in page(elsewhere.get("/"))
    with elsewhere.session_transaction() as held:
        assert dict(held) == {}
    assert still_member(member, MEMBER)


def test_the_keeper_keeps_the_gate_and_another_keeper_session_loses_it(keeper, people):
    elsewhere = signed_in(people, KEEPER, KEEPER_PASSWORD)
    said(change(keeper, KEEPER_PASSWORD), CHANGED)
    assert keeper.get("/letters").status_code == 200
    assert to_login(elsewhere.get("/letters"))


def test_the_founder_s_password_session_is_not_touched(keeper, founder):
    change(keeper, KEEPER_PASSWORD)
    assert founder.get("/letters").status_code == 200


# ---- refusals ------------------------------------------------------------

def test_a_wrong_current_password_is_refused(member, data_dir, derivations):
    before = record_of(data_dir, MEMBER)
    text = said(change(member, WRONG), NOT_THE_PASSWORD)
    assert CHANGED not in text
    assert record_of(data_dir, MEMBER) == before
    assert len(derivations) == 1
    assert still_member(member, MEMBER)


def test_a_wrong_current_password_is_counted(member, people, monkeypatch):
    for _ in range(5):
        said(change(member, WRONG), NOT_THE_PASSWORD)
    monkeypatch.setattr(vault, "_derive",
                        lambda *a, **k: pytest.fail("argon2id ran while the name was shut"))
    said(change(member, MEMBER_PASSWORD), NOT_THE_PASSWORD)
    said(sign_in(people.app.test_client(), MEMBER, MEMBER_PASSWORD), NOT_THE_PASSWORD)


def test_another_member_s_password_does_not_open_this_vault(member, data_dir):
    before = record_of(data_dir, MEMBER)
    said(change(member, KEEPER_PASSWORD), NOT_THE_PASSWORD)
    assert record_of(data_dir, MEMBER) == before


def test_new_passwords_that_differ_are_refused_and_not_counted(member, data_dir,
                                                                derivations):
    before = record_of(data_dir, MEMBER)
    for _ in range(6):
        text = said(change(member, MEMBER_PASSWORD, again="something else entirely"), DIFFER)
        assert NOT_THE_PASSWORD not in text
    assert derivations == []
    assert record_of(data_dir, MEMBER) == before
    said(change(member, MEMBER_PASSWORD), CHANGED)


def test_a_short_or_long_new_password_is_refused_with_its_reason_and_not_counted(
        member, data_dir, derivations):
    before = record_of(data_dir, MEMBER)
    for _ in range(3):
        said(change(member, MEMBER_PASSWORD, password="short"),
             "A password needs at least 10 characters.")
        said(change(member, MEMBER_PASSWORD, password="x" * 257),
             "A password can be at most 256 characters.")
    assert derivations == []
    assert record_of(data_dir, MEMBER) == before
    said(change(member, MEMBER_PASSWORD), CHANGED)


# ---- guessing, shared with the login page --------------------------------

def test_misses_at_login_shut_the_name_here_without_trying_anything(member, people,
                                                                    monkeypatch):
    guesser = people.app.test_client()
    for _ in range(5):
        sign_in(guesser, MEMBER, WRONG)
    monkeypatch.setattr(vault, "_derive",
                        lambda *a, **k: pytest.fail("argon2id ran while the name was shut"))
    said(change(member, MEMBER_PASSWORD), NOT_THE_PASSWORD)


def test_misses_are_shared_across_the_two_pages(member, people, monkeypatch):
    for _ in range(2):
        sign_in(people.app.test_client(), MEMBER, WRONG)
    for _ in range(3):
        said(change(member, WRONG), NOT_THE_PASSWORD)
    monkeypatch.setattr(vault, "_derive",
                        lambda *a, **k: pytest.fail("argon2id ran while the name was shut"))
    said(change(member, MEMBER_PASSWORD), NOT_THE_PASSWORD)
    said(sign_in(people.app.test_client(), MEMBER, MEMBER_PASSWORD), NOT_THE_PASSWORD)


def test_the_address_count_is_shared_too(member, people, monkeypatch):
    guesser = people.app.test_client()
    for n in range(10):
        sign_in(guesser, "guess-%d" % n, WRONG)
    monkeypatch.setattr(vault, "_derive",
                        lambda *a, **k: pytest.fail("argon2id ran while the address was shut"))
    said(change(member, MEMBER_PASSWORD), NOT_THE_PASSWORD)


def test_a_shut_name_opens_again_after_a_quarter_of_an_hour(member, clock):
    for _ in range(5):
        said(change(member, WRONG), NOT_THE_PASSWORD)
    said(change(member, MEMBER_PASSWORD), NOT_THE_PASSWORD)
    clock.shift(minutes=15, seconds=1)
    said(change(member, MEMBER_PASSWORD), CHANGED)


def test_a_change_clears_the_name_s_count(member, people):
    for _ in range(4):
        said(change(member, WRONG), NOT_THE_PASSWORD)
    said(change(member, MEMBER_PASSWORD), CHANGED)
    guesser = people.app.test_client()
    for _ in range(4):
        sign_in(guesser, MEMBER, WRONG)
    assert sign_in(guesser, MEMBER, NEW_PASSWORD).status_code == 302


def test_another_name_s_count_is_not_touched(member, people):
    for _ in range(5):
        said(change(member, WRONG), NOT_THE_PASSWORD)
    other = people.app.test_client()
    other.environ_base["REMOTE_ADDR"] = "203.0.113.9"
    assert sign_in(other, KEEPER, KEEPER_PASSWORD).status_code == 302


# ---- the token -----------------------------------------------------------

def test_a_change_without_the_token_is_refused(member, data_dir):
    before = record_of(data_dir, MEMBER)
    answer = member.post("/account", data={
        "current_password": MEMBER_PASSWORD, "password": NEW_PASSWORD,
        "password_again": NEW_PASSWORD})
    assert answer.status_code == 400 and CSRF_REFUSAL in page(answer)
    assert record_of(data_dir, MEMBER) == before


# ---- what is left behind -------------------------------------------------

def every_file(data_dir):
    return {str(path): path.stat().st_mtime_ns
            for path in data_dir.rglob("*") if path.is_file()}


def test_nothing_is_written_but_the_member_s_record(member, data_dir):
    before = every_file(data_dir)
    said(change(member, WRONG), NOT_THE_PASSWORD)
    said(change(member, MEMBER_PASSWORD, again="something else entirely"), DIFFER)
    said(change(member, MEMBER_PASSWORD, password="short"),
         "A password needs at least 10 characters.")
    assert every_file(data_dir) == before

    said(change(member, MEMBER_PASSWORD), CHANGED)
    after = every_file(data_dir)
    assert set(after) == set(before)
    changed = {path for path in after if after[path] != before[path]}
    assert changed == {str(data_dir / "members" / MEMBER / "member.json")}


def test_nothing_is_logged_of_the_name_or_the_passwords(member, caplog):
    with caplog.at_level("DEBUG"):
        change(member, WRONG)
        change(member, MEMBER_PASSWORD, again="something else entirely")
        change(member, MEMBER_PASSWORD)
    for line in caplog.text.splitlines():
        for secret in (MEMBER, MEMBER_PASSWORD, NEW_PASSWORD, WRONG):
            assert secret not in line, line
