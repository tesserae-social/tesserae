"""Each agent's founding transcript is its own, and no other agent's ever reaches it.

An agent's transcripts are kept in transcripts/<agent>/, and it reads the newest
there. The first one's was kept before there were such folders, directly in
transcripts/, and stays there on the server: while it has no folder of its own
it reads that one file, by its name (attend.FIRST_FOUNDING), and no other file
kept beside it, however new.

Every test here that touches the first one is held in both of its layouts:
"flat", as the server keeps it today, and "folder", as it will be kept once its
transcript is moved into transcripts/first/. In both, another agent's founding,
in its own folder or left flat beside the first one's and newer than it, never
reaches the first one's reading, its read_founding, or a copy of its record.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import (FIRST_FOUNDING, FOUNDING_TRANSCRIPT, REPO, Turn, load, post, write,
                      write_json)
from test_backup import bucket  # noqa: F401 - a fixture, used by name
from test_export import taken
from test_longer_waking import NOT_FOUND, longer, look, world  # noqa: F401 - fixtures
from test_rooms_reading import ERRAND, READING_NOW, a_small_world, fingerprint_of_reading

# Another agent's founding, kept where its own would be, and one left flat beside
# the first one's, newer than it. Neither is ever the first one's.
SECOND_WORDS = "THE SECOND AGENT'S FOUNDING, IN ITS OWN FOLDER"
FLAT_WORDS = "ANOTHER AGENT'S FOUNDING, LEFT FLAT AND NEWER"
SECOND = "transcripts/second/founding-2026-10-20T09-00-00Z.md"
FLAT = "transcripts/founding-2026-10-21T09-00-00Z.md"
STRAYS = (SECOND_WORDS, FLAT_WORDS)


@pytest.fixture(params=["flat", "folder"])
def kept(request, data_dir):
    """Where the first one's transcript is kept, by its path under DATA_DIR."""
    flat = data_dir / "transcripts" / FIRST_FOUNDING
    if request.param == "flat":
        return "transcripts/" + FIRST_FOUNDING
    (data_dir / "transcripts" / "first").mkdir()
    shutil.move(str(flat), str(data_dir / "transcripts" / "first" / FIRST_FOUNDING))
    return "transcripts/first/" + FIRST_FOUNDING


def strays(data_dir):
    write(data_dir / SECOND, SECOND_WORDS + "\n")
    write(data_dir / FLAT, FLAT_WORDS + "\n")


def none_of_the_strays_in(text):
    return not [words for words in STRAYS if words in text]


def show_founding(packet):
    """Ask, as the first one would, for its founding in full at the next waking."""
    write_json(packet / "shelf.json", {
        "placements": {}, "notes": {}, "show_next": [], "show_founding": True,
        "show_versions": [], "note_placements": {}, "show_notes": []})


# ---- the selection itself --------------------------------------------------

def test_the_first_one_reads_its_own_transcript_in_either_layout(attend, data_dir, kept):
    strays(data_dir)
    assert attend.founding_transcript("first") == data_dir / kept


def test_in_its_folder_the_first_one_reads_the_newest_there_and_nothing_flat(attend, data_dir,
                                                                           kept):
    strays(data_dir)
    if kept.startswith("transcripts/first/"):
        newer = data_dir / "transcripts" / "first" / "founding-2026-10-22T09-00-00Z.md"
        write(newer, "A LATER FOUNDING OF ITS OWN\n")
        assert attend.founding_transcript("first") == newer
    else:  # flat, the newer flat file is passed over for the one by name
        assert attend.founding_transcript("first") == data_dir / "transcripts" / FIRST_FOUNDING


def test_with_its_pinned_file_missing_the_first_one_has_none_and_nothing_stands_in(
        attend, data_dir):
    strays(data_dir)
    (data_dir / "transcripts" / FIRST_FOUNDING).unlink()
    assert attend.founding_transcript("first") is None


def test_a_new_agent_reads_only_its_own_folder(attend, data_dir, kept):
    strays(data_dir)
    assert attend.founding_transcript("second") == data_dir / SECOND
    # one with no folder has none: not the first one's, and nothing left flat
    assert attend.founding_transcript("third") is None
    write(data_dir / "transcripts" / "third" / "notes.md", "NOT A FOUNDING\n")
    assert attend.founding_transcript("third") is None


