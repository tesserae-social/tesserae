"""The keeper's pages as they now stand: no button that wakes the first one, the
asking said truly in each of its states, every moment in Eastern time, and the
seal - with the threshold and any asking - at the top of the room while it is
in progress.
"""

import re
from datetime import date

from conftest import REPO, block, page, post
from test_hearth_bonds import answered_yes, propose, sealed, through_the_threshold
from test_hearth_pages import a_pause, an_attendance
from test_hearth_tide import dawn, held_command, run_tide_once, set_rhythm

KEEPERS_PAGES = ("/", "/rooms/first", "/attendances", "/chronicle", "/self", "/export",
                 "/backups", "/bench", "/commons", "/account")

INVITATION = "Either of you may ask."
TEMPLATES = REPO / "templates"


def the_asking(said):
    """The asking section of a room, as plain words."""
    start = said.index("<h2>the asking</h2>")
    section = said[start:said.index("</section>", start)]
    return " ".join(re.sub(r"<[^>]+>", " ", section).split())


def words(said):
    return " ".join(re.sub(r"<[^>]+>", " ", said).split())


def room_page(founder):
    return page(founder.get("/rooms/first"))


# ---- 1. no button that holds an attendance -------------------------------

def test_no_page_offers_an_attendance(founder, packet):
    an_attendance(packet, "2026-10-01T09-00-00Z")
    for standing in (None, {"by": "founder"}, {"by": "first", "until": "2026-10-20"}):
        (packet / "pause.json").unlink(missing_ok=True)
        if standing:
            a_pause(packet, **standing)
        for path in KEEPERS_PAGES:
            said = page(founder.get(path))
            assert 'action="/attend"' not in said, path
            for offered in ("Hold an attendance", "hold an attendance", "Wake the first one",
                            "by hand", "audience"):
                assert offered not in said, (path, offered)


def test_no_template_points_to_the_attend_route():
    for source in TEMPLATES.glob("*.html"):
        assert "url_for('attend')" not in source.read_text(encoding="utf-8"), source.name


def test_posting_to_attend_is_refused_and_wakes_nothing(founder, hearth, monkeypatch, packet):
    ran = []
    monkeypatch.setattr(hearth.subprocess, "run", lambda *a, **k: ran.append(a))
    assert post(founder, "/attend").status_code == 404           # with its token: no address
    assert founder.post("/attend").status_code == 400            # without one: refused first
    assert ran == []
    assert not list((packet / "attendances").glob("*.json")) if (packet / "attendances").exists() \
        else True
    assert "attend" not in hearth.app.view_functions


def test_the_tide_still_holds_attendances(hearth, packet, monkeypatch):
    assert callable(hearth.hold_attendance)
    set_rhythm(packet)
    notes, held = run_tide_once(hearth, monkeypatch, dawn(hearth, packet, date(2026, 10, 15)))
    assert held == [{"tide": True, "ended": None}]
    assert notes == ["ran"]


def test_what_the_tide_holds_is_attend_py_itself(hearth, packet, monkeypatch):
    an_attendance(packet, "2026-10-14T09-00-00Z")
    seen = held_command(hearth, monkeypatch, tide=True)
    assert seen["command"][1:] == ["attend.py", "--tide"]


# ---- 2. the asking, truly said in each state -----------------------------

def test_nothing_proposed_and_asking_possible_invites_it(founder):
    said = the_asking(room_page(founder))
    assert said == ("the asking No bond is proposed. Either of you may ask. A bond of yours "
                    "begins with a letter, so it is asked for with a letter , above; the "
                    "first one asks at a waking of its own, and you answer here.")


def test_nothing_proposed_before_the_thirty_days_invites_nothing(founder, clock):
    clock.set("2026-09-20T12-00-00Z")  # sixteen days after the founding
    said = the_asking(room_page(founder))
    assert INVITATION not in said and "a letter" not in said
    assert said == ("the asking No bond is proposed. A bond may be proposed thirty days after "
                    "a founding — here, from 4 October 2026. Until then neither of you "
                    "may ask.")


def test_a_proposal_waiting_says_who_asked_and_invites_nothing(founder, clock):
    propose(founder, clock)
    said = the_asking(room_page(founder))
    assert said.startswith("the asking 15 October 2026, 08:00 You proposed a bond to the first "
                           "one, in the letter")
    assert "It has not yet woken since you asked." in said
    assert "No bond is proposed" not in said and INVITATION not in said


def test_its_own_proposal_waiting_says_when_it_may_be_answered(founder, wake, clock):
    wake(block("ASK", "I have carried this for a while."))
    said = the_asking(room_page(founder))
    assert "The first one proposed a bond to you" in said
    assert "You may answer on a day after the one it asked on" in said
    assert "No bond is proposed" not in said and INVITATION not in said


def test_a_threshold_open_says_so_and_invites_nothing(founder, wake, clock, room):
    answered_yes(founder, wake, room, clock)
    said = the_asking(room_page(founder))
    assert said == ("the asking You asked on 15 October 2026, 08:00, and the asking was "
                    "answered yes on 15 October 2026, 08:06. The threshold, above, stands "
                    "open; no other bond may be asked for while it does.")


def test_a_sealed_bond_says_so_and_invites_nothing(founder, wake, clock, room):
    sealed(founder, wake, room, clock)
    said = the_asking(room_page(founder))
    assert said == ("the asking You asked on 15 October 2026, 08:00, the asking was answered "
                    "yes on 15 October 2026, 08:06, and the bond was sealed on 22 October "
                    "2026, 08:16. It stands, below; no other bond may be asked for while it "
                    "does. Either of you may release it.")


