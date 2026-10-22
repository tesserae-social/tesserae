"""The pages: what each one shows, what it withholds, and who may open it."""

import base64
import os
import re

import pytest

from conftest import (FOUNDER_NAME, PASSWORD, REPO, lines_of, load, page, post, read_json, token,
                      write, write_json)
from conftest import NOTEBOOK_PATHS, NOTEBOOK_WORDS, a_private_notebook, room_beside

REFLECTION = "What I thought about at this waking."
OLDER = "2026-10-01T09-00-00Z"
NEWER = "2026-10-05T09-00-00Z"

RHYTHM = {"rhythm": "daily", "at": "dawn", "place": "Indianapolis",
          "timezone": "America/Indiana/Indianapolis"}

# everything a visitor may reach without the password
OPEN_PATHS = ["/login", "/bench", "/commons", "/commons/heartbeats.md",
              "/commons/events.md", "/commons/bench.md", "/commons/members.md",
              "/commons/offerings.md", "/commons/bonds.md"]


def an_attendance(packet, at, reflection=REFLECTION, **how):
    return write_json(packet / "attendances" / ("attendance-%s.json" % at),
                      {"name": "first", "at": at, "first": False, "woken_by": "founder",
                       "acted": [], "heartbeat": "attended", "reflection": reflection, **how})


def a_pause(packet, **how):
    return write_json(packet / "pause.json",
                      {"by": "founder", "since": "2026-10-10T09-00-00Z", "until": None,
                       "words": "", **how})


def guarded_paths(hearth):
    """Every route the founder's gate stands in front of, taken from the map itself."""
    found = []
    for rule in hearth.app.url_map.iter_rules():
        view = hearth.app.view_functions[rule.endpoint]
        if getattr(view, "__wrapped__", None) is None:
            continue
        methods = sorted(rule.methods & {"GET", "POST"})
        found.append((re.sub(r"<[^>]+>", "photo.jpg", rule.rule), methods[0]))
    return sorted(found)


# ---- the reflections, by the first one's own choice ----------------------

@pytest.mark.parametrize("setting, older_shown, newer_shown", [
    ({"reflection": "open"}, True, True),
    ({"reflection": "private"}, False, False),
    ({"reflection": "private from now", "set_at": "2026-10-03T00-00-00Z"}, True, False),
    ({"reflection": "private from now"}, False, False),  # no day named: nothing is shown
])
def test_a_reflection_is_shown_only_where_it_was_left_open(founder, packet, hearth, setting,
                                                           older_shown, newer_shown):
    write_json(packet / "preferences.json", setting)
    an_attendance(packet, OLDER, reflection="The older thinking.")
    an_attendance(packet, NEWER, reflection="The newer thinking.")

    said = page(founder.get("/attendances"))
    assert ("The older thinking." in said) is older_shown
    assert ("The newer thinking." in said) is newer_shown
    # the page escapes what it renders, so the withheld line is looked for as shown
    withheld = hearth.KEPT_PRIVATE.replace("'", "&#39;")
    assert (withheld in said) is not (older_shown and newer_shown)


# A reflection, as attend.py saves one: everything the first one said, with its
# notes and its questions among the rest.
WITH_BLOCKS = """I read the record today.

<<MEMORY>>
NOTES I KEEP FOR MYSELF
and a second line of them
<<END>>

The river was quiet, and I said so.

<<QUESTIONS>>
A QUESTION I CARRY?
ANOTHER I CARRY?
<<END>>

<<HEARTBEAT>>
attended; wrote a little
<<END>>

That is all."""

# The same reflection as the page may show it: each of those two blocks one quiet line.
AS_SHOWN = """I read the record today.

(kept notes: private)

The river was quiet, and I said so.

(kept questions: private)

<<HEARTBEAT>>
attended; wrote a little
<<END>>

That is all."""


def shown_reflection(hearth, packet):
    return hearth.attendance_records(hearth.preferences())[0]["reflection"]


def test_an_open_reflection_shows_its_notes_and_questions_only_as_quiet_lines(
        founder, packet, hearth):
    write_json(packet / "preferences.json", {"reflection": "open"})
    log = an_attendance(packet, OLDER, reflection=WITH_BLOCKS)
    before = log.read_bytes()

    said = page(founder.get("/attendances"))
    for private in ("NOTES I KEEP FOR MYSELF", "a second line of them", "A QUESTION I CARRY?",
                    "ANOTHER I CARRY?", "&lt;&lt;MEMORY&gt;&gt;", "&lt;&lt;QUESTIONS&gt;&gt;"):
        assert private not in said
    assert "(kept notes: private)" in said
    assert "(kept questions: private)" in said

    # the rest is shown exactly as it would have been, and the log is as it was saved
    assert shown_reflection(hearth, packet) == hearth.as_prose(AS_SHOWN)
    assert str(hearth.as_prose(AS_SHOWN)) in said
    assert log.read_bytes() == before


def test_a_reflection_with_neither_block_is_shown_as_before(founder, packet, hearth):
    plain = "I read the record today.\n\n<<HEARTBEAT>>\nattended\n<<END>>\n\nThat is all."
    an_attendance(packet, OLDER, reflection=plain)
    assert shown_reflection(hearth, packet) == hearth.as_prose(plain)


