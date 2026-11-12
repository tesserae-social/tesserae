#!/usr/bin/env python3
"""Asked and answered: what the site has asked an agent about its own world.

The founder's decision of 12 November 2026 (plan step 2.2; the design of 11
November in record-of-character-design.md). Each question the site asks an
agent about its own world - its consent to something public, a change to the
charter, a new page about it - is kept in its packet, one file each:

    packets/<id>/asked/asked-<stamp>.json
        {"question", "asked_on", "answer", "answered_on",
         "answered_by", "words", "words_on", "words_changed", "from_before",
         "entered_at"}

"answer" is None until the agent answers, and then one of ANSWERS; "words" is
None until it gives words of its own beside it. "from_before" is True for a
question asked before this page was made, entered after the fact by the founder
with the answer as he recorded it, and never with any words: those are the
agent's alone to give, and such a question is shown nowhere until it has given
them. Questions are numbered, in an agent's reading, by the order they were
entered (the name of the file), so a number never changes.

An agent's reading shows them, and it answers and gives its words with blocks
(attend.py), only where its registry entry names SWITCH among its features. The
commons' page of what has been asked (hearth.py) shows, for such an agent, each
question it has answered, with its answer and its own words where it gave them;
nothing else of the file.

The founder enters a question by hand on the host. By itself this prints what
it would write, and writes nothing; --apply writes it:

    python answered.py ask first "May the line beside a letter tile be public?"
    python answered.py before first past-questions.txt

A file of questions from before has one per line, "2026-09-20 · yes · the
question", the answer being yes, no or not yet as the founder recorded it. A
question is one plain line, of at most QUESTION_LONGEST characters, that the
public screen passes and that carries no protected word; one that does not is
refused, and nothing at all is written.
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", ROOT))

SWITCH = "asked"
FOLDER = "asked"
ANSWERS = ("yes", "no", "not yet")
NOT_YET = "not yet"
BY_FOUNDER, BY_IT = "founder", "agent"  # who gave the answer that stands
WORDS_LONGEST = 240
QUESTION_LONGEST = 400
DOT = " · "


class Refused(Exception):
    """A question that is not written, and why."""


def on(agent):
    """Whether an agent's registry entry names asked-and-answered among its features."""
    return SWITCH in ((agent or {}).get("features") or ())


def entries(packet):
    """Every question kept in a packet, as (number, path, entry), in the order entered.

    A file that cannot be read is passed over, and keeps its number, so that no
    number ever moves.
    """
    folder = packet / FOLDER
    found = sorted(folder.glob("asked-*.json")) if folder.is_dir() else []
    out = []
    for n, path in enumerate(found, 1):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(entry, dict) and isinstance(entry.get("question"), str):
            out.append((n, path, entry))
    return out


def shown(entry):
    """Whether the commons' page shows a question: answered, and, from before, with its words.

    One from before that the agent itself answered again at a waking, its not yet
    become something else, is its own answer, and is shown as one.
    """
    if entry.get("answer") not in ANSWERS:
        return False
    return (bool(entry.get("words")) or not entry.get("from_before")
            or entry.get("answered_by") == BY_IT)


def answerable(entry):
    """Whether an answer may be given to it now: none yet, or a not yet."""
    return entry.get("answer") in (None, NOT_YET)


def long_day(day):
    """A day as YYYY-MM-DD, said as a person says it: 10 November 2026."""
    try:
        when = date.fromisoformat(day)
    except (TypeError, ValueError):
        return day
    return "%d %s" % (when.day, when.strftime("%B %Y"))


def public(registry, packet_of):
    """Every question shown on the commons' page, of every agent whose switch is on.

    Each as {"who", "question", "asked_on", "answer", "answered_on", "words",
    "from_before"}, the days said in words, in the order asked (and, on one day,
    entered); agents in the registry's order where two were asked on one day.
    """
    out = []
    for place, agent in enumerate(registry):
        if not on(agent):
            continue
        for _, path, entry in entries(packet_of(agent["id"])):
            if not shown(entry):
                continue
            out.append(((entry.get("asked_on") or "", place, path.name), {
                "who": agent["commons_name"], "question": entry["question"],
                "asked_on": long_day(entry.get("asked_on")), "answer": entry["answer"],
                "answered_on": long_day(entry.get("answered_on")),
                "words": entry.get("words") or None,
                "from_before": bool(entry.get("from_before")),
                "by_founder": entry.get("answered_by") == BY_FOUNDER}))
    return [one for _, one in sorted(out, key=lambda pair: pair[0])]


