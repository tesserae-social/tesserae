"""The key vault: sealing, the recovery phrase, and a key that stays the same.

Every seal here is made at argon2id's minimum cost so the suite stays quick; the
limits a vault is really made with are checked once, by name, and never paid for.
"""

import base64
import json

import pytest
from nacl.pwhash import argon2id

import vault
from vault import VaultError

PASSWORD = "correct horse battery"
NEW_PASSWORD = "a longer, newer password"
SECRET = b"thirty-two bytes of secret seed!"

DEFAULT_LIMITS = (vault.OPSLIMIT, vault.MEMLIMIT)


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


def flipped(sealed, field, at=0):
    raw = bytearray(base64.b64decode(sealed[field]))
    raw[at] ^= 0x01
    return {**sealed, field: base64.b64encode(bytes(raw)).decode("ascii")}


def refused(fn, *args):
    with pytest.raises(VaultError) as caught:
        fn(*args)
    return str(caught.value)


# ---------------------------------------------------------------- seal / unseal


def test_new_seals_default_to_the_interactive_limits():
    assert DEFAULT_LIMITS == (argon2id.OPSLIMIT_INTERACTIVE, argon2id.MEMLIMIT_INTERACTIVE)


def test_seal_is_json_and_round_trips():
    sealed = vault.seal(SECRET, PASSWORD)
    assert set(sealed) == {"v", "kdf", "salt", "opslimit", "memlimit", "nonce", "box"}
    assert sealed["v"] == 1 and sealed["kdf"] == "argon2id"
    assert sealed["opslimit"] == argon2id.OPSLIMIT_MIN
    assert sealed["memlimit"] == argon2id.MEMLIMIT_MIN
    assert vault.unseal(json.loads(json.dumps(sealed)), PASSWORD) == SECRET


def test_two_seals_of_the_same_secret_differ():
    a, b = vault.seal(SECRET, PASSWORD), vault.seal(SECRET, PASSWORD)
    assert a["salt"] != b["salt"] and a["nonce"] != b["nonce"] and a["box"] != b["box"]


def test_wrong_passphrase_fails_and_is_not_repeated():
    sealed = vault.seal(SECRET, PASSWORD)
    wrong = "not the password at all"
    message = refused(vault.unseal, sealed, wrong)
    assert wrong not in message and PASSWORD not in message


@pytest.mark.parametrize("field", ["box", "nonce", "salt"])
def test_a_flipped_byte_fails(field):
    sealed = vault.seal(SECRET, PASSWORD)
    refused(vault.unseal, flipped(sealed, field), PASSWORD)
    refused(vault.unseal, flipped(sealed, field, at=-1), PASSWORD)


def _malformed():
    good = vault.seal(SECRET, PASSWORD, argon2id.OPSLIMIT_MIN, argon2id.MEMLIMIT_MIN)
    without_box = {k: v for k, v in good.items() if k != "box"}
    return [
        None,
        "a string",
        [],
        {},
        without_box,
        {**good, "extra": 1},
        {**good, "v": 2},
        {**good, "kdf": "scrypt"},
        {**good, "salt": "not base64!!"},
        {**good, "salt": base64.b64encode(b"short").decode()},
        {**good, "nonce": base64.b64encode(b"short").decode()},
        {**good, "box": 12345},
        {**good, "opslimit": "2"},
        {**good, "opslimit": True},
        {**good, "opslimit": 0},
        {**good, "memlimit": 1},
        {**good, "memlimit": vault.MAX_MEMLIMIT + 1},
        {**good, "opslimit": vault.MAX_OPSLIMIT + 1},
    ]


@pytest.mark.parametrize("sealed", _malformed())
def test_malformed_dict_fails(sealed):
    assert PASSWORD not in refused(vault.unseal, sealed, PASSWORD)


def test_unsealing_is_capped_at_the_moderate_limits():
    assert vault.MAX_MEMLIMIT == argon2id.MEMLIMIT_MODERATE
    assert vault.MAX_OPSLIMIT == argon2id.OPSLIMIT_MODERATE
    assert vault.OPSLIMIT <= vault.MAX_OPSLIMIT and vault.MEMLIMIT <= vault.MAX_MEMLIMIT