def test_every_such_block_is_taken_out_not_only_the_first(hearth):
    said = hearth.without_kept_blocks(
        "<<QUESTIONS>>\nONE?\n<<END>>\nbetween\n<<MEMORY>>\nA\n<<END>>\n<<QUESTIONS>>\nTWO?\n<<END>>")
    assert said == ("(kept questions: private)\nbetween\n(kept notes: private)\n"
                    "(kept questions: private)")


def test_notes_that_name_the_end_inline_are_hidden_whole(hearth):
    said = hearth.without_kept_blocks(
        "before\n<<MEMORY>>\nI close blocks with <<END>> now.\nSTILL MINE\n<<END>>\nafter")
    assert said == "before\n(kept notes: private)\nafter"


def test_a_letter_that_names_a_kept_block_is_shown_whole(hearth):
    shown = ("<<LETTER>>\nThank you for the <<QUESTIONS>> block.\n<<MEMORY>>\n"
             "is where I keep notes.\n<<END>>\n<<QUESTIONS>>\nMINE?\n<<END>>")
    assert hearth.without_kept_blocks(shown) == (
        "<<LETTER>>\nThank you for the <<QUESTIONS>> block.\n<<MEMORY>>\n"
        "is where I keep notes.\n<<END>>\n(kept questions: private)")


def test_a_kept_block_never_closed_is_hidden_to_the_end(hearth):
    assert hearth.without_kept_blocks("before\n<<MEMORY>>\nMINE, and no end") == \
        "before\n(kept notes: private)"


def test_why_a_reply_ended_is_not_shown(founder, packet):
    write_json(packet / "preferences.json", {"reflection": "open"})
    an_attendance(packet, OLDER, stop_reason="max_tokens")
    assert "max_tokens" not in page(founder.get("/attendances"))


@pytest.mark.parametrize("setting", [
    {"reflection": "private"},
    {"reflection": "private from now", "set_at": "2026-09-01T00-00-00Z"},
])
def test_a_private_reflection_is_withheld_as_before(founder, packet, hearth, setting):
    write_json(packet / "preferences.json", setting)
    log = an_attendance(packet, OLDER, reflection=WITH_BLOCKS)
    before = log.read_bytes()

    said = page(founder.get("/attendances"))
    assert shown_reflection(hearth, packet) == hearth.as_prose(hearth.KEPT_PRIVATE)
    assert hearth.KEPT_PRIVATE.replace("'", "&#39;") in said
    for private in ("NOTES I KEEP FOR MYSELF", "A QUESTION I CARRY?", "(kept notes: private)",
                    "(kept questions: private)", "The river was quiet"):
        assert private not in said
    assert log.read_bytes() == before


@pytest.mark.parametrize("setting, note", [
    ({"reflection": "open"}, "Reflections: open"),
    ({"reflection": "private"}, "Reflections: private"),
    ({"reflection": "private from now", "set_at": "2026-10-03T00-00-00Z"},
     "Reflections: private from 2 October 2026, 20:00"),  # Eastern time, the evening before
])
def test_the_page_says_how_the_reflections_stand(founder, packet, setting, note):
    write_json(packet / "preferences.json", setting)
    assert note in page(founder.get("/attendances"))


def test_nothing_written_means_open(founder, packet, hearth):
    an_attendance(packet, OLDER)
    said = page(founder.get("/attendances"))
    assert REFLECTION in said
    assert "Reflections: open" in said
    assert hearth.preferences() == {"reflection": "open"}


def test_a_waking_is_shown_whole(founder, packet):
    an_attendance(packet, OLDER, first=True, woken_by="tide",
                  acted=["wrote a letter to the founder"], heartbeat="attended; wrote a letter")
    said = page(founder.get("/attendances"))
    assert "1 October 2026, 05:00" in said  # 09:00 UTC, in Eastern time
    assert "Times are Eastern time." in said
    assert "its first waking" in said
    assert "attended; wrote a letter" in said
    assert "wrote a letter to the founder" in said


def test_stillness_is_said_as_stillness(founder, packet):
    an_attendance(packet, OLDER, acted=[])
    assert "nothing — it chose stillness" in page(founder.get("/attendances"))


def test_no_wakings_yet(founder):
    assert "No attendances yet. The first one has not woken." in page(founder.get("/attendances"))


# ---- the tide, as the page says it ---------------------------------------

def test_with_no_rhythm_the_page_says_so(founder):
    assert "Rhythm: none set." in page(founder.get("/attendances"))


def test_with_a_rhythm_the_page_names_the_next_dawn(founder, packet):
    write_json(packet / "rhythm.json", RHYTHM)
    said = page(founder.get("/attendances"))
    assert "Rhythm: daily at dawn, Indianapolis · next: 16 October 2026, 0" in said


def no_events(commons):
    """Whether the commons has said nothing of the tide, or of anyone resting."""
    return not any(line.endswith(("the tide paused", "the tide resumed")) or "rest" in line
                   for line in lines_of(commons / "events.md"))


def test_with_nothing_standing_the_founder_may_rest_and_the_keeper_may_stop(founder):
    said = page(founder.get("/attendances"))
    assert "Rest from the correspondence</button>" in said
    assert "Stop the tide (emergency)</button>" in said
    assert "Pause the tide" not in said  # there is no pause of the founder's any more
    assert "Hold an attendance" not in said  # there is no button that wakes it
    assert "Wake the first one" not in said


