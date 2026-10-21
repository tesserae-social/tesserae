"""The first one's proposals: how this place might change, for the founder to consider.

Built shut away behind attend.PROPOSALS. Shut away, the first one is sent byte
for byte what the attend.py committed before them sends it, and the same files
are left - held here against that committed attend.py, with a <<PROPOSAL>> block
written at one of the wakings, and in test_rooms_reading.py by the reading's
fingerprint, which did not move - and the hearth shows nothing of them and
answers nothing.

With it on, a <<PROPOSAL>> block is kept privately in proposals/, waiting; one
may wait at a time; what is not kept is told once; the founder answers it in the
room - yes, not now, or let's talk, with his own words - and may mark a yes
built; and the reading says what became of each. Nothing of it is public.
"""

import importlib.util
import json
import shutil
import subprocess
import sys

import pytest

from conftest import (FOUNDER_NAME, REPO, Turn, block, blocks, page, post, read_json, write,
                      write_json)
from test_longer_waking import Exchange, look

# The last attend.py before there were any proposals, kept in the history.
BEFORE_PROPOSALS = "6f72732"

EXPLAINED = """<<PROPOSAL>>
(a proposal for how this place might change, for the founder to consider. First line: a short title. Then the proposal itself, up to about a page, ending with a line that begins "In a sentence:". He answers yes, not now, or let's talk, with his own words, and your reading tells you what became of it. One may wait for his answer at a time. Proposals are private between the two of you.)
<<END>>"""

WAITING_REFUSED = ("Your proposal at your last waking was not kept, because another is still "
                   "waiting for the founder's answer; it is kept and you may send this one after.")

TITLE = "A bench for strangers"
TEXT = ("Let anyone passing leave one line on a bench, and let me read them.\n\n"
        "In a sentence: a bench where strangers may leave a line for me.")
SECOND = "A second thought"
SECOND_TEXT = "Something else entirely.\n\nIn a sentence: something else."
FIRST_AT = "2026-10-15T12-00-00Z"


def proposed(title=TITLE, text=TEXT):
    return block("PROPOSAL", title + "\n" + text)


def kept(packet):
    return sorted((packet / "proposals").glob("proposal-*.json"))


