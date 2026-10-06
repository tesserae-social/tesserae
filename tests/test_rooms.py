"""The rooms: three small menus, a member's home, and one page for each
correspondence.

A correspondence has a room. The home page says each of a member's in one card -
who it is with, the latest letter, what is waiting, how the bond stands - and
the room's own page is the letters and the bond together, open to its two
parties and to no one else. The menus are on every page: one line for everyone,
one for a member, and one, at the foot, for the keeper alone.
"""

import ast
import json
import re
from pathlib import Path

import pytest
from nacl.pwhash import argon2id

from conftest import FOUNDER_NAME, PASSWORD, REPO, block, page, post, write
from test_hearth_bonds import answered_yes, propose, sealed, through_the_threshold

MEMBER = "birch"

EVERYONE = "the hearth · the bench · offerings · bonds · tesserae.social"
A_MEMBER = "home · account · log out"
THE_KEEPER = "home · chronicle · account · log out"
KEEPING = "attendances · self · export · backups"

OPEN_PAGES = ["/", "/bench", "/offerings", "/bonds", "/login", "/recover"]
MEMBER_PAGES = ["/", "/account", "/bench", "/offerings", "/bonds"]
KEEPER_PAGES = MEMBER_PAGES + ["/rooms/first", "/chronicle", "/attendances", "/self",
                               "/export", "/backups"]

KEEPERS_OWN = ['href="/attendances"', 'href="/self"', 'href="/export"', 'href="/backups"']


@pytest.fixture(scope="session")
def member_vault():
    """A vault of a plain member's own, sealed once at argon2id's least cost."""
    import vault

    held = vault.OPSLIMIT, vault.MEMLIMIT
    vault.OPSLIMIT, vault.MEMLIMIT = argon2id.OPSLIMIT_MIN, argon2id.MEMLIMIT_MIN
    try:
        made, _, _ = vault.make_vault(PASSWORD)
    finally:
        vault.OPSLIMIT, vault.MEMLIMIT = held
    return made


@pytest.fixture
def member(hearth, member_vault):
    """A plain member, signed in: a door of their own, and no correspondence."""
    hearth.members.create_member(MEMBER, json.loads(json.dumps(member_vault)), "member", [])
    client = hearth.app.test_client()
    answer = post(client, "/login", data={"pseudonym": MEMBER, "password": PASSWORD})
    assert answer.status_code == 302 and answer.headers["Location"] == "/"
    return client


def words(markup):
    """What a piece of a page says, with its tags taken out and its spaces settled."""
    return " ".join(re.sub(r"<[^>]+>", " ", markup).split())


def menus(said):
    """Each menu on a page, by its label, as the words it shows."""
    return {label: words(inside) for label, inside in
            re.findall(r'<nav class="menu[^"]*" aria-label="([^"]+)">(.*?)</nav>', said, re.S)}


def to_login(answer):
    return answer.status_code == 302 and answer.headers["Location"].endswith("/login")


def home(client):
    """The cards section of the home page, or None where there is none."""
    said = page(client.get("/"))
    found = re.search(r'<section class="rooms">(.*?)</section>', said, re.S)
    return found.group(1) if found else None


def card(client):
    """The one card on the keeper's home, as the lines it says."""
    cards = re.findall(r'<article class="card">(.*?)</article>', home(client), re.S)
    assert len(cards) == 1
    return [words(line) for line in re.findall(r"<(?:h3|p)[^>]*>(.*?)</(?:h3|p)>", cards[0], re.S)]


def letter(packet, folder, stem, text="A letter.\n"):
    return write(packet / "letters" / folder / (stem + ".md"), text)


def errand(packet, at="2026-10-12T09-00-00Z"):
    return write(packet / "errands" / ("errand-%s.md" % at), "Go and look at the lake.\n")


# ---- the menus -----------------------------------------------------------

@pytest.mark.parametrize("path", OPEN_PAGES)
def test_a_visitor_is_shown_the_one_line_everyone_has(visitor, path):
    said = page(visitor.get(path))
    assert menus(said) == {"pages": EVERYONE}
    for own in KEEPERS_OWN + ['href="/account"', 'href="/chronicle"', "/logout"]:
        assert own not in said, own