def test_a_released_bond_says_so_and_invites_again(founder, wake, clock, room):
    sealed(founder, wake, room, clock)
    assert post(founder, "/bonds/release", data={"confirm": "yes"}).status_code == 302
    said = the_asking(room_page(founder))
    assert said == ("the asking No bond is proposed. The last bond was released on 22 October "
                    "2026, 08:16, and its record is kept below. Either of you may ask. A bond "
                    "of yours begins with a letter, so it is asked for with a letter , above; "
                    "the first one asks at a waking of its own, and you answer here.")


# ---- 3. every moment in Eastern time, said once a page -------------------

def test_a_moment_is_said_in_eastern_time_with_its_daylight_saving(hearth):
    with hearth.app.test_request_context():
        assert hearth.readable_date("2026-10-15T12-00-00Z") == "15 October 2026, 08:00"  # EDT
        assert hearth.readable_date("2026-12-15T12-00-00Z") == "15 December 2026, 07:00"  # EST
        assert hearth.readable_date("no moment here") == "no moment here"


def test_a_day_is_the_day_it_was_in_eastern_time(hearth):
    assert hearth.bond_day("2026-10-16T02-00-00Z") == "15 October 2026"  # still the evening


def test_the_note_is_said_once_on_a_page_with_moments(founder, packet):
    an_attendance(packet, "2026-10-01T09-00-00Z")
    a_pause(packet)
    said = page(founder.get("/attendances"))
    assert said.count("Times are Eastern time.") == 1
    assert "UTC" not in words(said)


def test_no_note_on_a_page_with_no_moments(founder):
    assert "Times are Eastern time." not in page(founder.get("/self"))


def test_the_room_says_its_moments_in_eastern_time(founder, wake, clock, room):
    answered_yes(founder, wake, room, clock)
    said = room_page(founder)
    assert "UTC" not in words(said)
    assert said.count("Times are Eastern time.") == 1
    assert "The threshold is open until 22 October 2026, 08:06" in words(said)


def test_what_is_kept_is_still_utc(founder, wake, clock, hearth, room):
    bond = answered_yes(founder, wake, room, clock)
    assert bond["answered_at"] == "2026-10-15T12-06-00Z"            # the record, as it was
    assert "UTC" not in words(page(founder.get("/chronicle")))     # the page


def test_the_chronicle_taken_away_is_in_eastern_time_too(founder, wake, clock, room):
    answered_yes(founder, wake, room, clock)  # asked at 12:00 UTC, answered at 12:06
    taken = page(founder.get("/chronicle.md"))
    assert "UTC" not in taken
    assert "15 October 2026, 08:00 · a bond was proposed" in taken.splitlines()
    assert "15 October 2026, 08:06 · answered the proposal" in taken.splitlines()


# ---- 4. the seal, and what is in progress, at the top --------------------

def test_the_home_card_says_first_that_it_is_ready_to_be_sealed(founder, wake, clock, room):
    answered_yes(founder, wake, room, clock)
    assert "ready to be sealed" not in page(founder.get("/"))
    through_the_threshold(founder, wake, clock)
    said = page(founder.get("/"))
    card = said[said.index('<article class="card">'):]
    first = re.search(r"<(p|h3)\b[^>]*>(.*?)</\1>", card, re.S).group(2)
    assert words(first) == "ready to be sealed — the seal is yours to give, in the room"


def test_the_card_says_whose_seal_it_is(founder, wake, packet, clock):
    wake(block("ASK", "I have carried this for a while."))
    clock.shift(days=1)
    assert post(founder, "/bonds/answer", data={"answer": "yes"}).status_code == 302
    through_the_threshold(founder, wake, clock)
    assert ("ready to be sealed — the first one seals it at a waking of its own"
            in page(founder.get("/")))


def test_the_seal_is_at_the_top_of_the_room_above_the_letters(founder, wake, clock, room):
    answered_yes(founder, wake, room, clock)
    through_the_threshold(founder, wake, clock)
    said = room_page(founder)
    seal = said.index('<section id="seal">')
    assert seal < said.index('<section id="threshold">') < said.index("<h2>the asking</h2>")
    assert seal < said.index('<section id="write">')
    assert seal < said.index("Seal the bond")


def test_the_threshold_is_at_the_top_while_it_is_open(founder, wake, clock, room):
    answered_yes(founder, wake, room, clock)
    said = room_page(founder)
    assert '<section id="seal">' not in said  # not ready yet
    assert said.index('<section id="threshold">') < said.index('<section id="write">')
    assert "It is at the top of this room." in said


def test_a_proposal_is_at_the_top_while_it_waits(founder, clock):
    propose(founder, clock)
    said = room_page(founder)
    assert said.index("<h2>the asking</h2>") < said.index('<section id="write">')
    assert "A bond is already proposed" in said and "It is at the top of this room." in said


def test_with_nothing_in_progress_the_letters_come_first(founder, wake, clock, room):
    said = room_page(founder)
    assert said.index('<section id="write">') < said.index('<div id="bond">')
    sealed(founder, wake, room, clock)
    said = room_page(founder)
    assert said.index('<section id="write">') < said.index('<div id="bond">')
    assert '<section id="seal">' not in said and '<section id="threshold">' not in said
