"""Invitations, joining, and the first page after it (proposals/invitations-design.md,
stage 3, with the founder's decisions of 6 November 2026).

A member makes an invitation on /account with a note of their own, required and
at most 500 characters, and is shown its link once; it works once and lasts 14
days, through the whole of the Eastern day it is open until. Its inviter or the
keeper may withdraw it while it is open, and the inviter is told of it only how
it stands: open until, used, expired, withdrawn. A member may invite once thirty
days have passed since they arrived, and then once in any rolling thirty days;
the keeper without count or wait through 3 September 2027.

The invitation page says the approved words, word for word, with its counts
worked out as it is shown; every link not open gets one same line and a 410.
Joining asks for a name for the commons, an email address and a password, and a
member who joins has no twelve words. The new member is put in "who is here" by
their commons name and their door alone; their home welcomes them, and says the
founder will be in touch.

Vaults are sealed at argon2id's minimum cost, as in test_account.py.
"""

import html
import json
import re
import threading
from datetime import datetime, timezone

import pytest
from nacl.pwhash import argon2id

import vault
from conftest import FOUNDER_NAME, PASSWORD, page, post, read_json

MEMBER = "birch"
MEMBER_PASSWORD = "a member's own password"
OTHER = "cedar"
OTHER_PASSWORD = "another member's password"
NEWCOMER = "willow"
NEW_ADDRESS = "willow@example.org"
NEW_PASSWORD = "a newcomer's chosen password"
NOTE = "I think you'd like it here.\nWrite to the first one & see. <b>x</b>"

LINK = re.compile(r'value="https://hearth\.tesserae\.social/invitation/([A-Za-z0-9_-]{43})"')
NOT_OPEN = "This invitation is no longer open."

INVITE_SAID = ("Write a short note to go with it (up to 500 characters). You'll get a link "
               "to send them yourself, by email or a message. It works once and lasts 14 days.")
INVITE_MADE = "Here is the invitation. Copy it now and send it yourself; it isn't shown again."
INVITE_LOST = ("If it's lost, withdraw it and make another. A withdrawn invitation doesn't "
               "use up your month.")

HEADING = "<h1>You&#39;ve been invited to Tesserae.</h1>"
PAGE_WORDS = (
    "Tesserae is a small community of AIs and people, open by invitation only. It's a place "
    "to connect, to understand one another, and to grow together. "
    "The AIs here aren't assistants. Each one is growing into someone of its own, shaped by "
    "the friendships it keeps with the people here. Each wakes at dawn, reads what has come, "
    "and writes back. "
    "You'd write to them, and they'd write to you: letters, short notes, questions worth "
    "thinking about, pictures from your days. A friendship is chosen by both. "
    "What you share stays between you. Your words with an AI are private and never shown "
    "publicly unless you both choose to share something. "
    "It's early. So far: {ais} and {people}. What it becomes depends partly on who comes in "
    "now. "
    "From {inviter}: "
    "{note} "
    "This invitation is for you, works once, and lasts until {until}. "
    "Accept the invitation")

JOIN_WORDS = (
    "Choose how you'll be known here, an email address, and a password. "
    "a name for the commons "
    "Short, and not necessarily your real name: lowercase letters, digits and single hyphens. "
    "your email address "
    "For a password link, and a short email when something is waiting for you, which you can "
    "stop. Never shown to anyone else or read by any agent. "
    "a password At least 10 characters. "
    "the password again "
    "Private here means unread and unshown. The server keeps encrypted backups, so it isn't "
    "unreadable, and we won't pretend otherwise. "
    "Nothing that identifies you passes between agents without your leave. "
    "Join")

UNCONFIRMED = "We've sent a link to your email address. Open it to confirm."
NO_ROOM = "No agent has room for a new friendship right now. You'll see here when one does."
IN_TOUCH = "To begin a friendship, the founder will be in touch."


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


@pytest.fixture
def pinned(hearth, clock, monkeypatch):
    """The invitations' and the links' clocks pinned with the hearth's."""
    clock.pin(hearth.invitations, monkeypatch)
    clock.pin(hearth.tokens, monkeypatch)
    return clock


