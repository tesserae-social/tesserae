#!/usr/bin/env python3
"""Make the founder member one, the keeper. Run once, on the host, by hand.

Usage:  flyctl ssh console, then:  python setup_keeper.py

It asks for a pseudonym and a password, seals the founder's own signing key -
the FOUNDER_KEY the hearth is given - in a vault under that password, and writes
the one member record. It shows the twelve-word recovery phrase once, and waits
until it has been written down.

Nothing it is given is kept anywhere else: the password, the key and the phrase
are never printed (save the phrase, the once), logged or written to a file, and
the member record is the only file it writes. It refuses, and writes nothing, if
there is a keeper already, or if the key it is handed is not the founder's.
"""

import base64
import getpass
import json
import os
import sys
from pathlib import Path

import members
import vault
from members import MemberError
from vault import VaultError

REPO = Path(__file__).resolve().parent

# The founder's identity document, baked into the image beside this script.
FOUNDER_DID = REPO / "ids" / "founder" / "did.json"

WRITTEN = "written"


class Refused(Exception):
    """Nothing was done, and this says why. The message is safe to show."""


# ---------------------------------------------------------------- the checks


def a_keeper_already():
    """The pseudonym of a keeper, if there is one."""
    for name in members.list_members():
        record = members.load_member(name)
        if isinstance(record, dict) and record.get("role") == "keeper":
            return name
    return None


def founder_key(environ):
    """The founder's signing key, out of FOUNDER_KEY as the hearth reads it."""
    given = environ.get("FOUNDER_KEY", "").strip()
    if not given:
        raise Refused("FOUNDER_KEY is not set here, so there is no key to keep. "
                      "Nothing was written.")
    try:
        return vault.key_from_text(given)
    except VaultError:
        raise Refused("FOUNDER_KEY could not be read as a key. Nothing was written.") from None


def did_public_key(path):
    """The verifying key the identity document names, as base64."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        return document["verificationMethod"][0]["publicKeyBase64"]
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        raise Refused("The founder's identity document at %s could not be read. "
                      "Nothing was written." % path) from None


def check_key_is_founders(key, did_path):
    public = base64.b64encode(key.verify_key.encode()).decode("ascii")
    if public != did_public_key(did_path):
        raise Refused("FOUNDER_KEY is not the key ids/founder/did.json names. "
                      "Nothing was written.")


# ---------------------------------------------------------------- the asking


def ask_pseudonym(ask, say):
    while True:
        name = ask("Your pseudonym: ").strip()
        try:
            members.validate_pseudonym(name)
            if members.load_member(name) is not None:
                raise MemberError("that name is already taken")
        except MemberError as reason:
            say("That will not do: %s." % reason)
            continue
        return name


def ask_password(ask_secret, say):
    while True:
        password = ask_secret("A password (not shown as you type): ")
        try:
            vault.check_password(password)
        except VaultError as reason:
            say("That will not do: %s." % reason)
            continue
        if ask_secret("The same password again: ") != password:
            say("The two did not match. Once more.")
            continue
        return password


def show_phrase(phrase, ask, say):
    say("")
    say("Your twelve words:")
    say("")
    say("    " + phrase)
    say("")
    say("Write these on paper. They open your key if you forget your password.")
    say("They are shown only now.")
    say("")
    while ask('Type "%s" once they are on paper: ' % WRITTEN).strip().lower() != WRITTEN:
        pass


# ---------------------------------------------------------------- the whole of it


def setup_keeper(ask, ask_secret, say, environ=os.environ, did_path=FOUNDER_DID):
    """Make member one. The exit code: 0 once it is done, 1 if it was refused."""
    try:
        keeper = a_keeper_already()
        if keeper is not None:
            raise Refused("There is a keeper already, %s. Nothing was written." % keeper)
        # the key is checked before anything is asked, so no one types a
        # password into a setup that was always going to be refused
        key = founder_key(environ)
        check_key_is_founders(key, did_path)

        pseudonym = ask_pseudonym(ask, say)
        password = ask_password(ask_secret, say)

        sealed, phrase = vault.vault_from_key(key, password)
        members.create_member(pseudonym, sealed, role="keeper", vouched_by=[])
    except Refused as reason:
        say(str(reason))
        return 1
    except (MemberError, VaultError) as reason:
        say("It could not be done: %s. Nothing was written." % reason)
        return 1

    show_phrase(phrase, ask, say)
    say("Done. You are member one, as %s." % pseudonym)
    return 0


def main():
    try:
        return setup_keeper(input, getpass.getpass, print)
    except (KeyboardInterrupt, EOFError):
        print()
        print("Stopped.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
