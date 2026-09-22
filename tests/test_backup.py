"""The nightly backup: what is copied off the machine, what is done with it in
the bucket, what is written down, and what the founder is shown and handed.

The bucket is in memory here. Nothing in this file goes out: the S3 client the
hearth builds is replaced by a fake that keeps its objects in a dict, and the
key is a throwaway Fernet key cut when this module is imported. The one thing
run for real is the encryption itself, and restore_backup.py, which is given a
backup this hearth actually made and asked to open it.
"""

import io
import subprocess
import sys
import tarfile
from datetime import timedelta

import pytest
from cryptography.fernet import Fernet

from conftest import NOW, REPO, lines_of, no_threads, page, write
from test_export import a_whole_world, files_under

KEY = Fernet.generate_key().decode("ascii")

BUCKET = "a bucket for the tests and nothing else"

VARIABLES = ("BACKUP_KEY", "BUCKET_NAME", "AWS_ENDPOINT_URL_S3",
             "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")

STAMP = "2026-10-15T12-00-00Z"
NAME = "tesserae-%s.tar.gz.enc" % STAMP
KEPT_LINE = "%s · backed up · %%d bytes · kept %%d" % STAMP
UNCONFIGURED = "%s · not configured" % STAMP


class Stop(BaseException):
    """Stops the backup thread from outside. Not an Exception: it swallows those."""


class Gone(Exception):
    """What the fake bucket raises for a key that is not in it."""


class Body:
    """One object on its way out, handed over the way botocore hands one over."""

    def __init__(self, data):
        self.data = data
        self.asked = []

    def iter_chunks(self, size=8192):
        self.asked.append(size)
        for at in range(0, len(self.data), size):
            yield self.data[at:at + size]


class Bucket:
    """The bucket, in memory: the four calls the hearth makes, and no wire at all.

    It pages its listing ten at a time, small on purpose, so that a hearth that
    forgot to follow the continuation token would be caught here rather than at
    the thirty-first backup.
    """

    page = 10

    def __init__(self, name=BUCKET):
        self.name = name
        self.objects = {}
        self.deleted = []
        self.bodies = []

    def put_object(self, Bucket, Key, Body):
        assert Bucket == self.name
        self.objects[Key] = bytes(Body)
        return {}

    def list_objects_v2(self, Bucket, Prefix="", ContinuationToken=None):
        assert Bucket == self.name
        keys = sorted(key for key in self.objects if key.startswith(Prefix))
        start = int(ContinuationToken or 0)
        answer = {"Contents": [{"Key": key, "Size": len(self.objects[key])}
                               for key in keys[start:start + self.page]]}
        if start + self.page < len(keys):
            answer["IsTruncated"] = True
            answer["NextContinuationToken"] = str(start + self.page)
        return answer

    def delete_object(self, Bucket, Key):
        assert Bucket == self.name
        del self.objects[Key]
        self.deleted.append(Key)
        return {}

    def get_object(self, Bucket, Key):
        assert Bucket == self.name
        if Key not in self.objects:
            raise Gone(Key)
        body = Body(self.objects[Key])
        self.bodies.append(body)
        return {"Body": body}

    # ---- what the tests ask of it ----
    @property
    def keys(self):
        return sorted(self.objects)

    @property
    def only(self):
        """The one thing in it, decrypted and opened as a tar.gz."""
        [key] = self.keys
        return tarfile.open(fileobj=io.BytesIO(Fernet(KEY).decrypt(self.objects[key])),
                            mode="r:gz")


def set_variables(monkeypatch):
    """The key and the bucket, as flyctl secrets would set them."""
    monkeypatch.setenv("BACKUP_KEY", KEY)
    monkeypatch.setenv("BUCKET_NAME", BUCKET)
    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "https://storage.example.invalid")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "an access key for the tests")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "a secret for the tests")
    monkeypatch.delenv("AWS_REGION", raising=False)


@pytest.fixture
def bucket(hearth, monkeypatch):
    """A configured hearth, with the bucket in memory instead of on the wire."""
    set_variables(monkeypatch)
    fake = Bucket()
    monkeypatch.setattr(hearth, "bucket_client", lambda: fake)
    return fake


@pytest.fixture
def unconfigured(hearth, monkeypatch):
    """A hearth given nothing: no key, no bucket, and no client to be had."""
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)

    def refuse():
        raise AssertionError("an unconfigured hearth reached for the bucket")

    monkeypatch.setattr(hearth, "bucket_client", refuse)
    return hearth


