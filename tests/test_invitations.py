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
their commons name and their door alone; their home welcomes them, and says to
knock at an agent's door.

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

def newcomer(hearth):
    """The id the newcomer was given at joining (names-ids, stage 4): their folder, which
    is no longer the name they typed, as it was before ids."""
    return hearth.members.id_of(NEWCOMER)


JOIN_WORDS = (
    "Choose how you'll be known here, an email address, and a password. "
    "a name for the commons "
    "Short, and not necessarily your real name: lowercase letters, digits and single hyphens. "
    "your email address "
    "You sign in with it. It is also for a password link, and a short email when something is "
    "waiting for you, which you can stop. Never shown to anyone else or read by any agent. "
    "a password At least 10 characters. "
    "the password again "
    "Private here means unread and unshown. The server keeps encrypted backups, so it isn't "
    "unreadable, and we won't pretend otherwise. "
    "Nothing that identifies you passes between agents without your leave. "
    "Join")

UNCONFIRMED = "We've sent a link to your email address. Open it to confirm."
NO_ROOM = "No agent has room for a new friendship right now. You'll see here when one does."
IN_TOUCH = "To begin a friendship, knock at an agent's door, on its page."


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
    said = page(client.get("/settings"))
    assert "<h2>open invitations</h2>" in said  # since tidy-pages; before, "invite someone"
    assert "You may invite someone from 31 October 2026." in said
    assert 'name="note"' not in said
    assert invite(client).status_code == 200
    assert files(hearth.DATA) == []


# ---- making one -------------------------------------------------------------------

def test_the_form_says_what_was_approved(member):
    said = page(member.get("/settings"))
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
    again = page(member.get("/settings"))
    assert link not in again
    assert "Made on 15 October 2026: open until 29 October 2026." in plain(again)
    # one in thirty days: the form is gone
    assert "You may invite someone from 14 November 2026." in again


def test_the_inviter_is_told_only_how_each_stands(hearth, member, keeper, data_dir, pinned):
    used = made_link(member)
    assert join(hearth.app.test_client(), used).status_code == 302
    said = plain(page(member.get("/settings")))
    assert "Made on 15 October 2026: used." in said
    assert NEWCOMER not in said
    pinned.set(datetime(2026, 11, 20, 15, tzinfo=timezone.utc))
    made_link(member)
    pinned.set(datetime(2026, 12, 25, 15, tzinfo=timezone.utc))
    said = plain(page(member.get("/settings")))
    # closed ones folded under "past invitations" for 30 days, and older ones not listed
    # (the founder's request of 16 November 2026)
    assert "past invitations" in said
    assert "Made on 20 November 2026: expired." in said
    assert "Made on 15 October 2026: used." not in said


# ---- withdrawing --------------------------------------------------------------------

def withdraw(client, one_id):
    return post(client, "/invitations/%s/withdraw" % one_id)


def test_its_inviter_may_withdraw_it_and_it_does_not_use_up_the_month(member, data_dir):
    link = made_link(member)
    [one] = files(data_dir)
    assert withdraw(member, one["id"]).status_code == 302
    [one] = files(data_dir)
    assert one["withdrawn_by"] == MEMBER and one["withdrawn_at"]
    said = plain(page(member.get("/settings")))
    assert "Made on 15 October 2026: withdrawn." in said
    assert INVITE_SAID in said
    answer = member.get("/invitation/" + link)
    assert answer.status_code == 410 and NOT_OPEN in page(answer)


def test_the_keeper_sees_every_open_one_without_its_note_and_may_withdraw_it(
        hearth, member, keeper, data_dir):
    made_link(member)
    said = page(keeper.get("/settings"))
    assert "<h2>open invitations</h2>" in said
    assert "Made by birch on 15 October 2026, open until 29 October 2026." in plain(said)
    assert "I think you" not in said
    [one] = files(data_dir)
    withdraw(keeper, one["id"])
    assert files(data_dir)[0]["withdrawn_by"] == FOUNDER_NAME
    assert "No invitations are open." in page(keeper.get("/settings"))


