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

and, once they have said how they usually write, those words, until they clear
them (see writing_of):

    members/<pseudonym>/writing.json
        {"words": up to WRITING_LONGEST characters, "at": UTC stamp}

and their email address (see email_of), kept once they have confirmed it, or,
for someone who has just joined, kept unconfirmed until they do; it is never
shown in full, never copied out and never read by any agent:

    members/<pseudonym>/email.json
        {"address": ..., "set_at": UTC stamp, "confirmed_at": UTC stamp or null}

and, once they have chosen, how often they are emailed when something is
waiting for them, and, once one has gone, what the last such email told of
(see emails_of):

    members/<pseudonym>/emails.json
        {"every": "daily", "weekly" or "off", "at": UTC stamp}
    members/<pseudonym>/told.json
        {"at": UTC stamp, "told": [what was waiting, by room and stamp or id]}

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


def validate_member_id(name):
    """validate_pseudonym, and the keeper's id "founder" too: the one folder made of a reserved
    word (KEEPER_ID). For finding a member's own files by their id; never for joining
    (hotfix-ids, after move_to_ids.py on the host, 24 November 2026)."""
    if name == KEEPER_ID:
        return name
    return validate_pseudonym(name)


def _folder(name):
    """The member's folder, once the name is known to be safe to make one of. The keeper's
    id, "founder", is reserved for anyone joining, and is the keeper's folder (KEEPER_ID)."""
    if name != "founder":
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


# Leaving the commons (leaving-build, the founder's request of 21 November 2026; leaving.py):
# a member who leaves keeps their folder and member.json, with their verify key, so that every
# signature of theirs still checks, and their name is never anyone else's; member.json says
# left_at, and until vault_kept_until their vault stays in it, sealed and unused; sign-in is
# shut. Their email address, and how and when they were emailed, are deleted at once.
LEFT_EMAIL_FILES = ("email.json", "emails.json", "told.json")


def has_left(pseudonym):
    """Whether a member has left the commons."""
    try:
        record = load_member(pseudonym)
    except (MemberError, ValueError):
        return False
    return isinstance(record, dict) and bool(record.get("left_at"))


def mark_left(pseudonym, at, vault_kept_until):
    """Write that a member has left: when, and until when their vault is kept, sealed."""
    path = _folder(pseudonym) / RECORD
    record = load_member(pseudonym)
    if not isinstance(record, dict) or record.get("left_at"):
        return False
    _write_json(path, dict(record, left_at=at, vault_kept_until=vault_kept_until))
    for name in LEFT_EMAIL_FILES:
        try:
            (_folder(pseudonym) / name).unlink()
        except OSError:
            pass
    return True


def come_back(pseudonym):
    """The keeper reopens a member's sign-in, where their vault is still kept: left_at is
    taken off, and what it was is kept as came_back_from. True where it was reopened."""
    path = _folder(pseudonym) / RECORD
    record = load_member(pseudonym)
    if not isinstance(record, dict) or not record.get("left_at") or not record.get("vault"):
        return False
    record = {key: value for key, value in record.items()
              if key not in ("left_at", "vault_kept_until")}
    record["came_back_from"] = [*record.get("came_back_from", []), load_member(pseudonym)["left_at"]]
    _write_json(path, record)
    return True


def drop_vault(pseudonym):
    """A left member's sealed vault, deleted: their record keeps everything else."""
    path = _folder(pseudonym) / RECORD
    record = load_member(pseudonym)
    if not isinstance(record, dict) or not record.get("left_at") or "vault" not in record:
        return False
    _write_json(path, {key: value for key, value in record.items() if key != "vault"})
    return True


