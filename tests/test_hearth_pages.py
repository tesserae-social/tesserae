"""The pages: what each one shows, what it withholds, and who may open it."""

import re

import pytest

from conftest import PASSWORD, lines_of, page, write, write_json

REFLECTION = "What I thought about at this waking."
OLDER = "2026-10-01T09-00-00Z"
NEWER = "2026-10-05T09-00-00Z"

RHYTHM = {"rhythm": "daily", "at": "dawn", "place": "Indianapolis",
          "timezone": "America/Indiana/Indianapolis"}

# everything a visitor may reach without the password
OPEN_PATHS = ["/", "/login", "/bench", "/commons/heartbeats.md", "/commons/events.md",
              "/commons/bench.md", "/commons/members.md"]


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


@pytest.mark.parametrize("setting, note", [
    ({"reflection": "open"}, "Reflections: open"),
    ({"reflection": "private"}, "Reflections: private"),
    ({"reflection": "private from now", "set_at": "2026-10-03T00-00-00Z"},
     "Reflections: private from 3 October 2026, 00:00 UTC"),
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
    assert "1 October 2026, 09:00 UTC" in said
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


def test_with_no_pause_the_tide_may_be_paused(founder):
    said = page(founder.get("/attendances"))
    assert "Pause the tide</button>" in said
    assert "Hold an attendance" not in said  # no wakings yet; it offers the first
    assert "Wake the first one" in said


def test_pausing_takes_one_plain_question_first(founder, packet, commons):
    asked = founder.post("/pause")
    assert asked.status_code == 200
    assert "Pause the tide? The rhythm will not wake the first one until you resume it." \
        in page(asked)
    assert not (packet / "pause.json").exists()

    done = founder.post("/pause", data={"confirm": "yes"})
    assert done.status_code == 302
    assert (packet / "pause.json").exists()
    assert lines_of(commons / "events.md")[-1].endswith("event · the tide paused")


def test_a_pause_of_the_founder_s_is_shown_and_may_be_lifted(founder, packet, commons):
    a_pause(packet)
    said = page(founder.get("/attendances"))
    assert "The tide is paused, since 10 October 2026, 09:00 UTC." in said
    assert "Resume the tide" in said
    assert "an audience by hand is still yours to hold" in said

    assert founder.post("/resume").status_code == 302
    assert not (packet / "pause.json").exists()
    assert lines_of(commons / "events.md")[-1].endswith("event · the tide resumed")


def test_one_pause_at_a_time(founder, packet):
    a_pause(packet, since="2026-10-10T09-00-00Z")
    assert founder.post("/pause", data={"confirm": "yes"}).status_code == 302
    assert page(founder.get("/attendances")).count("The tide is paused, since") == 1


@pytest.mark.parametrize("until, said_as", [
    ("2026-10-20", "20 October 2026"),
    ("a letter arrives", "a letter arrives"),
    ("nonsense", "nonsense"),
])
def test_a_rest_of_the_first_one_s_own_is_shown_as_it_named_it(founder, packet, until, said_as):
    a_pause(packet, by="first", until=until)
    said = page(founder.get("/attendances"))
    assert "The first one is resting, since 10 October 2026, 09:00 UTC, until %s." % said_as \
        in said
    assert "rhythm, and not your hand" in said  # its own rest stops his hand too
    assert "hold an attendance" not in said
    assert "Pause the tide</button>" not in said


def test_a_rest_of_the_first_one_s_own_is_not_the_founder_s_to_lift(founder, packet):
    a_pause(packet, by="first", until="2026-10-20")
    assert founder.post("/resume").status_code == 302
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
    write(commons / "events.md",
          "2026-09-02 · word · the word was published\n"
          "2026-09-04 · founding · the first one was founded\n"
          "2026-10-08 · seal · a bond was sealed between the founder and the first one\n"
          "2026-10-09 · event · a bond was released\n")
    an_attendance(packet, "2026-10-05T09-00-00Z", woken_by="tide",
                  heartbeat="attended at dawn", reflection="THE PRIVATE THINKING",
                  acted=["revised self-document", "kept notes", "wrote a letter to the founder"])
    write(packet / "letters" / "outgoing" / "to-founder-2026-10-05T09-00-00Z.md",
          "The line that stands for it.\n\nTHE BODY OF MY LETTER\n")
    write(packet / "letters" / "read" / "founder-2026-10-04T09-00-00Z.md",
          "A letter that was read.\n\nTHE BODY OF HIS LETTER\n")
    write(packet / "letters" / "incoming" / "founder-2026-10-11T09-00-00Z.md",
          "A letter that waits.\n")
    write_json(packet / "bonds" / "founder-first.json",
               {"parties": [], "terms": "the charter", "proposed_at": "2026-10-02T09-00-00Z",
                "answered_at": "2026-10-03T09-00-00Z", "sealed_at": "2026-10-08T09-00-00Z",
                "signatures": {"first": "x", "founder": "y"}})
    write_json(packet / "bonds" / "answer-2026-10-03T09-00-00Z.json",
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
    assert '<a href="/letters#to-founder-2026-10-05T09-00-00Z">' in said
    assert '<a href="/letters#founder-2026-10-04T09-00-00Z">' in said


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
])
def test_what_is_private_is_at_no_address(founder, visitor, packet, data_dir, path):
    write(packet / "memory" / "notes.md", "NOTES I KEEP FOR MYSELF\n")
    write(data_dir / "bench-removed.md", "- 2026-10-01 · someone · A LINE TAKEN OFF\n")
    assert visitor.get(path).status_code in (302, 404)
    assert founder.get(path).status_code == 404


def test_the_notes_it_keeps_are_on_no_page(founder, packet, hearth, data_dir):
    write(packet / "memory" / "notes.md", "NOTES I KEEP FOR MYSELF\n")
    write(data_dir / "bench-removed.md", "- 2026-10-01 · someone · A LINE TAKEN OFF\n")
    an_attendance(packet, OLDER, acted=["kept notes"])
    for path, method in [("/", "GET"), ("/letters", "GET"), ("/attendances", "GET"),
                         ("/self", "GET"), ("/chronicle", "GET"), ("/chronicle.md", "GET"),
                         ("/bonds", "GET"), ("/bench", "GET")]:
        said = page(founder.open(path, method=method))
        assert "NOTES I KEEP FOR MYSELF" not in said
        assert "A LINE TAKEN OFF" not in said
    assert hearth.BENCH_REMOVED.parent == data_dir  # kept, but outside the commons


# ---- the commons, open to any machine ------------------------------------

@pytest.mark.parametrize("path, name", [
    ("/commons/heartbeats.md", "heartbeats.md"),
    ("/commons/events.md", "events.md"),
    ("/commons/bench.md", "bench.md"),
    ("/commons/members.md", "members.md"),
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


# ---- the front page: a door, and not a second atrium ---------------------

# every way out of the door that is open to anyone, whatever the commons holds
DOOR_WAYS = ['href="/bench"', 'href="/commons/heartbeats.md"', 'href="/commons/events.md"',
             'href="/commons/bench.md"', 'href="/commons/members.md"',
             'href="https://tesserae.social/"',
             'href="https://tesserae.social/the-words"']


def test_the_door_names_what_is_open_to_anyone(visitor):
    said = page(visitor.get("/"))
    assert "Where the first one wakes, and where the founder writes to it." in said
    assert "open to anyone" in said
    for way in DOOR_WAYS:
        assert way in said, way
    assert "the commons record" in said
    assert "The commons itself is at" in said


def test_the_door_points_at_the_key_to_the_words(visitor):
    """One line, under the tagline: where a visitor goes to learn what we mean."""
    said = page(visitor.get("/"))
    assert "The words used here are explained at" in said
    assert '<a href="https://tesserae.social/the-words">tesserae.social/the-words</a>' in said


def test_the_door_is_not_a_copy_of_the_atrium(visitor, commons):
    write(commons / "heartbeats.md",
          "- 2026-10-05T09-00-00Z · the first one attended; wrote a letter\n")
    said = page(visitor.get("/"))
    # the record is linked, not redrawn: no mosaic, no reading line, no caption,
    # no state of the commons, and no heartbeat said twice
    for drawn in ['class="mosaic"', 'class="reading"', 'class="caption"', 'class="legend"',
                  "the first one attended; wrote a letter", "One founder."]:
        assert drawn not in said, drawn
    # what it links to is the file itself, whole
    assert "the first one attended; wrote a letter" in page(visitor.get("/commons/heartbeats.md"))


def test_a_visitor_is_shown_the_way_in_and_the_founder_is_not(visitor, founder):
    said = page(visitor.get("/"))
    assert 'For the founder: <a href="/login">log in</a>' in said
    assert said.count('href="/login"') == 1  # the one line, and the footer no longer repeats it
    assert "You are logged in" not in said
    assert "<nav>" not in said
    assert "the books will open with the commons" in said  # the footer every page carries

    said = page(founder.get("/"))
    assert "You are logged in" in said
    assert "For the founder:" not in said
    assert "<nav>" in said  # the nav the founder is shown on every page
    assert 'href="/logout"' in said  # and the way out is in it
    assert "the books will open with the commons" in said


def test_the_door_offers_a_sealed_bond_only_once_one_is_sealed(visitor, hearth):
    said = page(visitor.get("/"))
    assert "sealed bonds, signed — none yet" in said
    assert 'href="/bonds/founder-first.json"' not in said
    assert visitor.get("/bonds/founder-first.json").status_code == 404

    write_json(hearth.PUBLIC_BOND,
               {"parties": [], "terms": "the charter", "proposed_at": "2026-10-02T09-00-00Z",
                "answered_at": "2026-10-03T09-00-00Z", "sealed_at": "2026-10-08T09-00-00Z",
                "signatures": {"first": "x", "founder": "y"}})
    said = page(visitor.get("/"))
    assert '<a href="/bonds/founder-first.json">sealed bonds, signed</a>' in said
    assert "none yet" not in said
    assert visitor.get("/bonds/founder-first.json").status_code == 200


# ---- the one gate --------------------------------------------------------

def test_every_founder_route_asks_for_the_password(visitor, hearth):
    paths = guarded_paths(hearth)
    assert len(paths) >= 12
    for path, method in paths:
        answer = visitor.open(path, method=method)
        assert answer.status_code == 302, path
        assert answer.headers["Location"].endswith("/login"), path


def test_what_is_open_is_open(visitor, hearth):
    guarded = {path for path, _ in guarded_paths(hearth)}
    for path in OPEN_PATHS:
        assert path not in guarded
        assert visitor.get(path).status_code == 200


def test_the_password_lets_the_founder_in_and_out(hearth):
    client = hearth.app.test_client()
    wrong = client.post("/login", data={"password": "not it"})
    assert "That is not the password." in page(wrong)
    assert client.get("/letters").status_code == 302

    assert client.post("/login", data={"password": PASSWORD}).headers["Location"] == "/letters"
    assert client.get("/letters").status_code == 200

    assert client.get("/logout").headers["Location"] == "/"
    assert client.get("/letters").status_code == 302