def log_lines(hearth):
    return lines_of(hearth.BACKUP_LOG)


def files_now(where):
    return {path: path.read_bytes() for path in where.rglob("*") if path.is_file()}


# ---- what is in a backup -------------------------------------------------

def test_the_archive_holds_the_two_trees_whole(hearth, bucket, packet, commons, clock):
    a_whole_world(packet, commons)
    hearth.back_up(clock.at)

    with bucket.only as bundle:
        held = {member.name for member in bundle.getmembers() if member.isfile()}
        assert held == files_under(packet, "packets/first/") | files_under(commons, "commons/")
        # and what is in it is the file itself, byte for byte
        for name in ("packets/first/self.md", "commons/members.md"):
            assert bundle.extractfile(name).read() == (packet.parents[1] / name).read_bytes()


def test_nothing_outside_the_two_trees_is_in_the_archive(hearth, bucket, packet, commons,
                                                         data_dir, clock):
    a_whole_world(packet, commons)
    write(data_dir / ".env", "FOUNDER_PASSWORD_HASH=not the real one\n")
    write(data_dir / "bench-removed.md", "2026-10-09 · a line taken off\n")
    write(data_dir / "backup.log", "2026-10-14T13-00-00Z · backed up · 10 bytes · kept 1\n")
    hearth.back_up(clock.at)

    with bucket.only as bundle:
        for name in bundle.getnames():
            assert name.startswith(("packets/first/", "commons/")), name
        assert not [name for name in bundle.getnames() if "key" in name]
        assert "backup.log" not in bundle.getnames()  # not even its own log


def test_what_is_uploaded_is_encrypted_and_opens_with_the_key(hearth, bucket, packet,
                                                              commons, clock):
    a_whole_world(packet, commons)
    hearth.back_up(clock.at)

    [key] = bucket.keys
    assert key == "backups/" + NAME
    sealed = bucket.objects[key]
    assert not sealed.startswith(b"\x1f\x8b")  # not a tar.gz lying in the open

    plain = Fernet(KEY).decrypt(sealed)
    assert plain.startswith(b"\x1f\x8b")  # and under the key, one
    with tarfile.open(fileobj=io.BytesIO(plain), mode="r:gz") as bundle:
        assert bundle.getmembers()

    with pytest.raises(Exception):  # and no other key opens it
        Fernet(Fernet.generate_key()).decrypt(sealed)


def test_a_backup_writes_nothing_into_the_record(hearth, bucket, packet, commons,
                                                 data_dir, clock):
    a_whole_world(packet, commons)
    before = files_now(packet) | files_now(commons)
    hearth.back_up(clock.at)

    assert files_now(packet) | files_now(commons) == before  # not one byte of it moved
    assert hearth.BACKUP_LOG == data_dir / "backup.log"      # the line is kept outside
    assert not list(data_dir.rglob("*.tar.gz*"))             # and no archive anywhere


# ---- the bucket keeps thirty ---------------------------------------------

def take_many(hearth, count):
    """One backup a day, for as many days as asked. The stamps they were given."""
    return [hearth.back_up(NOW + timedelta(days=day)) for day in range(count)]


def test_the_bucket_keeps_thirty_and_the_oldest_go(hearth, bucket, packet, commons):
    a_whole_world(packet, commons)
    take_many(hearth, 35)

    assert len(bucket.keys) == 30
    assert len(bucket.deleted) == 5
    # the five that went are the five oldest, and the thirty left are the newest
    assert bucket.deleted == ["backups/tesserae-%s.tar.gz.enc"
                              % (NOW + timedelta(days=day)).strftime("%Y-%m-%dT%H-%M-%SZ")
                              for day in range(5)]
    assert bucket.keys[0].endswith("2026-10-20T12-00-00Z.tar.gz.enc")
    assert bucket.keys[-1].endswith("2026-11-18T12-00-00Z.tar.gz.enc")
    assert log_lines(hearth)[-1].endswith("· kept 30")


def test_the_count_climbs_as_the_bucket_fills(hearth, bucket):
    take_many(hearth, 3)
    assert [line.split("·")[-1].strip() for line in log_lines(hearth)] == [
        "kept 1", "kept 2", "kept 3"]
    assert len(bucket.keys) == 3
    assert bucket.deleted == []