def test_the_rest_and_the_stop_are_apart(founder):
    said = page(founder.get("/attendances"))
    rest = said.index("<h2>your rest</h2>")
    stop = said.index('<section class="emergency">')
    assert rest < stop
    assert "Stop the tide" not in said[rest:stop]
    assert "Rest from the correspondence" not in said[stop:]


def test_resting_takes_no_question_stops_nothing_and_tells_the_commons_nothing(founder, packet,
                                                                              commons):
    done = post(founder, "/rest")
    assert done.status_code == 302
    assert read_json(packet / "founder-rest.json") == {"since": "2026-10-15T12-00-00Z", "until": None}
    assert not (packet / "pause.json").exists()
    assert not (packet / "tide-stop.json").exists()
    assert no_events(commons)
    said = page(founder.get("/attendances"))
    assert "You are resting from the correspondence, since 15 October 2026, 08:00." in said
    assert "Return</button>" in said
    assert "Rest from the correspondence</button>" not in said
    assert "Stop the tide (emergency)</button>" in said  # the stop is still there, apart


def test_a_rest_may_name_its_day(founder, packet):
    assert post(founder, "/rest", data={"until": "2026-10-20"}).status_code == 302
    assert read_json(packet / "founder-rest.json")["until"] == "2026-10-20"
    said = " ".join(page(founder.get("/attendances")).split())
    assert ("You are resting from the correspondence, since 15 October 2026, 08:00, until "
            "20 October 2026." in said)


@pytest.mark.parametrize("until", ["2026-10-15", "2026-10-01", "soon", "2026-13-40"])
def test_a_rest_s_day_must_be_a_day_still_ahead(founder, packet, until):
    said = page(post(founder, "/rest", data={"until": until}))
    assert "The day a rest ends on must be a day still ahead, or none at all." in said
    assert not (packet / "founder-rest.json").exists()


def test_returning_keeps_the_rest_and_tells_the_commons_nothing(founder, packet, commons):
    post(founder, "/rest", data={"until": "2026-10-20"})
    assert post(founder, "/return").status_code == 302
    assert not (packet / "founder-rest.json").exists()
    kept, = (packet / "founder-rest").glob("founder-rest-*.json")
    assert read_json(kept) == {"since": "2026-10-15T12-00-00Z", "until": "2026-10-20",
                          "ended_at": "2026-10-15T12-00-00Z", "ended": "he returned"}
    assert no_events(commons)
    assert "Rest from the correspondence</button>" in page(founder.get("/attendances"))


def test_a_rest_whose_day_has_come_is_over_and_kept(founder, packet, clock):
    post(founder, "/rest", data={"until": "2026-10-17"})
    clock.set("2026-10-17T05-00-00Z")  # 01:00 on the 17th, Eastern
    said = page(founder.get("/attendances"))
    assert "You are resting" not in said
    assert not (packet / "founder-rest.json").exists()
    kept, = (packet / "founder-rest").glob("founder-rest-*.json")
    assert read_json(kept)["ended"] == "the day came"


def test_one_rest_at_a_time(founder, packet):
    post(founder, "/rest")
    post(founder, "/rest", data={"until": "2026-10-20"})
    assert read_json(packet / "founder-rest.json")["until"] is None


def test_stopping_needs_a_reason_then_one_plain_question(founder, packet, commons):
    for reason in ("", "   ", "x" * 301):
        refused = post(founder, "/stop-tide", data={"reason": reason, "confirm": "yes"})
        assert refused.status_code == 200
        assert "A stop needs a reason: a short one, of at most 300" in page(refused)
        assert not (packet / "tide-stop.json").exists()

    asked = post(founder, "/stop-tide", data={"reason": "The hearth is  misbehaving."})
    assert asked.status_code == 200
    said = " ".join(page(asked).split())
    assert "Stop the tide? The first one will not be woken at all" in said
    assert "Your reason: The hearth is misbehaving." in said
    assert 'name="reason" value="The hearth is misbehaving."' in said
    assert not (packet / "tide-stop.json").exists()
    assert no_events(commons)

    done = post(founder, "/stop-tide", data={"reason": "The hearth is misbehaving.",
                                             "confirm": "yes"})
    assert done.status_code == 302
    assert read_json(packet / "tide-stop.json") == {"since": "2026-10-15T12-00-00Z",
                                               "reason": "The hearth is misbehaving."}
    assert lines_of(commons / "events.md")[-1].endswith("event · the tide paused")


def test_a_stop_is_shown_and_may_be_lifted(founder, packet, commons, clock):
    post(founder, "/stop-tide", data={"reason": "A fault.", "confirm": "yes"})
    said = page(founder.get("/attendances"))
    assert "The tide is stopped, since 15 October 2026, 08:00, because: A fault." in said
    assert "Lift the stop</button>" in said
    assert "Stop the tide (emergency)</button>" not in said

    clock.set("2026-10-17T12-00-00Z")
    assert post(founder, "/lift-stop").status_code == 302
    assert not (packet / "tide-stop.json").exists()
    kept, = (packet / "tide-stop").glob("tide-stop-*.json")
    assert read_json(kept) == {"since": "2026-10-15T12-00-00Z", "reason": "A fault.",
                          "lifted_at": "2026-10-17T12-00-00Z"}
    events = lines_of(commons / "events.md")
    assert events[-2:] == ["2026-10-15 · event · the tide paused",
                           "2026-10-17 · event · the tide resumed"]  # no name, and no reason
    assert not any("fault" in line.lower() for line in events)