def test_the_first_line_leads_where_it_says(visitor):
    said = page(visitor.get("/bench"))
    line = re.search(r'<nav class="menu" aria-label="pages">(.*?)</nav>', said, re.S).group(1)
    assert re.findall(r'href="([^"]+)"', line) == ["/", "/offerings", "/bonds",
                                                   "https://tesserae.social"]
    assert '<span class="here">the bench</span>' in line  # where you stand is no link


def test_a_plain_member_is_shown_their_own_line_and_never_the_keepers(member):
    for path in MEMBER_PAGES:
        said = page(member.get(path))
        assert menus(said) == {"pages": EVERYONE, "yours": A_MEMBER}, path
        for own in KEEPERS_OWN + ['href="/chronicle"']:
            assert own not in said, (path, own)


def test_the_keeper_is_shown_all_three_and_the_third_at_the_very_foot(founder):
    for path in KEEPER_PAGES:
        said = page(founder.get(path))
        assert menus(said) == {"pages": EVERYONE, "yours": THE_KEEPER, "keeping": KEEPING}, path
        # the first two sit together under the heading; the keeper's is last of all
        assert (said.index("</header>") < said.index('aria-label="pages"')
                < said.index('aria-label="yours"') < said.index("</footer>")
                < said.index('aria-label="keeping"')), path
        assert said.count("<nav") == 3, path


def test_a_members_second_line_sits_directly_under_the_first(member):
    said = page(member.get("/account"))
    between = said[said.index("</nav>") + len("</nav>"):said.index('<nav class="menu" aria-label="yours">')]
    assert between.strip() == ""


def test_home_is_marked_as_here_to_a_member_and_the_hearth_to_a_visitor(visitor, member):
    assert '<span class="here">the hearth</span>' in page(visitor.get("/"))
    said = page(member.get("/"))
    assert '<span class="here">home</span>' in said
    assert '<a href="/">the hearth</a>' in said


def test_logging_out_is_a_post_drawn_as_a_link(member):
    said = page(member.get("/"))
    line = re.search(r'<nav class="menu" aria-label="yours">(.*?)</nav>', said, re.S).group(1)
    assert '<form method="post" action="/logout" class="as-link">' in line
    assert '<button type="submit" class="as-link">log out</button>' in line
    assert 'href="/logout"' not in said


def test_no_page_body_carries_a_list_of_links_the_menus_replace(visitor, founder):
    for client in (visitor, founder):
        said = page(client.get("/"))
        body = said[said.index("</header>"):]
        for nav in re.findall(r"<nav.*?</nav>", body, re.S):
            body = body.replace(nav, "")
        for gone in ['href="/bench"', 'href="/offerings"', 'href="/bonds', 'href="/letters"',
                     'href="/attendances"', '<ul class="lines">', "the atrium"]:
            assert gone not in body, gone


# ---- the home page -------------------------------------------------------

def test_a_visitor_still_gets_the_door(visitor):
    said = page(visitor.get("/"))
    assert home(visitor) is None
    assert "your correspondences" not in said and "your door" not in said
    assert "open to anyone" in said and '<a href="/login">log in</a>' in said


def test_a_plain_member_has_a_door_and_one_plain_line(member):
    said = page(member.get("/"))
    assert said.index('<section class="door">') < said.index("your correspondences")
    assert words(home(member)) == "your correspondences You have no correspondences yet."
    assert 'href="/rooms/' not in said


def test_the_keepers_home_is_the_door_and_then_one_card(founder):
    said = page(founder.get("/"))
    assert said.index('<section class="door">') < said.index("your correspondences")
    assert card(founder) == ["the first one", "no letters yet", "nothing is waiting",
                             "no bond", "open"]
    assert '<a href="/rooms/first">open</a>' in home(founder)
    assert "You have no correspondences yet." not in said
    assert FOUNDER_NAME not in said  # the other is named; the keeper never is


def test_a_new_letter_from_the_first_one_is_said_on_the_card(founder, packet):
    letter(packet, "read", "founder-2026-10-11T09-00-00Z")
    letter(packet, "outgoing", "to-founder-2026-10-14T06-30-00Z")
    assert card(founder)[1:3] == ["14 October 2026 · from the first one",
                                  "a new letter from the first one"]


