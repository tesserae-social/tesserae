#!/usr/bin/env python3
"""Open one encrypted backup of the record. Run on your own machine, never the server.

Usage:  python restore_backup.py <file.tar.gz.enc> <path to backup.key> <output dir>

A backup is the packet, the commons and the members' records whole, as they
stood at the hour it was taken: a tar.gz, encrypted with the backup key. This
decrypts one, unpacks it into a directory of your choosing, and prints what came
out. It refuses to unpack into a directory that already has anything in it, so
that a restore can never write over a record you still want.

It needs the cryptography package and nothing else:

    pip install cryptography

The key is the same BACKUP_KEY the hearth is given, kept in a file of its own:
one line, no quotes, nothing else. Keep that file somewhere that is neither the
bucket nor the machine - a backup nobody can open is not a backup. `flyctl
secrets list` shows the names of the hearth's secrets and never their values,
so the key cannot be read back off the server once it is set.

How to get a backup down
------------------------
The simplest way is the hearth itself: sign in and open /backups, which lists
what is in the bucket and hands one over.

There is no flyctl storage command needed for this. The bucket is plain
S3-compatible storage, so any S3 client will do, pointed at the endpoint. The
four values are the ones the hearth is given - BUCKET_NAME, AWS_ENDPOINT_URL_S3,
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY - from wherever you kept them when the
bucket was made (`flyctl storage create` printed them once).

With the AWS CLI:

    export AWS_ACCESS_KEY_ID=...  AWS_SECRET_ACCESS_KEY=...  AWS_REGION=auto
    aws s3 ls "s3://$BUCKET_NAME/backups/" --endpoint-url "$AWS_ENDPOINT_URL_S3"
    aws s3 cp "s3://$BUCKET_NAME/backups/tesserae-<stamp>.tar.gz.enc" . \\
        --endpoint-url "$AWS_ENDPOINT_URL_S3"

Or with boto3:

    import boto3, os
    s3 = boto3.client("s3", endpoint_url=os.environ["AWS_ENDPOINT_URL_S3"],
                      region_name=os.environ.get("AWS_REGION"))
    s3.download_file(os.environ["BUCKET_NAME"],
                     "backups/tesserae-<stamp>.tar.gz.enc",
                     "tesserae-<stamp>.tar.gz.enc")

Then:

    python restore_backup.py tesserae-<stamp>.tar.gz.enc backup.key restored/
"""

import io
import sys
import tarfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

USAGE = "Usage: python restore_backup.py <file.tar.gz.enc> <path to backup.key> <output dir>"


def refused(said):
    """Say why nothing was done, and give the exit code that says it too."""
    print(said)
    return 1


def safe(member):
    """Whether one member of the archive may be written out.

    A backup is written by the hearth and holds plain files under two known
    trees, so anything else - a path that climbs out of the output directory, a
    link, a device - is not unpacked, whatever the archive says.
    """
    name = member.name.replace("\\", "/")
    if name.startswith("/") or ".." in name.split("/"):
        return False
    return member.isfile() or member.isdir()


def empty_enough(out):
    """Whether the output directory may be written into: missing, or holding nothing."""
    if not out.exists():
        return True
    return out.is_dir() and not any(out.iterdir())


def restore(archive, key_file, out):
    """Decrypt one backup and unpack it. What went wrong, or nothing at all."""
    if not archive.is_file():
        return refused("No such backup: %s" % archive)
    if not key_file.is_file():
        return refused("No such key file: %s" % key_file)
    if not empty_enough(out):
        return refused("%s is not empty. Choose a directory that does not exist yet, or "
                       "an empty one: a restore never writes over what is already there."
                       % out)

    key = key_file.read_text(encoding="utf-8").strip()
    try:
        plain = Fernet(key).decrypt(archive.read_bytes())
    except InvalidToken:
        return refused("That key does not open this backup, or the file is damaged.")
    except (ValueError, TypeError) as trouble:
        return refused("That key cannot be read as a backup key: %s" % trouble)

    with tarfile.open(fileobj=io.BytesIO(plain), mode="r:gz") as bundle:
        members = [member for member in bundle.getmembers() if safe(member)]
        out.mkdir(parents=True, exist_ok=True)
        try:
            bundle.extractall(out, members=members, filter="data")
        except TypeError:  # Python before 3.12 has no filter; safe() is the whole guard there
            bundle.extractall(out, members=members)

    files = sorted(member.name for member in members if member.isfile())
    for name in files:
        print(name)
    print()
    print("%d files into %s" % (len(files), out.resolve()))
    return 0


def main(args):
    if len(args) != 3:
        print(USAGE)
        return 2
    return restore(Path(args[0]), Path(args[1]), Path(args[2]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
