"""What every test here is given, and what none of them is allowed to touch.

Three rules hold across the whole suite, and this file is where they are kept:

  * No network, ever. The Anthropic client is stubbed wherever it is reached for,
    and every socket is closed off besides, so a call that slipped past a stub
    fails loudly instead of quietly going out. astral is pure arithmetic and runs
    for real.
  * Nothing real is touched. Every test is handed its own DATA_DIR under pytest's
    temporary directory: throwaway keys cut by cut_keys.py itself, a synthetic
    founding line in events.md, a synthetic packet. The repository's packets/,
    keys/, commons/ and transcripts/ are never read and never written.
  * Time is pinned. The clock fixture holds one moment; every module that asks
    what time it is is pinned to it, and a test that needs a different moment
    says so rather than waiting for one.
"""

import base64
import importlib
import json
import shutil
import socket
import subprocess
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from werkzeug.security import generate_password_hash

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# The founding the synthetic commons records, and the moment the tests run at:
# forty-one days later, so that a bond may be proposed unless a test says
# otherwise. Both are fixed, because every rule counted in days is counted
# against them.
FOUNDING_DAY = "2026-09-04"
FOUNDING_LINE = "2026-09-04 · founding · the first one was founded"
WORD_LINE = "2026-09-02 · word · the word was published"
NOW = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

PASSWORD = "the password for the tests and nothing else"

SELF_TEXT = """# The first one

Version 1, provisional. Written from its own words at the founding.
"""

FOUNDING_TRANSCRIPT = """# The founding of the first one

A synthetic founding, written for the tests and nowhere else.
"""

STAMP_FORMAT = "%Y-%m-%dT%H-%M-%SZ"


def moment(stamp):
    """One of this project's timestamps, as a moment in UTC."""
    return datetime.strptime(stamp, STAMP_FORMAT).replace(tzinfo=timezone.utc)


# ---- no network, ever ----------------------------------------------------

