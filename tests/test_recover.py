"""The twelve words at the door: a member who has forgotten their password opens
their key with the phrase, seals it under a new password, and is signed in; the
key is the same key, the old password no longer opens it, and every session
made before is signed out at its next request.

Vaults are sealed at argon2id's minimum cost, as in test_member_login.py.
"""

import hashlib

import pytest
from markupsafe import escape
from nacl.pwhash import argon2id

import vault
from conftest import page, post, read_json, token

KEEPER = "ash"
KEEPER_PASSWORD = "the keeper's own password"
NEW_PASSWORD = "a new password, chosen at the door"
MEMBER = "birch"
MEMBER_PASSWORD = "a member's own password"

REFUSED = "Those words do not open that name's key."
INCOMPLETE = "Those words are not complete; check each one against your paper."
CSRF_REFUSAL = "This form was not sent from the hearth. Go back, refresh, and try again."


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


@pytest.fixture
def people(hearth):
    """A keeper and a member, with their phrases, as the paper they wrote them on."""
    phrases = {}
    for name, password, role in ((KEEPER, KEEPER_PASSWORD, "keeper"),
                                 (MEMBER, MEMBER_PASSWORD, "member")):
        sealed, phrases[name], _ = vault.make_vault(password)
        hearth.members.create_member(name, sealed, role, [])
    hearth.phrases = phrases
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


def other_phrase(phrase):
    """Twelve words whose checksum holds, and which are not these."""
    while True:
        other = vault.new_recovery_phrase()
        if other != phrase:
            return other


def incomplete(phrase):
    """The same words with the last one changed so the checksum fails."""
    words = phrase.split()
    for candidate in ("abandon", "ability", "able", "about", "above"):
        attempt = " ".join(words[:-1] + [candidate])
        try:
            vault.check_phrase(attempt)
        except vault.VaultError:
            return attempt
    raise AssertionError("could not spoil the phrase")


def recover(client, name, phrase, password=NEW_PASSWORD, again=None, **how):
    return post(client, "/recover", data={
        "pseudonym": name, "phrase": phrase, "password": password,
        "password_again": password if again is None else again}, **how)


def sign_in(client, name, password):
    return post(client, "/login", data={"pseudonym": name, "password": password})


def refused(answer, words=REFUSED):
    assert answer.status_code == 200
    said = page(answer)
    assert escape(words) in said
    return said


def shut_out(client, path="/letters"):
    answer = client.get(path)
    return answer.status_code == 302 and answer.headers["Location"].endswith("/login")


def record_of(data_dir, name):
    return read_json(data_dir / "members" / name / "member.json")


# ---- the page ------------------------------------------------------------

def test_the_page_asks_for_the_name_the_words_and_the_new_password_twice(visitor):
    said = page(visitor.get("/recover"))
    for field in ('name="pseudonym"', '<textarea id="phrase" name="phrase"',
                  'name="password"', 'name="password_again"'):
        assert field in said, field
    assert "open your key" in said and "same key" in said


def test_the_login_page_points_to_it(visitor):
    said = page(visitor.get("/login"))
    assert 'href="/recover"' in said
    assert "Forgotten your password? Your twelve words will let you in." in said


def test_the_recover_form_carries_the_token(visitor):
    said = page(visitor.get("/recover"))
    assert f'name="csrf_token" value="{token(visitor)}"' in said


# ---- recovering ----------------------------------------------------------

def test_the_right_words_and_a_new_password_sign_the_keeper_in(people, visitor):
    answer = recover(visitor, KEEPER, people.phrases[KEEPER])
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/letters")
    assert visitor.get("/letters").status_code == 200
    with visitor.session_transaction() as held:
        assert set(held) == {"member", "role", "seal", "csrf_token", "_permanent"}
        assert held["member"] == KEEPER and held["role"] == "keeper"


def test_a_member_goes_where_login_sends_a_member(people, visitor):
    answer = recover(visitor, MEMBER, people.phrases[MEMBER])
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/")
    assert shut_out(visitor)


def test_the_words_are_taken_however_they_are_written(people, visitor):
    messy = "  " + "\n".join(people.phrases[KEEPER].upper().split()) + "  "
    assert recover(visitor, " Ash ", messy).status_code == 302


def test_the_new_password_works_and_the_old_one_does_not(people, hearth):
    recover(hearth.app.test_client(), KEEPER, people.phrases[KEEPER])
    old, new = hearth.app.test_client(), hearth.app.test_client()
    assert "That is not the password." in page(sign_in(old, KEEPER, KEEPER_PASSWORD))
    assert sign_in(new, KEEPER, NEW_PASSWORD).status_code == 302


