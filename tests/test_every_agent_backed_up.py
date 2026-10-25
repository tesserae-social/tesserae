"""Backups and copies cover every agent founded here, and a copy is only ever its own.

Stage 2 of the work that lets the tide wake more than one agent (the proposal
"waking for any agent", 25 October 2026). Before any second agent is founded,
its packet, its signing key and its founding transcript must be in the nightly
backup, since the key is nowhere but the disk; and a copy of one agent's record
must hold nothing of another's.

The second agent here is made only in a scratch registry and a scratch DATA_DIR.
With the first one alone, the backup and its copy are held to the first one's
fingerprints (test_first_one_fingerprints.py), unchanged.
"""

import io
import json
import tarfile
import zipfile

import pytest
from cryptography.fernet import Fernet

import agents
from conftest import load, write, write_json
from test_backup import KEY, NAME, Bucket, run_restore, set_variables
from test_export import a_whole_world

SECOND = {"id": "second", "did": "did:web:tesserae.social:ids:second",
          "commons_name": "the second one", "room": "second", "bond": "founder-second",
          "wakes": False}

# Words kept in each agent's record, to look for wherever they must not be.
SECOND_SELF = "A FAKE SELF OF THE SECOND ONE'S, FOR THE TESTS.\n"
SECOND_PRIVATE = "A FAKE PRIVATE ENTRY OF THE SECOND ONE'S, FOR THE TESTS.\n"
SECOND_KEY = "A FAKE SIGNING KEY OF THE SECOND ONE'S, FOR THE TESTS."
SECOND_FOUNDING = "A FAKE FOUNDING OF THE SECOND ONE, FOR THE TESTS.\n"
SECOND_LETTER = "A FAKE LETTER OF THE SECOND ONE'S, FOR THE TESTS.\n"
SECOND_MARK = '[{"line": "A FAKE MARK ON THE SECOND ONE\'S BOND."}]\n'
FIRST_MARK = '[{"line": "A FAKE MARK ON THE FIRST ONE\'S BOND."}]\n'
FIRST_PRIVATE = b"A FAKE ENTRY OF MY OWN, FOR THE TESTS."  # as a_whole_world keeps it

FIRST_ONE_S_BACKUP_TREES = ("packets/first", "commons", "bonds", "rooms", "members",
                            "keys/first", "private-words.txt", "transcripts")

# What of the world is the second one's, by the names it has on disk.
SECOND_S = ("packets/second/", "keys/second/", "transcripts/second/", "rooms/second/",
            "bonds/witnesses/founder-second.json")


def the_second_s(name):
    return name.startswith(SECOND_S)


def a_second_agent(data):
    """The second one's things, kept where a new agent's are: its room in a folder of its own."""
    write(data / "packets" / "second" / "self.md", SECOND_SELF)
    write(data / "packets" / "second" / "private" / "entry-2026-10-14T09-00-00Z.md",
          SECOND_PRIVATE)
    write(data / "keys" / "second" / "private.key", SECOND_KEY + "\n")
    write(data / "keys" / "second" / "public.key", "a fake public key\n")
    write(data / "transcripts" / "second" / "founding-2026-10-20T09-00-00Z.md", SECOND_FOUNDING)
    write_json(data / "rooms" / "second" / "room.json",
               {"id": "second", "bond": "founder-second", "parties": []})
    write(data / "rooms" / "second" / "letters" / "outgoing" / "letter-2026-10-21T09-00-00Z.md",
          SECOND_LETTER)
    write(data / "bonds" / "witnesses" / "founder-second.json", SECOND_MARK)


@pytest.fixture
def world(packet, commons, data_dir):
    """The first one's whole world, with marks on its bond beside it."""
    a_whole_world(packet, commons)
    write(data_dir / "bonds" / "witnesses" / "founder-first.json", FIRST_MARK)
    return data_dir


