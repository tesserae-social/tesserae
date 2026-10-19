"""The one-time amending of the commons' existing lines, on the host.

Only the protected words change, nothing else of any file does, and one line
says in events.md that some words were amended - which, and how many, it does
not say. By itself it only shows what it would do. The names are made up.
"""

import importlib
import io
import sys

import pytest

from conftest import write

LIST = "Quillon => the founder\nVarrowmere\n"

HEARTBEATS = (
    "- 2026-10-14T11-55-25Z · the first one · Thirty-first waking; read Quillon's letter; "
    "resting.\n"
    "- 2026-10-15T11-56-29Z · the first one · Thirty-second waking; Quillon heading to "
    "Varrowmere; two days until the seal.\n"
    "- 2026-10-16T11-57-17Z · the first one · Thirty-third waking; holding the threshold open.\n")
EVENTS = "2026-10-17 · letter · the founder wrote a letter at night\r\n"


@pytest.fixture
def amend(env, data_dir):
    sys.modules.pop("private_words", None)
    sys.modules.pop("amend_public_words", None)
    return importlib.import_module("amend_public_words")


def run(amend, data_dir, *argv):
    out = io.StringIO()
    assert amend.main(list(argv), data=data_dir, out=out) == 0
    return out.getvalue()


@pytest.fixture
def world(data_dir, commons):
    write(data_dir / "private-words.txt", LIST)
    (commons / "heartbeats.md").write_bytes(HEARTBEATS.encode("utf-8"))
    (commons / "events.md").write_bytes(EVENTS.encode("utf-8"))
    return commons


def test_a_dry_run_shows_the_diff_and_writes_nothing(amend, data_dir, world):
    said = run(amend, data_dir)
    assert ("+- 2026-10-15T11-56-29Z · the first one · Thirty-second waking; the founder "
            "heading; two days until the seal.\n") in said
    assert ("+- 2026-10-14T11-55-25Z · the first one · Thirty-first waking; "
            "read the founder's letter") in said
    assert " · event · some heartbeat words were amended to keep private names private" in said
    assert "Thirty-third" not in said  # a line with nothing in it is not in the diff
    assert "A dry run: nothing was written." in said
    assert (world / "heartbeats.md").read_bytes() == HEARTBEATS.encode("utf-8")
    assert (world / "events.md").read_bytes() == EVENTS.encode("utf-8")


def test_applied_it_changes_only_the_protected_words(amend, data_dir, world):
    run(amend, data_dir, "--apply")
    assert (world / "heartbeats.md").read_bytes() == HEARTBEATS.replace(
        "Quillon heading to Varrowmere", "the founder heading").replace(
        "Quillon's", "the founder's").encode("utf-8")


def test_applied_it_says_so_in_one_line_with_no_name_and_no_count(amend, data_dir, world):
    run(amend, data_dir, "--apply")
    events = (world / "events.md").read_bytes().decode("utf-8")
    assert events.startswith(EVENTS)  # what was there is as it was, its line ends and all
    added = events[len(EVENTS):]
    day = added[:10]
    assert added == (day + " · event · some heartbeat words were amended to keep private "
                     "names private\r\n")


def test_a_second_run_changes_nothing_at_all(amend, data_dir, world):
    run(amend, data_dir, "--apply")
    before = {name: (world / name).read_bytes() for name in ("heartbeats.md", "events.md")}
    assert "Nothing to do." in run(amend, data_dir, "--apply")
    assert before == {name: (world / name).read_bytes() for name in before}


def test_every_file_of_the_commons_kept_as_lines_is_amended(amend, data_dir, world):
    for name in ("members.md", "bench.md", "offerings.md", "bonds.md"):
        write(world / name, "- 2026-10-15 · Quillon · kept\n")
    run(amend, data_dir, "--apply")
    for name in ("members.md", "bench.md", "offerings.md", "bonds.md"):
        assert (world / name).read_text(encoding="utf-8") == "- 2026-10-15 · the founder · kept\n"


def test_what_is_signed_is_not_touched(amend, data_dir, world):
    signed = write(world / "bonds" / "founder-first.json", '{"text": "Quillon"}\n')
    words = write(world / "offerings" / "one.md", "Quillon\n")
    run(amend, data_dir, "--apply")
    assert signed.read_text(encoding="utf-8") == '{"text": "Quillon"}\n'
    assert words.read_text(encoding="utf-8") == "Quillon\n"


def test_a_mark_at_the_start_of_a_file_is_kept(amend, data_dir, world):
    (world / "heartbeats.md").write_bytes(b"\xef\xbb\xbf" + HEARTBEATS.encode("utf-8"))
    run(amend, data_dir, "--apply")
    assert (world / "heartbeats.md").read_bytes().startswith(b"\xef\xbb\xbf- 2026-10-14")


def test_with_no_list_it_does_nothing(amend, data_dir, commons):
    (commons / "heartbeats.md").write_bytes(HEARTBEATS.encode("utf-8"))
    assert "Nothing to do." in run(amend, data_dir, "--apply")
    assert (commons / "heartbeats.md").read_bytes() == HEARTBEATS.encode("utf-8")
    assert not (commons / "events.md").exists() or "amended" not in (
        commons / "events.md").read_text(encoding="utf-8")