def test_the_key_is_unchanged(people, visitor, data_dir):
    before = record_of(data_dir, KEEPER)
    recover(visitor, KEEPER, people.phrases[KEEPER])
    after = record_of(data_dir, KEEPER)
    assert after["verify_key"] == before["verify_key"] == after["vault"]["verify_key"]
    assert after["vault"]["by_phrase"] == before["vault"]["by_phrase"]
    assert after["vault"]["by_password"] != before["vault"]["by_password"]
    assert vault.unlock(after["vault"], NEW_PASSWORD).verify_key.encode().hex() \
        == before["verify_key"]
    assert not (data_dir / "members" / KEEPER / "key-history.json").exists()


def test_the_same_words_still_work_a_second_time(people, hearth):
    recover(hearth.app.test_client(), KEEPER, people.phrases[KEEPER])
    again = recover(hearth.app.test_client(), KEEPER, people.phrases[KEEPER],
                    password="and another new password")
    assert again.status_code == 302


def test_recovering_clears_whatever_session_was_there(people, visitor):
    with visitor.session_transaction() as held:
        held["leftover"], held["founder"] = "from before", True
    recover(visitor, MEMBER, people.phrases[MEMBER])
    with visitor.session_transaction() as held:
        assert "leftover" not in held and "founder" not in held


# ---- other devices -------------------------------------------------------

def test_a_session_from_before_the_recovery_loses_the_gate(people, hearth):
    left_open = hearth.app.test_client()
    assert sign_in(left_open, KEEPER, KEEPER_PASSWORD).status_code == 302
    assert left_open.get("/letters").status_code == 200

    assert recover(hearth.app.test_client(), KEEPER, people.phrases[KEEPER]).status_code == 302

    assert shut_out(left_open)
    with left_open.session_transaction() as held:
        assert dict(held) == {}
    assert "<nav>" not in page(left_open.get("/"))


def test_a_member_s_session_from_before_the_recovery_is_cleared(people, hearth):
    left_open = hearth.app.test_client()
    assert sign_in(left_open, MEMBER, MEMBER_PASSWORD).status_code == 302
    assert "You are logged in" in page(left_open.get("/"))

    assert recover(hearth.app.test_client(), MEMBER, people.phrases[MEMBER]).status_code == 302

    assert "You are logged in" not in page(left_open.get("/"))
    with left_open.session_transaction() as held:
        assert dict(held) == {}


def test_the_member_s_recovering_session_stays_signed_in(people, visitor):
    recover(visitor, MEMBER, people.phrases[MEMBER])
    assert "You are logged in" in page(visitor.get("/"))
    with visitor.session_transaction() as held:
        assert held["member"] == MEMBER


def test_a_stale_session_s_form_is_refused_before_it_reaches_a_page(people, hearth,
                                                                     packet):
    left_open = hearth.app.test_client()
    sign_in(left_open, KEEPER, KEEPER_PASSWORD)
    old_token = token(left_open)
    recover(hearth.app.test_client(), KEEPER, people.phrases[KEEPER])
    answer = left_open.post("/pause", data={"confirm": "yes", "csrf_token": old_token})
    assert answer.status_code == 400 and CSRF_REFUSAL in page(answer)
    assert not (packet / "pause.json").exists()


def test_the_recovering_session_keeps_the_gate(people, visitor):
    recover(visitor, KEEPER, people.phrases[KEEPER])
    assert visitor.get("/letters").status_code == 200
    assert visitor.get("/chronicle").status_code == 200


def test_the_fingerprint_is_the_password_box_s(people, visitor, data_dir):
    recover(visitor, KEEPER, people.phrases[KEEPER])
    box = record_of(data_dir, KEEPER)["vault"]["by_password"]["box"]
    with visitor.session_transaction() as held:
        assert held["seal"] == hashlib.sha256(box.encode()).hexdigest()[:16]


def test_a_keeper_session_with_no_fingerprint_is_signed_out(people, visitor):
    sign_in(visitor, KEEPER, KEEPER_PASSWORD)
    with visitor.session_transaction() as held:
        del held["seal"]
    assert shut_out(visitor)