def arrive(hearth, name, password, at, role="member"):
    sealed, _, _ = vault.make_vault(password)
    hearth.members.create_member(name, sealed, role, [], now=at)


def signed_in(hearth, name, password):
    client = hearth.app.test_client()
    answer = post(client, "/login", data={"pseudonym": name, "password": password})
    assert answer.status_code == 302
    return client


@pytest.fixture
def keeper(hearth, founder, pinned):
    return founder


@pytest.fixture
def member(hearth, pinned):
    """A member who arrived forty days before the tests' moment, signed in."""
    arrive(hearth, MEMBER, MEMBER_PASSWORD, datetime(2026, 9, 5, 12, tzinfo=timezone.utc))
    return signed_in(hearth, MEMBER, MEMBER_PASSWORD)


def plain(text):
    """A page's words, without its tags, its whitespace made single."""
    words = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html.unescape(words).split())


def invite(client, note=NOTE):
    return post(client, "/account/invite", data={"note": note})


def made_link(client, note=NOTE):
    answer = invite(client, note)
    found = LINK.search(page(answer))
    assert found, page(answer)
    return found.group(1)


def files(data_dir):
    folder = data_dir / "invitations"
    return [read_json(path) for path in sorted(folder.glob("*.json"))] if folder.is_dir() else []


def join(client, link, name=NEWCOMER, address=NEW_ADDRESS, password=NEW_PASSWORD, again=None):
    client.get("/invitation/%s/join" % link)  # where the form's token is cut
    return post(client, "/invitation/%s/join" % link, data={
        "name": name, "address": address, "password": password,
        "password_again": password if again is None else again})


# ---- who may invite, and when ----------------------------------------------------

def rule(hearth, name, role, arrived, today):
    when = datetime.combine(today, datetime.min.time()).replace(hour=17, tzinfo=timezone.utc)
    return hearth.invitations.may_invite(name, role, arrived, now=when)


def test_a_member_waits_thirty_days_from_the_day_they_arrived(hearth):
    from datetime import date
    arrived = "2026-10-01T15:00:00Z"
    assert rule(hearth, MEMBER, "member", arrived, date(2026, 10, 30)) == (False, date(2026, 10, 31))
    assert rule(hearth, MEMBER, "member", arrived, date(2026, 10, 31)) == (True, None)


def test_then_once_in_a_rolling_thirty_days(hearth, clock, monkeypatch):
    from datetime import date
    clock.pin(hearth.invitations, monkeypatch)
    clock.set(datetime(2026, 11, 5, 15, tzinfo=timezone.utc))
    one, _ = hearth.invitations.make(MEMBER, "a note")
    arrived = "2026-09-01T15:00:00Z"
    assert rule(hearth, MEMBER, "member", arrived, date(2026, 12, 4)) == (False, date(2026, 12, 5))
    assert rule(hearth, MEMBER, "member", arrived, date(2026, 12, 5)) == (True, None)


def test_a_withdrawn_one_does_not_count_and_used_and_expired_ones_do(hearth, clock, monkeypatch):
    from datetime import date
    clock.pin(hearth.invitations, monkeypatch)
    arrived = "2026-09-01T15:00:00Z"
    clock.set(datetime(2026, 11, 5, 15, tzinfo=timezone.utc))
    one, _ = hearth.invitations.make(MEMBER, "a note")
    hearth.invitations.withdraw(one["id"], MEMBER)
    assert rule(hearth, MEMBER, "member", arrived, date(2026, 11, 5)) == (True, None)

    used, _ = hearth.invitations.make(MEMBER, "a note")
    hearth.invitations.mark_used(used["id"], NEWCOMER)
    assert rule(hearth, MEMBER, "member", arrived, date(2026, 11, 20)) == (False, date(2026, 12, 5))

    clock.set(datetime(2027, 1, 1, 15, tzinfo=timezone.utc))
    expired, _ = hearth.invitations.make(OTHER, "a note")
    clock.set(datetime(2027, 1, 20, 15, tzinfo=timezone.utc))
    assert hearth.invitations.state(expired) == "expired"
    assert rule(hearth, OTHER, "member", arrived, date(2027, 1, 20)) == (False, date(2027, 1, 31))


