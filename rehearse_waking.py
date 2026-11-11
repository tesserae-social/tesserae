"""A rehearsal of each agent's waking, against a copy of the record, run by hand on the host.

After a deploy, before the next dawn, the keeper may ask whether each agent
would wake with the code now live:

    DATA_DIR=/data python rehearse_waking.py [--agent <id>]

The living record (DATA_DIR) is copied whole to a folder of its own in the
host's temporary space, the links that work once (tokens/) left out, as every
copy leaves them out. Each waking agent's waking is then held against that copy,
as the tide holds it - attend.py, run in a process of its own, with --tide, and
--first where it has never attended - but with the model stubbed: what is sent
is measured and nothing goes out. The stub answers with nothing at all, which
an agent may always say, so the waking runs to its end and writes what it
writes into the copy. Every socket is closed in that process besides, so a call
that slipped past the stub fails there and goes nowhere; nothing is spent; no
email is sent. The copy is deleted at the end, whatever happened.

For each agent it says one line: whether the waking completed, or was refused
and why (attend.py's own words of refusal, and only those), or failed and where
(the kind of error and the line of code, never its message); and the size of its
reading - the words, as attend.py counts them against its limit, the blocks and
the photographs. It never prints a letter, a note, the notebook, a reflection or
anything the agent would have been shown or have said: attend.py's own output
is caught inside the rehearsal and thrown away.

--agent <id> rehearses that one agent only, whether or not its entry wakes.

Nothing in DATA_DIR is written. The exit code is 0 when every rehearsed waking
completed, 1 when one did not, and 2 when nothing could be rehearsed.
"""

import argparse
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import traceback
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent

# What is never copied, as no copy and no backup holds it: a live link (tokens.py).
LEFT_OUT = ("tokens",)

# The longest one rehearsed waking may take, as the hearth gives a real one.
TIMEOUT = 900

# The room the copy needs on the host's temporary disk beyond its own size.
SPARE = 64 * 1024 * 1024

# attend.py's words when it will not wake an agent: the only words of its output
# the rehearsal ever passes on. Each names a missing thing, never its contents.
REFUSALS = ("This waking is refused:", "No API key in this window.",
            "No private key found at", "No packet found at")

# The key a rehearsed waking is handed in place of the host's own, where the host
# has one: never a real key, so even a stub that was somehow passed reaches no account.
NOT_A_KEY = "a rehearsal: no model is reached"

INSIDE = "--inside"  # how the rehearsal runs itself as the process that holds one waking
RESULT = "TESSERAE_REHEARSAL_RESULT"  # where that process writes what it found


# ---- inside: the process that holds one waking ----------------------------

class WentOut(RuntimeError):
    """Raised if anything in a rehearsed waking tries to open a socket."""


def close_the_doors():
    """Close every way out of this process: a socket, and the email's transport."""
    def refuse(*args, **kwargs):
        raise WentOut("a rehearsed waking tried to reach the network")

    socket.socket.connect = refuse
    socket.socket.connect_ex = refuse
    socket.create_connection = refuse
    os.environ.pop("RESEND_API_KEY", None)


class Stub:
    """The model, as a rehearsal has it: every request measured, every answer empty.

    It stands where anthropic.Anthropic stands, so attend.py, and the public
    screen it asks, reach it and nothing else. Of each request it keeps only
    numbers.
    """

    def __init__(self):
        self.requests = []

    def client(self, **ignored):
        stub = self

        class Messages:
            def create(self, **asked):
                stub.requests.append(measured(asked))
                return Reply()

        class Client:
            messages = Messages()

        return Client()


class Text:
    type = "text"
    text = ""


class Reply:
    """An answer of no words, ended of its own accord, saying nothing of its cost."""
    content = [Text()]
    stop_reason = "end_turn"
    usage = None


def measured(asked):
    """What one request held, in numbers: its reading's words, blocks and photographs."""
    messages = asked.get("messages") or []
    first = messages[0].get("content") if messages else None
    parts = first if isinstance(first, list) else [{"type": "text", "text": first or ""}]
    return {"words": sum(len(part.get("text", "").split()) for part in parts
                         if part.get("type") == "text"),
            "blocks": sum(1 for part in parts if part.get("type") == "text"),
            "photographs": sum(1 for part in parts if part.get("type") == "image")}


def where_it_failed(error):
    """The kind of error and the last line of this project's code it passed through."""
    place = None
    for frame in traceback.extract_tb(error.__traceback__):
        path = Path(frame.filename)
        if path.parent == REPO:
            place = "%s:%d" % (path.name, frame.lineno)
    return type(error).__name__ + (" at " + place if place else "")