@pytest.mark.parametrize("field, over", [
    ("memlimit", argon2id.MEMLIMIT_MODERATE + 1),
    ("memlimit", argon2id.MEMLIMIT_SENSITIVE),
    ("opslimit", argon2id.OPSLIMIT_MODERATE + 1),
    ("opslimit", argon2id.OPSLIMIT_SENSITIVE),
])
def test_limits_above_moderate_are_refused_before_any_work(monkeypatch, field, over):
    sealed = {**vault.seal(SECRET, PASSWORD), field: over}
    v, _, _ = vault.make_vault(PASSWORD)
    v = {**v, "by_password": {**v["by_password"], field: over}}

    def no_kdf(*args, **kwargs):
        raise AssertionError("the key was derived before the limits were checked")

    monkeypatch.setattr(vault.argon2id, "kdf", no_kdf)
    assert refused(vault.unseal, sealed, PASSWORD) == "this vault is malformed"
    assert refused(vault.unlock, v, PASSWORD) == "this vault is malformed"


def test_stored_limits_are_honored_when_unsealing(monkeypatch):
    # Sealed at a cost other than today's default: it still opens, by its own.
    ops, mem = argon2id.OPSLIMIT_MIN + 1, argon2id.MEMLIMIT_MIN * 2
    sealed = vault.seal(SECRET, PASSWORD, opslimit=ops, memlimit=mem)
    assert (sealed["opslimit"], sealed["memlimit"]) == (ops, mem)

    seen = []
    real = argon2id.kdf

    def spy(size, password, salt, opslimit, memlimit):
        seen.append((opslimit, memlimit))
        return real(size, password, salt, opslimit=opslimit, memlimit=memlimit)

    monkeypatch.setattr(vault.argon2id, "kdf", spy)
    assert vault.unseal(sealed, PASSWORD) == SECRET
    assert seen == [(ops, mem)]

    # And the limits are part of the key: change them and it no longer opens.
    refused(vault.unseal, {**sealed, "opslimit": argon2id.OPSLIMIT_MIN}, PASSWORD)


# ---------------------------------------------------------------- the phrase


def test_phrase_is_twelve_valid_words():
    phrase = vault.new_recovery_phrase()
    words = phrase.split(" ")
    assert len(words) == 12
    wordlist = set(vault._mnemonic.wordlist)
    assert all(w in wordlist for w in words)
    assert vault._mnemonic.check(phrase)
    assert vault._checked_phrase(phrase) == phrase


def test_a_bad_checksum_is_rejected():
    words = vault.new_recovery_phrase().split()
    wordlist = vault._mnemonic.wordlist
    # Swap the last word for others until one breaks the checksum.
    for candidate in wordlist:
        if candidate == words[-1]:
            continue
        broken = " ".join(words[:-1] + [candidate])
        if not vault._mnemonic.check(broken):
            break
    assert refused(vault._checked_phrase, broken) == "that phrase is not complete"


@pytest.mark.parametrize("phrase", [
    "",
    "abandon " * 11 + "about extra",  # thirteen words
    "abandon " * 10 + "about",        # eleven words
    "abandon " * 11 + "notaword",
])
def test_an_incomplete_phrase_is_rejected(phrase):
    assert refused(vault._checked_phrase, phrase) == "that phrase is not complete"


def test_normalization_accepts_extra_spaces_and_capitals():
    phrase = vault.new_recovery_phrase()
    messy = "  " + "   \t".join(w.upper() if i % 2 else w.title()
                               for i, w in enumerate(phrase.split())) + " \n"
    assert vault.normalize_phrase(messy) == phrase
    assert vault._checked_phrase(messy) == phrase


# ---------------------------------------------------------------- passwords


@pytest.mark.parametrize("pw", ["", "short", "123456789", "x" * 257, None, b"bytes password"])
def test_bad_passwords_are_refused_in_one_line(pw):
    message = refused(vault.check_password, pw)
    assert message and "\n" not in message


@pytest.mark.parametrize("pw", ["1234567890", "x" * 256, PASSWORD])
def test_good_passwords_pass(pw):
    vault.check_password(pw)


def test_make_vault_checks_the_password():
    refused(vault.make_vault, "short")


# ---------------------------------------------------------------- the vault


@pytest.fixture
def made():
    return vault.make_vault(PASSWORD)


def test_make_and_unlock(made):
    v, phrase, verify_hex = made
    assert set(v) == {"v", "verify_key", "by_password", "by_phrase"}
    assert v["verify_key"] == verify_hex
    key = vault.unlock(v, PASSWORD)
    assert key.verify_key.encode().hex() == verify_hex
    assert len(phrase.split()) == 12
    signed = key.sign(b"a line for the record")
    key.verify_key.verify(signed)


