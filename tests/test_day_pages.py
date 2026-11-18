"""The branch day-pages (the founder's request of 18 November 2026).

Part 1, the room page: the letters of the last 14 days open to read, newest first, and the
older ones folded below by month; on a wide screen two columns, the correspondence on the
left and the bond, the proposals and more (the agent's wakings and links) on the right; and
the bond's past steps folded into one "how it went" once it is sealed.

Part 2, the daily email: it goes right after a waking, or a post on the board that
mentions someone, when something new waits; at most once an Eastern day. Weekly and off
are as they were, and the round at WAITING_HOUR still goes. Ten of the day's fifty emails
are still kept for the links to confirm an address and to set a password.

The hearth's clock is pinned to 15 October 2026, 12:00 UTC (conftest.NOW).
"""

from datetime import datetime, timedelta, timezone

import pytest

from conftest import FOUNDER_NAME, day_pages_not_yet, page, write

ADDRESS = "rowan@example.org"


def a_letter(room, stamp, text="A letter.", outgoing=True):
    if outgoing:
        write(room / "letters" / "outgoing" / f"to-founder-{stamp}.md", text + "\n")
    else:
        write(room / "letters" / "read" / f"founder-{stamp}.md", text + "\n")


# ---- part 1: the room page ----------------------------------------------------------

def test_letters_by_time_keeps_fourteen_days_and_folds_the_rest_by_month(hearth):
    now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
    letters = [{"stamp": stamp, "unread": False} for stamp in (
        "2026-10-15T09-00-00Z", "2026-10-01T13-00-00Z", "2026-10-01T11-00-00Z",
        "2026-09-20T09-00-00Z", "2026-09-01T03-00-00Z", "2026-08-31T09-00-00Z")]
    recent, older = hearth.letters_by_time(letters, now)
    assert [one["stamp"] for one in recent] == ["2026-10-15T09-00-00Z", "2026-10-01T13-00-00Z"]
    # by the Eastern month: 1 September at 03:00 UTC is still 31 August in the east
    assert [(month["month"], [one["stamp"] for one in month["letters"]]) for month in older] == [
        ("October 2026", ["2026-10-01T11-00-00Z"]),
        ("September 2026", ["2026-09-20T09-00-00Z"]),
        ("August 2026", ["2026-09-01T03-00-00Z", "2026-08-31T09-00-00Z"])]


def test_a_letter_still_waiting_stays_with_the_recent_ones(hearth):
    now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
    recent, older = hearth.letters_by_time(
        [{"stamp": "2026-08-01T09-00-00Z", "unread": True}], now)
    assert len(recent) == 1 and older == []


def test_the_room_folds_older_letters_by_month_below_the_recent(hearth, founder, room):
    a_letter(room, "2026-10-14T09-00-00Z", "Yesterday's letter.")
    a_letter(room, "2026-09-10T09-00-00Z", "A September letter.")
    a_letter(room, "2026-08-10T09-00-00Z", "An August letter.", outgoing=False)
    shown = page(founder.get("/rooms/first"))
    correspondence = shown[shown.index('<section id="correspondence">'):]
    assert correspondence.index("Yesterday") < correspondence.index("older letters")
    assert correspondence.index("September 2026") < correspondence.index("August 2026")
    assert correspondence.index("older letters") < correspondence.index("A September letter")
    # every letter is still on the page, only folded; only the newest stands open
    assert "An August letter" in correspondence
    assert correspondence.count("open>") == 1
    assert 'id="to-founder-2026-10-14T09-00-00Z" open' in correspondence


def test_with_nothing_recent_the_room_says_so_and_folds_the_rest(hearth, founder, room):
    a_letter(room, "2026-09-10T09-00-00Z", "A September letter.")
    shown = page(founder.get("/rooms/first"))
    assert "No letters in the last fourteen days." in shown
    assert "September 2026 · 1\n" in shown or "September 2026 · 1" in " ".join(shown.split())