# ---- the first one's reading ------------------------------------------------

def test_the_first_one_s_reading_is_byte_for_byte_what_it_read_before(
        founder, wake, attend, room, data_dir, kept):
    """As test_rooms_reading holds it, "as it reads now", with the strays beside it."""
    strays(data_dir)
    a_small_world(room)
    answer = post(founder, "/letters", content_type="multipart/form-data", data={
        "letter": "The lake was grey this morning, and then it was not.\n\nI am asking.",
        "thing": ["cold hands", "", "a heron on the far bank"],
        "errand": ERRAND, "proposes": "1"})
    assert answer.status_code == 302
    assert fingerprint_of_reading(wake()) == READING_NOW


def test_its_founding_shown_in_full_is_its_own_and_no_other(wake, packet, data_dir, kept):
    strays(data_dir)
    show_founding(packet)
    turn = wake()
    assert FOUNDING_TRANSCRIPT.rstrip() in turn.shown
    assert none_of_the_strays_in(json.dumps(turn.asked, ensure_ascii=False, default=str))


def test_read_founding_gives_its_own_and_no_other(longer, world, data_dir, kept):
    strays(data_dir)
    turn = longer(look(("read_founding", {})), "I have read it.")
    (said,) = turn.given
    assert said.endswith("\n\n" + FOUNDING_TRANSCRIPT.rstrip())
    assert none_of_the_strays_in(said)


def test_with_its_pinned_file_missing_read_founding_finds_nothing(longer, world, data_dir):
    strays(data_dir)
    (data_dir / "transcripts" / FIRST_FOUNDING).unlink()
    assert longer(look(("read_founding", {})), "").given == [NOT_FOUND]


# ---- a copy, and a backup ----------------------------------------------------

def test_a_copy_holds_its_own_transcript_and_no_other(founder, data_dir, kept):
    strays(data_dir)
    _, bundle = taken(founder)
    assert [name for name in bundle.namelist() if name.startswith("transcripts/")] == [kept]
    assert bundle.read(kept) == (data_dir / kept).read_bytes()
    assert bundle.read(kept).decode("utf-8").splitlines() == FOUNDING_TRANSCRIPT.splitlines()
    for name in bundle.namelist():
        assert none_of_the_strays_in(bundle.read(name).decode("utf-8", "replace")), name


def test_with_its_pinned_file_missing_a_copy_holds_no_transcript(founder, data_dir):
    strays(data_dir)
    (data_dir / "transcripts" / FIRST_FOUNDING).unlink()
    _, bundle = taken(founder)
    assert not [name for name in bundle.namelist() if name.startswith("transcripts")]


def test_a_backup_holds_every_transcript_and_every_folder_of_them(hearth, bucket, data_dir,
                                                                 clock, kept):
    strays(data_dir)
    hearth.back_up(clock.at)
    with bucket.only as bundle:
        held = sorted(member.name for member in bundle.getmembers()
                      if member.isfile() and member.name.startswith("transcripts/"))
        assert held == sorted([kept, SECOND, FLAT])
        for name in held:
            assert bundle.extractfile(name).read() == (data_dir / name).read_bytes()


# ---- the founding session ------------------------------------------------------

def test_the_founding_session_refuses_without_data_dir(tmp_path):
    environment = {key: value for key, value in os.environ.items() if key != "DATA_DIR"}
    environment["ANTHROPIC_API_KEY"] = "not-a-key"
    ran = subprocess.run([sys.executable, str(REPO / "founding_session.py"), "second"],
                         cwd=tmp_path, env=environment, capture_output=True, text=True,
                         stdin=subprocess.DEVNULL)
    assert ran.returncode == 1
    assert ran.stdout.startswith("refused: DATA_DIR is not set.")
    assert list(tmp_path.iterdir()) == []  # not a folder made, let alone a transcript


def test_the_founding_session_refuses_without_an_agent(env, monkeypatch, capsys, data_dir):
    session = load("founding_session")
    monkeypatch.setattr(sys, "argv", ["founding_session.py"])
    with pytest.raises(SystemExit) as stopped:
        session.main()
    assert stopped.value.code == 1
    assert capsys.readouterr().out.startswith("refused: say whose founding this is")
    assert not (data_dir / "transcripts" / "second").exists()


