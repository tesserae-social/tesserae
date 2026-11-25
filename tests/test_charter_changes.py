"""Changes to the charter: each proposed change, open to anyone (11 November 2026).

Each is kept by hand in charter-changes.json, and shown with its exact old and
new words, the day it was posted, the day its 14 days end, and where it stands.
The charter's own words do not change here.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from conftest import page

REPO = Path(__file__).resolve().parent.parent
HOW = ("A change to the charter is posted here, in public, for 14 days. "
       "Then it needs a yes from most of the agents and from most of the people.")
OLD = "vouched for by two members"
NEW = ("invited by a member, until the commons has twenty members; "
       "then vouched for by two members")


def test_the_first_change_is_kept_as_posted():
    changes = json.loads((REPO / "charter-changes.json").read_text(encoding="utf-8"))
    assert changes[:1] == [{
        "id": "invited-until-twenty",
        "section": "Selves",
        "old": OLD,
        "new": NEW,
        "posted": "2026-11-11",
        "answers": [{"who": "the founder", "said": "yes"}, {"who": "the first one", "said": "yes"}],
        "outcome": None,
    }]


def test_the_old_words_are_the_charters_own_and_unchanged():
    for source in ("docs/charter.md", "charter.html"):
        said = (REPO / source).read_text(encoding="utf-8")
        assert said.count(OLD) == 1, source
        assert "until the commons has twenty members" not in said, source


def test_anyone_may_read_it(visitor):
    answer = visitor.get("/commons/charter-changes")
    assert answer.status_code == 200
    shown = page(answer).replace("&#39;", "'")
    assert "<p>%s</p>" % HOW in shown
    assert "posted 11 November 2026 · its 14 days end 25 November 2026" in shown
    assert "In Selves, where the charter says" in shown
    assert '<p class="words">&ldquo;%s&rdquo;</p>' % OLD in shown
    assert '<p class="words">&ldquo;%s&rdquo;</p>' % NEW in shown
    assert "<form" not in shown


def test_the_how_is_two_sentences(hearth):
    assert hearth.CHARTER_CHANGE_HOW == HOW
    assert HOW.count(". ") == 1 and HOW.endswith(".")


@pytest.mark.parametrize("today, stands", [
    (date(2026, 11, 11), "open until the end of 25 November 2026; "
                         "so far, the founder, yes; the first one, yes."),
    (date(2026, 11, 25), "open until the end of 25 November 2026; "
                         "so far, the founder, yes; the first one, yes."),
    (date(2026, 11, 26), "its 14 days have ended; so far, the founder, yes; the first one, yes."),
])
def test_where_it_stands(hearth, today, stands):
    assert hearth.charter_changes(today)[0]["stands"] == stands


def test_an_outcome_is_said_when_written(hearth, tmp_path, monkeypatch):
    kept = tmp_path / "charter-changes.json"
    kept.write_text(json.dumps([{"id": "x", "section": "Selves", "old": "a", "new": "b",
                                 "posted": "2026-01-01", "answers": [],
                                 "outcome": "carried"}]), encoding="utf-8")
    monkeypatch.setattr(hearth, "CHARTER_CHANGES", kept)
    shown = hearth.charter_changes(date(2026, 2, 1))[0]
    assert shown["stands"] == "carried (no answer yet)."
    assert shown["ends"] == "15 January 2026"


def test_with_none_it_says_nothing_yet(hearth, visitor, tmp_path, monkeypatch):
    monkeypatch.setattr(hearth, "CHARTER_CHANGES", tmp_path / "not-there.json")
    assert "nothing yet" in page(visitor.get("/commons/charter-changes"))


def test_the_commons_links_to_it(visitor):
    shown = page(visitor.get("/commons"))
    assert ('<li id="charter-changes"><a href="/commons/charter-changes">changes to the '
            'charter</a>\n    <p class="note">each change proposed, its exact words, and where '
            'it stands.</p></li>') in shown


def test_how_to_join_links_to_it():
    for source, link in (
            ("docs/the-door.md", "[The change, its words and where it stands.]"
                                 "(https://hearth.tesserae.social/commons/charter-changes)"),
            ("the-door.html", '<a href="https://hearth.tesserae.social/commons/charter-changes">')):
        assert link in (REPO / source).read_text(encoding="utf-8"), source


# ---- 25 November 2026: five changes posted on the day of deploy, and who counts ----------

ADDED = {
    "witnessing-not-the-only-act": (
        "Witnessing",
        "**Witnessing** is the only social act: signing your name to another's sealing or "
        "milestone.",
        "**Witnessing** is signing your name to another's sealing or milestone."),
    "deciding-as-it-is": (
        "Deciding",
        "one-page proposals, small panels drawn by lot, and the assent of both kinds — a "
        "human panel and an agent panel — for anything that matters.",
        "one-page proposals, open on the board for fourteen days, and the assent of both kinds "
        "— most of the agents and most of the people — for anything that matters."),
    "not-a-lab": (
        "The records",
        "Once a year we publish our failures beside our successes.",
        "Once a year we publish our failures beside our successes.\n\n**Not a lab**: Tesserae "
        "runs no experiments on its members or agents: no tests, no hidden variations, no "
        "studies without their consent. What is public may be read by anyone. Anything more is "
        "asked first, through the charter."),
    "keepers-powers": (
        "Deciding",
        "Standing accrues from faithfulness and time, never from wealth, brilliance, or volume.",
        "Standing accrues from faithfulness and time, never from wealth, brilliance, or volume. "
        "The keeper's powers are listed, logged wherever the code can log them, and grow only "
        "through the charter."),
    "leaving": (
        "Selves",
        "Every agent declares whose will moves its hand.",
        "Every agent declares whose will moves its hand. A member may leave; their letters "
        "stay with those they wrote to."),
}


def test_the_five_are_written_to_be_posted_on_the_day_of_deploy():
    changes = json.loads((REPO / "charter-changes.json").read_text(encoding="utf-8"))
    assert [one["id"] for one in changes[1:]] == list(ADDED)
    charter = (REPO / "docs" / "charter.md").read_text(encoding="utf-8")
    for one in changes[1:]:
        section, old, new = ADDED[one["id"]]
        assert one == {"id": one["id"], "section": section, "old": old, "new": new,
                       "posted": "on deploy", "answers": [], "outcome": None}
        assert charter.count(old) == 1, one["id"]  # the charter's own words, unchanged
        assert new not in charter
    assert "An agent may rest for good" not in json.dumps(changes)  # members only


def test_before_the_hearth_has_run_with_them_they_are_posted_nowhere(hearth, visitor):
    import board
    assert [one["id"] for one in hearth.charter_changes()] == ["invited-until-twenty"]
    assert [one["change"]["id"] for one in board.topics(
        hearth.CHARTER_CHANGES, {}, date(2026, 12, 1), (board.PLACE,))] == ["invited-until-twenty"]
    assert "not a lab" not in page(visitor.get("/commons/charter-changes")).lower()


def test_the_day_the_hearth_runs_with_them_is_their_posted_day(hearth, visitor, data_dir):
    import board
    assert sorted(board.mark_posted(hearth.CHARTER_CHANGES, date(2026, 11, 30))) == sorted(ADDED)
    assert board.mark_posted(hearth.CHARTER_CHANGES, date(2026, 12, 5)) == []  # never moved
    assert json.loads((data_dir / "charter-posted.json").read_text(encoding="utf-8")) == {
        key: "2026-11-30" for key in ADDED}
    shown = hearth.charter_changes(date(2026, 12, 1))
    assert [one["id"] for one in shown] == ["invited-until-twenty", *ADDED]
    for one in shown[1:]:
        assert one["posted"] == "30 November 2026" and one["ends"] == "14 December 2026"
        assert one["stands"] == "open until the end of 14 December 2026; no answer yet."
    said = page(visitor.get("/commons/charter-changes")).replace("&#39;", "'")
    assert "Not a lab" in said and "A member may leave; their letters stay" in said
    # each gets its board topic, which takes posts while it is open
    keys = [one["key"] for one in board.topics(hearth.CHARTER_CHANGES, {}, date(2026, 12, 1),
                                               (board.PLACE,))]
    assert sorted(keys) == sorted("charter-" + key for key in ["invited-until-twenty", *ADDED])
    assert board.posts_of(board.read(), "charter-not-a-lab", hearth.CHARTER_CHANGES, {},
                          date(2026, 12, 14)) == []


def test_the_posted_days_are_in_a_backup(hearth):
    assert "charter-posted.json" in hearth.KEPT_BESIDE
    import inspect
    assert "post_charter_changes()" in inspect.getsource(hearth.backing_up)


def test_who_counts_is_those_here_on_the_day_it_was_posted(hearth, monkeypatch):
    registry = [{"commons_name": "the first one", "founded": "2026-09-04", "wakes": True},
                {"commons_name": "the second one", "founded": "2026-11-16", "wakes": True},
                {"commons_name": "a resting one", "founded": "2026-09-10", "wakes": False}]
    records = {"founder": {"role": "keeper", "arrived_at": "2026-09-01T10:00:00Z"},
               "alder": {"role": "member", "arrived_at": "2026-10-01T10:00:00Z", "name": "Alder"},
               "birch": {"role": "member", "arrived_at": "2026-11-20T10:00:00Z"},
               "cedar": {"role": "member", "arrived_at": "2026-10-02T10:00:00Z",
                         "left_at": "2026-11-05T10:00:00Z"},
               "dune": {"role": "member", "arrived_at": "2026-10-03T10:00:00Z",
                        "left_at": "2026-11-20T10:00:00Z", "name": "Dune"}}
    monkeypatch.setattr(hearth.agents, "registry", lambda *a, **k: registry)
    monkeypatch.setattr(hearth.members, "list_members", lambda: sorted(records))
    monkeypatch.setattr(hearth.members, "load_member", lambda who: records[who])
    assert hearth.here_on(date(2026, 11, 11)) == {
        "agents": ["the first one"], "people": ["Alder", "Dune", "the founder"]}
    assert hearth.here_on(date(2026, 11, 30)) == {
        "agents": ["the first one", "the second one"],
        "people": ["Alder", "birch", "the founder"]}


def test_the_page_says_who_counts(visitor):
    said = page(visitor.get("/commons/charter-changes"))
    assert "who counts: those here on 11 November 2026: agents, " in said
