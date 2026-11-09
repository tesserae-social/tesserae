"""A person's email address: added on /account, confirmed by a link sent to it, and
kept beside their record (proposals/invitations-design.md, stage 1).

The address is a personal detail. No page shows it in full - its owner's own
included - and only /account shows its owner their own confirmed one, partly
hidden, as s•••@example.org; no other page shows it in any form. No copy of the record carries it, no waking reads it, and no log names it. It is
kept in members/<name>/email.json, which goes only where members/ goes: into the
encrypted backup. The links that confirm one are kept in tokens/, by their hash,
and in neither a copy nor a backup.

Vaults are sealed at argon2id's minimum cost, as in test_account.py.
"""

import io
import re
import tarfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from markupsafe import escape
from nacl.pwhash import argon2id

import vault
from conftest import FOUNDER_NAME, PASSWORD, page, post, read_json, token

ADDRESS = "Someone@Example.org"
KEPT = "someone@example.org"
OTHER = "another@example.net"
MEMBER = "birch"
MEMBER_PASSWORD = "a member's own password"
WRONG = "not anyone's password at all"

SENT = "A link is on its way to that address."
NOT_SENT = "The email couldn't be sent just now. Try again later."
CONFIRMED = "Your email address is confirmed."
NOT_OPEN = "This link is no longer open."
NOT_THE_PASSWORD = "That is not the password."
NOT_AN_ADDRESS = "That doesn't look like an email address."
LINK = re.compile(r"https://hearth\.tesserae\.social/email/confirm/([A-Za-z0-9_-]{43})\n")


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


@pytest.fixture
def member(hearth):
    sealed, _, _ = vault.make_vault(MEMBER_PASSWORD)
    hearth.members.create_member(MEMBER, sealed, "member", [])
    client = hearth.app.test_client()
    assert post(client, "/login", data={"pseudonym": MEMBER,
                                        "password": MEMBER_PASSWORD}).status_code == 302
    return client


def ask(client, address=ADDRESS, password=PASSWORD, **how):
    return post(client, "/account/email", data={"address": address, "email_password": password},
                **how)


def link_in(sent):
    found = LINK.search(sent["text"])
    assert found, sent["text"]
    return found.group(1)


def confirm(client, link):
    return post(client, "/email/confirm/" + link)


def confirmed(client, outbox, address=ADDRESS, password=PASSWORD):
    assert SENT in page(ask(client, address, password))
    return confirm(client, link_in(outbox.sent[-1]))


# ---- the store -------------------------------------------------------------

def test_an_address_is_kept_trimmed_and_lowercased(hearth):
    assert hearth.members.email_address("  " + ADDRESS + " ") == KEPT


@pytest.mark.parametrize("text", ["", "someone", "someone@", "@example.org", "some one@example.org",
                                  "someone@example", "a@b@example.org", "someone@example.org\nx",
                                  "s" * 250 + "@example.org", None])
def test_what_is_no_address_is_refused(hearth, text):
    with pytest.raises(hearth.members.MemberError, match=NOT_AN_ADDRESS):
        hearth.members.email_address(text)


def test_an_address_is_kept_beside_the_record_and_found_by_it(hearth, founder, data_dir):
    store = hearth.members
    held = store.set_email(FOUNDER_NAME, ADDRESS, confirmed_at="2026-10-15T12:00:00Z")
    assert held["address"] == KEPT
    assert read_json(data_dir / "members" / FOUNDER_NAME / "email.json") == held
    assert store.email_of(FOUNDER_NAME) == held
    assert store.member_by_email(ADDRESS.upper()) == FOUNDER_NAME
    assert store.member_by_email(OTHER) is None
    assert "email" not in read_json(data_dir / "members" / FOUNDER_NAME / "member.json")


def test_no_two_people_hold_one_address(hearth, founder, member):
    store = hearth.members
    store.set_email(FOUNDER_NAME, ADDRESS, confirmed_at="2026-10-15T12:00:00Z")
    with pytest.raises(store.MemberError, match="already in use"):
        store.set_email(MEMBER, KEPT)
    store.set_email(FOUNDER_NAME, ADDRESS, confirmed_at="2026-10-15T12:00:00Z")  # one's own again is no clash


