"""A visitor, signed in nowhere, costs the site nothing: no model is asked, no agent woken.

The founder's request of 13 November 2026. Every route the hearth has - read off
its url_map, so that a route added later is walked too - is asked for by a
visitor with no session, by every method it takes, with a form full of the
fields any page here sends. Throughout, every way a model could be reached is
watched: Anthropic's client being made at all, the public screen, Google's
client, and an attendance being held. Not one may be reached.

An email is the one thing a visitor may cause, and only in three places, each
the way a person comes back to their own account or takes up an invitation
already given them:

  /forgot                  a link to choose a new password, sent only to an address a
                           member has already confirmed (5 asks an hour from one
                           address, 3 emails an hour to one person)
  /reset/<token>           with a live link from that email: a note that the password
                           was changed, to the same confirmed address
  /invitation/<token>/join with a live invitation: one confirmation, to the address the
                           newcomer gives (5 tries an hour for each invitation and each
                           address; an invitation is used once)

Any other route that sends one fails here. Each of the three is followed with
a live link too, and is seen to ask no model.
"""

import re

import anthropic
import pytest
from nacl.pwhash import argon2id

import vault
from conftest import post

MEMBER = "birch"
MEMBER_PASSWORD = "a member's own password"
MEMBER_ADDRESS = "birch@example.org"

# The routes a visitor may cause an email from, and nothing else at all.
VISITOR_EMAILS = {"forgot", "reset_password", "invitation_join"}

# A value for each part of an address that names something; anything not here is "x".
NAMED = {"room_id": "first", "agent_id": "first", "bond_id": "founder-first",
         "party": "founder", "name": MEMBER, "filename": "x.jpg", "token": "x" * 43,
         "invitation_id": "0" * 16}

# Every field a form on these pages sends, filled, so that a route that would
# act on one has what it needs to act.
FORM = {"line": "A kind word on a quiet day.", "words": "A kind word on a quiet day.",
        "question": "What are you glad of today?", "introduction": "I like rivers.",
        "letter": "Dear first one,\n\nHello.\n", "commons_line": "a quiet day",
        "writing": "plainly", "given": MEMBER, "pseudonym": MEMBER, "name": "newcomer",
        "address": "newcomer@example.org", "password": "a long enough password",
        "password_again": "a long enough password", "current_password": MEMBER_PASSWORD,
        "words_twelve": "one two three", "to": "", "confirm": "yes", "kind": "letter",
        "source": "founder-2026-10-14T09-00-00Z", "text": "Hello.", "id": "x",
        "reason": "a reason", "agent": "first", "note": "come and see", "until": "",
        "room": "4", "open": "1", "answer": "yes", "intends": "yes"}


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


class Watched:
    """Every way a model may be reached, each counted where it is reached."""

    def __init__(self):
        self.reached = []

    def note(self, how):
        def counted(*args, **kwargs):
            self.reached.append(how)
            raise RuntimeError("a visitor reached " + how)
        return counted


@pytest.fixture
def watched(hearth, screen, monkeypatch, clock):
    import gemini
    import public_screen

    seen = Watched()
    # Anthropic's client may not even be made, by any module, however it was imported
    monkeypatch.setattr(anthropic.Anthropic, "__init__", seen.note("Anthropic"))
    monkeypatch.setattr(anthropic.AsyncAnthropic, "__init__", seen.note("AsyncAnthropic"))
    monkeypatch.setattr(gemini, "sdk_client", seen.note("Gemini"))
    monkeypatch.setattr(hearth, "hold_attendance", seen.note("a waking"))
    screen.says = seen.note("the public screen")
    monkeypatch.setattr(public_screen, "ask", screen)
    clock.pin(hearth.tokens, monkeypatch)
    clock.pin(hearth.invitations, monkeypatch)
    sealed, _, _ = vault.make_vault(MEMBER_PASSWORD)
    hearth.members.create_member(MEMBER, sealed, "member", [])
    hearth.members.set_email(MEMBER, MEMBER_ADDRESS, confirmed_at="2026-10-15T12:00:00Z")
    return seen