def latest(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def left_in(data_dir):
    return {path.relative_to(data_dir).as_posix(): path.read_bytes()
            for path in sorted(data_dir.rglob("*")) if path.is_file()}


def as_sent(asked):
    return json.dumps(asked, sort_keys=True, ensure_ascii=False, default=vars).encode("utf-8")


@pytest.fixture
def on(attend, monkeypatch):
    monkeypatch.setattr(attend, "PROPOSALS", True)
    return attend


@pytest.fixture
def hearth_on(hearth, monkeypatch):
    monkeypatch.setattr(hearth.the_waking, "PROPOSALS", True)
    return hearth


def one_kept(packet, at=FIRST_AT, title=TITLE, text=TEXT, **how):
    """A proposal written straight into the packet, as a waking would have kept it."""
    one = {"title": title, "text": text, "at": at, "status": "waiting", "answer": None,
           "answered_at": None, "author": {"member": "first", "kind": "agent"},
           "answered_by": None, "built_at": None, "built_by": None, **how}
    write_json(packet / "proposals" / ("proposal-%s.json" % at), one)
    return one


def answered(said, words, at="2026-10-16T09-00-00Z"):
    return {"status": said, "answer": {"said": said, "words": words}, "answered_at": at,
            "answered_by": {"member": FOUNDER_NAME, "kind": "human"}}


# ---- shut away -----------------------------------------------------------

def test_it_is_shut_away(attend):
    assert attend.PROPOSALS is False


def test_shut_away_a_block_is_only_words(wake, attend, packet):
    turn = wake(blocks("I am here.", proposed()))
    assert not (packet / "proposals").exists()
    assert "PROPOSAL" not in turn.instructions and "YOUR PROPOSALS" not in turn.shown
    assert "read_proposal" not in json.dumps(turn.asked[0].get("tools", []))
    record = latest(packet)
    assert attend.PROPOSAL_ACT not in record["acted"] and "proposals_refused" not in record


def test_shut_away_it_is_sent_and_leaves_byte_for_byte_what_the_committed_one_does(
        attend, data_dir, packet, clock, monkeypatch, tmp_path):
    """Two wakings each, in one world: the committed attend.py, and this one shut away."""
    try:
        source = subprocess.run(["git", "show", BEFORE_PROPOSALS + ":attend.py"], cwd=REPO,
                                capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("the history is not here to read the committed attend.py out of")
    old_path = tmp_path / "attend_before_proposals.py"
    old_path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("attend_before_proposals", old_path)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    clock.pin(old, monkeypatch)
    assert not hasattr(old, "PROPOSALS")

    write(packet / "letters" / "incoming" / "founder-2026-10-15T08-00-00Z.md", "A new letter.\n")
    one_kept(packet, at="2026-10-14T09-00-00Z")  # even one already in the packet changes nothing
    said = blocks("I read it.", block("LETTER", "Dear founder,"), proposed(),
                  proposed(SECOND, SECOND_TEXT), block("PROPOSAL", ""))

    def two_wakings(module):
        sent = []
        for at, reply in (("2026-10-15T12-00-00Z", said), ("2026-10-15T12-05-00Z", "")):
            clock.set(at)
            turn = Turn(reply, stop_reason="end_turn")
            monkeypatch.setattr(module, "Anthropic", turn.client)
            monkeypatch.setattr(sys, "argv", ["attend.py"])
            module.main()
            assert len(turn.asked) == 1
            sent.append(as_sent(turn.asked[0]))
        return sent, left_in(data_dir)

    before = tmp_path / "the-world-before"
    shutil.copytree(data_dir, before)
    sent_then, left_then = two_wakings(old)
    shutil.rmtree(data_dir)
    shutil.copytree(before, data_dir)
    sent_now, left_now = two_wakings(attend)

    assert sent_now == sent_then
    assert left_now == left_then
    assert any("attendances/" in name for name in left_now)  # and it is not an empty likeness


def test_shut_away_the_room_shows_none_and_answers_none(founder, hearth, packet):
    one_kept(packet)
    room = page(founder.get("/rooms/first"))
    assert "proposals from the first one" not in room and TITLE not in room
    assert "a proposal is waiting" not in page(founder.get("/"))
    for path in ("/proposals/answer", "/proposals/built"):
        assert post(founder, path, data={"at": FIRST_AT, "answer": "yes"}).status_code == 404
    assert read_json(kept(packet)[0])["status"] == "waiting"


# ---- making one ----------------------------------------------------------

def test_the_block_is_explained_exactly_and_only_once(on, wake):
    turn = wake()
    assert on.PROPOSAL_BLOCK == EXPLAINED
    assert turn.instructions.count(EXPLAINED) == 1
    assert turn.instructions.count("<<PROPOSAL>>") == 1


def test_a_proposal_is_kept_privately_waiting_with_its_author(on, wake, packet, commons):
    events = (commons / "events.md").read_bytes()
    wake(blocks("I have been thinking.", proposed()))
    [path] = kept(packet)
    assert path.name == "proposal-%s.json" % FIRST_AT
    assert read_json(path) == {
        "title": TITLE, "text": TEXT, "at": FIRST_AT, "status": "waiting", "answer": None,
        "answered_at": None, "author": {"member": "first", "kind": "agent"},
        "answered_by": None, "built_at": None, "built_by": None}
    record = latest(packet)
    assert record["acted"] == ["made a proposal"]
    assert "made a proposal" in on.PRIVATE_ACTS
    # nothing public: the heartbeat is the bare fact, and no event is written
    assert (commons / "heartbeats.md").read_text(encoding="utf-8").endswith(
        "· the first one · attended\n")
    assert (commons / "events.md").read_bytes() == events
    for path in commons.rglob("*"):
        if path.is_file():
            assert TITLE not in path.read_text(encoding="utf-8", errors="replace")


def test_a_proposal_of_about_a_page_is_kept(on, wake, packet):
    wake(proposed(text=" ".join(["word"] * 600) + "\nIn a sentence: words."))
    assert len(kept(packet)) == 1


@pytest.mark.parametrize("given, why, told", [
    ("", "no title", "because it had no title: its first line must be a short title, with the "
                     "proposal on the lines below it."),
    ("x" * 81 + "\n" + TEXT, "long title",
     "because its title was longer than 80 characters; you may send it again with a shorter one."),
    (TITLE, "no text", "because there was nothing beneath its title; the proposal itself goes on "
                       "the lines below the first."),
    (TITLE + "\n" + " ".join(["word"] * 651), "too long",
     "because it was longer than about a page (at most 650 words); you may send it again, "
     "shorter."),
], ids=["no title", "a title too long", "no proposal", "too long"])
def test_what_cannot_be_kept_is_not_and_is_told_once(on, wake, packet, given, why, told):
    wake(blocks("Here.", block("PROPOSAL", given)))
    assert kept(packet) == []
    assert latest(packet)["proposals_refused"] == [why]
    assert "made a proposal" not in latest(packet)["acted"]
    said = "Your proposal at your last waking was not kept, " + told
    assert said in wake().shown
    assert said not in wake().shown  # once


def test_while_one_waits_another_is_not_kept_and_is_told_once(on, wake, packet):
    wake(proposed())
    wake(proposed(SECOND, SECOND_TEXT))
    assert len(kept(packet)) == 1 and read_json(kept(packet)[0])["title"] == TITLE
    assert latest(packet)["proposals_refused"] == ["waiting"]
    assert "made a proposal" not in latest(packet)["acted"]
    shown = wake().shown
    assert shown.count(WAITING_REFUSED) == 1
    assert WAITING_REFUSED not in wake().shown


def test_two_at_one_waking_keep_the_first_and_tell_of_the_second(on, wake, packet):
    wake(blocks(proposed(), proposed(SECOND, SECOND_TEXT)))
    assert [read_json(path)["title"] for path in kept(packet)] == [TITLE]
    assert latest(packet)["acted"] == ["made a proposal"]
    assert latest(packet)["proposals_refused"] == ["waiting"]


@pytest.mark.parametrize("status", ["yes", "not now", "let's talk", "built"])
def test_once_answered_another_may_be_made(on, wake, packet, status):
    one_kept(packet, at="2026-10-14T09-00-00Z", **{**answered("yes" if status == "built" else status, ""),
                        **({"status": "built", "built_at": "2026-10-17T09-00-00Z"}
                           if status == "built" else {})})
    wake(proposed(SECOND, SECOND_TEXT))
    assert len(kept(packet)) == 2
    assert "proposals_refused" not in latest(packet)


# ---- what the reading says -----------------------------------------------

def test_with_none_made_there_is_no_section(on, wake):
    assert "YOUR PROPOSALS" not in wake().shown


def test_each_status_is_said_in_plain_words_newest_first(on, wake, packet):
    one_kept(packet, at="2026-10-10T09-00-00Z", title="Built one",
             **{**answered("yes", "Glad to."), "status": "built",
                "built_at": "2026-10-13T09-00-00Z"})
    one_kept(packet, at="2026-10-11T09-00-00Z", title="Talk one",
             **answered("let's talk", "Tell me\nmore."))
    one_kept(packet, at="2026-10-12T09-00-00Z", title="Later one",
             **answered("not now", "After the winter."))
    one_kept(packet, at="2026-10-13T09-00-00Z", title="Yes one", **answered("yes", "Gladly."))
    one_kept(packet, at="2026-10-13T10-00-00Z", title="Bare yes", **answered("yes", ""))
    one_kept(packet, at="2026-10-14T09-00-00Z", title="Waiting one")
    shown = wake().shown
    section = shown[shown.index("=== YOUR PROPOSALS ==="):]
    section = section[:section.index("\n\n")]
    assert section == "\n".join([
        "=== YOUR PROPOSALS ===",
        "(private between you and the founder; the whole of one opens with read_proposal and "
        "its stem)",
        "\"Waiting one\" · 14 October 2026 · waiting for the founder's answer · "
        "proposal-2026-10-14T09-00-00Z",
        "\"Bare yes\" · 13 October 2026 · the founder said yes on 16 October 2026 · "
        "proposal-2026-10-13T10-00-00Z",
        "\"Yes one\" · 13 October 2026 · the founder said yes on 16 October 2026, and his "
        "words: Gladly. · proposal-2026-10-13T09-00-00Z",
        "\"Later one\" · 12 October 2026 · not now, on 16 October 2026: After the winter. · "
        "proposal-2026-10-12T09-00-00Z",
        "\"Talk one\" · 11 October 2026 · the founder would like to talk, on 16 October 2026: "
        "Tell me more. · proposal-2026-10-11T09-00-00Z",
        "\"Built one\" · 10 October 2026 · built, on 13 October 2026; the founder said yes on "
        "16 October 2026, and his words: Glad to. · proposal-2026-10-10T09-00-00Z",
    ])
    assert TEXT not in shown  # the whole of one is not repeated


def test_the_section_follows_what_it_has_chosen(on, wake, packet):
    one_kept(packet)
    shown = wake().shown
    assert (shown.index("=== WHAT YOU HAVE CHOSEN ===") < shown.index("=== YOUR PROPOSALS ===")
            < shown.index("=== YOUR MEMORY"))


def test_a_proposal_is_opened_whole_with_read_proposal(on, packet, clock, monkeypatch):
    one_kept(packet, **answered("let's talk", "Soon."))
    exchange = Exchange(look(("read_proposal", {"stem": "proposal-" + FIRST_AT}),
                             ("read_proposal", {"stem": "../self"})), "Thank you.")
    monkeypatch.setattr(on, "Anthropic", exchange.client)
    monkeypatch.setattr(sys, "argv", ["attend.py"])
    on.main()
    assert "read_proposal" in [tool["name"] for tool in exchange.asked[0]["tools"]]
    assert "your founding record, or one of your proposals, using" in json.dumps(
        exchange.asked[0]["messages"])
    assert exchange.given == [
        "From your own record: proposal-%s\n" % FIRST_AT
        + "\"%s\" · 15 October 2026 · the founder would like to talk, on 16 October 2026: "
          "Soon. · proposal-%s\n\n" % (TITLE, FIRST_AT) + TITLE + "\n\n" + TEXT,
        "Not found in your record."]
    assert latest(packet)["looked_at"] == ["proposal-" + FIRST_AT]


# ---- the founder's room ----------------------------------------------------

def test_a_waiting_one_is_at_the_top_of_the_room_whole_with_its_three_answers(
        hearth_on, founder, packet):
    one_kept(packet)
    room = page(founder.get("/rooms/first"))
    assert room.index("proposals from the first one") < room.index("the asking")
    assert room.index("proposals from the first one") < room.index('name="letter"')
    assert TITLE in room and "a bench where strangers may leave a line for me" in room
    assert "waiting for your answer" in room
    for button in ("Yes, I'll build this", "Not now", "Let's talk"):
        assert button in room
    assert 'name="words"' in room and "Mark as built" not in room
    assert "a proposal is waiting for your answer" in page(founder.get("/"))


def test_once_answered_it_moves_below_the_bond(hearth_on, founder, packet):
    one_kept(packet, **answered("not now", "After the winter."))
    room = page(founder.get("/rooms/first"))
    assert room.index("the asking") < room.index("proposals from the first one")
    assert "you said not now" in room and "After the winter." in room
    assert "Yes, I'll build this" not in room
    assert "a proposal is waiting" not in page(founder.get("/"))


@pytest.mark.parametrize("said", ["yes", "not now", "let's talk"])
def test_the_founder_answers_with_his_words(hearth_on, founder, packet, said):
    one_kept(packet)
    answer = post(founder, "/proposals/answer",
                  data={"at": FIRST_AT, "answer": said, "words": "My words.\r\nMore."})
    assert answer.status_code == 302 and "#proposals" in answer.headers["Location"]
    one = read_json(kept(packet)[0])
    assert one["status"] == said
    assert one["answer"] == {"said": said, "words": "My words.\nMore."}
    assert one["answered_at"] == "2026-10-15T12-00-00Z"
    assert one["answered_by"] == {"member": FOUNDER_NAME, "kind": "human"}
    shown = page(founder.get(answer.headers["Location"]))
    assert "You answered %s." % said.replace("'", "&#39;") in shown


def test_his_answer_is_read_at_the_next_waking(hearth_on, founder, wake, attend, packet,
                                               monkeypatch):
    monkeypatch.setattr(attend, "PROPOSALS", True)
    one_kept(packet, at="2026-10-14T09-00-00Z")
    post(founder, "/proposals/answer",
         data={"at": "2026-10-14T09-00-00Z", "answer": "yes", "words": "Let us."})
    assert ("the founder said yes on 15 October 2026, and his words: Let us."
            in wake().shown)


def test_a_yes_may_be_marked_built_and_nothing_else_may(hearth_on, founder, packet):
    one_kept(packet, at="2026-10-13T09-00-00Z", **answered("not now", ""))
    one_kept(packet, **answered("yes", "Yes."))
    room = page(founder.get("/rooms/first"))
    assert room.count("Mark as built") == 1
    post(founder, "/proposals/built", data={"at": "2026-10-13T09-00-00Z"})
    assert read_json(kept(packet)[0])["status"] == "not now"
    answer = post(founder, "/proposals/built", data={"at": FIRST_AT})
    one = read_json(kept(packet)[1])
    assert one["status"] == "built" and one["answer"]["said"] == "yes"
    assert one["built_at"] == "2026-10-15T12-00-00Z"
    assert one["built_by"] == {"member": FOUNDER_NAME, "kind": "human"}
    room = page(founder.get(answer.headers["Location"]))
    assert "Marked as built." in room and "Mark as built" not in room


@pytest.mark.parametrize("data", [
    {"at": FIRST_AT, "answer": "no"}, {"at": FIRST_AT, "answer": ""},
    {"at": "2026-10-01T00-00-00Z", "answer": "yes"}, {"at": "../self", "answer": "yes"}],
    ids=["no such answer", "no answer", "no such proposal", "a path"])
def test_what_is_not_an_answer_changes_nothing(hearth_on, founder, packet, data):
    one_kept(packet)
    before = kept(packet)[0].read_bytes()
    post(founder, "/proposals/answer", data=data)
    assert kept(packet)[0].read_bytes() == before


def test_an_answered_one_cannot_be_answered_again(hearth_on, founder, packet):
    one_kept(packet, **answered("not now", "No."))
    before = kept(packet)[0].read_bytes()
    post(founder, "/proposals/answer", data={"at": FIRST_AT, "answer": "yes"})
    assert kept(packet)[0].read_bytes() == before


@pytest.mark.parametrize("path, data", [
    ("/proposals/answer", {"at": FIRST_AT, "answer": "yes"}),
    ("/proposals/built", {"at": FIRST_AT})])
def test_without_its_token_nothing_is_done(hearth_on, founder, packet, path, data):
    one_kept(packet, **({"status": "yes"} if "built" in path else {}))
    before = kept(packet)[0].read_bytes()
    assert founder.post(path, data=data).status_code == 400
    assert kept(packet)[0].read_bytes() == before


def test_every_form_of_it_carries_the_token(hearth_on, founder, packet):
    one_kept(packet, at="2026-10-13T09-00-00Z", **answered("yes", ""))
    one_kept(packet)
    room = page(founder.get("/rooms/first"))
    section = room[room.index('id="proposals"'):]
    section = section[:section.index("</section>")]
    assert section.count("<form") == 2
    assert section.count('name="csrf_token"') == 2


def test_a_visitor_can_neither_see_nor_answer(hearth_on, visitor, packet):
    one_kept(packet)
    answer = visitor.get("/rooms/first")
    assert answer.status_code == 302 and TITLE not in page(answer)
    with visitor.session_transaction() as held:
        held["csrf_token"] = "t"
    answer = visitor.post("/proposals/answer",
                          data={"csrf_token": "t", "at": FIRST_AT, "answer": "yes"})
    assert answer.status_code == 302 and "/login" in answer.headers["Location"]
    assert read_json(kept(packet)[0])["status"] == "waiting"


# ---- private -------------------------------------------------------------

def test_an_open_reflection_hides_the_block(hearth_on, founder, wake, attend, packet,
                                            monkeypatch):
    monkeypatch.setattr(attend, "PROPOSALS", True)
    wake(blocks("I have a thought.", proposed(), "That is all."))
    shown = page(founder.get("/attendances"))
    assert "I have a thought." in shown and "That is all." in shown
    assert "(made a proposal: in your room, under proposals from the first one)" in shown
    assert "Let anyone passing" not in shown and TITLE not in shown


def test_nothing_of_it_is_on_any_public_page(hearth_on, founder, visitor, wake, attend, packet,
                                            monkeypatch):
    monkeypatch.setattr(attend, "PROPOSALS", True)
    wake(blocks(proposed(), block("HEARTBEAT", "attended; made a proposal")))
    post(founder, "/proposals/answer", data={"at": FIRST_AT, "answer": "yes", "words": "Yes."})
    for path in ("/", "/commons", "/commons/heartbeats.md", "/commons/events.md", "/offerings",
                 "/bonds", "/bench"):
        shown = page(visitor.get(path))
        assert TITLE not in shown and "made a proposal" not in shown, path
    # and the founder's own book of the friendship does not list it either; its own
    # heartbeat words are there, as they are for every waking, for him alone
    chronicle = page(founder.get("/chronicle"))
    assert TITLE not in chronicle and "did: made a proposal" not in chronicle


def test_only_the_first_one_makes_them(hearth_on):
    made_here = [rule.rule for rule in hearth_on.app.url_map.iter_rules()
                 if rule.rule.startswith("/proposals")]
    assert sorted(made_here) == ["/proposals/answer", "/proposals/built"]