def test_an_unconfirmed_address_reserves_nothing_and_is_let_go_when_another_confirms(
        hearth, founder, member, outbox, data_dir):
    store = hearth.members
    store.set_email(MEMBER, ADDRESS)  # kept unconfirmed, as a new member's is
    assert store.member_by_email(ADDRESS) is None
    member_client = member
    ask(member_client, ADDRESS, MEMBER_PASSWORD)
    theirs = link_in(outbox.sent[-1])
    ask(founder)  # not refused, and no "already in use" email: it is a link like any
    assert outbox.sent[-1]["subject"] == "Confirm your email address for Tesserae"
    assert confirm(founder, link_in(outbox.sent[-1])).status_code == 200
    assert store.member_by_email(ADDRESS) == FOUNDER_NAME
    assert store.email_of(MEMBER) is None  # theirs is let go
    for answer in (member_client.get("/email/confirm/" + theirs), confirm(member_client, theirs)):
        assert answer.status_code == 410 and escape(NOT_OPEN) in page(answer)
    assert store.member_by_email(ADDRESS) == FOUNDER_NAME


def test_no_address_is_kept_for_a_name_no_one_has_or_could_have(hearth):
    for name in ("nobody", "../members", "Founder"):
        with pytest.raises(hearth.members.MemberError):
            hearth.members.set_email(name, ADDRESS)


# ---- the account page -------------------------------------------------------

def test_the_keeper_and_a_member_are_each_asked_for_an_address(founder, member):
    for client in (founder, member):
        text = page(client.get("/account"))
        # it says, truly, what the address is used for: a link, and the emails that stop
        assert ("Add an email address. It's used to send you a link if you forget your password, "
                "and a") in text
        assert 'name="address"' in text and 'name="email_password"' in text
        assert "Send a link to confirm it" in text


def test_asking_sends_a_link_to_the_address_and_keeps_only_its_hash(
        hearth, founder, outbox, data_dir):
    text = page(ask(founder))
    assert escape(SENT) in text and KEPT not in text.lower()
    [sent] = outbox.sent
    assert sent["to"] == KEPT and sent["subject"] == "Confirm your email address for Tesserae"
    link = link_in(sent)
    [kept] = list((data_dir / "tokens").iterdir())
    assert link not in kept.name and kept.name.startswith("confirm-")
    assert read_json(kept)["address"] == KEPT and read_json(kept)["name"] == FOUNDER_NAME
    assert not (data_dir / "members" / FOUNDER_NAME / "email.json").exists()  # not until confirmed
    assert "it lasts a day" in page(founder.get("/account"))


def test_the_link_opens_a_button_and_the_button_confirms(hearth, founder, outbox, data_dir):
    ask(founder)
    link = link_in(outbox.sent[0])
    visitor = hearth.app.test_client()  # the link may be opened anywhere
    for _ in range(2):  # opening it spends nothing: a mail service may open it first
        shown = visitor.get("/email/confirm/" + link)
        assert shown.status_code == 200 and "Confirm this address" in page(shown)
    answer = confirm(visitor, link)
    assert answer.status_code == 200 and escape(CONFIRMED) in page(answer)
    held = read_json(data_dir / "members" / FOUNDER_NAME / "email.json")
    assert held["address"] == KEPT and held["confirmed_at"] == "2026-10-15T12:00:00Z"
    text = page(founder.get("/account"))
    assert "Your email address is %s, confirmed on 15 October 2026." % MASKED in text
    assert KEPT not in text.lower() and "Change it" in text


def test_a_link_works_once(hearth, founder, outbox):
    ask(founder)
    link = link_in(outbox.sent[0])
    assert confirm(founder, link).status_code == 200
    for answer in (confirm(founder, link), founder.get("/email/confirm/" + link)):
        assert answer.status_code == 410 and escape(NOT_OPEN) in page(answer)


@pytest.mark.parametrize("link", ["x" * 43, "short", "..%2F..%2Fmembers"])
def test_a_link_no_one_was_sent_is_no_longer_open(founder, link):
    for answer in (founder.get("/email/confirm/" + link), confirm(founder, link)):
        assert answer.status_code in (404, 410)
        if answer.status_code == 410:
            assert escape(NOT_OPEN) in page(answer)


def test_a_newer_link_takes_the_place_of_an_older_one(founder, outbox):
    ask(founder)
    ask(founder, OTHER)
    older, newer = link_in(outbox.sent[0]), link_in(outbox.sent[1])
    assert confirm(founder, older).status_code == 410
    assert confirm(founder, newer).status_code == 200


def test_a_link_lasts_a_day(hearth, founder, outbox):
    ask(founder)
    link = link_in(outbox.sent[0])
    later = datetime.now(timezone.utc) + timedelta(days=1, seconds=1)
    assert hearth.tokens.peek("confirm", link) is not None
    assert hearth.tokens.peek("confirm", link, now=later) is None
    assert hearth.tokens.take("confirm", link, now=later) is None