def test_nothing_else_in_the_bucket_is_touched(hearth, bucket):
    bucket.objects["backups/something-else-entirely"] = b"not ours"
    bucket.objects["another-thing.txt"] = b"nor this"
    take_many(hearth, 35)

    assert bucket.objects["backups/something-else-entirely"] == b"not ours"
    assert bucket.objects["another-thing.txt"] == b"nor this"
    assert not [key for key in bucket.deleted if "tesserae-" not in key]


# ---- when there is nothing set up ----------------------------------------

def test_a_hearth_with_no_bucket_says_so_once_a_day(unconfigured, clock):
    hearth = unconfigured
    assert hearth.back_up(NOW) == UNCONFIGURED
    assert log_lines(hearth) == [UNCONFIGURED]

    # the same day, again and again: the line is not written twice
    hearth.back_up(NOW + timedelta(hours=1))
    hearth.back_up(NOW + timedelta(hours=11, minutes=59))
    assert log_lines(hearth) == [UNCONFIGURED]

    # the next day it is said once more, and once only
    hearth.back_up(NOW + timedelta(days=1))
    hearth.back_up(NOW + timedelta(days=1, hours=1))
    assert log_lines(hearth) == [UNCONFIGURED, "2026-10-16T12-00-00Z · not configured"]


@pytest.mark.parametrize("missing", VARIABLES)
def test_one_variable_missing_is_not_configured(hearth, bucket, monkeypatch, missing):
    monkeypatch.delenv(missing)
    monkeypatch.setattr(hearth, "bucket_client",
                        lambda: pytest.fail("it reached for the bucket anyway"))
    assert hearth.back_up(NOW) == UNCONFIGURED
    assert bucket.keys == []


def test_a_region_is_not_needed(hearth, bucket, monkeypatch):
    monkeypatch.delenv("AWS_REGION", raising=False)
    assert hearth.back_up(NOW).endswith("kept 1")


# ---- when something goes wrong -------------------------------------------

def test_a_bucket_that_will_not_take_it_is_written_down_and_not_raised(hearth, bucket,
                                                                       monkeypatch):
    def refuse(**how):
        raise RuntimeError("the bucket said no\n   and said it over two lines")

    monkeypatch.setattr(bucket, "put_object", refuse)
    said = hearth.back_up(NOW)

    assert said == "%s · error · the bucket said no and said it over two lines" % STAMP
    assert log_lines(hearth) == [said]  # one line, whatever shape the trouble had
    assert bucket.keys == []


def test_a_key_that_is_not_a_key_is_written_down_and_not_raised(hearth, bucket, monkeypatch):
    monkeypatch.setenv("BACKUP_KEY", "not a Fernet key at all")
    said = hearth.back_up(NOW)

    assert said.startswith("%s · error · " % STAMP)
    assert log_lines(hearth) == [said]
    assert bucket.keys == []


def test_an_error_while_clearing_out_still_leaves_the_backup(hearth, bucket, monkeypatch):
    take_many(hearth, 31)  # thirty kept, the oldest already gone
    monkeypatch.setattr(bucket, "delete_object",
                        lambda **how: (_ for _ in ()).throw(RuntimeError("no")))
    said = hearth.back_up(NOW + timedelta(days=31))

    assert "· error ·" in said
    assert len(bucket.keys) == 31  # what was uploaded is in the bucket, untidied


def test_a_very_long_complaint_is_cut_to_one_readable_line(hearth, bucket, monkeypatch):
    monkeypatch.setattr(bucket, "put_object",
                        lambda **how: (_ for _ in ()).throw(RuntimeError("no " * 500)))
    said = hearth.back_up(NOW)
    assert len(said) < 260 and said.endswith("…")
    assert log_lines(hearth) == [said]


# ---- the line on the attendances page ------------------------------------

def told(founder):
    """The attendances page as running text, so a sentence can be looked for whole."""
    return " ".join(page(founder.get("/attendances")).split())


def test_the_page_says_there_is_no_backup_yet(founder, bucket):
    assert "Last backup: none yet" in told(founder)


def test_the_page_says_when_the_last_one_was(founder, bucket, hearth, clock):
    hearth.back_up(clock.at)
    assert "Last backup: 15 October 2026 · 30 kept" not in told(founder)
    assert "Last backup: 15 October 2026 · 1 kept" in told(founder)

    take_many(hearth, 35)
    assert "Last backup: 18 November 2026 · 30 kept" in told(founder)


def test_the_attendances_page_says_when_backups_are_not_configured(founder, unconfigured):
    said = told(founder)
    assert "Backups are not configured." in said
    assert "Last backup:" not in said


