"""The protected words: names and places that never reach the commons.

The list is private, on the host, at DATA_DIR/private-words.txt. Every public
line the hearth writes goes through it, and so does every public text it
serves; nothing it signs is changed by it. The names here are made up: no
real one is in the source.
"""

import json

import pytest

from conftest import block, blocks, lines_of, page, post, write
from conftest import NOTEBOOK_PATHS, NOTEBOOK_WORDS, a_private_notebook
from test_bond_page import a_bond, placed, threshold_module  # noqa: F401 (fixtures)
from test_offerings import HIS, a_correspondence, offer, only_pending, only_placed

LIST = "Quillon => the founder\n# a note to whoever keeps the list\n\nVarrowmere\nthe Ostle\n"
WORDS = [("Quillon", "the founder"), ("Varrowmere", None), ("the Ostle", None)]


@pytest.fixture
def listed(data_dir):
    return write(data_dir / "private-words.txt", LIST)


# ---- the list, and how a word is protected ---------------------------------

def test_the_list_is_read_with_its_notes_and_blank_lines_passed_over(attend, listed):
    import private_words
    assert private_words.listed() == WORDS


def test_no_list_is_no_words_and_changes_nothing(attend):
    import private_words
    assert private_words.listed() == []
    assert private_words.protect("Quillon went to Varrowmere") == "Quillon went to Varrowmere"


@pytest.mark.parametrize("said, kept", [
    ("Quillon asked about consciousness", "The founder asked about consciousness"),
    ("answered quillon's questions", "answered the founder's questions"),
    ("QUILLON wrote. Quillon slept", "THE FOUNDER wrote. The founder slept"),
    ("Quillon heading to Varrowmere; two days", "The founder heading; two days"),
    ("returned from the Ostle with joy", "returned with joy"),
    ("went to  Varrowmere\tand back", "went\tand back"),
    ("Varrowmere was cold", "A place was cold"),
    ("At Varrowmere, a heron", "At a place, a heron"),
    ("the light over varrowmere", "the light over a place"),
    ("Quillonia and Varrowmeres", "Quillonia and Varrowmeres"),  # whole words only
    ("no names here\n", "no names here\n"),
])
def test_a_word_is_said_as_its_replacement_or_left_out(attend, said, kept):
    import private_words
    assert private_words.protect(said, WORDS) == kept


def test_a_line_with_no_protected_word_comes_back_byte_for_byte(attend):
    import private_words
    line = "- 2026-10-18T12-00-06Z · the first one · attended; chose stillness\r\n"
    assert private_words.protect(line, WORDS) == line


def test_on_a_page_only_the_words_between_tags_are_read(attend):
    import private_words
    html = '<a href="/Quillon" title="Varrowmere">Quillon</a> in Varrowmere.'
    assert private_words.protect_page(html, WORDS) == (
        '<a href="/Quillon" title="Varrowmere">the founder</a>.')


# ---- as it is written ------------------------------------------------------

def test_the_heartbeat_line_keeps_no_protected_word_and_its_record_keeps_its_own(
        wake, listed, commons, packet):
    # its own words go to the commons only where it has chosen to show them
    wake(blocks(block("HEARTBEAT_SHOWN", "words"),
                block("HEARTBEAT", "Quillon at the Ostle; attended")))
    assert lines_of(commons / "heartbeats.md")[-1].endswith("the first one · the founder; attended")
    (record,) = (packet / "attendances").glob("attendance-*.json")
    assert json.loads(record.read_text(encoding="utf-8"))["heartbeat"] == (
        "Quillon at the Ostle; attended")


def test_a_line_of_events_keeps_no_protected_word(hearth, attend, listed, commons):
    hearth.note_event("event", "Quillon was at Varrowmere")
    attend.note_event("event", "a letter for Quillon")
    written = lines_of(commons / "events.md")[-2:]
    assert written[0].endswith(" · event · the founder was")
    assert written[1].endswith(" · event · a letter for the founder")


def test_a_line_on_the_bench_keeps_no_protected_word(hearth, listed, commons):
    hearth.place_line("2026-10-18", "a friend of Quillon", "hello from Varrowmere")
    assert lines_of(commons / "bench.md") == [
        "- 2026-10-18 · a friend of the founder · hello"]