def test_pages_that_carry_a_link_are_kept_from_caches_referrers_and_indexes(founder, outbox):
    ask(founder)
    link = link_in(outbox.sent[0])
    for answer in (founder.get("/email/confirm/" + link), confirm(founder, link),
                   founder.get("/email/confirm/" + link)):
        assert answer.headers["Cache-Control"] == "no-store"
        assert answer.headers["Referrer-Policy"] == "same-origin"
        assert answer.headers["X-Robots-Tag"] == "noindex"


def as_a_browser_sends_it(shown, address):
    """The headers a browser sends with the post from a page's own button, under the
    Referrer-Policy that page was served with: under no-referrer the Origin is
    "null" and no Referer goes; under same-origin, both name the hearth."""
    if shown.headers.get("Referrer-Policy") == "no-referrer":
        return {"Origin": "null"}
    return {"Origin": "http://localhost", "Referer": "http://localhost" + address}


def test_the_button_works_with_what_a_browser_sends_from_the_page(hearth, founder, outbox):
    ask(founder)
    address = "/email/confirm/" + link_in(outbox.sent[0])
    browser = hearth.app.test_client()
    shown = browser.get(address)
    form = re.search(r'name="csrf_token" value="([^"]+)"', page(shown)).group(1)
    answer = browser.post(address, data={"csrf_token": form},
                          headers=as_a_browser_sends_it(shown, address))
    assert answer.status_code == 200 and escape(CONFIRMED) in page(answer), page(answer)
    assert hearth.members.email_of(FOUNDER_NAME)["address"] == KEPT


def test_the_link_is_on_the_hearth_s_own_address_whatever_host_is_asked_for(
        hearth, founder, outbox):
    form = token(founder)
    founder.set_cookie("session", founder.get_cookie("session").value,
                       domain="elsewhere.example")  # the sign-in, carried to the forged host
    answer = founder.post("/account/email", base_url="http://elsewhere.example", data={
        "address": ADDRESS, "email_password": PASSWORD, "csrf_token": form})
    assert answer.status_code == 200 and outbox.sent, page(answer)
    assert "elsewhere" not in outbox.sent[0]["text"]
    link_in(outbox.sent[0])


def test_a_wrong_password_sends_nothing_and_is_counted(hearth, founder, outbox, data_dir):
    answer = ask(founder, password=WRONG)
    assert escape(NOT_THE_PASSWORD) in page(answer)
    assert outbox.sent == [] and not (data_dir / "tokens").exists()
    assert any(key[0] == "name" and key[1] == FOUNDER_NAME for key in hearth.LOGIN_MISSES)


def test_a_name_shut_by_too_many_misses_is_refused_with_nothing_tried(hearth, founder, outbox):
    for _ in range(hearth.TRIES_AT_A_NAME):
        ask(founder, password=WRONG)
    assert escape(NOT_THE_PASSWORD) in page(ask(founder))
    assert outbox.sent == []


def test_what_is_no_address_is_said_so_and_not_counted(hearth, founder, outbox):
    assert escape(NOT_AN_ADDRESS) in page(ask(founder, "not an address"))
    assert outbox.sent == [] and hearth.LOGIN_MISSES == {}


def test_an_address_someone_else_holds_is_told_so_by_email_and_on_no_page(
        hearth, founder, member, outbox, data_dir):
    hearth.members.set_email(FOUNDER_NAME, ADDRESS, confirmed_at="2026-10-15T12:00:00Z")
    text = page(ask(member, ADDRESS, MEMBER_PASSWORD))
    assert escape(SENT) in text  # the one sentence, whoever holds it
    [sent] = outbox.sent
    assert sent["to"] == KEPT and sent["subject"] == "Your email address on Tesserae"
    assert "already uses it" in sent["text"] and not LINK.search(sent["text"])
    assert not (data_dir / "tokens").exists()
    assert hearth.members.email_of(MEMBER) is None


def test_a_change_tells_the_old_address(hearth, founder, outbox):
    confirmed(founder, outbox)
    ask(founder, OTHER)
    to_new, to_old = outbox.sent[-2], outbox.sent[-1]
    assert to_new["to"] == OTHER and LINK.search(to_new["text"])
    assert to_old["to"] == KEPT and "is being changed" in to_old["text"]
    confirm(founder, link_in(to_new))
    assert hearth.members.email_of(FOUNDER_NAME)["address"] == OTHER


def test_an_email_that_cannot_go_is_said_so(founder, outbox):
    outbox.says = "not sent: unreachable"
    text = page(ask(founder))
    assert escape(NOT_SENT) in text and escape(SENT) not in text


