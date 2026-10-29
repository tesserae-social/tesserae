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

and, once they have opened a room with a letter in it from the other party, how
far they have read in each:

    members/<pseudonym>/seen.json
        {room id: the stamp of the newest letter of the other's they have opened}

and, while they rest from the correspondence, their rest, with each one that is
over kept beside it (see rest_of):

    members/<pseudonym>/rest.json
        {"since": UTC stamp, "until": YYYY-MM-DD or null}
    members/<pseudonym>/rest/rest-<since>.json

Storage only: no route, no page. A member's public identity document is shaped
here from their record (did_document), and served by the hearth. The name is checked before it is ever made into
a path, and that check is the whole of the path's safety. Nothing here logs or
prints a vault, and no error raised here carries one.
"""

import base64
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

import agents
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
SEEN = "seen.json"

ROLES = ("keeper", "member")

PSEUDONYM_MIN = 2
PSEUDONYM_MAX = 30
# a letter first; then letters and digits, in runs joined by single hyphens
PSEUDONYM = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")

# names that already mean someone, or something, here: and every agent's id,
# and its commons name as an address writes it (as bonds.slug does), so that no
# member is ever named as an agent is
RESERVED = frozenset({
    "founder", "first", "the-first-one", "keeper", "tesserae", "hearth",
    "commons", "bench", "admin", "root", "system",
} | {agent["id"] for agent in agents.registry()}
  | {re.sub(r"[^a-z0-9]+", "-", agent["commons_name"].lower()).strip("-")
     for agent in agents.registry()})

# names Windows will not make a folder under, whatever the folder is
DEVICES = frozenset({"con", "prn", "aux", "nul"}
                    | {"com%d" % n for n in range(1, 10)}
                    | {"lpt%d" % n for n in range(1, 10)})

VERIFY_KEY = re.compile(r"[0-9a-f]{64}")

# Who a member is to anyone outside. A member's identity document is served by
# the hearth, under their pseudonym; the keeper is the founder, whose document
# has always been at tesserae.social, and is never named under the hearth.
FOUNDER_DID = "did:web:tesserae.social:ids:founder"
HEARTH_DID = "did:web:hearth.tesserae.social:ids:"


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


# ---------------------------------------------------------------- identities


def did_for(pseudonym):
    """The DID a member signs as: the founder's for the keeper, the hearth's for a member."""
    record = load_member(pseudonym)
    if not isinstance(record, dict) or record.get("role") not in ROLES:
        raise MemberError("there is no member by that name")
    if record["role"] == "keeper":
        return FOUNDER_DID
    return HEARTH_DID + pseudonym


def did_document(pseudonym):
    """A member's public identity document, or None for anyone who has no such document.

    The same shape as the documents under ids/, and nothing more of the record
    than the key: no vault, no day of arrival, no vouchers, no role. The keeper,
    a name no one has, and a name no one could have all come back as None alike.
    """
    try:
        record = load_member(pseudonym)
    except MemberError:
        return None
    if not isinstance(record, dict) or record.get("role") != "member":
        return None
    key = record.get("verify_key")
    if not isinstance(key, str) or not VERIFY_KEY.fullmatch(key):
        return None
    did = HEARTH_DID + pseudonym
    return {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": did,
        "verificationMethod": [
            {
                "id": did + "#key-1",
                "type": "Ed25519VerificationKey2020",
                "controller": did,
                "publicKeyBase64": base64.b64encode(bytes.fromhex(key)).decode("ascii"),
            }
        ],
    }


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


# ---------------------------------------------------------------- what is seen

# How far a member has read in each of their rooms. It is theirs and not the
# room's, so it is kept with them, beside their record and never in it, and goes
# wherever members/ goes. A file that is not there, or cannot be read, or says
# nothing of a room, is nothing seen there: what it is for is only to stop saying
# a letter is new, and it never stands in the way of anything.
SEEN_LOCK = threading.Lock()  # one reading and writing at a time, so it moves only forward


def _seen(path):
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(held, dict):
        return {}
    return {room: stamp for room, stamp in held.items() if isinstance(stamp, str)}


def seen(pseudonym, room_id):
    """The newest stamp this member has opened in a room, or "" for nothing seen."""
    return _seen(_folder(pseudonym) / SEEN).get(room_id, "")


def mark_seen(pseudonym, room_id, stamp):
    """Record that a member has opened a room as far as stamp; never further back.

    Only a member who is there is written for. Whatever cannot be read in the
    file is let go of when it is written again.
    """
    folder = _folder(pseudonym)
    if not (folder / RECORD).is_file():
        return
    with SEEN_LOCK:
        held = _seen(folder / SEEN)
        if stamp <= held.get(room_id, ""):
            return
        held[room_id] = stamp
        _write_json(folder / SEEN, held)


# ---------------------------------------------------------------- a rest

# A person's rest from the correspondence is theirs, and covers their own rooms
# and no others: an agent reads the rest of each person it shares a room with,
# and of no one else. The founder's is where it has always been, in the first
# one's packet, so that the first one's packet, its backup and its reading are
# what they were; a member's is kept with them. The hearth writes both; a waking
# only reads.
FOUNDER = "founder"  # the founder in a room, as rooms.store_name names him
REST = "rest.json"
REST_KEPT = "rest"


def rest_of(person):
    """Where a person's rest stands, and where each one that is over is kept: (rest, kept).

    person is a room's name for them: "founder", or a member's pseudonym, which
    is checked before it is made into a path. A rest that is over is kept in
    kept under the folder's own name and its since: founder-rest-<since>.json,
    as always, or rest-<since>.json.
    """
    if person == FOUNDER:
        packet = DATA / "packets" / agents.first()["id"]
        return packet / "founder-rest.json", packet / "founder-rest"
    folder = _folder(person)
    return folder / REST, folder / REST_KEPT