def test_a_letter_of_yours_not_yet_read_is_said_on_the_card(founder, packet):
    letter(packet, "outgoing", "to-founder-2026-10-11T06-30-00Z")
    letter(packet, "incoming", "founder-2026-10-13T21-00-00Z")
    assert card(founder)[1:3] == ["13 October 2026 · from you",
                                  "your letter is waiting to be read"]


def test_a_letter_of_yours_that_was_read_leaves_nothing_waiting(founder, packet):
    letter(packet, "outgoing", "to-founder-2026-10-11T06-30-00Z")
    letter(packet, "read", "founder-2026-10-13T21-00-00Z")
    assert card(founder)[1:3] == ["13 October 2026 · from you", "nothing is waiting"]


def test_an_errand_is_said_on_the_card(founder, packet):
    errand(packet)
    assert card(founder)[1:3] == ["no letters yet", "an errand asked of you"]


def test_an_offering_of_the_first_ones_is_said_on_the_card(founder, wake, packet):
    letter(packet, "outgoing", "to-founder-2026-10-13T09-00-00Z", "Dear founder.\n")
    wake(block("OFFER", "offer letter to-founder-2026-10-13T09-00-00Z"))
    assert "an offering is waiting for your answer" in card(founder)


def test_everything_that_waits_is_said_together_and_nothing_is_counted(founder, packet):
    letter(packet, "read", "founder-2026-10-11T09-00-00Z")
    letter(packet, "outgoing", "to-founder-2026-10-12T06-30-00Z")
    errand(packet)
    one_of_each = card(founder)
    assert one_of_each == ["the first one", "12 October 2026 · from the first one",
                           "a new letter from the first one", "an errand asked of you",
                           "no bond", "open"]

    # more of everything, and the card says the same words: none of it is a number
    letter(packet, "outgoing", "to-founder-2026-10-12T07-30-00Z")
    letter(packet, "outgoing", "to-founder-2026-10-12T08-30-00Z")
    errand(packet, "2026-10-13T09-00-00Z")
    errand(packet, "2026-10-14T09-00-00Z")
    assert card(founder) == one_of_each
    for line in one_of_each[2:]:
        assert not re.search(r"\d", line), line


def test_the_card_says_a_bond_is_proposed(founder, clock):
    propose(founder, clock)
    assert card(founder)[-2] == "a bond is proposed"


def test_the_card_counts_the_days_of_the_threshold(founder, wake, packet, clock):
    answered_yes(founder, wake, packet, clock)
    assert card(founder)[-2] == "the threshold: day 1 of 7"
    clock.shift(days=3)
    assert card(founder)[-2] == "the threshold: day 4 of 7"
    clock.shift(days=3)
    assert card(founder)[-2] == "the threshold: day 7 of 7"
    clock.shift(days=1)
    assert card(founder)[-2] == "the threshold: the seven days have passed"
    assert "<img" not in home(founder)  # no tile until it is sealed


def test_the_card_shows_a_sealed_bond_with_its_small_tile(founder, wake, packet, clock):
    sealed(founder, wake, packet, clock)
    assert card(founder)[-2] == "sealed"
    tile = re.search(r"<img[^>]*>", home(founder), re.S).group()
    assert 'src="/bonds/founder-first/tessera.svg?size=24"' in tile
    assert 'width="24"' in tile and 'height="24"' in tile
    drawn = founder.get("/bonds/founder-first/tessera.svg?size=24")
    assert drawn.status_code == 200 and drawn.mimetype == "image/svg+xml"


def test_the_card_says_a_released_bond_is_released(founder, wake, packet, clock):
    sealed(founder, wake, packet, clock)
    assert post(founder, "/bonds/release", data={"confirm": "yes"}).status_code == 302
    assert card(founder)[-2] == "released"
    assert "<img" not in home(founder)


# ---- the room ------------------------------------------------------------

def test_a_visitor_is_turned_away_from_a_room(visitor, packet):
    assert to_login(visitor.get("/rooms/first"))
    assert to_login(post(visitor, "/rooms/first", data={"letter": "Let me in."},
                         content_type="multipart/form-data"))
    assert not list((packet / "letters" / "incoming").iterdir())