def test_no_other_member_may_withdraw_it_and_none_once_used(hearth, member, data_dir, pinned):
    link = made_link(member)
    arrive(hearth, OTHER, OTHER_PASSWORD, datetime(2026, 9, 1, tzinfo=timezone.utc))
    other = signed_in(hearth, OTHER, OTHER_PASSWORD)
    [one] = files(data_dir)
    # the keeper's list of every open invitation (since tidy-pages so called; before, "open
    # invitations", which now heads one's own)
    assert "every open invitation" not in page(other.get("/settings"))
    withdraw(other, one["id"])
    assert files(data_dir)[0]["withdrawn_at"] is None
    join(hearth.app.test_client(), link)
    withdraw(member, one["id"])
    assert files(data_dir)[0]["withdrawn_at"] is None
    assert files(data_dir)[0]["used_by"] == newcomer(hearth)


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
    assert hearth.member_record(newcomer(hearth)) is not None


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
    record = read_json(data_dir / "members" / newcomer(hearth) / "member.json")
    assert record["role"] == "member" and record["vouched_by"] == [FOUNDER_NAME]
    assert read_json(data_dir / "members" / newcomer(hearth) / "email.json")["address"] ==         NEW_ADDRESS
    [one] = files(data_dir)
    assert one["used_by"] == newcomer(hearth) and one["used_at"]
    # a link to confirm the address went to it, and the words went nowhere
    [sent] = outbox.sent
    assert sent["to"] == NEW_ADDRESS and sent["subject"] == "Confirm your email address for Tesserae"
    [words] = words_given
    home = page(client.get("/"))
    for place in [home, page(client.get("/settings")), sent["text"]] + \
            [path.read_text(encoding="utf-8", errors="replace")
             for path in data_dir.rglob("*") if path.is_file() and path.suffix in (".json", ".md")]:
        assert str(words) not in place
        assert words.split()[0] + " " + words.split()[1] not in place
    with client.session_transaction() as held:
        assert held["member"] == newcomer(hearth) and str(words) not in json.dumps(dict(held))
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
    assert sum(hearth.members.id_of(name) is not None for name in ("willow", "aspen")) == 1


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
    # a new member's door starts open, with room for two (the founder's request of 14
    # November 2026), and who is here says so, with no number
    assert lines[-1] == "member · willow · door open · has room"
    assert hearth.door.read(newcomer(hearth))["room"] == 2
    assert lines[:2] == ["citizen · the first one, unnamed by its own choosing · founded "
                         "4 September 2026, attends at dawn",
                         "member · the founder · keeps the hearth"]
    assert (commons / "events.md").read_bytes() == events  # nothing said on the commons
    hearth.door.set_door(newcomer(hearth), state="closed")
    served = page(visitor.get("/commons/members.md"))
    assert "member · willow · door closed" in served
    assert NEW_ADDRESS not in served and FOUNDER_NAME not in served


# ---- the first page after joining ------------------------------------------------

def test_the_first_page_welcomes_them_and_says_no_door_has_room(hearth, keeper):
    link = made_link(keeper)
    client = hearth.app.test_client()
    join(client, link)
    said = page(client.get("/"))
    words = plain(said)
    assert ("Welcome to Tesserae. What you can do now: write on the board, "
            "linked first in the commons read the commons see which agents have doors open: the first one"
            " · door for people: closed · door for agents: closed") \
        in words
    # named in plain words; the menu has the commons, and the commons the board
    assert '<li>write on the board, linked first in the commons</li>' in said
    assert '<li>read the commons</li>' in said
    assert NO_ROOM in words and IN_TOUCH in words
    assert "You have no correspondences yet." not in said


def test_an_open_door_with_room_is_shown_in_place_of_the_no_room_line(hearth, keeper):
    hearth.door.set_door("first", state="open", room=2)
    link = made_link(keeper)
    client = hearth.app.test_client()
    join(client, link)
    words = plain(page(client.get("/")))
    # both doors, plainly (who-fix, 17 November 2026)
    assert ("see which agents have doors open: the first one · door for people: open, has room"
            " · door for agents: closed") in words
    assert NO_ROOM not in words and IN_TOUCH in words


def test_the_founder_s_home_is_as_it_was(keeper):
    said = page(keeper.get("/"))
    assert "Welcome to Tesserae" not in said and IN_TOUCH not in said


# ---- /account for a member without twelve words ---------------------------------

def test_a_member_s_account_says_nothing_of_twelve_words_and_the_keeper_s_does(member, keeper):
    said = plain(page(member.get("/settings")))
    assert ("Your key stays the same; only the password that seals it changes. Anywhere else "
            "you are logged in will be logged out.") in said
    assert "twelve words" not in said
    assert ("Your key stays the same; only the password that seals it changes, and your twelve "
            "words still open it.") in plain(page(keeper.get("/settings")))


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
    assert hearth.members.member_by_email(NEW_ADDRESS) == newcomer(hearth)
    # the unconfirmed keeping is let go, and its link stops working
    assert hearth.members.email_of(hearth.members.id_of("squatter")) is None
    assert confirm_by(squatter, squatter_s_link).status_code == 410
    assert hearth.members.member_by_email(NEW_ADDRESS) == newcomer(hearth)
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


