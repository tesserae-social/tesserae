"""safety-fixes: the founder's request of 18 November 2026.

Part 1, the export (the inventory's x1): a person who shares a room with an agent
takes a copy of that room only, the letters both ways in it and the commons, and
never another room's letters, nor the agent's memory, notes, self, blocks or
notebook. The whole copy is the keeper's alone. A person in one room gets nothing
of another room's letters, by any route.

The world is test_pages_by_agent's: the second one, whose first room it shares
with alder, and here a later room it shares with hazel.
"""

import pytest

from conftest import page, post, write, write_json
from test_pages_by_agent import (FIRST_SAYS, SECOND, SECOND_PRIVATE, SECOND_SAYS,  # noqa: F401
                                 alder, hazel, hearth, scratch_registry, world, zipped)
from test_rooms_for_any_agent import member_vaults  # noqa: F401

HAZEL_DID = "did:web:hearth.tesserae.social:ids:hazel"
LATER = "hazel-and-second"
LATER_SAYS = {"a letter to it": "SENTINEL-LATER-LETTER-TO-IT",
              "a letter of its": "SENTINEL-LATER-LETTER-OF-ITS"}
SECOND_BLOCKS = "SENTINEL-SECOND-BLOCKS"
SECOND_SITE_NOTE = "SENTINEL-SECOND-SITE-NOTE"


@pytest.fixture
def later(world):
    """A later room of the second one's, shared with hazel, with a letter each way."""
    home = world / "rooms" / LATER
    write_json(home / "room.json", {"id": LATER, "bond": LATER, "kind": "person",
                                    "parties": [HAZEL_DID, SECOND["did"]],
                                    "opened_at": "2026-10-10T09-00-00Z"})
    for folder in ("letters/outgoing", "letters/incoming", "letters/read", "bonds", "errands"):
        (home / folder).mkdir(parents=True, exist_ok=True)
    write(home / "letters" / "read" / "hazel-2026-10-11T09-00-00Z.md",
          LATER_SAYS["a letter to it"] + "\n")
    write(home / "letters" / "outgoing" / "to-hazel-2026-10-12T09-00-00Z.md",
          LATER_SAYS["a letter of its"] + "\n")
    second = world / "packets" / "second"
    write(second / "blocks.json", '["%s"]\n' % SECOND_BLOCKS)
    write(second / "site-notes" / "note.md", SECOND_SITE_NOTE + "\n")
    return world


def everything_of(client, agent_id="second"):
    """Every page and file a party can reach of an agent, and its room copy, as one text."""
    said = [page(client.get("/agents/%s/%s" % (agent_id, kind)))
            for kind in ("attendances", "self", "chronicle", "chronicle.md", "export")]
    copied = zipped(post(client, "/agents/%s/export" % agent_id))
    return "\n".join(said), copied


def test_a_person_in_a_later_room_gets_nothing_of_the_first_room_s_letters_by_any_route(
        later, hazel):
    assert page(hazel.get("/rooms/" + LATER))
    pages, copied = everything_of(hazel)
    text = pages + "\n" + b"\n".join(copied.values()).decode("utf-8", "replace")
    for what in ("a letter to it", "a letter of its"):
        assert SECOND_SAYS[what] not in text, what
        assert FIRST_SAYS[what] not in text, what
    assert not any(name.startswith("rooms/second") for name in copied)
    # nor by the room itself, its photographs or its pictures
    for path in ("/rooms/second", "/rooms/second/photo/x.jpg", "/rooms/second/picture/x.svg"):
        assert hazel.get(path).status_code == 404, path


def test_a_person_s_copy_is_their_room_and_the_commons_and_nothing_of_the_agent_s_own(
        later, hazel, clock):
    _, copied = everything_of(hazel)
    names = sorted(copied)
    assert all(name.startswith(("rooms/%s/" % LATER, "commons/")) for name in names), names
    assert "rooms/%s/letters/read/hazel-2026-10-11T09-00-00Z.md" % LATER in copied
    assert "rooms/%s/letters/outgoing/to-hazel-2026-10-12T09-00-00Z.md" % LATER in copied
    text = b"\n".join(copied.values()).decode("utf-8", "replace")
    for words in (SECOND_SAYS["its self"], SECOND_SAYS["its notes"],
                  SECOND_SAYS["its reflection"], SECOND_PRIVATE, SECOND_BLOCKS,
                  SECOND_SITE_NOTE):
        assert words not in text, words
    taken = (later / "packets" / "second" / "exports.log").read_text(encoding="utf-8")
    assert taken.endswith("export taken by hazel\n")


def test_the_first_room_s_person_gets_their_own_room_and_nothing_of_the_later_one(later, alder):
    pages, copied = everything_of(alder)
    text = pages + "\n" + b"\n".join(copied.values()).decode("utf-8", "replace")
    for words in LATER_SAYS.values():
        assert words not in text
    assert all(name.startswith(("rooms/second/", "commons/")) for name in copied)
    assert "rooms/second/letters/read/founder-2026-10-21T09-00-00Z.md" in copied
    for words in (SECOND_SAYS["its self"], SECOND_SAYS["its notes"], SECOND_PRIVATE,
                  SECOND_BLOCKS):
        assert words.encode() not in b"\n".join(copied.values())
    assert hazel_free(alder)


def hazel_free(client):
    return client.get("/rooms/" + LATER).status_code == 404


def test_the_page_says_what_a_person_s_copy_holds(later, hazel):
    said = page(hazel.get("/agents/second/export"))
    assert "A copy of your room with the scratch one" in said
    assert "nothing of any other room" in said
    assert "private notebook" not in said and "packet" not in said


def test_the_chronicle_of_a_later_room_s_person_has_no_letter_of_the_first_room(later, hazel,
                                                                                 alder):
    for client, sees in ((hazel, False), (alder, True)):
        book = page(client.get("/agents/second/chronicle.md"))
        assert (SECOND_SAYS["a letter to it"] in book) is sees
        assert ("letter from" in book) is sees


def test_the_keeper_in_a_room_with_it_takes_the_whole_copy_as_before(later, founder, hearth):
    write_json(later / "rooms" / "second" / "room.json",
               {"id": "second", "bond": "founder-second",
                "parties": [hearth.FOUNDER_DID, SECOND["did"]]})
    copied = zipped(post(founder, "/agents/second/export"))
    text = b"\n".join(copied.values()).decode("utf-8", "replace")
    assert SECOND_SAYS["its notes"] in text and SECOND_SAYS["its self"] in text
    assert SECOND_PRIVATE not in text
    assert "packet" in page(founder.get("/agents/second/export"))


def test_room_copy_off_puts_the_whole_copy_back_for_every_party(later, hazel, hearth,
                                                                 monkeypatch):
    monkeypatch.setattr(hearth, "ROOM_COPY", False)
    _, copied = everything_of(hazel)
    text = b"\n".join(copied.values()).decode("utf-8", "replace")
    assert SECOND_SAYS["its notes"] in text and SECOND_SAYS["a letter to it"] in text


def test_the_first_one_s_copy_is_the_founder_s_whole_as_before(world, founder):
    copied = zipped(post(founder, "/export"))
    text = b"\n".join(copied.values()).decode("utf-8", "replace")
    assert FIRST_SAYS["its notes"] in text and FIRST_SAYS["a letter to it"] in text