def test_a_keeper_session_with_a_wrong_fingerprint_is_signed_out(people, visitor):
    sign_in(visitor, KEEPER, KEEPER_PASSWORD)
    with visitor.session_transaction() as held:
        held["seal"] = "0" * 16
    assert shut_out(visitor)
    with visitor.session_transaction() as held:
        assert dict(held) == {}


def test_the_founder_s_password_session_is_not_touched(people, founder, hearth):
    recover(hearth.app.test_client(), KEEPER, people.phrases[KEEPER])
    assert founder.get("/letters").status_code == 200


# ---- refusals ------------------------------------------------------------

def test_words_whose_checksum_fails_are_named_as_incomplete(people, visitor, derivations,
                                                            data_dir):
    before = record_of(data_dir, KEEPER)
    for words in (incomplete(people.phrases[KEEPER]),
                  " ".join(people.phrases[KEEPER].split()[:11]),
                  "", "not twelve real words at all"):
        derivations.clear()
        refused(recover(visitor, KEEPER, words), INCOMPLETE)
        assert derivations == []
    assert record_of(data_dir, KEEPER) == before
    assert shut_out(visitor)


@pytest.mark.parametrize("name", ["nobody-here", "founder", "con", "x", "../ash",
                                  "has space", "a" * 31, ""])
def test_wrong_words_unknown_and_invalid_names_get_the_one_refusal(people, visitor,
                                                                   derivations, name):
    wrong = refused(recover(visitor, KEEPER, other_phrase(people.phrases[KEEPER])))
    derivations.clear()
    assert refused(recover(visitor, name, people.phrases[KEEPER])) == wrong
    assert len(derivations) == 1, "a name that is no one's must cost one derivation too"


def test_wrong_words_cost_one_derivation(people, visitor, derivations):
    refused(recover(visitor, KEEPER, other_phrase(people.phrases[KEEPER])))
    assert len(derivations) == 1


def test_another_member_s_words_do_not_open_this_name(people, visitor, data_dir):
    before = record_of(data_dir, KEEPER)
    refused(recover(visitor, KEEPER, people.phrases[MEMBER]))
    assert record_of(data_dir, KEEPER) == before
    assert shut_out(visitor)


def test_new_passwords_that_differ_are_refused(people, visitor, derivations, data_dir):
    before = record_of(data_dir, KEEPER)
    said = refused(recover(visitor, KEEPER, people.phrases[KEEPER], again="something else"),
                   "The two new passwords are not the same.")
    assert REFUSED not in said
    assert derivations == []
    assert record_of(data_dir, KEEPER) == before


def test_a_short_new_password_is_refused_with_its_reason(people, visitor, derivations,
                                                         data_dir):
    before = record_of(data_dir, KEEPER)
    refused(recover(visitor, KEEPER, people.phrases[KEEPER], password="short"),
            "A password needs at least 10 characters.")
    refused(recover(visitor, KEEPER, people.phrases[KEEPER], password="x" * 257),
            "A password can be at most 256 characters.")
    assert derivations == []
    assert record_of(data_dir, KEEPER) == before


def test_a_refusal_signs_no_one_in(people, visitor):
    refused(recover(visitor, KEEPER, other_phrase(people.phrases[KEEPER])))
    with visitor.session_transaction() as held:
        assert "member" not in held


# ---- guessing, shared with the login page --------------------------------

def test_misses_at_login_shut_the_name_here_without_trying_anything(people, visitor,
                                                                    monkeypatch):
    for _ in range(5):
        sign_in(visitor, KEEPER, "not anyone's password at all")
    monkeypatch.setattr(vault, "_derive",
                        lambda *a, **k: pytest.fail("argon2id ran while the name was shut"))
    refused(recover(visitor, KEEPER, people.phrases[KEEPER]))
    assert shut_out(visitor)


def test_misses_here_shut_the_name_at_login(people, visitor, monkeypatch):
    for _ in range(5):
        refused(recover(visitor, KEEPER, other_phrase(people.phrases[KEEPER])))
    monkeypatch.setattr(vault, "_derive",
                        lambda *a, **k: pytest.fail("argon2id ran while the name was shut"))
    assert "That is not the password." in page(sign_in(visitor, KEEPER, KEEPER_PASSWORD))
    refused(recover(visitor, KEEPER, people.phrases[KEEPER]))


