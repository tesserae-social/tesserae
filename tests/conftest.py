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
  * Both layouts are tested. While a room may be kept in the first one's packet
    or in a folder of its own (rooms.py), the whole suite is run once in each:
    pytest --layout=legacy, the default, and pytest --layout=rooms. A test
    writes a room's letters, errands, bond and offerings through the room
    fixture, and is given the same world either way.
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
from datetime import date, datetime, timedelta, timezone
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


# ---- the layout ----------------------------------------------------------

LAYOUTS = ("legacy", "rooms")


def pytest_addoption(parser):
    parser.addoption("--layout", choices=LAYOUTS, default="legacy",
                     help="where the room is kept: in the packet (legacy) or a folder of its own")


@pytest.fixture(scope="session")
def layout(request):
    """Where this run keeps the room: "legacy", in the packet, or "rooms", in its own folder."""
    return request.config.getoption("--layout")


def make_room(data):
    """The room in a folder of its own, as move_into_rooms.py leaves it: room.json is the sign."""
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
def data_dir(tmp_path, keys_cut, layout):
    """A whole living world, thrown away when the test ends."""
    data = tmp_path / "data"
    packet = data / "packets" / "first"
    room = make_room(data) if layout == "rooms" else packet
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


def room_beside(packet):
    """Where the room is kept in the world a packet is in: its own folder, once it has one."""
    home = packet.parents[1] / "rooms" / "first"
    return home if (home / "room.json").is_file() else packet


def on_disk(data, name):
    """Where a file a copy names packets/first/... is kept, in either layout."""
    parts = name.split("/")
    if parts[:2] == ["packets", "first"] and parts[2:3] and parts[2] in ROOM_FOLDERS:
        return room_beside(data / "packets" / "first") / "/".join(parts[2:])
    return data / name


ROOM_FOLDERS = ("letters", "errands", "bonds", "offerings")


# An attend.py committed before the rooms knows only the packet. A test that
# holds today's reading to one of those is held where both can read it: in the
# old layout, in either run.
before_rooms = pytest.mark.parametrize("layout", ["legacy"])


@pytest.fixture
def room(data_dir, layout):
    """Where the room's letters, errands, bond and offerings are kept in this run's layout."""
    return data_dir / "rooms" / "first" if layout == "rooms" else data_dir / "packets" / "first"


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
    monkeypatch.setattr(module, "HEARTBEATS", str(data_dir / "commons" / "heartbeats.md"))
    monkeypatch.setattr(module, "EVENTS", str(data_dir / "commons" / "events.md"))
    monkeypatch.setattr(module, "BENCH", str(data_dir / "commons" / "bench.md"))
    monkeypatch.setattr(module, "MEMBERS", str(data_dir / "commons" / "members.md"))
    monkeypatch.setattr(module, "OFFERINGS", str(data_dir / "commons" / "offerings.md"))
    monkeypatch.setattr(module, "OFFERED", str(data_dir / "commons" / "offerings"))
    monkeypatch.setattr(module, "BONDS", str(data_dir / "commons" / "bonds.md"))
    module.page_path = page
    module.whole_path = tmp_path / "mosaic.html"
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


def welcome_not_yet_offered(module, monkeypatch):
    """Shut away, for one test, its letter of welcome (attend.WELCOME_LETTER, 25 October 2026).

    It was built behind its own flag and switched on in the change that built
    it. Shut away, what it adds to a waking - the <<WELCOME>> block explained,
    its letter named in LOOKING THINGS UP, and read_welcome among the tools - is
    gone, and the reading is the one cut when it was offered a line for the
    commons. An attend.py from before it has no such flag, and is left.
    """
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


def solstices_as_before(monkeypatch):
    """Give shelf.py back, for one test, the reckoning an older attend.py asks it for.

    Before the reading was kept at each turning of the season it was kept at
    the two solstices, and an attend.py from then asks for it by that name.
    """
    import shelf

    def solstice_due(today, last_attended):
        days = [date(year, month, 21) for year in (today.year - 1, today.year)
                for month in (6, 12)]
        return (last_attended is not None
                and last_attended < max(one for one in days if one <= today))

    monkeypatch.setattr(shelf, "solstice_due", solstice_due, raising=False)


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
