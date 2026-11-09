"""A password forgotten, and a link by email (proposals/invitations-design.md, stage 2).

The login page offers /forgot, where a person gives their commons name or their
email address, and the page says one sentence whatever came of it. A member with
a confirmed address is sent a link that works once, within an hour; it opens a
page with a form, and nothing is done by its being opened. Choosing a new
password there cuts the member a new key - a member who joins has no twelve
words, so the old one cannot be opened again - and the old key is written into
their key history. The keeper is never sent a link: his key is the founder's
own, and his email points him to his twelve words at /recover. Asking is counted:
five an hour from one address, three emails an hour to one person. No address
and no link goes into any log, any print, or mail.log.

Vaults are sealed at argon2id's minimum cost, as in test_account.py.
"""

import io
import json
import re
import threading
from contextlib import redirect_stderr, redirect_stdout
from datetime import timedelta

import pytest
from nacl.pwhash import argon2id

import vault
from conftest import FOUNDER_NAME, PASSWORD, page, post, read_json

MEMBER = "birch"
MEMBER_PASSWORD = "a member's own password"
MEMBER_ADDRESS = "birch@example.org"
KEEPER_ADDRESS = "keeper@example.net"
NEW_PASSWORD = "a brand new password of theirs"

SAID = ("If that name or address belongs to someone here who has added an email "
        "address, a link is on its way to it. It works once, within an hour.")
RESET_SAID = ("Choosing a new password this way gives your account a new key. What you "
              "signed before stays signed by the old one, and your letters and friendships "
              "are just as they were.")
NOT_OPEN = "This link is no longer open."
FOOTER = "\n\nReplies to this address aren't read.\n"
LINK = re.compile(r"https://hearth\.tesserae\.social/reset/([A-Za-z0-9_-]{43})\n")


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


@pytest.fixture
def pinned(hearth, clock, monkeypatch):
    """The links' clock pinned with the hearth's, so an hour can be made to pass."""
    clock.pin(hearth.tokens, monkeypatch)
    return clock


@pytest.fixture
def member(hearth, pinned):
    """A member, with a confirmed address, and no session anywhere."""
    sealed, _, _ = vault.make_vault(MEMBER_PASSWORD)
    hearth.members.create_member(MEMBER, sealed, "member", [])
    hearth.members.set_email(MEMBER, MEMBER_ADDRESS, confirmed_at="2026-10-15T12:00:00Z")
    return hearth


@pytest.fixture
def keeper(hearth, founder, pinned):
    """The keeper, signed in elsewhere, with a confirmed address."""
    hearth.members.set_email(FOUNDER_NAME, KEEPER_ADDRESS, confirmed_at="2026-10-15T12:00:00Z")
    return founder


def ask(client, given):
    return post(client, "/forgot", data={"given": given})


def link_in(sent):
    found = LINK.search(sent["text"])
    assert found, sent["text"]
    return found.group(1)


def choose(client, link, password=NEW_PASSWORD, again=None):
    return post(client, "/reset/" + link,
                data={"password": password, "password_again": password if again is None else again})


def record_of(data_dir, name):
    return read_json(data_dir / "members" / name / "member.json")


def token_files(data_dir):
    folder = data_dir / "tokens"
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


def sent_link(client, outbox, given=MEMBER):
    assert SAID in page(ask(client, given))
    return link_in(outbox.sent[-1])


# ---- the login page, and /forgot ----------------------------------------------

def test_the_login_page_offers_the_email_link_alone(visitor):
    said = page(visitor.get("/login"))
    assert '<p class="muted">Forgotten your password? <a href="/forgot">We can email you a link.</a></p>' in said
    assert "twelve words" not in said


def test_the_page_asks_for_a_name_or_an_address(visitor):
    said = page(visitor.get("/forgot"))
    assert "<h1>a forgotten password</h1>" in said
    assert '<label for="given">your commons name or email address</label>' in said
    assert 'name="given"' in said and 'name="csrf_token"' in said
    assert "Send me a link" in said
    assert SAID not in said