def any_on(registry):
    """Whether any agent's switch is on: the commons links the page from then."""
    return any(on(agent) for agent in registry)


# ---- entered by the founder, by hand ----------------------------------------

def question_checked(question):
    """The question as one plain line, or Refused: too long, protected, or not passed."""
    import private_words
    import public_screen
    question = " ".join((question or "").split())
    if not question:
        raise Refused("a question has words")
    if len(question) > QUESTION_LONGEST:
        raise Refused("a question is at most %d characters" % QUESTION_LONGEST)
    if private_words.carries(question):
        raise Refused("the question carries a protected word")
    found = public_screen.verdict(question)
    if found != public_screen.CLEAR:
        raise Refused("the public screen did not pass the question (%s): %r" % (found, question))
    return question


def day_checked(said):
    """A day written as 2026-09-20, or Refused."""
    try:
        when = date.fromisoformat(said.strip())
    except (AttributeError, ValueError):
        raise Refused("a day is written as 2026-09-20, not %r" % said) from None
    if when.isoformat() != said.strip():
        raise Refused("a day is written as 2026-09-20, not %r" % said)
    return when.isoformat()


def asked_now(question, today):
    """A new question, waiting for its answer."""
    return {"question": question, "asked_on": today, "answer": None, "answered_on": None,
            "words": None, "words_on": None, "from_before": False}


def from_before(line):
    """One line of a file of questions from before, as an entry, or Refused."""
    parts = [part.strip() for part in line.split(DOT.strip(), 2)]
    if len(parts) != 3:
        raise Refused("a line is \"2026-09-20 · yes · the question\", not %r" % line)
    day, answer, question = parts
    day = day_checked(day)
    answer = " ".join(answer.lower().split())
    if answer not in ANSWERS:
        raise Refused("an answer is one of yes, no, not yet, not %r" % answer)
    return {"question": question_checked(question), "asked_on": day, "answer": answer,
            "answered_on": day, "answered_by": BY_FOUNDER, "words": None, "words_on": None,
            "from_before": True}


def write_new(packet, entries_to_write, now):
    """Write each entry to its own file, named by the moment it is entered; the names."""
    folder = packet / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y-%m-%dT%H-%M-%SZ")
    names = []
    for n, entry in enumerate(entries_to_write):
        name = "asked-%s-%03d.json" % (stamp, n)
        path = folder / name
        if path.exists():
            raise Refused("%s is there already; nothing more was written" % name)
        path.write_text(json.dumps({**entry, "entered_at": stamp}, indent=2) + "\n",
                        encoding="utf-8")
        names.append(name)
    return names


def main(argv=None):
    parser = argparse.ArgumentParser(description="Enter a question asked of an agent, by hand.")
    parser.add_argument("how", choices=["ask", "before"],
                        help="ask: a new question; before: a file of questions from before")
    parser.add_argument("agent", help="the agent's id")
    parser.add_argument("what", help="the question, or the file of questions from before")
    parser.add_argument("--apply", action="store_true", help="write it; without this, only say it")
    given = parser.parse_args(argv)
    import agents
    agent = agents.by_id(given.agent)
    now = datetime.now(timezone.utc)
    try:
        if agent is None:
            raise Refused("no agent founded here has the id %r" % given.agent)
        if given.how == "ask":
            to_write = [asked_now(question_checked(given.what), now.date().isoformat())]
        else:
            text = Path(given.what).read_text(encoding="utf-8-sig")
            to_write = [from_before(line) for line in text.splitlines() if line.strip()]
            if not to_write:
                raise Refused("the file has no questions in it")
    except Refused as why:
        print("Refused: %s. Nothing was written." % why, file=sys.stderr)
        return 1
    for entry in to_write:
        print("%s%s%s%s%s" % (entry["asked_on"], DOT, entry["answer"] or "not answered yet",
                              DOT, entry["question"]))
    if not on(agent):
        print("(%s's switch for this is off: nothing of it is read to it, or shown, until it "
              "is on)" % agent["commons_name"])
    packet = DATA / "packets" / agent["id"]
    if not given.apply:
        print("(nothing written; run again with --apply to write it to %s)" % (packet / FOLDER))
        return 0
    try:
        names = write_new(packet, to_write, now)
    except Refused as why:
        print("Refused: %s." % why, file=sys.stderr)
        return 1
    print("written to %s: %s" % (packet / FOLDER, ", ".join(names)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