def test_a_visitor_has_no_address_to_add(visitor):
    answer = post(visitor, "/account/email", data={"address": ADDRESS, "email_password": PASSWORD})
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/login")


def test_without_the_form_token_nothing_is_sent(founder, outbox):
    answer = founder.post("/account/email", data={"address": ADDRESS, "email_password": PASSWORD})
    assert answer.status_code == 400 and outbox.sent == []


# ---- kept out of everything but the backup ----------------------------------

def test_no_page_shows_the_address(hearth, founder, member, visitor, outbox):
    confirmed(founder, outbox)
    plain = [rule.rule for rule in hearth.app.url_map.iter_rules()
             if "GET" in rule.methods and not rule.arguments]
    for client in (founder, member, visitor):
        for address in plain:
            text = client.get(address).get_data(as_text=True).lower()
            assert KEPT not in text, address
            if client is founder and address == "/account":
                continue  # its owner's own page, where it is shown partly hidden
            assert "@example.org" not in text and MASKED.lower() not in text, address


# ---- shown to its owner, partly hidden, on /account alone --------------------

MASKED = "s•••@example.org"


def test_the_owner_sees_their_confirmed_address_partly_hidden(founder, member, outbox):
    confirmed(founder, outbox)
    text = page(founder.get("/account"))
    assert "Your email address is %s, confirmed on" % MASKED in text
    assert KEPT not in text.lower()
    assert MASKED not in page(member.get("/account")) and "@example.org" not in page(
        member.get("/account"))


def test_an_address_not_yet_confirmed_is_not_shown_in_any_form(founder, outbox):
    ask(founder)
    text = page(founder.get("/account"))
    assert "@example.org" not in text and MASKED not in text


def test_a_changed_address_is_shown_partly_hidden_once_confirmed(founder, outbox):
    confirmed(founder, outbox)
    ask(founder, OTHER)
    text = page(founder.get("/account"))
    assert MASKED in text and "@example.net" not in text  # the new one is not yet kept
    confirm(founder, link_in(outbox.sent[-2]))
    text = page(founder.get("/account"))
    assert "a•••@example.net" in text and OTHER not in text and MASKED not in text


@pytest.mark.parametrize("address, shown", [
    ("nathan@gmail.com", "n•••@gmail.com"),
    ("n@gmail.com", "n•••@gmail.com"),
    ("someone.with.a.long.name@mail.example.co.uk", "s•••@mail.example.co.uk"),
])
def test_the_dots_are_three_whatever_the_name(hearth, address, shown):
    assert hearth.address_masked(address) == shown


def test_no_copy_carries_the_address(founder, outbox):
    confirmed(founder, outbox)
    answer = post(founder, "/export")
    with zipfile.ZipFile(io.BytesIO(answer.get_data())) as bundle:
        for name in bundle.namelist():
            assert not name.startswith(("members/", "tokens/")), name
            assert KEPT.encode() not in bundle.read(name), name


def test_the_backup_keeps_the_address_and_no_link(hearth, founder, outbox):
    confirmed(founder, outbox)
    ask(founder, OTHER)  # a link waiting, too
    with tarfile.open(fileobj=io.BytesIO(hearth.backup_archive()), mode="r:gz") as bundle:
        names = bundle.getnames()
    assert "members/%s/email.json" % FOUNDER_NAME in names
    assert not any(name.startswith("tokens") for name in names)
    assert "tokens" not in hearth.BACKUP_TREES and "mail.log" not in hearth.BACKUP_TREES


def test_no_log_names_the_address(founder, outbox, data_dir):
    confirmed(founder, outbox)
    log = (data_dir / "mail.log").read_text(encoding="utf-8")
    assert log.splitlines() and KEPT not in log.lower() and "confirm/" not in log


def test_no_waking_reads_the_address(founder, outbox, wake, room):
    confirmed(founder, outbox)
    turn = wake("")
    assert KEPT not in repr(turn.asked).lower()


def test_the_waking_never_names_an_address_at_all():
    attend = (Path(__file__).resolve().parent.parent / "attend.py").read_text(encoding="utf-8")
    assert "email" not in attend.lower()
    assert not re.search(r"^\s*(?:import|from)\s+(?:tokens|mail)\b", attend, re.M)


def test_no_access_log_writes_down_a_link():
    """gunicorn's access log would keep each path, and a path can carry a token."""
    dockerfile = (Path(__file__).resolve().parent.parent / "Dockerfile").read_text(encoding="utf-8")
    assert "access-log" not in dockerfile and "accesslog" not in dockerfile