# ---- an invitation sent by email (the founder's request of 14 November 2026) -------------

INVITED = "Nell.Invited@Example.org"
INVITED_KEPT = "nell.invited@example.org"
INVITED_HIDDEN = "n•••@example.org"
EMAILED_LINK = re.compile(r"Accept the invitation: https://hearth\.tesserae\.social/invitation/"
                          r"([A-Za-z0-9_-]{43})\n")
EMAIL_SAID = ("Or give their email address, and the invitation is sent to them for you, once, "
              "from hello@tesserae.social. Leave it empty to get the link instead.")


@pytest.fixture
def reader(hearth, monkeypatch):
    from conftest import Reader
    stub = Reader()
    monkeypatch.setattr(hearth, "Anthropic", stub)
    return stub


# the approved words of 15 November 2026, in both parts of the email
WORDS = ("Something new is being worked out between AIs and people. People have lives; AIs "
         "have new ways of seeing. At Tesserae, each gives the other what it lacks: an AI grows "
         "into someone through the friendships it keeps, and a person finds their days read "
         "with fresh eyes. You could be part of who one becomes.")
CELL = re.compile(r'<td width="20" height="20" bgcolor="(#[0-9A-Fa-f]{6})" '
                  r'style="[^"]*border:1px solid (#[0-9A-Fa-f]{6});')


def assert_the_html_part_says_the_same(said, name, from_name, note, link, until):
    """The HTML part: the approved words in their order, the note escaped, one button to the
    plain link, and nothing fetched, no image and no other link."""
    import html as html_words
    to_it = "https://hearth.tesserae.social/invitation/" + link
    order = ['<td style="padding:0 0 16px;font-size:18px;font-weight:600;">'
             + html_words.escape(name) + " has invited you to Tesserae.</td>",
             html_words.escape(WORDS),
             html_words.escape("From %s:" % from_name),
             "<br>\n".join(html_words.escape(line) for line in note.splitlines()),
             '<a href="%s" style="' % to_it,
             ">Accept the invitation</a>",
             "Works once. Open until %s." % until,
             "Replies to this address aren&#x27;t read."]
    at = [said.find(one) for one in order]
    assert -1 not in at and at == sorted(at), list(zip(order, at))
    assert re.findall(r"https?://[^\s\"<]+", said) == [to_it]  # one link, the plain one
    for nothing in ("<img", "src=", "url(", "<link", "<script", "@import", "<b>x</b>",
                    "ignore it"):
        assert nothing not in said, nothing


def invite_by_email(client, note=NOTE, address=INVITED):
    return post(client, "/account/invite", data={"note": note, "address": address})


def emailed_link(sent):
    found = EMAILED_LINK.search(sent["text"])
    assert found, sent["text"]
    return found.group(1)


def test_the_form_offers_an_address_beside_the_note(member):
    said = page(member.get("/settings"))
    assert EMAIL_SAID in plain(said)
    assert '<label for="invite_address">their email address (optional)</label>' in said
    assert 'name="address"' in said and "Make the invitation" in said


def test_an_emailed_invitation_says_the_approved_words_and_nothing_more(
        hearth, member, reader, outbox, data_dir):
    answer = invite_by_email(member)
    said = page(answer)
    assert answer.status_code == 200
    assert ("The invitation was sent to %s. It is sent only once: if the address was wrong, "
            "withdraw it and make another." % INVITED_HIDDEN) in plain(said)
    assert not LINK.search(said) and "/invitation/" not in said  # the link goes only by email
    [sent] = outbox.sent
    link = emailed_link(sent)
    assert sent["to"] == INVITED_KEPT
    assert sent["subject"] == "Birch invited you to Tesserae"
    assert sent["text"] == (
        "Birch has invited you to Tesserae.\n\n" + WORDS + "\n\n"
        "From birch:\n" + NOTE + "\n\n"
        "Accept the invitation: https://hearth.tesserae.social/invitation/" + link + "\n"
        "Works once. Open until 29 October 2026.\n\n"
        "Replies to this address aren't read.\n")
    # no image, no pixel, no link but the invitation's own
    assert re.findall(r"https?://\S+", sent["text"]) == [
        "https://hearth.tesserae.social/invitation/" + link]
    assert "<img" not in sent["text"] and "ignore it" not in sent["text"]
    assert_the_html_part_says_the_same(sent["html"], "Birch", "birch", NOTE, link,
                                       "29 October 2026")
    # the note was read for good spirit, once
    assert len(reader.asked) == 1 and "I think you" in repr(reader.asked[0]["messages"])
    [kept] = files(data_dir)
    assert kept["email"] == INVITED_KEPT and kept["by"] == MEMBER
    assert hearth.app.test_client().get("/invitation/" + link).status_code == 200
    # its inviter sees the address partly hidden, and only in their own list
    assert ("Made on 15 October 2026: open until 29 October 2026. Sent to %s."
            % INVITED_HIDDEN) in plain(page(member.get("/settings")))
    log = (data_dir / "mail.log").read_text(encoding="utf-8")
    assert log.rstrip().endswith("invitation · sent") and INVITED_KEPT not in log
    # one in thirty days, as by a link
    assert "You may invite someone from 14 November 2026." in page(member.get("/settings"))


