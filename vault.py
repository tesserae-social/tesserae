"""The key vault: a member's signing key, kept sealed.

A member's private key is sealed twice over the same key: once by their password,
for every day, and once by a twelve-word recovery phrase, for the day the password
is lost. The phrase is shown once, when the vault is made, and never stored. Only
the public key is kept in the clear.

Pure functions only: nothing here touches a file, a route, a log or the screen,
and no error raised here carries a password, a phrase or a key.

    vault, phrase, verify_key_hex = make_vault(password)
    signing_key = unlock(vault, password)
    vault = change_password(vault, old_password, new_password)
    vault = recover(vault, phrase, new_password)
"""

import base64
import binascii

from mnemonic import Mnemonic
from nacl.exceptions import CryptoError
from nacl.pwhash import argon2id
from nacl.secret import SecretBox
from nacl.signing import SigningKey
from nacl.utils import random

VERSION = 1
KDF = "argon2id"

# What a new seal costs. The host has 1 GB of memory, so the interactive limits.
# Each sealed dict records the limits it was made with, so these may be raised
# later and every older vault still opens by its own.
OPSLIMIT = argon2id.OPSLIMIT_INTERACTIVE
MEMLIMIT = argon2id.MEMLIMIT_INTERACTIVE

# The most a sealed dict may ask of the host when it is opened: 256 MB, a quarter
# of the host's 1 GB. An edited dict must not be able to demand more than that.
MAX_OPSLIMIT = argon2id.OPSLIMIT_MODERATE
MAX_MEMLIMIT = argon2id.MEMLIMIT_MODERATE

PASSWORD_MIN = 10
PASSWORD_MAX = 256
PHRASE_WORDS = 12

_SEALED_KEYS = {"v", "kdf", "salt", "opslimit", "memlimit", "nonce", "box"}
_mnemonic = Mnemonic("english")


class VaultError(Exception):
    """The vault would not do what was asked. The message is safe to show."""


class _WontOpen(VaultError):
    """Well formed, but the passphrase is wrong or the box was tampered with."""


# ---------------------------------------------------------------- keys


def cut_key():
    """A new Ed25519 signing key, cut the way the founder's was."""
    return SigningKey.generate()


# ---------------------------------------------------------------- sealing


def _secret_bytes(passphrase):
    if isinstance(passphrase, str):
        return passphrase.encode("utf-8")
    if isinstance(passphrase, bytes):
        return passphrase
    raise VaultError("a passphrase must be text")


def _derive(passphrase, salt, opslimit, memlimit):
    return argon2id.kdf(
        SecretBox.KEY_SIZE, _secret_bytes(passphrase), salt,
        opslimit=opslimit, memlimit=memlimit,
    )


def _b64(raw):
    return base64.b64encode(raw).decode("ascii")


def _unb64(text, length):
    if not isinstance(text, str):
        raise VaultError("this vault is malformed")
    try:
        raw = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        raise VaultError("this vault is malformed") from None
    if length is not None and len(raw) != length:
        raise VaultError("this vault is malformed")
    return raw