def test_one_sentence_for_a_member_the_keeper_and_no_one(member, keeper, visitor, outbox):
    answers = [page(ask(visitor, given)) for given in (
        MEMBER, MEMBER_ADDRESS.upper(), FOUNDER_NAME, KEEPER_ADDRESS, "nobody",
        "nobody@example.org", "", "../members", "x" * 300)]
    assert len(set(answers)) == 1
    assert SAID in answers[0] and 'name="given"' not in answers[0]
    for address in (MEMBER_ADDRESS, KEEPER_ADDRESS, MEMBER, FOUNDER_NAME):
        assert address not in answers[0]
    # four sent: two to the member, two to the keeper, and none for anyone else
    assert [sent["to"] for sent in outbox.sent] == [MEMBER_ADDRESS] * 2 + [KEEPER_ADDRESS] * 2


def test_a_member_by_name_or_address_is_sent_a_link_kept_only_by_its_hash(
        member, visitor, outbox, data_dir):
    link = sent_link(visitor, outbox, MEMBER)
    [sent] = outbox.sent
    assert sent["to"] == MEMBER_ADDRESS
    assert sent["subject"] == "Choose a new password for Tesserae"
    assert sent["text"] == (
        "A new password was asked for the account on Tesserae that uses this address. "
        "Your name there is birch. To choose one, open this link within an hour; it works once:\n\n"
        "https://hearth.tesserae.social/reset/" + link + "\n\n"
        "If you didn't ask, ignore this email; your password stays as it is." + FOOTER)
    [kept] = token_files(data_dir)
    assert kept.name.startswith("reset-") and link not in kept.read_text(encoding="utf-8")
    held = read_json(kept)
    assert held["name"] == MEMBER
    assert held["seal"] == vault.fingerprint(record_of(data_dir, MEMBER)["vault"])
    # by address, a newer link takes the older one's place
    newer = sent_link(visitor, outbox, "  " + MEMBER_ADDRESS.upper() + " ")
    assert newer != link and len(token_files(data_dir)) == 1


def test_the_keeper_is_pointed_to_his_twelve_words_and_no_link_is_made(
        keeper, visitor, outbox, data_dir, hearth):
    before = (data_dir / "members" / FOUNDER_NAME / "member.json").read_bytes()
    for given in (FOUNDER_NAME, KEEPER_ADDRESS):
        assert SAID in page(ask(visitor, given))
    assert token_files(data_dir) == []
    for sent in outbox.sent:
        assert sent["to"] == KEEPER_ADDRESS
        assert sent["subject"] == "Your password on Tesserae"
        assert sent["text"] == (
            "A new password was asked for the account on Tesserae that uses this address. "
            "That account opens with its twelve words, not by email: use them at "
            "https://hearth.tesserae.social/recover.\n\n"
            "If you didn't ask, ignore this email; nothing has changed." + FOOTER)
        assert "/reset/" not in sent["text"]
    assert (data_dir / "members" / FOUNDER_NAME / "member.json").read_bytes() == before
    assert not (data_dir / "members" / FOUNDER_NAME / "key-history.json").exists()


def test_a_reset_link_made_for_the_keeper_by_hand_is_still_shut(keeper, visitor, hearth, data_dir):
    record = record_of(data_dir, FOUNDER_NAME)
    link = hearth.tokens.issue("reset", FOUNDER_NAME, timedelta(hours=1),
                               seal=vault.fingerprint(record["vault"]))
    assert visitor.get("/reset/" + link).status_code == 410
    answer = choose(visitor, link)
    assert answer.status_code == 410 and NOT_OPEN in page(answer)
    assert record_of(data_dir, FOUNDER_NAME) == record


def test_no_one_is_sent_anything_and_nothing_is_written(hearth, visitor, outbox, data_dir):
    for given in ("nobody", "nobody@example.org"):
        assert SAID in page(ask(visitor, given))
    assert outbox.sent == [] and token_files(data_dir) == []


def test_an_address_not_yet_confirmed_is_sent_nothing(member, visitor, outbox, data_dir):
    member.members.set_email(MEMBER, MEMBER_ADDRESS, confirmed_at=None)
    for given in (MEMBER, MEMBER_ADDRESS):
        assert SAID in page(ask(visitor, given))
    assert outbox.sent == [] and token_files(data_dir) == []


def test_an_email_that_cannot_go_changes_nothing_on_the_page(member, visitor, outbox):
    outbox.says = "not sent: unreachable"
    assert SAID in page(ask(visitor, MEMBER))