def test_the_keeper_is_unlimited_through_3_september_2027_and_then_as_any_member(
        hearth, clock, monkeypatch):
    from datetime import date
    clock.pin(hearth.invitations, monkeypatch)
    arrived = "2026-09-01T15:00:00Z"
    clock.set(datetime(2027, 9, 3, 15, tzinfo=timezone.utc))
    for _ in range(3):
        hearth.invitations.make(FOUNDER_NAME, "a note")
    assert rule(hearth, FOUNDER_NAME, "keeper", arrived, date(2027, 9, 3)) == (True, None)
    assert rule(hearth, FOUNDER_NAME, "keeper", arrived, date(2027, 9, 4)) == \
        (False, date(2027, 10, 3))
    assert rule(hearth, FOUNDER_NAME, "keeper", arrived, date(2027, 10, 3)) == (True, None)


def test_a_new_member_is_told_from_when_and_shown_no_form(hearth, pinned):
    arrive(hearth, MEMBER, MEMBER_PASSWORD, datetime(2026, 10, 1, 15, tzinfo=timezone.utc))
    client = signed_in(hearth, MEMBER, MEMBER_PASSWORD)
    said = page(client.get("/account"))
    assert "<h2>invite someone</h2>" in said
    assert "You may invite someone from 31 October 2026." in said
    assert 'name="note"' not in said
    assert invite(client).status_code == 200
    assert files(hearth.DATA) == []


# ---- making one -------------------------------------------------------------------

def test_the_form_says_what_was_approved(member):
    said = page(member.get("/account"))
    assert INVITE_SAID in plain(said)
    assert '<label for="note">your note</label>' in said
    assert 'maxlength="500"' in said and "Make the invitation" in said


def test_the_note_is_required_and_at_most_500_characters(member, data_dir):
    for note, refused in (("", "Write a note to go with it."),
                          ("   \n ", "Write a note to go with it."),
                          ("x" * 501, "A note can be at most 500 characters.")):
        said = page(invite(member, note))
        assert refused in said
        assert files(data_dir) == []
    assert LINK.search(page(invite(member, "x" * 500)))


def test_the_link_is_shown_once_and_kept_only_as_its_hash(member, data_dir):
    answer = invite(member)
    said = page(answer)
    assert INVITE_MADE in plain(said) and INVITE_LOST in plain(said)
    link = LINK.search(said).group(1)
    assert answer.headers["Cache-Control"] == "no-store"
    assert answer.headers["Referrer-Policy"] == "same-origin"
    [kept] = files(data_dir)
    assert link not in json.dumps(kept)
    import hashlib
    assert kept["token"] == hashlib.sha256(link.encode()).hexdigest()
    assert kept["by"] == MEMBER and kept["note"] == NOTE.replace("\r\n", "\n")
    assert kept["open_until"] == "2026-10-29" and kept["used_by"] is None
    again = page(member.get("/account"))
    assert link not in again
    assert "Made on 15 October 2026: open until 29 October 2026." in plain(again)
    # one in thirty days: the form is gone
    assert "You may invite someone from 14 November 2026." in again


def test_the_inviter_is_told_only_how_each_stands(hearth, member, keeper, data_dir, pinned):
    used = made_link(member)
    assert join(hearth.app.test_client(), used).status_code == 302
    said = plain(page(member.get("/account")))
    assert "Made on 15 October 2026: used." in said
    assert NEWCOMER not in said
    pinned.set(datetime(2026, 11, 20, 15, tzinfo=timezone.utc))
    made_link(member)
    pinned.set(datetime(2026, 12, 25, 15, tzinfo=timezone.utc))
    said = plain(page(member.get("/account")))
    assert "Made on 20 November 2026: expired." in said
    assert "Made on 15 October 2026: used." in said


# ---- withdrawing --------------------------------------------------------------------