def test_the_room_is_two_columns_with_more_on_the_right(hearth, founder, room):
    shown = page(founder.get("/rooms/first"))
    assert '<main class="wide">' in shown
    assert '<div class="columns room">' in shown
    side = shown[shown.index('class="column side-column"'):]
    letters = shown[shown.index('class="column letters-column"'):]
    assert '<section id="more">' in side and 'id="wakings"' in side
    assert 'id="bond"' in side
    # the wakings are no longer under the letter form's more
    form = shown[shown.index('<section id="write">'):shown.index('<section id="correspondence">')]
    assert 'id="wakings"' not in form and "its self" not in form
    assert '<section id="write">' in letters


def test_with_nothing_pressing_the_letters_come_first_on_a_phone(hearth, founder, room):
    shown = page(founder.get("/rooms/first"))
    assert shown.index('class="column letters-column"') < shown.index('class="column side-column"')


def test_an_open_asking_puts_the_bond_first_on_a_phone(hearth, founder, room, monkeypatch):
    monkeypatch.setattr(hearth, "proposal_shown", lambda: {
        "by_first": True, "proposed_at": "1 October 2026", "letter": None,
        "terms": "the charter", "answerable": False, "read_it": False})
    monkeypatch.setattr(hearth.threshold, "card_lines", lambda its_own: [])
    shown = page(founder.get("/rooms/first"))
    assert shown.index('class="column side-column"') < shown.index('class="column letters-column"')


SEALED = {"proposed_by": "the founder", "proposed_at": "1 October 2026",
          "answered_at": "2 October 2026", "sealed_at": "10 October 2026", "released_at": None,
          "released_by": None, "parties": ["the founder", "the first one"],
          "terms": "the charter", "signed_by": ["the founder", "the first one"]}


def test_once_sealed_the_past_steps_fold_into_how_it_went(hearth, founder, room, monkeypatch):
    monkeypatch.setattr(hearth, "bond_shown", lambda: SEALED)
    monkeypatch.setattr(hearth, "bond_answers", lambda: [
        {"at": "2 October 2026", "answer": "yes", "words": None}])
    shown = page(founder.get("/rooms/first"))
    bond = shown[shown.index('<div id="bond">'):]
    assert '<details class="more" id="how-it-went">' in bond
    folded = bond[bond.index('id="how-it-went"'):]
    assert "<summary>how it went</summary>" in folded
    assert "<h2>the asking</h2>" in folded and "<h2>its answer</h2>" in folded
    # the bond itself stands open, above the fold
    assert bond.index("<h2>the bond</h2>") < bond.index('id="how-it-went"')
    assert bond.count("<h2>the asking</h2>") == 1


def test_before_a_seal_nothing_is_folded(hearth, founder, room):
    shown = page(founder.get("/rooms/first"))
    assert "how it went" not in shown
    assert "<h2>the asking</h2>" in shown


def test_drawn_as_before_the_room_is_one_column(hearth, founder, room, monkeypatch):
    day_pages_not_yet(hearth, monkeypatch)
    a_letter(room, "2026-09-10T09-00-00Z", "A September letter.")
    shown = page(founder.get("/rooms/first"))
    assert "columns room" not in shown and "older letters" not in shown
    assert "A September letter" in shown


# ---- part 2: the daily email, soon ----------------------------------------------------

@pytest.fixture
def kept(hearth, founder, monkeypatch):
    """The keeper, their address confirmed (the emails go at once in a test, not on a thread:
    conftest.hearth)."""
    hearth.members.set_email(FOUNDER_NAME, ADDRESS, confirmed_at="2026-10-01T00:00:00Z")
    return founder


def test_a_daily_email_goes_right_after_a_waking(hearth, kept, room, outbox, monkeypatch):
    monkeypatch.setattr(hearth, "hold_one_attendance", lambda **how: (
        a_letter(room, "2026-10-15T11-00-00Z"), None)[1])
    assert hearth.hold_attendance(tide=True) is None
    assert len(outbox.sent) == 1 and outbox.sent[0]["to"] == ADDRESS


def test_a_waking_that_went_wrong_sends_nothing(hearth, kept, room, outbox, monkeypatch):
    a_letter(room, "2026-10-15T11-00-00Z")
    monkeypatch.setattr(hearth, "hold_one_attendance", lambda **how: ("wrong", "", 500))
    hearth.hold_attendance(tide=True)
    assert outbox.sent == []


