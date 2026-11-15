"""What the backup holds, how it lets old ones go, and files rewritten whole.

The founder's request of 15 November 2026 (audit-inventory-15-nov.md, c1, c3,
c4 and c5):

  * a backup holds the knocks with their notes and replies, the weekly
    questions, and the posts the keeper took down from the board;
  * before the oldest backups are deleted, the new one is checked whole: it
    opens with the key, it holds something of packets/first and of the commons,
    and it is not less than half the size of the last whole one. One that fails
    is kept, nothing is deleted, and /tides says so until a whole one is taken;
  * the board's file, the keeper's record of what was taken down, and the
    commons' lines (heartbeats.md, where a line is rewritten) are written beside
    themselves and put in place whole; one that is there and can't be read is
    never taken for an empty one: nothing is written to it, and /tides says so.
"""

import html
from datetime import timedelta

import pytest
from cryptography.fernet import Fernet

import safe_write

from conftest import NOW, block, page, post, write
from test_backup import KEY, bucket, log_lines  # noqa: F401 - a fixture
from test_board import signed_in
from test_export import a_whole_world
from test_kept_words import world  # noqa: F401 - a fixture
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

NOT_WHOLE = "backed up, nothing deleted"


def take(hearth, days):
    return [hearth.back_up(NOW + timedelta(days=day)) for day in days]


def tides_said(founder):
    return " ".join(html.unescape(page(founder.get("/tides"))).split())


# ---- what a backup holds ---------------------------------------------------------

def test_a_backup_holds_the_knocks_the_weekly_questions_and_what_was_taken_down(
        hearth, bucket, packet, commons, data_dir):  # noqa: F811
    a_whole_world(packet, commons)
    write(data_dir / "knocks" / "hazel--second.json", '{"note": "A FAKE NOTE."}\n')
    write(data_dir / "knocks" / "history" / "hazel--second-1.json", '{"note": "AN OLD ONE."}\n')
    write(data_dir / "weekly-questions.json", '{"weeks": {}}\n')
    (data_dir / "board-removed.json").write_bytes(b'[{"from": "1/1"}]\n')
    said = hearth.back_up(NOW)
    assert " · backed up · " in said and said.endswith("kept 1")
    with bucket.only as bundle:
        names = set(bundle.getnames())
        assert {"knocks/hazel--second.json", "knocks/history/hazel--second-1.json",
                "weekly-questions.json", "board-removed.json"} <= names
        assert bundle.extractfile("board-removed.json").read() == b'[{"from": "1/1"}]\n'


def test_with_none_of_them_the_backup_holds_what_it_did(hearth, bucket, packet, commons):  # noqa: F811
    a_whole_world(packet, commons)
    hearth.back_up(NOW)
    with bucket.only as bundle:
        assert not [name for name in bundle.getnames()
                    if name.startswith(("knocks", "weekly-questions", "board-removed"))]


# ---- letting the old ones go -----------------------------------------------------

def test_a_backup_that_is_not_whole_deletes_nothing_and_tides_says_so(
        hearth, bucket, packet, commons, data_dir):  # noqa: F811
    a_whole_world(packet, commons)
    take(hearth, range(30))
    assert len(bucket.keys) == 30 and bucket.deleted == []
    assert hearth.tides_troubles() == []
    # the volume comes up empty: no packet, no commons
    import shutil
    shutil.rmtree(packet)
    shutil.rmtree(commons)
    said = take(hearth, [30])[0]
    assert " · %s · " % NOT_WHOLE in said
    assert "it held nothing from packets/first" in said and said.endswith("kept 31")
    assert bucket.deleted == [] and len(bucket.keys) == 31
    shown = " ".join(hearth.tides_troubles())
    assert ("did not look whole: it held nothing from packets/first. It was kept, and no older "
            "backup was deleted.") in shown
    # the backups page goes on saying when the last whole one was
    assert hearth.last_backup()[1] == 30
    # a second empty one deletes nothing either
    take(hearth, [31])
    assert bucket.deleted == [] and len(bucket.keys) == 32
    # once a whole one is taken, the oldest go again, and /tides says nothing more
    a_whole_world(packet, commons)
    said = take(hearth, [32])[0]
    assert " · backed up · " in said and said.endswith("kept 30")
    assert len(bucket.deleted) == 3
    assert hearth.tides_troubles() == []


def test_one_much_smaller_than_the_last_whole_one_deletes_nothing(
        hearth, bucket, packet, commons, data_dir):  # noqa: F811
    a_whole_world(packet, commons)
    write(packet / "memory" / "a-long-one.md", "".join(
        "%06d %s\n" % (n, Fernet.generate_key().decode("ascii")) for n in range(4000)))
    take(hearth, range(30))
    (packet / "memory" / "a-long-one.md").unlink()
    said = take(hearth, [30])[0]
    assert "it was less than half the size of the last whole one" in said
    assert bucket.deleted == []


def test_one_that_does_not_open_with_the_key_is_not_whole(hearth, packet, commons):
    other = Fernet.generate_key().decode("ascii")
    assert hearth.not_whole(Fernet(other).encrypt(b"not a tar.gz"), KEY) == \
        "it did not open with the key"
    assert hearth.not_whole(b"nothing at all", KEY) == "it did not open with the key"


def test_a_line_the_log_cannot_read_is_stepped_over(hearth, data_dir):
    write(data_dir / "backup.log", "2026-10-14T13-00-00Z · backed up · many bytes · kept 1\n"
          "not a line\n2026-10-15T13-00-00Z · %s · 10 bytes · why · kept 2\n" % NOT_WHOLE)
    assert hearth.last_whole_size() is None
    assert "did not look whole: why." in hearth.backup_not_whole_note()


