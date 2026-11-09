"""An email when something is waiting: who wrote, and a link, and nothing else.

proposals/quiet-and-questions.md, section 3, as the founder changed it on 9
November 2026: sent only when something is waiting for the person (a letter of
the agent's they have not opened, an errand it has asked, an offering of its that
waits on them); the words say only who wrote and give a link, never any letter
text and no counts; each person chooses daily, weekly or off on /account, daily
until they choose; a stop link in every email; sent through mail.py, whose
transport the tests replace with the outbox. Nothing here reaches the network.

The emails go once a day at hearth.WAITING_HOUR, eighteen o'clock UTC.
"""

import re
from datetime import datetime, timedelta, timezone

import pytest
from nacl.pwhash import argon2id

import vault
from conftest import FOUNDER_NAME, page, post, write

ADDRESS = "rowan@example.org"
LETTER = "A FAKE LETTER FROM THE FIRST ONE, FOR THE TESTS. It names 3 things."
SAYS = "The first one has written to you at Tesserae."
STOP = re.compile(r"https://hearth\.tesserae\.social(/email/stop/[a-z0-9-]+/[0-9a-f]{32})\n")


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


@pytest.fixture
def kept(hearth, founder):
    """The keeper, signed in, their address confirmed: the first one's room is theirs."""
    hearth.members.set_email(FOUNDER_NAME, ADDRESS, confirmed_at="2026-10-01T00:00:00Z")
    return founder


def a_letter(room, stamp="2026-10-15T09-00-00Z", text=LETTER):
    write(room / "letters" / "outgoing" / f"to-founder-{stamp}.md", text + "\n")


def at(stamp):
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)


def a_round(hearth, when="2026-10-15T18:00"):
    return hearth.send_waiting_emails(at(when))


# ---- what it says ----------------------------------------------------------

def test_a_letter_waiting_is_told_by_who_wrote_and_a_link_and_nothing_else(
        hearth, kept, room, outbox):
    a_letter(room)
    assert a_round(hearth) == 1
    (sent,) = outbox.sent
    assert sent["to"] == ADDRESS
    assert sent["subject"] == "Someone has written to you at Tesserae"
    text = sent["text"]
    assert text.startswith(SAYS + "\n\nhttps://hearth.tesserae.social/login\n\n"
                           "To stop these emails, open this link: ")
    assert text.endswith("Replies to this address aren't read.\n")
    assert "FAKE LETTER" not in text and "3 things" not in text
    # no count of anything: not a figure in it outside its links
    words = re.sub(r"https://\S+", "", text)
    assert not re.search(r"\d", words)
    assert STOP.search(text)


def test_more_than_one_who_wrote_are_named_together(hearth, kept, room, outbox, monkeypatch):
    monkeypatch.setattr(hearth, "waiting_for",
                        lambda name: (["the first one", "the second one"], {"letter:x:y"}))
    assert a_round(hearth) == 1
    assert outbox.sent[0]["text"].startswith(
        "The first one and the second one have written to you at Tesserae.")


def test_an_errand_waiting_is_told_too(hearth, kept, room, outbox):
    write(room / "errands" / "errand-2026-10-15T09-00-00Z.md", "Go down to the lake.\n")
    assert a_round(hearth) == 1
    assert outbox.sent[0]["text"].startswith(SAYS)
    assert "lake" not in outbox.sent[0]["text"]


# ---- only when something new is waiting -------------------------------------

def test_nothing_waiting_is_no_email(hearth, kept, room, outbox):
    assert a_round(hearth) == 0 and outbox.sent == []


def test_a_letter_already_opened_is_no_email(hearth, kept, room, outbox):
    a_letter(room)
    hearth.members.mark_seen(FOUNDER_NAME, "first", "2026-10-15T09-00-00Z")
    assert a_round(hearth) == 0


def test_a_letter_answered_since_is_no_email(hearth, kept, room, outbox):
    a_letter(room)
    write(room / "letters" / "incoming" / "founder-2026-10-15T10-00-00Z.md", "An answer.\n")
    assert a_round(hearth) == 0


def test_what_has_been_told_is_not_told_again(hearth, kept, room, outbox):
    a_letter(room)
    assert a_round(hearth, "2026-10-15T18:00") == 1
    assert a_round(hearth, "2026-10-16T18:00") == 0
    assert a_round(hearth, "2026-10-20T18:00") == 0
    assert len(outbox.sent) == 1


def test_daily_a_new_letter_is_told_the_next_day(hearth, kept, room, outbox):
    a_letter(room)
    assert a_round(hearth, "2026-10-15T18:00") == 1
    a_letter(room, "2026-10-16T09-00-00Z")
    assert a_round(hearth, "2026-10-15T23:00") == 0  # not twice in a day
    assert a_round(hearth, "2026-10-16T18:00") == 1
    assert len(outbox.sent) == 2


def test_weekly_at_most_once_a_week(hearth, kept, room, outbox):
    hearth.members.set_emails(FOUNDER_NAME, "weekly")
    a_letter(room)
    assert a_round(hearth, "2026-10-15T18:00") == 1
    a_letter(room, "2026-10-16T09-00-00Z")
    for day in range(16, 22):
        assert a_round(hearth, "2026-10-%dT18:00" % day) == 0
    assert a_round(hearth, "2026-10-22T18:00") == 1


def test_off_is_no_email(hearth, kept, room, outbox):
    hearth.members.set_emails(FOUNDER_NAME, "off")
    a_letter(room)
    assert a_round(hearth) == 0