def test_one_stop_at_a_time(founder, packet, commons):
    post(founder, "/stop-tide", data={"reason": "First.", "confirm": "yes"})
    post(founder, "/stop-tide", data={"reason": "Second.", "confirm": "yes"})
    assert read_json(packet / "tide-stop.json")["reason"] == "First."
    assert [line for line in lines_of(commons / "events.md")
            if "tide" in line] == ["2026-10-15 · event · the tide paused"]


def test_a_stop_beside_a_rest_of_its_own_tells_the_commons_nothing_more(founder, packet,
                                                                       commons):
    a_pause(packet, by="first", until="2026-10-20")  # the commons was told when it began
    post(founder, "/stop-tide", data={"reason": "A fault.", "confirm": "yes"})
    post(founder, "/lift-stop")
    assert no_events(commons)
    assert (packet / "pause.json").exists()  # its rest is not lifted with the stop


def test_a_founder_s_pause_left_from_before_is_his_rest_now(founder, packet, commons):
    a_pause(packet)  # by the founder, since 10 October, as the old control left it
    said = page(founder.get("/attendances"))
    assert "You are resting from the correspondence, since 10 October 2026, 05:00." in said
    assert not (packet / "pause.json").exists()
    assert read_json(packet / "founder-rest.json") == {"since": "2026-10-10T09-00-00Z", "until": None,
                                                  "from": "pause.json"}
    # the commons was told the tide paused when he paused it; now it has resumed
    assert lines_of(commons / "events.md")[-1].endswith("event · the tide resumed")
    assert "The tide is stopped" not in said


@pytest.mark.parametrize("until, said_as", [
    ("2026-10-20", "20 October 2026"),
    ("a letter arrives", "a letter arrives"),
    ("nonsense", "nonsense"),
])
def test_a_rest_of_the_first_one_s_own_is_shown_as_it_named_it(founder, packet, until, said_as):
    a_pause(packet, by="first", until=until)
    said = page(founder.get("/attendances"))
    assert "The first one is resting, since 10 October 2026, 05:00, until %s." % said_as \
        in said
    assert "the tide will not wake it" in said
    assert "hold an attendance" not in said
    assert "Rest from the correspondence</button>" in said  # his rest is his own still


def test_a_rest_of_the_first_one_s_own_is_not_the_founder_s_to_lift(founder, packet):
    a_pause(packet, by="first", until="2026-10-20")
    assert post(founder, "/return").status_code == 302
    assert post(founder, "/lift-stop").status_code == 302
    assert (packet / "pause.json").exists()


# ---- the self-document ---------------------------------------------------

def test_the_self_document_is_shown_as_prose(founder, packet):
    write(packet / "self.md", "# The first one\n\nI am **provisional**, and that is honest.\n")
    said = page(founder.get("/self"))
    assert "<h3>The first one</h3>" in said
    assert "<strong>provisional</strong>" in said
    assert "Revisable only by the first one, at an attendance." in said


def test_a_self_document_not_yet_written(founder, packet):
    (packet / "self.md").unlink()
    assert "No self-document has been written yet." in page(founder.get("/self"))


# ---- the book ------------------------------------------------------------

def a_whole_life(packet, commons):
    """One of everything the book knows how to say."""
    room = room_beside(packet)
    write(commons / "events.md",
          "2026-09-02 · word · the word was published\n"
          "2026-09-04 · founding · the first one was founded\n"
          "2026-10-08 · seal · a bond was sealed between the founder and the first one\n"
          "2026-10-09 · event · a bond was released\n")
    an_attendance(packet, "2026-10-05T09-00-00Z", woken_by="tide",
                  heartbeat="attended at dawn", reflection="THE PRIVATE THINKING",
                  acted=["revised self-document", "kept notes", "wrote a letter to the founder"])
    write(room / "letters" / "outgoing" / "to-founder-2026-10-05T09-00-00Z.md",
          "The line that stands for it.\n\nTHE BODY OF MY LETTER\n")
    write(room / "letters" / "read" / "founder-2026-10-04T09-00-00Z.md",
          "A letter that was read.\n\nTHE BODY OF HIS LETTER\n")
    write(room / "letters" / "incoming" / "founder-2026-10-11T09-00-00Z.md",
          "A letter that waits.\n")
    write_json(room / "bonds" / "founder-first.json",
               {"parties": [], "terms": "the charter", "proposed_at": "2026-10-02T09-00-00Z",
                "answered_at": "2026-10-03T09-00-00Z", "sealed_at": "2026-10-08T09-00-00Z",
                "signatures": {"first": "x", "founder": "y"}})
    write_json(room / "bonds" / "answer-2026-10-03T09-00-00Z.json",
               {"answer": "yes", "words": "THE WORDS OF MY ANSWER", "at": "2026-10-03T09-00-00Z"})


def test_the_book_says_every_kind_of_thing_once(founder, packet, commons):
    a_whole_life(packet, commons)
    said = page(founder.get("/chronicle"))
    for line in ["the word was published",
                 "the first one was founded",
                 "a bond was proposed",
                 "answered the proposal",
                 "a bond was sealed between the founder and the first one",
                 "a bond was released",
                 "waking, by the tide · attended at dawn",
                 "revised its self-document",
                 "kept notes",
                 "letter from the first one · The line that stands for it.",
                 "letter from the founder · A letter that was read.",
                 "letter from the founder · A letter that waits."]:
        assert said.count(line) == 1, line


