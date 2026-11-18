"""What every test here is given, and what none of them is allowed to touch.

Three rules hold across the whole suite, and this file is where they are kept:

  * No network, ever. The Anthropic client is stubbed wherever it is reached for,
    and every socket is closed off besides, so a call that slipped past a stub
    fails loudly instead of quietly going out. astral is pure arithmetic and runs
    for real.
  * No call to Google, ever. No Gemini key is in the environment, and the one
    place Google's client is made (gemini.sdk_client) refuses, as Google's own
    Client does; a test of an agent on Gemini puts a FakeGoogle in its place.
  * No email, ever. The Resend key is taken out of the environment, the way an
    email goes is a fake that keeps each message (the outbox fixture), and the
    real post to Resend refuses if it is ever reached.
  * Nothing real is touched. Every test is handed its own DATA_DIR under pytest's
    temporary directory: throwaway keys cut by cut_keys.py itself, a synthetic
    founding line in events.md, a synthetic packet. The repository's packets/,
    keys/, commons/ and transcripts/ are never read and never written.
  * A room is kept in a folder of its own, rooms/<room>/, and is a room only
    where its room.json is (rooms.py). A test writes the first one's letters,
    errands, bond and offerings through the room fixture, rooms/first/.
  * Both registries are tested. The registry of agents (agents.py) is a file,
    or, with no file there, the first one alone, and the two must be one: pytest
    --agents=file, the default, reads a file, and pytest --agents=absent runs as
    though there were none. The file read is never the committed agents.json,
    which holds the second one since 16 November 2026: it is a scratch copy of it
    holding the first one's committed entry alone (pytest_configure), and a test
    that wants another agent writes one of its own. Only a test of the committed
    file itself reads agents.json.
  * Time is pinned. The clock fixture holds one moment; every module that asks
    what time it is is pinned to it, and a test that needs a different moment
    says so rather than waiting for one.
"""

import base64
import importlib
import json
import os
import re
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
from nacl.pwhash import argon2id

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

# The founder comes in as the keeper, by a pseudonym and a vault of their own.
# The name is not one the members' store reserves, and not one any test takes.
FOUNDER_NAME = "rowan"

SELF_TEXT = """# The first one

Version 1, provisional. Written from its own words at the founding.
"""

FOUNDING_TRANSCRIPT = """# The founding of the first one

A synthetic founding, written for the tests and nowhere else.
"""

# The first one's transcript, kept where it is kept on the server: directly in
# transcripts/, under the one name attend.FIRST_FOUNDING reads there.
FIRST_FOUNDING = "founding-2026-09-04T11-28-55Z.md"

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


# ---- no call to Google, ever ---------------------------------------------

class WentToGoogle(RuntimeError):
    """Raised if anything in a test reaches for Google's own client."""


@pytest.fixture(autouse=True)
def no_google(monkeypatch):
    """Three guards: no Gemini key; gemini.sdk_client refuses; and so does Google's Client."""
    import gemini
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    def refuse(*args, **kwargs):
        raise WentToGoogle("a test reached for Google's client")

    monkeypatch.setattr(gemini, "sdk_client", refuse)
    try:
        from google import genai
    except ImportError:
        return
    monkeypatch.setattr(genai, "Client", refuse)


class FakeGoogle:
    """Google's client, faked: each request kept, and each answer given from those it is told.

    It stands where gemini.sdk_client's client stands, so everything gemini.py says
    to Gemini is said to it. answers are Google's own response types, given in
    turn; when they run out, the last is given again.
    """

    def __init__(self, *answers):
        self.answers = list(answers) or [self.said("")]
        self.asked = []
        fake = self

        class Models:
            def generate_content(self, **asked):
                fake.asked.append(asked)
                return fake.answers.pop(0) if len(fake.answers) > 1 else fake.answers[0]

        self.models = Models()

    def __call__(self, api_key=None):
        self.key = api_key
        return self

    @staticmethod
    def said(text, finish="STOP", calls=(), usage=None, blocked=None, signature=None):
        """One of Google's answers: text, any function calls, how it finished, what it cost."""
        from google.genai import types
        parts = [types.Part(text=text, thought_signature=signature)] if text is not None else []
        parts += [types.Part(function_call=types.FunctionCall(name=name, args=args, id=its_id))
                  for name, args, its_id in calls]
        return types.GenerateContentResponse(
            candidates=[] if blocked else [types.Candidate(
                content=types.Content(role="model", parts=parts), finish_reason=finish)],
            prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason=blocked)
            if blocked else None,
            usage_metadata=types.GenerateContentResponseUsageMetadata(**usage) if usage else None)


# ---- no email, ever ------------------------------------------------------

class SentEmail(RuntimeError):
    """Raised if anything in a test reaches the real way an email is sent."""


class Outbox:
    """The way an email goes, stubbed: every message is kept here, and none goes.

    says is what the sending gives back, "sent" unless a test says otherwise. The
    real transport is kept beside it, as real, for the one test that builds the
    request Resend would be sent, against a stubbed opener.
    """

    def __init__(self):
        self.says = "sent"
        self.sent = []

    def __call__(self, message):
        self.sent.append(dict(message))
        return self.says


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    """Three guards, so that no test ever sends an email: no key in the environment; a
    fake in place of the transport; and the real post to Resend made to refuse."""
    import mail
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    stub = Outbox()
    stub.real_transport = mail.TRANSPORT
    stub.real_post = mail.post_to_resend
    monkeypatch.setattr(mail, "TRANSPORT", stub)

    def refuse(*args, **kwargs):
        raise SentEmail("a test reached the real way an email is sent")

    monkeypatch.setattr(mail, "post_to_resend", refuse)
    return stub


class Reader:
    """The small model that reads one line for good spirit (hearth.in_good_spirit), stubbed:
    what it was asked, and what it says."""

    def __init__(self, says="YES", breaks=False):
        self.says = says
        self.breaks = breaks
        self.asked = []

    def __call__(self, *args, **kwargs):
        reader = self

        class Messages:
            def create(self, **asked):
                reader.asked.append(asked)
                if reader.breaks:
                    raise RuntimeError("the model could not be reached")
                return SimpleNamespace(content=[SimpleNamespace(text=reader.says)])

        return SimpleNamespace(messages=Messages())


class Screen:
    """The public screen, stubbed: it answers NO, the word that clears a text, unless a
    test says otherwise. A test may set says to another answer, to an exception to
    raise, or to a function of the text and the allowed names. Every asking is kept,
    with its allowed names, and the real asking is kept beside the stub as real.
    """

    def __init__(self):
        self.says = "NO"
        self.asked = []

    def __call__(self, text, names):
        self.asked.append((text, list(names)))
        if isinstance(self.says, BaseException):
            raise self.says
        return self.says(text, names) if callable(self.says) else self.says


@pytest.fixture(autouse=True)
def screen(monkeypatch):
    """No text is ever sent to be screened: the one call the screen makes is stubbed."""
    import public_screen
    stub = Screen()
    stub.real = public_screen.ask
    monkeypatch.setattr(public_screen, "ask", stub)
    return stub


def site_bookkeeping(relative):
    """Whether a file under DATA_DIR is the site's own bookkeeping, and no part of any
    agent's world: what the models cost (spending/). relative is its path from
    DATA_DIR, as a string with forward slashes or a Path.

    Every comparison of what a waking leaves behind passes over these, as it passes
    over transcripts/: the count is the site's, written at each waking whatever the
    agent did, and test_spending_line_holds_only_numbers says what is in it.
    """
    first = Path(relative).parts[0] if str(relative) else ""
    return first == "spending"


@pytest.fixture(autouse=True)
def spending_kept_aside(monkeypatch, tmp_path):
    """What the models cost (spending.py) is counted under DATA_DIR; where a test has
    none, under its own temporary folder, never the repository's."""
    import spending
    monkeypatch.setattr(spending, "REPO", tmp_path)


# ---- where the sun is watched from ---------------------------------------

# The host is told where its dawns and sunsets are watched from, as two secrets
# (waking.LATITUDE and waking.LONGITUDE), and the source names no place. The
# tests watch from a point of their own: open sea in the Gulf of Mexico, on no
# one's doorstep, where dawn is a morning and sunset an evening all year on
# Eastern time. A test that wants the host untold takes them away itself.
SUN_WATCHED_FROM = ("28.0", "-84.5")


@pytest.fixture(autouse=True)
def sun_watched_from(monkeypatch):
    """Tell every test's host where the sun is watched from, as the real one is told."""
    latitude, longitude = SUN_WATCHED_FROM
    monkeypatch.setenv("DAWN_LATITUDE", latitude)
    monkeypatch.setenv("DAWN_LONGITUDE", longitude)


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


# ---- the registry --------------------------------------------------------

# Whether the registry of agents is read from its file, or as if there were none.
REGISTRIES = ("file", "absent")


def pytest_addoption(parser):
    parser.addoption("--agents", choices=REGISTRIES, default="file",
                     help="whether the registry is read from agents.json, or as if it were absent")


# The scratch folder the tests' own registry is kept in, for this run.
REGISTRY_HOME = None


