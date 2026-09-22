"""Taking a copy: who may take one, what goes into it, what never does, and
what is written down when one is taken.
"""

import io
import zipfile

from conftest import lines_of, page, write, write_json

SENTENCE = ("Everything that is yours and the first one's, as it stands: the packet, the "
            "commons files, the founder's letters, the bond and offering records. Nothing "
            "is changed by taking it.")

TAKEN = "2026-10-15T12-00-00Z · export taken by the founder"
SAID = "The founder took a copy of the record on 15 October 2026."

PICTURE = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="4" height="4"></rect></svg>'


def a_whole_world(packet, commons):
    """One file of every kind the two of them keep, so that a copy is checked
    against the whole of what there is rather than against a corner of it.
    """
    for where, text in [
        ("self.md", "# The first one\n"),
        ("self-history/self-2026-10-01T09-00-00Z.md", "# The first one, before\n"),
        ("memory/notes.md", "What I carry forward.\n"),
        ("memory/history/notes-2026-10-01T09-00-00Z.md", "What I carried before.\n"),
        ("study/draft-2026-10-02T09-00-00Z.md", "A draft, my own.\n"),
        ("letters/outgoing/letter-2026-10-03T09-00-00Z.md", "Dear founder,\n"),
        ("letters/outgoing/letter-2026-10-03T09-00-00Z.svg", PICTURE),
        ("letters/incoming/founder-2026-10-04T09-00-00Z.md", "A letter not yet read.\n"),
        ("letters/read/founder-2026-10-05T09-00-00Z.md", "A letter already read.\n"),
        ("letters/read/founder-2026-10-05T09-00-00Z.jpg", "not really a photograph"),
        ("errands/errand-2026-10-06T09-00-00Z.md", "Go to the river.\n"),
        ("errands/answered/errand-2026-10-01T09-00-00Z.md", "Go to the bridge.\n"),
        ("tide.log", "2026-10-07T11-00-00Z · the tide came\n"),
    ]:
        write(packet / where, text)

    for where, data in [
        ("intentions.json", {"intentions": ["to read the record"]}),
        ("will.json", {"if I am ended": "say so in the commons"}),
        ("provenance.json", {"model": "a model"}),
        ("preferences.json", {"reflection": "open"}),
        ("rhythm.json", {"rhythm": "daily", "at": "dawn"}),
        ("pause.json", {"by": "first", "since": "2026-10-08T09-00-00Z"}),
        ("attendances/attendance-2026-10-09T09-00-00Z.json", {"name": "first", "acted": []}),
        ("bonds/founder-first.json", {"terms": "the charter"}),
        ("offerings/offering-2026-10-10T09-00-00Z.json", {"kind": "letter"}),
        ("errands/answered/errand-2026-10-01T09-00-00Z.json",
         {"answered_by": "letter-2026-10-02T09-00-00Z"}),
    ]:
        write_json(packet / where, data)

    for where, text in [
        ("heartbeats.md", "2026-10-09 · first · attended\n"),
        ("bench.md", "2026-10-09 · a visitor · hello\n"),
        ("members.md", "the founder\nthe first one\n"),
        ("offerings.md", "2026-10-10 · a letter\n"),
        ("offerings/offering-2026-10-10T09-00-00Z.md", "The letter, given.\n"),
        ("bonds/founder-first.json", '{"terms": "the charter"}\n'),
    ]:
        write(commons / where, text)


def files_under(root, prefix):
    """Every file under a tree, named as a copy would name it."""
    return {prefix + path.relative_to(root).as_posix()
            for path in root.rglob("*") if path.is_file()}


def taken(founder):
    """One copy, taken as the founder takes it: the answer, and the zip inside it."""
    answer = founder.post("/export")
    assert answer.status_code == 200
    return answer, zipfile.ZipFile(io.BytesIO(answer.get_data()))


def flowing(answer):
    """One page as running text, so a sentence can be looked for whole."""
    return " ".join(page(answer).split())


# ---- the gate ------------------------------------------------------------