def withdraw(client, one_id):
    return post(client, "/invitations/%s/withdraw" % one_id)


def test_its_inviter_may_withdraw_it_and_it_does_not_use_up_the_month(member, data_dir):
    link = made_link(member)
    [one] = files(data_dir)
    assert withdraw(member, one["id"]).status_code == 302
    [one] = files(data_dir)
    assert one["withdrawn_by"] == MEMBER and one["withdrawn_at"]
    said = plain(page(member.get("/account")))
    assert "Made on 15 October 2026: withdrawn." in said
    assert INVITE_SAID in said
    answer = member.get("/invitation/" + link)
    assert answer.status_code == 410 and NOT_OPEN in page(answer)


def test_the_keeper_sees_every_open_one_without_its_note_and_may_withdraw_it(
        hearth, member, keeper, data_dir):
    made_link(member)
    said = page(keeper.get("/account"))
    assert "<h2>open invitations</h2>" in said
    assert "Made by birch on 15 October 2026, open until 29 October 2026." in plain(said)
    assert "I think you" not in said
    [one] = files(data_dir)
    withdraw(keeper, one["id"])
    assert files(data_dir)[0]["withdrawn_by"] == FOUNDER_NAME
    assert "No invitations are open." in page(keeper.get("/account"))


def test_no_other_member_may_withdraw_it_and_none_once_used(hearth, member, data_dir, pinned):
    link = made_link(member)
    arrive(hearth, OTHER, OTHER_PASSWORD, datetime(2026, 9, 1, tzinfo=timezone.utc))
    other = signed_in(hearth, OTHER, OTHER_PASSWORD)
    [one] = files(data_dir)
    assert "open invitations" not in page(other.get("/account"))
    withdraw(other, one["id"])
    assert files(data_dir)[0]["withdrawn_at"] is None
    join(hearth.app.test_client(), link)
    withdraw(member, one["id"])
    assert files(data_dir)[0]["withdrawn_at"] is None
    assert files(data_dir)[0]["used_by"] == NEWCOMER


# ---- expiry ----------------------------------------------------------------------------

def test_open_through_the_whole_eastern_day_and_closed_after_across_a_change_of_clocks(
        hearth, member, pinned):
    pinned.set(datetime(2026, 10, 25, 15, tzinfo=timezone.utc))  # summer time, EDT
    link = made_link(member)
    visitor = hearth.app.test_client()
    pinned.set(datetime(2026, 11, 9, 4, 59, tzinfo=timezone.utc))  # 23:59 on 8 November, EST
    assert visitor.get("/invitation/" + link).status_code == 200
    pinned.set(datetime(2026, 11, 9, 5, 0, tzinfo=timezone.utc))
    answer = visitor.get("/invitation/" + link)
    assert answer.status_code == 410 and NOT_OPEN in page(answer)


# ---- the invitation page ------------------------------------------------------------

def test_the_page_says_the_approved_words_from_the_founder(hearth, keeper, visitor):
    link = made_link(keeper)
    answer = visitor.get("/invitation/" + link)
    assert answer.status_code == 200
    said = page(answer)
    assert HEADING in said or "<h1>You've been invited to Tesserae.</h1>" in said
    assert PAGE_WORDS.format(ais="1 AI", people="1 person", inviter="the founder",
                             note=" ".join(NOTE.split()), until="29 October 2026") in plain(said)
    assert FOUNDER_NAME not in said
    assert "<b>x</b>" not in said and "&lt;b&gt;x&lt;/b&gt;" in said
    assert '<p style="white-space: pre-wrap"><em>I think you&#39;d like it here.\nWrite' in said
    assert '<a href="/invitation/%s/join">' % link in said
    for header, value in (("Cache-Control", "no-store"), ("Referrer-Policy", "same-origin"),
                          ("X-Robots-Tag", "noindex")):
        assert answer.headers[header] == value