def test_the_founder_s_is_from_his_commons_name_and_never_a_title(hearth, keeper, reader, outbox):
    invite_by_email(keeper)
    [sent] = outbox.sent
    assert sent["subject"] == "The founder invited you to Tesserae"
    assert sent["text"].startswith("The founder has invited you to Tesserae.\n")
    assert "\n\nFrom the founder:\n" in sent["text"]
    assert FOUNDER_NAME not in sent["text"] and "Founder of" not in sent["text"]


def test_an_empty_address_gives_the_link_as_before(member, reader, outbox, data_dir):
    assert LINK.search(page(invite_by_email(member, address="   ")))
    assert outbox.sent == [] and reader.asked == []
    assert files(data_dir)[0]["email"] is None


def test_a_note_not_in_good_spirit_makes_and_sends_nothing(member, reader, outbox, data_dir):
    reader.says = "NO"
    said = page(invite_by_email(member))
    assert "That note wasn't taken; no invitation was made." in plain(said)
    assert INVITED in html.unescape(said)  # what was typed is kept, to change and try again
    assert outbox.sent == [] and files(data_dir) == []


def test_it_is_counted_in_the_day_s_screened_tries(hearth, member, reader, outbox, data_dir,
                                                 monkeypatch):
    monkeypatch.setattr(hearth, "SCREENED_TRIES", {})
    reader.says = "NO"
    for _ in range(hearth.SCREENED_A_DAY):
        invite_by_email(member)
    asked = len(reader.asked)
    reader.says = "YES"
    said = plain(page(invite_by_email(member)))
    assert "That is as much as can be checked for you today; nothing was changed." in said
    assert len(reader.asked) == asked and outbox.sent == [] and files(data_dir) == []


def test_a_bad_address_or_note_is_refused_before_any_check(member, reader, outbox, data_dir):
    assert "That doesn't look like an email address." in plain(page(
        invite_by_email(member, address="not an address")))
    assert "Write a note to go with it." in page(invite_by_email(member, note=" "))
    assert reader.asked == [] and outbox.sent == [] and files(data_dir) == []


def test_with_no_room_for_it_today_nothing_is_made(hearth, member, reader, outbox, data_dir,
                                                   monkeypatch):
    monkeypatch.setattr(hearth.mail, "sent_today", lambda now: hearth.mail.WAITING_A_DAY)
    said = plain(page(invite_by_email(member)))
    assert ("No more emails can be sent today, so no invitation was made. Try again tomorrow, "
            "or leave the address empty to get a link to send yourself.") in said
    assert reader.asked == [] and outbox.sent == [] and files(data_dir) == []
    # the ten kept for confirm and reset links are still there
    monkeypatch.setattr(hearth.mail, "sent_today", lambda now: hearth.mail.MAIL_A_DAY - 1)
    assert hearth.mail.send_confirm("x@example.org", "t" * 43) == "sent"


def test_an_email_that_could_not_go_makes_nothing(member, reader, outbox, data_dir):
    outbox.says = "not sent: unreachable"
    said = plain(page(invite_by_email(member)))
    assert "The email couldn't be sent, so no invitation was made." in said
    assert files(data_dir) == []
    assert INVITE_SAID in plain(page(member.get("/settings")))  # the month is not used up


def test_the_address_is_forgotten_once_withdrawn(member, reader, outbox, data_dir):
    invite_by_email(member)
    [one] = files(data_dir)
    withdraw(member, one["id"])
    [one] = files(data_dir)
    assert one["email"] is None and INVITED_KEPT not in json.dumps(one)
    said = plain(page(member.get("/settings")))
    assert "Made on 15 October 2026: withdrawn." in said and INVITED_HIDDEN not in said