def test_the_form_must_come_from_here(member, visitor, outbox):
    answer = visitor.post("/forgot", data={"given": MEMBER})
    assert answer.status_code == 400 and outbox.sent == []


# ---- the limits -----------------------------------------------------------------

def test_five_asks_an_hour_from_one_address(member, visitor, outbox, pinned):
    for _ in range(4):
        ask(visitor, "nobody")
    ask(visitor, MEMBER)  # the fifth
    assert len(outbox.sent) == 1
    assert SAID in page(ask(visitor, MEMBER))  # the sixth: the same line, and nothing sent
    assert len(outbox.sent) == 1
    pinned.shift(hours=1, seconds=1)
    ask(visitor, MEMBER)
    assert len(outbox.sent) == 2


def from_address(hearth, address):
    client = hearth.app.test_client()
    client.environ_base["REMOTE_ADDR"] = address
    return client


def test_three_emails_an_hour_to_one_person(member, hearth, outbox, pinned):
    for n in range(5):  # from five addresses, so that only the person's count is reached
        client = from_address(hearth, "10.0.0.%d" % n)
        assert SAID in page(ask(client, MEMBER if n % 2 else MEMBER_ADDRESS))
    assert len(outbox.sent) == 3
    pinned.shift(hours=1, seconds=1)
    ask(from_address(hearth, "10.0.0.9"), MEMBER)
    assert len(outbox.sent) == 4


def test_the_day_s_ceiling_stands_behind_both(member, visitor, outbox, monkeypatch):
    monkeypatch.setattr(member.mail, "MAIL_A_DAY", 0)
    assert SAID in page(ask(visitor, MEMBER))
    assert outbox.sent == []


# ---- the link ---------------------------------------------------------------------

def test_opening_the_link_does_nothing_but_show_a_form(member, visitor, outbox, data_dir):
    link = sent_link(visitor, outbox)
    before = record_of(data_dir, MEMBER)
    for _ in range(2):
        answer = visitor.get("/reset/" + link)
        said = page(answer)
        assert answer.status_code == 200
        assert "<h1>a new password</h1>" in said
        assert RESET_SAID in said
        for field in ('name="password"', 'name="password_again"', 'name="csrf_token"'):
            assert field in said, field
        assert "Choose the new password" in said
    assert record_of(data_dir, MEMBER) == before and len(token_files(data_dir)) == 1


def test_choosing_cuts_a_new_key_records_the_old_and_signs_in(
        member, visitor, outbox, data_dir, pinned):
    link = sent_link(visitor, outbox)
    before = record_of(data_dir, MEMBER)
    answer = choose(visitor, link)
    assert answer.status_code == 302 and answer.headers["Location"] == "/"
    after = record_of(data_dir, MEMBER)
    assert after["verify_key"] != before["verify_key"]
    assert {k: v for k, v in after.items() if k not in ("verify_key", "vault")} == \
        {k: v for k, v in before.items() if k not in ("verify_key", "vault")}
    [history] = read_json(data_dir / "members" / MEMBER / "key-history.json")
    assert history["old_key"] == before["verify_key"] and history["new_key"] == after["verify_key"]
    assert vault.unlock(after["vault"], NEW_PASSWORD)  # the new password opens the new key
    with pytest.raises(vault.VaultError):
        vault.unlock(after["vault"], MEMBER_PASSWORD)
    assert token_files(data_dir) == []
    with visitor.session_transaction() as held:
        assert held["member"] == MEMBER
    assert visitor.get("/account").status_code == 200
    # and the address is told, without the link
    changed = outbox.sent[-1]
    assert changed["to"] == MEMBER_ADDRESS
    assert changed["subject"] == "Your password on Tesserae was changed"
    assert changed["text"] == (
        "The password for birch on Tesserae was changed on 15 October 2026. If that wasn't you, "
        "choose a new one at https://hearth.tesserae.social/forgot." + FOOTER)


def test_the_words_the_new_key_was_cut_with_appear_nowhere(
        member, visitor, outbox, data_dir, monkeypatch):
    handed = []
    real = vault.make_vault

    def keeping(password):
        made = real(password)
        handed.append(made[1])
        return made

    monkeypatch.setattr(member.vault, "make_vault", keeping)
    link = sent_link(visitor, outbox)
    answer = choose(visitor, link)
    [phrase] = handed
    assert phrase not in page(answer)
    with visitor.session_transaction() as held:
        assert phrase not in json.dumps(dict(held))
    for path in data_dir.rglob("*"):
        if path.is_file():
            assert phrase.encode("utf-8") not in path.read_bytes(), path