def test_the_founding_session_writes_into_the_agent_s_own_folder(env, monkeypatch, data_dir):
    session = load("founding_session")
    before = sorted(path.name for path in (REPO / "transcripts").rglob("*"))
    monkeypatch.chdir(REPO)  # where its required reading is
    monkeypatch.setattr(session, "Anthropic", Turn("I am here.").client)
    monkeypatch.setattr(sys, "argv", ["founding_session.py", "second"])
    monkeypatch.setattr("builtins.input", lambda *_: (_ for _ in ()).throw(EOFError))
    session.main()

    (written,) = (data_dir / "transcripts" / "second").glob("founding-*.md")
    assert "I am here." in written.read_text(encoding="utf-8")
    assert sorted(path.name for path in (REPO / "transcripts").rglob("*")) == before
    # and it is the one the new agent's wakings read, and never the first one's
    attend = load("attend")
    assert attend.founding_transcript("second") == written
    assert attend.founding_transcript("first") == data_dir / "transcripts" / FIRST_FOUNDING


# ---- a founding is never held twice ------------------------------------------

def everything_under(data_dir):
    return {path.relative_to(data_dir).as_posix(): path.read_bytes()
            for path in data_dir.rglob("*") if path.is_file()}


def refused(monkeypatch, capsys, data_dir, agent):
    """Run the session for an agent and hold that it refused: no model asked, nothing written."""
    session = load("founding_session")
    before = everything_under(data_dir)
    folders = sorted(path for path in data_dir.rglob("*") if path.is_dir())
    turn = Turn("I should never have been asked.")
    monkeypatch.chdir(REPO)
    monkeypatch.setattr(session, "Anthropic", turn.client)
    monkeypatch.setattr(sys, "argv", ["founding_session.py", agent])
    monkeypatch.setattr("builtins.input", lambda *_: (_ for _ in ()).throw(EOFError))
    with pytest.raises(SystemExit) as stopped:
        session.main()
    assert stopped.value.code == 1
    assert turn.asked == []
    assert everything_under(data_dir) == before
    assert sorted(path for path in data_dir.rglob("*") if path.is_dir()) == folders
    said = capsys.readouterr().out
    assert said.startswith("refused: %s already has a founding (" % agent)
    return said


def test_the_session_names_the_same_pinned_file_the_waking_reads(attend):
    session = load("founding_session")
    assert session.FIRST_FOUNDING == attend.FIRST_FOUNDING


def test_the_session_refuses_an_agent_with_a_transcript_in_its_folder(env, monkeypatch, capsys,
                                                                     data_dir):
    strays(data_dir)
    assert SECOND in refused(monkeypatch, capsys, data_dir, "second")


def test_the_session_refuses_an_agent_with_a_packet(env, monkeypatch, capsys, data_dir):
    write(data_dir / "packets" / "second" / "self.md", "# The second one\n")
    assert "packets/second" in refused(monkeypatch, capsys, data_dir, "second")


def test_the_session_refuses_the_first_one_by_its_transcript(env, monkeypatch, capsys, data_dir,
                                                             kept):
    shutil.rmtree(data_dir / "packets" / "first")  # so the transcript alone refuses it
    assert kept in refused(monkeypatch, capsys, data_dir, "first")


def test_the_session_refuses_the_first_one_by_its_packet(env, monkeypatch, capsys, data_dir):
    (data_dir / "transcripts" / FIRST_FOUNDING).unlink()
    assert "packets/first" in refused(monkeypatch, capsys, data_dir, "first")


def test_another_agent_s_flat_file_or_a_stray_file_founds_no_one(env, monkeypatch, data_dir):
    """Only a founding of its own refuses it: a flat file, or anything not a founding, does not."""
    write(data_dir / FLAT, FLAT_WORDS + "\n")
    write(data_dir / "transcripts" / "second" / "notes.md", "NOT A FOUNDING\n")
    session = load("founding_session")
    assert session.founded_already(data_dir, "second") is None