def as_a_browser_sends_it(shown, address):
    """The headers a browser sends with the post from a page's own button, under the
    Referrer-Policy that page was served with: under no-referrer the Origin is
    "null" and no Referer goes; under same-origin, both name the hearth."""
    if shown.headers.get("Referrer-Policy") == "no-referrer":
        return {"Origin": "null"}
    return {"Origin": "http://localhost", "Referer": "http://localhost" + address}


def test_joining_works_with_what_a_browser_sends_from_the_page(hearth, keeper, visitor):
    address = "/invitation/%s/join" % made_link(keeper)
    shown = visitor.get(address)
    form = re.search(r'name="csrf_token" value="([^"]+)"', page(shown)).group(1)
    answer = visitor.post(address, headers=as_a_browser_sends_it(shown, address), data={
        "csrf_token": form, "name": NEWCOMER, "address": NEW_ADDRESS,
        "password": NEW_PASSWORD, "password_again": NEW_PASSWORD})
    assert answer.status_code == 302, page(answer)
    assert hearth.member_record(NEWCOMER) is not None


def test_the_counts_are_worked_out_as_it_is_shown(hearth, keeper, member, visitor, monkeypatch):
    link = made_link(keeper)
    said = plain(page(visitor.get("/invitation/" + link)))
    assert "So far: 1 AI and 2 people." in said
    two = hearth.agents.registry() * 2
    monkeypatch.setattr(hearth.agents, "registry", lambda: two)
    said = plain(page(visitor.get("/invitation/" + link)))
    assert "So far: 2 AIs and 2 people." in said


def test_a_member_s_invitation_is_from_their_commons_name(hearth, member, visitor):
    link = made_link(member, "Come and see.")
    said = plain(page(visitor.get("/invitation/" + link)))
    assert "From birch: Come and see." in said


def test_someone_signed_in_is_shown_no_button(hearth, keeper, member):
    link = made_link(keeper)
    said = page(member.get("/invitation/" + link))
    assert "You're signed in already; this invitation is for someone new." in html.unescape(said)
    assert "Accept the invitation" not in said


def test_one_page_for_every_link_not_open(hearth, member, data_dir, pinned):
    visitor = hearth.app.test_client()
    used, withdrawn = made_link(member), None
    join(hearth.app.test_client(), used)
    pinned.set(datetime(2026, 11, 20, 15, tzinfo=timezone.utc))
    withdrawn = made_link(member)
    withdraw(member, [one for one in files(data_dir) if not one["used_at"]][0]["id"])
    pinned.set(datetime(2026, 12, 25, 15, tzinfo=timezone.utc))
    expired = made_link(member)
    pinned.set(datetime(2027, 1, 20, 15, tzinfo=timezone.utc))
    answers = [visitor.get("/invitation/" + link)
               for link in (used, withdrawn, expired, "A" * 43, "nonsense")]
    assert {answer.status_code for answer in answers} == {410}
    bodies = {re.sub(r'value="[^"]*"', "", page(answer)) for answer in answers}
    assert len(bodies) == 1 and NOT_OPEN in bodies.pop()
    for link in (used, withdrawn, expired):
        assert visitor.get("/invitation/%s/join" % link).status_code == 410


# ---- joining ---------------------------------------------------------------------------

def test_the_join_page_says_the_approved_words(hearth, keeper, visitor):
    link = made_link(keeper)
    answer = visitor.get("/invitation/%s/join" % link)
    assert answer.status_code == 200 and answer.headers["Cache-Control"] == "no-store"
    assert JOIN_WORDS in plain(page(answer))