def test_misses_are_shared_across_the_two_pages(people, visitor, monkeypatch):
    for _ in range(2):
        sign_in(visitor, KEEPER, "not anyone's password at all")
    for _ in range(3):
        refused(recover(visitor, KEEPER, other_phrase(people.phrases[KEEPER])))
    monkeypatch.setattr(vault, "_derive",
                        lambda *a, **k: pytest.fail("argon2id ran while the name was shut"))
    refused(recover(visitor, KEEPER, people.phrases[KEEPER]))


def test_the_address_count_is_shared_too(people, hearth, visitor, monkeypatch):
    for n in range(5):
        sign_in(visitor, "guess-%d" % n, "not anyone's password at all")
    for n in range(5, 10):
        refused(recover(visitor, "guess-%d" % n, people.phrases[KEEPER]))

    real, shut = vault._derive, [True]

    def guarded(*args, **kwargs):
        assert not shut[0], "argon2id ran while the address was shut"
        return real(*args, **kwargs)

    monkeypatch.setattr(vault, "_derive", guarded)
    refused(recover(visitor, MEMBER, people.phrases[MEMBER]))

    shut[0] = False
    elsewhere = hearth.app.test_client()
    elsewhere.environ_base["REMOTE_ADDR"] = "203.0.113.9"
    assert recover(elsewhere, MEMBER, people.phrases[MEMBER]).status_code == 302


def test_a_shut_name_opens_again_after_a_quarter_of_an_hour(people, visitor, clock):
    for _ in range(5):
        refused(recover(visitor, KEEPER, other_phrase(people.phrases[KEEPER])))
    refused(recover(visitor, KEEPER, people.phrases[KEEPER]))
    clock.shift(minutes=15, seconds=1)
    assert recover(visitor, KEEPER, people.phrases[KEEPER]).status_code == 302


def test_a_recovery_clears_the_name_s_count(people, visitor):
    for _ in range(4):
        sign_in(visitor, KEEPER, "not anyone's password at all")
    assert recover(visitor, KEEPER, people.phrases[KEEPER]).status_code == 302
    for _ in range(4):
        sign_in(visitor, KEEPER, "not anyone's password at all")
    assert sign_in(visitor, KEEPER, NEW_PASSWORD).status_code == 302


def test_an_empty_name_does_not_count_against_the_keeper(people, hearth, visitor):
    for _ in range(5):
        refused(recover(visitor, "", people.phrases[KEEPER]))
    other = hearth.app.test_client()
    other.environ_base["REMOTE_ADDR"] = "203.0.113.9"
    assert post(other, "/login", data={"pseudonym": KEEPER,
                                       "password": KEEPER_PASSWORD}).status_code == 302


# ---- the token -----------------------------------------------------------

def test_a_recovery_without_the_token_is_refused(people, visitor, data_dir):
    before = record_of(data_dir, KEEPER)
    answer = visitor.post("/recover", data={
        "pseudonym": KEEPER, "phrase": people.phrases[KEEPER],
        "password": NEW_PASSWORD, "password_again": NEW_PASSWORD})
    assert answer.status_code == 400 and CSRF_REFUSAL in page(answer)
    assert record_of(data_dir, KEEPER) == before
    assert shut_out(visitor)


# ---- what is left behind -------------------------------------------------

def every_file(data_dir):
    return {str(path): path.stat().st_mtime_ns
            for path in data_dir.rglob("*") if path.is_file()}


def test_nothing_is_written_but_the_member_s_record(people, visitor, data_dir):
    before = every_file(data_dir)
    refused(recover(visitor, KEEPER, other_phrase(people.phrases[KEEPER])))
    refused(recover(visitor, "nobody-here", people.phrases[KEEPER]))
    refused(recover(visitor, KEEPER, incomplete(people.phrases[KEEPER])), INCOMPLETE)
    assert every_file(data_dir) == before

    recover(visitor, KEEPER, people.phrases[KEEPER])
    after = every_file(data_dir)
    record = str(data_dir / "members" / KEEPER / "member.json")
    assert set(after) == set(before)
    changed = {path for path in after if after[path] != before[path]}
    assert changed == {record}


def test_nothing_is_logged_of_the_name_or_the_words(people, visitor, caplog):
    phrase = people.phrases[KEEPER]
    with caplog.at_level("DEBUG"):
        recover(visitor, KEEPER, other_phrase(phrase))
        recover(visitor, KEEPER, incomplete(phrase))
        recover(visitor, KEEPER, phrase)
    words = set(phrase.split())
    for line in caplog.text.splitlines():
        assert KEEPER not in line and NEW_PASSWORD not in line
        assert not words & set(line.lower().split()), line
