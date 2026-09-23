"""Members at the door: a keeper signs in with their own vault and passes the
founder's gate, a member signs in and does not, the founder's one password
still works beside them, and guessing is slowed where it is counted.

Every vault here is sealed at argon2id's minimum cost so the suite stays quick,
as in test_vault.py; the vault a name that belongs to no one is tried against is
made at the same cost, since it is made at whatever the limits are.
"""

import shutil
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from types import SimpleNamespace

import pytest
from nacl.pwhash import argon2id

import vault
from conftest import PASSWORD, page, post

KEEPER = "ash"
KEEPER_PASSWORD = "the keeper's own password"
MEMBER = "birch"
MEMBER_PASSWORD = "a member's own password"
WRONG = "not anyone's password at all"

REFUSAL = "That is not the password."


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


@pytest.fixture
def people(hearth):
    """A keeper and a member, each with a vault of their own, in the test's DATA_DIR."""
    for name, password, role in ((KEEPER, KEEPER_PASSWORD, "keeper"),
                                 (MEMBER, MEMBER_PASSWORD, "member")):
        sealed, _, _ = vault.make_vault(password)
        hearth.members.create_member(name, sealed, role, [])
    return hearth


@pytest.fixture
def derivations(hearth, monkeypatch):
    """Count every argon2id derivation, and let each one run."""
    counted = []
    real = vault._derive

    def counting(*args, **kwargs):
        counted.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(vault, "_derive", counting)
    return counted


def sign_in(client, name, password):
    return post(client, "/login", data={"pseudonym": name, "password": password})


def refused(answer):
    assert answer.status_code == 200
    assert REFUSAL in page(answer)
    return page(answer)


def shut_out(client, path="/letters"):
    answer = client.get(path)
    return answer.status_code == 302 and answer.headers["Location"].endswith("/login")


# ---- signing in ----------------------------------------------------------

def test_the_login_page_asks_for_a_pseudonym_above_the_password(visitor):
    said = page(visitor.get("/login"))
    assert 'name="pseudonym"' in said
    assert said.index('name="pseudonym"') < said.index('name="password"')


def test_a_keeper_signs_in_and_reaches_a_founder_page(people, visitor):
    answer = sign_in(visitor, KEEPER, KEEPER_PASSWORD)
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/letters")
    assert visitor.get("/letters").status_code == 200
    with visitor.session_transaction() as held:
        assert held["member"] == KEEPER and held["role"] == "keeper"
        assert "founder" not in held


def test_a_pseudonym_is_taken_however_it_is_capitalised(people, visitor):
    answer = sign_in(visitor, "  Ash ", KEEPER_PASSWORD)
    assert answer.status_code == 302
    with visitor.session_transaction() as held:
        assert held["member"] == KEEPER


def test_the_key_is_not_kept_anywhere_in_the_session(people, visitor):
    sign_in(visitor, KEEPER, KEEPER_PASSWORD)
    with visitor.session_transaction() as held:
        assert set(held) == {"member", "role", "seal", "csrf_token", "_permanent"}
        assert len(held["seal"]) == 16  # the vault's fingerprint, not the vault


def test_signing_in_clears_whatever_session_was_there(people, visitor):
    with visitor.session_transaction() as held:
        held["leftover"] = "from before"
    sign_in(visitor, KEEPER, KEEPER_PASSWORD)
    with visitor.session_transaction() as held:
        assert "leftover" not in held


def test_a_wrong_password_is_refused(people, visitor):
    refused(sign_in(visitor, KEEPER, WRONG))
    assert shut_out(visitor)
    with visitor.session_transaction() as held:
        assert "member" not in held


@pytest.mark.parametrize("name", ["nobody-here", "founder", "keeper", "con", "x",
                                  "../ash", "ash/..", "has space", "a" * 31, "9lives"])
def test_unknown_and_impossible_names_are_refused_in_the_same_words(people, visitor,
                                                                    derivations, name):
    wrong_password = refused(sign_in(visitor, KEEPER, WRONG))
    derivations.clear()
    assert refused(sign_in(visitor, name, KEEPER_PASSWORD)) == wrong_password
    assert len(derivations) == 1, "a name that is no one's must cost one derivation too"


def test_a_member_signs_in_but_cannot_reach_the_founder_s_pages(people, visitor, hearth):
    answer = sign_in(visitor, MEMBER, MEMBER_PASSWORD)
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/")
    with visitor.session_transaction() as held:
        assert held["role"] == "member"
    for path in ("/letters", "/chronicle", "/attendances", "/bonds", "/export", "/backups"):
        assert shut_out(visitor, path), path
    assert post(visitor, "/pause", data={"confirm": "yes"}).status_code == 302
    assert not (hearth.PAUSE).exists()