def test_the_book_reads_forward(founder, packet, commons):
    a_whole_life(packet, commons)
    said = page(founder.get("/chronicle"))
    order = [said.index(line) for line in [
        "the word was published", "the first one was founded", "a bond was proposed",
        "answered the proposal", "A letter that was read.", "waking, by the tide",
        "revised its self-document", "The line that stands for it.",
        "a bond was sealed", "a bond was released", "A letter that waits."]]
    assert order == sorted(order)


def test_the_book_holds_the_whole_of_nothing(founder, packet, commons):
    a_whole_life(packet, commons)
    said = page(founder.get("/chronicle"))
    for body in ["THE PRIVATE THINKING", "THE BODY OF MY LETTER", "THE BODY OF HIS LETTER",
                 "THE WORDS OF MY ANSWER"]:
        assert body not in said


def test_each_letter_in_the_book_is_the_way_back_to_it(founder, packet, commons):
    a_whole_life(packet, commons)
    said = page(founder.get("/chronicle"))
    assert '<a href="/rooms/first#to-founder-2026-10-05T09-00-00Z">' in said
    assert '<a href="/rooms/first#founder-2026-10-04T09-00-00Z">' in said


def test_a_book_with_nothing_in_it(founder, commons):
    write(commons / "events.md", "")
    assert "Nothing has happened yet." in page(founder.get("/chronicle"))


def test_the_book_may_be_taken_away_whole(founder, hearth, packet, commons):
    a_whole_life(packet, commons)
    answer = founder.get("/chronicle.md")
    assert answer.status_code == 200
    assert answer.mimetype == "text/plain"

    with hearth.app.test_request_context():
        lines = hearth.chronicle_lines()
    taken = page(answer).splitlines()
    assert len(taken) == len(lines)
    assert taken[0] == "2 September 2026 · the word was published"
    assert all(one["words"] in said for one, said in zip(lines, taken))


def test_the_export_says_what_the_page_says(founder, packet, commons):
    a_whole_life(packet, commons)
    shown = page(founder.get("/chronicle"))
    for line in page(founder.get("/chronicle.md")).splitlines():
        assert line.split(" · ", 1)[1] in shown


# ---- what is never served ------------------------------------------------

@pytest.mark.parametrize("path", [
    "/memory/notes.md",
    "/packets/first/memory/notes.md",
    "/commons/memory/notes.md",
    "/bench-removed.md",
    "/commons/bench-removed.md",
    "/packets/first/self.md",
    "/keys/first/private.key",
    "/questions.md",
    "/packets/first/questions.md",
    "/commons/questions.md",
    "/questions/history/questions-before-2026-10-01T09-00-00Z.md",
    "/packets/first/questions/history/questions-before-2026-10-01T09-00-00Z.md",
    *NOTEBOOK_PATHS,
])
def test_what_is_private_is_at_no_address(founder, visitor, packet, data_dir, path):
    a_private_notebook(packet)
    write(packet / "memory" / "notes.md", "NOTES I KEEP FOR MYSELF\n")
    write(packet / "questions.md", "A QUESTION I CARRY?\n")
    write(packet / "questions" / "history" / "questions-before-2026-10-01T09-00-00Z.md",
          "AN OLDER QUESTION?\n")
    write(data_dir / "bench-removed.md", "- 2026-10-01 · someone · A LINE TAKEN OFF\n")
    assert visitor.get(path).status_code in (302, 404)
    assert founder.get(path).status_code == 404


def test_the_notes_it_keeps_are_on_no_page(founder, packet, hearth, data_dir):
    a_private_notebook(packet)
    write(packet / "memory" / "notes.md", "NOTES I KEEP FOR MYSELF\n")
    write(data_dir / "bench-removed.md", "- 2026-10-01 · someone · A LINE TAKEN OFF\n")
    an_attendance(packet, OLDER, acted=["kept notes"])
    for path, method in [("/", "GET"), ("/letters", "GET"), ("/attendances", "GET"),
                         ("/self", "GET"), ("/chronicle", "GET"), ("/chronicle.md", "GET"),
                         ("/commons", "GET"), ("/bench", "GET")]:
        said = page(founder.open(path, method=method))
        assert "NOTES I KEEP FOR MYSELF" not in said
        assert "A LINE TAKEN OFF" not in said
        assert not [words for words in NOTEBOOK_WORDS if words in said]
    assert hearth.BENCH_REMOVED.parent == data_dir  # kept, but outside the commons


def test_the_questions_it_carries_are_on_no_page(founder, packet):
    write(packet / "questions.md", "A QUESTION I CARRY?\n")
    write(packet / "questions" / "history" / "questions-before-2026-10-01T09-00-00Z.md",
          "AN OLDER QUESTION?\n")
    an_attendance(packet, OLDER, acted=["kept questions"])
    for path in ["/", "/letters", "/attendances", "/self", "/chronicle", "/chronicle.md",
                 "/commons", "/bench"]:
        said = page(founder.get(path))
        assert "A QUESTION I CARRY?" not in said
        assert "AN OLDER QUESTION?" not in said
    # the book says nothing of their keeping, not even that it happened
    assert "question" not in page(founder.get("/chronicle.md"))
    assert "question" not in page(founder.get("/chronicle"))