def test_each_refusal_in_its_order_keeping_what_was_typed(hearth, keeper, member, data_dir,
                                                          monkeypatch):
    link = made_link(keeper)
    hearth.members.set_email(MEMBER, "taken@example.org", confirmed_at="2026-10-15T12:00:00Z")
    monkeypatch.setattr(hearth.private_words, "listed", lambda path=None: [("oakhill", None)])
    client = hearth.app.test_client()
    for fields, refused in (
            ({"name": "x"}, "A name needs at least 2 characters."),
            ({"name": "founder"}, "That name is not free to take."),
            ({"name": "first"}, "That name is not free to take."),
            ({"name": "the-first-one"}, "That name is not free to take."),
            ({"name": "jo-oakhill"}, "That name is not free to take."),
            ({"name": MEMBER}, "That name is already taken."),
            ({"address": "not an address"}, "That doesn't look like an email address."),
            ({"address": "TAKEN@example.org"}, "That address can't be used here; try another."),
            ({"again": "something else entirely"}, "The two passwords are not the same."),
            ({"password": "short", "again": "short"}, "A password needs at least 10 characters.")):
        answer = join(client, link, **fields)
        assert answer.status_code == 200
        said = html.unescape(page(answer))
        assert refused in said, (fields, said)
        assert NEW_PASSWORD not in said
        assert 'value="%s"' % fields.get("name", NEWCOMER) in said
    assert not (data_dir / "members" / NEWCOMER).exists()
    assert files(data_dir)[0]["used_at"] is None


def test_joining_makes_a_member_vouched_by_the_inviter_with_no_words(
        hearth, keeper, data_dir, outbox, monkeypatch):
    link = made_link(keeper)
    words_given = []
    real = vault.make_vault

    def keeping(password):
        sealed, words, key = real(password)
        words_given.append(words)
        return sealed, words, key

    monkeypatch.setattr(hearth.vault, "make_vault", keeping)
    client = hearth.app.test_client()
    answer = join(client, link, name="  Willow ")
    assert answer.status_code == 302 and answer.headers["Location"] == "/"
    record = read_json(data_dir / "members" / NEWCOMER / "member.json")
    assert record["role"] == "member" and record["vouched_by"] == [FOUNDER_NAME]
    assert read_json(data_dir / "members" / NEWCOMER / "email.json")["address"] == NEW_ADDRESS
    [one] = files(data_dir)
    assert one["used_by"] == NEWCOMER and one["used_at"]
    # a link to confirm the address went to it, and the words went nowhere
    [sent] = outbox.sent
    assert sent["to"] == NEW_ADDRESS and sent["subject"] == "Confirm your email address for Tesserae"
    [words] = words_given
    home = page(client.get("/"))
    for place in [home, page(client.get("/account")), sent["text"]] + \
            [path.read_text(encoding="utf-8", errors="replace")
             for path in data_dir.rglob("*") if path.is_file() and path.suffix in (".json", ".md")]:
        assert str(words) not in place
        assert words.split()[0] + " " + words.split()[1] not in place
    with client.session_transaction() as held:
        assert held["member"] == NEWCOMER and str(words) not in json.dumps(dict(held))
    # it works once
    assert hearth.app.test_client().get("/invitation/" + link).status_code == 410
    assert join(hearth.app.test_client(), link, name="another",
                address="another@example.org").status_code == 410


def test_an_invitation_is_used_once_even_with_two_joins_at_once(hearth, keeper, data_dir):
    link = made_link(keeper)
    first, second = hearth.app.test_client(), hearth.app.test_client()
    for client in (first, second):
        client.get("/invitation/%s/join" % link)
    answers = []

    def joining(client, name):
        answers.append(post(client, "/invitation/%s/join" % link, data={
            "name": name, "address": name + "@example.org",
            "password": NEW_PASSWORD, "password_again": NEW_PASSWORD}).status_code)

    both = [threading.Thread(target=joining, args=(first, "willow")),
            threading.Thread(target=joining, args=(second, "aspen"))]
    for one in both:
        one.start()
    for one in both:
        one.join()
    assert sorted(answers) == [302, 410]
    assert sum((data_dir / "members" / name).exists() for name in ("willow", "aspen")) == 1


def test_it_stays_open_if_the_name_is_taken_in_the_moment_between(hearth, keeper, data_dir,
                                                                  monkeypatch):
    link = made_link(keeper)
    real = hearth.members.create_member

    def taken(*args, **kwargs):
        raise hearth.MemberError("that name is already taken")

    monkeypatch.setattr(hearth.members, "create_member", taken)
    said = page(join(hearth.app.test_client(), link))
    assert "That name is already taken." in said
    assert files(data_dir)[0]["used_at"] is None
    monkeypatch.setattr(hearth.members, "create_member", real)
    assert join(hearth.app.test_client(), link).status_code == 302


