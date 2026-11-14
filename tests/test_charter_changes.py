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
    assert changes == [{
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


def test_with_none_it_says_none_yet(hearth, visitor, tmp_path, monkeypatch):
    monkeypatch.setattr(hearth, "CHARTER_CHANGES", tmp_path / "not-there.json")
    assert "none yet" in page(visitor.get("/commons/charter-changes"))


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