def test_every_other_session_of_the_member_ends(member, hearth, visitor, outbox):
    elsewhere = hearth.app.test_client()
    assert post(elsewhere, "/login", data={"pseudonym": MEMBER,
                                           "password": MEMBER_PASSWORD}).status_code == 302
    assert elsewhere.get("/account").status_code == 200
    choose(visitor, sent_link(visitor, outbox))
    answer = elsewhere.get("/account")
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/login")


def test_a_signature_made_before_a_reset_still_verifies_after_it(member, visitor, outbox):
    """A witness mark signed with the old key holds against the member's identity
    document after the reset, by the key it was signed with, now marked as past;
    the newest key is the one for signing, and the old mark does not hold against it."""
    import base64
    import witness

    old_key = vault.unlock(member.members.load_member(MEMBER)["vault"], MEMBER_PASSWORD)
    mark = {"v": 1, "bond_id": "a-bond", "bond_commitment": "0" * 64,
            "witness_did": "did:web:hearth.tesserae.social:ids:" + MEMBER,
            "witness_name": MEMBER, "at": "2026-10-15T12:00:00Z", "line": "I saw it sealed."}
    mark["signature"] = base64.b64encode(old_key.sign(witness.payload(mark)).signature).decode()

    def document():
        answer = visitor.get("/ids/%s/did.json" % MEMBER)
        assert answer.status_code == 200
        return json.loads(page(answer))

    def holding(doc):
        return [method["id"] for method in doc["verificationMethod"]
                if witness.holds(mark, base64.b64decode(method["publicKeyBase64"]))]

    before = document()
    assert holding(before) == [before["id"] + "#key-1"]

    choose(visitor, sent_link(visitor, outbox))
    after = document()
    assert after["id"] == before["id"]
    assert holding(after) == [after["id"] + "#key-1"]  # still held, by the old key
    [old] = [m for m in after["verificationMethod"] if m["id"].endswith("#key-1")]
    assert old["publicKeyBase64"] == before["verificationMethod"][0]["publicKeyBase64"]
    assert "pastSince" in old
    assert after["assertionMethod"] == [after["id"] + "#key-2"]
    [current] = [m for m in after["verificationMethod"] if m["id"] in after["assertionMethod"]]
    assert "pastSince" not in current
    assert not witness.holds(mark, base64.b64decode(current["publicKeyBase64"]))
    # and what the member signs from now on holds against the current key
    new_key = vault.unlock(member.members.load_member(MEMBER)["vault"], NEW_PASSWORD)
    fresh = dict(mark, at="2026-10-15T13:00:00Z")
    fresh.pop("signature")
    fresh["signature"] = base64.b64encode(new_key.sign(witness.payload(fresh)).signature).decode()
    assert witness.holds(fresh, base64.b64decode(current["publicKeyBase64"]))


def test_the_link_works_once(member, visitor, outbox, data_dir):
    link = sent_link(visitor, outbox)
    assert choose(visitor, link).status_code == 302
    key = record_of(data_dir, MEMBER)["verify_key"]
    for answer in (visitor.get("/reset/" + link), choose(visitor, link, "yet another password")):
        assert answer.status_code == 410 and NOT_OPEN in page(answer)
    assert record_of(data_dir, MEMBER)["verify_key"] == key


