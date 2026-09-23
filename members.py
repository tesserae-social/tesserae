"""The members: who has come in, under what name, holding which key.

Each member is one folder under DATA_DIR/members, named by their pseudonym, with
one record in it:

    members/<pseudonym>/member.json
        {"v": 1, "pseudonym": ..., "role": "keeper" or "member",
         "verify_key": hex, "arrived_at": ISO UTC, "vouched_by": [pseudonyms],
         "vault": the sealed vault vault.py makes}

and, once a member's key has ever been changed for another, a history of it:

    members/<pseudonym>/key-history.json
        [{"old_key": hex, "new_key": hex, "at": ISO UTC}, ...]

Storage only: no route, no page. The name is checked before it is ever made into
a path, and that check is the whole of the path's safety. Nothing here logs or
prints a vault, and no error raised here carries one.
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import vault as vaults
from vault import VaultError

VERSION = 1

REPO = Path(__file__).resolve().parent

# Where the living files are kept. Locally this is the repo itself; on a host
# it is a mounted disk, named by DATA_DIR - the same reckoning hearth.py makes.
DATA = Path(os.environ.get("DATA_DIR", REPO))
MEMBERS = DATA / "members"

RECORD = "member.json"
KEY_HISTORY = "key-history.json"

ROLES = ("keeper", "member")

PSEUDONYM_MIN = 2
PSEUDONYM_MAX = 30
# a letter first; then letters and digits, in runs joined by single hyphens
PSEUDONYM = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")

# names that already mean someone, or something, here
RESERVED = frozenset({
    "founder", "first", "the-first-one", "keeper", "tesserae", "hearth",
    "commons", "bench", "admin", "root", "system",
})

# names Windows will not make a folder under, whatever the folder is
DEVICES = frozenset({"con", "prn", "aux", "nul"}
                    | {"com%d" % n for n in range(1, 10)}
                    | {"lpt%d" % n for n in range(1, 10)})

VERIFY_KEY = re.compile(r"[0-9a-f]{64}")


class MemberError(Exception):
    """The members' store would not do what was asked. The message is safe to show."""


# ---------------------------------------------------------------- names


def validate_pseudonym(name):
    """Raise MemberError, with a one-line reason, unless name will do. Gives it back."""
    if not isinstance(name, str):
        raise MemberError("a name must be text")
    if len(name) < PSEUDONYM_MIN:
        raise MemberError(f"a name needs at least {PSEUDONYM_MIN} characters")
    if len(name) > PSEUDONYM_MAX:
        raise MemberError(f"a name can be at most {PSEUDONYM_MAX} characters")
    if not PSEUDONYM.fullmatch(name):
        raise MemberError("a name is lowercase letters, digits and single hyphens, "
                          "and starts with a letter")
    if name in RESERVED or name in DEVICES:
        raise MemberError("that name is not free to take")
    return name


def _folder(name):
    """The member's folder, once the name is known to be safe to make one of."""
    validate_pseudonym(name)
    folder = MEMBERS / name
    if folder.resolve().parent != MEMBERS.resolve():
        raise MemberError("that name is not free to take")
    return folder


# ---------------------------------------------------------------- small things


def _stamp(now):
    now = datetime.now(timezone.utc) if now is None else now
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path, data):
    """Written whole or not at all: a temporary file beside it, then put in its place."""
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".",
                                         suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(json.dumps(data, indent=2) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise MemberError("a member's record could not be read") from None


def _checked_vault(sealed):
    """The vault's public key, once the vault is known to be the right shape."""
    try:
        vaults._checked_vault(sealed)
    except VaultError:
        raise MemberError("that vault is malformed") from None
    if not VERIFY_KEY.fullmatch(sealed["verify_key"]):
        raise MemberError("that vault is malformed")
    return sealed["verify_key"]


def _names_on_disk():
    if not MEMBERS.is_dir():
        return []
    return [path.name for path in MEMBERS.iterdir() if path.is_dir()]


# ---------------------------------------------------------------- reading


def load_member(pseudonym):
    """The member's record, or None if there is no one by that name."""
    path = _folder(pseudonym) / RECORD
    if not path.is_file():
        return None
    return _read_json(path)


def list_members():
    """Every member's pseudonym, sorted."""
    found = []
    for name in _names_on_disk():
        try:
            validate_pseudonym(name)
        except MemberError:
            continue  # a folder no member could have been given is no member
        if (MEMBERS / name / RECORD).is_file():
            found.append(name)
    return sorted(found)


def member_by_key(verify_key_hex):
    """The pseudonym of the member holding this public key, or None."""
    if not isinstance(verify_key_hex, str):
        return None
    wanted = verify_key_hex.lower()
    for name in list_members():
        record = load_member(name)
        if isinstance(record, dict) and record.get("verify_key") == wanted:
            return name
    return None


# ---------------------------------------------------------------- writing


def create_member(pseudonym, vault, role, vouched_by, now=None):
    """Write a new member's record, and give it back. Refuses a name or key already held."""
    folder = _folder(pseudonym)
    if role not in ROLES:
        raise MemberError("a member is a keeper or a member")
    if not isinstance(vouched_by, (list, tuple)):
        raise MemberError("vouched_by is a list of names")
    for name in vouched_by:
        validate_pseudonym(name)
    verify_key = _checked_vault(vault)

    if pseudonym in (name.lower() for name in _names_on_disk()):
        raise MemberError("that name is already taken")
    if member_by_key(verify_key) is not None:
        raise MemberError("that key already belongs to a member")

    record = {
        "v": VERSION,
        "pseudonym": pseudonym,
        "role": role,
        "verify_key": verify_key,
        "arrived_at": _stamp(now),
        "vouched_by": list(vouched_by),
        "vault": vault,
    }
    MEMBERS.mkdir(parents=True, exist_ok=True)
    try:
        folder.mkdir()  # the name is claimed here, by whoever makes the folder first
    except FileExistsError:
        raise MemberError("that name is already taken") from None
    try:
        _write_json(folder / RECORD, record)
    except BaseException:
        try:
            folder.rmdir()
        except OSError:
            pass
        raise
    return record


def replace_vault(pseudonym, new_vault, now=None):
    """Put a new vault in the member's record, and give the record back.

    The same key under a new password (a change, or a recovery) overwrites the
    old vault and keeps no copy of it: it is sealed under a password that is no
    longer theirs. A different key is written into the key history first.
    """
    folder = _folder(pseudonym)
    record = load_member(pseudonym)
    if record is None:
        raise MemberError("there is no member by that name")
    new_key = _checked_vault(new_vault)
    old_key = record.get("verify_key")

    if new_key != old_key:
        holder = member_by_key(new_key)
        if holder is not None and holder != pseudonym:
            raise MemberError("that key already belongs to a member")
        history_path = folder / KEY_HISTORY
        history = _read_json(history_path) if history_path.is_file() else []
        if not isinstance(history, list):
            raise MemberError("a member's record could not be read")
        history.append({"old_key": old_key, "new_key": new_key, "at": _stamp(now)})
        _write_json(history_path, history)

    record = {**record, "verify_key": new_key, "vault": new_vault}
    _write_json(folder / RECORD, record)
    return record