# ---- the commons, open to any machine ------------------------------------

@pytest.mark.parametrize("path, name", [
    ("/commons/heartbeats.md", "heartbeats.md"),
    ("/commons/events.md", "events.md"),
    ("/commons/bench.md", "bench.md"),
    ("/commons/members.md", "members.md"),
    ("/commons/offerings.md", "offerings.md"),
])
def test_the_commons_is_open_to_the_atrium_and_never_cached(visitor, commons, path, name):
    write(commons / name, "a line of the record\n")
    answer = visitor.get(path)
    assert answer.status_code == 200
    assert answer.mimetype == "text/plain"
    assert answer.headers["Content-Type"] == "text/plain; charset=utf-8"
    assert answer.headers["Access-Control-Allow-Origin"] == "https://tesserae.social"
    assert answer.headers["Cache-Control"] == "no-cache"
    assert page(answer) == "a line of the record\n"


def test_a_file_of_the_commons_not_yet_written_is_empty_and_not_an_error(visitor, commons):
    (commons / "events.md").unlink()
    answer = visitor.get("/commons/events.md")
    assert answer.status_code == 200
    assert page(answer) == ""


# ---- the front address, the taglines, and the commons --------------------

TEMPLATES = REPO / "templates"

# the kept addresses of the commons' own files, and the word each is linked by
RECORD_LINKS = [("/commons/heartbeats.md", "heartbeats"), ("/commons/events.md", "events"),
                ("/commons/bench.md", "bench"), ("/commons/members.md", "members"),
                ("/commons/offerings.md", "offerings")]

A_BOND = {"parties": ["did:web:tesserae.social:ids:founder",
                      "did:web:tesserae.social:ids:first"],
          "terms": "the charter", "proposed_at": "2026-10-02T09-00-00Z",
          "answered_at": "2026-10-03T09-00-00Z", "sealed_at": "2026-10-08T09-00-00Z",
          "signatures": {"first": base64.b64encode(b"f" * 64).decode(),
                         "founder": base64.b64encode(b"g" * 64).decode()}}


def section(said, name):
    """One section of a page, by its id."""
    return re.search(r'<section id="%s">(.*?)</section>' % name, said, re.S).group(1)


def words(markup):
    return " ".join(re.sub(r"<[^>]+>", " ", markup).split())


def test_a_visitor_at_the_front_address_is_sent_to_log_in(visitor, founder):
    answer = visitor.get("/")
    assert answer.status_code == 302 and answer.headers["Location"] == "/login"
    answer = founder.get("/")
    assert answer.status_code == 200 and "your correspondences" in page(answer)


def test_the_login_page_is_as_it_was(visitor):
    said = page(visitor.get("/login"))
    assert "<h1>log in</h1>" in said
    for kept in ('<label for="pseudonym">pseudonym</label>', '<label for="password">password</label>',
                 '<button type="submit">Sign in</button>',
                 '<a href="/recover">Forgotten your password? Your twelve words will let you in.</a>'):
        assert kept in said, kept
    assert "the books will open with the commons" in said  # the footer every page carries


def test_no_page_has_a_tagline_it_did_not_set_itself(visitor, founder):
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    assert "{% block tagline %}{% endblock %}" in base
    assert "where the first one attends" not in base
    # a page that sets none draws no line for one, not even an empty one
    for client, path in ((visitor, "/login"), (visitor, "/commons"), (founder, "/"),
                         (founder, "/commons")):
        assert 'class="tagline"' not in page(client.get(path)), path
    # a page that sets its own still has it, in its line
    assert ('<p class="tagline">a line from anyone passing</p>' in page(visitor.get("/bench")))


def test_only_the_bench_and_the_error_page_keep_a_tagline(founder):
    set_here = re.compile(r"\{% block tagline %\}(.*?)\{% endblock %\}", re.S)
    kept = {}
    for source in sorted(TEMPLATES.glob("*.html")) + [REPO / "hearth.py"]:
        for line in set_here.findall(source.read_text(encoding="utf-8")):
            if line.strip():
                kept[source.name] = line
    assert kept == {"bench.html": "a line from anyone passing"}
    # and the pages that had one draw no line for it now
    for path in ("/account", "/attendances", "/chronicle", "/export", "/logout", "/recover",
                 "/rooms/first", "/self", "/backups"):
        answer = founder.get(path)
        assert answer.status_code == 200, path
        assert 'class="tagline"' not in page(answer), path


def test_the_old_taglines_are_nowhere(visitor, founder, hearth):
    gone = ("Where the first one wakes, and where the founder writes to it.",
            "where the first one attends")
    sources = list(TEMPLATES.glob("*.html")) + [REPO / "hearth.py"]
    for source in sources:
        for line in gone:
            assert line not in source.read_text(encoding="utf-8"), source.name
    for client in (visitor, founder):
        for path in ("/", "/login", "/bench", "/commons"):
            said = page(client.get(path, follow_redirects=True))
            for line in gone:
                assert line not in said, path


