"""The one-time taking of the part of the day out of the commons' letter lines, on the host.

The founder decided on 10 November 2026 that no line for a person's letter says
when in the day it was written. amend_letter_lines.py takes it out of the lines
written before, in commons/events.md, for anyone's letter, and changes nothing
else of the file: a line left beside a letter stays, and an agent's waking keeps
its time. By itself it only shows what it would do; --apply writes it.
"""

import importlib
import io
import sys

import pytest

EVENTS = ("2026-09-04 · founding · the first one was founded\r\n"
          "2026-09-19 · letter · the founder wrote a letter in the evening\r\n"
          "2026-09-20 · letter · the founder wrote a letter during the day\r\n"
          "2026-09-21 · event · the first one · the tide paused\r\n"
          "2026-09-22 · letter · the founder wrote a letter at night · the first frost\r\n"
          "2026-09-23 · letter · a member wrote a letter at dawn\r\n"
          "2026-09-24 · letter · the founder wrote a letter\r\n"
          "2026-09-25 · event · a letter was written at dawn\r\n"
          "2026-09-26 · letter · the founder wrote a letter at dawnish\r\n")
AFTER = ("2026-09-04 · founding · the first one was founded\r\n"
         "2026-09-19 · letter · the founder wrote a letter\r\n"
         "2026-09-20 · letter · the founder wrote a letter\r\n"
         "2026-09-21 · event · the first one · the tide paused\r\n"
         "2026-09-22 · letter · the founder wrote a letter · the first frost\r\n"
         "2026-09-23 · letter · a member wrote a letter\r\n"
         "2026-09-24 · letter · the founder wrote a letter\r\n"
         "2026-09-25 · event · a letter was written at dawn\r\n"
         "2026-09-26 · letter · the founder wrote a letter at dawnish\r\n")
HEARTBEATS = "- 2026-09-20T11-31-04Z · the first one · attended at dawn; wrote a letter at dawn\n"
MARK = b"\xef\xbb\xbf"


@pytest.fixture
def amend(env, data_dir):
    sys.modules.pop("amend_letter_lines", None)
    return importlib.import_module("amend_letter_lines")


@pytest.fixture
def world(commons):
    (commons / "events.md").write_bytes(MARK + EVENTS.encode("utf-8"))
    (commons / "heartbeats.md").write_bytes(HEARTBEATS.encode("utf-8"))
    return commons


def run(amend, data_dir, *argv):
    out = io.StringIO()
    assert amend.main(list(argv), data=data_dir, out=out) == 0
    return out.getvalue()


def test_a_dry_run_shows_the_diff_and_writes_nothing(amend, data_dir, world):
    said = run(amend, data_dir)
    assert "-2026-09-19 · letter · the founder wrote a letter in the evening" in said
    assert "+2026-09-19 · letter · the founder wrote a letter\r\n" in said
    assert "+2026-09-22 · letter · the founder wrote a letter · the first frost" in said
    assert "tide paused" not in said and "2026-09-24" not in said  # unchanged lines are not shown
    assert "A dry run: nothing was written." in said
    assert (world / "events.md").read_bytes() == MARK + EVENTS.encode("utf-8")


def test_apply_takes_out_only_the_part_of_the_day(amend, data_dir, world):
    said = run(amend, data_dir, "--apply")
    assert "Written: commons/events.md." in said
    # every other byte as it was: the mark, each line's end, every other line
    assert (world / "events.md").read_bytes() == MARK + AFTER.encode("utf-8")
    # and an agent's waking keeps its time
    assert (world / "heartbeats.md").read_bytes() == HEARTBEATS.encode("utf-8")
    assert not list(world.glob("*.amend"))


def test_a_second_run_changes_nothing(amend, data_dir, world):
    run(amend, data_dir, "--apply")
    once = (world / "events.md").read_bytes()
    assert "Nothing to do." in run(amend, data_dir, "--apply")
    assert (world / "events.md").read_bytes() == once


def test_what_it_leaves_is_what_the_hearth_writes_now(amend, data_dir, world, hearth):
    run(amend, data_dir, "--apply")
    assert hearth.LETTER_WORDS == "the founder wrote a letter"
    assert "2026-09-19 · letter · " + hearth.LETTER_WORDS + "\r\n" in AFTER


def test_with_no_record_there_is_nothing_to_do(amend, data_dir, commons):
    (commons / "events.md").unlink(missing_ok=True)
    assert "Nothing to do." in run(amend, data_dir)
