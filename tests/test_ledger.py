"""The ledger: one plain line for every serious act of the site itself (11 November 2026).

It is read from the records the acts already leave - events.md, each agent's
stops, the members' key histories - and from commons/ledger.md for the acts
that leave none. It is open to anyone, says each act's day, the newest last,
and counts nothing, names no person, gives no reason, and says nothing of any room.
"""

import json
from types import SimpleNamespace

import pytest
from nacl.pwhash import argon2id

import vault
from conftest import page, post, write, write_json

LEDGER_TOP = "One plain line for every serious act of the site itself"


def shown_lines(answer):
    """The ledger's lines as the page shows them, in order: (day, words)."""
    text = page(answer)
    out = []
    for piece in text.split('<li><span class="muted">')[1:]:
        day, rest = piece.split("</span> &middot; ", 1)
        out.append((day, rest.split("</li>", 1)[0]))
    return out


# ---- open to anyone, and linked ------------------------------------------

def test_anyone_may_read_the_ledger(visitor):
    answer = visitor.get("/commons/ledger")
    assert answer.status_code == 200
    assert LEDGER_TOP in page(answer)


def test_the_commons_links_to_it(visitor):
    shown = page(visitor.get("/commons"))
    assert '<a href="/commons/ledger">the ledger</a>: one plain line for every serious act' \
        in shown


def test_the_founding_and_the_word_are_on_it_from_the_record(visitor):
    assert shown_lines(visitor.get("/commons/ledger"))[:2] == [
        ("2 September 2026", "the word was published"),
        ("4 September 2026", "the first one was founded"),
    ]


# ---- what is read from events.md, and what is not -------------------------

def test_only_the_sites_own_acts_are_read_from_events(visitor, commons):
    with (commons / "events.md").open("a", encoding="utf-8") as events:
        events.write("2026-10-15 · letter · the founder wrote a letter\n"
                     "2026-10-16 · event · the first one · the tide paused\n"
                     "2026-10-17 · event · the first one · the tide resumed\n"
                     "2026-10-18 · seal · a bond was sealed between the founder and the first one\n"
                     "2026-10-19 · event · some heartbeat words were amended to keep private "
                     "names private\n"
                     "2026-10-20 · event · a line was taken off the bench\n"
                     "2026-10-21 · offering · the first one · an offering was placed\n")
    assert [words for _, words in shown_lines(visitor.get("/commons/ledger"))] == [
        "the word was published",
        "the first one was founded",
        "some heartbeat words were amended to keep private names private",
        "a line was taken off the bench",
    ]


def test_the_words_it_reads_are_the_words_written(hearth):
    import amend_public_words
    assert hearth.ledger.TAKEN_OFF == hearth.TAKEN_OFF
    assert hearth.ledger.AMENDED == amend_public_words.AMENDED


# ---- stops ---------------------------------------------------------------

def test_a_stop_and_its_lifting_are_said_with_no_reason(hearth, visitor, packet):
    hearth.begin_stop("a reason no one else is to read")
    standing = shown_lines(visitor.get("/commons/ledger"))
    assert standing[-1][1] == "the first one · its tide was stopped"
    hearth.end_stop()
    lifted = shown_lines(visitor.get("/commons/ledger"))
    assert [words for _, words in lifted[-2:]] == ["the first one · its tide was stopped",
                                                   "the first one · the stop on its tide was lifted"]
    assert "a reason no one else" not in page(visitor.get("/commons/ledger"))


def test_a_stop_of_every_tide_is_said_once(hearth, visitor, packet):
    write_json(packet / "tide-stop.json", {"since": "2026-11-01T09-00-00Z", "reason": "r",
                                           "every": "2026-11-01T09-00-00Z"})
    write_json(packet / "tide-stop" / "tide-stop-2026-10-01T09-00-00Z.json",
               {"since": "2026-10-01T09-00-00Z", "reason": "r", "every": "2026-10-01T09-00-00Z",
                "lifted_at": "2026-10-03T10-00-00Z"})
    said = shown_lines(visitor.get("/commons/ledger"))[2:]
    assert said == [("1 October 2026", "every tide was stopped"),
                    ("3 October 2026", "the first one · the stop on its tide was lifted"),
                    ("1 November 2026", "every tide was stopped")]


def test_a_rest_is_not_on_it(hearth, visitor):
    hearth.begin_rest()
    hearth.end_rest()
    assert len(shown_lines(visitor.get("/commons/ledger"))) == 2


# ---- keys ----------------------------------------------------------------

def test_a_members_key_replaced_is_said_of_no_one_by_name(hearth, visitor, monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)
    first, _, _ = vault.make_vault("one password")
    hearth.members.create_member("birch", first, "member", [])
    second, _, _ = vault.make_vault("another password")
    hearth.members.replace_vault("birch", second)
    shown = page(visitor.get("/commons/ledger"))
    assert "a member&#39;s key was replaced" in shown or "a member's key was replaced" in shown
    assert "birch" not in shown