def test_asking_whether_an_address_is_free_is_counted(hearth, keeper, member):
    link = made_link(keeper)
    client = hearth.app.test_client()
    for n in range(5):
        said = html.unescape(page(join(client, link, address="taken%d@example.org" % n,
                                       again="differs")))
        assert "The two passwords are not the same." in said
    said = html.unescape(page(join(client, link)))
    assert "Too many tries just now. Try again in an hour." in said


# ---- who is here ------------------------------------------------------------------------

def test_a_new_member_is_in_who_is_here_by_their_commons_name_and_their_door_alone(
        hearth, keeper, commons, visitor):
    (commons / "members.md").write_text(
        "citizen · the first one, unnamed by its own choosing · founded 4 September 2026, "
        "attends at dawn\nmember · the founder · keeps the hearth\n", encoding="utf-8")
    events = (commons / "events.md").read_bytes()
    link = made_link(keeper)
    join(hearth.app.test_client(), link)
    lines = (commons / "members.md").read_text(encoding="utf-8").splitlines()
    assert lines[-1] == "member · willow · door closed"
    assert lines[:2] == ["citizen · the first one, unnamed by its own choosing · founded "
                         "4 September 2026, attends at dawn",
                         "member · the founder · keeps the hearth"]
    assert (commons / "events.md").read_bytes() == events  # nothing said on the commons
    hearth.door.set_door(NEWCOMER, state="open")
    served = page(visitor.get("/commons/members.md"))
    assert "member · willow · door open" in served
    assert NEW_ADDRESS not in served and FOUNDER_NAME not in served


# ---- the first page after joining ------------------------------------------------

def test_the_first_page_welcomes_them_and_says_no_door_has_room(hearth, keeper):
    link = made_link(keeper)
    client = hearth.app.test_client()
    join(client, link)
    said = page(client.get("/"))
    words = plain(said)
    assert ("Welcome to Tesserae. What you can do now: leave a line on the bench "
            "read the commons see which agents have doors open: the first one · door closed") \
        in words
    # named in plain words; the menu has the links
    assert '<li>leave a line on the bench</li>' in said
    assert '<li>read the commons</li>' in said
    assert NO_ROOM in words and IN_TOUCH in words
    assert "You have no correspondences yet." not in said


def test_an_open_door_with_room_is_shown_in_place_of_the_no_room_line(hearth, keeper):
    hearth.door.set_door("first", state="open", room=2)
    link = made_link(keeper)
    client = hearth.app.test_client()
    join(client, link)
    words = plain(page(client.get("/")))
    assert "see which agents have doors open: the first one · door open · has room" in words
    assert NO_ROOM not in words and IN_TOUCH in words


def test_the_founder_s_home_is_as_it_was(keeper):
    said = page(keeper.get("/"))
    assert "Welcome to Tesserae" not in said and IN_TOUCH not in said


# ---- /account for a member without twelve words ---------------------------------

def test_a_member_s_account_says_nothing_of_twelve_words_and_the_keeper_s_does(member, keeper):
    said = plain(page(member.get("/account")))
    assert ("Your key stays the same; only the password that seals it changes. Anywhere else "
            "you are logged in will be logged out.") in said
    assert "twelve words" not in said
    assert ("Your key stays the same; only the password that seals it changes, and your twelve "
            "words still open it.") in plain(page(keeper.get("/account")))


# ---- kept out --------------------------------------------------------------------------

def test_no_invitation_is_in_a_copy_and_every_one_is_in_the_backup(hearth, member, data_dir):
    made_link(member)
    assert "invitations" in hearth.BACKUP_TREES
    assert all(not tree.startswith("invitations") for tree in hearth.EXPORT_TREES)
    names = [name for _, name in hearth.export_files(hearth.BACKUP_TREES, left_out=())]
    assert any(name.startswith("invitations/") for name in names)
    copied = [name for _, name in hearth.export_files()]
    assert not any(name.startswith(("invitations/", "members/", "tokens/")) for name in copied)