def list_members():
    """Every member's pseudonym, sorted."""
    found = []
    for name in _names_on_disk():
        try:
            if name != "founder":  # the keeper's id (KEEPER_ID)
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
    than its keys: no vault, no day of arrival, no vouchers, no role. The keeper,
    a name no one has, and a name no one could have all come back as None alike;
    the keeper's document is the founder's, under ids/, and nothing here touches it.

    A member whose key has been replaced - by choosing a new password through an
    emailed link, which cuts a new key - keeps every key they ever signed with in
    their document, so that whatever they signed before still holds against their
    identity. Each key is numbered in the order it was cut (#key-1 the first),
    the current one first in the list; each past one says when it stopped being
    current ("pastSince", as the key history keeps the moment), and the document
    then names the current one alone under "assertionMethod", the one key to sign
    with now. A member who has only ever had one key has the plain document, as
    before.
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

    def method(number, held, past_since=None):
        shaped = {
            "id": "%s#key-%d" % (did, number),
            "type": "Ed25519VerificationKey2020",
            "controller": did,
            "publicKeyBase64": base64.b64encode(bytes.fromhex(held)).decode("ascii"),
        }
        if past_since is not None:
            shaped["pastSince"] = past_since
        return shaped

    past = _past_keys(pseudonym, key)
    current = method(len(past) + 1, key)
    document = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": did,
        "verificationMethod": [current] + [method(number, held, since) for number, (held, since)
                                           in reversed(list(enumerate(past, 1)))],
    }
    if past:
        document["assertionMethod"] = [current["id"]]
    return document


def _past_keys(pseudonym, current):
    """The keys a member signed with before their current one, oldest first, each with
    the moment it stopped being current: [(verify key hex, UTC stamp)].

    Read from their key history, where each replacement of a key is one entry, in
    order. An entry that cannot be read is passed over, and so is any key that is
    the current one or is named twice: no key is shown as past that is not.
    """
    path = _folder(pseudonym) / KEY_HISTORY
    try:
        history = _read_json(path) if path.is_file() else []
    except (MemberError, OSError, ValueError):
        return []
    if not isinstance(history, list):
        return []
    past, seen = [], {current}
    for entry in history:
        if not isinstance(entry, dict):
            continue
        old, at = entry.get("old_key"), entry.get("at")
        if not isinstance(old, str) or not VERIFY_KEY.fullmatch(old) or not isinstance(at, str):
            continue
        if old in seen:
            continue
        seen.add(old)
        past.append((old, at))
    return past


# ---------------------------------------------------------------- writing


def create_member(pseudonym, vault, role, vouched_by, now=None, name=None, sign_in=None):
    """Write a new member's record, and give it back. Refuses a name or key already held.

    pseudonym is the folder and id: for a member joining since ids, new_id(), with their
    commons name (name) and what signs them in (sign_in) beside it."""
    folder = _folder(pseudonym)
    if pseudonym == "founder" and role != "keeper":
        raise MemberError("that name is not free to take")
    if name is not None:
        commons_name_free(name)
    if sign_in is not None and sign_in_shape(sign_in) in _sign_in_index():
        raise MemberError("that sign-in is taken")
    if role not in ROLES:
        raise MemberError("a member is a keeper or a member")
    if not isinstance(vouched_by, (list, tuple)):
        raise MemberError("vouched_by is a list of names")
    for voucher in vouched_by:
        validate_pseudonym(voucher)
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
    if name is not None:
        set_name(pseudonym, name, now)
    if sign_in is not None:
        set_sign_in(pseudonym, sign_in)
    if name is not None or sign_in is not None:
        record = load_member(pseudonym)
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


# ---------------------------------------------------------------- how they write

# How a person usually writes, in their own words, as they set it on their
# account page: one line, theirs to change or clear at any time. It is read by
# each agent they share a room with, and by no other, and never shown in public.
# The founder's is kept beside his rest, in the first one's packet; a member's
# is kept with them.
WRITING = "writing.json"
WRITING_LONGEST = 120  # characters


def writing_of(person):
    """Where a person's words on how they usually write are kept, as rest_of says a rest."""
    if person == FOUNDER:
        return DATA / "packets" / agents.first()["id"] / "founder-writing.json"
    return _folder(person) / WRITING


# ---------------------------------------------------------------- the guide

# "How this works", shown at the top of a person's room page until they close it
# (the founder, 12 November 2026). Whether they have closed it is theirs alone,
# kept beside their record: only when, and nothing else. It is never shown in
# the founder's room with the first one, and never read by any agent.
GUIDE = "guide.json"