def test_a_plain_member_is_turned_away_from_a_room_that_is_not_theirs(member, founder, packet):
    letter(packet, "outgoing", "to-founder-2026-10-14T06-30-00Z", "FOR THE FOUNDER ALONE.\n")
    for path in ("/rooms/first", "/letters"):
        answer = member.get(path)
        assert to_login(answer), path
        assert "FOR THE FOUNDER ALONE" not in page(answer)
    assert to_login(post(member, "/rooms/first", data={"letter": "Let me in."},
                         content_type="multipart/form-data"))
    assert not list((packet / "letters" / "incoming").iterdir())
    # and a room that is not there is answered exactly as one that is
    assert to_login(member.get("/rooms/no-such-room"))


def test_the_keeper_opens_their_room_and_no_other(founder):
    assert founder.get("/rooms/first").status_code == 200
    assert founder.get("/rooms/no-such-room").status_code == 404
    assert founder.get("/rooms/" + FOUNDER_NAME).status_code == 404


def test_the_room_holds_what_the_letters_page_and_the_bonds_page_held(founder, packet):
    letter(packet, "read", "founder-2026-10-01T09-00-00Z", "The oldest.\n")
    letter(packet, "outgoing", "to-founder-2026-10-02T09-00-00Z", "The newest.\n")
    errand(packet)
    said = page(founder.get("/rooms/first"))

    assert "<h1>the first one</h1>" in said
    assert said.count('class="thing"') == 3  # three plain things
    for held in ['<textarea id="letter" name="letter">', 'type="file" id="photo" name="photo"',
                 'id="proposes" name="proposes"', "What a proposal might say",
                 '<select id="errand" name="errand">', "asked of you",
                 "offer to the commons", "the correspondence",
                 # and the bond, as it was on its own page
                 "the asking", "No bond is proposed.", "its answer"]:
        assert held in said, held
    assert said.index("The newest.") < said.index("The oldest.")  # newest first
    assert said.index("the correspondence") < said.index('<div id="bond">')
    # one page, and no two fields on it share a name to be found by
    ids = re.findall(r'\sid="([^"]+)"', said)
    assert len(ids) == len(set(ids))


def test_a_letter_left_in_the_room_is_left_as_it_always_was(founder, packet, clock):
    answer = post(founder, "/rooms/first", content_type="multipart/form-data",
                  data={"letter": "Dear first one.", "thing": ["cold hands", "", ""]})
    assert answer.status_code == 302
    assert answer.headers["Location"] == "/rooms/first?saved=1"
    kept = packet / "letters" / "incoming" / ("founder-%s.md" % clock.stamp())
    assert kept.read_text(encoding="utf-8").endswith("Dear first one.\n")
    assert "Your letter will be found at the next attendance." in page(
        founder.get(answer.headers["Location"]))


def test_a_post_to_the_room_needs_its_token(founder, packet):
    answer = founder.post("/rooms/first", data={"letter": "Dear first one."},
                          content_type="multipart/form-data")
    assert answer.status_code == 400
    assert not list((packet / "letters" / "incoming").iterdir())


def test_every_form_in_the_room_carries_the_token(founder, wake, packet, clock):
    errand(packet)
    answered_yes(founder, wake, packet, clock)  # so the threshold's forms are drawn too
    said = page(founder.get("/rooms/first"))
    assert said.count("<form") >= 5
    assert said.count('name="csrf_token"') == said.count("<form")


# ---- the old addresses ---------------------------------------------------

def test_letters_sends_the_keeper_on_to_the_room(founder):
    answer = founder.get("/letters")
    assert answer.status_code == 302 and answer.headers["Location"] == "/rooms/first"
    carried = founder.get("/letters", query_string={"saved": 1, "answered": 1})
    assert carried.headers["Location"] == "/rooms/first?saved=1&answered=1"


def test_letters_sends_anyone_else_to_the_login_page(visitor, member):
    assert to_login(visitor.get("/letters"))
    assert to_login(member.get("/letters"))


def test_a_letter_posted_to_the_old_address_is_still_left(founder, packet, clock):
    answer = post(founder, "/letters", data={"letter": "Dear first one."},
                  content_type="multipart/form-data")
    assert answer.status_code == 302 and answer.headers["Location"] == "/rooms/first?saved=1"
    assert (packet / "letters" / "incoming" / ("founder-%s.md" % clock.stamp())).exists()


