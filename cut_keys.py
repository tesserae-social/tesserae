import os
from pathlib import Path
from nacl.signing import SigningKey
import base64

name = "first"
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

print("Keys cut for:", name)
print("Public key (safe to share):", pub_b64)
print("Private key stored at:", priv_path, "- never share this, never commit it.")