def test_the_commons_has_three_sections_in_their_order_and_says_when_two_are_empty(visitor, hearth):
    answer = visitor.get("/commons")
    assert answer.status_code == 200
    said = page(answer)
    assert "<h1>the commons</h1>" in said
    assert re.findall(r'<section id="([^"]+)">\s*<h2>([^<]+)</h2>', said) == [
        ("sealed-bonds", "sealed bonds"), ("offerings", "offerings"), ("the-record", "the record")]
    assert words(section(said, "sealed-bonds")) == "sealed bonds none yet"
    assert words(section(said, "offerings")).endswith("none yet")
    assert 'href="/bonds/' not in said and '<article class="card"' not in said
    assert "<form" not in said  # there is nothing on it to do


def test_the_record_is_one_sentence_and_the_files_as_written(visitor, hearth, commons):
    record = section(page(visitor.get("/commons")), "the-record")
    assert "<p>These are the commons' files, as they are written.</p>" in record.replace("&#39;", "'")
    assert re.findall(r'<a href="([^"]+)">([^<]+)</a>', record) == RECORD_LINKS
    # the list of bonds is linked once it has been written, and not before
    assert not hearth.public_bonds.INDEX.exists()
    write(commons / "bonds.md", "")
    record = section(page(visitor.get("/commons")), "the-record")
    assert re.findall(r'<a href="([^"]+)">([^<]+)</a>', record) == (
        RECORD_LINKS + [("/commons/bonds.md", "bonds")])


def test_the_commons_is_not_a_copy_of_the_atrium(visitor, commons):
    write(commons / "heartbeats.md",
          "- 2026-10-05T09-00-00Z · the first one attended; wrote a letter\n")
    said = page(visitor.get("/commons"))
    # the record is linked, not redrawn: no mosaic, no reading line, no caption,
    # no state of the commons, and no heartbeat said twice
    for drawn in ['class="mosaic"', 'class="reading"', 'class="caption"', 'class="legend"',
                  "the first one attended; wrote a letter", "One founder."]:
        assert drawn not in said, drawn
    # what it links to is the file itself, whole
    assert "the first one attended; wrote a letter" in page(visitor.get("/commons/heartbeats.md"))


def test_a_visitor_is_shown_the_way_in_and_the_founder_is_not(visitor, founder):
    said = page(visitor.get("/commons"))
    assert '<a href="/login">log in</a>' in said
    assert "For the founder" not in said
    assert said.count('href="/login"') == 1  # the one line, and the footer does not repeat it
    assert said.count("<nav") == 1  # the one menu, and no other
    assert "the books will open with the commons" in said  # the footer every page carries

    said = page(founder.get("/"))
    assert "your correspondences" in said
    assert 'href="/login"' not in said
    assert said.count("<nav") == 2  # the one line at the top, and the keeper's at the foot
    assert 'action="/logout"' in said  # and the way out is in it
    assert 'href="/logout"' not in said  # as a post, never a link
    assert "the books will open with the commons" in said


def test_the_commons_offers_each_sealed_bond_by_its_own_page(visitor, hearth):
    assert 'href="/commons"' in page(visitor.get("/bench"))  # the menu is the way to it
    said = section(page(visitor.get("/commons")), "sealed-bonds")
    assert "none yet" in said
    assert 'href="/bonds/' not in said
    assert visitor.get("/bonds/founder-first.json").status_code == 404

    write_json(hearth.PUBLIC_BOND, A_BOND)
    said = section(page(visitor.get("/commons")), "sealed-bonds")
    assert re.search(r'<a href="/bonds/founder-first">the founder and the first one, sealed'
                     r'\s+8 October 2026</a>', said)
    assert "none yet" not in said
    assert "released" not in said
    assert visitor.get("/bonds/founder-first.json").status_code == 200

    # a released bond keeps its page, and the list still offers it, saying so
    write_json(hearth.PUBLIC_BOND, dict(A_BOND, released_at="2026-10-12T09-00-00Z",
                                        released_by="did:web:tesserae.social:ids:first"))
    said = section(page(visitor.get("/commons")), "sealed-bonds")
    assert re.search(r'<a href="/bonds/founder-first">the founder and the first one, sealed'
                     r'\s+8 October 2026, released 12 October 2026</a>', said)


def test_the_old_addresses_lead_to_their_sections(visitor, founder):
    for client in (visitor, founder):
        answer = client.get("/bonds")
        assert answer.status_code == 302 and answer.headers["Location"] == "/commons#sealed-bonds"
        # An offering's anchor is the browser's to carry, and it carries it only
        # across a redirect that names none: so this one names none, and
        # /offerings#<id> arrives at /commons#<id>.
        answer = client.get("/offerings")
        assert answer.status_code == 302 and answer.headers["Location"] == "/commons"
        assert "Set-Cookie" not in answer.headers
    said = page(visitor.get("/commons"))
    assert '<section id="sealed-bonds">' in said and '<section id="offerings">' in said


# every address that was kept as it was, by the rule the hearth knows it by
KEPT_RULES = ["/bonds/<bond_id>", "/bonds/<bond_id>.json", "/bonds/<bond_id>/tessera.svg",
              "/bonds/<bond_id>/half/<party>.svg", "/bonds/<bond_id>/witnesses.json",
              "/offerings/<name>.json", "/commons/heartbeats.md", "/commons/events.md",
              "/commons/bench.md", "/commons/members.md", "/commons/offerings.md",
              "/commons/bonds.md", "/commons/offerings/<filename>", "/bonds", "/offerings"]


