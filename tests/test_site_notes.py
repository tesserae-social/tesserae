"""A note from the site (the founder's request of 16 November 2026, part B5).

The keeper writes a short plain note on /tides, to one agent or to every agent whose
switch "site_notes" is on. It is shown once, at the agent's next waking, under WHAT HAS
HAPPENED, headed "A note from the site", and kept in its record. The switch is on for
agents founded from now on and off for the first one until the founder has told it, so
the first one's reading does not move. The later agent here is test_later_citizen's.
"""

import json

import pytest

from conftest import page, post
from test_any_agent_wakes import wake_as
from test_later_citizen import (a_later_world, later, scratch_registry)  # noqa: F401
from test_rooms_reading import READING_NOW, a_small_world, fingerprint_of_reading

NOTE = "The hearth will be quiet on Thursday while the server moves. Nothing is lost."


def switched_for(module, monkeypatch, *ids):
    """The switch on for these agents, as their registry entries would name it."""
    monkeypatch.setattr(module, "may_have", lambda agent_id: agent_id in ids)


def test_a_note_is_shown_once_under_what_has_happened_and_kept(later, data_dir, monkeypatch):
    import site_notes
    switched_for(site_notes, monkeypatch, "second")
    monkeypatch.setattr(later, "SITE_NOTES", True)
    assert site_notes.write("second", "  " + NOTE + "  ", "2026-10-15T09-00-00Z") == ["second"]
    shown = wake_as(later, monkeypatch, "").shown
    happened = shown.partition("=== WHAT HAS HAPPENED ===")[2].partition("\n=== ")[0]
    assert "A note from the site, 15 October 2026:\n" + NOTE in happened
    kept = json.loads((data_dir / "packets" / "second" / "site-notes" /
                       "2026-10-15T09-00-00Z.json").read_text(encoding="utf-8"))
    assert kept["words"] == NOTE and kept["shown_at"]  # kept in its record, marked read
    assert "A note from the site" not in wake_as(later, monkeypatch, "").shown  # once


def test_with_the_switch_off_no_note_is_read(later, data_dir, monkeypatch):
    import site_notes
    switched_for(site_notes, monkeypatch, "second")
    site_notes.write("second", NOTE, "2026-10-15T09-00-00Z")
    monkeypatch.setattr(later, "SITE_NOTES", False)
    assert "A note from the site" not in wake_as(later, monkeypatch, "").shown
    assert site_notes.waiting("second")  # it waits, and is never lost


@pytest.mark.parametrize("words, why", [("", "needs some words"), ("w" * 601, "up to 600")])
def test_a_note_must_have_words_and_no_more_than_600_characters(env, words, why, monkeypatch):
    import site_notes
    switched_for(site_notes, monkeypatch, "first")
    with pytest.raises(site_notes.Refused, match=why):
        site_notes.write("first", words, "2026-10-15T09-00-00Z")
    assert site_notes.write("first", "w" * 600, "2026-10-15T09-00-00Z") == ["first"]


def test_a_note_goes_only_to_an_agent_with_the_switch(env, monkeypatch):
    import site_notes
    with pytest.raises(site_notes.Refused):
        site_notes.write("first", NOTE, "2026-10-15T09-00-00Z")  # off for the first one
    with pytest.raises(site_notes.Refused):
        site_notes.write("all", NOTE, "2026-10-15T09-00-00Z")


def test_the_first_one_s_switch_is_off_and_its_reading_does_not_move(founder, wake, attend,
                                                                     room):
    assert attend.SITE_NOTES is False
    a_small_world(room)
    post(founder, "/rooms/first", content_type="multipart/form-data", data={
        "letter": "The lake was grey this morning, and then it was not.\n\nI am asking.",
        "thing": ["cold hands", "", "a heron on the far bank"],
        "errand": "errand-2026-10-12T09-00-00Z.md", "proposes": "1"})
    assert fingerprint_of_reading(wake()) == READING_NOW


