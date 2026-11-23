#!/usr/bin/env python3
"""The acts done by hand on the host, found by what they changed, and put on the ledger.

powers-logged (the founder's request of 19 November 2026). Some of the keeper's
acts are done by hand on the host, where no code of the site is asked to do
them, and so none can write a line as it happens: the list of private words
edited, the charter or its page of changes edited, the site's code deployed
anew, an agent's entry in the registry changed, an agent's key replaced. Each
leaves its mark on a file. This keeps a fingerprint of each such file (a
SHA-256, never the words), and when one is found changed, one line goes on the
ledger, in fixed words (ledger.py), with the day it was found:

    the list of private words was changed
    the charter was changed
    the page of changes to the charter was changed
    the site's code was changed (the public code says how)
    <agent> · its entry in the registry was changed
    an agent's entry was taken out of the registry
    <agent> · its key was replaced

Nothing of what changed is said: not a word of the list, not a switch, not a
key. The day is the day it was found, which is at most a day after it was done:
the hearth looks once as it starts and once a day before the nightly backup
(hearth.backing_up), and the keeper may look at any time:

    DATA_DIR=/data python ledger_watch.py

The fingerprints are kept in DATA_DIR/ledger-watch.json, which no page serves
and no backup holds. Where there are none yet (the first look, or a disk
restored from a backup), the fingerprints are only taken, and no line is
written: nothing can be said to have changed from a state never seen. An agent
newly in the registry, or a key newly cut, is no change (its founding is on the
ledger already).

What this cannot see: a file changed and changed back between two looks, and
anything done on the host that leaves no mark on these files. The keeper's
powers page says so.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

import agents
import ledger

REPO = Path(__file__).resolve().parent
NONE = "none"  # the fingerprint of a file that is not there


def data():
    return Path(os.environ.get("DATA_DIR", REPO))


def watch_file():
    return data() / "ledger-watch.json"


def of_bytes(raw):
    """A fingerprint of a file's bytes, its line endings made one kind."""
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def of_file(path):
    return of_bytes(path.read_bytes()) if path.is_file() else NONE


def of_code():
    """One fingerprint of the site's code as deployed: every .py beside this file and every
    template, in order of their names."""
    whole = hashlib.sha256()
    for path in sorted([*REPO.glob("*.py"), *(REPO / "templates").glob("*.html")]):
        whole.update(path.name.encode("utf-8") + b"\0" + of_bytes(path.read_bytes()).encode())
    return whole.hexdigest()


def fingerprints():
    """Every file watched, by what it is, as {key: fingerprint}."""
    found = {"private-words": of_file(data() / "private-words.txt"),
             "charter": of_file(REPO / "docs" / "charter.md"),
             "charter-changes": of_file(REPO / "charter-changes.json"),
             "code": of_code()}
    for agent in agents.registry():
        found["entry:" + agent["id"]] = of_bytes(
            json.dumps(agent, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        found["key:" + agent["id"]] = of_file(data() / "keys" / agent["id"] / "public.key")
    return found


def name_of(agent_id):
    agent = agents.by_id(agent_id)
    return agent["commons_name"] if agent else None


def lines_for(before, now):
    """The ledger's words for each change between two sets of fingerprints, in a fixed order."""
    said = []
    fixed = [("private-words", ledger.PRIVATE_WORDS_CHANGED),
             ("charter", ledger.CHARTER_CHANGED),
             ("charter-changes", ledger.CHARTER_CHANGES_CHANGED),
             ("code", ledger.CODE_CHANGED)]
    for key, words in fixed:
        if key in before and before[key] != now.get(key):
            said.append(words)
    for key in sorted(before):
        kind, _, agent_id = key.partition(":")
        if kind == "entry":
            if key not in now:
                said.append(ledger.ENTRY_TAKEN_OUT)
            elif before[key] != now[key]:
                said.append(name_of(agent_id) + ledger.DOT + ledger.ENTRY_CHANGED)
        elif kind == "key" and key in now and before[key] not in (NONE, now[key]):
            said.append(name_of(agent_id) + ledger.DOT + ledger.AGENT_KEY_REPLACED)
    return said


def check(day=None):
    """Look once: write a ledger line for each change found, keep the fingerprints as they are
    now, and give back the words written. The first look writes nothing."""
    now = fingerprints()
    kept = watch_file()
    try:
        before = json.loads(kept.read_text(encoding="utf-8")) if kept.is_file() else None
    except (OSError, ValueError):
        before = None  # unreadable is taken as never seen, and nothing is said of it
    said = lines_for(before, now) if isinstance(before, dict) else []
    for words in said:
        ledger.write(words, day=day, path=data() / "commons" / "ledger.md")
    beside = kept.with_name(kept.name + ".tmp")
    beside.parent.mkdir(parents=True, exist_ok=True)
    beside.write_text(json.dumps(now, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(beside, kept)
    return said


def main():
    if "DATA_DIR" not in os.environ:
        print("Say DATA_DIR: the ledger is written where it is kept, and nowhere else.")
        return 1
    said = check()
    for words in said:
        print("on the ledger:", words)
    if not said:
        print("nothing watched has changed since the last look")
    return 0


if __name__ == "__main__":
    sys.exit(main())