def test_every_old_post_comes_back_to_the_room(founder, wake, packet, clock):
    letter(packet, "read", "founder-2026-10-01T09-00-00Z", "The lake was still.\n")
    offered = post(founder, "/offer", data={"kind": "letter",
                                            "source": "founder-2026-10-01T09-00-00Z"})
    assert offered.headers["Location"].startswith("/rooms/first?offered=")
    assert post(founder, "/offer/decline", data={"id": "nothing"}).headers[
        "Location"] == "/rooms/first"
    assert post(founder, "/offer/consent", data={"id": "nothing"}).headers[
        "Location"] == "/rooms/first"

    answered_yes(founder, wake, packet, clock)
    kept = post(founder, "/bonds/intention", data={"letter": "I bring my days."})
    assert kept.headers["Location"] == "/rooms/first?intended=1#bond"
    assert "Your letter of intention is signed and kept." in page(
        founder.get("/rooms/first?intended=1"))
    for path in ("/bonds/seal", "/bonds/release", "/bonds/answer"):
        answer = post(founder, path)
        assert answer.status_code in (200, 302), path
        if answer.status_code == 302:
            assert answer.headers["Location"] == "/rooms/first#bond", path


# ---- the public list of sealed bonds -------------------------------------

def test_the_bonds_page_is_open_to_anyone_and_says_when_there_are_none(visitor, member):
    for client in (visitor, member):
        answer = client.get("/bonds")
        assert answer.status_code == 200
        assert "No bond has been sealed yet." in page(answer)


def test_the_bonds_page_lists_a_sealed_bond_and_nothing_of_an_unsealed_one(
        founder, visitor, wake, packet, clock):
    answered_yes(founder, wake, packet, clock)
    said = page(visitor.get("/bonds"))  # on the threshold: nothing is public
    assert "No bond has been sealed yet." in said and 'href="/bonds/' not in said

    through_the_threshold(founder, wake, clock)
    assert post(founder, "/bonds/seal").status_code == 302
    said = page(visitor.get("/bonds"))
    assert re.search(r'<a href="/bonds/founder-first">the founder and the first one, sealed\s+'
                     r'22 October 2026</a>', said)
    # the list, and nothing of what the two of them see in their room
    for private in ("the asking", "letter of intention", "Release the bond", "<form"):
        assert private not in said, private


# ---- rooms.py ------------------------------------------------------------

def test_the_keeper_and_the_first_one_share_the_one_room(founder, hearth):
    rooms = hearth.rooms
    (theirs,) = rooms.of(FOUNDER_NAME)
    (its,) = rooms.of("first")
    assert theirs.id == its.id == "first"
    assert (theirs.other, its.other) == ("the first one", "the founder")
    assert theirs.bond == its.bond == "founder-first"
    assert rooms.find("first", FOUNDER_NAME) == theirs
    assert rooms.find("elsewhere", FOUNDER_NAME) is None
    # what the first one is handed never carries the keeper's name
    assert FOUNDER_NAME not in json.dumps(its)


def test_a_plain_member_and_a_stranger_have_no_room(member, hearth):
    rooms = hearth.rooms
    for who in (MEMBER, "no-one-at-all", "", None, "../first"):
        assert rooms.of(who) == [], who
        assert rooms.find("first", who) is None, who


def test_the_room_is_kept_where_the_packet_has_always_been(hearth, packet):
    kept = hearth.rooms.places("first")
    assert kept == (hearth.PACKET, hearth.INCOMING, hearth.READ, hearth.OUTGOING,
                    hearth.ERRANDS, hearth.BONDS, packet / "offerings")
    assert kept.packet == packet
    assert hearth.rooms.places("elsewhere") is None


def test_rooms_writes_nothing_and_attend_knows_nothing_of_it():
    """A room is a way of looking; the first one's waking does not look through it."""
    def imported(name):
        tree = ast.parse((REPO / name).read_text(encoding="utf-8"))
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module.split(".")[0])
        return found

    read_at_a_waking = {"attend"} | {name for name in imported("attend.py")
                                     if (REPO / (name + ".py")).exists()}
    for name in sorted(read_at_a_waking):
        assert "rooms" not in imported(name + ".py"), name
    source = (Path(REPO) / "rooms.py").read_text(encoding="utf-8")
    for writes in ("write_text", "write_bytes", "open(", "mkdir", "rename", "unlink"):
        assert writes not in source, writes