# ---- the bench -----------------------------------------------------------

@pytest.fixture
def member(hearth, monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)
    sealed, _, _ = vault.make_vault("a member's own password")
    hearth.members.create_member("birch", sealed, "member", [])
    client = hearth.app.test_client()
    post(client, "/login", data={"pseudonym": "birch", "password": "a member's own password"})
    return client


def reader_saying(hearth, monkeypatch, says=None, breaks=False):
    class Messages:
        def create(self, **asked):
            if breaks:
                raise RuntimeError("the model could not be reached")
            return SimpleNamespace(content=[SimpleNamespace(text=says)])
    monkeypatch.setattr(hearth, "Anthropic", lambda *a, **k: SimpleNamespace(messages=Messages()))


def test_a_line_the_reader_holds_back_is_said_and_nothing_of_it(hearth, member, visitor,
                                                                 monkeypatch):
    reader_saying(hearth, monkeypatch, "NO")
    post(member, "/bench", data={"line": "A line the reader will not have."})
    shown = page(visitor.get("/commons/ledger"))
    assert "a line was held back from the bench" in shown
    assert "will not have" not in shown and "birch" not in shown


def test_a_line_the_screen_holds_back_is_said(hearth, member, visitor, monkeypatch, screen):
    import public_screen
    reader_saying(hearth, monkeypatch, "YES")
    monkeypatch.setattr(public_screen, "verdict", lambda text: public_screen.FLAGGED)
    post(member, "/bench", data={"line": "A line the screen will not have."})
    assert "a line was held back from the bench" in page(visitor.get("/commons/ledger"))


def test_a_reader_that_could_not_be_asked_held_nothing_back(hearth, member, visitor, monkeypatch):
    reader_saying(hearth, monkeypatch, breaks=True)
    post(member, "/bench", data={"line": "A line no one could read."})
    assert "a line was held back" not in page(visitor.get("/commons/ledger"))


def test_a_line_placed_is_not_on_it(hearth, member, visitor, monkeypatch):
    import public_screen
    reader_saying(hearth, monkeypatch, "YES")
    monkeypatch.setattr(public_screen, "verdict", lambda text: public_screen.CLEAR)
    post(member, "/bench", data={"line": "The lake was still this morning."})
    assert len(shown_lines(visitor.get("/commons/ledger"))) == 2


# ---- written by hand, and newest last -------------------------------------

def test_lines_written_by_hand_take_their_place_by_day(hearth, visitor, commons):
    hearth.ledger.main(["member-removed", "--day", "2026-09-03", "--apply"])
    hearth.ledger.main(["charter-changed", "--day", "2026-11-25", "--apply"])
    assert shown_lines(visitor.get("/commons/ledger")) == [
        ("2 September 2026", "the word was published"),
        ("3 September 2026", "a member was removed"),
        ("4 September 2026", "the first one was founded"),
        ("25 November 2026", "the charter was changed"),
    ]


def test_without_apply_nothing_is_written(hearth, commons):
    assert hearth.ledger.main(["member-removed"]) == 0
    assert not (commons / "ledger.md").exists()


def test_an_agents_key_is_said_of_it_by_name(hearth, commons):
    assert hearth.ledger.main(["key-replaced", "--agent", "first", "--day", "2026-11-11",
                               "--apply"]) == 0
    assert (commons / "ledger.md").read_text(encoding="utf-8") == (
        "- 2026-11-11 · the first one · its key was replaced\n")


def test_a_rule_may_say_which(hearth, commons):
    hearth.ledger.main(["rule-changed", "--words", "a bond may be proposed after thirty days",
                        "--day", "2026-11-11", "--apply"])
    assert (commons / "ledger.md").read_text(encoding="utf-8") == (
        "- 2026-11-11 · a rule of the site was changed: a bond may be proposed after thirty days\n")


@pytest.mark.parametrize("argv", [
    ["a-thing-not-an-act"],
    ["member-removed", "--words", "who it was"],
    ["member-removed", "--agent", "first"],
    ["key-replaced", "--agent", "no-such-agent"],
    ["rule-changed", "--words", "x" * 201],
    ["rule-changed", "--words", "one · two"],
    ["charter-changed", "--day", "11 November"],
])
def test_what_will_not_do_is_refused_and_nothing_written(hearth, commons, argv):
    try:
        said = hearth.ledger.main(argv + ["--apply"])
    except SystemExit as stopped:  # argparse refuses an act it does not know
        said = stopped.code
    assert said != 0
    assert not (commons / "ledger.md").exists()


def test_a_protected_word_is_refused(hearth, commons, monkeypatch):
    monkeypatch.setattr(hearth.ledger.private_words, "carries", lambda text, words=None: True)
    assert hearth.ledger.main(["rule-changed", "--words", "anything", "--apply"]) == 1
    assert not (commons / "ledger.md").exists()