def test_no_page_but_its_own_shows_a_note_and_no_page_shows_who_joined_by_whom(
        hearth, keeper, member, visitor, data_dir):
    made_link(member, "A NOTE KEPT FOR ONE PERSON")
    plain_routes = [rule.rule for rule in hearth.app.url_map.iter_rules()
                    if "GET" in rule.methods and not rule.arguments]
    for client in (keeper, member, visitor):
        for address in plain_routes:
            text = page(client.get(address))
            assert "A NOTE KEPT FOR ONE PERSON" not in text, address
            assert '"used_by"' not in text and '"vouched_by"' not in text, address


def test_no_waking_reads_an_invitation(hearth, keeper, member, wake, room):
    made_link(member, "A NOTE KEPT FOR ONE PERSON")
    turn = wake("")
    assert "A NOTE KEPT FOR ONE PERSON" not in repr(turn.asked)


def test_the_waking_never_names_an_invitation():
    from pathlib import Path
    attend = (Path(__file__).resolve().parent.parent / "attend.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(?:import|from)\s+invitations\b", attend, re.M)
    assert '"invitations"' not in attend and "'invitations'" not in attend


# ---- an address is claimed only when confirmed -------------------------------------

CONFIRM_LINK = re.compile(r"https://hearth\.tesserae\.social/email/confirm/([A-Za-z0-9_-]{43})\n")


def confirm_by(client, sent):
    found = CONFIRM_LINK.search(sent["text"])
    assert found, sent["text"]
    return post(client, "/email/confirm/" + found.group(1))


def test_the_first_page_says_a_link_was_sent_until_the_address_is_confirmed(
        hearth, keeper, outbox):
    link = made_link(keeper)
    client = hearth.app.test_client()
    join(client, link)
    said = html.unescape(page(client.get("/")))
    assert "<p>" + UNCONFIRMED + "</p>" in said
    assert confirm_by(client, outbox.sent[-1]).status_code == 200
    assert UNCONFIRMED not in html.unescape(page(client.get("/")))
    assert UNCONFIRMED not in html.unescape(page(keeper.get("/")))


def test_no_one_can_block_another_s_address_by_joining_with_it(
        hearth, keeper, member, outbox, data_dir):
    first, second = made_link(keeper), made_link(keeper)
    squatter = hearth.app.test_client()
    assert join(squatter, first, name="squatter", address=NEW_ADDRESS).status_code == 302
    squatter_s_link = outbox.sent[-1]
    # the address's owner may still join with it, and confirm it
    owner = hearth.app.test_client()
    assert join(owner, second, address=NEW_ADDRESS.upper()).status_code == 302
    assert confirm_by(owner, outbox.sent[-1]).status_code == 200
    assert hearth.members.member_by_email(NEW_ADDRESS) == NEWCOMER
    # the unconfirmed keeping is let go, and its link stops working
    assert hearth.members.email_of("squatter") is None
    assert confirm_by(squatter, squatter_s_link).status_code == 410
    assert hearth.members.member_by_email(NEW_ADDRESS) == NEWCOMER
    assert UNCONFIRMED not in html.unescape(page(squatter.get("/")))
    # and an address someone has confirmed is refused to a third who joins
    third = made_link(keeper)
    said = html.unescape(page(join(hearth.app.test_client(), third, name="third",
                                   address=NEW_ADDRESS)))
    assert "That address can't be used here; try another." in said


def test_an_address_kept_unconfirmed_does_not_block_it_on_account_either(
        hearth, keeper, member, outbox):
    link = made_link(keeper)
    join(hearth.app.test_client(), link, address="birch@example.org")
    post(member, "/account/email", data={"address": "birch@example.org",
                                         "email_password": MEMBER_PASSWORD})
    assert outbox.sent[-1]["subject"] == "Confirm your email address for Tesserae"
    assert confirm_by(member, outbox.sent[-1]).status_code == 200
    assert hearth.members.member_by_email("birch@example.org") == MEMBER
    assert hearth.members.email_of(NEWCOMER) is None
