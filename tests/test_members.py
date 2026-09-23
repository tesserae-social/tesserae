"""The members' store: the names it takes, the records it keeps, the keys it
will not let two members hold, and a vault replaced without a trace of the old.

Every vault here is sealed at argon2id's minimum cost so the suite stays quick,
as in test_vault.py.
"""

import importlib
import sys
from datetime import datetime, timezone

import pytest
from nacl.pwhash import argon2id

import vault
from conftest import read_json, write
from vault import VaultError

PASSWORD = "correct horse battery"
NEW_PASSWORD = "a longer, newer password"

ARRIVED = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
CHANGED = datetime(2026, 10, 20, 9, 30, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


@pytest.fixture
def members(env):
    """members.py, read afresh against the test's own DATA_DIR."""
    sys.modules.pop("members", None)
    return importlib.import_module("members")


@pytest.fixture
def folder(members, data_dir):
    return data_dir / "members"


def a_vault(password=PASSWORD):
    sealed, phrase, _ = vault.make_vault(password)
    return sealed, phrase


def refused(fn, *args, **kwargs):
    from members import MemberError
    with pytest.raises(MemberError) as caught:
        fn(*args, **kwargs)
    message = str(caught.value)
    assert message and "\n" not in message
    return message


# ---------------------------------------------------------------- names


@pytest.mark.parametrize("name", [
    "ada", "ab", "a1", "ada-lovelace", "a-b-c", "x2-y3", "a" * 30, "river9",
])
def test_good_names_pass(members, name):
    assert members.validate_pseudonym(name) == name


@pytest.mark.parametrize("name", [
    "founder", "first", "the-first-one", "keeper", "tesserae", "hearth",
    "commons", "bench", "admin", "root", "system",
])
def test_reserved_names_are_refused(members, name):
    assert refused(members.validate_pseudonym, name) == "that name is not free to take"


@pytest.mark.parametrize("name", [
    "Ada", "ADA", "ada_lovelace", "ada lovelace", "ada.lovelace", "ada!", "adä",
    "1ada", "-ada", "ada-", "ada--lovelace", "ada\n", "\nada", "ada\x00",
])
def test_bad_characters_are_refused(members, name):
    refused(members.validate_pseudonym, name)


@pytest.mark.parametrize("name", ["", "a", "a" * 31, "a" * 300])
def test_too_short_or_too_long_is_refused(members, name):
    refused(members.validate_pseudonym, name)


@pytest.mark.parametrize("name", [
    "..", ".", "../x", "..\\x", "x/../y", "x/y", "x\\y", "/etc", "C:\\x", "C:x",
    "~root", "%2e%2e", "con", "nul", "com1",
])
def test_path_tricks_are_refused(members, name):
    refused(members.validate_pseudonym, name)
    refused(members.load_member, name)
    refused(members.create_member, name, a_vault()[0], "member", [])


@pytest.mark.parametrize("name", [None, 12, b"ada", ["ada"]])
def test_a_name_must_be_text(members, name):
    refused(members.validate_pseudonym, name)


def test_the_folder_must_stay_inside_members(members, monkeypatch, tmp_path):
    # Were the check on the name ever loosened, the resolved path still holds the line.
    monkeypatch.setattr(members, "validate_pseudonym", lambda name: name)
    refused(members._folder, "../outside")
    assert members._folder("ada") == members.MEMBERS / "ada"


# ---------------------------------------------------------------- create, load, list


def test_create_and_load(members, folder):
    sealed, _ = a_vault()
    record = members.create_member("ada", sealed, "keeper", ["bram"], now=ARRIVED)
    assert record == {
        "v": 1,
        "pseudonym": "ada",
        "role": "keeper",
        "verify_key": sealed["verify_key"],
        "arrived_at": "2026-10-15T12:00:00Z",
        "vouched_by": ["bram"],
        "vault": sealed,
    }
    assert read_json(folder / "ada" / "member.json") == record
    assert members.load_member("ada") == record
    assert not (folder / "ada" / "key-history.json").exists()
    # the vault it holds still opens
    assert vault.unlock(members.load_member("ada")["vault"], PASSWORD)


def test_nothing_is_left_beside_the_record(members, folder):
    members.create_member("ada", a_vault()[0], "member", [])
    assert [path.name for path in (folder / "ada").iterdir()] == ["member.json"]


def test_load_of_no_one_is_none(members):
    assert members.load_member("nobody") is None


def test_list_members_is_sorted_and_only_members(members, folder):
    assert members.list_members() == []
    for name in ("mira", "ada", "zed-9"):
        members.create_member(name, a_vault()[0], "member", [])
    (folder / "empty").mkdir()                    # a folder with no record
    write(folder / "stray.json", "{}")            # a file, not a folder
    (folder / "Not-A-Name").mkdir()               # a name no member could be given
    write(folder / "Not-A-Name" / "member.json", "{}")
    assert members.list_members() == ["ada", "mira", "zed-9"]


def test_member_by_key(members):
    ada, _ = a_vault()
    bram, _ = a_vault()
    members.create_member("ada", ada, "member", [])
    members.create_member("bram", bram, "member", ["ada"])
    assert members.member_by_key(ada["verify_key"]) == "ada"
    assert members.member_by_key(bram["verify_key"].upper()) == "bram"
    assert members.member_by_key(vault.cut_key().verify_key.encode().hex()) is None
    assert members.member_by_key(None) is None


def test_the_time_of_arrival_defaults_to_now(members):
    record = members.create_member("ada", a_vault()[0], "member", [])
    arrived = datetime.strptime(record["arrived_at"], "%Y-%m-%dT%H:%M:%SZ")
    assert abs((datetime.now(timezone.utc).replace(tzinfo=None) - arrived).total_seconds()) < 60


@pytest.mark.parametrize("role", ["founder", "Keeper", "", None])
def test_a_role_is_keeper_or_member(members, role):
    refused(members.create_member, "ada", a_vault()[0], role, [])
    assert members.load_member("ada") is None


@pytest.mark.parametrize("vouched_by", ["bram", None, ["../x"], ["Bram"]])
def test_vouched_by_is_a_list_of_names(members, vouched_by):
    refused(members.create_member, "ada", a_vault()[0], "member", vouched_by)
    assert members.load_member("ada") is None


def test_a_malformed_vault_is_refused(members):
    sealed, _ = a_vault()
    for bad in (None, {}, {**sealed, "extra": 1}, {**sealed, "verify_key": "not hex"},
                {**sealed, "verify_key": sealed["verify_key"].upper()}):
        refused(members.create_member, "ada", bad, "member", [])
    assert members.list_members() == []


# ---------------------------------------------------------------- duplicates


def test_a_name_already_taken_is_refused(members):
    first, _ = a_vault()
    members.create_member("ada", first, "member", [])
    assert refused(members.create_member, "ada", a_vault()[0], "member", []) == \
        "that name is already taken"
    assert members.load_member("ada")["vault"] == first


def test_a_name_taken_in_another_case_is_refused(members, folder):
    # nothing here writes a capital, but a folder made by hand might have one
    write(folder / "Ada" / "member.json", "{}")
    assert refused(members.create_member, "ada", a_vault()[0], "member", []) == \
        "that name is already taken"


def test_a_key_already_held_is_refused(members):
    sealed, _ = a_vault()
    members.create_member("ada", sealed, "member", [])
    # the same key, sealed again under another password, is still the same key
    again = vault.change_password(sealed, PASSWORD, NEW_PASSWORD)
    assert refused(members.create_member, "bram", again, "member", []) == \
        "that key already belongs to a member"
    assert members.list_members() == ["ada"]


# ---------------------------------------------------------------- replacing a vault


def test_same_key_replaces_and_forgets_the_old(members, folder):
    sealed, phrase = a_vault()
    members.create_member("ada", sealed, "member", [], now=ARRIVED)

    changed = vault.change_password(sealed, PASSWORD, NEW_PASSWORD)
    record = members.replace_vault("ada", changed, now=CHANGED)

    assert record["vault"] == changed and record["verify_key"] == sealed["verify_key"]
    assert record["arrived_at"] == "2026-10-15T12:00:00Z"
    stored = members.load_member("ada")
    assert stored == record
    assert vault.unlock(stored["vault"], NEW_PASSWORD)
    with pytest.raises(VaultError):
        vault.unlock(stored["vault"], PASSWORD)  # the old password opens nothing now

    # no history, and no trace of the old seal anywhere in the folder
    assert not (folder / "ada" / "key-history.json").exists()
    assert [path.name for path in (folder / "ada").iterdir()] == ["member.json"]
    old_box = sealed["by_password"]["box"]
    for path in folder.rglob("*"):
        if path.is_file():
            assert old_box not in path.read_text(encoding="utf-8")


def test_recovery_replaces_the_same_way(members, folder):
    sealed, phrase = a_vault()
    members.create_member("ada", sealed, "member", [])
    members.replace_vault("ada", vault.recover(sealed, phrase, NEW_PASSWORD))
    assert vault.unlock(members.load_member("ada")["vault"], NEW_PASSWORD)
    assert not (folder / "ada" / "key-history.json").exists()


def test_a_new_key_is_written_into_the_history(members, folder):
    first, _ = a_vault()
    second, _ = a_vault()
    third, _ = a_vault()
    members.create_member("ada", first, "member", [])

    record = members.replace_vault("ada", second, now=CHANGED)
    assert record["verify_key"] == second["verify_key"]
    assert members.member_by_key(second["verify_key"]) == "ada"
    assert members.member_by_key(first["verify_key"]) is None
    assert read_json(folder / "ada" / "key-history.json") == [
        {"old_key": first["verify_key"], "new_key": second["verify_key"],
         "at": "2026-10-20T09:30:00Z"},
    ]

    members.replace_vault("ada", third, now=ARRIVED.replace(month=11))
    history = read_json(folder / "ada" / "key-history.json")
    assert [entry["new_key"] for entry in history] == [second["verify_key"],
                                                       third["verify_key"]]
    assert history[1]["old_key"] == second["verify_key"]


def test_a_new_key_held_by_another_is_refused(members, folder):
    ada, _ = a_vault()
    bram, _ = a_vault()
    members.create_member("ada", ada, "member", [])
    members.create_member("bram", bram, "member", [])
    assert refused(members.replace_vault, "ada", bram) == \
        "that key already belongs to a member"
    assert members.load_member("ada")["vault"] == ada
    assert not (folder / "ada" / "key-history.json").exists()


def test_replacing_for_no_one_is_refused(members):
    refused(members.replace_vault, "nobody", a_vault()[0])
    refused(members.replace_vault, "../x", a_vault()[0])


def test_a_malformed_replacement_is_refused(members):
    sealed, _ = a_vault()
    members.create_member("ada", sealed, "member", [])
    refused(members.replace_vault, "ada", {"verify_key": sealed["verify_key"]})
    assert members.load_member("ada")["vault"] == sealed


def test_a_write_that_fails_leaves_the_old_record_whole(members, monkeypatch, folder):
    sealed, _ = a_vault()
    members.create_member("ada", sealed, "member", [])
    before = (folder / "ada" / "member.json").read_bytes()

    def broken(*args):
        raise OSError("the disk is full")

    monkeypatch.setattr(members.os, "replace", broken)
    with pytest.raises(OSError):
        members.replace_vault("ada", vault.change_password(sealed, PASSWORD, NEW_PASSWORD))
    assert (folder / "ada" / "member.json").read_bytes() == before
    assert [path.name for path in (folder / "ada").iterdir()] == ["member.json"]


# ---------------------------------------------------------------- nothing said aloud


def test_no_error_carries_the_vault(members):
    sealed, _ = a_vault()
    members.create_member("ada", sealed, "member", [])
    for message in (
        refused(members.create_member, "ada", sealed, "member", []),
        refused(members.create_member, "bram", sealed, "member", []),
        refused(members.create_member, "bram", {**sealed, "extra": 1}, "member", []),
    ):
        for secret in (sealed["by_password"]["box"], sealed["by_phrase"]["box"],
                       sealed["verify_key"]):
            assert secret not in message


def test_nothing_is_printed(members, capsys, caplog):
    sealed, _ = a_vault()
    members.create_member("ada", sealed, "member", [])
    members.replace_vault("ada", vault.change_password(sealed, PASSWORD, NEW_PASSWORD))
    members.load_member("ada")
    members.member_by_key(sealed["verify_key"])
    said = capsys.readouterr()
    assert said.out == "" and said.err == ""
    assert caplog.records == []


# ---------------------------------------------------------------- the hearth serves none of it


PROBES = [
    "/members/ada/member.json",
    "/members/ada/key-history.json",
    "/members/ada/",
    "/members/",
    "/commons/../members/ada/member.json",
    "/commons/%2e%2e/members/ada/member.json",
    "/commons/..%2Fmembers%2Fada%2Fmember.json",
    "/commons/offerings/..%2F..%2Fmembers%2Fada%2Fmember.json",
    "/commons/offerings/member.json",
    "/static/../members/ada/member.json",
    "/static/members/ada/member.json",
    "/static/..%2Fmembers%2Fada%2Fmember.json",
    "/letters/photo/..%2F..%2F..%2F..%2Fmembers%2Fada%2Fmember.json",
    "/letters/picture/..%2F..%2F..%2F..%2Fmembers%2Fada%2Fmember.json",
    "/offerings/..%2F..%2Fmembers%2Fada%2Fmember.json",
    "/offerings/member.json",
    "/backups/..%2Fmembers%2Fada%2Fmember.json",
    "/bonds/..%2F..%2Fmembers%2Fada%2Fmember.json",
]


@pytest.mark.parametrize("who", ["visitor", "founder"])
def test_no_hearth_route_serves_a_member(request, hearth, members, folder, who):
    sealed, _ = a_vault()
    members.create_member("ada", sealed, "member", [])
    members.replace_vault("ada", a_vault()[0])  # so that there is a key history too
    assert (folder / "ada" / "member.json").is_file()
    assert (folder / "ada" / "key-history.json").is_file()

    stored = members.load_member("ada")
    telltales = [stored["vault"]["by_password"]["box"], stored["vault"]["by_phrase"]["box"],
                 stored["verify_key"], sealed["verify_key"], '"by_password"']

    client = request.getfixturevalue(who)
    for path in PROBES:
        answer = client.get(path)
        body = answer.get_data(as_text=True)
        assert answer.status_code != 200 or not any(t in body for t in telltales), path
        for telltale in telltales:
            assert telltale not in body, path
