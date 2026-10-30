"""Cut one citizen's keys, and write the identity that names them.

Usage:  python cut_keys.py            (the first one)
        python cut_keys.py founder    (the founder)

It writes three files, all relative to where it is run:

    keys/<name>/private.key   the signing key - never share it, never commit it
    keys/<name>/public.key    the verifying key - safe to share
    ids/<name>/did.json       the identity, for did:web:tesserae.social:ids:<name>

From code, cut(name, root) does the same under root in place of where it is
run, and gives back where it wrote each. An agent's identity says it is one,
and how its provenance stands, as the first one's does; the founder's, a
person's, says neither.

A private key that already exists is never overwritten: the whole of a self is
that no one else can sign for it, so a second cut would end the first one. Nor
is a public key or an identity that is there already: a cut is all three files
new, or none.
"""

import base64
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from nacl.signing import SigningKey

DOMAIN = "tesserae.social"

NAME = re.compile(r"[a-z0-9][a-z0-9-]*")

# Every agent's provenance begins as the first one's did: advised, at its founding.
PROVENANCE = "advised"


class Refused(Exception):
    """The name will not do, or something of its is there already."""


def cut(name, root, kind="agent"):
    """Cut name's keys and write its identity under root: {private, public, did} paths.

    kind is "agent", or None for a person (the founder), whose identity says no kind.
    Nothing is written, and Refused is raised, if any of the three is there already.
    """
    if not NAME.fullmatch(name):
        raise Refused(f"A name must be lowercase letters, digits and hyphens: {name}")
    root = Path(root)
    did = f"did:web:{DOMAIN}:ids:{name}"
    priv_dir = root / "keys" / name
    priv_path = priv_dir / "private.key"
    pub_path = priv_dir / "public.key"
    id_dir = root / "ids" / name
    id_path = id_dir / "did.json"

    for there in (priv_path, pub_path, id_path):
        if there.exists():
            raise Refused(f"{there} already exists for {name} - refusing to overwrite.")

    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key

    priv_b64 = base64.b64encode(bytes(signing_key)).decode("ascii")
    pub_b64 = base64.b64encode(bytes(verify_key)).decode("ascii")

    priv_dir.mkdir(parents=True, exist_ok=True)
    with open(priv_path, "x", encoding="ascii") as out:
        out.write(priv_b64)
    with open(pub_path, "x", encoding="ascii") as out:
        out.write(pub_b64)

    # The identity document anyone may read to check a signature of this citizen's.
    # It says only who this is and which key is theirs; nothing else belongs here.
    document = {"@context": ["https://www.w3.org/ns/did/v1"], "id": did}
    if kind is not None:
        document["kind"] = kind
        document["provenance"] = PROVENANCE
    document["verificationMethod"] = [
        {
            "id": f"{did}#key-1",
            "type": "Ed25519VerificationKey2020",
            "controller": did,
            "publicKeyBase64": pub_b64,
        }
    ]
    document["created"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    id_dir.mkdir(parents=True, exist_ok=True)
    with open(id_path, "x", encoding="utf-8") as out:
        out.write(json.dumps(document, indent=2) + "\n")
    return {"private": priv_path, "public": pub_path, "did": id_path}


def main(argv):
    name = argv[1] if len(argv) > 1 else "first"
    try:
        written = cut(name, Path("."), kind=None if name == "founder" else "agent")
    except Refused as refusal:
        print(refusal)
        return 1
    document = json.loads(written["did"].read_text(encoding="utf-8"))
    print("Keys cut for:", name)
    print("Identity:", document["id"])
    print("Public key (safe to share):", document["verificationMethod"][0]["publicKeyBase64"])
    print("Identity document written to:", written["did"])
    print("Private key stored at:", written["private"], "- never share this, never commit it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