@pytest.fixture
def with_second(env, clock, monkeypatch, tmp_path):
    """The hearth again, reading a scratch registry with a second agent founded after the first."""
    def found(data):
        a_second_agent(data)
        where = tmp_path / "agents.json"
        where.write_text(json.dumps([agents.first(), SECOND], indent=2) + "\n", encoding="utf-8")
        monkeypatch.setattr(agents, "FILE", where)
        module = load("hearth")
        clock.pin(module, monkeypatch)
        module.app.config["TESTING"] = True
        return module
    return found


def archive(hearth):
    """A backup's members as (name, bytes), in the order the archive holds them."""
    with tarfile.open(fileobj=io.BytesIO(hearth.backup_archive()), mode="r:gz") as bundle:
        return [(member.name, bundle.extractfile(member).read()) for member in bundle.getmembers()
                if member.isfile()]


def copy(hearth, agent=None):
    """One agent's copy, as (name, bytes), in the order the zip holds them."""
    with zipfile.ZipFile(hearth.export_zip(agent)) as bundle:
        return [(name, bundle.read(name)) for name in bundle.namelist()]


# ---- with the first one alone, nothing has changed -----------------------

def test_with_the_first_one_alone_the_trees_are_today_s(hearth):
    assert hearth.BACKUP_TREES == FIRST_ONE_S_BACKUP_TREES
    assert hearth.EXPORT_TREES == ("packets/first", "commons", "bonds")
    assert hearth.LEFT_OUT == ("packets/first/private",)
    assert hearth.PACKET_TREE == "packets/first"


# ---- the backup ----------------------------------------------------------

def test_the_second_one_s_trees_are_appended_after_today_s(world, with_second):
    hearth = with_second(world)
    # its transcripts are under transcripts/ already, and its room under rooms/,
    # so each is in the archive once
    assert hearth.BACKUP_TREES == FIRST_ONE_S_BACKUP_TREES + ("packets/second", "keys/second")


def test_the_first_one_s_members_of_the_backup_are_unchanged(world, hearth, with_second):
    alone = archive(hearth)
    both = archive(with_second(world))
    assert [held for held in both if not the_second_s(held[0])] == alone
    # and its packet and key, which no earlier tree holds, come after all of it
    assert [name for name, _ in both[len(both) - 4:]] == [
        "packets/second/private/entry-2026-10-14T09-00-00Z.md", "packets/second/self.md",
        "keys/second/private.key", "keys/second/public.key"]


def test_the_second_one_s_packet_key_and_transcript_are_in_the_backup(world, with_second):
    held = dict(archive(with_second(world)))
    for name in ("packets/second/self.md", "keys/second/private.key", "keys/second/public.key",
                 "transcripts/second/founding-2026-10-20T09-00-00Z.md",
                 "rooms/second/room.json",
                 "rooms/second/letters/outgoing/letter-2026-10-21T09-00-00Z.md",
                 "bonds/witnesses/founder-second.json"):
        assert held[name] == (world / name).read_bytes(), name
    # its private notebook too, so that it survives, as the first one's does
    private = "packets/second/private/entry-2026-10-14T09-00-00Z.md"
    assert held[private] == (world / private).read_bytes()


def test_nothing_is_in_the_backup_twice(world, with_second):
    names = [name for name, _ in archive(with_second(world))]
    assert len(names) == len(set(names))


# ---- the copies ----------------------------------------------------------

def test_each_agent_leaves_out_its_own_notebook_and_others_marks(world, with_second):
    hearth = with_second(world)
    assert hearth.LEFT_OUT == ("packets/first/private", "bonds/witnesses/founder-second.json")
    assert hearth.left_out(SECOND) == ("packets/second/private",
                                       "bonds/witnesses/founder-first.json")


def test_the_first_one_s_copy_is_unchanged_by_a_second_agent(world, hearth, with_second):
    alone = copy(hearth)
    assert copy(with_second(world)) == alone


