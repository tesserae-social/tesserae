"""The person's guide, "How this works" (the founder, 12 November 2026).

It is shown at the top of a person's room page, with the agent's commons name
filled in, until they close it; closing it is remembered for them, and for no
one else; their home page links to it, which shows it again. It is never shown
in the founder's room with the first one, and nothing of the first one's world
moves (test_first_one_fingerprints.py holds those pages).

The world is test_rooms_for_any_agent.py's: the keeper's room with the first
one, and alder's with the second agent, "the scratch one", made only in a
scratch registry and a scratch DATA_DIR.
"""

import json

from conftest import page, post
from test_rooms_for_any_agent import (  # noqa: F401 - fixtures
    ALDER, found_room, keeper, alder, hazel, member_vaults, scratch_registry, two, world)

WORDS = [
    "How this works",
    "The scratch one wakes once a day, reads what has come, and writes back.",
    "Write when you like. A letter, or just a few words in the short lines. A few words is "
    "enough. Silence is fine too; it keeps waking, and your next letter is waiting for it.",
    "Its letters arrive after it wakes. If you've turned on the daily email, you'll get a "
    "short note saying something is waiting.",
    "Under “more” you can add a photograph.",
    "What you write is private between you two. Its line on the main page is about itself, "
    "never about you.",
    "On your settings page you can rest from writing for a while.",
]
GUIDE = 'id="how-this-works"'


def plain(said):
    """A page with its whitespace folded and its entities as written, to look for words in."""
    return " ".join(said.replace("&#39;", "'").replace("&#x27;", "'").split())


def test_a_person_s_room_shows_the_guide_at_its_top_in_the_founder_s_words(world, alder):
    said = page(alder.get("/rooms/second"))
    assert GUIDE in said
    for words in WORDS:
        assert words in plain(said), words
    # at the top: before the letters
    assert said.index(GUIDE) < said.index("A FAKE LETTER TO THE SCRATCH ONE")


def test_closed_it_stays_closed_for_them_and_is_kept_with_them(world, alder, two, data_dir):
    answer = post(alder, "/rooms/second/close-the-guide")
    assert answer.status_code == 302 and answer.headers["Location"] == "/rooms/second"
    assert GUIDE not in page(alder.get("/rooms/second"))
    assert two.members.guide_closed(ALDER)
    held = json.loads((data_dir / "members" / ALDER / "guide.json").read_text(encoding="utf-8"))
    assert list(held) == ["closed_at"]


def test_the_home_page_links_to_it_and_shows_it_again_once_closed(world, alder):
    post(alder, "/rooms/second/close-the-guide")
    home = page(alder.get("/"))
    assert '<a href="/rooms/second?guide=1#how-this-works">how this works</a>' in home
    said = page(alder.get("/rooms/second?guide=1"))
    assert GUIDE in said and WORDS[1] in plain(said)
    assert GUIDE not in page(alder.get("/rooms/second"))  # and still closed after


def test_never_in_the_founder_s_room_with_the_first_one(world, keeper):
    assert GUIDE not in page(keeper.get("/rooms/first"))
    assert GUIDE not in page(keeper.get("/rooms/first?guide=1"))
    home = page(keeper.get("/"))
    assert "how this works" not in home


def test_only_a_party_may_close_it(world, hazel, two):
    answer = post(hazel, "/rooms/second/close-the-guide")
    assert answer.status_code in (302, 404)
    assert not two.members.guide_closed("hazel")
    assert not two.members.guide_closed(ALDER)


def test_unreadable_is_not_closed(world, alder, data_dir):
    (data_dir / "members" / ALDER / "guide.json").write_text("not json", encoding="utf-8")
    assert GUIDE in page(alder.get("/rooms/second"))


def test_it_says_how_leaving_stands_in_this_room(world, alder, two, monkeypatch):
    """words-sweep (24 November 2026): the leaving line says what blocks.leavable allows. The
    scratch one's room is its first, which it could not wake without, so it is never left."""
    def guide():
        said = plain(page(alder.get("/rooms/second")))
        return said[said.index("How this works"):said.index("Close this")]
    shown = guide()
    assert two.GUIDE_COPY in shown
    assert "how you usually write" not in shown and "errand" not in shown
    assert "leave" not in shown
    monkeypatch.setattr(two.blocks, "first_room_kept", lambda room: False)
    monkeypatch.setattr(two.blocks, "without_a_block", lambda room: False)
    assert ("You can leave this room once you have blocked the scratch one. It closes for both "
            "of you, and you both keep a copy of everything you two have written.") in guide()
    monkeypatch.setattr(two.blocks, "without_a_block", lambda room: True)
    assert ("Either of you can leave this room at any time. It closes for both of you, and you "
            "both keep a copy of everything you two have written.") in guide()