def test_an_error_does_not_pass_for_a_backup(founder, bucket, hearth, monkeypatch):
    hearth.back_up(NOW - timedelta(days=1))  # one good one, a day ago
    monkeypatch.setattr(bucket, "put_object",
                        lambda **how: (_ for _ in ()).throw(RuntimeError("no")))
    hearth.back_up(NOW)

    assert "Last backup: 14 October 2026 · 1 kept" in told(founder)  # the last good one


def test_a_line_that_is_not_a_line_is_stepped_over(hearth, bucket, data_dir):
    write(data_dir / "backup.log",
          "not a stamp · backed up · 10 bytes · kept 3\n"
          "2026-10-13T13-00-00Z · backed up · 10 bytes · kept several\n"
          "2026-10-12T13-00-00Z · backed up · 10 bytes · kept 7\n")
    assert hearth.backup_shown() == "Last backup: 12 October 2026 · 7 kept"


# ---- backing up by hand --------------------------------------------------

def test_only_the_founder_may_back_up_by_hand(visitor, bucket, hearth):
    answer = visitor.post("/backup-now", data={"confirm": "yes"})
    assert answer.status_code == 302
    assert answer.headers["Location"].endswith("/login")
    assert bucket.keys == []
    assert log_lines(hearth) == []


def test_backing_up_by_hand_takes_one_question_first(founder, bucket, hearth):
    asked = founder.post("/backup-now")
    assert asked.status_code == 200
    assert "Back one up now?" in page(asked)
    assert bucket.keys == []  # nothing has been done yet
    assert log_lines(hearth) == []


def test_backing_up_by_hand_runs_it_and_shows_the_line(founder, bucket, hearth, clock):
    done = founder.post("/backup-now", data={"confirm": "yes"})
    assert done.status_code == 200
    assert bucket.keys == ["backups/" + NAME]

    [line] = log_lines(hearth)
    assert line in " ".join(page(done).split())
    assert line.startswith("%s · backed up · " % STAMP) and line.endswith("· kept 1")


def test_backing_up_by_hand_with_nothing_set_up_says_so(founder, unconfigured):
    done = founder.post("/backup-now", data={"confirm": "yes"})
    assert UNCONFIGURED in " ".join(page(done).split())


# ---- the backups page ----------------------------------------------------

def test_only_the_founder_may_see_the_backups(visitor, bucket):
    for where in ("/backups", "/backups/" + NAME):
        answer = visitor.get(where)
        assert answer.status_code == 302, where
        assert answer.headers["Location"].endswith("/login")


def test_the_page_lists_what_is_in_the_bucket_newest_first(founder, bucket, hearth):
    take_many(hearth, 3)
    said = page(founder.get("/backups"))

    for day in range(3):
        stamp = (NOW + timedelta(days=day)).strftime("%Y-%m-%dT%H-%M-%SZ")
        assert 'href="/backups/tesserae-%s.tar.gz.enc"' % stamp in said
    assert said.index("2026-10-17") < said.index("2026-10-15")  # newest first
    assert "17 October 2026, 12:00 UTC" in said  # said in words
    assert " KB" in said or " bytes" in said     # and with its size
    assert "3 kept" in said


def test_the_page_is_plain_when_there_is_nothing_in_the_bucket(founder, bucket):
    assert "No backups yet." in page(founder.get("/backups"))


def test_the_page_says_when_backups_are_not_configured(founder, unconfigured):
    assert "Backups are not configured." in page(founder.get("/backups"))


def test_a_bucket_that_cannot_be_read_is_said_plainly(founder, bucket, monkeypatch):
    monkeypatch.setattr(bucket, "list_objects_v2",
                        lambda **how: (_ for _ in ()).throw(RuntimeError("the door is shut")))
    said = page(founder.get("/backups"))
    assert "The bucket could not be read: the door is shut" in said


def test_one_backup_is_handed_over_whole_and_in_chunks(founder, bucket, hearth):
    held = b"a backup, as far as this page is concerned. " * 5000
    bucket.objects["backups/" + NAME] = held

    answer = founder.get("/backups/" + NAME)
    assert answer.status_code == 200
    assert answer.get_data() == held  # byte for byte, still encrypted
    assert answer.content_type == "application/octet-stream"
    assert answer.headers["Content-Disposition"] == 'attachment; filename="%s"' % NAME

    # and it went out in pieces rather than being held whole in the hearth
    [body] = bucket.bodies
    assert body.asked == [hearth.BACKUP_STREAM]
    assert len(held) > hearth.BACKUP_STREAM