def test_a_member_session_claiming_to_be_keeper_is_checked_against_the_record(people,
                                                                              visitor):
    sign_in(visitor, MEMBER, MEMBER_PASSWORD)  # a real sign-in, fingerprint and all
    with visitor.session_transaction() as held:
        held["role"] = "keeper"
    assert shut_out(visitor)
    with visitor.session_transaction() as held:
        assert held["member"] == MEMBER  # turned away by the role, not signed out


def test_the_founder_s_password_still_works_with_the_pseudonym_left_empty(people, visitor):
    answer = sign_in(visitor, "", PASSWORD)
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/letters")
    assert visitor.get("/letters").status_code == 200
    with visitor.session_transaction() as held:
        assert held["founder"] is True


def test_the_founder_s_password_is_not_a_member_s(people, visitor):
    refused(sign_in(visitor, KEEPER, PASSWORD))
    refused(sign_in(visitor, "", KEEPER_PASSWORD))
    assert shut_out(visitor)


def test_a_keeper_whose_folder_is_gone_loses_the_gate_at_the_next_request(people, visitor,
                                                                          data_dir):
    sign_in(visitor, KEEPER, KEEPER_PASSWORD)
    assert visitor.get("/letters").status_code == 200
    shutil.rmtree(data_dir / "members" / KEEPER)
    assert shut_out(visitor)


def test_a_deleted_member_s_session_is_cleared_at_the_next_request(people, visitor,
                                                                   data_dir):
    sign_in(visitor, MEMBER, MEMBER_PASSWORD)
    assert "You are logged in" in page(visitor.get("/"))
    shutil.rmtree(data_dir / "members" / MEMBER)
    assert "You are logged in" not in page(visitor.get("/"))
    with visitor.session_transaction() as held:
        assert dict(held) == {}


def test_a_member_session_with_no_fingerprint_is_cleared(people, visitor):
    sign_in(visitor, MEMBER, MEMBER_PASSWORD)
    with visitor.session_transaction() as held:
        del held["seal"]
    assert "You are logged in" not in page(visitor.get("/"))


def test_the_founder_s_session_names_no_member_and_is_left_alone(people, visitor):
    sign_in(visitor, "", PASSWORD)
    assert visitor.get("/letters").status_code == 200
    with visitor.session_transaction() as held:
        assert held["founder"] is True and "member" not in held


def test_the_nav_is_shown_to_the_keeper_and_not_to_a_member(people, hearth):
    keeper, member = hearth.app.test_client(), hearth.app.test_client()
    sign_in(keeper, KEEPER, KEEPER_PASSWORD)
    sign_in(member, MEMBER, MEMBER_PASSWORD)
    assert "<nav>" in page(keeper.get("/"))
    assert "<nav>" not in page(member.get("/"))
    assert "You are logged in" in page(member.get("/"))


# ---- guessing ------------------------------------------------------------

def test_five_misses_at_a_name_shut_it_without_trying_anything(people, visitor, monkeypatch,
                                                               clock):
    for _ in range(5):
        refused(sign_in(visitor, KEEPER, WRONG))
    def refuse(*args, **kwargs):
        raise AssertionError("argon2id was run while the name was shut")
    monkeypatch.setattr(vault, "_derive", refuse)
    refused(sign_in(visitor, KEEPER, KEEPER_PASSWORD))
    assert shut_out(visitor)
    clock.shift(minutes=14)
    refused(sign_in(visitor, KEEPER, KEEPER_PASSWORD))


def test_a_shut_name_opens_again_after_a_quarter_of_an_hour(people, visitor, clock):
    for _ in range(5):
        refused(sign_in(visitor, KEEPER, WRONG))
    clock.shift(minutes=15, seconds=1)
    assert sign_in(visitor, KEEPER, KEEPER_PASSWORD).status_code == 302


def test_misses_spread_past_the_window_do_not_add_up(people, visitor, clock):
    for _ in range(4):
        refused(sign_in(visitor, KEEPER, WRONG))
    clock.shift(minutes=16)
    refused(sign_in(visitor, KEEPER, WRONG))
    assert sign_in(visitor, KEEPER, KEEPER_PASSWORD).status_code == 302


def test_a_shut_name_does_not_shut_another(people, hearth):
    guesser, member = hearth.app.test_client(), hearth.app.test_client()
    for _ in range(5):
        refused(sign_in(guesser, KEEPER, WRONG))
    assert sign_in(member, MEMBER, MEMBER_PASSWORD).status_code == 302


def test_ten_misses_from_one_address_shut_it(people, hearth, visitor, monkeypatch):
    real_derive, real_check = vault._derive, hearth.check_password_hash
    shut = SimpleNamespace(now=False)

    def guarded(real):
        def called(*args, **kwargs):
            assert not shut.now, "something was tried while the address was shut"
            return real(*args, **kwargs)
        return called

    monkeypatch.setattr(vault, "_derive", guarded(real_derive))
    monkeypatch.setattr(hearth, "check_password_hash", guarded(real_check))

    # the misses are spread over names, so no one name reaches its own five
    for n in range(10):
        refused(sign_in(visitor, "guess-%d" % n, WRONG))

    shut.now = True
    refused(sign_in(visitor, KEEPER, KEEPER_PASSWORD))
    refused(sign_in(visitor, "", PASSWORD))

    shut.now = False
    elsewhere = hearth.app.test_client()
    elsewhere.environ_base["REMOTE_ADDR"] = "203.0.113.9"
    assert sign_in(elsewhere, KEEPER, KEEPER_PASSWORD).status_code == 302


