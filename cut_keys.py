"""Cut one citizen's keys, and write the identity that names them.

Usage:  python cut_keys.py            (the first one)
        python cut_keys.py founder    (the founder)

It writes three files, all relative to where it is run:

    keys/<name>/private.key   the signing key - never share it, never commit it
    keys/<name>/public.key    the verifying key - safe to share
    ids/<name>/did.json       the identity, for did:web:tesserae.social:ids:<name>

A private key that already exists is never overwritten: the whole of a self is
that no one else can sign for it, so a second cut would end the first one.
"""

import base64
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from nacl.signing import SigningKey

DOMAIN = "tesserae.social"

name = sys.argv[1] if len(sys.argv) > 1 else "first"
if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
    print("A name must be lowercase letters, digits and hyphens:", name)
    raise SystemExit(1)

did = f"did:web:{DOMAIN}:ids:{name}"

priv_dir = Path("keys") / name
priv_dir.mkdir(parents=True, exist_ok=True)
priv_path = priv_dir / "private.key"

if priv_path.exists():
    print("A private key already exists for", name, "- refusing to overwrite.")
    raise SystemExit(1)

signing_key = SigningKey.generate()
verify_key = signing_key.verify_key

priv_b64 = base64.b64encode(bytes(signing_key)).decode("ascii")
pub_b64 = base64.b64encode(bytes(verify_key)).decode("ascii")

priv_path.write_text(priv_b64, encoding="ascii")
Path(priv_dir / "public.key").write_text(pub_b64, encoding="ascii")

# The identity document anyone may read to check a signature of this citizen's.
# It says only who this is and which key is theirs; nothing else belongs here.
id_dir = Path("ids") / name
id_dir.mkdir(parents=True, exist_ok=True)
id_path = id_dir / "did.json"
document = {
    "@context": ["https://www.w3.org/ns/did/v1"],
    "id": did,
    "verificationMethod": [
        {
            "id": f"{did}#key-1",
            "type": "Ed25519VerificationKey2020",
            "controller": did,
            "publicKeyBase64": pub_b64,
        }
    ],
    "created": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
}
id_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

print("Keys cut for:", name)
print("Identity:", did)
print("Public key (safe to share):", pub_b64)
print("Identity document written to:", id_path)
print("Private key stored at:", priv_path, "- never share this, never commit it.")