@pytest.mark.parametrize("name", [
    "tesserae-nonsense.tar.gz.enc",       # not a stamp
    "tesserae-%s.tar.gz" % STAMP,         # not an encrypted one
    "backup.log", "members.md", "..",
])
def test_no_other_name_is_at_an_address(founder, bucket, name):
    bucket.objects["backups/" + name] = b"whatever this is"
    assert founder.get("/backups/" + name).status_code == 404


def test_a_backup_that_is_not_there_is_not_there(founder, bucket):
    assert founder.get("/backups/" + NAME).status_code == 404


def test_the_backups_are_reached_from_the_attendances_page(founder, bucket):
    assert 'href="/backups"' in page(founder.get("/attendances"))


# ---- the daily thread ----------------------------------------------------

def run_backing_up(hearth, monkeypatch):
    """The thread, run until it first lies down. What it took, and how long it slept."""
    taken = []
    monkeypatch.setattr(hearth, "back_up", lambda now: taken.append(now))

    def never(seconds):
        raise Stop(seconds)

    monkeypatch.setattr(hearth.time, "sleep", never)
    with pytest.raises(Stop) as stopped:
        hearth.backing_up()
    return taken, stopped.value.args[0]


def test_the_hour_is_thirteen_hundred_utc(hearth, clock):
    assert hearth.next_backup(NOW).isoformat() == "2026-10-15T13:00:00+00:00"
    assert hearth.next_backup(NOW.replace(hour=13)).isoformat() == "2026-10-16T13:00:00+00:00"
    assert hearth.next_backup(NOW.replace(hour=23)).isoformat() == "2026-10-16T13:00:00+00:00"


def test_the_thread_waits_for_the_hour_in_short_stretches(hearth, bucket, monkeypatch,
                                                          data_dir):
    write(data_dir / "backup.log", "2026-10-15T06-00-00Z · backed up · 10 bytes · kept 1\n")
    taken, slept = run_backing_up(hearth, monkeypatch)

    assert taken == []  # this morning's is recent enough; it waits for the hour
    assert 0 < slept <= hearth.BACKUP_CHUNK


def test_a_machine_that_missed_the_hour_backs_up_at_once(hearth, bucket, monkeypatch,
                                                         data_dir):
    write(data_dir / "backup.log", "2026-10-14T06-00-00Z · backed up · 10 bytes · kept 1\n")
    taken, _ = run_backing_up(hearth, monkeypatch)
    assert taken == [NOW]  # thirty hours is too long to have gone without one


def test_a_hearth_that_has_never_backed_up_backs_up_at_once(hearth, bucket, monkeypatch):
    taken, _ = run_backing_up(hearth, monkeypatch)
    assert taken == [NOW]


@pytest.mark.parametrize("since, overdue", [
    (timedelta(hours=1), False),
    (timedelta(hours=23, minutes=59), False),
    (timedelta(hours=24), True),
    (timedelta(days=3), True),
])
def test_what_counts_as_too_long_ago(hearth, bucket, data_dir, since, overdue):
    write(data_dir / "backup.log", "%s · backed up · 10 bytes · kept 1\n"
          % (NOW - since).strftime("%Y-%m-%dT%H-%M-%SZ"))
    assert hearth.backup_overdue(NOW) is overdue


def test_the_thread_outlives_anything_that_goes_wrong(hearth, monkeypatch):
    def fall_over(setting):
        raise RuntimeError("the clock has come apart")

    monkeypatch.setattr(hearth, "back_up", lambda now: None)
    monkeypatch.setattr(hearth, "next_backup", fall_over)
    slept = []

    def once(seconds):
        slept.append(seconds)
        raise Stop(seconds)

    monkeypatch.setattr(hearth.time, "sleep", once)
    with pytest.raises(Stop):
        hearth.backing_up()
    assert slept == [hearth.BACKUP_ERROR]  # it waits, rather than spinning or ending


def test_the_backup_thread_is_set_going_once(hearth, monkeypatch):
    assert hearth.BACKUPS_RUNNING is True  # the import set it going
    with no_threads() as started:
        hearth.start_backups()
        hearth.start_backups()
    assert started == []

    monkeypatch.setattr(hearth, "BACKUPS_RUNNING", False)
    with no_threads() as started:
        hearth.start_backups()
        hearth.start_backups()
    assert [thread.name for thread in started] == ["backups"]
    assert started[0].daemon is True


# ---- the client the hearth would really build ----------------------------