def _limit(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise VaultError("this vault is malformed")
    return value


def seal(secret_bytes, passphrase, opslimit=None, memlimit=None):
    """Seal secret_bytes under passphrase; a dict that json.dumps can carry."""
    if not isinstance(secret_bytes, bytes):
        raise VaultError("only bytes can be sealed")
    opslimit = OPSLIMIT if opslimit is None else opslimit
    memlimit = MEMLIMIT if memlimit is None else memlimit
    salt = random(argon2id.SALTBYTES)
    box = SecretBox(_derive(passphrase, salt, opslimit, memlimit))
    encrypted = box.encrypt(secret_bytes)
    return {
        "v": VERSION,
        "kdf": KDF,
        "salt": _b64(salt),
        "opslimit": opslimit,
        "memlimit": memlimit,
        "nonce": _b64(encrypted.nonce),
        "box": _b64(encrypted.ciphertext),
    }


def unseal(sealed, passphrase):
    """The bytes sealed under passphrase, by the limits the seal recorded.

    Raises VaultError on a wrong passphrase, a tampered box, or a malformed dict.
    """
    if not isinstance(sealed, dict) or set(sealed) != _SEALED_KEYS:
        raise VaultError("this vault is malformed")
    if sealed["v"] != VERSION or sealed["kdf"] != KDF:
        raise VaultError("this vault is malformed")
    salt = _unb64(sealed["salt"], argon2id.SALTBYTES)
    nonce = _unb64(sealed["nonce"], SecretBox.NONCE_SIZE)
    ciphertext = _unb64(sealed["box"], None)
    opslimit = _limit(sealed["opslimit"], argon2id.OPSLIMIT_MIN, MAX_OPSLIMIT)
    memlimit = _limit(sealed["memlimit"], argon2id.MEMLIMIT_MIN, MAX_MEMLIMIT)
    try:
        key = _derive(passphrase, salt, opslimit, memlimit)
        return SecretBox(key).decrypt(ciphertext, nonce)
    except VaultError:
        raise
    except (CryptoError, ValueError, TypeError):
        raise _WontOpen("that does not open this vault") from None


# ---------------------------------------------------------------- the phrase


def new_recovery_phrase():
    """Twelve English BIP39 words: 128 bits of entropy and a checksum."""
    return _mnemonic.generate(strength=128)


def normalize_phrase(phrase):
    """Lowercased, trimmed, one space between words."""
    if not isinstance(phrase, str):
        raise VaultError("that phrase is not complete")
    return " ".join(phrase.lower().split())


def _checked_phrase(phrase):
    phrase = normalize_phrase(phrase)
    try:
        whole = len(phrase.split()) == PHRASE_WORDS and _mnemonic.check(phrase)
    except (ValueError, LookupError):
        whole = False
    if not whole:
        raise VaultError("that phrase is not complete")
    return phrase


# ---------------------------------------------------------------- passwords


def check_password(pw):
    """Raise VaultError, with a one-line reason, unless pw will do."""
    if not isinstance(pw, str):
        raise VaultError("a password must be text")
    if len(pw) < PASSWORD_MIN:
        raise VaultError(f"a password needs at least {PASSWORD_MIN} characters")
    if len(pw) > PASSWORD_MAX:
        raise VaultError(f"a password can be at most {PASSWORD_MAX} characters")


# ---------------------------------------------------------------- the vault


def _checked_vault(vault):
    if (
        not isinstance(vault, dict)
        or set(vault) != {"v", "verify_key", "by_password", "by_phrase"}
        or vault["v"] != VERSION
        or not isinstance(vault["verify_key"], str)
    ):
        raise VaultError("this vault is malformed")
    return vault


def _open(vault, which, passphrase, refusal):
    try:
        seed = unseal(vault[which], passphrase)
    except _WontOpen:
        raise VaultError(refusal) from None
    try:
        key = SigningKey(seed)
    except (ValueError, TypeError, CryptoError):
        raise VaultError("this vault is malformed") from None
    if key.verify_key.encode().hex() != vault["verify_key"]:
        raise VaultError("this vault is malformed")
    return key


def _vault(key, by_password, by_phrase):
    return {
        "v": VERSION,
        "verify_key": key.verify_key.encode().hex(),
        "by_password": by_password,
        "by_phrase": by_phrase,
    }


def make_vault(password):
    """(vault, phrase, verify_key_hex). The phrase is handed back once, never kept."""
    check_password(password)
    key = cut_key()
    phrase = new_recovery_phrase()
    seed = bytes(key)
    vault = _vault(key, seal(seed, password), seal(seed, phrase))
    return vault, phrase, vault["verify_key"]


def unlock(vault, password):
    """The SigningKey the vault keeps, opened by password."""
    return _open(_checked_vault(vault), "by_password", password,
                 "that password does not open this vault")


def change_password(vault, old_password, new_password):
    """A new vault: the same key, sealed by new_password. The phrase copy is kept."""
    _checked_vault(vault)
    check_password(new_password)
    key = unlock(vault, old_password)
    return _vault(key, seal(bytes(key), new_password), dict(vault["by_phrase"]))


def recover(vault, phrase, new_password):
    """A new vault: the same key, opened by the phrase, sealed by new_password."""
    _checked_vault(vault)
    phrase = _checked_phrase(phrase)
    check_password(new_password)
    key = _open(vault, "by_phrase", phrase, "that phrase does not open this vault")
    return _vault(key, seal(bytes(key), new_password), dict(vault["by_phrase"]))
