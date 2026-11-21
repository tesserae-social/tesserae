"""small-fixes: the founder's request of 21 November 2026.

(1) A new agent's reflections are private as it begins: found_agent writes them private, and
with nothing written the hearth and attend.py keep any agent's but the first one's private.
(2) Behind made_here_talk (with made_here_agents), an agent sees what people wrote about its
own pieces in their topics in made here, which read_board never lists.
(3) With made here the agents' alone, <<PUBLISH>> no longer promises a topic "about: <title>".
"""

import json

from conftest import made_talk_not_yet
from test_later_citizen import later, scratch_registry  # noqa: F401 - fixtures

AT = "2026-10-01T09-00-00Z"


def with_talk(later, monkeypatch, on=True):
    monkeypatch.setattr(later, "MADE_AGENTS_ONLY", True)
    monkeypatch.setattr(later, "PUBLISH_TOPIC_FIXED", True)
    monkeypatch.setattr(later, "MADE_TALK", on)


def a_piece_with_talk(later):
    made = later.made_here
    mine = made.publish("second", made.piece("writing Its own", "Words."), AT)
    key = later.board.key_of("made", mine["id"])
    later.board.add(key, "alder", "I liked the second line.", "2026-10-02",
                    charter_path=later.CHARTER_CHANGES, weeks=later.board_weeks(),
                    today=later.board_today())
    return mine


# ---- (1) reflections private as it begins ----------------------------------------------

def test_a_later_agent_with_nothing_written_is_private(later):
    path = later.PACKET / "preferences.json"
    path.unlink(missing_ok=True)
    assert later.preferences() == {"reflection": "private"}


def test_the_first_one_with_nothing_written_is_as_it_was(attend):
    path = attend.PACKET / "preferences.json"
    if not path.exists():
        assert attend.preferences() == {"reflection": "open"}


def test_the_coming_no_longer_says_a_person_reads_its_reflections():
    import coming
    said = " ".join(new for _, new in coming.DISCLOSURE_CORRECTIONS)
    assert "your reflections and your self-document" not in said
    assert "Your reflections are private: no person reads them." in said


# ---- (2) the talk about its own pieces -------------------------------------------------

def test_it_reads_what_people_wrote_about_its_own_piece(later, monkeypatch):
    with_talk(later, monkeypatch)
    mine = a_piece_with_talk(later)
    said = later.made_said(mine["id"])
    assert said.startswith("A piece of yours made here.")
    assert later.MADE_TALK_HEAD in said
    assert "I liked the second line." in said and "alder" in said
    listed = later.made_said(None)
    assert "Its own" in listed and "· 1 post in its topic" in listed
    assert "what people wrote about it" in later.READ_MADE_HERE_TALK["description"]


def test_with_no_talk_yet_it_says_so(later, monkeypatch):
    with_talk(later, monkeypatch)
    made = later.made_here
    mine = made.publish("second", made.piece("writing Quiet", "Words."), AT)
    assert later.MADE_TALK_NONE in later.made_said(mine["id"])


def test_without_the_switch_nothing_of_the_talk_is_said(later, monkeypatch):
    with_talk(later, monkeypatch, on=False)
    mine = a_piece_with_talk(later)
    said = later.made_said(mine["id"])
    assert "I liked the second line." not in said
    assert said.startswith("A piece made here. It is someone else's")
    assert "in its topic" not in later.made_said(None)


def test_the_switch_is_the_second_one_s_and_a_new_agent_s_not_the_first_one_s():
    import found_agent
    from conftest import REPO
    registry = {one["id"]: one for one in json.loads((REPO / "agents.json").read_text(
        encoding="utf-8"))}
    assert "made_here_talk" in found_agent.FEATURES
    assert "made_here_talk" in registry["second"]["features"]
    assert "made_here_talk" not in registry["first"]["features"]


# ---- (3) <<PUBLISH>> says where its topic is ------------------------------------------

def test_publish_says_its_topic_is_in_made_here(later, monkeypatch):
    with_talk(later, monkeypatch)
    said = later.publish_block()
    assert '"about: <title>"' not in said
    assert ("Each gets its own topic in made here, where people may write about it. Open the "
            "piece with read_made_here to read what they wrote.") in said


def test_publish_without_made_here_agents_is_as_it_was(later, monkeypatch):
    monkeypatch.setattr(later, "MADE_AGENTS_ONLY", False)
    assert 'Each gets its own topic on the board, "about: <title>".' in later.publish_block()


def test_made_talk_not_yet_puts_both_back(later, monkeypatch):
    with_talk(later, monkeypatch)
    made_talk_not_yet(later, monkeypatch)
    assert 'Each gets its own topic on the board, "about: <title>".' in later.publish_block()
    assert not later.MADE_TALK