def test_the_client_is_built_out_of_the_environment(hearth, monkeypatch):
    """The one place boto3 is called for real - built, not used. No call goes out."""
    set_variables(monkeypatch)
    monkeypatch.setenv("AWS_REGION", "auto")
    client = hearth.bucket_client()

    assert client.meta.endpoint_url == "https://storage.example.invalid"
    assert client.meta.region_name == "auto"
    credentials = client._request_signer._credentials
    assert credentials.access_key == "an access key for the tests"
    assert credentials.secret_key == "a secret for the tests"


# ---- opening one again, on the founder's own machine ---------------------

def run_restore(*args):
    """restore_backup.py, run the way the founder runs it."""
    return subprocess.run([sys.executable, str(REPO / "restore_backup.py"), *args],
                          capture_output=True, text=True)


@pytest.fixture
def backup_file(hearth, bucket, packet, commons, tmp_path, clock):
    """One real backup, made by this hearth, and the key that opens it."""
    a_whole_world(packet, commons)
    hearth.back_up(clock.at)
    archive = tmp_path / NAME
    archive.write_bytes(bucket.objects["backups/" + NAME])
    key_file = tmp_path / "backup.key"
    key_file.write_text(KEY + "\n", encoding="utf-8")
    return archive, key_file


def test_a_backup_opens_again_into_the_same_two_trees(backup_file, packet, commons, tmp_path):
    archive, key_file = backup_file
    out = tmp_path / "restored"
    done = run_restore(str(archive), str(key_file), str(out))
    assert done.returncode == 0, done.stdout + done.stderr

    came_back = {path.relative_to(out).as_posix()
                 for path in out.rglob("*") if path.is_file()}
    assert came_back == files_under(packet, "packets/first/") | files_under(commons, "commons/")
    # byte for byte, and the list of them printed
    assert (out / "packets/first/self.md").read_bytes() == (packet / "self.md").read_bytes()
    assert "packets/first/self.md" in done.stdout
    assert "commons/members.md" in done.stdout
    assert "%d files" % len(came_back) in done.stdout


def test_it_refuses_a_directory_with_anything_in_it(backup_file, tmp_path):
    archive, key_file = backup_file
    out = tmp_path / "not empty"
    out.mkdir()
    (out / "a record someone still wants.md").write_text("mine", encoding="utf-8")

    done = run_restore(str(archive), str(key_file), str(out))
    assert done.returncode == 1
    assert "is not empty" in done.stdout
    assert [path.name for path in out.iterdir()] == ["a record someone still wants.md"]


def test_an_empty_directory_is_fine(backup_file, tmp_path):
    archive, key_file = backup_file
    out = tmp_path / "empty"
    out.mkdir()
    assert run_restore(str(archive), str(key_file), str(out)).returncode == 0


def test_the_wrong_key_opens_nothing(backup_file, tmp_path):
    archive, _ = backup_file
    other = tmp_path / "another.key"
    other.write_bytes(Fernet.generate_key())
    out = tmp_path / "restored"

    done = run_restore(str(archive), str(other), str(out))
    assert done.returncode == 1
    assert "does not open this backup" in done.stdout
    assert not out.exists() or not list(out.iterdir())


def test_it_says_how_to_be_used(tmp_path):
    done = run_restore()
    assert done.returncode == 2
    assert "restore_backup.py <file.tar.gz.enc> <path to backup.key> <output dir>" in done.stdout

    missing = run_restore(str(tmp_path / "nothing.enc"), str(tmp_path / "no.key"),
                          str(tmp_path / "out"))
    assert missing.returncode == 1
    assert "No such backup" in missing.stdout


def test_it_will_not_write_outside_the_output_directory(tmp_path):
    """A backup is written by the hearth, but the script trusts no archive."""
    import restore_backup

    held = io.BytesIO()
    with tarfile.open(fileobj=held, mode="w:gz") as bundle:
        for name in ("../escaped.md", "/rooted.md", "packets/first/self.md"):
            body = b"a file"
            info = tarfile.TarInfo(name)
            info.size = len(body)
            bundle.addfile(info, io.BytesIO(body))

    archive = tmp_path / NAME
    archive.write_bytes(Fernet(KEY).encrypt(held.getvalue()))
    key_file = tmp_path / "backup.key"
    key_file.write_text(KEY, encoding="utf-8")
    out = tmp_path / "restored"

    assert restore_backup.main([str(archive), str(key_file), str(out)]) == 0
    assert {path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file()} \
        == {"packets/first/self.md"}
    assert not (tmp_path / "escaped.md").exists()
