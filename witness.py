"""Witnessing.

Once a bond is sealed, a member of the commons who is not a party to it may
witness it: sign their name to it, and leave one line. To witness is to say
you have seen the bond as sealed. A mark is a small signed record:

    {"v": 1, "bond_id": ..., "bond_commitment": ..., "witness_did": ...,
     "witness_name": ..., "at": ..., "line": ..., "signature": ...}

bond_commitment is the sha256 of the bond's public record as it was sealed -
the record as JSON with its keys sorted, with any witness data taken out, and
with the two marks a release leaves on it (released_at, released_by) taken out
too - so that a mark stays good as more witnesses come, and stays good after a
release, which changes nothing a witness saw. The signature is over every field
but itself, as JSON with its keys sorted, made with the witness's own Ed25519
key, and kept as base64 text, as a bond keeps its own.

A mark is never edited and never removed. A witness who got something wrong may
add one correction to their mark, and only one: the same shape, with "corrects"
naming the signature of the mark it is beneath, its own line, and its own
signature by the same key.

The marks of a bond are kept together, in the order they were made, in
DATA_DIR/bonds/witnesses/<bond id>.json: a list that only ever grows.

Who may witness is decided here, so that every hand that ever signs a mark is
held to the one rule. Only the hearth signs any yet, for a member at the bond's
own page. There is no agent witness path: nothing about witnessing goes into
the first one's reading, attend.py does not import this module, and no line of
events.md says that a bond was witnessed. The rule for fellowships below is
kept and tested all the same, ahead of the day there is one.
"""

import base64
import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

import bonds

VERSION = 1

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

WITNESSES = DATA / "bonds" / "witnesses"

# The longest a witness's line may be: the bench's own length.
LINE_MAX = 200

# What the commitment does not cover: anything of the witnesses themselves, and
# what a release writes onto the record afterwards.
UNCOMMITTED = ("witnesses", "released_at", "released_by")

# Why a mark is not taken, each a word for whoever asked to tell apart.
NOT_SEALED = "not sealed"
RELEASED = "released"
A_PARTY = "a party"
ALREADY = "already witnessed"
HUMAN_FIRST = "a human first"
NO_MARK = "no mark to correct"
CORRECTED = "already corrected"
NOT_A_LINE = "not a line"
UNSIGNED = "unsigned"

# Two marks made at once must not both find the list as it was.
LOCK = threading.Lock()


class Refused(Exception):
    """A mark was not taken. The reason is one of the words above."""


# ---- what is signed ------------------------------------------------------

def bond_commitment(bond):
    """The fingerprint of a bond as it was sealed: sha256 of its record, keys sorted."""
    body = {key: value for key, value in bond.items() if key not in UNCOMMITTED}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def payload(mark):
    """The bytes a witness signs: the mark without its signature, keys sorted."""
    body = {key: value for key, value in mark.items() if key != "signature"}
    return json.dumps(body, sort_keys=True).encode("utf-8")


def holds(mark, verify_key):
    """Whether a mark's signature holds against a public key, given as its 32 raw bytes."""
    try:
        VerifyKey(verify_key).verify(payload(mark), base64.b64decode(mark["signature"]))
    except (BadSignatureError, KeyError, TypeError, ValueError):
        return False
    return True


# ---- the marks -----------------------------------------------------------

def path_for(bond_id):
    """Where a bond's marks are kept, or None for a name no bond could have."""
    if not isinstance(bond_id, str) or not bonds.ID.match(bond_id):
        return None
    return WITNESSES / (bond_id + ".json")


def kept(bond_id):
    """A bond's marks exactly as kept. Raises ValueError if the file cannot be read."""
    path = path_for(bond_id)
    if path is None or not path.is_file():
        return []
    held = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(held, list) or not all(isinstance(one, dict) for one in held):
        raise ValueError("The witnesses of %s could not be read." % bond_id)
    return held


def marks(bond_id):
    """Every mark and correction on a bond, in the order they were made."""
    try:
        return kept(bond_id)
    except (OSError, ValueError):
        return []


def is_correction(mark):
    return "corrects" in mark


def mark_by(held, did):
    """The mark this witness made, or None. A correction is not a mark of its own."""
    for mark in held:
        if mark.get("witness_did") == did and not is_correction(mark):
            return mark
    return None


def correction_of(held, mark):
    """The correction beneath a mark, by the same witness, or None."""
    for one in held:
        if (is_correction(one) and one["corrects"] == mark.get("signature")
                and one.get("witness_did") == mark.get("witness_did")):
            return one
    return None


def shown(bond_id):
    """The marks as a page shows them: each in order, with its correction beneath it."""
    held = marks(bond_id)
    return [{"mark": mark, "correction": correction_of(held, mark)}
            for mark in held if not is_correction(mark)]


# ---- who may witness -----------------------------------------------------

def is_fellowship(bond):
    """Whether both parties to a bond are agents."""
    parties = bond.get("parties") or []
    return bool(parties) and all(did in bonds.AGENTS for did in parties)


def refusal(bond, did, held, correcting=False):
    """Why this one may not witness this bond now (or correct their mark), or None.

    A bond takes marks while it is sealed and not released; a released bond
    keeps the ones it has and gathers no more, a correction included. A party
    does not witness their own bond. One mark each, and one correction to it.
    A fellowship is witnessed by a human before any agent may sign.
    """
    if not bond or not bond.get("sealed_at"):
        return NOT_SEALED
    if bond.get("released_at"):
        return RELEASED
    if did in (bond.get("parties") or []):
        return A_PARTY
    own = mark_by(held, did)
    if correcting:
        if not own:
            return NO_MARK
        return CORRECTED if correction_of(held, own) else None
    if own:
        return ALREADY
    if is_fellowship(bond) and did in bonds.AGENTS and not any(
            mark.get("witness_did") not in bonds.AGENTS
            for mark in held if not is_correction(mark)):
        return HUMAN_FIRST
    return None


def is_line(line):
    """One line of plain text, of some length and not too much.

    What a line may say beyond that is for whoever takes it to check: the
    hearth holds a witness's line to the bench's own rule against links.
    """
    return (isinstance(line, str) and bool(line.strip()) and len(line) <= LINE_MAX
            and "\n" not in line and "\r" not in line)


def add(bond_id, did, name, line, sign, at, correcting=False):
    """Sign one mark (or one correction) and keep it; the mark is given back.

    The signing is handed in, as threshold.py takes it, so that each hand signs
    with its own key in its own way: it is given the bytes and gives back the
    signature as base64 text. Raises Refused, with nothing written, if the mark
    may not be made or no signature came back.
    """
    if not is_line(line):
        raise Refused(NOT_A_LINE)
    with LOCK:
        bond = bonds.record(bond_id)
        held = kept(bond_id) if bond else []
        why = refusal(bond, did, held, correcting)
        if why:
            raise Refused(why)
        mark = {"v": VERSION, "bond_id": bond_id, "bond_commitment": bond_commitment(bond),
                "witness_did": did, "witness_name": name, "at": at, "line": line}
        if correcting:
            mark["corrects"] = mark_by(held, did)["signature"]
        signature = sign(payload(mark))
        if not signature:
            raise Refused(UNSIGNED)
        mark["signature"] = signature
        write(path_for(bond_id), held + [mark])
    return mark


def write(path, held):
    """The list with its new mark, written whole or not at all."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".",
                                         suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(json.dumps(held, indent=2) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