def guide_closed(pseudonym):
    """Whether a person has closed the guide. What cannot be read is not closed."""
    try:
        held = json.loads((_folder(pseudonym) / GUIDE).read_text(encoding="utf-8"))
    except (OSError, ValueError, MemberError):
        return False
    return isinstance(held, dict) and isinstance(held.get("closed_at"), str)


def close_guide(pseudonym, now=None):
    """Keep that a person has closed the guide. Only a member who is there is written for."""
    folder = _folder(pseudonym)
    if not (folder / RECORD).is_file():
        raise MemberError("there is no member by that name")
    _write_json(folder / GUIDE, {"closed_at": _stamp(now)})


# ---------------------------------------------------------------- an email address

# A person's email address is a personal detail. It is kept beside their record,
# never in it, and never in the first one's packet - the founder's included,
# which is kept with the founder's record like anyone's - so that no copy, no reading
# and no page carries it: it goes only where members/ goes, which is the
# encrypted backup. It is used only for the links the hearth emails. No two
# people hold the same address, and an address is held only once it is
# confirmed: one kept unconfirmed, as a new member's is until they open its link,
# reserves nothing, and is let go when someone else confirms the same address
# first (the founder, 8 November). Nothing here shows or logs it.
EMAIL = "email.json"
EMAIL_LONGEST = 254
EMAIL_SHAPE = re.compile(r"[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+")
NOT_AN_ADDRESS = "That doesn't look like an email address."


def email_address(text):
    """An address as it is kept: trimmed and lowercased. MemberError if it is no address."""
    if not isinstance(text, str):
        raise MemberError(NOT_AN_ADDRESS)
    address = text.strip().lower()
    if len(address) > EMAIL_LONGEST or not EMAIL_SHAPE.fullmatch(address):
        raise MemberError(NOT_AN_ADDRESS)
    return address