# ---- written whole ---------------------------------------------------------------

def test_a_write_cut_short_leaves_the_file_as_it_was(tmp_path, monkeypatch):
    where = tmp_path / "commons" / "board.json"
    safe_write.write_text(where, "as it was\n")

    def crash(*a):
        raise OSError("the machine stopped")
    monkeypatch.setattr(safe_write.os, "replace", crash)
    with pytest.raises(OSError):
        safe_write.write_text(where, "as it would have become\n")
    assert where.read_text(encoding="utf-8") == "as it was\n"
    assert [path.name for path in where.parent.iterdir()] == ["board.json"]


def test_the_board_is_written_whole_and_leaves_nothing_beside_it(hearth, data_dir):
    import board
    board.start(board.PLACE, "alder", "Lanterns", "Hello.", "2026-11-13")
    assert [path.name for path in (data_dir / "commons").glob("*board*")] == ["board.json"]
    assert board.read()["topics"][0]["subject"] == "Lanterns"


def test_a_board_that_cannot_be_read_is_not_written_to_and_tides_says_so(
        hearth, data_dir, monkeypatch, founder):
    import board
    board.start(board.PLACE, "alder", "Lanterns", "Hello.", "2026-11-13")
    torn = (data_dir / "commons" / "board.json").read_bytes()[:40]
    (data_dir / "commons" / "board.json").write_bytes(torn)
    with pytest.raises(board.Unreadable):
        board.add("1", "alder", "Again.", "2026-11-13")
    with pytest.raises(board.Unreadable):
        board.start(board.CONVERSATION, "alder", "Another", "Hello.", "2026-11-13")
    with pytest.raises(board.Unreadable):
        board.take_down("1", 1, "2026-11-13", keeper=True)
    assert (data_dir / "commons" / "board.json").read_bytes() == torn
    assert not (data_dir / "board-removed.json").exists()
    assert board.unreadable() == ["board.json"]
    assert "The board's file (commons/board.json) is there and can't be read." in \
        tides_said(founder)
    # a member is told, and no screened try is spent on it
    monkeypatch.setattr(hearth, "in_good_spirit", lambda line: pytest.fail("screened"))
    birch = signed_in(hearth, monkeypatch, "birch")
    said = " ".join(html.unescape(page(post(birch, "/board/conversation",
                              data={"subject": "Hello", "words": "Hello."}))).split())
    assert "The board can't be written to just now; nothing was posted." in said
    assert (data_dir / "commons" / "board.json").read_bytes() == torn


def test_a_record_of_what_was_taken_down_that_cannot_be_read_stops_the_taking_down(
        hearth, data_dir, founder):
    import board
    board.start(board.PLACE, "alder", "Lanterns", "Hello.", "2026-11-13")
    before = (data_dir / "commons" / "board.json").read_bytes()
    (data_dir / "board-removed.json").write_text("[{\"from\": ", encoding="utf-8")
    with pytest.raises(board.Unreadable):
        board.take_down("1", 1, "2026-11-13", keeper=True)
    assert (data_dir / "commons" / "board.json").read_bytes() == before  # still standing
    assert (data_dir / "board-removed.json").read_text(encoding="utf-8") == "[{\"from\": "
    # one's own may still be taken down: it keeps nothing outside the commons
    assert board.take_down("1", 1, "2026-11-13", by="alder")
    assert "The record of posts you took down (board-removed.json) is there" in \
        tides_said(founder)


def test_an_agent_is_told_a_board_that_cannot_be_read_took_nothing(world):  # noqa: F811
    world.wake(block("BOARD", "section: the place\nsubject: Winter\nHello from the second one."))
    board_file = world.data / "commons" / "board.json"
    board_file.write_text('{"topics": [', encoding="utf-8")
    world.wake(block("BOARD", "section: the place\nsubject: Spring\nHello again."))
    assert board_file.read_text(encoding="utf-8") == '{"topics": ['
    assert world.module.BOARD_REFUSED["unreadable"] in world.wake().shown


# ---- the commons' lines ----------------------------------------------------------

def test_lines_that_cannot_be_read_are_never_rewritten_and_tides_says_so(world, founder):  # noqa: F811
    world.wake(block("COMMONS_LINE", "A quiet day by the water."))
    heartbeats = world.data / "commons" / "heartbeats.md"
    own = next(line for line in heartbeats.read_text(encoding="utf-8").splitlines()
               if "the second one · A quiet day" in line)
    stamp = own.split(" · ")[0][2:]
    broken = heartbeats.read_bytes() + b"\xff\xfe a line that is not UTF-8\n"
    heartbeats.write_bytes(broken)
    world.wake(block("REWRITE", "%s\nA quieter day." % stamp))
    after = heartbeats.read_bytes()
    assert after.startswith(broken)  # nothing rewritten; only the waking's own line added
    assert b"A quieter day" not in after
    assert world.module.REWRITE_REFUSED["unreadable"] in world.wake().shown
    assert "The commons' lines (commons/heartbeats.md) are there and can't be read." in \
        tides_said(founder)


def test_a_rewrite_is_written_whole_and_leaves_nothing_beside_it(world):  # noqa: F811
    world.wake(block("COMMONS_LINE", "A quiet day by the water."))
    heartbeats = world.data / "commons" / "heartbeats.md"
    own = next(line for line in heartbeats.read_text(encoding="utf-8").splitlines()
               if "the second one · A quiet day" in line)
    world.wake(block("REWRITE", "%s\nA quieter day." % own.split(" · ")[0][2:]))
    assert "A quieter day" in heartbeats.read_text(encoding="utf-8")
    assert [path.name for path in heartbeats.parent.glob("*heartbeats*")] == ["heartbeats.md"]