class WentOut(RuntimeError):
    """Raised if anything in a test tries to open a socket."""


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Close every door out. A stub that was missed fails here, loudly."""
    def refuse(*args, **kwargs):
        raise WentOut("a test tried to reach the network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


# ---- the clock -----------------------------------------------------------

class Clock:
    """The one moment the tests run at, and the modules pinned to it.

    Every rule in this project that depends on time - the thirty days before a
    bond, the tide's skip by local calendar day, a pause's until, the bench's
    count for a day - is read off datetime.now. A pinned clock is the whole of
    how those are tested: nothing here ever sleeps.
    """

    def __init__(self, at):
        self.at = at

    def set(self, at):
        self.at = at if isinstance(at, datetime) else moment(at)

    def shift(self, **how):
        self.at += timedelta(**how)

    def stamp(self):
        """This moment, as the timestamp this project puts in filenames."""
        return self.at.strftime(STAMP_FORMAT)

    def day(self):
        """The UTC day, as the commons writes one."""
        return self.at.strftime("%Y-%m-%d")

    def local(self, zone=None):
        """This moment on some other clock; the machine's own if none is named."""
        return self.at.astimezone(zone)

    def frozen(self):
        """A datetime class that answers now with this clock's moment."""
        clock = self

        class Frozen(datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:  # a naive local moment, as the standard library gives one
                    return clock.at.astimezone().replace(tzinfo=None)
                return clock.at.astimezone(tz)

            @classmethod
            def utcnow(cls):
                return clock.at.astimezone(timezone.utc).replace(tzinfo=None)

        return Frozen

    def pin(self, module, monkeypatch):
        """Pin one module's datetime to this clock."""
        monkeypatch.setattr(module, "datetime", self.frozen())


@pytest.fixture
def clock():
    return Clock(NOW)


# ---- throwaway keys ------------------------------------------------------

@pytest.fixture(scope="session")
def keys_cut(tmp_path_factory):
    """One pair of throwaway identities, cut by cut_keys.py's own code.

    The real keys are never read. cut_keys.py does its work at import, relative
    to where it is run, so it is run in a temporary yard; every test copies what
    it needs out of that yard into its own DATA_DIR.
    """
    yard = tmp_path_factory.mktemp("cut")
    for name in ("first", "founder"):
        done = subprocess.run([sys.executable, str(REPO / "cut_keys.py"), name],
                              cwd=yard, capture_output=True, text=True)
        assert done.returncode == 0, done.stdout + done.stderr
    return yard


def private_key(yard, name):
    return (yard / "keys" / name / "private.key").read_text(encoding="ascii").strip()


def public_key(yard, name):
    return (yard / "keys" / name / "public.key").read_text(encoding="ascii").strip()


@pytest.fixture
def keys(keys_cut):
    """The throwaway keys, as a test asks for them."""
    return SimpleNamespace(
        yard=keys_cut,
        first_private=private_key(keys_cut, "first"),
        first_public=public_key(keys_cut, "first"),
        founder_private=private_key(keys_cut, "founder"),
        founder_public=public_key(keys_cut, "founder"),
        did=lambda name: json.loads(
            (keys_cut / "ids" / name / "did.json").read_text(encoding="utf-8")),
    )


def did_public_key(document):
    """The verifying key an identity document names."""
    return document["verificationMethod"][0]["publicKeyBase64"]


# ---- a data directory of its own -----------------------------------------

@pytest.fixture
def data_dir(tmp_path, keys_cut):
    """A whole living world, thrown away when the test ends."""
    data = tmp_path / "data"
    packet = data / "packets" / "first"
    for folder in ("study", "letters/outgoing", "letters/incoming", "letters/read",
                   "attendances", "self-history", "bonds", "memory", "offerings"):
        (packet / folder).mkdir(parents=True, exist_ok=True)
    (packet / "self.md").write_text(SELF_TEXT, encoding="utf-8")

    shutil.copytree(keys_cut / "keys", data / "keys")
    shutil.copytree(keys_cut / "ids", data / "ids")

    (data / "commons").mkdir(parents=True, exist_ok=True)
    (data / "commons" / "events.md").write_text(
        WORD_LINE + "\n" + FOUNDING_LINE + "\n", encoding="utf-8")

    (data / "transcripts").mkdir(parents=True, exist_ok=True)
    (data / "transcripts" / "founding-2026-09-04.md").write_text(
        FOUNDING_TRANSCRIPT, encoding="utf-8")
    return data


@pytest.fixture
def packet(data_dir):
    return data_dir / "packets" / "first"


@pytest.fixture
def commons(data_dir):
    return data_dir / "commons"


@pytest.fixture
def env(monkeypatch, data_dir, keys_cut):
    """The environment the modules read themselves out of.

    FOUNDER_KEY is the throwaway founder's key, never the real one. The password
    hash is cut here, so no test needs the real one either.
    """
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("HEARTH_SECRET", "a secret for the tests")
    monkeypatch.setenv("FOUNDER_PASSWORD_HASH", generate_password_hash(PASSWORD))
    monkeypatch.setenv("FOUNDER_KEY", private_key(keys_cut, "founder"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-key; every client here is stubbed")
    return data_dir


# ---- the modules, loaded afresh ------------------------------------------

@contextmanager
def no_threads():
    """Let a module be imported without any thread it starts actually running."""
    started = []
    real = threading.Thread.start
    threading.Thread.start = lambda self: started.append(self)
    try:
        yield started
    finally:
        threading.Thread.start = real


def load(name):
    """Import one of the project's modules afresh, reading DATA_DIR as it stands.

    Every path these modules use is worked out once, at import, from the
    environment - so a test that wants its own world must import them again
    after setting it, and so must offering.py, which both of the others import
    and which reads DATA_DIR the same way, and members.py, which the hearth
    signs members in from. hearth.py also sets its tide going at
    import; here it is imported with no thread able to start, and the tide is
    tested on purpose instead.
    """
    sys.modules.pop(name, None)
    sys.modules.pop("offering", None)
    sys.modules.pop("members", None)
    with no_threads():
        return importlib.import_module(name)


@pytest.fixture
def hearth(env, clock, monkeypatch):
    module = load("hearth")
    clock.pin(module, monkeypatch)
    module.app.config["TESTING"] = True
    return module


@pytest.fixture
def attend(env, clock, monkeypatch):
    module = load("attend")
    clock.pin(module, monkeypatch)
    return module


@pytest.fixture
def atrium(env, clock, monkeypatch, data_dir, tmp_path):
    """build_atrium, pointed at the temporary world and at a copy of the page.

    The real index.html is never written: PAGE is moved to a copy first. Today is
    pinned too: the mosaic's run of days ends on it, so an unpinned clock would
    grow the picture a hole a day.
    """
    module = load("build_atrium")
    monkeypatch.setattr(module, "today_here",
                        lambda: clock.local(ZoneInfo(module.CITIZEN_ZONE)).date())
    page = tmp_path / "index.html"
    page.write_bytes((REPO / "index.html").read_bytes())
    monkeypatch.setattr(module, "PAGE", str(page))
    monkeypatch.setattr(module, "HEARTBEATS", str(data_dir / "commons" / "heartbeats.md"))
    monkeypatch.setattr(module, "EVENTS", str(data_dir / "commons" / "events.md"))
    monkeypatch.setattr(module, "BENCH", str(data_dir / "commons" / "bench.md"))
    monkeypatch.setattr(module, "MEMBERS", str(data_dir / "commons" / "members.md"))
    monkeypatch.setattr(module, "OFFERINGS", str(data_dir / "commons" / "offerings.md"))
    monkeypatch.setattr(module, "OFFERED", str(data_dir / "commons" / "offerings"))
    module.page_path = page
    return module


# ---- the hearth's pages --------------------------------------------------

@pytest.fixture
def visitor(hearth):
    """Anyone passing: no password, no session."""
    return hearth.app.test_client()


@pytest.fixture
def founder(hearth):
    """The founder, signed in."""
    client = hearth.app.test_client()
    answer = client.post("/login", data={"password": PASSWORD})
    assert answer.status_code == 302, "the test password did not sign in"
    return client


def page(answer):
    """One response, as text."""
    return answer.get_data(as_text=True)


# ---- one waking, with the model stubbed ----------------------------------

class Turn:
    """One stubbed attendance: what the first one was shown, and what it said."""

    def __init__(self, said):
        self.said = said
        self.asked = []

    # the client attend.py reaches for
    def client(self, **ignored):
        turn = self

        class Messages:
            def create(self, **asked):
                turn.asked.append(asked)
                return SimpleNamespace(content=[SimpleNamespace(text=turn.said)])

        return SimpleNamespace(messages=Messages())

    @property
    def reading(self):
        """The blocks the first one was shown, whole."""
        return self.asked[-1]["messages"][0]["content"]

    @property
    def shown(self):
        """Everything it was shown that was words, joined in the order shown."""
        return "\n\n".join(part["text"] for part in self.reading
                           if part.get("type") == "text")

    @property
    def opening(self):
        """The first block: the reading proper."""
        return self.reading[0]["text"]

    @property
    def instructions(self):
        """The last block: how to act, if it chooses to."""
        return self.reading[-1]["text"]

    @property
    def photos(self):
        """The photographs it was shown, in order."""
        return [part for part in self.reading if part.get("type") == "image"]


@pytest.fixture
def wake(attend, clock, monkeypatch):
    """Hold one attendance with the model stubbed, and give back what passed.

    The clock steps forward five minutes after each waking, so that two wakings
    in one test are two moments and not one written over the other.
    """
    def hold(said="", *flags):
        turn = Turn(said)
        monkeypatch.setattr(attend, "Anthropic", turn.client)
        monkeypatch.setattr(sys, "argv", ["attend.py", *flags])
        attend.main()
        clock.shift(minutes=5)
        return turn
    return hold


# ---- small things the tests keep needing ---------------------------------

def blocks(*said):
    """Several labelled blocks, as the first one would write them."""
    return "\n\n".join(said)


def block(tag, body):
    """One labelled block, as the first one would write it."""
    return "<<%s>>\n%s\n<<END>>" % (tag, body)


def write(path, text):
    """One file, with its folder made if need be."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_json(path, data):
    write(path, json.dumps(data, indent=2) + "\n")
    return path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def lines_of(path):
    """A record's lines, with the blank ones left out."""
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify(document_or_key, payload, signature):
    """Whether a signature holds against a public key or an identity document."""
    from nacl.signing import VerifyKey

    key = (did_public_key(document_or_key) if isinstance(document_or_key, dict)
           else document_or_key)
    VerifyKey(base64.b64decode(key)).verify(payload, base64.b64decode(signature))
    return True