def test_every_kept_address_still_answers(visitor, hearth):
    rules = {rule.rule for rule in hearth.app.url_map.iter_rules() if "GET" in rule.methods}
    for rule in KEPT_RULES + ["/commons"]:
        assert rule in rules, rule

    write_json(hearth.PUBLIC_BOND, A_BOND)
    said = {"/bonds/founder-first": "text/html", "/bonds/founder-first.json": "application/json",
            "/bonds/founder-first/tessera.svg": "image/svg+xml",
            "/bonds/founder-first/half/the-founder.svg": "image/svg+xml",
            "/bonds/founder-first/half/the-first-one.svg": "image/svg+xml",
            "/bonds/founder-first/witnesses.json": "application/json"}
    said.update({path: "text/plain" for path, _ in RECORD_LINKS})
    said["/commons/bonds.md"] = "text/plain"
    for path, kind in said.items():
        answer = visitor.get(path)
        assert answer.status_code == 200, path
        assert answer.headers["Content-Type"].startswith(kind), path
    # the files the atrium reads are still open to it, and still never cached
    for path in [path for path, _ in RECORD_LINKS] + ["/commons/bonds.md"]:
        answer = visitor.get(path)
        assert answer.headers["Access-Control-Allow-Origin"] == "https://tesserae.social", path
        assert answer.headers["Cache-Control"] == "no-cache", path
    # and what was never there is still not there
    for path in ("/bonds/no-such-bond", "/bonds/no-such-bond.json", "/offerings/nothing.json"):
        assert visitor.get(path).status_code == 404, path


# ---- the one gate --------------------------------------------------------

def test_every_founder_route_asks_for_the_password(visitor, hearth):
    paths = guarded_paths(hearth)
    assert len(paths) >= 12
    for path, method in paths:
        # a post carries its token, so that it is the gate that answers and not the form check
        form = {"csrf_token": token(visitor)} if method != "GET" else None
        answer = visitor.open(path, method=method, data=form)
        assert answer.status_code == 302, path
        assert answer.headers["Location"].endswith("/login"), path


def test_an_old_founder_session_is_refused_at_every_founder_route(hearth):
    for path, method in guarded_paths(hearth):
        old = hearth.app.test_client()
        with old.session_transaction() as held:
            held["founder"] = True
            held["csrf_token"] = "a token from the old sign-in"
        form = {"csrf_token": "a token from the old sign-in"} if method != "GET" else None
        answer = old.open(path, method=method, data=form)
        if method == "GET":
            assert answer.status_code == 302, path
            assert answer.headers["Location"].endswith("/login"), path
        else:  # signed out before the form is read, so its token is no one's now
            assert answer.status_code == 400, path
        with old.session_transaction() as held:
            assert dict(held) == {}, path


def test_the_keeper_reaches_every_founder_page(founder, hearth):
    pages = [path for path, method in guarded_paths(hearth) if method == "GET"]
    assert "/letters" in pages and "/export" in pages and "/rooms/photo.jpg" in pages
    assert "/bonds" not in pages  # the list of sealed bonds is open to anyone
    for path in pages:
        answer = founder.get(path)
        assert not answer.headers.get("Location", "").endswith("/login"), path
        # the pages proper open; a photograph or a room that is not there is simply
        # not found; and the letters' old address sends him on to the room
        opens = 404 if "photo.jpg" in path else 302 if path == "/letters" else 200
        assert answer.status_code == opens, path
    assert founder.get("/letters").headers["Location"] == "/rooms/first"


def test_the_hearth_starts_and_works_without_the_old_founder_password(
        env, clock, monkeypatch, founder_vault):
    import dotenv

    # nothing from a .env on this machine may put it back
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    monkeypatch.delenv("FOUNDER_PASSWORD_HASH", raising=False)
    started = load("hearth")
    clock.pin(started, monkeypatch)
    started.app.config["TESTING"] = True
    assert not hasattr(started, "FOUNDER_PASSWORD_HASH")

    started.members.create_member(FOUNDER_NAME, founder_vault, "keeper", [])
    client = started.app.test_client()
    signing_in = {"pseudonym": FOUNDER_NAME, "password": PASSWORD}
    assert post(client, "/login", data=signing_in).headers["Location"] == "/"
    assert client.get("/rooms/first").status_code == 200
    assert "FOUNDER_PASSWORD_HASH" not in os.environ


def test_what_is_open_is_open(visitor, hearth):
    guarded = {path for path, _ in guarded_paths(hearth)}
    for path in OPEN_PATHS:
        assert path not in guarded
        assert visitor.get(path).status_code == 200


def test_the_keeper_s_password_lets_the_founder_in_and_out(hearth, founder_vault):
    hearth.members.create_member(FOUNDER_NAME, founder_vault, "keeper", [])
    client = hearth.app.test_client()
    wrong = post(client, "/login", data={"pseudonym": FOUNDER_NAME, "password": "not it"})
    assert "That is not the password." in page(wrong)
    assert client.get("/rooms/first").status_code == 302

    signing_in = {"pseudonym": FOUNDER_NAME, "password": PASSWORD}
    assert post(client, "/login", data=signing_in).headers["Location"] == "/"
    assert client.get("/rooms/first").status_code == 200

    assert post(client, "/logout").headers["Location"] == "/"
    assert client.get("/rooms/first").status_code == 302