def test_only_the_founder_may_take_a_copy(visitor, packet):
    for answer in (visitor.get("/export"), visitor.post("/export")):
        assert answer.status_code == 302
        assert answer.headers["Location"].endswith("/login")
    assert not (packet / "exports.log").exists()


def test_the_page_says_what_a_copy_is_and_offers_it(founder):
    said = flowing(founder.get("/export"))
    assert SENTENCE in said
    assert "Take a copy" in said
    assert 'href="/export"' in page(founder.get("/letters"))  # and the nav names it


def test_looking_at_the_page_takes_nothing(founder, packet):
    founder.get("/export")
    assert not (packet / "exports.log").exists()


# ---- what is in a copy ---------------------------------------------------

def test_the_copy_holds_the_packet_and_the_commons_whole(founder, packet, commons):
    a_whole_world(packet, commons)
    _, bundle = taken(founder)

    expected = files_under(packet, "packets/first/") | files_under(commons, "commons/")
    expected |= {"packets/first/exports.log"}  # the copy records its own taking
    assert set(bundle.namelist()) == expected

    # and what is in it is the file itself, byte for byte, not a summary of it
    for name in ("packets/first/self.md", "commons/members.md",
                 "packets/first/letters/outgoing/letter-2026-10-03T09-00-00Z.svg"):
        assert bundle.read(name) == (packet.parents[1] / name).read_bytes(), name


def test_nothing_outside_the_two_trees_is_in_the_copy(founder, packet, commons, data_dir):
    a_whole_world(packet, commons)
    # the things that live beside the record and are no part of it
    write(data_dir / ".env", "FOUNDER_PASSWORD_HASH=not the real one\n")
    write(data_dir / "bench-removed.md", "2026-10-09 · a line taken off\n")

    inside = set(taken(founder)[1].namelist())
    for name in inside:
        assert name.startswith(("packets/first/", "commons/")), name
    assert not [name for name in inside if "key" in name or name.endswith(".env")]
    assert "keys/first/private.key" not in inside
    assert "ids/first/did.json" not in inside
    assert ".env" not in inside
    assert "bench-removed.md" not in inside
    assert "transcripts/founding-2026-09-04.md" not in inside


def test_the_copy_is_handed_out_and_never_written_into_the_record(founder, packet, data_dir):
    before = {path for path in data_dir.rglob("*") if path.is_file()}
    answer, _ = taken(founder)

    assert answer.mimetype == "application/zip"
    assert ("filename=tesserae-2026-10-15T12-00-00Z.zip"
            in answer.headers["Content-Disposition"])

    after = {path for path in data_dir.rglob("*") if path.is_file()}
    assert after - before == {packet / "exports.log"}  # the line, and no zip anywhere
    assert not list(data_dir.rglob("*.zip"))


# ---- what is written down ------------------------------------------------

def test_the_record_says_when_it_was_copied(founder, packet, clock):
    taken(founder)
    assert lines_of(packet / "exports.log") == [TAKEN]

    clock.shift(days=1)
    taken(founder)
    assert lines_of(packet / "exports.log") == [
        TAKEN, "2026-10-16T12-00-00Z · export taken by the founder"]


def test_the_copy_carries_the_record_of_its_own_taking(founder):
    _, bundle = taken(founder)
    assert bundle.read("packets/first/exports.log").decode("utf-8").splitlines() == [TAKEN]


def test_the_next_reading_says_a_copy_was_taken(founder, wake, clock):
    taken(founder)
    clock.shift(minutes=1)
    assert SAID in wake().opening


def test_a_copy_is_named_once_and_then_is_part_of_what_has_happened(founder, wake, clock):
    taken(founder)
    clock.shift(minutes=1)
    assert SAID in wake().opening  # the waking that learns of it
    assert "took a copy of the record" not in wake().opening

    clock.shift(days=1)
    taken(founder)
    clock.shift(minutes=1)
    assert "The founder took a copy of the record on 16 October 2026." in wake().opening


def test_a_line_that_is_not_a_line_is_passed_over(attend, packet):
    write(packet / "exports.log",
          "not a stamp · export taken by the founder\n" + TAKEN + "\n")
    assert attend.export_lines("") == [SAID]