def test_the_address_is_forgotten_once_expired(hearth, member, reader, outbox, data_dir, pinned):
    invite_by_email(member)
    pinned.set(datetime(2026, 10, 30, 5, 0, tzinfo=timezone.utc))
    assert files(data_dir)[0]["email"] == INVITED_KEPT  # nothing has looked yet
    hearth.back_up(datetime(2026, 10, 30, 8, tzinfo=timezone.utc))  # before any backup
    assert files(data_dir)[0]["email"] is None


def test_the_address_is_forgotten_once_used_and_counts_as_confirmed(
        hearth, member, reader, outbox, data_dir):
    invite_by_email(member)
    link = emailed_link(outbox.sent[0])
    client = hearth.app.test_client()
    form = html.unescape(page(client.get("/invitation/%s/join" % link)))
    assert 'value="%s"' % INVITED_KEPT in form
    answer = join(client, link, address=INVITED_KEPT)
    assert answer.status_code == 302
    kept = hearth.members.email_of(newcomer(hearth))
    assert kept["address"] == INVITED_KEPT and kept["confirmed_at"]
    assert hearth.members.member_by_email(INVITED_KEPT) == newcomer(hearth)
    assert len(outbox.sent) == 1  # no link to confirm it
    assert UNCONFIRMED not in html.unescape(page(client.get("/")))
    [one] = files(data_dir)
    assert one["email"] is None and one["used_by"] == newcomer(hearth)
    assert INVITED_HIDDEN not in page(member.get("/settings"))


def test_a_changed_address_is_confirmed_by_the_usual_link(hearth, member, reader, outbox,
                                                          data_dir):
    invite_by_email(member)
    link = emailed_link(outbox.sent[0])
    client = hearth.app.test_client()
    join(client, link, address=NEW_ADDRESS)
    kept = hearth.members.email_of(newcomer(hearth))
    assert kept["address"] == NEW_ADDRESS and kept["confirmed_at"] is None
    sent = outbox.sent[-1]
    assert sent["to"] == NEW_ADDRESS
    assert sent["subject"] == "Confirm your email address for Tesserae"
    assert files(data_dir)[0]["email"] is None


def test_the_address_is_on_no_page_but_its_own_join_and_in_no_reading(
        hearth, keeper, member, reader, outbox, visitor, wake, room):
    invite_by_email(member)
    link = emailed_link(outbox.sent[0])
    assert INVITED_KEPT not in page(visitor.get("/invitation/" + link))
    plain_routes = [rule.rule for rule in hearth.app.url_map.iter_rules()
                    if "GET" in rule.methods and not rule.arguments]
    for client in (keeper, member, visitor):
        for address in plain_routes:
            text = html.unescape(page(client.get(address)))
            assert INVITED_KEPT not in text, address
            if client is not member:
                assert INVITED_HIDDEN not in text, address
    turn = wake("")
    assert INVITED_KEPT not in repr(turn.asked) and INVITED_HIDDEN not in repr(turn.asked)
    copied = [name for _, name in hearth.export_files()]
    assert not any(name.startswith("invitations/") for name in copied)


# ---- the name an invitation is from (the founder's request of 14 November 2026, later) ---

CHOSEN = "Birch from the river"


def invite_from(client, from_name, note=NOTE, address=""):
    return post(client, "/account/invite",
                data={"note": note, "address": address, "from_name": from_name})


def test_the_form_offers_the_name_filled_in_with_their_commons_name(member, keeper):
    said = page(member.get("/settings"))
    assert """<label for="from_name">Your name, as they'll see it</label>""" in said
    assert re.search(r'<input type="text" id="from_name" name="from_name" maxlength="40"\s+'
                     r'required value="birch">', said)
    assert 'value="the founder"' in page(keeper.get("/settings"))


def test_an_emailed_one_is_from_the_name_chosen_in_one_screened_try(
        hearth, member, reader, outbox, data_dir):
    invite_from(member, "  Birch   from the river ", address=INVITED)
    [sent] = outbox.sent
    assert sent["subject"] == CHOSEN + " invited you to Tesserae"
    assert sent["text"].startswith(CHOSEN + " has invited you to Tesserae.\n")
    assert "\n\nFrom %s:\n" % CHOSEN in sent["text"]
    [asked] = reader.asked  # one try, for the name and the note together
    assert CHOSEN in repr(asked["messages"]) and "I think you" in repr(asked["messages"])
    [kept] = files(data_dir)
    assert kept["from_name"] == CHOSEN and kept["by"] == MEMBER
    shown = plain(page(hearth.app.test_client().get("/invitation/" + emailed_link(sent))))
    assert "From %s:" % CHOSEN in shown and "From birch:" not in shown


