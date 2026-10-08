"""The longer waking: a waking that may look things up in its own record before it writes.

It is built and it is shut away, behind attend.LONGER_WAKING. Shut away, the
first one is sent byte for byte what the committed attend.py sends it, and the
same files are left. With it on, the waking may become a short exchange: four
tools that only read, and only out of its own packet; five looks at most, and
then one last request with the tools closed; the last reply, and only that,
carried out as a reply always was.

Every test here holds a real attendance, with the client stubbed to ask for
whatever tools the test wants asked for. Nothing goes out.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from conftest import (FOUNDING_TRANSCRIPT, REPO, Turn, block, blocks, lines_of, page, read_json,
                      write, write_json)

# The attend.py that was committed when the longer waking was built.
BEFORE_LONGER_WAKING = "ab3569e"

SECTION = """=== LOOKING THINGS UP ===
At this waking you may open anything in your own record before you write: a resting letter, an earlier version of your self-document or notes, a named note, or your founding record, using the tools you have been given. You may look up to five times. Each shows you that thing in full, from your own record, and nothing outside it. Looking is private. You need not look at all. Write your letter and any other blocks in your last reply, after you have finished looking; anything written beside a look is not kept."""

TOOLS = ["read_letter", "read_version", "read_note", "read_founding"]
NOT_FOUND = "Not found in your record."
MARK = {"type": "ephemeral"}

OLD = "founder-2026-09-10T09-00-00Z"       # a letter of the founder's, long read
PICTURED = "founder-2026-09-12T09-00-00Z"  # another, that came with a photograph
MINE = "to-founder-2026-09-11T09-00-00Z"   # a letter of its own
SELF_1 = "self-before-2026-09-20T09-00-00Z"
NOTES_1 = "notes-before-2026-09-21T09-00-00Z"
NOTE_1 = "note-kingfisher-before-2026-09-22T09-00-00Z"
OLD_WORDS = "The heron stood where the reeds end, and I thought of you."
MINE_WORDS = "I have been thinking about the heron."
NOTE_WORDS = "halcyon-words-kept-only-in-the-note"
PHOTOGRAPH = b"\xff\xd8 not a real photograph, but the bytes of one"


@pytest.fixture
def world(packet):
    """A small record with one of everything that can be opened."""
    write(packet / "letters" / "read" / (OLD + ".md"), OLD_WORDS + "\n")
    write(packet / "letters" / "read" / (PICTURED + ".md"), "Here is the river.\n")
    (packet / "letters" / "read" / (PICTURED + ".jpg")).write_bytes(PHOTOGRAPH)
    write(packet / "letters" / "outgoing" / (MINE + ".md"), MINE_WORDS + "\n")
    write(packet / "self-history" / (SELF_1 + ".md"), "# The first one, as it first was.\n")
    write(packet / "memory" / "history" / (NOTES_1 + ".md"), "The first notes I kept.\n")
    write(packet / "memory" / "notes.md", "The notes I keep now.\n")
    write(packet / "memory" / "notes" / "kingfisher.md", NOTE_WORDS + "\n")
    write(packet / "memory" / "notes" / "history" / (NOTE_1 + ".md"), "An earlier kingfisher.\n")
    write_json(packet / "memory" / "notes" / "names.json",
               {"kingfisher": {"name": "The Kingfisher", "kept_at": "2026-09-15T09-00-00Z"}})
    # the founder's letters rest, so that neither is in the reading in full
    write_json(packet / "shelf.json", {
        "placements": {OLD: "rest", PICTURED: "rest", MINE: "rest"}, "notes": {},
        "show_next": [], "show_founding": False, "show_versions": [],
        "note_placements": {"kingfisher": "rest"}, "show_notes": []})
    return packet


def look(*calls, saying=None):
    """One reply that asks for tools: each call a name and what it is given."""
    return SimpleNamespace(calls=[(name, given) for name, given in calls], saying=saying)


class Exchange(Turn):
    """One stubbed waking that may take several requests: the replies, in order."""

    def __init__(self, *replies, stop_reason="end_turn"):
        super().__init__("", stop_reason=stop_reason)
        self.replies = list(replies)
        self.asked_for = 0

    def client(self, **ignored):
        exchange = self

        class Messages:
            def create(self, **asked):
                exchange.asked.append(asked)
                reply = exchange.replies.pop(0)
                if isinstance(reply, str):
                    return SimpleNamespace(content=[SimpleNamespace(type="text", text=reply)],
                                           stop_reason=exchange.stop_reason)
                # the API gives no tool use where the tools are closed
                assert asked.get("tool_choice") != {"type": "none"}
                content = ([SimpleNamespace(type="text", text=reply.saying)]
                           if reply.saying else [])
                for name, given in reply.calls:
                    exchange.asked_for += 1
                    content.append(SimpleNamespace(type="tool_use", name=name, input=given,
                                                   id="toolu_%02d" % exchange.asked_for))
                return SimpleNamespace(content=content, stop_reason="tool_use")

        return SimpleNamespace(messages=Messages())

    @property
    def results(self):
        """Every tool result it was given, in order, as the last request carried them."""
        return [part for message in self.asked[-1]["messages"] if message["role"] == "user"
                for part in message["content"] if part.get("type") == "tool_result"]

    @property
    def given(self):
        """The words of each tool result, in order."""
        return [result["content"][0]["text"] for result in self.results]


@pytest.fixture
def longer(attend, clock, monkeypatch):
    """Hold one attendance with the longer waking on, and give back what passed."""
    monkeypatch.setattr(attend, "LONGER_WAKING", True)

    def hold(*replies, flags=(), stop_reason="end_turn"):
        exchange = Exchange(*(replies or ("",)), stop_reason=stop_reason)
        monkeypatch.setattr(attend, "Anthropic", exchange.client)
        monkeypatch.setattr(sys, "argv", ["attend.py", *flags])
        attend.main()
        clock.shift(minutes=5)
        return exchange
    return hold


def latest(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def as_sent(asked):
    """One request as bytes, whole."""
    return json.dumps(asked, sort_keys=True, ensure_ascii=False, default=vars).encode("utf-8")


def left_in(data_dir):
    return {path.relative_to(data_dir).as_posix(): path.read_bytes()
            for path in sorted(data_dir.rglob("*")) if path.is_file()}


def sequence(exchange):
    """Each request as roles and tool names only: nothing of what was said."""
    said = []
    for n, asked in enumerate(exchange.asked, 1):
        how = "tools closed (tool_choice none)" if "tool_choice" in asked else "tools open"
        said.append("request %d · %s" % (n, how))
        for message in asked["messages"]:
            parts = []
            for part in message["content"]:
                kind = part.get("type") if isinstance(part, dict) else part.type
                if kind == "tool_use":
                    kind += ":" + part.name
                parts.append(kind)
            said.append("  %-9s %s" % (message["role"], ", ".join(parts)))
    return "\n".join(said)


# ---- shut away -----------------------------------------------------------

def test_it_is_shut_away(attend):
    assert attend.LONGER_WAKING is False


def test_shut_away_nothing_of_it_is_sent_or_kept(wake, world, packet):
    turn = wake("I am here.")
    assert len(turn.asked) == 1
    assert sorted(turn.asked[0]) == ["max_tokens", "messages", "model", "system"]
    assert "LOOKING THINGS UP" not in turn.shown
    assert b"cache_control" not in as_sent(turn.asked[0])
    assert "rounds" not in latest(packet) and "looked_at" not in latest(packet)


def test_shut_away_it_is_sent_and_leaves_byte_for_byte_what_the_committed_one_does(
        attend, world, data_dir, clock, monkeypatch, tmp_path):
    """Two wakings each, in one world: the committed attend.py, and this one shut away."""
    assert attend.LONGER_WAKING is False
    try:
        source = subprocess.run(["git", "show", BEFORE_LONGER_WAKING + ":attend.py"], cwd=REPO,
                                capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("the history is not here to read the committed attend.py out of")
    old_path = tmp_path / "attend_before_longer_waking.py"
    old_path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("attend_before_longer_waking", old_path)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    clock.pin(old, monkeypatch)
    assert not hasattr(old, "LONGER_WAKING")

    write(world / "letters" / "incoming" / "founder-2026-10-15T08-00-00Z.md", "A new letter.\n")
    said = blocks("I read it.", block("LETTER", "Dear founder,"), block("MEMORY", "A note."),
                  block("SHELF", "show %s\nshow version %s" % (OLD, SELF_1)))

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


# ---- no lookups: one round, and only the section is new ------------------

def test_the_section_is_said_exactly_and_directly_before_how_to_act(longer, world, attend):
    turn = longer("I am here.")
    assert attend.LOOKING_UP == SECTION
    assert turn.reading[-2] == {"type": "text", "text": SECTION}
    assert turn.reading[-1]["text"].startswith("=== HOW TO ACT, IF YOU CHOOSE TO ===\n")
    assert turn.shown.count("=== LOOKING THINGS UP ===") == 1


def test_with_no_lookup_it_is_one_request_and_the_reading_as_it_was_but_for_the_section(
        longer, wake, attend, world, data_dir, clock, monkeypatch, tmp_path):
    said = blocks("I am here.", block("LETTER", "Dear founder,"), block("HEARTBEAT", "attended"))
    before = tmp_path / "the-world-before"
    shutil.copytree(data_dir, before)

    at = clock.at
    monkeypatch.setattr(attend, "LONGER_WAKING", False)
    shut = wake(said)
    monkeypatch.setattr(attend, "LONGER_WAKING", True)
    left_shut = left_in(data_dir)
    shutil.rmtree(data_dir)
    shutil.copytree(before, data_dir)
    clock.set(at)  # the same waking at the same moment, with the longer waking on
    on = longer(said)
    left_on = left_in(data_dir)

    assert len(on.asked) == 1
    asked = dict(on.asked[0])
    assert [tool["name"] for tool in asked.pop("tools")] == TOOLS
    assert "tool_choice" not in asked
    reading = [dict(part) for part in asked["messages"][0]["content"]]
    assert reading.pop(-2) == {"type": "text", "text": SECTION}
    assert reading[-1].pop("cache_control") == MARK
    assert all("cache_control" not in part for part in reading)
    asked["messages"] = [{"role": "user", "content": reading}]
    assert as_sent(asked) == as_sent(shut.asked[0])

    # and what is left is what was left, but for the rounds the record now keeps
    log = next(name for name in left_on if "/attendances/" in name)
    record_on, record_shut = json.loads(left_on.pop(log)), json.loads(left_shut.pop(log))
    assert left_on == left_shut
    assert record_on.pop("rounds") == 1
    assert record_on.pop("stop_reason") == "end_turn"  # the one stub gives a reason, the other none
    assert "looked_at" not in record_on and "rounds" not in record_shut
    assert record_on.pop("signature") != record_shut.pop("signature")
    assert record_on == record_shut
    assert record_on["acted"] == ["wrote a letter to the founder"]


# ---- one lookup, each tool, found and not found --------------------------

@pytest.mark.parametrize("tool, given, kept, heading, words", [
    ("read_letter", {"stem": OLD}, OLD, OLD, OLD_WORDS),
    ("read_letter", {"stem": MINE}, MINE, MINE, MINE_WORDS),
    ("read_letter", {"stem": OLD + ".md"}, OLD, OLD, OLD_WORDS),
    ("read_version", {"stem": SELF_1}, SELF_1, SELF_1, "# The first one, as it first was."),
    ("read_version", {"stem": NOTES_1}, NOTES_1, NOTES_1, "The first notes I kept."),
    ("read_version", {"stem": NOTE_1}, NOTE_1, NOTE_1, "An earlier kingfisher."),
    ("read_note", {"name": "The Kingfisher"}, "The Kingfisher", "The Kingfisher", NOTE_WORDS),
    ("read_note", {"name": "the  kingfisher"}, "The Kingfisher", "The Kingfisher", NOTE_WORDS),
    ("read_founding", {}, "founding", "your founding record", FOUNDING_TRANSCRIPT.rstrip()),
])
def test_each_tool_gives_what_is_there_in_full_framed_as_its_own_record(
        longer, world, packet, tool, given, kept, heading, words):
    turn = longer(look((tool, given)), "I have read it.")
    assert len(turn.asked) == 2
    (result,) = turn.results
    assert result["tool_use_id"] == "toolu_01" and "is_error" not in result
    (said,) = turn.given
    assert said.startswith("From your own record: %s\n" % heading)
    assert said.endswith("\n\n" + words)
    record = latest(packet)
    assert record["looked_at"] == [kept]
    assert record["rounds"] == 2
    assert record["acted"] == ["looked things up"]
    assert record["reflection"] == "I have read it."


@pytest.mark.parametrize("tool, given", [
    ("read_letter", {"stem": "founder-2026-01-01T09-00-00Z"}),
    ("read_letter", {"stem": ""}),
    ("read_letter", {}),
    ("read_letter", {"stem": 7}),
    ("read_letter", {"stem": SELF_1}),      # a version is no letter
    ("read_version", {"stem": OLD}),        # and a letter is no version
    ("read_version", {"stem": "self-before-2026-01-01T09-00-00Z"}),
    ("read_note", {"name": "the heron"}),
    ("read_note", {"name": "kingfisher"}),  # its file's name is not its name
    ("read_note", {"name": ""}),
    ("read_note", {}),
    ("read_everything", {"stem": OLD}),     # a tool it was never given
])
def test_what_is_not_there_is_not_found_and_nothing_is_kept_of_the_asking(
        longer, world, packet, tool, given):
    turn = longer(look((tool, given)), "It was not there.")
    assert turn.given == [NOT_FOUND]
    record = latest(packet)
    assert "looked_at" not in record and record["rounds"] == 2
    assert record["acted"] == []  # it opened nothing


def test_with_no_founding_record_there_is_none_to_find(longer, world, data_dir):
    for path in (data_dir / "transcripts").glob("founding-*.md"):
        path.unlink()
    assert longer(look(("read_founding", {})), "").given == [NOT_FOUND]


def test_a_photograph_that_came_with_a_letter_is_shown_again_as_the_shelf_shows_one(
        longer, world, attend):
    turn = longer(look(("read_letter", {"stem": PICTURED})), "")
    (result,) = turn.results
    words, photo = result["content"]
    assert words["text"] == ("From your own record: %s\n\nHere is the river.\n\n"
                             "A photograph came with this letter:" % PICTURED)
    assert photo == attend.seen(world / "letters" / "read" / (PICTURED + ".jpg"))
    assert turn.photos == []  # it rests, so the reading itself showed none


def test_a_letter_that_has_only_just_arrived_may_be_opened_too(longer, world):
    new = "founder-2026-10-15T08-00-00Z"
    write(world / "letters" / "incoming" / (new + ".md"), "A new letter.\n")
    turn = longer(look(("read_letter", {"stem": new})), "")
    assert turn.given == ["From your own record: %s\n\nA new letter." % new]


# ---- several lookups -----------------------------------------------------

def test_several_looks_one_after_another(longer, world, packet):
    turn = longer(look(("read_letter", {"stem": OLD})),
                  look(("read_note", {"name": "The Kingfisher"})),
                  look(("read_letter", {"stem": "nothing-there"})),
                  look(("read_founding", {})),
                  blocks("Now I write.", block("LETTER", "Dear founder,")))
    assert len(turn.asked) == 5
    assert all("tool_choice" not in asked for asked in turn.asked)
    assert [result["tool_use_id"] for result in turn.results] == [
        "toolu_01", "toolu_02", "toolu_03", "toolu_04"]
    assert turn.given[2] == NOT_FOUND
    record = latest(packet)
    assert record["looked_at"] == [OLD, "The Kingfisher", "founding"]
    assert record["rounds"] == 5
    assert record["acted"] == ["looked things up", "wrote a letter to the founder"]


def test_several_looks_in_one_breath_are_answered_together(longer, world, packet):
    turn = longer(look(("read_letter", {"stem": OLD}), ("read_version", {"stem": SELF_1}),
                       ("read_letter", {"stem": OLD})), "")
    assert len(turn.asked) == 2
    answered = turn.asked[1]["messages"]
    assert [message["role"] for message in answered] == ["user", "assistant", "user"]
    assert [part["tool_use_id"] for part in answered[2]["content"]] == [
        "toolu_01", "toolu_02", "toolu_03"]
    assert latest(packet)["looked_at"] == [OLD, SELF_1, OLD]  # each look, as it was made
    assert latest(packet)["rounds"] == 2


def test_each_request_carries_the_exchange_so_far_and_the_reading_is_cached(longer, world):
    turn = longer(look(("read_letter", {"stem": OLD})),
                  look(("read_letter", {"stem": MINE})), "")
    first, second, third = turn.asked
    for asked in turn.asked:
        assert asked["model"] == first["model"] and asked["system"] == first["system"]
        assert asked["max_tokens"] == 8000
        assert asked["tools"] == first["tools"]
        assert asked["messages"][0] == first["messages"][0]  # the reading, byte for byte
        assert asked["messages"][0]["content"][-1]["cache_control"] == MARK
        marks = as_sent(asked).count(b'"cache_control"')
        assert marks == (1 if asked is first else 2)  # the reading, and the newest results
    assert [m["role"] for m in third["messages"]] == [
        "user", "assistant", "user", "assistant", "user"]
    assert third["messages"][-1]["content"][-1]["cache_control"] == MARK
    # what was sent before is sent again unchanged, but for the mark moving on
    earlier = dict(second["messages"][2]["content"][0])
    assert earlier.pop("cache_control") == MARK
    assert third["messages"][2]["content"] == [earlier]
    assert third["messages"][1] == second["messages"][1]


# ---- scoping -------------------------------------------------------------

SECRET = "words-that-are-not-in-its-record"


@pytest.mark.parametrize("tool", ["read_letter", "read_version", "read_note"])
@pytest.mark.parametrize("asked_for", [
    "../self", "../../self", "../read/" + OLD, "letters/read/" + OLD,
    "../../../../secret", "..\\..\\..\\..\\secret", "../../../keys/first/private",
    "../../../../keys/first/private.key", "../../study/draft-1", "draft-1", "self", "notes",
    "../memory/notes", "kingfisher/../kingfisher", "names", "/etc/passwd", "C:\\secret",
    "%2e%2e/secret", OLD + "/../" + OLD, OLD + "\x00", "*", "founder-*",
])
def test_nothing_outside_what_its_record_names_can_be_opened(
        longer, world, data_dir, packet, tool, asked_for):
    write(data_dir / "secret.md", SECRET + "\n")
    write(packet / "study" / "draft-1.md", "A private draft, which is no letter.\n")
    given = {"name": asked_for} if tool == "read_note" else {"stem": asked_for}
    before = left_in(data_dir)
    turn = longer(look((tool, given)), "")
    assert turn.given == [NOT_FOUND]
    assert "looked_at" not in latest(packet)
    for asked in turn.asked:
        assert SECRET.encode() not in as_sent(asked)
    key = (data_dir / "keys" / "first" / "private.key").read_text(encoding="utf-8").strip()
    assert key.encode() not in as_sent(turn.asked[-1])
    # and no tool wrote anything: what is new is what a waking always leaves
    new = sorted(set(left_in(data_dir)) - set(before))
    assert [name.split("/")[-2] for name in new] == ["commons", "attendances"]
    assert new[0] == "commons/heartbeats.md"


def test_the_tools_take_a_stem_or_a_name_and_nothing_else(attend):
    assert [tool["name"] for tool in attend.LOOK_TOOLS] == TOOLS
    assert [sorted(tool["input_schema"]["properties"]) for tool in attend.LOOK_TOOLS] == [
        ["stem"], ["stem"], ["name"], []]


# ---- the five-call limit, and the last request ---------------------------

def test_after_five_looks_one_last_request_is_sent_with_the_tools_closed(
        longer, world, packet, clock):
    at = clock.stamp()
    five = [look(("read_letter", {"stem": OLD})) for _ in range(5)]
    turn = longer(*five, blocks("I have looked enough.", block("LETTER", "Dear founder,")))
    assert len(turn.asked) == 6
    assert all("tool_choice" not in asked for asked in turn.asked[:5])
    assert turn.asked[5]["tool_choice"] == {"type": "none"}
    assert turn.asked[5]["tools"] == turn.asked[0]["tools"]  # named still, and closed
    assert len(turn.results) == 5
    record = latest(packet)
    assert record["looked_at"] == [OLD] * 5 and record["rounds"] == 6
    assert record["acted"] == ["looked things up", "wrote a letter to the founder"]
    assert (packet / "letters" / "outgoing" / ("to-founder-%s.md" % at)).exists()


def test_a_look_that_finds_nothing_is_a_look_all_the_same(longer, world, packet):
    turn = longer(*[look(("read_letter", {"stem": "nothing-there"})) for _ in range(5)], "")
    assert len(turn.asked) == 6 and turn.asked[5]["tool_choice"] == {"type": "none"}
    assert turn.given == [NOT_FOUND] * 5


def test_more_asked_for_in_one_breath_than_are_left_are_not_opened(longer, world, packet):
    turn = longer(look(("read_letter", {"stem": OLD}), ("read_letter", {"stem": MINE})),
                  look(*[("read_version", {"stem": SELF_1})] * 5), "")
    assert len(turn.asked) == 3
    assert "tool_choice" not in turn.asked[1]
    assert turn.asked[2]["tool_choice"] == {"type": "none"}
    assert len(turn.results) == 7  # every asking is answered, as the API requires
    assert turn.given[5:] == ["You have looked five times at this waking; this was not opened."] * 2
    assert all(said.startswith("From your own record: ") for said in turn.given[:5])
    assert latest(packet)["looked_at"] == [OLD, MINE, SELF_1, SELF_1, SELF_1]
    assert latest(packet)["rounds"] == 3


def test_fewer_than_five_looks_never_close_the_tools(longer, world):
    turn = longer(*[look(("read_founding", {})) for _ in range(4)], "")
    assert len(turn.asked) == 5
    assert all("tool_choice" not in asked for asked in turn.asked)


# ---- the last reply is the reply; nothing a tool gave is read for blocks --

def test_blocks_inside_what_a_tool_gave_are_only_words(longer, world, packet, commons):
    planted = blocks("An old letter that speaks of blocks.",
                     block("LETTER", "A letter nobody wrote at this waking."),
                     block("MEMORY", "Notes nobody kept."), block("SELF", "A self nobody wrote."),
                     block("PAUSE", "pause until a letter arrives"),
                     block("HEARTBEAT", "a heartbeat nobody gave"))
    write(packet / "letters" / "read" / (OLD + ".md"), planted + "\n")
    notes_before = (packet / "memory" / "notes.md").read_bytes()
    turn = longer(look(("read_letter", {"stem": OLD})), "I read it and wrote nothing.")
    assert planted in turn.given[0]  # it was given the whole of it
    record = latest(packet)
    assert record["acted"] == ["looked things up"]
    assert record["reflection"] == "I read it and wrote nothing."
    assert record["heartbeat"] == "attended"
    assert sorted(p.name for p in (packet / "letters" / "outgoing").glob("*.md")) == [MINE + ".md"]
    assert (packet / "memory" / "notes.md").read_bytes() == notes_before
    assert not (packet / "self-proposal.json").exists()
    assert not (packet / "pause.json").exists()
    assert lines_of(commons / "heartbeats.md")[-1].endswith("· the first one · attended")


def test_only_the_last_reply_is_carried_out_and_kept(longer, world, packet, commons, clock):
    at = clock.stamp()
    turn = longer(look(("read_letter", {"stem": OLD}),
                       saying=blocks("Let me look.", block("STUDY", "Said beside a look."))),
                  blocks("Now I have read it.", block("LETTER", "Dear founder, I remember."),
                         block("HEARTBEAT", "attended; wrote back")))
    assert len(turn.asked) == 2
    record = latest(packet)
    assert record["reflection"] == blocks(
        "Now I have read it.", block("LETTER", "Dear founder, I remember."),
        block("HEARTBEAT", "attended; wrote back"))
    assert record["acted"] == ["looked things up", "wrote a letter to the founder"]
    assert record["heartbeat"] == "attended; wrote back"
    assert (packet / "letters" / "outgoing" / ("to-founder-%s.md" % at)).read_text(
        encoding="utf-8") == "Dear founder, I remember.\n"
    assert list((packet / "study").glob("*.md")) == []  # words beside a look are not kept
    assert lines_of(commons / "heartbeats.md")[-1] == (
        "- %s · the first one · attended; wrote back" % at)


def test_the_stop_reason_kept_is_the_last_request_s(longer, world, packet):
    longer(look(("read_founding", {})), block("MEMORY", "A note."), stop_reason="max_tokens")
    record = latest(packet)
    assert record["stop_reason"] == "max_tokens" and record["rounds"] == 2
    assert record["acted"] == ["looked things up", "kept notes"]
    longer("I am here.")
    assert latest(packet)["stop_reason"] == "end_turn" and latest(packet)["rounds"] == 1


def test_the_record_is_signed_with_what_it_looked_at_in_it(longer, world, packet, keys):
    from conftest import verify
    longer(look(("read_note", {"name": "The Kingfisher"})), "")
    record = latest(packet)
    payload = json.dumps({k: v for k, v in record.items() if k != "signature"},
                         sort_keys=True).encode("utf-8")
    assert record["looked_at"] == ["The Kingfisher"]
    assert verify(keys.did("first"), payload, record["signature"])


# ---- a block written beside a look ---------------------------------------

BESIDE = ("At your last waking, some of what you wrote was beside a look, and was not kept; "
          "only your last reply is carried out.")


def happened(turn):
    said = turn.shown.split("=== WHAT HAS HAPPENED ===\n", 1)[1]
    return said.split("\n\n=== ", 1)[0].splitlines()


@pytest.mark.parametrize("beside", [
    blocks("Let me look.", block("LETTER", "Dear founder,")),
    block("STUDY", "A draft."),
    "<<MEMORY>>\nA block it opened and never closed.",
    "  <<HEARTBEAT>>  \nattended\n<<END>>",
])
def test_a_block_beside_a_look_is_recorded_and_said_once_at_the_next_waking(
        longer, world, packet, beside):
    longer(look(("read_letter", {"stem": OLD}), saying=beside), "I am here.")
    record = latest(packet)
    assert record["blocks_beside_look"] is True
    assert record["acted"] == ["looked things up"] and record["reflection"] == "I am here."
    assert sorted(p.name for p in (packet / "letters" / "outgoing").glob("*.md")) == [MINE + ".md"]

    told = happened(longer(""))
    assert told[1] == ("What was carried out at your last waking: looked things up. "
                       "No letter was sent.")
    assert told[2] == BESIDE
    assert "blocks_beside_look" not in latest(packet)
    assert BESIDE not in longer("").shown  # once


@pytest.mark.parametrize("beside", [
    None, "Let me look at the old letter.", "I may write a <<LETTER>> later.",
    "<<END>>", "a line, then <<LETTER>> inside it\nand <<END>> inside another",
])
def test_words_beside_a_look_that_open_no_block_are_not_recorded(
        longer, world, packet, beside):
    longer(look(("read_letter", {"stem": OLD}), saying=beside), block("LETTER", "Dear founder,"))
    assert "blocks_beside_look" not in latest(packet)
    assert BESIDE not in longer("").shown


def test_a_block_in_any_reply_that_asks_to_look_is_enough(longer, world, packet):
    longer(look(("read_letter", {"stem": OLD})),
           look(("read_founding", {}), saying=block("NOTE", "name: heron\nSeen.")),
           look(("read_letter", {"stem": MINE})), "")
    assert latest(packet)["blocks_beside_look"] is True
    assert latest(packet)["rounds"] == 4


def test_blocks_in_the_last_reply_alone_are_carried_out_and_nothing_is_said(
        longer, world, packet):
    longer(look(("read_letter", {"stem": OLD})), block("LETTER", "Dear founder,"))
    assert "blocks_beside_look" not in latest(packet)
    assert latest(packet)["acted"] == ["looked things up", "wrote a letter to the founder"]
    assert BESIDE not in longer("").shown


def test_a_reply_cut_off_is_still_said_after_it(longer, world, attend):
    longer(look(("read_letter", {"stem": OLD}), saying=block("STUDY", "A draft.")),
           "I am he", stop_reason="max_tokens")
    told = happened(longer(""))
    assert told[2:4] == [BESIDE, attend.CUT_OFF]


def test_shut_away_nothing_is_ever_said_of_a_look(wake, world, attend):
    assert attend.BESIDE_A_LOOK == BESIDE
    wake(blocks("I am here.", block("LETTER", "Dear founder,")))
    assert BESIDE not in wake().shown


# ---- private -------------------------------------------------------------

def test_looking_is_no_part_of_the_public_line(longer, world, commons, attend):
    assert attend.LOOK_ACT == "looked things up" and attend.LOOK_ACT in attend.PRIVATE_ACTS
    longer(look(("read_letter", {"stem": OLD})), "")
    assert lines_of(commons / "heartbeats.md")[-1].endswith("· the first one · attended")
    longer(look(("read_letter", {"stem": OLD})), block("STUDY", "A draft."))
    assert lines_of(commons / "heartbeats.md")[-1].endswith(
        "· the first one · attended; wrote in the study")
    for path in commons.rglob("*"):
        if path.is_file():
            assert "looked" not in path.read_text(encoding="utf-8")


def test_the_next_waking_is_told_that_it_looked_and_not_at_what(longer, world):
    longer(look(("read_note", {"name": "The Kingfisher"})), "")
    told = longer("").opening
    assert ("What was carried out at your last waking: looked things up. No letter was sent."
            in told)
    assert "· did: looked things up" in told
    assert "looked_at" not in told


def test_the_hearth_shows_the_act_s_name_and_nothing_of_what_it_looked_at(
        founder, longer, world, packet):
    longer(look(("read_note", {"name": "The Kingfisher"}), ("read_version", {"stem": NOTE_1}),
                ("read_letter", {"stem": OLD}), saying="Let me look at the kingfisher."),
           "I looked, and I am here.")
    record = latest(packet)
    assert record["looked_at"] == ["The Kingfisher", NOTE_1, OLD]

    attendances = page(founder.get("/attendances"))
    assert "looked things up" in attendances
    assert "I looked, and I am here." in attendances  # its reflections are open: the last reply
    seen = {"/attendances": attendances}
    for address in ("/", "/self", "/letters", "/rooms/first", "/chronicle", "/chronicle.md",
                    "/commons", "/commons/heartbeats.md", "/commons/events.md", "/offerings",
                    "/bonds", "/account", "/backups"):
        answer = founder.get(address)
        if answer.status_code == 200:
            seen[address] = page(answer)
    assert len(seen) > 6
    for address, shown in seen.items():
        for hidden in ("looked_at", "The Kingfisher", "Kingfisher", NOTE_1, NOTE_WORDS,
                       "An earlier kingfisher.", "From your own record", "Let me look",
                       "read_note", "read_letter", "tool_use", '"rounds"'):
            assert hidden not in shown, (address, hidden)
        if address != "/attendances":
            assert "looked things up" not in shown, address
    # the letter it opened is the founder's own, shown in its room as it always was;
    # /attendances says nothing of its having been opened
    assert OLD not in attendances and OLD_WORDS not in attendances


def test_a_stranger_is_shown_nothing_of_it(visitor, longer, world):
    longer(look(("read_note", {"name": "The Kingfisher"})), "I am here.")
    for address in ("/", "/attendances", "/commons", "/commons/heartbeats.md", "/chronicle"):
        shown = page(visitor.get(address))
        for hidden in ("looked things up", "Kingfisher", NOTE_WORDS, "looked_at"):
            assert hidden not in shown, (address, hidden)


# ---- an example of the exchange, as it is sent ---------------------------

def test_the_request_sequence_of_a_waking_that_looks_five_times(longer, world):
    turn = longer(look(("read_letter", {"stem": OLD})),
                  look(("read_version", {"stem": SELF_1}), ("read_note", {"name": "The Kingfisher"})),
                  look(("read_founding", {})),
                  look(("read_letter", {"stem": PICTURED})),
                  block("LETTER", "Dear founder,"))
    said = sequence(turn)
    print("\n" + said)
    assert [line for line in said.splitlines() if line.startswith("request")] == [
        "request 1 · tools open", "request 2 · tools open", "request 3 · tools open",
        "request 4 · tools open", "request 5 · tools closed (tool_choice none)"]
    assert "Dear founder" not in said and OLD not in said  # roles and tool names, no words