def test_two_posts_at_once_make_one_new_key(member, hearth, visitor, outbox, data_dir):
    link = sent_link(visitor, outbox)
    clients = [hearth.app.test_client() for _ in range(2)]
    for client in clients:
        client.get("/reset/" + link)  # each cuts its own form token
    answers = []
    start = threading.Barrier(2)

    def go(client, password):
        start.wait()
        answers.append(choose(client, link, password).status_code)

    threads = [threading.Thread(target=go, args=(client, "password number %d!" % n))
               for n, client in enumerate(clients)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(answers) == [302, 410]
    assert len(read_json(data_dir / "members" / MEMBER / "key-history.json")) == 1


def test_the_link_lasts_an_hour(member, visitor, outbox, pinned):
    link = sent_link(visitor, outbox)
    pinned.shift(minutes=59)
    assert visitor.get("/reset/" + link).status_code == 200
    pinned.shift(minutes=1)
    for answer in (visitor.get("/reset/" + link), choose(visitor, link)):
        assert answer.status_code == 410 and NOT_OPEN in page(answer)


def test_a_password_changed_since_shuts_the_link(member, visitor, outbox, data_dir):
    link = sent_link(visitor, outbox)
    record = record_of(data_dir, MEMBER)
    member.members.replace_vault(MEMBER, vault.change_password(
        record["vault"], MEMBER_PASSWORD, "changed on the account page"))
    for answer in (visitor.get("/reset/" + link), choose(visitor, link)):
        assert answer.status_code == 410 and NOT_OPEN in page(answer)
    assert not (data_dir / "members" / MEMBER / "key-history.json").exists()


def test_a_newer_link_shuts_the_older(member, visitor, outbox):
    older = sent_link(visitor, outbox)
    newer = sent_link(visitor, outbox)
    assert visitor.get("/reset/" + older).status_code == 410
    assert visitor.get("/reset/" + newer).status_code == 200


@pytest.mark.parametrize("link", ["x" * 43, "short", "../../members/birch/member"])
def test_a_link_no_one_was_sent_is_shut(member, visitor, link):
    answer = visitor.get("/reset/" + link)
    assert answer.status_code in (404, 410)
    if answer.status_code == 410:
        assert NOT_OPEN in page(answer)


def test_passwords_that_differ_or_will_not_do_leave_the_link_open(member, visitor, outbox, data_dir):
    link = sent_link(visitor, outbox)
    before = record_of(data_dir, MEMBER)
    said = page(choose(visitor, link, NEW_PASSWORD, "something else entirely"))
    assert "The two new passwords are not the same." in said
    said = page(choose(visitor, link, "short"))
    assert 'class="error"' in said and 'name="password"' in said
    assert record_of(data_dir, MEMBER) == before and len(token_files(data_dir)) == 1
    assert choose(visitor, link).status_code == 302


def test_the_pages_that_carry_a_link_are_kept_out_of_caches_and_indexes(member, visitor, outbox):
    link = sent_link(visitor, outbox)
    for answer in (visitor.get("/reset/" + link), visitor.get("/reset/" + "x" * 43)):
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


def test_the_button_works_with_what_a_browser_sends_from_the_page(
        member, visitor, outbox, data_dir):
    link = sent_link(visitor, outbox)
    address = "/reset/" + link
    before = record_of(data_dir, MEMBER)
    shown = visitor.get(address)
    form = re.search(r'name="csrf_token" value="([^"]+)"', page(shown)).group(1)
    answer = visitor.post(address, headers=as_a_browser_sends_it(shown, address), data={
        "csrf_token": form, "password": NEW_PASSWORD, "password_again": NEW_PASSWORD})
    assert answer.status_code == 302 and answer.headers["Location"] == "/", page(answer)
    assert record_of(data_dir, MEMBER)["verify_key"] != before["verify_key"]


# ---- kept out of every log ------------------------------------------------------

def test_no_address_name_or_link_is_written_down_or_printed(
        member, keeper, visitor, outbox, data_dir, caplog):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), caplog.at_level("DEBUG"):
        ask(visitor, MEMBER_ADDRESS)
        ask(visitor, KEEPER_ADDRESS)
        ask(visitor, "nobody@example.org")
        link = link_in(outbox.sent[0])
        choose(visitor, link)
    told = out.getvalue() + err.getvalue() + caplog.text
    log = (data_dir / "mail.log").read_text(encoding="utf-8")
    for secret in (MEMBER_ADDRESS, KEEPER_ADDRESS, "nobody@example.org", link, "/reset/"):
        assert secret not in told and secret not in log, secret
    assert [line.split(" · ", 1)[1] for line in log.splitlines()] == [
        "reset · sent", "reset-keeper · sent", "changed · sent"]
    # and no file outside the members' own holds an address or the link
    for path in data_dir.rglob("*"):
        if path.is_file() and path.name != "email.json":
            held = path.read_bytes()
            for secret in (MEMBER_ADDRESS, KEEPER_ADDRESS, link):
                assert secret.encode("utf-8") not in held, (path, secret)