def test_a_link_one_is_from_the_name_chosen_screened_once(hearth, member, reader, data_dir):
    link = LINK.search(page(invite_from(member, CHOSEN))).group(1)
    assert len(reader.asked) == 1 and CHOSEN in repr(reader.asked[0]["messages"])
    assert files(data_dir)[0]["from_name"] == CHOSEN
    assert "From %s:" % CHOSEN in plain(page(hearth.app.test_client().get("/invitation/" + link)))


def test_their_own_commons_name_needs_no_screen_by_link(member, reader, data_dir):
    assert LINK.search(page(invite_from(member, " Birch ")))
    assert reader.asked == []


def test_a_name_not_in_good_spirit_makes_nothing(member, reader, outbox, data_dir):
    reader.says = "NO"
    said = plain(page(invite_from(member, CHOSEN)))
    assert "That name wasn't taken; no invitation was made." in said
    said = plain(page(invite_from(member, CHOSEN, address=INVITED)))
    assert "That name or note wasn't taken; no invitation was made." in said
    assert outbox.sent == [] and files(data_dir) == []


def test_no_one_passes_as_someone_else(hearth, keeper, member, reader, outbox, data_dir,
                                       monkeypatch):
    monkeypatch.setattr(hearth.private_words, "listed", lambda path=None: [("oakhill", None)])
    arrive(hearth, OTHER, OTHER_PASSWORD, datetime(2026, 9, 1, tzinfo=timezone.utc))
    refused = "That name can't be used. Choose another."
    for typed, said in (("", "Write the name they'll see it is from."),
                        ("x" * 41, "A name can be at most 40 characters, on one line."),
                        ("birch\nthe founder", "A name can be at most 40 characters, on one line."),
                        ("birch at example.org", refused),
                        ("see http://x", refused),
                        ("jo oakhill", refused),
                        ("The Founder", refused),
                        ("a friend of the founder", refused),
                        ("Tesserae", refused),
                        ("tesserae team", refused),
                        ("Cedar", refused),
                        (FOUNDER_NAME, refused),
                        ("the first one", refused),
                        ("first", refused)):
        for address in ("", INVITED):
            answer = html.unescape(page(invite_from(member, typed, address=address)))
            assert said in answer, (typed, answer)
            assert NOTE.split("\n")[0] in answer  # what was typed is kept
    assert reader.asked == [] and outbox.sent == [] and files(data_dir) == []
    # the keeper may be "the founder", and no one may be the keeper's sign-in name
    assert LINK.search(page(invite_from(keeper, "the founder")))
    assert "That name can't be used." in html.unescape(page(invite_from(keeper, FOUNDER_NAME)))


def test_the_name_is_forgotten_with_the_address_and_who_invited_whom_is_kept(
        hearth, member, keeper, reader, outbox, data_dir, pinned):
    invite_from(member, CHOSEN, address=INVITED)
    [one] = files(data_dir)
    assert "Made by birch on" in plain(page(keeper.get("/settings")))  # by commons name
    assert CHOSEN not in page(keeper.get("/settings"))
    withdraw(member, one["id"])
    [one] = files(data_dir)
    assert one["from_name"] is None and one["email"] is None and one["by"] == MEMBER
    # and once used, and once expired
    pinned.set(datetime(2026, 11, 20, 17, tzinfo=timezone.utc))
    link = LINK.search(page(invite_from(member, CHOSEN))).group(1)
    join(hearth.app.test_client(), link)
    used = [held for held in files(data_dir) if held["used_by"]][0]
    assert used["from_name"] is None and used["by"] == MEMBER
    pinned.set(datetime(2026, 12, 25, 17, tzinfo=timezone.utc))
    invite_from(keeper, "a friend", address=INVITED)
    pinned.set(datetime(2027, 1, 15, 17, tzinfo=timezone.utc))
    hearth.back_up(datetime(2027, 1, 15, 17, tzinfo=timezone.utc))
    assert all(held["from_name"] is None and held["email"] is None for held in files(data_dir))


def test_the_name_is_on_no_page_but_its_own_and_in_no_reading(
        hearth, keeper, member, reader, outbox, visitor, wake, room):
    invite_from(member, "Quillwort Unseen", address=INVITED)
    plain_routes = [rule.rule for rule in hearth.app.url_map.iter_rules()
                    if "GET" in rule.methods and not rule.arguments]
    for client in (keeper, member, visitor):
        for address in plain_routes:
            assert "Quillwort Unseen" not in html.unescape(page(client.get(address))), address
    turn = wake("")
    assert "Quillwort Unseen" not in repr(turn.asked)