def address_of(rule):
    """A concrete address for one rule, each named part given a value."""
    path = rule.rule
    for part in rule.arguments:
        path = re.sub(r"<(?:[^:<>]+:)?%s>" % part, NAMED.get(part, "x"), path)
    return path


def walk(hearth, outbox):
    """Ask for every route as a fresh visitor; give back what each emailed, by route."""
    emailed = {}
    for rule in sorted(hearth.app.url_map.iter_rules(), key=lambda r: r.rule):
        if rule.endpoint == "static":
            continue
        path = address_of(rule)
        for method in sorted(rule.methods & {"GET", "POST"}):
            client = hearth.app.test_client()  # a new visitor each time: no session at all
            before = len(outbox.sent)
            if method == "GET":
                client.get(path)
            else:
                post(client, path, data=dict(FORM))
            if len(outbox.sent) > before:
                emailed.setdefault(rule.endpoint, []).extend(outbox.sent[before:])
    return emailed


def test_no_route_a_visitor_can_reach_asks_a_model_or_wakes_anyone(hearth, watched, outbox):
    walk(hearth, outbox)
    assert watched.reached == []


def test_no_route_a_visitor_can_reach_emails_anyone_but_the_three(hearth, watched, outbox):
    emailed = walk(hearth, outbox)
    assert set(emailed) <= VISITOR_EMAILS
    assert "forgot" in emailed  # the walk reaches what a route does, not only its door
    # and what /forgot sends goes only to the address the member confirmed themself
    assert all(one["to"] == MEMBER_ADDRESS for sent in emailed.values() for one in sent)


def test_every_route_is_walked(hearth, watched):
    """The walk reads the url_map itself: a route added later is in it."""
    walked = {rule.endpoint for rule in hearth.app.url_map.iter_rules()}
    assert {"board_page", "board_section", "board_topic", "board_take_down", "forgot", "room",
            "account", "witness_bond",
            "propose_weekly_question", "my_introduction"} <= walked


def test_a_live_reset_link_emails_only_the_member_and_asks_no_model(hearth, watched, outbox):
    seal = vault.fingerprint(hearth.member_record(MEMBER)["vault"])
    link = hearth.tokens.issue("reset", MEMBER, hearth.tokens.LIFETIMES["reset"], seal=seal)
    client = hearth.app.test_client()
    client.get("/reset/" + link)
    post(client, "/reset/" + link, data={"password": "a brand new password of theirs",
                                         "password_again": "a brand new password of theirs"})
    assert [one["to"] for one in outbox.sent] == [MEMBER_ADDRESS]
    assert watched.reached == []


def test_a_live_invitation_sends_one_confirmation_and_asks_no_model(hearth, watched, outbox):
    _, link = hearth.invitations.make(MEMBER, "come and see")
    client = hearth.app.test_client()
    client.get("/invitation/%s/join" % link)
    post(client, "/invitation/%s/join" % link, data={
        "name": "newcomer", "address": "newcomer@example.org",
        "password": "a long enough password", "password_again": "a long enough password"})
    assert [one["to"] for one in outbox.sent] == ["newcomer@example.org"]
    assert watched.reached == []
    # and the invitation is spent: a second try sends nothing more
    other = hearth.app.test_client()
    post(other, "/invitation/%s/join" % link, data={
        "name": "another", "address": "another@example.org",
        "password": "a long enough password", "password_again": "a long enough password"})
    assert len(outbox.sent) == 1


def test_the_watch_sees_a_member_s_line_go_to_a_model(hearth, watched):
    """So that a walk that saw nothing saw nothing because there was nothing."""
    client = hearth.app.test_client()
    post(client, "/login", data={"pseudonym": MEMBER, "password": MEMBER_PASSWORD})
    post(client, "/board/place", data={"subject": "A quiet day",
                                       "words": "A kind word on a quiet day."})
    assert watched.reached
