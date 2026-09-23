"""Making member one: who may be made, from which key, and what is shown and kept.

The key is a throwaway cut for each test, handed over as FOUNDER_KEY and named
in an identity document under the test's own temporary directory; the real
founder's key and ids/founder/did.json are never read. Every question the
script asks is answered from a list, and every line it says is kept.
"""

import base64
import importlib
import json
import sys

import pytest
from nacl.pwhash import argon2id
from nacl.signing import SigningKey

import vault
from conftest import write

PASSWORD = "a password for member one"


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


def seed_of(key):
    return base64.b64encode(bytes(key)).decode("ascii")


def did_for(key):
    return {"verificationMethod": [{
        "type": "Ed25519VerificationKey2020",
        "publicKeyBase64": base64.b64encode(key.verify_key.encode()).decode("ascii"),
    }]}


@pytest.fixture
def key():
    return SigningKey.generate()


@pytest.fixture
def did_path(tmp_path, key):
    return write(tmp_path / "ids" / "founder" / "did.json", json.dumps(did_for(key)))


@pytest.fixture
def setup(env, monkeypatch, key):
    """setup_keeper.py, and the members.py it writes with, read afresh against DATA_DIR."""
    monkeypatch.setenv("FOUNDER_KEY", seed_of(key))
    for name in ("members", "setup_keeper"):
        sys.modules.pop(name, None)
    return importlib.import_module("setup_keeper")


class Console:
    """The person at the terminal: answers given in order, and every line kept."""

    def __init__(self, answers=(), secrets=()):
        self.answers = list(answers)
        self.secrets = list(secrets)
        self.lines = []
        self.asked = []

    def ask(self, prompt):
        self.asked.append(prompt)
        assert self.answers, "it asked for more than it was given: %r" % prompt
        return self.answers.pop(0)

    def ask_secret(self, prompt):
        self.asked.append(prompt)
        assert self.secrets, "it asked for more secrets than it was given: %r" % prompt
        return self.secrets.pop(0)

    def say(self, line=""):
        self.lines.append(str(line))

    @property
    def said(self):
        return "\n".join(self.lines)


def run(setup, did_path, console):
    code = setup.setup_keeper(console.ask, console.ask_secret, console.say, did_path=did_path)
    assert not console.answers and not console.secrets, "some answers were never asked for"
    return code


def files_in(root):
    return {path for path in root.rglob("*") if path.is_file()}


# ---- the whole of it ------------------------------------------------------

def test_member_one_is_made_a_keeper_of_the_founders_key(setup, did_path, key, data_dir,
                                                         tmp_path):
    before = files_in(tmp_path)
    console = Console(["ada", "written"], [PASSWORD, PASSWORD])
    assert run(setup, did_path, console) == 0

    record = setup.members.load_member("ada")
    assert record["role"] == "keeper"
    assert record["vouched_by"] == []
    assert record["verify_key"] == key.verify_key.encode().hex()
    assert bytes(vault.unlock(record["vault"], PASSWORD)) == bytes(key)
    assert setup.members.list_members() == ["ada"]

    # the one file written is the record
    assert files_in(tmp_path) - before == {data_dir / "members" / "ada" / "member.json"}
    assert console.lines[-1] == "Done. You are member one, as ada."


def test_the_phrase_is_shown_once_and_the_password_never(setup, did_path, key):
    console = Console(["ada", "written"], [PASSWORD, PASSWORD])
    assert run(setup, did_path, console) == 0

    record = setup.members.load_member("ada")
    [phrase] = [line.strip() for line in console.lines
                if len(line.split()) == vault.PHRASE_WORDS and line.startswith("    ")]
    # it is the phrase that opens this vault, not merely twelve words
    recovered = vault.recover(record["vault"], phrase, "another password entirely")
    assert bytes(vault.unlock(recovered, "another password entirely")) == bytes(key)

    assert console.said.count(phrase) == 1
    assert PASSWORD not in console.said
    assert seed_of(key) not in console.said
    assert "write these on paper" in console.said.lower()
    assert "if you forget your password" in console.said
    assert "shown only now" in console.said
    # and after the phrase, only the one line
    after = console.lines[[line.strip() for line in console.lines].index(phrase) + 1:]
    assert [line for line in after if line.strip() and "paper" not in line
            and "shown only now" not in line] == ["Done. You are member one, as ada."]


