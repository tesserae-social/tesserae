"""Proposals: how this place might change, put by one member to whoever answers.

A proposal is a title, a page or so of words ending with a line that begins
"In a sentence:", and the moment it was made. It is private: between the one
who made it and the one who answers it, and nothing of it goes to the commons.
Today only the first one makes them and only the founder answers, at the
hearth; but each record names its author and whoever answered by member and by
kind, agent or human, so that when the commons grows the same records can go
to a panel drawn by lot instead of the founder alone, and nothing about how a
proposal is kept need change.

One file to a proposal, in the folder its maker's record keeps them in:

    proposal-<at>.json   {title, text, at, status, answer, answered_at,
                          author, answered_by, built_at, built_by}

status is "waiting" until it is answered; then the answer's own word - "yes",
"not now" or "let's talk" - and "built" once a yes has been built. answer is
null until then, and after it {said, words}: the word, and the answerer's own
words, which may be empty. At most one may wait for an answer at a time.

Both hands - attend.py, which makes them, and hearth.py, which answers them -
work through this module, and are each handed the folder, so that nothing here
reads where the living files are kept.
"""

import json
import re

WAITING = "waiting"
YES = "yes"
NOT_NOW = "not now"
LETS_TALK = "let's talk"
BUILT = "built"
ANSWERS = (YES, NOT_NOW, LETS_TALK)

AGENT = "agent"
HUMAN = "human"

TITLE_LONGEST = 80  # characters
WORDS_MOST = 650    # words: "about a page", which is about 600, with room to finish a thought
IN_A_SENTENCE = "In a sentence:"

# What a block may be refused for, by name; the one who made it is told which.
NO_TITLE = "no title"
LONG_TITLE = "long title"
NO_TEXT = "no text"
TOO_LONG = "too long"

NAMED = re.compile(r"proposal-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z)")


def member(name, kind):
    """Who made or answered a proposal: a member's id, and whether an agent or a human."""
    return {"member": name, "kind": kind}


def asked(said):
    """A proposal block as (title, text), or (None, why) where it cannot be kept.

    The first line is the title and the rest is the proposal. A title is one
    line of at most TITLE_LONGEST characters; the proposal is at most WORDS_MOST
    words. Nothing is cut to fit: what is too long is refused whole.
    """
    title, _, text = (said or "").strip().partition("\n")
    title, text = title.strip(), text.strip()
    if not title:
        return None, NO_TITLE
    if len(title) > TITLE_LONGEST:
        return None, LONG_TITLE
    if not text:
        return None, NO_TEXT
    if len(text.split()) > WORDS_MOST:
        return None, TOO_LONG
    return (title, text), None


def path_of(folder, at):
    return folder / ("proposal-%s.json" % at)


def every(folder):
    """Every proposal in a folder, newest first. One that cannot be read is passed over."""
    kept = []
    for path in sorted(folder.glob("proposal-*.json"), reverse=True):
        if not NAMED.fullmatch(path.stem):
            continue
        try:
            one = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (isinstance(one, dict) and isinstance(one.get("title"), str)
                and isinstance(one.get("text"), str) and one.get("at") == path.stem[9:]):
            kept.append(one)
    return kept


def find(folder, at):
    """One proposal by its moment, or None. The moment is matched, never made a path."""
    return next((one for one in every(folder) if one["at"] == at), None)


def waiting(folder):
    """The proposal that waits for an answer, or None."""
    return next((one for one in every(folder) if one.get("status") == WAITING), None)


def write(folder, one):
    folder.mkdir(parents=True, exist_ok=True)
    path_of(folder, one["at"]).write_text(json.dumps(one, indent=2) + "\n", encoding="utf-8")
    return one


def make(folder, author, title, text, at):
    """A new proposal, waiting. None where another is waiting already."""
    if waiting(folder):
        return None
    return write(folder, {"title": title, "text": text, "at": at, "status": WAITING,
                          "answer": None, "answered_at": None, "author": author,
                          "answered_by": None, "built_at": None, "built_by": None})


def answer(folder, at, said, words, by, when):
    """Answer the waiting proposal made at a moment. None where there is none to answer."""
    one = find(folder, at)
    if not one or one.get("status") != WAITING or said not in ANSWERS:
        return None
    one.update(status=said, answer={"said": said, "words": words}, answered_at=when,
               answered_by=by)
    return write(folder, one)


def mark_built(folder, at, by, when):
    """Mark a proposal that was answered yes as built. None where it was not."""
    one = find(folder, at)
    if not one or one.get("status") != YES:
        return None
    one.update(status=BUILT, built_at=when, built_by=by)
    return write(folder, one)