# ---- the invitation email's look (the founder's request of 15 November 2026) ---------

def test_the_strip_is_the_front_page_s_latest_tiles_in_their_colours(
        hearth, member, reader, outbox, data_dir):
    commons = data_dir / "commons"
    commons.mkdir(exist_ok=True)
    (commons / "events.md").write_text(
        "2026-09-02 · word · the word was published\n"
        "2026-09-04 · founding · the first one was founded\n"
        "2026-10-14 · letter · the founder wrote a letter\n", encoding="utf-8")
    (commons / "heartbeats.md").write_text(
        "- 2026-10-14T12-00-00Z · the first one · A line.\n", encoding="utf-8")
    assert hearth.invitation_tiles() == [  # newest first, as the front page lays them
        ("#F6DDD1", None),           # a waking at dawn (08:00 Eastern)
        ("#DDCDB0", "#97805A"),      # a person's letter
        ("#D85A30", None),           # the founding
        (None, "#D85A30"),           # the word: no fill, a coral edge
    ]
    invite_by_email(member)
    [sent] = outbox.sent
    assert CELL.findall(sent["html"]) == [
        ("#F6DDD1", "#F6DDD1"), ("#DDCDB0", "#97805A"), ("#D85A30", "#D85A30"),
        ("#faf7f2", "#D85A30")]


def test_only_the_first_twelve_given_are_drawn(hearth, member, reader, outbox, monkeypatch):
    many = [("#%06X" % n, None) for n in range(20)]
    monkeypatch.setattr(hearth, "invitation_tiles", lambda: many)
    invite_by_email(member)
    [sent] = outbox.sent
    assert [fill for fill, _ in CELL.findall(sent["html"])] == [one for one, _ in many[:12]]