def test_an_existing_key_is_sealed_as_it_is():
    key = vault.cut_key()
    v, phrase = vault.vault_from_key(key, PASSWORD)
    assert set(v) == {"v", "verify_key", "by_password", "by_phrase"}
    assert v["verify_key"] == key.verify_key.encode().hex()
    assert bytes(vault.unlock(v, PASSWORD)) == bytes(key)
    recovered = vault.recover(v, phrase, NEW_PASSWORD)
    assert bytes(vault.unlock(recovered, NEW_PASSWORD)) == bytes(key)


def test_vault_from_key_checks_what_it_is_given():
    refused(vault.vault_from_key, vault.cut_key(), "short")
    refused(vault.vault_from_key, bytes(vault.cut_key()), PASSWORD)
    refused(vault.vault_from_key, None, PASSWORD)


def test_unlock_refuses_a_wrong_password(made):
    v, _, _ = made
    message = refused(vault.unlock, v, "the wrong password")
    assert "the wrong password" not in message and PASSWORD not in message


def test_the_phrase_does_not_open_the_password_copy(made):
    v, phrase, _ = made
    refused(vault.unlock, v, phrase)


def test_unlock_refuses_a_swapped_public_key(made):
    v, _, _ = made
    other = vault.cut_key().verify_key.encode().hex()
    refused(vault.unlock, {**v, "verify_key": other}, PASSWORD)


def test_recover_keeps_the_same_key(made):
    v, phrase, verify_hex = made
    messy = "  " + phrase.upper().replace(" ", "   ") + " "
    recovered = vault.recover(v, messy, NEW_PASSWORD)
    assert recovered["verify_key"] == verify_hex
    assert recovered["by_phrase"] == v["by_phrase"]
    assert bytes(vault.unlock(recovered, NEW_PASSWORD)) == bytes(vault.unlock(v, PASSWORD))
    refused(vault.unlock, recovered, PASSWORD)
    # The phrase still works a second time.
    again = vault.recover(recovered, phrase, "yet another password")
    assert again["verify_key"] == verify_hex


def test_recover_refuses_the_wrong_phrase(made):
    v, _, _ = made
    other = vault.new_recovery_phrase()
    message = refused(vault.recover, v, other, NEW_PASSWORD)
    assert other not in message and NEW_PASSWORD not in message


def test_recover_refuses_an_incomplete_phrase(made):
    v, phrase, _ = made
    words = phrase.split()
    assert refused(vault.recover, v, " ".join(words[:11]), NEW_PASSWORD) == \
        "that phrase is not complete"


def test_recover_checks_the_new_password(made):
    v, phrase, _ = made
    refused(vault.recover, v, phrase, "short")


def test_change_password_keeps_the_same_key(made):
    v, phrase, verify_hex = made
    changed = vault.change_password(v, PASSWORD, NEW_PASSWORD)
    assert changed["verify_key"] == verify_hex
    assert changed["by_phrase"] == v["by_phrase"]
    assert bytes(vault.unlock(changed, NEW_PASSWORD)) == bytes(vault.unlock(v, PASSWORD))
    # The old password stops working; the phrase still does.
    refused(vault.unlock, changed, PASSWORD)
    assert vault.recover(changed, phrase, "third password here")["verify_key"] == verify_hex


def test_change_password_needs_the_old_one(made):
    v, _, _ = made
    refused(vault.change_password, v, "not the old password", NEW_PASSWORD)
    refused(vault.change_password, v, PASSWORD, "short")


def test_the_vault_does_not_change_under_its_caller(made):
    v, phrase, _ = made
    before = json.dumps(v, sort_keys=True)
    vault.change_password(v, PASSWORD, NEW_PASSWORD)
    vault.recover(v, phrase, NEW_PASSWORD)
    assert json.dumps(v, sort_keys=True) == before


def test_no_secret_appears_in_the_stored_vault(made):
    v, phrase, _ = made
    seed = bytes(vault.unlock(v, PASSWORD))
    for stored in (v, vault.change_password(v, PASSWORD, NEW_PASSWORD),
                   vault.recover(v, phrase, NEW_PASSWORD)):
        text = json.dumps(stored)
        for secret in (
            PASSWORD, NEW_PASSWORD, phrase,
            seed.hex(), seed.hex().upper(),
            base64.b64encode(seed).decode(), base64.urlsafe_b64encode(seed).decode(),
            seed.decode("latin-1"),
        ):
            assert secret not in text
        # Nor any run of three phrase words.
        words = phrase.split()
        for i in range(len(words) - 2):
            assert " ".join(words[i:i + 3]) not in text