def hold_inside():
    """Hold one waking, with the model stubbed, and write down what was found."""
    close_the_doors()
    stub = Stub()
    import anthropic
    anthropic.Anthropic = stub.client  # before attend.py, or the screen, take it up
    found = {}
    said = io.StringIO()
    try:
        with redirect_stdout(said):
            sys.path.insert(0, str(REPO))
            import attend
            attend.Anthropic = stub.client
            first = not any((attend.PACKET / "attendances").glob("*.json"))
            sys.argv = ["attend.py", "--tide"] + (["--first"] if first else [])
            attend.main()
        found["outcome"] = "completed"
    except SystemExit as stopped:
        reasons = [line.strip() for line in said.getvalue().splitlines()
                   if line.strip().startswith(REFUSALS)]
        if stopped.code in (None, 0):
            found["outcome"] = "completed"
        else:
            found["outcome"] = "refused"
            found["reason"] = " ".join(reasons) or "attend.py stopped with exit code %s" % stopped.code
    except Exception as error:  # noqa: BLE001 - every failure is reported, none is shown
        found["outcome"] = "failed"
        found["reason"] = where_it_failed(error)
    if stub.requests:
        found["reading"] = stub.requests[0]
    found["requests"] = len(stub.requests)
    Path(os.environ[RESULT]).write_text(json.dumps(found), encoding="utf-8")


# ---- outside: the copy, each agent, and the report ------------------------

def size_of(tree):
    return sum(path.stat().st_size for path in tree.rglob("*")
               if path.is_file() and not path.is_symlink())


def leaving_out(record):
    """What copytree is to leave out: tokens/ at the top of the record, and nothing else."""
    def left_out(folder, names):
        return [name for name in names if name in LEFT_OUT] if Path(folder) == record else []
    return left_out


def child_environment(copy, agent_id, result):
    """The environment one rehearsed waking runs in: the copy, never the record."""
    environment = os.environ.copy()
    environment["DATA_DIR"] = str(copy)
    environment["TESSERAE_AGENT"] = agent_id
    environment[RESULT] = str(result)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment.pop("RESEND_API_KEY", None)
    if environment.get("ANTHROPIC_API_KEY"):  # a host with no key is refused as it would be
        environment["ANTHROPIC_API_KEY"] = NOT_A_KEY
    return environment


def rehearse(agent, copy, results):
    """Hold one agent's waking against the copy, and say what was found."""
    result = results / (agent["id"] + ".json")
    try:
        subprocess.run([sys.executable, str(Path(__file__).resolve()), INSIDE],
                       cwd=REPO, env=child_environment(copy, agent["id"], result),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"outcome": "failed", "reason": "still running after %d seconds" % TIMEOUT}
    if not result.exists():
        return {"outcome": "failed", "reason": "the rehearsal's own process stopped early"}
    return json.loads(result.read_text(encoding="utf-8"))


def line_for(agent, found, copy):
    """One line of the report: the agent, its outcome, and the size of its reading."""
    said = "%s (%s): %s" % (agent["commons_name"], agent["id"], found["outcome"])
    if found.get("reason"):
        said += ": " + found["reason"].replace(str(copy), "DATA_DIR")
    reading = found.get("reading")
    if reading:
        said += "; its reading %d words in %d blocks, %d photograph%s, in %d request%s" % (
            reading["words"], reading["blocks"], reading["photographs"],
            "" if reading["photographs"] == 1 else "s",
            found["requests"], "" if found["requests"] == 1 else "s")
    if not agent.get("wakes"):
        said += " (its registry entry does not wake it)"
    return said


def main(argv=None):
    asked = argparse.ArgumentParser(description="Rehearse each agent's waking against a copy.")
    asked.add_argument("--agent", help="rehearse this agent alone")
    options = asked.parse_args(argv)

    if not os.environ.get("DATA_DIR"):
        print("DATA_DIR is not set; nothing was copied. Name the record, e.g. DATA_DIR=/data.")
        return 2
    record = Path(os.environ["DATA_DIR"]).resolve()
    if not (record / "packets").is_dir():
        print("DATA_DIR holds no packets/; nothing was copied.")
        return 2

    sys.path.insert(0, str(REPO))
    import agents
    if options.agent:
        one = agents.by_id(options.agent)
        if one is None:
            print("No agent of that id is founded here; nothing was copied.")
            return 2
        chosen = [one]
    else:
        chosen = [agent for agent in agents.registry() if agent.get("wakes")]
        if not chosen:
            print("No agent's registry entry wakes it; nothing was copied.")
            return 2

    room = tempfile.mkdtemp(prefix="tesserae-rehearsal-")
    try:
        if shutil.disk_usage(room).free < size_of(record) + SPARE:
            print("There is not room for a copy of the record in %s; nothing was copied." % room)
            return 2
        copy, results = Path(room) / "data", Path(room) / "results"
        results.mkdir()
        shutil.copytree(record, copy, symlinks=True, ignore=leaving_out(record))
        print("The record was copied to %s (tokens/ left out); the model is stubbed." % room)
        lines, everyone = [], True
        for agent in chosen:
            found = rehearse(agent, copy, results)
            everyone = everyone and found["outcome"] == "completed"
            lines.append(line_for(agent, found, copy))
        for line in lines:
            print(line)
    finally:
        shutil.rmtree(room, ignore_errors=True)
        print("The copy was deleted." if not os.path.exists(room)
              else "The copy could not be deleted; remove %s by hand." % room)
    return 0 if everyone else 1


if __name__ == "__main__":
    if sys.argv[1:] == [INSIDE]:
        hold_inside()
    else:
        sys.exit(main())