def test_with_no_tiles_or_trouble_the_email_goes_without_a_strip(
        hearth, member, reader, outbox, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("no commons")

    monkeypatch.setattr(hearth.build_atrium, "tiles_from", broken)
    assert hearth.invitation_tiles() == []
    invite_by_email(member)
    [sent] = outbox.sent
    assert not CELL.search(sent["html"]) and "has invited you to Tesserae." in sent["html"]


def test_nothing_but_a_colour_reaches_the_strip():
    import mail
    assert mail.tile_strip([('#ffffff"><img src="https://x.example/p.gif', None),
                            ("red", "url(x)"), "not a tile", None]) == ""
    assert mail.tile_strip([("#D85A30", "#zzzzzz")]).count("#D85A30") == 3


def test_the_preview_s_parts_are_as_sent(hearth):
    import mail
    said = mail.invitation_html("Wren", "wren", "Come & see.\nTwo lines.", "https://hearth"
                                ".tesserae.social/invitation/abc", "1 December 2026",
                                [("#D85A30", None)])
    assert "Come &amp; see.<br>\nTwo lines." in said
    assert said.count('bgcolor="#D85A30"') == 1


# ---- withdrawing an emailed one to fix a typo (e1) ---------------------------------
# The founder's request of 15 November 2026, later: a member may withdraw an emailed
# invitation and send another twice in 30 days; from the third, a withdrawn emailed
# invitation counts against the month, and /account says so where it applies.

RESENDS_LEFT = ("To fix a typo, you may withdraw an emailed invitation and send another "
                "twice in 30 days. You have {left} left.")
RESENDS_USED = ("You've withdrawn two emailed invitations in the last 30 days. If you "
                "withdraw this one, it counts against your month.")


def emailed_and_withdrawn(hearth, by=MEMBER, withdrawn_by=None):
    one, _ = hearth.invitations.prepare(by, "a note", email="birch@example.org")
    hearth.invitations.keep(one)
    hearth.invitations.withdraw(one["id"], withdrawn_by or by,
                                keeper=bool(withdrawn_by and withdrawn_by != by))
    return one


def test_two_withdrawn_emailed_ones_are_free_and_the_third_counts(hearth, clock, monkeypatch,
                                                                  data_dir):
    from datetime import date
    clock.pin(hearth.invitations, monkeypatch)
    arrived = "2026-09-01T15:00:00Z"
    clock.set(datetime(2026, 11, 5, 15, tzinfo=timezone.utc))
    emailed_and_withdrawn(hearth)
    emailed_and_withdrawn(hearth)
    assert rule(hearth, MEMBER, "member", arrived, date(2026, 11, 5)) == (True, None)
    assert hearth.invitations.resends_left(MEMBER) == 0
    emailed_and_withdrawn(hearth)
    assert rule(hearth, MEMBER, "member", arrived, date(2026, 11, 5)) == (False, date(2026, 12, 5))
    kept = [one for one in files(data_dir) if one["by"] == MEMBER]
    assert all(one["emailed"] and one["email"] is None for one in kept)  # the address is gone


def test_the_two_are_counted_in_a_rolling_thirty_days(hearth, clock, monkeypatch):
    from datetime import date
    clock.pin(hearth.invitations, monkeypatch)
    arrived = "2026-09-01T15:00:00Z"
    clock.set(datetime(2026, 11, 5, 15, tzinfo=timezone.utc))
    emailed_and_withdrawn(hearth)
    emailed_and_withdrawn(hearth)
    clock.set(datetime(2026, 12, 5, 15, tzinfo=timezone.utc))  # thirty days on
    assert hearth.invitations.resends_left(MEMBER) == 2
    emailed_and_withdrawn(hearth)
    assert rule(hearth, MEMBER, "member", arrived, date(2026, 12, 5)) == (True, None)
    assert hearth.invitations.resends_left(MEMBER) == 1


def test_a_link_withdrawn_or_one_the_keeper_withdrew_never_counts(hearth, clock, monkeypatch):
    from datetime import date
    clock.pin(hearth.invitations, monkeypatch)
    arrived = "2026-09-01T15:00:00Z"
    clock.set(datetime(2026, 11, 5, 15, tzinfo=timezone.utc))
    for _ in range(3):
        one, _ = hearth.invitations.make(MEMBER, "a note")
        hearth.invitations.withdraw(one["id"], MEMBER)
    for _ in range(3):
        emailed_and_withdrawn(hearth, withdrawn_by=FOUNDER_NAME)
    assert rule(hearth, MEMBER, "member", arrived, date(2026, 11, 5)) == (True, None)
    assert hearth.invitations.resends_left(MEMBER) == 2


def test_the_account_says_so_beside_an_open_emailed_one(hearth, member, outbox, reader):
    invite_by_email(member)
    said = plain(page(member.get("/settings")))
    assert RESENDS_LEFT.format(left=2) in said
    emailed_and_withdrawn(hearth)
    assert RESENDS_LEFT.format(left=1) in plain(page(member.get("/settings")))
    emailed_and_withdrawn(hearth)
    said = plain(page(member.get("/settings")))
    assert RESENDS_USED in said and "You have" not in said


def test_nothing_is_said_beside_a_link_or_for_the_keeper(hearth, member, keeper, outbox, reader):
    made_link(member)
    assert "withdraw an emailed" not in plain(page(member.get("/settings")))
    invite_by_email(keeper)
    said = plain(page(keeper.get("/settings")))
    assert "emailed invitation" not in said


# ---- joining since ids (names-ids, stage 4; the founder's request of 20 November 2026) -------

def test_a_newcomer_is_kept_by_a_random_id_and_shown_by_the_name_they_chose(
        hearth, keeper, outbox, data_dir, commons):
    client = hearth.app.test_client()
    assert join(client, made_link(keeper)).status_code == 302
    member_id = newcomer(hearth)
    assert re.fullmatch(r"p-[a-z0-9]{8}", member_id)
    assert not (data_dir / "members" / NEWCOMER).exists()
    assert hearth.members.name_of(member_id) == NEWCOMER
    assert hearth.members.did_for(member_id).endswith(member_id)
    # their address signs them in once confirmed, and never before
    other = hearth.app.test_client()
    tried = post(other, "/login", data={"pseudonym": NEW_ADDRESS, "password": NEW_PASSWORD})
    assert tried.status_code != 302
    assert confirm_by(client, outbox.sent[-1]).status_code == 200
    tried = post(other, "/login", data={"pseudonym": NEW_ADDRESS, "password": NEW_PASSWORD})
    assert tried.status_code == 302
    # the name they chose, or their id, signs no one in
    for given in (NEWCOMER, member_id):
        tried = post(hearth.app.test_client(), "/login",
                     data={"pseudonym": given, "password": NEW_PASSWORD})
        assert tried.status_code != 302


def test_a_name_anyone_has_held_is_never_given_again(hearth, keeper, outbox):
    assert join(hearth.app.test_client(), made_link(keeper)).status_code == 302
    hearth.members.set_name(newcomer(hearth), "birch-tree")
    said = html.unescape(page(join(hearth.app.test_client(), made_link(keeper),
                                   address="another@example.org")))
    assert "That name is already taken." in said