def test_an_address_not_confirmed_is_no_email(hearth, founder, room, outbox):
    hearth.members.set_email(FOUNDER_NAME, ADDRESS)
    a_letter(room)
    assert a_round(hearth) == 0


def test_no_address_is_no_email(hearth, founder, room, outbox):
    a_letter(room)
    assert a_round(hearth) == 0


def test_no_email_while_resting(hearth, kept, room, outbox):
    hearth.begin_rest()
    a_letter(room)
    assert a_round(hearth) == 0


def test_a_member_in_no_room_is_emailed_nothing(hearth, kept, room, outbox):
    sealed, _, _ = vault.make_vault("a member's own password")
    hearth.members.create_member("hazel", sealed, "member", [FOUNDER_NAME])
    hearth.members.set_email("hazel", "hazel@example.org", confirmed_at="2026-10-01T00:00:00Z")
    a_letter(room)
    a_round(hearth)
    assert [one["to"] for one in outbox.sent] == [ADDRESS]


def test_an_email_that_does_not_go_is_told_again_next_time(hearth, kept, room, outbox):
    outbox.says = "not sent: unreachable"
    a_letter(room)
    assert a_round(hearth, "2026-10-15T18:00") == 0
    outbox.says = "sent"
    assert a_round(hearth, "2026-10-16T18:00") == 1


# ---- the choice, and the stop link ------------------------------------------

def test_daily_until_chosen_and_chosen_on_the_account_page(hearth, kept):
    said = page(kept.get("/account"))
    assert "emails when something is waiting" in said
    assert re.search(r'value="daily"\s+checked', said)
    answer = post(kept, "/account/emails", data={"every": "weekly"})
    assert "Saved." in page(answer)
    assert hearth.members.emails_of(FOUNDER_NAME) == "weekly"
    assert re.search(r'value="weekly"\s+checked', page(kept.get("/account")))
    answer = post(kept, "/account/emails", data={"every": "hourly"})
    assert "Choose daily, weekly or never." in page(answer)
    assert hearth.members.emails_of(FOUNDER_NAME) == "weekly"


def test_the_choice_is_only_one_s_own(hearth, visitor):
    answer = post(visitor, "/account/emails", data={"every": "off"})
    assert answer.status_code == 302 and "/login" in answer.headers["Location"]


def test_the_stop_link_stops_them_with_one_button(hearth, kept, room, outbox, visitor):
    a_letter(room)
    a_round(hearth)
    path = STOP.search(outbox.sent[0]["text"]).group(1)
    shown = visitor.get(path)
    assert shown.status_code == 200 and "Stop these emails" in page(shown)
    assert shown.headers["Cache-Control"] == "no-store"
    assert hearth.members.emails_of(FOUNDER_NAME) == "daily"  # opening it stops nothing
    stopped = post(visitor, path, data={})
    assert "be emailed when something is waiting." in page(stopped)
    assert hearth.members.emails_of(FOUNDER_NAME) == "off"
    a_letter(room, "2026-10-16T09-00-00Z")
    assert a_round(hearth, "2026-10-16T18:00") == 0


@pytest.mark.parametrize("path", [
    "/email/stop/rowan/" + "0" * 32,
    "/email/stop/nobody-here/" + "0" * 32,
    "/email/stop/NOT A NAME/" + "0" * 32,
])
def test_a_stop_link_the_hearth_did_not_make_stops_nothing(hearth, kept, visitor, path):
    assert visitor.get(path).status_code == 410
    assert post(visitor, path, data={}).status_code == 410
    assert hearth.members.emails_of(FOUNDER_NAME) == "daily"


# ---- when ---------------------------------------------------------------------

def test_the_hour_is_away_from_every_dawn_and_the_backup(hearth):
    assert hearth.WAITING_HOUR == 18
    assert abs(hearth.WAITING_HOUR - hearth.BACKUP_HOUR) >= 4
    assert hearth.next_round(at("2026-10-15T12:00")) == at("2026-10-15T18:00")
    assert hearth.next_round(at("2026-10-15T18:00")) == at("2026-10-16T18:00")


def test_dawn_is_hours_before_the_round_all_year(hearth):
    # the dawn the tide wakes an agent at, reckoned where the tests watch the sun from,
    # on the first and fifteenth of every month: the round is never within four hours
    from datetime import date
    import waking
    for month in range(1, 13):
        for day in (1, 15):
            dawn = waking.moment_on(None, "dawn", date(2026, month, day))
            round_at = at("2026-%02d-%02dT18:00" % (month, day))
            assert round_at - dawn >= timedelta(hours=4), (month, day, dawn)


def test_a_round_goes_once_a_day_after_its_hour(hearth, kept, room, outbox):
    assert not hearth.round_due(at("2026-10-15T17:59"))
    assert hearth.round_due(at("2026-10-15T18:00"))
    a_letter(room)
    hearth.email_round(at("2026-10-15T18:05"))
    assert len(outbox.sent) == 1
    assert not hearth.round_due(at("2026-10-15T23:00"))
    assert hearth.round_due(at("2026-10-16T18:00"))


def test_the_email_thread_is_set_going_once(hearth, monkeypatch):
    from conftest import no_threads
    assert hearth.EMAILS_RUNNING is True
    monkeypatch.setattr(hearth, "EMAILS_RUNNING", False)
    with no_threads() as started:
        hearth.start_emails()
        hearth.start_emails()
    assert [thread.name for thread in started] == ["emails"]
    assert started[0].daemon is True