def test_who_is_here_keeps_no_protected_word_once_it_is_tended(hearth, listed, commons):
    write(commons / "members.md", "member · Quillon · keeps the hearth\n")
    hearth.tend_members()
    assert (commons / "members.md").read_text(encoding="utf-8") == (
        "member · the founder · keeps the hearth\n")


# ---- as it is served -------------------------------------------------------

@pytest.mark.parametrize("name", ["heartbeats.md", "events.md", "bench.md", "members.md",
                                  "offerings.md", "bonds.md"])
def test_every_file_of_the_commons_is_served_with_no_protected_word(
        hearth, visitor, listed, commons, name):
    # written before the word was on the list, as the lines already there were
    write(commons / name, "- 2026-10-15 · Quillon heading to Varrowmere; two days\n")
    said = page(visitor.get("/commons/" + name))
    assert said == "- 2026-10-15 · the founder heading; two days\n"


def test_the_bench_page_shows_no_protected_word(hearth, visitor, listed, commons):
    write(commons / "bench.md", "- 2026-10-15 · a passerby · hello Quillon\n")
    said = page(visitor.get("/bench"))
    assert "hello the founder" in said and "Quillon" not in said


def test_a_bond_page_shows_no_protected_word(visitor, listed, placed, threshold_module):
    placed(a_bond(threshold_module, "public", "I will walk Quillon to Varrowmere."))
    said = page(visitor.get("/bonds/founder-first"))
    assert "I will walk the founder." in said
    assert "Quillon" not in said and "Varrowmere" not in said
    # and its signed record is handed out exactly as it was signed
    assert "Quillon to Varrowmere" in page(visitor.get("/bonds/founder-first.json"))


def test_an_offering_is_shown_with_no_protected_word_and_signed_as_it_was(
        founder, wake, visitor, packet, commons, data_dir):
    a_correspondence(packet)
    offer(founder, "passage", HIS, "The lake was still this morning")
    wake(block("OFFER", "consent %s" % only_pending(packet)["id"]))
    one = only_placed(packet)
    write(data_dir / "private-words.txt", "lake => water\n")
    assert "The water was still" in page(visitor.get("/commons/offerings/%s.md" % one["id"]))
    assert "The water was still" in page(visitor.get("/commons"))
    signed = page(visitor.get("/offerings/%s.json" % one["id"]))
    assert "The lake was still" in signed and "water" not in signed


def test_a_private_page_is_not_changed(hearth, founder, listed, packet):
    write(packet / "letters" / "read" / "founder-2026-10-14T09-00-00Z.md",
          "Dear first one,\n\nQuillon here, back from Varrowmere.\n")
    assert "Quillon here, back from Varrowmere." in page(founder.get("/rooms/first"))


def test_no_signed_record_is_among_what_is_protected(hearth):
    assert not hearth.PUBLIC_WORDS & {"public_bond", "offering_record", "public_witnesses",
                                       "member_identity"}


# ---- where the list itself is kept -----------------------------------------

@pytest.mark.parametrize("path", ["/private-words.txt", "/commons/private-words.txt",
                                  "/commons/offerings/private-words.txt",
                                  "/commons/..%2Fprivate-words.txt", *NOTEBOOK_PATHS])
def test_the_list_is_never_served(hearth, visitor, founder, listed, packet, path):
    a_private_notebook(packet)
    for client in (visitor, founder):
        answer = client.get(path)
        assert answer.status_code in (302, 404) and "Varrowmere" not in page(answer)
        assert not [words for words in NOTEBOOK_WORDS if words in page(answer)]
    assert founder.get(path).status_code == 404


def test_the_list_is_in_the_backup_and_never_in_the_plain_export(hearth, listed):
    assert "private-words.txt" not in [name for _, name in hearth.export_files()]
    assert "private-words.txt" in [name for _, name in hearth.export_files(hearth.BACKUP_TREES)]


def test_the_list_is_never_committed_nor_baked_into_the_image():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for ignored in (".gitignore", ".dockerignore"):
        lines = (root / ignored).read_bytes().decode("utf-8", "replace").splitlines()
        assert "private-words.txt" in [line.strip() for line in lines], ignored