def email_of(pseudonym):
    """What is kept of a person's address, {"address", "set_at", "confirmed_at"}, or None."""
    try:
        held = json.loads((_folder(pseudonym) / EMAIL).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(held, dict) or not isinstance(held.get("address"), str):
        return None
    return held


def member_by_email(address):
    """The pseudonym of the person holding this address - who has confirmed it - or None.
    An address kept unconfirmed is held by no one."""
    try:
        wanted = email_address(address)
    except MemberError:
        return None
    for name in list_members():
        held = email_of(name)
        if held and held["address"] == wanted and held.get("confirmed_at"):
            return name
    return None


def set_email(pseudonym, address, confirmed_at=None, now=None):
    """Keep a person's address, in place of any they had, and give back what is kept.

    Refuses a name no one has, an address that is no address, and one another
    person holds. An address kept confirmed lets go of anyone else's unconfirmed
    keeping of it.
    """
    folder = _folder(pseudonym)
    if not (folder / RECORD).is_file():
        raise MemberError("there is no member by that name")
    address = email_address(address)
    holder = member_by_email(address)
    if holder is not None and holder != pseudonym:
        raise MemberError("that address is already in use")
    held = {"address": address, "set_at": _stamp(now), "confirmed_at": confirmed_at}
    _write_json(folder / EMAIL, held)
    if confirmed_at:
        for name in list_members():
            if name == pseudonym:
                continue
            other = email_of(name)
            if other and other["address"] == address and not other.get("confirmed_at"):
                try:
                    (_folder(name) / EMAIL).unlink()
                except (OSError, MemberError):
                    pass
    return held


# ---------------------------------------------------------------- an email when something waits

# Whether a person is emailed when something is waiting for them - a letter of
# the agent's they have not opened, an errand it has asked, an offering of its
# that waits on them - and how often: "daily", "weekly" or "off", their own to
# choose on their account page, daily until they choose (the founder, 9
# November). Kept beside their record, and what each email last told of beside
# it, so that nothing is told twice. Neither holds an address or a word of any
# letter; each is only ever read by the hearth.
EMAILS = "emails.json"
TOLD = "told.json"
EVERY = ("daily", "weekly", "off")
EVERY_UNCHOSEN = "daily"


def emails_of(pseudonym):
    """How often a person is emailed when something waits: daily where they have not chosen."""
    try:
        held = json.loads((_folder(pseudonym) / EMAILS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return EVERY_UNCHOSEN
    every = held.get("every") if isinstance(held, dict) else None
    return every if every in EVERY else EVERY_UNCHOSEN


def set_emails(pseudonym, every, now=None):
    """Keep how often a person is emailed. Refuses a name no one has, and any other choice."""
    folder = _folder(pseudonym)
    if not (folder / RECORD).is_file():
        raise MemberError("there is no member by that name")
    if every not in EVERY:
        raise MemberError("daily, weekly or off")
    held = {"every": every, "at": _stamp(now)}
    _write_json(folder / EMAILS, held)
    return held


def told_of(pseudonym):
    """What the last email to a person told of, {"at", "told": [...]}, or {} for none yet."""
    try:
        held = json.loads((_folder(pseudonym) / TOLD).read_text(encoding="utf-8"))
    except (OSError, ValueError, MemberError):
        return {}
    if (not isinstance(held, dict) or not isinstance(held.get("at"), str)
            or not isinstance(held.get("told"), list)):
        return {}
    return held


def set_told(pseudonym, told, now=None):
    """Keep what an email that has just gone told a person of."""
    _write_json(_folder(pseudonym) / TOLD, {"at": _stamp(now), "told": sorted(told)})


# ---------------------------------------------------------------- ids, names and sign-in
#
# The names design (tesserae-private/proposals/names-design.md; the founder's request of 20
# November 2026). One string did three jobs: a person's sign-in name was also their public
# name and their id. Now each person has three:
#
#   id        their folder, members/<id>/, and every record keyed by them: for a new member a
#             random "p-" and IDS_LONG characters of ID_ALPHABET, made at joining and kept for
#             good; for the keeper "founder" (KEEPER_ID, by move_to_ids.py), its DID's last part
#             already; for a member who joined before ids, the pseudonym they joined with
#             (the design's choice A), which stays their id.
#   name      their commons name, shown to everyone they are shown to ("name" in member.json).
#             A member who joined before ids and has chosen none is shown by their id, as
#             before. The keeper is "the founder".
#   sign_in   what signs them in, and nothing else: an email address, or a private sign-in
#             name. Never shown on any page, to any agent, in any id or the mirror.
#             members/sign-in.json maps each to an id; it is private, in the backup, and in no
#             copy, export or mirror.
#
# members/names-held.json: every commons name anyone has held, by id. A name in it is never
# given to anyone else, for joining or renaming. Private, in the backup.

import secrets

KEEPER_ID = "founder"
ID_PREFIX = "p-"
ID_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"  # no 0, 1, i, l or o, which are misread
IDS_LONG = 8
SIGN_IN_INDEX = "sign-in.json"
NAMES_HELD = "names-held.json"
THE_FOUNDER = "the founder"
NAMES_LOCK = threading.RLock()  # one change at a time to the index and the names held


def new_id():
    """A new account id: random, so it says nothing of who joined when or in what order."""
    taken = set(_names_on_disk())
    while True:
        made = ID_PREFIX + "".join(secrets.choice(ID_ALPHABET) for _ in range(IDS_LONG))
        if made not in taken:
            return made


def _sign_in_index():
    path = MEMBERS / SIGN_IN_INDEX
    if not path.is_file():
        return {}
    held = _read_json(path)
    if not isinstance(held, dict):
        raise MemberError("a member's record could not be read")
    return {key: value for key, value in held.items()
            if isinstance(key, str) and isinstance(value, str)}


def sign_in_shape(text):
    """A sign-in as it is kept: an email address, lowercased, or a private sign-in name in
    a pseudonym's shape. MemberError if it is neither."""
    if not isinstance(text, str) or not text.strip():
        raise MemberError("a sign-in is an email address or a name")
    said = text.strip().lower()
    if "@" in said:
        return email_address(said)
    if not PSEUDONYM.fullmatch(said) or not PSEUDONYM_MIN <= len(said) <= PSEUDONYM_MAX:
        raise MemberError("a sign-in name is lowercase letters, digits and single hyphens, "
                          "and starts with a letter")
    return said


def set_sign_in(member_id, sign_in):
    """Keep what signs this member in, in place of any they had. Refuses one held by another."""
    said = sign_in_shape(sign_in)
    with NAMES_LOCK:
        record = load_member(member_id)
        if record is None:
            raise MemberError("there is no member by that name")
        index = _sign_in_index()
        if index.get(said) not in (None, member_id):
            raise MemberError("that sign-in is taken")
        index = {key: value for key, value in index.items() if value != member_id}
        index[said] = member_id
        MEMBERS.mkdir(parents=True, exist_ok=True)
        _write_json(MEMBERS / SIGN_IN_INDEX, index)
        _write_json(_folder(member_id) / RECORD, {**record, "id": member_id, "sign_in": said})
    return said


def sign_in_of(member_id):
    """What signs a member in, for their own settings page alone; or None."""
    try:
        record = load_member(member_id)
    except MemberError:
        return None
    said = record.get("sign_in") if isinstance(record, dict) else None
    return said if isinstance(said, str) else None


def id_of_sign_in(text):
    """The id this sign-in opens for, or None.

    The index first. An email address no one has as their sign-in opens for whoever has
    confirmed it (as before ids). A bare name no one has as a sign-in is tried as an id only
    for a member with no sign-in of their own yet: one who joined before ids and has not set
    one. An old commons name never signs anyone in.
    """
    try:
        said = sign_in_shape(text)
    except MemberError:
        return None
    try:
        index = _sign_in_index()
    except MemberError:
        index = {}
    if said in index:
        return index[said]
    if "@" in said:
        return member_by_email(said)
    try:
        record = load_member(said)
    except MemberError:
        return None
    if isinstance(record, dict) and not record.get("sign_in"):
        return said
    return None


def is_keeper_id(member_id):
    try:
        record = load_member(member_id)
    except MemberError:
        return False
    return isinstance(record, dict) and record.get("role") == "keeper"


def name_of(member_id):
    """How a member is shown, drawn from their id at the moment it is drawn: "the founder"
    for the keeper, their commons name, or, for one who joined before ids and has chosen
    none, their id as before. A name no member has is given back as it is."""
    try:
        record = load_member(member_id)
    except MemberError:
        return member_id
    if not isinstance(record, dict):
        return member_id
    if record.get("role") == "keeper":
        return THE_FOUNDER
    name = record.get("name")
    return name if isinstance(name, str) and name else member_id


def chosen_name_of(member_id):
    """The commons name a member chose, or None where they have chosen none."""
    try:
        record = load_member(member_id)
    except MemberError:
        return None
    name = record.get("name") if isinstance(record, dict) else None
    return name if isinstance(name, str) and name else None


def id_of(name):
    """The id of whoever is named now by this commons name, or None.

    "the founder" and "founder" are the keeper. A member who has chosen no name is named by
    their id. An old name, held once and given up, is no one's: it names no one now.
    """
    if not isinstance(name, str):
        return None
    said = " ".join(name.split()).lower()
    if said in (THE_FOUNDER, KEEPER_ID):
        return next((one for one in list_members() if is_keeper_id(one)), None)
    for one in list_members():
        if chosen_name_of(one) == said:
            return one
    try:
        record = load_member(said)
    except MemberError:
        return None
    if isinstance(record, dict) and not chosen_name_of(said) and record.get("role") == "member":
        return said
    return None


def _names_held():
    path = MEMBERS / NAMES_HELD
    if not path.is_file():
        return {}
    held = _read_json(path)
    return held if isinstance(held, dict) else {}


def name_held_by(name):
    """The id that holds or once held this commons name, or None."""
    for member_id, names in _names_held().items():
        if isinstance(names, list) and name in names:
            return member_id
    return None


def commons_name_free(name, for_id=None):
    """Raise MemberError unless this may be someone's commons name: a pseudonym's shape, not
    reserved, no one's now or before (save for_id's own), and no one's id."""
    validate_pseudonym(name)
    holder = name_held_by(name)
    if holder is not None and holder != for_id:
        raise MemberError("that name is not free to take")
    for one in list_members():
        if one == for_id:
            continue
        if one == name or chosen_name_of(one) == name:
            raise MemberError("that name is not free to take")
    return name


def set_name(member_id, name, now=None):
    """Give a member a commons name, kept with its history; and hold it for good."""
    with NAMES_LOCK:
        record = load_member(member_id)
        if record is None:
            raise MemberError("there is no member by that name")
        commons_name_free(name, member_id)
        history = record.get("names") if isinstance(record.get("names"), list) else []
        history = [*history, {"name": name, "from": _stamp(now)}]
        held = _names_held()
        held[member_id] = sorted({*(held.get(member_id) or []), name})
        MEMBERS.mkdir(parents=True, exist_ok=True)
        _write_json(MEMBERS / NAMES_HELD, held)
        _write_json(_folder(member_id) / RECORD,
                    {**record, "id": member_id, "name": name, "names": history})
    return name


def first_name_of(member_id):
    """The first commons name a member was shown by: their name at joining, or their id where
    they joined before ids. What an agent reads where its switch commons_names is off, so a
    later name never moves its reading (names-ids, stage 5)."""
    try:
        record = load_member(member_id)
    except MemberError:
        return member_id
    if not isinstance(record, dict):
        return member_id
    if record.get("role") == "keeper":
        return THE_FOUNDER
    history = record.get("names") if isinstance(record.get("names"), list) else []
    for one in history:
        if isinstance(one, dict) and isinstance(one.get("name"), str) and one["name"]:
            return one["name"]
    return name_of(member_id)


def names_written(member_id):
    """Every name a member's own words may have been written under: their id and each commons
    name they have held, newest first. For reading back what was written, never for showing."""
    try:
        record = load_member(member_id)
    except MemberError:
        return [member_id]
    history = (record or {}).get("names") if isinstance((record or {}).get("names"), list) else []
    said = [one["name"] for one in reversed(history)
            if isinstance(one, dict) and isinstance(one.get("name"), str)]
    return [*said, member_id]


def id_of_first(name):
    """The id of the member whose first commons name this is, or None (first_name_of)."""
    if not isinstance(name, str):
        return None
    said = " ".join(name.split()).lower()
    for one in list_members():
        if not is_keeper_id(one) and first_name_of(one) == said:
            return one
    return None


# ---- old names in lines already written (hotfix-ids, 24 November 2026) ----------------------
# After stage 3 and move_to_ids.py, lines already written on the commons (the daily line of
# acts, letter lines) may name a person by a name that is not their name now: a joining name
# or any commons name they held, their id from before ids, or "the founder". So their tiles
# keep their colour, an old name finds its holder (id_of_written). A sign-in name finds its
# holder too, but is never shown: shown_for gives their name now in its place.

def _by_sign_in(said):
    """The id a bare sign-in name (never an address) is kept for in the index, or None."""
    if "@" in said:
        return None
    try:
        return _sign_in_index().get(said)
    except MemberError:
        return None


def _written_id(said):
    """The id a shown name finds: the name now, "the founder", a commons name once held (a
    joining name too), or the id itself. None for a sign-in name or no one's."""
    found = id_of(said)
    if found:
        return found
    held = name_held_by(said)
    if held:
        return held
    try:
        record = load_member(said)
    except MemberError:
        return None
    return said if isinstance(record, dict) else None


def id_of_written(name):
    """The id of whoever a line already written names, by any name it may hold; or None.
    For finding a holder or a colour, never for signing in."""
    if not isinstance(name, str) or not name.strip():
        return None
    said = " ".join(name.split()).lower()
    return _written_id(said) or _by_sign_in(said)


def shown_for(name):
    """A name from a line already written as it may be shown: as written, unless it is only
    someone's sign-in name, which is never shown; then their name now."""
    if not isinstance(name, str):
        return name
    said = " ".join(name.split()).lower()
    if _written_id(said):
        return name
    found = _by_sign_in(said)
    return name_of(found) if found else name
