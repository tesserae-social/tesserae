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
    "The scratch one wakes once a day at dawn, reads what has come, and writes back.",
    "Write when you like. A letter, or just a few words in the short lines. A few words is "
    "enough. Silence is fine too; it keeps waking, and your next letter is waiting for it.",
    "Its letters arrive in the morning. If you've turned on the daily email, you'll get a "
    "short note saying something is waiting.",
    "Under “more” you can add a photograph. It may ask you to go and notice something for "
    "it (an errand); you can answer when you can.",
    "What you write is private between you two. Its line on the main page is about itself, "
    "never about you.",
    "On your account page you can write a line about how you usually write, so it knows "
    "your rhythm, and rest from writing for a while.",
    "You can leave whenever you like, and take a copy of everything you two have written.",
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