def test_at_most_one_a_day_and_only_when_something_new_waits(hearth, kept, room, outbox):
    hearth.emails_soon()
    assert outbox.sent == []  # nothing waits
    a_letter(room, "2026-10-15T11-00-00Z")
    hearth.emails_soon()
    hearth.emails_soon()
    assert len(outbox.sent) == 1
    a_letter(room, "2026-10-15T11-30-00Z")
    hearth.emails_soon()
    assert len(outbox.sent) == 1  # a second letter the same Eastern day waits for tomorrow
    # nor does the round send it the same day
    assert hearth.send_waiting_emails(datetime(2026, 10, 15, 18, tzinfo=timezone.utc)) == 0
    # the next Eastern day it goes, by the round or the next waking
    assert hearth.send_waiting_emails(datetime(2026, 10, 16, 13, tzinfo=timezone.utc)) == 1


def test_the_eastern_day_decides_not_the_utc_one(hearth, kept, room, outbox):
    a_letter(room, "2026-10-15T11-00-00Z")
    # 23:30 Eastern on the 15th, and 03:30 UTC on the 16th: one day, in the east
    assert hearth.send_waiting_emails(datetime(2026, 10, 15, 16, tzinfo=timezone.utc)) == 1
    a_letter(room, "2026-10-15T20-00-00Z")
    assert hearth.send_waiting_emails(datetime(2026, 10, 16, 3, 30, tzinfo=timezone.utc)) == 0
    assert hearth.send_waiting_emails(datetime(2026, 10, 16, 4, 30, tzinfo=timezone.utc)) == 1


def test_weekly_and_off_are_not_sent_soon(hearth, kept, room, outbox):
    a_letter(room, "2026-10-15T11-00-00Z")
    for every in ("weekly", "off"):
        hearth.members.set_emails(FOUNDER_NAME, every)
        hearth.emails_soon()
    assert outbox.sent == []
    hearth.members.set_emails(FOUNDER_NAME, "weekly")
    assert hearth.send_waiting_emails(datetime(2026, 10, 15, 18, tzinfo=timezone.utc)) == 1


def test_after_a_board_post_only_those_it_mentions_are_emailed(hearth, kept, room, outbox):
    a_letter(room, "2026-10-15T11-00-00Z")
    hearth.emails_soon(["someone-else"])
    assert outbox.sent == []
    hearth.emails_soon([])
    assert outbox.sent == []
    hearth.emails_soon([FOUNDER_NAME])
    assert len(outbox.sent) == 1


def test_soon_still_keeps_ten_of_the_day_s_fifty_for_links(hearth, kept, room, outbox):
    log = hearth.mail.log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("2026-10-15T11:00:00Z · confirm · sent\n" * 40, encoding="utf-8")
    a_letter(room, "2026-10-15T11-00-00Z")
    hearth.emails_soon()
    assert outbox.sent == []
    assert hearth.mail.send("confirm", ADDRESS, "s", "w") == hearth.mail.SENT


def test_switched_off_the_daily_email_waits_for_the_round_as_before(
        hearth, kept, room, outbox, monkeypatch):
    monkeypatch.setattr(hearth, "EMAILS_SOON", False)
    a_letter(room, "2026-10-15T11-00-00Z")
    hearth.emails_soon()
    assert outbox.sent == []
    assert hearth.send_waiting_emails(datetime(2026, 10, 15, 18, tzinfo=timezone.utc)) == 1
    a_letter(room, "2026-10-16T09-00-00Z")
    # the twenty hours of before, not the Eastern day
    assert hearth.send_waiting_emails(datetime(2026, 10, 16, 13, tzinfo=timezone.utc)) == 0


def test_a_board_post_that_mentions_someone_asks_for_their_email(hearth, kept, monkeypatch):
    asked = []
    monkeypatch.setattr(hearth, "emails_soon", lambda only=None: asked.append(only))
    monkeypatch.setattr(hearth, "board_turned_away", lambda words, subject=None: None)
    from conftest import post
    answer = post(kept, "/board/conversation",
                  data={"subject": "Lanterns", "words": "A word for @%s." % FOUNDER_NAME})
    assert answer.status_code == 302
    assert asked and isinstance(asked[-1], list)