def test_the_address_is_counted_only_as_a_hash(people, hearth, visitor):
    refused(sign_in(visitor, "nobody-here", WRONG))
    counted = repr(hearth.LOGIN_MISSES)
    assert "127.0.0.1" not in counted


def test_the_founder_s_password_is_counted_too(people, hearth, visitor, monkeypatch):
    for _ in range(5):
        refused(sign_in(visitor, "", WRONG))
    monkeypatch.setattr(hearth, "check_password_hash",
                        lambda *a: pytest.fail("the password was checked while shut"))
    refused(sign_in(visitor, "", PASSWORD))
    assert shut_out(visitor)


def test_a_success_clears_that_name_s_count(people, visitor):
    for _ in range(4):
        refused(sign_in(visitor, KEEPER, WRONG))
    assert sign_in(visitor, KEEPER, KEEPER_PASSWORD).status_code == 302
    for _ in range(4):
        refused(sign_in(visitor, KEEPER, WRONG))
    assert sign_in(visitor, KEEPER, KEEPER_PASSWORD).status_code == 302


def test_a_success_by_the_founder_clears_the_founder_s_count(people, visitor):
    for _ in range(4):
        refused(sign_in(visitor, "", WRONG))
    assert sign_in(visitor, "", PASSWORD).status_code == 302
    for _ in range(4):
        refused(sign_in(visitor, "", WRONG))
    assert sign_in(visitor, "", PASSWORD).status_code == 302


# ---- the session ---------------------------------------------------------

def test_a_sign_in_lasts_fourteen_days_behind_a_careful_cookie(people, hearth, visitor):
    assert hearth.app.permanent_session_lifetime == timedelta(days=14)
    answer = sign_in(visitor, KEEPER, KEEPER_PASSWORD)
    cookie = answer.headers["Set-Cookie"]
    for flag in ("Secure", "HttpOnly", "SameSite=Lax"):
        assert flag in cookie, flag
    expires = parsedate_to_datetime(cookie.split("Expires=")[1].split(";")[0])
    expected = datetime.now(timezone.utc) + timedelta(days=14)
    assert abs((expires - expected).total_seconds()) < 60


def test_the_founder_s_sign_in_lasts_fourteen_days_too(people, visitor):
    cookie = sign_in(visitor, "", PASSWORD).headers["Set-Cookie"]
    assert "Expires=" in cookie and "Secure" in cookie and "HttpOnly" in cookie


def test_after_fourteen_days_the_password_is_asked_for_again(people, visitor, monkeypatch):
    sign_in(visitor, KEEPER, KEEPER_PASSWORD)
    assert visitor.get("/letters").status_code == 200
    later = time.time() + timedelta(days=14, minutes=1).total_seconds()
    monkeypatch.setattr("itsdangerous.timed.time", SimpleNamespace(time=lambda: later))
    assert shut_out(visitor)


def test_being_used_does_not_stretch_a_sign_in(people, visitor):
    sign_in(visitor, KEEPER, KEEPER_PASSWORD)
    assert "Set-Cookie" not in visitor.get("/letters").headers


def test_logging_out_clears_the_member_s_session(people, visitor):
    sign_in(visitor, KEEPER, KEEPER_PASSWORD)
    visitor.get("/logout")
    with visitor.session_transaction() as held:
        assert dict(held) == {}
    assert shut_out(visitor)


# ---- what is left behind -------------------------------------------------

def every_file(data_dir):
    return sorted((str(path), path.stat().st_mtime_ns)
                  for path in data_dir.rglob("*") if path.is_file())


def test_nothing_is_written_to_disk_by_signing_in_or_failing(people, visitor, data_dir):
    before = every_file(data_dir)
    for _ in range(6):
        sign_in(visitor, KEEPER, WRONG)
    sign_in(visitor, "nobody-here", WRONG)
    sign_in(visitor, "", WRONG)
    sign_in(visitor, MEMBER, MEMBER_PASSWORD)
    sign_in(visitor, "", PASSWORD)
    assert every_file(data_dir) == before


def test_nothing_is_logged_of_a_name_or_a_password(people, visitor, caplog):
    with caplog.at_level("DEBUG"):
        sign_in(visitor, KEEPER, WRONG)
        sign_in(visitor, KEEPER, KEEPER_PASSWORD)
    for line in caplog.text.splitlines():
        assert KEEPER not in line and WRONG not in line and KEEPER_PASSWORD not in line