# ---- what it refuses -------------------------------------------------------

def test_it_refuses_when_there_is_a_keeper_already(setup, did_path, data_dir):
    other, _ = vault.vault_from_key(SigningKey.generate(), PASSWORD)
    setup.members.create_member("bram", other, role="keeper", vouched_by=[])
    before = files_in(data_dir)

    console = Console()
    assert run(setup, did_path, console) == 1
    assert "There is a keeper already" in console.said
    assert console.asked == []
    assert files_in(data_dir) == before


def test_it_refuses_without_a_founder_key(setup, did_path, data_dir, monkeypatch):
    monkeypatch.delenv("FOUNDER_KEY")
    console = Console()
    assert run(setup, did_path, console) == 1
    assert "FOUNDER_KEY is not set" in console.said
    assert console.asked == []
    assert not (data_dir / "members").exists()


def test_it_refuses_a_founder_key_that_is_not_a_key(setup, did_path, data_dir, monkeypatch):
    monkeypatch.setenv("FOUNDER_KEY", "not a key at all")
    console = Console()
    assert run(setup, did_path, console) == 1
    assert "could not be read as a key" in console.said
    assert "not a key at all" not in console.said
    assert not (data_dir / "members").exists()


def test_it_refuses_a_key_the_identity_document_does_not_name(setup, did_path, data_dir, key):
    stranger = SigningKey.generate()
    did_path.write_text(json.dumps(did_for(stranger)), encoding="utf-8")

    console = Console()
    assert run(setup, did_path, console) == 1
    assert "is not the key ids/founder/did.json names" in console.said
    assert seed_of(key) not in console.said
    assert console.asked == []
    assert not (data_dir / "members").exists()


def test_it_refuses_an_identity_document_it_cannot_read(setup, tmp_path, data_dir):
    console = Console()
    assert run(setup, tmp_path / "nowhere" / "did.json", console) == 1
    assert "could not be read" in console.said
    assert not (data_dir / "members").exists()


# ---- what it asks again ----------------------------------------------------

def test_a_name_that_is_not_free_is_asked_again(setup, did_path):
    console = Console(["founder", "Ada!", "ada", "written"], [PASSWORD, PASSWORD])
    assert run(setup, did_path, console) == 0
    assert "that name is not free to take" in console.said
    assert "lowercase letters" in console.said
    assert setup.members.list_members() == ["ada"]


def test_a_short_password_is_asked_again(setup, did_path):
    console = Console(["ada", "written"], ["short", PASSWORD, PASSWORD])
    assert run(setup, did_path, console) == 0
    assert "a password needs at least 10 characters" in console.said
    assert "short" not in console.said


def test_two_passwords_that_differ_are_asked_again(setup, did_path):
    console = Console(["ada", "written"],
                      [PASSWORD, "a different password altogether", PASSWORD, PASSWORD])
    assert run(setup, did_path, console) == 0
    assert "did not match" in console.said
    assert "a different password altogether" not in console.said
    assert vault.unlock(setup.members.load_member("ada")["vault"], PASSWORD)


def test_it_waits_until_the_word_is_written(setup, did_path):
    console = Console(["ada", "done", "", "yes", "written"], [PASSWORD, PASSWORD])
    assert run(setup, did_path, console) == 0
    asked_for_it = [prompt for prompt in console.asked if '"written"' in prompt]
    assert len(asked_for_it) == 4
    assert console.lines[-1] == "Done. You are member one, as ada."
    assert console.said.count("Done.") == 1