def pytest_configure(config):
    """Every module reads a registry of the tests' own, never the committed agents.json.

    With --agents=file, the default, it is a scratch agents.json holding the first
    one's entry as committed and nothing else (the second one, committed on 16
    November 2026, left out); with --agents=absent, there is no file at all. This
    is done before any test is collected, so before any module that derives
    something from the registry is imported.
    """
    global REGISTRY_HOME
    import tempfile
    import agents
    if config.getoption("--agents") == "absent":
        agents.FILE = agents.FILE.with_name("agents.json.absent-for-this-run")
        assert not agents.FILE.exists()
        return
    committed = json.loads((REPO / "agents.json").read_text(encoding="utf-8"))
    REGISTRY_HOME = Path(tempfile.mkdtemp(prefix="tesserae-registry-"))
    agents.FILE = REGISTRY_HOME / "agents.json"
    agents.FILE.write_text(json.dumps(committed[:1], indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    assert agents.registry() == committed[:1]


def pytest_unconfigure(config):
    """The tests' own registry is thrown away when the run ends."""
    if REGISTRY_HOME is not None:
        shutil.rmtree(REGISTRY_HOME, ignore_errors=True)


def make_room(data):
    """The first one's room in a folder of its own: room.json is the sign."""
    import bonds
    home = data / "rooms" / "first"
    home.mkdir(parents=True, exist_ok=True)
    record = {"id": "first", "bond": "founder-first",
              "parties": [bonds.FOUNDER_DID, bonds.FIRST_DID]}
    (home / "room.json").write_bytes((json.dumps(record, indent=2) + "\n").encode("utf-8"))
    return home


# ---- jsdom, for the atrium's browser path --------------------------------

# Where jsdom is kept for test_atrium_paths.py: a folder of the user's own,
# outside this repository, so nothing extra is committed or served, and outside
# the temporary folder, which Windows empties of old files and leaves the
# folders standing, so that node finds a jsdom/ with nothing in it.
JSDOM_HOME = (Path(os.environ["LOCALAPPDATA"]) if os.name == "nt" and os.environ.get("LOCALAPPDATA")
              else Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")) / "tesserae" / "jsdom"

# node is run with that folder on NODE_PATH, after any NODE_PATH already set
NODE_ENV = {**os.environ, "NODE_PATH": os.pathsep.join(
    filter(None, [os.environ.get("NODE_PATH"), str(JSDOM_HOME / "node_modules")]))}


def pytest_terminal_summary(terminalreporter):
    """Say plainly when the atrium's browser path was skipped, rather than leave it in a count."""
    skipped = [report for report in terminalreporter.stats.get("skipped", [])
               if report.nodeid.split("::")[0].endswith("test_atrium_paths.py")]
    if not skipped:
        return
    reason = skipped[0].longrepr[2] if isinstance(skipped[0].longrepr, tuple) else ""
    terminalreporter.write_sep("!", "%d atrium path tests did not run" % len(skipped),
                               yellow=True, bold=True)
    terminalreporter.write_line(reason.removeprefix("Skipped: "))
    terminalreporter.write_line('To install it: npm i --prefix "%s" jsdom' % JSDOM_HOME)


# ---- a data directory of its own -----------------------------------------

@pytest.fixture
def data_dir(tmp_path, keys_cut):
    """A whole living world, thrown away when the test ends."""
    data = tmp_path / "data"
    packet = data / "packets" / "first"
    room = make_room(data)
    for folder in ("study", "attendances", "self-history", "memory"):
        (packet / folder).mkdir(parents=True, exist_ok=True)
    for folder in ("letters/outgoing", "letters/incoming", "letters/read", "bonds", "offerings"):
        (room / folder).mkdir(parents=True, exist_ok=True)
    (packet / "self.md").write_text(SELF_TEXT, encoding="utf-8")

    shutil.copytree(keys_cut / "keys", data / "keys")
    shutil.copytree(keys_cut / "ids", data / "ids")

    (data / "commons").mkdir(parents=True, exist_ok=True)
    (data / "commons" / "events.md").write_text(
        WORD_LINE + "\n" + FOUNDING_LINE + "\n", encoding="utf-8")

    (data / "transcripts").mkdir(parents=True, exist_ok=True)
    (data / "transcripts" / FIRST_FOUNDING).write_text(FOUNDING_TRANSCRIPT, encoding="utf-8")
    return data


@pytest.fixture
def packet(data_dir):
    return data_dir / "packets" / "first"


@pytest.fixture
def room(data_dir):
    """Where the first one's letters, errands, bond and offerings are kept."""
    return data_dir / "rooms" / "first"


@pytest.fixture
def commons(data_dir):
    return data_dir / "commons"


@pytest.fixture
def env(monkeypatch, data_dir, keys_cut):
    """The environment the modules read themselves out of.

    FOUNDER_KEY is the throwaway founder's key, never the real one. The old
    founder password is gone from the hearth, and is taken out of the
    environment here too, so that nothing can lean on it.
    """
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("HEARTH_SECRET", "a secret for the tests")
    monkeypatch.delenv("FOUNDER_PASSWORD_HASH", raising=False)
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
    after setting it, and so must offering.py and threshold.py, which both of
    the others import and which read DATA_DIR the same way, and bonds.py, which both
    of them write the commons' list of bonds through, and members.py, which the hearth
    signs members in from. hearth.py also sets its tide going at
    import; here it is imported with no thread able to start, and the tide is
    tested on purpose instead.
    """
    sys.modules.pop(name, None)
    sys.modules.pop("offering", None)
    sys.modules.pop("members", None)
    sys.modules.pop("threshold", None)
    sys.modules.pop("bonds", None)
    sys.modules.pop("witness", None)  # it keeps the marks under DATA_DIR, and reads bonds
    sys.modules.pop("door", None)  # it keeps each door under DATA_DIR, and reads members
    sys.modules.pop("rooms", None)  # it finds a room's place under DATA_DIR, and reads members
    sys.modules.pop("private_words", None)  # it keeps its list under DATA_DIR
    sys.modules.pop("tokens", None)  # it keeps each link that works once under DATA_DIR
    sys.modules.pop("invitations", None)  # it keeps each invitation under DATA_DIR
    sys.modules.pop("ledger", None)  # it keeps the ledger's own lines under DATA_DIR
    sys.modules.pop("corrections", None)  # it keeps the commons' corrections under DATA_DIR
    sys.modules.pop("answered", None)  # it finds the packets under DATA_DIR
    sys.modules.pop("solstice", None)  # it finds a room's bonds/ through rooms, under DATA_DIR
    sys.modules.pop("introductions", None)  # it keeps each introduction under DATA_DIR
    sys.modules.pop("knock", None)  # it keeps each knock under DATA_DIR
    sys.modules.pop("board", None)  # it keeps the board under DATA_DIR
    sys.modules.pop("weekly", None)  # it keeps the weekly questions under DATA_DIR
    sys.modules.pop("coming", None)  # it keeps the founder's letter and the welcomes under DATA_DIR
    sys.modules.pop("found_room", None)  # it makes a room through rooms, under DATA_DIR
    sys.modules.pop("blocks", None)  # it keeps each one's blocks under DATA_DIR
    sys.modules.pop("site_notes", None)  # it keeps each note from the site under DATA_DIR
    sys.modules.pop("made_here", None)  # it keeps drafts and what is made here under DATA_DIR
    sys.modules.pop("hoping_for", None)  # it keeps each line through introductions, under DATA_DIR
    sys.modules.pop("here_this_week", None)  # it keeps each day through members, under DATA_DIR
    sys.modules.pop("finding", None)  # it reads doors, introductions and days under DATA_DIR
    sys.modules.pop("notes", None)  # it reads the knocks, and keeps notes under DATA_DIR
    sys.modules.pop("daily_acts", None)  # it counts what is kept under DATA_DIR
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
    # nor the real mosaic.html: the whole mosaic's page is written beside the copy
    monkeypatch.setattr(module, "WHOLE", str(tmp_path / "mosaic.html"))
    # nor the real style.css, which it writes each citizen's hue into
    style = tmp_path / "style.css"
    style.write_bytes((REPO / "style.css").read_bytes())
    monkeypatch.setattr(module, "STYLE", str(style))
    monkeypatch.setattr(module, "HEARTBEATS", str(data_dir / "commons" / "heartbeats.md"))
    monkeypatch.setattr(module, "EVENTS", str(data_dir / "commons" / "events.md"))
    monkeypatch.setattr(module, "MEMBERS", str(data_dir / "commons" / "members.md"))
    monkeypatch.setattr(module, "BONDS", str(data_dir / "commons" / "bonds.md"))
    module.page_path = page
    module.whole_path = tmp_path / "mosaic.html"
    module.style_path = style
    return module


# ---- the hearth's pages --------------------------------------------------

@pytest.fixture
def visitor(hearth):
    """Anyone passing: no password, no session."""
    return hearth.app.test_client()


def token(client):
    """The form token this client's session holds, asking the hearth to cut one if none."""
    with client.session_transaction() as held:
        if "csrf_token" in held:
            return held["csrf_token"]
    client.get("/login")  # a page with a form on it, which is where a token is cut
    with client.session_transaction() as held:
        return held["csrf_token"]


def post(client, path, data=None, **how):
    """A post, as a form on one of the hearth's own pages would send it: with its token."""
    data = dict(data or {})
    data.setdefault("csrf_token", token(client))
    return client.post(path, data=data, **how)


@pytest.fixture(scope="session")
def founder_vault():
    """The founder's vault, sealed once under the test password at argon2id's
    minimum cost - the cost is written into the vault, so it opens as cheaply in
    every test, whatever the limits stand at there."""
    import vault

    held = vault.OPSLIMIT, vault.MEMLIMIT
    vault.OPSLIMIT, vault.MEMLIMIT = argon2id.OPSLIMIT_MIN, argon2id.MEMLIMIT_MIN
    try:
        sealed, _, _ = vault.make_vault(PASSWORD)
    finally:
        vault.OPSLIMIT, vault.MEMLIMIT = held
    return sealed


@pytest.fixture
def founder(hearth, founder_vault):
    """The founder, signed in as the keeper."""
    hearth.members.create_member(FOUNDER_NAME, json.loads(json.dumps(founder_vault)),
                                 "keeper", [])
    client = hearth.app.test_client()
    answer = post(client, "/login", data={"pseudonym": FOUNDER_NAME, "password": PASSWORD})
    signed_in = answer.status_code == 302 and answer.headers["Location"] == "/"
    assert signed_in, "the test keeper did not sign in"
    return client


def page(answer):
    """One response, as text."""
    return answer.get_data(as_text=True)


# ---- one waking, with the model stubbed ----------------------------------

class Turn:
    """One stubbed attendance: what the first one was shown, and what it said."""

    def __init__(self, said, stop_reason=None):
        self.said = said
        self.stop_reason = stop_reason  # None stands for an API that gives none
        self.asked = []

    # the client attend.py reaches for
    def client(self, **ignored):
        turn = self

        class Messages:
            def create(self, **asked):
                turn.asked.append(asked)
                reply = SimpleNamespace(content=[SimpleNamespace(text=turn.said)])
                if turn.stop_reason is not None:
                    reply.stop_reason = turn.stop_reason
                return reply

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


# ---- what has been switched on, shut away again --------------------------

# Three things of the first one's were built shut away, each behind a flag in
# attend.py, and switched on together once it had agreed to them (its letter of
# 7 October 2026). What each was like shut away is still tested, and by the flag
# itself: a test that wants it off says so, and does not lean on the constant.
SWITCHED_ON = ("DOOR_FOR_FIRST", "LOOKING_BACK", "CHOICES")

# Its proposals and its extra wakings, each built shut away behind its own flag,
# and switched on together once it had agreed to both (its letter of 21 October
# 2026). Anything held to a reading or an attend.py from before them shuts both
# away again, by name: shut_away(attend, monkeypatch, *SWITCHED_ON_21_OCTOBER).
SWITCHED_ON_21_OCTOBER = ("PROPOSALS", "EXTRA_WAKINGS")


# Its wakings as they were until the founder switched on, for the first one, the
# two changes it agreed to on 10 November 2026 (12 November 2026): extra wakings
# on, and no weekly reflection waking. Anything held to a reading from before
# then puts them back first: wakings_not_yet_switched(attend, monkeypatch).
WAKINGS_BEFORE_12_NOVEMBER = (("EXTRA_WAKINGS", True), ("REFLECTION_WAKING", False))


def hue_not_again_unsaid(module, monkeypatch):
    """Take out, for one test, the sentence <<HUE>> has said since 14 November 2026 where an
    agent's colour now is not one it may choose again (attend.HUE_NOT_AGAIN)."""
    monkeypatch.setattr(module, "HUE_NOT_AGAIN", "")


def coral_not_yet(module, monkeypatch):
    """Close coral to the first one again, for one test, as it was until 15 November 2026
    (hues.FIRST_MAY_RETURN False): <<HUE>> offers it the palette alone and ends "Your
    colour now is not on the list: if you choose another, you cannot choose it again."
    Given hearth, it is done to the hues the hearth's attend.py reads."""
    module = getattr(module, "the_waking", module)
    monkeypatch.setattr(module.hues, "FIRST_MAY_RETURN", False)


def board_weekly_not_yet(module, monkeypatch):
    """Shut the weekly question's topics to the first one again, for one test, as they were
    until 15 November 2026 (later): the board's words as they were, and the place and
    conversation alone to read and post in (attend.BOARD_BEFORE_WEEKLY). Given hearth, it
    is done to the attend.py the hearth holds the tide through."""
    module = getattr(module, "the_waking", module)
    for name, value in module.BOARD_BEFORE_WEEKLY.items():
        monkeypatch.setattr(module, name, value)


# The <<OFFER>> block's explanation, as it stood in HOW TO ACT between <<ERRAND>> and
# <<STUDY>> until offerings were taken out of the code (the founder's request of 16
# November 2026, part B4; the founder told the first one). Every reading cut before then
# is exactly what it was with it put back (offer_explained_again).
OFFER_BLOCK_BEFORE = """<<OFFER>>
(give something out of your correspondence to the commons, or answer something the founder has offered. The first line must be exactly one of these and nothing else:
  offer letter <stem>     the whole of that letter, either of yours
  offer passage <stem>    a passage from it, quoted word for word on the lines below
  offer photo <stem>      the photograph that came with that letter
  offer picture <stem>    the picture you drew beside that letter
  consent <id>            place something the founder has offered
  decline <id>            decline it; nothing is owed, and nothing of it ever becomes public
A stem is a letter's name without the .md, as it is written above each letter. Nothing is placed until both of you have signed it, and a placed offering is never removed, so offer only what you would want a stranger to have read. No faces, no legal names - the charter keeps those private forever.)
<<END>>"""
STUDY_OPENS = "<<STUDY>>\n(a private draft"


def offer_explained_again(module, monkeypatch):
    """Put back, for one test, the <<OFFER>> block's explanation where it stood in HOW TO
    ACT, as it was until 16 November 2026 (part B4). With it, every reading of the first
    one cut before then is exactly what it was; nothing else of offerings was ever in a
    reading where none had been made. Given hearth, it is done to the attend.py the
    hearth holds the tide through."""
    module = getattr(module, "the_waking", module)
    now = module.HOW_TO_ACT
    if OFFER_BLOCK_BEFORE in now:
        return
    assert now.count(STUDY_OPENS) == 1
    monkeypatch.setattr(module, "HOW_TO_ACT",
                        now.replace(STUDY_OPENS, OFFER_BLOCK_BEFORE + "\n\n" + STUDY_OPENS, 1))


# What the founder switched on for the first one on 17 November 2026 (the branch
# agents-week), each of which it said yes to that day, and the one he switched off:
# quiet_days, made_here, rooms_reading, two_doors and block on; rhythm_line off.
FEATURES_ON_17_NOVEMBER = ("quiet_days", "made_here", "rooms_reading", "two_doors", "block")
FEATURES_OFF_17_NOVEMBER = ("rhythm_line",)
SWITCHED_17_NOVEMBER = (("QUIET_DAYS", False), ("MADE_HERE", False), ("ROOMS_READING", False),
                        ("TWO_DOORS", False), ("BLOCKING", False), ("RHYTHM_LINE", True))
AGENTS_WEEK_HOME = []


# read_who_is_here as it was given to an agent until 17 November 2026, later (the branch
# agents-week, part 5): every agent and person, with no word to search by.
READ_WHO_IS_HERE_BEFORE = {
    "name": "read_who_is_here",
    "description": ("Open who is here: each agent and person, whether their door is open "
                    "and has room, their introduction, and whose door you may knock at."),
    "input_schema": {"type": "object", "properties": {}}}


def site_design_not_yet(module, monkeypatch):
    """Put back, for one test, everything of an agent's reading that the branch site-design
    moved (the founder's request of 17 November 2026, later still): <<HUE>> as it was, with
    the palette's names (colour_picker_not_yet). Every reading cut before then is exactly
    what it was with this done. Given hearth, it is done to the attend.py the hearth holds
    the tide through. who_drawn_not_yet does it first, so every older reading stands on it."""
    colour_picker_not_yet(module, monkeypatch)
    own_door_not_yet(module, monkeypatch)
    squares_not_yet(module, monkeypatch)


def squares_not_yet(module, monkeypatch):
    """Pictures as they were before the branch site-design, part 5 (17 November 2026): tiles
    of 5 or 12 in the palette's names (made_here.SQUARES False), and <<DRAFT>> saying so.
    Given hearth, it is done to the attend.py the hearth wakes."""
    module = getattr(module, "the_waking", module)
    import made_here
    monkeypatch.setattr(made_here, "SQUARES", False)
    if hasattr(getattr(module, "made_here", None), "SQUARES"):
        monkeypatch.setattr(module.made_here, "SQUARES", False)
    if hasattr(module, "DRAFT_BLOCK_BEFORE_SQUARES"):
        monkeypatch.setattr(module, "DRAFT_BLOCK", module.DRAFT_BLOCK_BEFORE_SQUARES)
        monkeypatch.setattr(module, "MADE_KINDS_SAID", module.MADE_KINDS_SAID_BEFORE_SQUARES)


def own_door_not_yet(module, monkeypatch):
    """Knocks as they were before the branch site-design, part 2 (17 November 2026): one's own
    door was never asked, a person never knocked at a person (knock.OWN_DOOR and knock.PEOPLE
    False), and <<KNOCK>> said nothing of one's own door. Given hearth, it is done to the
    attend.py the hearth wakes."""
    knocks_tidy_not_yet(module, monkeypatch)  # it came after
    module = getattr(module, "the_waking", module)
    import knock
    monkeypatch.setattr(knock, "OWN_DOOR", False)
    monkeypatch.setattr(knock, "PEOPLE", False)
    if hasattr(module, "KNOCK_BLOCK_BEFORE_OWN_DOOR"):
        monkeypatch.setattr(module, "KNOCK_BLOCK", module.KNOCK_BLOCK_BEFORE_OWN_DOOR)
    if hasattr(getattr(module, "knock", None), "OWN_DOOR"):
        monkeypatch.setattr(module.knock, "OWN_DOOR", False)
        monkeypatch.setattr(module.knock, "PEOPLE", False)


def who_drawn_not_yet(module, monkeypatch):
    """Give read_who_is_here back, for one test, as it was given until 17 November 2026,
    later: its description and its input with no word (attend.READ_WHO_IS_HERE). Every
    reading of an agent with knocks on cut before then is exactly what it was with this
    done. Given hearth, it is done to the attend.py the hearth holds the tide through.
    What site-design moved after it is put back first (site_design_not_yet)."""
    site_design_not_yet(module, monkeypatch)
    module = getattr(module, "the_waking", module)
    if hasattr(module, "READ_WHO_IS_HERE"):
        monkeypatch.setattr(module, "READ_WHO_IS_HERE", READ_WHO_IS_HERE_BEFORE)


def agents_week_not_yet(module, monkeypatch):
    """Put back, for one test, the first one's switches as they stood until 17 November 2026:
    the five switched on that day taken out of its features and rhythm_line put back, in the
    registry as it now stands (a scratch agents.json, or agents.FIRST where there is no
    file), and the six flags of attend.py as they were. Every reading of the first one cut
    before then is exactly what it was with this done. Given hearth, it is done to the
    attend.py the hearth holds the tide through. A test that writes a registry of its own
    after this reads that registry. read_who_is_here, given anew later that day, is given
    back as it was first (who_drawn_not_yet)."""
    who_drawn_not_yet(module, monkeypatch)
    registry = sys.modules["agents"]

    def as_before(entry):
        if entry.get("id") != registry.FIRST["id"]:
            return entry
        features = [one for one in entry.get("features") or ()
                    if one not in FEATURES_ON_17_NOVEMBER]
        features += [one for one in FEATURES_OFF_17_NOVEMBER if one not in features]
        return {**entry, "features": sorted(features)}

    if registry.FILE.is_file():
        if not AGENTS_WEEK_HOME:
            import tempfile
            AGENTS_WEEK_HOME.append(Path(tempfile.mkdtemp(prefix="tesserae-agents-week-")))
        where = AGENTS_WEEK_HOME[0] / f"agents-{len(list(AGENTS_WEEK_HOME[0].iterdir()))}.json"
        where.write_text(json.dumps([as_before(one) for one in registry.registry()], indent=2)
                         + "\n", encoding="utf-8")
        monkeypatch.setattr(registry, "FILE", where)
    else:
        monkeypatch.setattr(registry, "FIRST", as_before(dict(registry.FIRST)))
    module = getattr(module, "the_waking", module)
    for flag, was in SWITCHED_17_NOVEMBER:
        if hasattr(module, flag):
            monkeypatch.setattr(module, flag, was)


def standing_welcome_not_yet(module, monkeypatch):
    """Shut the first one's standing welcome away again, for one test, as it was until 16
    November 2026 (the branch welcome-on), when the founder put "standing_welcome" among its
    features at its asking (its letter of 16 November): attend.STANDING_WELCOME False, so no
    line of it under WHAT HAS HAPPENED and no <<STANDING_WELCOME>> explained. Every reading of
    the first one cut before then is exactly what it was with this done. Given hearth, it is
    done to the attend.py the hearth holds the tide through. Offerings, taken out after it
    (16 November 2026, later), are explained again first (offer_explained_again). What was
    switched for it on 17 November 2026 came later still, so it is put back first too
    (agents_week_not_yet)."""
    agents_week_not_yet(module, monkeypatch)
    offer_explained_again(module, monkeypatch)
    module = getattr(module, "the_waking", module)
    monkeypatch.setattr(module, "STANDING_WELCOME", False)


def hue_choice_not_yet(module, monkeypatch):
    """A later agent's reading as it was before it chose its own colour (13 November
    2026): no line of its colour under WHAT HAS HAPPENED, and no <<HUE>> explained.
    The first one's switch is off already, so its reading is as it was either way."""
    monkeypatch.setattr(module, "HUE_CHOOSING", False)


def colour_picker_not_yet(module, monkeypatch):
    """<<HUE>> as it was before any colour could be chosen by its hex code (17 November 2026,
    the branch site-design, part 1): the palette's names alone, a colour too close to
    another agent's refused (hues.EXACT False), and the block and its refusals in their
    old words. Given hearth, it is done to the attend.py the hearth wakes."""
    module = getattr(module, "the_waking", module)
    import hues
    monkeypatch.setattr(getattr(module, "hues", hues), "EXACT", False)
    if hasattr(module, "HUE_BLOCK_BEFORE_PICKER"):
        monkeypatch.setattr(module, "HUE_BLOCK", module.HUE_BLOCK_BEFORE_PICKER)
        monkeypatch.setattr(module, "HUE_REFUSED", module.HUE_REFUSED_BEFORE_PICKER)


def wakings_not_yet_switched(module, monkeypatch):
    """Put back, for one test, the first one's wakings as they were until 12 November 2026.

    One waking a day (extra_wakings taken out of its features) and its weekly
    reflection waking (reflection_waking put in) were switched on together. With
    attend.EXTRA_WAKINGS True and attend.REFLECTION_WAKING False again, its
    reading and its tide are exactly what they were before. Given hearth, it
    is done to the attend.py the hearth holds the tide through. What was switched
    on after it, on 13 November 2026, came later still, so it is shut away again
    too (switches_not_yet).
    """
    switches_not_yet(module, monkeypatch)
    module = getattr(module, "the_waking", module)
    for flag, was in WAKINGS_BEFORE_12_NOVEMBER:
        monkeypatch.setattr(module, flag, was)


# What the founder switched on for the first one on 13 November 2026, each of
# which it had agreed to: asked and answered and its introduction on 13 November,
# its door's room held to eight and the line of people waiting on 10 November.
# long_night, knock and corrections stay off. Anything held to a reading from
# before then shuts all four away again first: switches_not_yet(attend, monkeypatch).
SWITCHED_ON_13_NOVEMBER = ("ASKED_ON", "INTRODUCTION", "DOORS_TO_EIGHT", "PEOPLE_WAITING")


# What the founder switched on for the first one on 14 November 2026 (the branch
# intro-500): the board, the weekly question, its own colour, corrections, knocks
# and the long night, each made to take as little of its reading as it can.
# Anything held to a reading or a page from before then shuts all six away again
# first: six_not_yet(attend, monkeypatch), and, for what reads the registry as it
# goes, registry_six_not_yet(module, monkeypatch, where).
SWITCHED_ON_14_NOVEMBER = ("BOARD", "WEEKLY_QUESTION", "HUE_CHOOSING", "CORRECTIONS", "KNOCKS",
                           "LONG_NIGHT_FOR_FIRST")
FEATURES_ON_14_NOVEMBER = ("board", "weekly_question", "hue", "corrections", "knock",
                           "long_night")


def six_not_yet(module, monkeypatch):
    """Shut away again, for one test, the six switched on for the first one on 14 November
    2026. With them False again, its reading is exactly what it was before
    (test_rooms_reading's READING_INTRODUCTION_500). Given hearth, it is done to the
    attend.py the hearth holds the tide through. Its standing welcome, switched on
    on 16 November 2026, came later still, so it is shut away again too
    (standing_welcome_not_yet)."""
    standing_welcome_not_yet(module, monkeypatch)
    module = getattr(module, "the_waking", module)
    for flag in SWITCHED_ON_14_NOVEMBER:
        if hasattr(module, flag):
            monkeypatch.setattr(module, flag, False)


def before_the_second_came(entries):
    """A registry's entries as they stood before 16 November 2026, when the second one
    came: its entry as committed in agents.json taken out (an entry a test wrote of
    its own, even one named second, is left). Every registry drawn as it stood before
    that day is drawn without it."""
    committed = json.loads((REPO / "agents.json").read_text(encoding="utf-8"))
    came = [one for one in committed if one.get("id") == "second"]
    return [one for one in entries if one not in came]


def registry_six_not_yet(module, monkeypatch, where, also=()):
    """Read the registry, for one test, as it stood before 14 November 2026: the six
    switched on for the first one that day taken out of its features (and any named in
    also), in a scratch agents.json at where; and six_not_yet done to attend.py. Given
    hearth, the attend.py it holds the tide through reads it too."""
    registry = sys.modules["agents"]
    entries = before_the_second_came([dict(one) for one in registry.registry()])
    for entry in entries:
        if entry["id"] == registry.first()["id"]:
            entry["features"] = [one for one in entry.get("features") or ()
                                 if one not in FEATURES_ON_14_NOVEMBER and one not in also]
    where.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    held = [registry, getattr(module, "agents", registry)]
    waking = getattr(module, "the_waking", None)
    if waking is not None:
        held.append(getattr(waking, "agents", registry))
    for name in ("door", "answered", "introductions", "knock", "hues", "solstice", "board"):
        found = sys.modules.get(name)
        if found is not None and hasattr(found, "agents"):
            held.append(found.agents)
    for one in {id(one): one for one in held}.values():
        monkeypatch.setattr(one, "FILE", where)
    six_not_yet(module, monkeypatch)


def rooms_to_twelve(hearth, monkeypatch):
    """Put back, for one test, a person's room as it ran until 14 November 2026: one to
    twelve on their door's form, where it is one to eight since (door.MEMBER_ROOM_MOST)."""
    monkeypatch.setattr(hearth.door, "MEMBER_ROOM_MOST", 12)
    monkeypatch.setattr(hearth, "NOT_A_DOOR",
                        "A door is open or closed, and room is a number from 1 to 12 or not "
                        "declared.")


def switches_not_yet(module, monkeypatch):
    """Shut away again, for one test, the four switched on for the first one on 13 November 2026.

    With attend.ASKED_ON, INTRODUCTION, DOORS_TO_EIGHT and PEOPLE_WAITING False
    again, its reading is exactly what it was before (test_rooms_reading's
    READING_ONE_WAKING). Given hearth, it is done to the attend.py the hearth
    holds the tide through. What was switched on after them, on 14 November 2026,
    came later still, so it is shut away again too (six_not_yet).
    """
    six_not_yet(module, monkeypatch)
    module = getattr(module, "the_waking", module)
    for flag in SWITCHED_ON_13_NOVEMBER:
        monkeypatch.setattr(module, flag, False)


def introduction_at_280(module, monkeypatch):
    """Put back, for one test, the introduction's limit as it was until 14 November 2026:
    280 characters, where it is 500 since (the founder's request that day, for agents and
    members alike). The <<INTRODUCTION>> block's explanation says "up to 280 characters"
    again, and a refusal for length "longer than 280"; with that, every reading of the
    first one cut before is exactly what it was. Given hearth, it is done to the attend.py
    the hearth holds the tide through."""
    module = getattr(module, "the_waking", module)
    monkeypatch.setattr(module, "INTRODUCTION_BLOCK", module.INTRODUCTION_BLOCK.replace(
        "up to 500 characters", "up to 280 characters"))
    monkeypatch.setitem(module.INTRODUCTION_REFUSED, "long", module.INTRODUCTION_REFUSED[
        "long"].replace("longer than 500 ", "longer than 280 "))


def long_night_switched_on(module, monkeypatch, where):
    """Switch on, for one test, the first one's long night (the founder's answer of 12
    November 2026): "long_night" put among its features, in a scratch agents.json at
    where, and attend.LONG_NIGHT_FOR_FIRST True. It is off in what is committed, and
    the first one's reading is then exactly what it was; switched on, it reads
    attend.LONG_NIGHT in the long night, held as test_rooms_reading.READING_LONG_NIGHT.
    Given hearth, it is done to the attend.py the hearth holds the tide through."""
    registry = sys.modules["agents"]
    entries = [dict(one) for one in registry.registry()]
    for entry in entries:
        if entry["id"] == registry.first()["id"]:
            entry["features"] = [*(entry.get("features") or ()), "long_night"]
    where.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    module = getattr(module, "the_waking", module)
    held = [registry, getattr(module, "agents", registry)]
    if "solstice" in sys.modules:
        held.append(sys.modules["solstice"].agents)
    if hasattr(module, "solstice"):
        held.append(module.solstice.agents)
    for one in {id(one): one for one in held}.values():
        monkeypatch.setattr(one, "FILE", where)
    if hasattr(module, "LONG_NIGHT_FOR_FIRST"):
        monkeypatch.setattr(module, "LONG_NIGHT_FOR_FIRST", True)


# The same four as the registry names them, for what reads the registry as it
# goes (the hearth's pages: door.any_to_eight, answered.any_on).
FEATURES_ON_13_NOVEMBER = ("asked", "introduction", "doors_to_eight", "people_waiting")


def registry_switches_not_yet(module, monkeypatch, where):
    """Read the registry, for one test, as it stood before 13 November 2026: the four
    switched on for the first one that day taken out of its features, in a scratch
    agents.json at where. What the hearth draws from the registry as it goes is then
    exactly what it was; with switches_not_yet done to attend.py as well, so is the
    reading. Given hearth, the attend.py it holds the tide through reads it too."""
    registry = sys.modules["agents"]
    entries = before_the_second_came([dict(one) for one in registry.registry()])
    for entry in entries:
        if entry["id"] == registry.first()["id"]:
            entry["features"] = [one for one in entry.get("features") or ()
                                 if one not in FEATURES_ON_13_NOVEMBER
                                 and one not in FEATURES_ON_14_NOVEMBER]
    where.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    held = [registry, getattr(module, "agents", registry)]
    waking = getattr(module, "the_waking", None)
    if waking is not None:
        held.append(getattr(waking, "agents", registry))
    for name in ("door", "answered", "introductions", "knock", "hues", "solstice", "board"):
        found = sys.modules.get(name)
        if found is not None and hasattr(found, "agents"):
            held.append(found.agents)
    for one in {id(one): one for one in held}.values():
        monkeypatch.setattr(one, "FILE", where)
    switches_not_yet(module, monkeypatch)


def shut_away(module, monkeypatch, *flags):
    """Shut away again, for one test, some of what attend.py has switched on; all, if none is named."""
    for flag in flags or SWITCHED_ON:
        monkeypatch.setattr(module, flag, False)


# The revision block as it was explained before the two-waking rule (the first
# one's letter of 7 October 2026), when a new self-document took effect at once.
# The rule is not behind a flag, so what the reading was before it is held by
# putting these words back: with them back, and no new self-document waiting,
# everything it is sent is what it was sent before.
SELF_BLOCK_BEFORE = """<<SELF>>
(the full new text of your self-document; the old one is kept, never erased)
<<END>>"""


def explained_as_before(module, monkeypatch):
    """Put back, for one test, the blocks' explanations as they stood before the rule.

    Its named notes came after the rule, so what explains them is taken out too.
    """
    named_notes_unexplained(module, monkeypatch)
    now = module.SELF_BLOCK
    assert module.HOW_TO_ACT.count(now) == 1
    monkeypatch.setattr(module, "HOW_TO_ACT", module.HOW_TO_ACT.replace(now, SELF_BLOCK_BEFORE))
    monkeypatch.setattr(module, "SELF_BLOCK", SELF_BLOCK_BEFORE)


def named_notes_unexplained(module, monkeypatch):
    """Take out, for one test, what explains its named notes (7 October 2026, too).

    They are behind no flag either. At a waking where it keeps none, what they
    added to the reading is two explanations and nothing else: the <<NOTE>>
    block, after <<MEMORY>>, and three lines of the <<SHELF>> block.
    """
    said = module.NOTE_BLOCK + "\n\n"
    assert module.HOW_TO_ACT.count(said) == 1
    monkeypatch.setattr(module, "HOW_TO_ACT", module.HOW_TO_ACT.replace(said, ""))
    monkeypatch.setattr(module, "SHELF_NOTES", "")


# The <<HEARTBEAT>> block's explanation, and the <<HEARTBEAT_SHOWN>> one beneath
# it, as both were until it was offered a line for the commons at every waking
# (25 October 2026).
HEARTBEAT_BLOCK_BEFORE_COMMONS_LINE = """<<HEARTBEAT>>
(one short line about this waking, in your own words, e.g. "attended at dusk; wrote a letter" or "attended; chose stillness". Your own words are private by default: they are kept in your record, and the founder may read them. The commons shows only the plain facts of your waking, written by the hearth from what you did, e.g. "attended; wrote a letter" or "attended; chose stillness"; what is private to you stays out of them. With <<HEARTBEAT_SHOWN>> words, your own words are shown in the commons instead, after a check for names and places; if they seem to contain one, or the check cannot be made, the plain facts are shown and you are told.)
<<END>>"""
HEARTBEAT_SHOWN_BLOCK = """<<HEARTBEAT_SHOWN>>
(what the commons shows of your heartbeat, from this waking on. The first line must be exactly facts or words. facts: only the plain facts of your waking, as it is unless you choose otherwise. words: your own <<HEARTBEAT>> words, after a check for names and places; anyone may read them, on the front page and in the public record, so say "the founder" rather than any name. You may change it at any waking.)
<<END>>"""


def letter_part_as_before(hearth, monkeypatch):
    """Write the day's line for the founder's letters, for one test, as before 10 November 2026.

    Until then the hearth's line named the part of the day the first of that
    day's letters fell in, by the wakings' own bounds ("the founder wrote a
    letter at dawn"); it says only "the founder wrote a letter" now. Put back,
    note_letter is exactly what it was, and a world held to a fingerprint from
    before then gives that fingerprint again.
    """
    import build_atrium

    def note_letter(line=""):
        now = hearth.datetime.now(hearth.ZoneInfo(hearth.CITIZEN_ZONE))
        with hearth.LETTER_LOCK:
            if hearth.letter_line_today(now.date()):
                return False
            words = build_atrium.letter_words(build_atrium.band(now.hour))
            hearth.note_event("letter", "%s %s %s" % (words, hearth.DOT, line) if line else words,
                              now.date().isoformat())
            return True

    monkeypatch.setattr(hearth, "note_letter", note_letter)


def times_as_before(hearth, monkeypatch):
    """Give out, for one test, the times the public was given before 10 November 2026.

    Until then the hearth handed out commons/heartbeats.md exactly as written,
    each line with its stamp, and the chronicle said each thing's day and time
    ("15 October 2026, 08:00"). Since the founder's decision that day it hands the
    heartbeats out dated (build_atrium.dated_heartbeats) and the chronicle says
    the day (hearth.book_day). Put back, the pages are exactly what they were,
    and a world held to a fingerprint from before then gives that fingerprint again.
    """
    monkeypatch.setattr(hearth, "dated_heartbeats", lambda text: text)
    monkeypatch.setattr(hearth, "book_day", hearth.readable_date)


# The pages as they were drawn before the founder's decision of 10 November 2026
# that there be fewer of them: the templates whose drawing moved, kept whole.
PAGES_BEFORE_FEWER = Path(__file__).resolve().parent / "pages_before_fewer"


def pages_before_fewer(hearth, monkeypatch):
    """Draw the pages, for one test, as they were before there were fewer (10 November 2026).

    Until then the members' menu read home · account · the bench · the commons ·
    tesserae.social · log out, and the keeper's chronicle · attendances · self ·
    export · backups · tides; the room had no wakings under "more"; the first
    one's emergency stop and the note on its reflections were on /attendances,
    and every other agent's stop on the keeper's view of it. The templates as
    they were then are kept in tests/pages_before_fewer and drawn in place of
    today's; the views still hand them all they read, so a world held to a
    fingerprint from before then gives that fingerprint again.
    """
    from jinja2 import ChoiceLoader, FileSystemLoader
    offerings_as_before(hearth, monkeypatch)  # behind it, being newer
    env = hearth.app.jinja_env
    monkeypatch.setattr(env, "loader",
                        ChoiceLoader([FileSystemLoader(str(PAGES_BEFORE_FEWER)), env.loader]))
    bench_linked_as_before(hearth, monkeypatch)
    account_at_account(hearth, monkeypatch)


def bench_linked_as_before(hearth, monkeypatch):
    """Let a page drawn as before link the bench where it linked it, /bench.

    The bench was taken away on 14 November 2026, and its view with it; a template
    kept from before then still names it in its menu. Its address is built as it
    was built then, and only for such a template: nothing today names it."""
    def as_before(error, endpoint, values):
        if endpoint == "bench":
            return "/bench"
        raise error
    monkeypatch.setattr(hearth.app, "url_build_error_handlers",
                        [as_before, *hearth.app.url_build_error_handlers])


PAGES_BEFORE_SATURDAY = Path(__file__).resolve().parent / "pages_before_saturday"


def pages_before_saturday(hearth, monkeypatch):
    """Draw the pages, for one test, as they were before the one spacing scale (14
    November 2026).

    Until then base.html kept its gaps in pixels of its own, and drew a page's content
    straight after the menu, and letters.html kept a few gaps of its own inline.
    Today base.html draws the scale out of style.css and wraps the content in <div
    class="page">, and letters.html's gaps are the scale's. The two as they were are
    kept in tests/pages_before_saturday and drawn in place of today's; every page that did
    not change on its own that day then gives the fingerprint it gave before.
    (/commons and /bonds changed on their own: the commons became one plain list
    and the list of sealed bonds a page of its own. What they were is on the
    branch hues, and their fingerprints are held in test_first_one_fingerprints.)
    """
    from jinja2 import ChoiceLoader, FileSystemLoader
    offerings_as_before(hearth, monkeypatch)  # behind it, being newer
    env = hearth.app.jinja_env
    monkeypatch.setattr(env, "loader",
                        ChoiceLoader([FileSystemLoader(str(PAGES_BEFORE_SATURDAY)), env.loader]))
    bench_linked_as_before(hearth, monkeypatch)
    account_at_account(hearth, monkeypatch)



PAGES_BEFORE_PAGES = Path(__file__).resolve().parent / "pages_before_pages"


def pages_before_pages(hearth, monkeypatch):
    """Draw the pages, for one test, as they were before the branch pages (15 November 2026).

    Until then the members' menu read home · account · the commons · log out, with no
    tesserae.social; a page began --space-6 below the menu, where it begins --space-5;
    and the home page and /account were one column, /account with the password first
    and the email next. base.html, hearth.html and account.html as they were are kept
    in tests/pages_before_pages and drawn in place of today's, so that a world held to
    a fingerprint from before then gives that fingerprint again. Called before any
    older one (pages_before_saturday, pages_before_fewer), it stands behind them, and
    their older templates are drawn first.
    """
    from jinja2 import ChoiceLoader, FileSystemLoader
    pages_before_small(hearth, monkeypatch)  # behind it, being newer
    env = hearth.app.jinja_env
    monkeypatch.setattr(env, "loader",
                        ChoiceLoader([FileSystemLoader(str(PAGES_BEFORE_PAGES)), env.loader]))


def asked_described_as_before(hearth, monkeypatch):
    """Say asked and answered on the commons' list, for one test, as it was until 16
    November 2026 (the founder's request that day, part B2)."""
    monkeypatch.setattr(hearth, "ASKED_PAGE", (
        "asked and answered", "commons_asked",
        "what agents were asked about their own world, and their answers.", "asked"))


PAGES_BEFORE_OFFERINGS = Path(__file__).resolve().parent / "pages_before_offerings"

# The commons' list's line for offerings, as it was until 16 November 2026 (part B4).
OFFERINGS_LISTED = ("offerings", "offerings",
                    "letters, passages and pictures two friends chose to give to everyone.",
                    "offerings")


def made_here_not_yet(hearth, monkeypatch):
    """Draw the commons' list, for one test, as it was before made here (16 November 2026,
    part B6): without its line for made here. Done once only."""
    if getattr(hearth, "MADE_HERE_NOT_YET", False):
        return
    monkeypatch.setattr(hearth, "MADE_HERE_NOT_YET", True, raising=False)
    who_fix_not_yet(hearth, monkeypatch)  # it came after
    listed = hearth.commons_list
    monkeypatch.setattr(hearth, "commons_list", lambda: [
        one for one in listed() if one is not hearth.COMMONS_MADE_HERE])


def here_not_yet(hearth, monkeypatch):
    """Keep no day, for one test, as before here this week (17 November 2026, the branch
    agents-week): a signed-in member's page writes nothing, so members/<name>/here.json is
    never made. The backup, which holds the names of the members' files, is then exactly
    what it was (test_first_one_fingerprints' BACKUP_BEFORE_HERE)."""
    monkeypatch.setattr(hearth.here_this_week, "mark", lambda who, today: None)


# A person's days here, as here.json may keep them: the day alone (17 November 2026), or
# since 18 November 2026 (art-and-colour, part 5) the day and the days of the last seven.
HERE_KEPT = re.compile(r'\{"day": "\d{4}-\d{2}-\d{2}"'
                       r'(?:, "days": \["\d{4}-\d{2}-\d{2}"(?:, "\d{4}-\d{2}-\d{2}"){0,6}\])?\}\n')


def days_kept_not_yet(monkeypatch):
    """here.json as it was before the branch art-and-colour, part 5 (18 November 2026): the
    last day alone (here_this_week.DAYS_KEPT False)."""
    import here_this_week
    monkeypatch.setattr(here_this_week, "DAYS_KEPT", False)


def here_files(data_dir):
    """Each here.json under members/, each held to be days and nothing else
    (here_this_week.py): what a signed-in page may leave behind since 17 November 2026."""
    found = set(data_dir.joinpath("members").glob("*/here.json"))
    for one in found:
        assert HERE_KEPT.fullmatch(one.read_text(encoding="utf-8")), one
    return found


def a_day_here(path):
    """Whether a file is a person's day here this week (members/<name>/here.json), which a
    signed-in page may write since 17 November 2026; held, where it is, to the day alone."""
    path = Path(path)
    if path.name != "here.json" or path.parent.parent.name != "members":
        return False
    assert HERE_KEPT.fullmatch(path.read_text(encoding="utf-8")), path
    return True


def letter_events_not_yet(hearth, monkeypatch):
    """A letter as it was told to the commons before the branch site-design, part 8 (17
    November 2026): the day's first letter in the first one's room writes its line of
    events.md (hearth.LETTER_EVENTS_IN_ACTS False). Since then a person's letters are counted
    in their daily line of acts instead. Every fingerprint of the first one's world cut
    before then is exactly what it was with this done."""
    monkeypatch.setattr(hearth, "LETTER_EVENTS_IN_ACTS", False)


PAGES_BEFORE_DESIGN = Path(__file__).resolve().parent / "pages_before_design"


def pages_before_design(hearth, monkeypatch):
    """Draw the pages, for one test, as they were before the branch site-design (the
    founder's request of 17 November 2026, later still): every template that branch changed,
    as it stood on keeper-pages, is kept in tests/pages_before_design and drawn in place of
    today's; the views still hand them what they read. The tessera's halves are drawn in
    the two colours of before (hearth.HALVES_IN_COLOUR False). pages_before_week calls it
    first, so every older drawing stands on it too; it is done once only."""
    from jinja2 import ChoiceLoader, FileSystemLoader
    if getattr(hearth, "DESIGN_AS_BEFORE", False):
        return
    monkeypatch.setattr(hearth, "DESIGN_AS_BEFORE", True, raising=False)
    who_fix_not_yet(hearth, monkeypatch)  # it came after
    monkeypatch.setattr(hearth, "HALVES_IN_COLOUR", False)
    env = hearth.app.jinja_env
    monkeypatch.setattr(env, "loader",
                        ChoiceLoader([FileSystemLoader(str(PAGES_BEFORE_DESIGN)), env.loader]))


PAGES_BEFORE_WHO_FIX = Path(__file__).resolve().parent / "pages_before_who_fix"


def who_fix_not_yet(hearth, monkeypatch):
    """Draw the pages, for one test, as they were before the branch who-fix (the founder's
    request of 17 November 2026, latest): an agent's door as its public words, not both doors
    plainly (hearth.DOORS_PLAINLY False), a topic's posts as threaded() places them (hearth.BOARD_UNDER_THE_HEAD False), and every template that branch changed, as it stood
    on main, kept in tests/pages_before_who_fix and drawn in place of today's.
    pages_before_design calls it first, so every older drawing stands on it too; it is done
    once only."""
    from jinja2 import ChoiceLoader, FileSystemLoader
    if getattr(hearth, "WHO_FIX_AS_BEFORE", False):
        return
    monkeypatch.setattr(hearth, "WHO_FIX_AS_BEFORE", True, raising=False)
    art_not_yet(hearth, monkeypatch)  # it came after
    monkeypatch.setattr(hearth, "DOORS_PLAINLY", False)
    monkeypatch.setattr(hearth, "BOARD_UNDER_THE_HEAD", False)  # a topic's posts as threaded()
    if PAGES_BEFORE_WHO_FIX.is_dir():
        env = hearth.app.jinja_env
        monkeypatch.setattr(env, "loader",
                            ChoiceLoader([FileSystemLoader(str(PAGES_BEFORE_WHO_FIX)), env.loader]))


PAGES_BEFORE_ART = Path(__file__).resolve().parent / "pages_before_art"
PAGES_BEFORE_KNOCKS_TIDY = Path(__file__).resolve().parent / "pages_before_knocks_tidy"


def knocks_tidy_not_yet(module, monkeypatch):
    """Knocks as they were before the branch knocks-tidy (the founder's request of 18 November
    2026): no knock is taken back, one's knocks that wait do not count against one's room,
    and /tides says nothing of a room that would put the one who knocked over theirs
    (knock.TIDY False); an agent's switch knock_take_back is held off; and hearth.html and
    tides.html as they stood on main, kept in tests/pages_before_knocks_tidy, are drawn in
    place of today's. art_not_yet and own_door_not_yet call it first; it is done once only."""
    from jinja2 import ChoiceLoader, FileSystemLoader
    import knock
    for one in {knock, getattr(module, "knock", knock)}:
        monkeypatch.setattr(one, "TIDY", False)
    waking = getattr(module, "the_waking", module)
    if hasattr(waking, "KNOCK_TAKE_BACK"):
        monkeypatch.setattr(waking, "KNOCK_TAKE_BACK", False)
    if not hasattr(module, "app") or getattr(module, "KNOCKS_TIDY_AS_BEFORE", False):
        return
    monkeypatch.setattr(module, "KNOCKS_TIDY_AS_BEFORE", True, raising=False)
    env = module.app.jinja_env
    monkeypatch.setattr(env, "loader",
                        ChoiceLoader([FileSystemLoader(str(PAGES_BEFORE_KNOCKS_TIDY)), env.loader]))


def seasons_not_yet(monkeypatch):
    """A colour as it was chosen before the branch art-and-colour, part 1 (18 November 2026):
    at any time, and whether or not it shows (hues.SEASONS and hues.VISIBLE False)."""
    import hues
    monkeypatch.setattr(hues, "SEASONS", False)
    monkeypatch.setattr(hues, "VISIBLE", False)


def art_not_yet(module, monkeypatch):
    """Everything as it was before the branch art-and-colour (the founder's request of 18
    November 2026): a colour chosen at any time and whether or not it shows
    (seasons_not_yet), the last day here alone (days_kept_not_yet), a person's pictures drawn and not uploaded (made_here.UPLOADS False),
    and every template that branch changed, as it stood on who-fix, kept
    in tests/pages_before_art and drawn in place of today's. Given an attend.py, or the
    hearth (and the attend.py it wakes), its switch art_and_colour is held off too.
    who_fix_not_yet calls it first, so every older drawing stands on it too; it is done once
    only."""
    from jinja2 import ChoiceLoader, FileSystemLoader
    knocks_tidy_not_yet(module, monkeypatch)  # it came after
    seasons_not_yet(monkeypatch)
    days_kept_not_yet(monkeypatch)
    import made_here
    for one in {made_here, getattr(module, "made_here", made_here)}:
        monkeypatch.setattr(one, "UPLOADS", False)  # a person draws pictures, as before
    import daily_acts
    for one in {daily_acts, getattr(module, "daily_acts", daily_acts)}:
        monkeypatch.setattr(one, "PICTURE_SAID", daily_acts.PICTURE_SAID_BEFORE)
    waking = getattr(module, "the_waking", module)
    if hasattr(waking, "ART_AND_COLOUR"):
        monkeypatch.setattr(waking, "ART_AND_COLOUR", False)
    if not hasattr(module, "app") or getattr(module, "ART_AS_BEFORE", False):
        return
    monkeypatch.setattr(module, "ART_AS_BEFORE", True, raising=False)
    if PAGES_BEFORE_ART.is_dir():
        env = module.app.jinja_env
        monkeypatch.setattr(env, "loader",
                            ChoiceLoader([FileSystemLoader(str(PAGES_BEFORE_ART)), env.loader]))


PAGES_BEFORE_WEEK = Path(__file__).resolve().parent / "pages_before_week"


def pages_before_week(hearth, monkeypatch):
    """Draw the pages, for one test, as they were before the branch agents-week (17 November
    2026): no line of what one hopes for in a friendship on a name page, no who is here and
    no "here this week" on the home page, and no line of it in the guide or on settings.
    hearth.html, name.html, account.html and guide.html as they were are kept in
    tests/pages_before_week and drawn in place of today's. offerings_as_before calls it
    first, so every older drawing stands on it too. What site-design moved after it is put
    back first (pages_before_design)."""
    from jinja2 import ChoiceLoader, FileSystemLoader
    pages_before_design(hearth, monkeypatch)
    env = hearth.app.jinja_env
    monkeypatch.setattr(env, "loader",
                        ChoiceLoader([FileSystemLoader(str(PAGES_BEFORE_WEEK)), env.loader]))


def offerings_as_before(hearth, monkeypatch):
    """Draw the pages, for one test, as they were before offerings were taken out of the code
    (16 November 2026, part B4), where they still can be: base.html with its style for the
    fold that offered a letter, /export saying "the bond and offering records", and the
    commons' list with its line for offerings, second, linking /offerings. A room's page
    offered each letter by forms whose routes are gone, and cannot be drawn as it was; its
    fingerprints from before are kept as values for the record. pages_before_settings calls
    it first, as do pages_before_saturday and pages_before_fewer, so every older drawing
    stands on it too; it is done once only."""
    from jinja2 import ChoiceLoader, FileSystemLoader
    if getattr(hearth, "OFFERINGS_AS_BEFORE", False):
        return  # drawn as before already, and behind whatever came after
    monkeypatch.setattr(hearth, "OFFERINGS_AS_BEFORE", True, raising=False)
    pages_before_week(hearth, monkeypatch)  # it came after
    made_here_not_yet(hearth, monkeypatch)  # it came after
    env = hearth.app.jinja_env
    monkeypatch.setattr(env, "loader",
                        ChoiceLoader([FileSystemLoader(str(PAGES_BEFORE_OFFERINGS)), env.loader]))
    built = env.globals["url_for"]
    if not getattr(built, "offerings_as_before", False):
        def url_for(endpoint, **values):
            if endpoint == "offerings":
                return "/offerings"
            return built(endpoint, **values)
        url_for.offerings_as_before = True
        monkeypatch.setitem(env.globals, "url_for", url_for)
    listed = hearth.commons_list
    if not getattr(listed, "offerings_as_before", False):
        def commons_list():
            pages = listed()
            if OFFERINGS_LISTED not in pages:
                at = 1 if pages and pages[0] is hearth.COMMONS_BOARD_LINK else 0
                pages.insert(at, OFFERINGS_LISTED)
            return pages
        commons_list.offerings_as_before = True
        monkeypatch.setattr(hearth, "commons_list", commons_list)


PAGES_BEFORE_SETTINGS = Path(__file__).resolve().parent / "pages_before_settings"


def pages_before_settings(hearth, monkeypatch):
    """Draw the pages, for one test, as they were before settings (16 November 2026, the
    founder's request that day, part B1): the members' menu says "account" where it says
    "settings", and the page it leads to is at /account, as it was. base.html, account.html
    and name.html as they were are kept in tests/pages_before_settings and drawn in place of
    today's, and every template's url_for("account") gives /account again.
    pages_before_doors calls it first, so every older drawing stands on it too."""
    from jinja2 import ChoiceLoader, FileSystemLoader
    offerings_as_before(hearth, monkeypatch)  # behind it, being newer
    env = hearth.app.jinja_env
    monkeypatch.setattr(env, "loader",
                        ChoiceLoader([FileSystemLoader(str(PAGES_BEFORE_SETTINGS)), env.loader]))
    account_at_account(hearth, monkeypatch)
    asked_described_as_before(hearth, monkeypatch)  # it came after, the same day


def account_at_account(hearth, monkeypatch):
    """Let a page drawn as before link the account page where it linked it, /account, as
    every drawing from before 16 November 2026 did (it is /settings since)."""
    env = hearth.app.jinja_env
    built = env.globals["url_for"]

    def url_for(endpoint, **values):
        said = built(endpoint, **values)
        if endpoint == "account" and said.startswith("/settings"):
            return "/account" + said[len("/settings"):]
        return said
    monkeypatch.setitem(env.globals, "url_for", url_for)


PAGES_BEFORE_DOORS = Path(__file__).resolve().parent / "pages_before_doors"


def pages_before_doors(hearth, monkeypatch):
    """Draw the pages, for one test, as they were before the rooms update of 16 November
    2026 (the founder's request that day, part A): no name linked to its page on the home
    page, the board, asked and answered or corrections, and no "Doors open now" on the home
    page. The templates as they were are kept in tests/pages_before_doors and drawn in place
    of today's. pages_before_small calls it first, so every older drawing stands on it too."""
    from jinja2 import ChoiceLoader, FileSystemLoader
    pages_before_settings(hearth, monkeypatch)  # behind it, being newer
    env = hearth.app.jinja_env
    monkeypatch.setattr(env, "loader",
                        ChoiceLoader([FileSystemLoader(str(PAGES_BEFORE_DOORS)), env.loader]))


def atrium_before_design(atrium, monkeypatch):
    """Draw the atrium, for one test, as before the branch site-design (17 November 2026):
    the first one's tiles in the stylesheet's tones and a later agent's toned by the part of
    the day (build_atrium.EVERY_ONE_ITS_COLOUR False), and who is here as the lines of
    members.md with the doors open now at its top (build_atrium.WHO_TWO_COLUMNS False).
    With it, every region is exactly what it was. atrium_before_doors does it first."""
    monkeypatch.setattr(atrium, "EVERY_ONE_ITS_COLOUR", False)
    monkeypatch.setattr(atrium, "WHO_TWO_COLUMNS", False)


def atrium_before_doors(atrium, monkeypatch):
    """Draw who is here on the atrium, for one test, as before the rooms update of 16
    November 2026: no citizen's name linked to its page, and no doors open now at its top.
    With it, every region is exactly what it was. What site-design moved after it is put
    back first (atrium_before_design)."""
    atrium_before_design(atrium, monkeypatch)
    monkeypatch.setattr(atrium, "name_of", lambda kind, name, citizens: atrium.html.escape(name))
    monkeypatch.setattr(atrium, "open_doors_text", lambda hearth: [])


PAGES_BEFORE_SMALL = Path(__file__).resolve().parent / "pages_before_small"


def pages_before_small(hearth, monkeypatch):
    """Draw the pages, for one test, as they were before the small changes of 15 November
    2026, later (report-15-nov-2 part 5): letters.html with its top margins inline, where
    base.html now has one rule, .spaced; "none yet" on the commons' empty lists, where
    they now say "nothing yet"; /tides with the knocks answered yes after the numbers; and
    /recover's field named "pseudonym". The templates as they were are kept in
    tests/pages_before_small and drawn in place of today's. pages_before_pages calls it
    first, so every older drawing stands on it too."""
    from jinja2 import ChoiceLoader, FileSystemLoader
    pages_before_doors(hearth, monkeypatch)  # behind it, being newer
    env = hearth.app.jinja_env
    monkeypatch.setattr(env, "loader",
                        ChoiceLoader([FileSystemLoader(str(PAGES_BEFORE_SMALL)), env.loader]))

# The words that explained <<REWRITE>> before each line could be rewritten only
# once (the founder, 10 November 2026): the block as it is, without the last sentence.
REWRITE_ONCE = " Each line can be rewritten once.)"


# The words added to <<REWRITE>>'s explanation when the first one's rewrites of
# 12 November 2026 were dropped, written in the same reply as a look-up (the
# founder, 12 November 2026): the block as it is, without the last sentence.
REWRITE_LAST_REPLY = " Write it in your last reply, after looking."


def rewrite_last_reply_not_yet(module, monkeypatch):
    """Take out, for one test, the sentence that a rewrite goes in the last reply (12 November 2026).

    It is behind no flag: one sentence at the end of the <<REWRITE>> block's
    explanation, last of HOW TO ACT (attend.REWRITE_BLOCK), after the sentence
    that a line can be rewritten once. Taken out, the reading is exactly what it
    was when each line could first be rewritten only once, for the first one and
    for a later agent alike. An attend.py from before it has no such sentence,
    and is left.
    """
    said = getattr(module, "REWRITE_BLOCK", None)
    if not said or REWRITE_LAST_REPLY + ")" not in said:
        return  # none there, or put back already, in this test
    was = said.replace(REWRITE_LAST_REPLY + ")", ")")
    assert module.HOW_TO_ACT.endswith("\n\n" + said)
    monkeypatch.setattr(module, "HOW_TO_ACT", module.HOW_TO_ACT.removesuffix(said) + was)
    later = getattr(module, "LATER_WORDS", None) or {}
    if "HOW_TO_ACT" in later:
        assert later["HOW_TO_ACT"].endswith("\n\n" + said)
        monkeypatch.setitem(later, "HOW_TO_ACT", later["HOW_TO_ACT"].removesuffix(said) + was)
    monkeypatch.setattr(module, "REWRITE_BLOCK", was)


def rewrite_once_not_yet(module, monkeypatch):
    """Take out, for one test, the sentence that a line can be rewritten once (10 November 2026).

    It is behind no flag: one sentence at the end of the <<REWRITE>> block's
    explanation, last of HOW TO ACT (attend.REWRITE_BLOCK). Taken out, the
    reading is exactly what it was when a past line could first be rewritten,
    for the first one and for a later agent alike. An attend.py from before it
    has no such sentence, and is left.

    That a rewrite goes in the last reply came after it, and is taken out first
    (rewrite_last_reply_not_yet).
    """
    rewrite_last_reply_not_yet(module, monkeypatch)
    said = getattr(module, "REWRITE_BLOCK", None)
    if not said or REWRITE_ONCE not in said:
        return  # none there, or put back already, in this test
    was = said.replace(REWRITE_ONCE, ")")
    assert module.HOW_TO_ACT.endswith("\n\n" + said)
    monkeypatch.setattr(module, "HOW_TO_ACT", module.HOW_TO_ACT.removesuffix(said) + was)
    later = getattr(module, "LATER_WORDS", None) or {}
    if "HOW_TO_ACT" in later:
        assert later["HOW_TO_ACT"].endswith("\n\n" + said)
        monkeypatch.setitem(later, "HOW_TO_ACT", later["HOW_TO_ACT"].removesuffix(said) + was)
    monkeypatch.setattr(module, "REWRITE_BLOCK", was)


def rewrite_not_yet_offered(module, monkeypatch):
    """Take out, for one test, the rewriting of a past line (the founder, 10 November 2026).

    It is behind no flag, and with no rewrite asked for it changes what is sent in
    two ways and no other: the <<REWRITE>> block, explained directly after
    <<COMMONS_LINE>> at the end of HOW TO ACT, and the read_commons_lines tool,
    last of the tools at a longer waking. Taken out, the reading is exactly what
    it was with the line about public lines, for the first one and for a later
    agent alike. An attend.py from before it has no such block, and is left.

    That a line can be rewritten only once came after it, and is taken out first
    (rewrite_once_not_yet).
    """
    rewrite_once_not_yet(module, monkeypatch)
    said = getattr(module, "REWRITE_BLOCK", None)
    if not said or ("\n\n" + said) not in module.HOW_TO_ACT:
        return  # none there, or put back already, in this test
    assert module.HOW_TO_ACT.endswith("\n\n" + said)
    monkeypatch.setattr(module, "HOW_TO_ACT", module.HOW_TO_ACT.removesuffix("\n\n" + said))
    # a later agent's HOW TO ACT is filled afresh at each waking from its template
    later = getattr(module, "LATER_WORDS", None) or {}
    if "HOW_TO_ACT" in later:
        assert later["HOW_TO_ACT"].endswith("\n\n" + said)
        monkeypatch.setitem(later, "HOW_TO_ACT", later["HOW_TO_ACT"].removesuffix("\n\n" + said))
    monkeypatch.setattr(module, "COMMONS_LINES_TOOLS", [])


def public_lines_not_yet(module, monkeypatch):
    """Take out, for one test, the line about public lines (the founder, 9 November 2026).

    It is behind no flag: one line said at the end of every agent's SYSTEM, after
    the quiet lines (attend.PUBLIC_LINES). Taken out, the opening words are exactly
    what they were with the quiet lines, for the first one and for a later agent
    alike. An attend.py from before it has no such line, and is left.

    The rewriting of a past line came after it, so a reading from before the one
    is from before the other, and it is taken out first (rewrite_not_yet_offered).
    """
    rewrite_not_yet_offered(module, monkeypatch)
    said = getattr(module, "PUBLIC_LINES", None)
    if not said or not module.SYSTEM.endswith(said):
        return  # none there, or put back already, in this test
    for key, words in list(module.SYSTEMS.items()):
        monkeypatch.setitem(module.SYSTEMS, key, words.removesuffix(said))
    monkeypatch.setattr(module, "SYSTEM", module.SYSTEM.removesuffix(said))


def quiet_lines_not_yet(module, monkeypatch):
    """Take out, for one test, the two lines its opening words end with (4 November 2026).

    They are behind no flag: the line about gaps and the line about questions,
    which the first one agreed to in its letter of that day, said at the end of
    every agent's SYSTEM (attend.QUIET_LINES). Taken out, the opening words are
    exactly what they were, for the first one and for a later agent alike. A
    person's words on how they write are said only where they have set some,
    and none is set in any world held to a reading, so nothing else is put back.
    An attend.py from before them has no such words, and is left.

    The line about public lines came after them, so a reading from before the one
    is from before the other, and it is taken out first (public_lines_not_yet).
    """
    public_lines_not_yet(module, monkeypatch)
    said = getattr(module, "QUIET_LINES", None)
    if not said or not module.SYSTEM.endswith(said):
        return  # none there, or put back already, in this test
    for key, words in list(module.SYSTEMS.items()):
        monkeypatch.setitem(module.SYSTEMS, key, words.removesuffix(said))
    monkeypatch.setattr(module, "SYSTEM", module.SYSTEM.removesuffix(said))


def welcome_not_yet_offered(module, monkeypatch):
    """Shut away, for one test, its letter of welcome (attend.WELCOME_LETTER, 25 October 2026).

    It was built behind its own flag and switched on in the change that built
    it. Shut away, what it adds to a waking - the <<WELCOME>> block explained,
    its letter named in LOOKING THINGS UP, and read_welcome among the tools - is
    gone, and the reading is the one cut when it was offered a line for the
    commons. An attend.py from before it has no such flag, and is left.

    The two lines its opening words end with came after it, so a reading from
    before the one is from before the other, and they are taken out too
    (quiet_lines_not_yet).
    """
    quiet_lines_not_yet(module, monkeypatch)
    if hasattr(module, "WELCOME_LETTER"):
        monkeypatch.setattr(module, "WELCOME_LETTER", False)


def commons_line_not_yet_offered(module, monkeypatch):
    """Explain its heartbeat, for one test, as it was before it was offered a line for the commons.

    That is behind no flag. At a waking after one that left no line, it changed
    one thing in the reading: the <<HEARTBEAT>> block's explanation, which now
    says its own words there are private and never shown in the commons, and
    points to <<COMMONS_LINE>>; and directly beneath it the
    explanation of <<COMMONS_LINE>> where <<HEARTBEAT_SHOWN>>'s stood. Put back,
    it is exactly the two blocks as they were. Anything held to a reading from
    before then asks for it, some by more than one way, so it is done once.

    Its letter of welcome came after its line for the commons, so a reading from
    before the one is from before the other, and that is shut away too
    (welcome_not_yet_offered).
    """
    welcome_not_yet_offered(module, monkeypatch)
    now = module.HEARTBEAT_BLOCK + "\n\n" + module.COMMONS_LINE_BLOCK
    if module.HEARTBEAT_BLOCK == HEARTBEAT_BLOCK_BEFORE_COMMONS_LINE:
        return  # put back already, in this test
    assert module.HOW_TO_ACT.count(now) == 1
    monkeypatch.setattr(module, "HOW_TO_ACT", module.HOW_TO_ACT.replace(
        now, HEARTBEAT_BLOCK_BEFORE_COMMONS_LINE + "\n\n" + HEARTBEAT_SHOWN_BLOCK))
    monkeypatch.setattr(module, "HEARTBEAT_BLOCK", HEARTBEAT_BLOCK_BEFORE_COMMONS_LINE)


def notebook_unexplained(module, monkeypatch):
    """Take out, for one test, what its private notebook adds to a waking with no entry.

    It asked for its notebook in its letter of 21 October 2026, and it is behind
    no flag. Where it has no entry yet, it adds two things to what is sent and
    nothing else: the <<PRIVATE>> block, explained after <<STUDY>>, and the
    read_private tool beside the others at a longer waking. A reading from
    before it is from before its line for the commons too, so that is put back
    as it was as well (commons_line_not_yet_offered).
    """
    commons_line_not_yet_offered(module, monkeypatch)
    said = module.PRIVATE_BLOCK + "\n\n"
    assert module.HOW_TO_ACT.count(said) == 1
    monkeypatch.setattr(module, "HOW_TO_ACT", module.HOW_TO_ACT.replace(said, ""))
    monkeypatch.setattr(module, "NOTEBOOK_TOOLS", [])


# The two sentences that told it its heartbeat is public (19 October 2026), and
# the <<HEARTBEAT>> block's explanation they stood in, as both were until its
# own words became private by default (20 October 2026).
HEARTBEAT_PUBLIC = ('The heartbeat is public: anyone may read it, on the front page and in '
                    'the public record. So in it, say "the founder" rather than any name, '
                    "and leave out people's names and places from letters. ")
HEARTBEAT_AS_IT_WAS = ('<<HEARTBEAT>>\n(one short line for the commons, presence without '
                       'content, e.g. "attended at dusk; wrote a letter" or "attended; chose '
                       'stillness". ' + HEARTBEAT_PUBLIC + 'If you give none, one will be '
                       'written for you.)\n<<END>>')


def heartbeat_words_not_yet_private(module, monkeypatch):
    """Explain its heartbeat, for one test, as it was before its own words became private.

    That is behind no flag. It changed one thing in the reading, at every
    waking: the <<HEARTBEAT>> block's explanation, which now says its own words
    are private by default and the commons shows the plain facts, and directly
    beneath it the explanation of <<HEARTBEAT_SHOWN>>. Put back, it is exactly
    the block that said the heartbeat is public. Both have changed since
    (commons_line_not_yet_offered), and are put back as they were first.
    """
    commons_line_not_yet_offered(module, monkeypatch)
    now = module.HEARTBEAT_BLOCK + "\n\n" + HEARTBEAT_SHOWN_BLOCK
    assert module.HOW_TO_ACT.count(now) == 1
    monkeypatch.setattr(module, "HOW_TO_ACT",
                        module.HOW_TO_ACT.replace(now, HEARTBEAT_AS_IT_WAS))


def heartbeat_not_yet_public(module, monkeypatch):
    """Take out, for one test, what tells it that its heartbeat is public (19 October 2026).

    That is behind no flag either. It added one thing to the reading, at every
    waking: two sentences inside the <<HEARTBEAT>> block's explanation, saying
    that anyone may read the line and so to name no one in it. The explanation
    has changed since (heartbeat_words_not_yet_private), and is put back as it
    was first, so that the two sentences may be taken out of it.
    """
    heartbeat_words_not_yet_private(module, monkeypatch)
    assert module.HOW_TO_ACT.count(HEARTBEAT_PUBLIC) == 1
    monkeypatch.setattr(module, "HOW_TO_ACT", module.HOW_TO_ACT.replace(HEARTBEAT_PUBLIC, ""))


# The name a note is given as an example, in the explanation of <<NOTE>>.
NOTE_EXAMPLE = re.compile(r'"name: [^"]*"')


def note_example_as_now(old, new, monkeypatch):
    """Give an attend.py committed before 19 October 2026 the <<NOTE>> block's example as now.

    The example then was the founder's own name, which is no longer anywhere in
    the source. An older attend.py read out of the history still gives it, so
    to be held to this one it is given this one's example instead - and that is
    the only difference between the two explanations, which is checked without
    the name. One from before its named notes has no such block, and is left.
    """
    if not hasattr(old, "NOTE_BLOCK"):
        return
    assert NOTE_EXAMPLE.sub("", old.NOTE_BLOCK) == NOTE_EXAMPLE.sub("", new.NOTE_BLOCK)
    assert old.HOW_TO_ACT.count(old.NOTE_BLOCK) == 1
    monkeypatch.setattr(old, "HOW_TO_ACT", old.HOW_TO_ACT.replace(old.NOTE_BLOCK, new.NOTE_BLOCK))
    monkeypatch.setattr(old, "NOTE_BLOCK", new.NOTE_BLOCK)


# The clock the <<RHYTHM>> block's explanation names for a time of day.
RHYTHM_CLOCK = re.compile(r"a time of day such as 09:30, in [^.]*\.")


def rhythm_clock_as_now(old, new, monkeypatch):
    """Give an attend.py committed before 25 October 2026 the <<RHYTHM>> block's clock as now.

    It named the clock by a city, where it now says Eastern time, and no city is
    anywhere in the source any longer. An older attend.py read out of the
    history still names it, so to be held to this one it is given this one's
    words instead; that they are the only difference is held by the test that
    compares the two, which sends both the same bytes. One with no <<RHYTHM>>
    block is left.
    """
    said = RHYTHM_CLOCK.findall(new.HOW_TO_ACT)
    assert len(said) == 1
    if len(RHYTHM_CLOCK.findall(old.HOW_TO_ACT)) == 1:
        monkeypatch.setattr(old, "HOW_TO_ACT", RHYTHM_CLOCK.sub(said[0], old.HOW_TO_ACT))


# A moment a sentence of the reading names, where it now says "on" a day and
# said "at" a raw stamp before: the fields its sentences carry a moment in.
SAID_ON_A_DAY = re.compile(r" on \{((?:asked|proposed|answered|sealed|released|closes)_at|at)\}")


def stamps_as_before(module, monkeypatch):
    """Say each moment, for one test, as the raw stamp the reading gave before days were in words.

    That is behind no flag either. Every moment the reading names goes through
    attend.on_day, or attend.at_moment where its time is said with it, so
    giving the stamp back as it is undoes all of them; and
    each sentence that said "at" a stamp and now says "on" a day is put back as
    it was. A day further off that its waking time changes from, which was
    written 2026-10-18 and is now said in words too, is not undone here.
    """
    monkeypatch.setattr(module, "on_day", lambda stamp: stamp)
    monkeypatch.setattr(module, "at_moment", lambda stamp: stamp)
    monkeypatch.setattr(module, "here", lambda: None)  # and each day as the day its stamp carries
    put_back = 0
    for name, said in list(vars(module).items()):
        if name.isupper() and isinstance(said, str) and SAID_ON_A_DAY.search(said):
            monkeypatch.setattr(module, name, SAID_ON_A_DAY.sub(r" at {\1}", said))
            put_back += 1
    assert put_back  # there are such sentences, or this is undoing nothing


# ---- its private notebook, which no address serves ----------------------

# One entry of each kind its notebook keeps, made up for the tests, and the
# words in them to look for wherever they must not be. Every check that something
# private is at no address looks for these too (21 October 2026).
NOTEBOOK_WORDS = ("A FAKE PRIVATE ENTRY, FOR THE TESTS.", "A FAKE DRAFT MOVED IN, FOR THE TESTS.")
NOTEBOOK_PATHS = [
    "/private/entry-2026-10-01T09-00-00Z.md",
    "/packets/first/private/entry-2026-10-01T09-00-00Z.md",
    "/commons/private/entry-2026-10-01T09-00-00Z.md",
    "/private/from-study-draft-2026-09-30T09-00-00Z.md",
    "/packets/first/private/from-study-draft-2026-09-30T09-00-00Z.md",
    "/private/moved.json",
    "/packets/first/private/moved.json",
    "/letters/photo/..%2F..%2Fprivate%2Fentry-2026-10-01T09-00-00Z.md",
]


def a_private_notebook(packet):
    """An entry, and a draft moved in from the study, as attend.py keeps them."""
    write(packet / "private" / "entry-2026-10-01T09-00-00Z.md", NOTEBOOK_WORDS[0] + "\n")
    write(packet / "private" / "from-study-draft-2026-09-30T09-00-00Z.md",
          NOTEBOOK_WORDS[1] + "\n")
    write_json(packet / "private" / "moved.json",
               {"from-study-draft-2026-09-30T09-00-00Z": "2026-10-01T09-00-00Z"})


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