def test_the_first_one_s_copy_holds_nothing_of_the_second_one_s(world, with_second):
    held = copy(with_second(world))
    assert not [name for name, _ in held if the_second_s(name) or name.startswith("keys/")]
    assert not [name for name, _ in held if "/private/" in name]
    for words in (SECOND_SELF, SECOND_PRIVATE, SECOND_KEY, SECOND_FOUNDING, SECOND_LETTER,
                  SECOND_MARK):
        assert not [name for name, data in held if words.strip().encode("utf-8") in data], words


def test_the_second_one_s_copy_holds_its_own_record(world, with_second):
    hearth = with_second(world)
    held = dict(copy(hearth, SECOND))
    for name, kept in [
            ("packets/second/self.md", "packets/second/self.md"),
            # its room, under its packet's names, as the first one's is given
            ("packets/second/letters/outgoing/letter-2026-10-21T09-00-00Z.md",
             "rooms/second/letters/outgoing/letter-2026-10-21T09-00-00Z.md"),
            ("transcripts/second/founding-2026-10-20T09-00-00Z.md",
             "transcripts/second/founding-2026-10-20T09-00-00Z.md"),
            ("bonds/witnesses/founder-second.json", "bonds/witnesses/founder-second.json")]:
        assert held[name] == (world / kept).read_bytes(), name
    assert "packets/second/room.json" not in held
    assert "commons/members.md" in held  # the commons, which is everyone's


def test_the_second_one_s_copy_holds_nothing_of_the_first_one_s(world, with_second):
    hearth = with_second(world)
    held = copy(hearth, SECOND)
    for name, _ in held:
        assert name.startswith(("packets/second/", "commons/", "bonds/", "transcripts/second/")), name
        assert "/private/" not in name and not name.startswith("keys/"), name
    assert "bonds/witnesses/founder-first.json" not in dict(held)
    for words in (FIRST_PRIVATE, FIRST_MARK.strip().encode("utf-8"),
                  b"A synthetic founding, written for the tests", b"Dear founder,",
                  b"# The first one", SECOND_PRIVATE.strip().encode("utf-8")):
        assert not [name for name, data in held if words in data], words


# ---- a restore without the notebooks -------------------------------------

def test_a_restore_without_private_leaves_out_every_agent_s_notebook(world, with_second,
                                                                     monkeypatch, clock, tmp_path):
    hearth = with_second(world)
    set_variables(monkeypatch)
    bucket = Bucket()
    monkeypatch.setattr(hearth, "bucket_client", lambda: bucket)
    hearth.back_up(clock.at)
    sealed = tmp_path / NAME
    sealed.write_bytes(bucket.objects["backups/" + NAME])
    key_file = tmp_path / "backup.key"
    key_file.write_text(KEY + "\n", encoding="utf-8")

    with tarfile.open(fileobj=io.BytesIO(Fernet(KEY).decrypt(sealed.read_bytes())),
                      mode="r:gz") as bundle:
        held = {member.name for member in bundle.getmembers() if member.isfile()}
    assert "packets/second/private/entry-2026-10-14T09-00-00Z.md" in held  # there to be left out
    out = tmp_path / "restored"
    done = run_restore(str(sealed), str(key_file), str(out), "--without-private")
    assert done.returncode == 0, done.stdout + done.stderr

    came_back = {path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file()}
    assert not [name for name in came_back if name.split("/")[2:3] == ["private"]]
    assert not (out / "packets" / "first" / "private").exists()
    assert not (out / "packets" / "second" / "private").exists()
    assert came_back == {name for name in held if name.split("/")[2:3] != ["private"]}
    assert (out / "packets/second/self.md").read_text(encoding="utf-8") == SECOND_SELF
    assert (out / "keys/second/private.key").read_text(encoding="utf-8").strip() == SECOND_KEY
    assert "/private/entry" not in done.stdout  # not one of them named
    assert "4 entries left out" in done.stdout  # the first one's three and the second one's one