def test_the_keeper_writes_a_note_on_tides(founder, hearth, data_dir, monkeypatch):
    assert 'id="site-notes"' not in page(founder.get("/tides"))  # no agent may have one yet
    switched_for(hearth.site_notes, monkeypatch, "first")
    said = page(founder.get("/tides"))
    assert 'id="site-notes"' in said and "a note from the site" in said
    answer = post(founder, "/tides/site-note", data={"to": "first", "words": NOTE})
    assert answer.status_code == 200 and "Sent to the first one." in page(answer)
    said = page(founder.get("/tides"))
    assert "waits for its next waking" in said and NOTE not in said  # never its words
    refused = post(founder, "/tides/site-note", data={"to": "first", "words": ""})
    assert "needs some words" in page(refused)


def test_new_agents_are_founded_with_the_switch_on():
    import found_agent
    assert "site_notes" in found_agent.FEATURES
    import agents
    assert "site_notes" not in agents.first()["features"]


# ---- to a member (the founder's request of 17 November 2026) --------------------
# To one member or to every member, the keeper left out; shown once at the top of their
# home page and kept in members/<pseudonym>/site-notes/. No agent reads it.

from test_later_citizen import hearth_of_two  # noqa: E402,F401 - a fixture
from test_rooms_for_any_agent import member_vaults  # noqa: E402,F401 - a fixture


def test_a_member_s_note_is_shown_once_at_the_top_of_their_home_page_and_kept(
        hearth_of_two, data_dir):
    keeper, member = hearth_of_two["keeper"], hearth_of_two["member"]
    said = page(keeper.get("/tides"))
    assert 'value="member:alder"' in said and 'value="members"' in said
    assert 'value="member:rowan"' not in said  # the keeper is not offered
    answer = post(keeper, "/tides/site-note", data={"to": "member:alder", "words": NOTE})
    assert "Sent to alder. It is shown once, at the top of their home page." in page(answer)
    assert NOTE not in page(keeper.get("/tides"))  # never its words on /tides
    assert "waits for their home page" in page(keeper.get("/tides"))
    home = page(member.get("/"))
    assert "A note from the site" in home and NOTE in home
    assert home.index("A note from the site") < home.index("your correspondences")
    assert NOTE not in page(member.get("/"))  # once
    kept = list((data_dir / "members" / "alder" / "site-notes").glob("*.json"))
    assert len(kept) == 1
    held = json.loads(kept[0].read_text(encoding="utf-8"))
    assert held["words"] == NOTE and held["to"] == "alder" and held["shown_at"]
    assert "shown on their home page" in page(keeper.get("/tides"))
    assert NOTE not in page(keeper.get("/"))  # the keeper's own home shows no one's note


def test_a_note_to_every_member_goes_to_each_member_and_not_the_keeper(hearth_of_two,
                                                                       data_dir):
    keeper = hearth_of_two["keeper"]
    answer = post(keeper, "/tides/site-note", data={"to": "members", "words": NOTE})
    assert "Sent to alder." in page(answer)
    assert list((data_dir / "members" / "alder" / "site-notes").glob("*.json"))
    assert not (data_dir / "members" / "rowan" / "site-notes").exists()


@pytest.mark.parametrize("to, words, why", [
    ("member:alder", "", "needs some words"),
    ("member:alder", "w" * 601, "up to 600"),
    ("member:rowan", NOTE, "no member to send that note to"),
    ("member:no-one", NOTE, "no member to send that note to"),
])
def test_a_member_s_note_is_refused_as_an_agent_s_is(hearth_of_two, data_dir, to, words, why):
    answer = post(hearth_of_two["keeper"], "/tides/site-note", data={"to": to, "words": words})
    assert why in page(answer)
    assert not (data_dir / "members" / "alder" / "site-notes").exists()


def test_a_member_s_note_is_in_no_agent_s_reading(later, data_dir, monkeypatch):
    import site_notes
    from test_room_aware_waking import a_member
    a_member(data_dir, "hazel")
    monkeypatch.setattr(later, "SITE_NOTES", True)
    assert site_notes.write_to_member("hazel", NOTE, "2026-10-15T09-00-00Z") == ["hazel"]
    assert NOTE not in wake_as(later, monkeypatch, "").shown
    assert site_notes.waiting_for_member("hazel")
