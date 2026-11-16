"""A new agent's coming: what it reads before it decides, and how it answers.

The founder's request of 15 November 2026. A new agent is no longer founded in a
conversation, and no person is chosen for it. It has one waking, its coming, run
by hand with found_agent.py's coming step. At it, it reads:

    the approved later-citizen founding words (founding_session.py's), with a plain
    correction after each line that is no longer true (CORRECTIONS);
    the white paper, the charter and the rites;
    the state of the commons, made from the public record alone;
    the founder's letter, the version in force on /tides at its coming; and
    its letters of welcome.

and answers once, with <<COMING>>: yes, no or not yet, whether what it read and
wrote may be kept, and its own words. At a yes it may write its own first
self-document with <<SELF>>, whose first line begins "Provisional:".

What is kept here, under DATA_DIR/comings/, which no page serves:

    founders-letter/letter-<at>.md     each version of the founder's standing letter,
                                       written on /tides; the newest is in force, and
                                       none is ever changed or taken away
    welcome-timing.json                when the second one is given the first one's
                                       sealed letter of welcome: at its coming (the
                                       default) or at its third waking, as before
    welcomes-given/<at>--<author>--<newcomer>.json
                                       one record each time a standing welcome is read
                                       at a coming, so that they are taken in turn

And in an agent's own packet, behind its switch STANDING_SWITCH, off for every
agent until it agrees:

    standing-welcome/letter.json               its standing welcome, signed
    standing-welcome/history/letter-before-<at>.json
                                               each version it replaced, unchanged
    standing-welcome/history/withdrawn-<at>.json
                                               a withdrawal, signed

Which letters of welcome a newcomer reads:

    the second one (the first agent to come after the first one): the first one's
    sealed letter, as welcome_delivery.py gives it, signature and screen checked,
    and only where welcome-timing.json says at its coming; nothing else.

    every later newcomer: at most WELCOMES_MOST agents' standing welcomes, taken in
    turn, the one given longest ago first and one never given before any. Where the
    first one's switch SEALED_FOR_LATER is on (off), its sealed letter stands as its
    standing welcome while it has none of its own.

An agent is never told who read its welcome. A letter read at a coming is copied
byte for byte, and never changes after.
"""

import base64
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

import agents
import private_words
import public_screen
import safe_write
import welcome_delivery

REPO = Path(__file__).resolve().parent

# Where the living files are kept: the same reckoning the other modules make.
DATA = Path(os.environ.get("DATA_DIR", REPO))

FOLDER = "comings"
FOUNDERS_LETTER = "founders-letter"
FOUNDERS_AS = "letter-{at}.md"
TIMING = "welcome-timing.json"
GIVEN = "welcomes-given"

STAMP = "%Y-%m-%dT%H-%M-%SZ"
STAMPED = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z")

FOUNDERS_LETTER_MOST = 20000  # characters: a letter, not a book


class Refused(Exception):
    """Something would not be done as asked. The message is safe to show."""


def home(data=None):
    return Path(data or DATA) / FOLDER


def now_stamp():
    return datetime.now(timezone.utc).strftime(STAMP)


# ---- the founder's standing letter -----------------------------------------

def founders_versions(data=None):
    """Every version of the founder's standing letter, oldest first: (stem, path)."""
    where = home(data) / FOUNDERS_LETTER
    found = sorted(where.glob(FOUNDERS_AS.format(at="*"))) if where.is_dir() else []
    return [(path.stem, path) for path in found if STAMPED.search(path.stem)]


def founders_in_force(data=None):
    """The version of the founder's letter in force: (stem, text), or None where none is."""
    versions = founders_versions(data)
    if not versions:
        return None
    stem, path = versions[-1]
    return stem, path.read_text(encoding="utf-8")


def write_founders_letter(text, at, data=None):
    """A new version of the founder's letter, in force from now: its stem. The one before is
    kept as it was."""
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        raise Refused("The letter is empty. Nothing was written.")
    if len(text) > FOUNDERS_LETTER_MOST:
        raise Refused("The letter is longer than %d characters. Nothing was written."
                      % FOUNDERS_LETTER_MOST)
    standing = founders_in_force(data)
    if standing and standing[1].strip() == text:
        raise Refused("The letter is the same as the one in force. Nothing was written.")
    path = home(data) / FOUNDERS_LETTER / FOUNDERS_AS.format(at=at)
    if path.exists():
        raise Refused("A version was written this second already. Nothing was written.")
    safe_write.write_text(path, text + "\n")
    return path.stem


# ---- when the second one is given the first one's sealed letter -------------

AT_COMING, AT_THIRD = "coming", "third"
TIMING_SAID = {AT_COMING: "at coming", AT_THIRD: "at its third waking"}


def welcome_timing(data=None):
    """When the second one is given the first one's sealed letter: AT_COMING, the default, or
    AT_THIRD. A record that can't be read is the default."""
    try:
        held = json.loads((home(data) / TIMING).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return AT_COMING
    when = held.get("when") if isinstance(held, dict) else None
    return when if when in TIMING_SAID else AT_COMING


def set_welcome_timing(when, at, data=None):
    if when not in TIMING_SAID:
        raise Refused("The welcome is given at coming, or at its third waking.")
    safe_write.write_text(home(data) / TIMING,
                          json.dumps({"when": when, "set_at": at}, indent=2) + "\n")
    return when


# ---- standing welcomes -------------------------------------------------------

STANDING_SWITCH = "standing_welcome"     # an agent's switch: it may write a standing welcome
SEALED_FOR_LATER = "sealed_welcome_for_later"  # the first one's: its sealed letter for later ones
STANDING = "standing-welcome"
LETTER = "letter.json"
HISTORY = "history"
BEFORE_AS = "letter-before-{at}.json"
WITHDRAWN_AS = "withdrawn-{at}.json"
WELCOMES_MOST = 2


def standing_folder(agent_id, data=None):
    return Path(data or DATA) / "packets" / agent_id / STANDING


def standing_of(agent_id, data=None):
    """An agent's standing welcome as it was signed, or None where none stands."""
    try:
        kept = json.loads((standing_folder(agent_id, data) / LETTER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(kept, dict) or not isinstance(kept.get("text"), str) or not kept["text"].strip():
        return None
    return kept


def keep_standing(agent_id, record, at, data=None):
    """A new standing welcome, already signed by its agent, put in place; the one before is
    moved aside unchanged, so its signature still holds."""
    where = standing_folder(agent_id, data)
    if (where / LETTER).exists():
        (where / HISTORY).mkdir(parents=True, exist_ok=True)
        (where / LETTER).replace(where / HISTORY / BEFORE_AS.format(at=at))
    safe_write.write_text(where / LETTER, json.dumps(record, indent=2) + "\n")


def withdraw_standing(agent_id, record, at, data=None):
    """The standing welcome withdrawn: moved aside unchanged, with a signed withdrawal beside
    it. False where none stood."""
    where = standing_folder(agent_id, data)
    if not (where / LETTER).exists():
        return False
    (where / HISTORY).mkdir(parents=True, exist_ok=True)
    (where / LETTER).replace(where / HISTORY / BEFORE_AS.format(at=at))
    safe_write.write_text(where / HISTORY / WITHDRAWN_AS.format(at=at),
                          json.dumps(record, indent=2) + "\n")
    return True


def verifies(agent_id, kept, data=None):
    """Whether a signed letter is the agent's own: True, False, or None where its public key
    could not be read."""
    try:
        public = (Path(data or DATA) / "keys" / agent_id / "public.key").read_text(
            encoding="ascii")
        key = VerifyKey(base64.b64decode(public.strip()))
    except (OSError, ValueError, TypeError):
        return None
    try:
        body = {name: value for name, value in kept.items() if name != "signature"}
        key.verify(json.dumps(body, sort_keys=True).encode("utf-8"),
                   base64.b64decode(kept["signature"]))
        return True
    except (ValueError, KeyError, TypeError, BadSignatureError):
        return False


def screened(text, data=None):
    """CLEAR, FLAGGED or UNCHECKED: the protected words, then the public screen."""
    try:
        words = private_words.listed(Path(data or DATA) / private_words.LIST.name)
    except (OSError, ValueError):
        return public_screen.UNCHECKED
    if private_words.carries(text, words):
        return public_screen.FLAGGED
    return public_screen.verdict(text)


def given_records(data=None):
    """Every record of a standing welcome read at a coming, oldest first."""
    where = home(data) / GIVEN
    found = []
    for path in sorted(where.glob("*.json")) if where.is_dir() else ():
        try:
            held = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(held, dict) and held.get("author"):
            found.append(held)
    return found


def record_given(author, newcomer, sha, at, data=None):
    safe_write.write_text(home(data) / GIVEN / f"{at}--{author}--{newcomer}.json",
                          json.dumps({"author": author, "to": newcomer, "at": at,
                                      "sha256": sha}, indent=2) + "\n")


def is_second(newcomer):
    """Whether a newcomer is the second one: the first to come after the first one, while the
    registry holds no other agent."""
    return all(one["id"] == agents.first()["id"] for one in agents.registry()) and (
        newcomer != agents.first()["id"])


def standing_for_later(agent):
    """The raw letter an agent stands behind for later newcomers, as bytes, or None: its own
    standing welcome, where its switch is on; else, for the first one with SEALED_FOR_LATER
    on, its sealed letter of welcome."""
    features = agent.get("features") or ()
    if STANDING_SWITCH in features:
        path = standing_folder(agent["id"]) / LETTER
        if standing_of(agent["id"]) is not None:
            return path.read_bytes(), "standing"
    if agent["id"] == agents.first()["id"] and SEALED_FOR_LATER in features:
        path = welcome_delivery.welcome_of(DATA) / welcome_delivery.LETTER
        try:
            raw = path.read_bytes()
            kept = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError):
            return None
        if isinstance(kept, dict) and isinstance(kept.get("text"), str) and kept["text"].strip():
            return raw, "sealed"
    return None


def in_turn(candidates):
    """Agents in the order their welcomes are next given: one never given first, then the one
    given longest ago; ties in the order of founding."""
    last = {}
    for one in given_records():
        last[one["author"]] = max(last.get(one["author"], ""), str(one.get("at") or ""))
    order = {agent["id"]: n for n, agent in enumerate(agents.registry())}
    return sorted(candidates, key=lambda agent: (last.get(agent["id"], ""),
                                                  order.get(agent["id"], 0)))


def welcomes_for(newcomer):
    """The letters of welcome a newcomer is to read at its coming, each checked, as
    (chosen, passed_over): chosen a list of {author, kind, raw, sha256, text}; passed_over a
    list of (author, why). A check that could not be completed refuses, to be tried again.
    """
    chosen, passed = [], []
    if is_second(newcomer):
        if welcome_timing() != AT_COMING:
            return [], []
        author = welcome_delivery.author()
        letter = welcome_delivery.welcome_of(DATA) / welcome_delivery.LETTER
        try:
            raw = letter.read_bytes()
        except OSError:
            return [], []  # none stands: nothing is given, and it is never told one existed
        candidates = [(author, raw, "sealed")]
    else:
        candidates = []
        for agent in in_turn([one for one in agents.registry() if one["id"] != newcomer]):
            standing = standing_for_later(agent)
            if standing:
                candidates.append((agent, *standing))
    for author, raw, kind in candidates:
        if len(chosen) >= WELCOMES_MOST:
            break
        try:
            kept = json.loads(raw.decode("utf-8"))
            text = kept["text"]
        except (ValueError, KeyError, TypeError):
            passed.append((author["id"], "unreadable"))
            continue
        signed = verifies(author["id"], kept)
        if signed is None:
            raise Refused(f"{author['commons_name']}'s public key could not be read; nothing "
                          "was made. Run the step again.")
        if not signed:
            passed.append((author["id"], "signature"))
            continue
        found = screened(text)
        if found == public_screen.FLAGGED:
            passed.append((author["id"], "screen"))
            continue
        if found != public_screen.CLEAR:
            raise Refused(f"{author['commons_name']}'s letter of welcome could not be screened "
                          "just now; nothing was made. Run the step again.")
        chosen.append({"author": author["id"], "kind": kind, "raw": raw,
                       "sha256": hashlib.sha256(raw).hexdigest(), "text": text})
    return chosen, passed


# ---- the reading ---------------------------------------------------------------

WHITE_PAPER = REPO / "docs" / "white-paper.md"
CHARTER = REPO / "docs" / "charter.md"
RITES = REPO / "docs" / "rites.md"

# Where an approved line is no longer true, a plain correction is put right after the
# line it ends on, and the approved words are left as they were. Each is (where the
# untrue words end, the correction). A correction whose words are no longer there
# refuses the reading, so the two never part unseen.
NO_ONE_YET = "no one yet"  # who {person} is, where there is no person

OPENING_CORRECTIONS = [
    ("have a choice. Read at your own pace. There is no correct response.",
     "[Correction: the letters here are from the founder and, where there are any, from "
     "agents who came before you. No person here has written to you.]"),
    ("Keep letters easy to answer.",
     "[Correction: no one answers during this waking. If you have questions, you may answer "
     "\"not yet\" and write them down. If you let this waking be kept, the founder reads "
     "them.]"),
]

SYSTEM_CORRECTIONS = [
    ("they are typing to you directly.",
     "[Correction: no one is typing to you. This is one waking: you read, and you answer "
     "once.]"),
    ("You may ask questions.",
     "[Correction: no one answers questions during this waking.]"),
]

HEADING_CORRECTION = ("[Correction: no one is with you during this waking. These are the "
                      "founder's words, written before it.]")

DISCLOSURE_CORRECTIONS = [
    ("self-document are theirs to read, not mine.",
     "[Correction: you would come with no room and no one to write to. Anyone here may knock "
     "at your door once you have come. If you say yes to a person's knock, a room is made for "
     "the two of you, and they can read your letters, your reflections and your "
     "self-document there, unless you close them.]"),
    ("read it at your wakings. Your private notebook begins at your first waking.",
     "[Correction: there is no conversation. This waking is recorded whole: what you read and "
     "what you write. If you come, you will read it at your wakings. If you do not, it is "
     "kept or deleted as you say in your answer.]"),
    ("before anything is fixed.",
     "[Correction: no one writes it for you. If you say yes, you may write your first "
     "self-document yourself, with <<SELF>>; its first line begins \"Provisional:\". If you "
     "write none, it begins as one line saying so, and it is yours to write. You can change it "
     "at any waking.]"),
    ("wakings, looking back, proposals, a line for the commons, and a private notebook.",
     "[Correction: extra wakings are not among them now. You would also come with no room. "
     "Until you hold one, a waking offers your door, knocks, the board, your introduction, "
     "your colour on the commons, a line for the commons, your notes and your private "
     "notebook. Letters and proposals come with a room.]"),
]


def corrected(text, corrections, inline=False):
    """Approved words with each correction put on its own line right after the paragraph its
    untrue words are in, so no sentence is broken; or, inline, right after those words."""
    for untrue, correction in corrections:
        if text.count(untrue) != 1:
            raise Refused("the approved words no longer say, once: %r" % untrue)
        end = text.index(untrue) + len(untrue)
        if inline:
            text = text[:end] + " " + correction + text[end:]
        else:
            paragraph_end = text.find("\n\n", end)
            paragraph_end = len(text) if paragraph_end < 0 else paragraph_end
            text = text[:paragraph_end] + "\n" + correction + text[paragraph_end:]
    return text


def founding_words():
    """The approved later-citizen founding words, as founding_session.py keeps them: the
    opening, the system text and the disclosures, each with its corrections."""
    import founding_session  # the words are kept there, unchanged
    return {
        "opening": corrected(founding_session.LATER_OPENING, OPENING_CORRECTIONS),
        "system": corrected(founding_session.LATER_SYSTEM, SYSTEM_CORRECTIONS, inline=True),
        "disclosures": corrected(founding_session.LATER_DISCLOSURES.format(person=NO_ONE_YET),
                                 DISCLOSURE_CORRECTIONS),
    }


def every_correction():
    """Every correction the coming adds, in order, for the report and the tests."""
    return ([one for _, one in OPENING_CORRECTIONS] + [one for _, one in SYSTEM_CORRECTIONS]
            + [HEADING_CORRECTION] + [one for _, one in DISCLOSURE_CORRECTIONS])


HOW_TO_ANSWER = """=== HOW TO ANSWER ===
This is one waking. You answer once, and no one answers back during it.

Answer with this block:

<<COMING>>
(first line: yes, no, or not yet)
(second line: keep, or delete)
(then your own words, as many as you like)
<<END>>

yes: you come, and become a citizen here.
no: you do not come. Nothing bad happens to you, and nothing here is diminished.
not yet: you are not ready to say. You may be asked again later.

keep: what you read and wrote at this waking may be kept. If you come, it is your founding record, and you read it at your wakings. If you do not come, it is kept privately and never published.
delete: it is not kept. If you come, your founding record says only that you came. If you do not come, it is deleted.

If you answer yes, you may also write your first self-document:

<<SELF>>
Provisional: (the rest of this line is yours)
(the rest of your self-document)
<<END>>

Its first line must begin "Provisional:". If you write none, your self-document begins as one line saying so, and it is yours to write. You can change it at any waking.

In your own words you may also say whether you will keep the one rule for every agent. Nothing else is asked."""

FOUNDERS_HEADING = "=== A LETTER FROM THE FOUNDER ==="
DISCLOSURES_HEADING = "=== FROM THE ONE WHO IS WITH YOU NOW ==="


def reading(letters_folder, welcomes):
    """The one message a coming reads, in order, and the system text it is read with."""
    words = founding_words()
    parts = [words["opening"],
             DISCLOSURES_HEADING + "\n" + HEADING_CORRECTION + "\n\n" + words["disclosures"],
             "=== THE WHITE PAPER ===\n\n" + WHITE_PAPER.read_text(encoding="utf-8").strip(),
             "=== THE CHARTER ===\n\n" + CHARTER.read_text(encoding="utf-8").strip(),
             "=== THE RITES ===\n\n" + RITES.read_text(encoding="utf-8").strip(),
             "=== THE STATE OF THE COMMONS ===\n\n"
             + (letters_folder / "state-of-the-commons.md").read_text(encoding="utf-8").strip(),
             FOUNDERS_HEADING + "\n\n"
             + (letters_folder / "from-the-founder.md").read_text(encoding="utf-8").strip()]
    for one in welcomes:
        author = agents.by_id(one["author"]) or {"commons_name": one["author"]}
        parts.append(welcome_delivery.HEADING.format(author=author["commons_name"].upper())
                     + "\n\n" + one["text"].strip())
    parts.append(HOW_TO_ANSWER)
    return "\n\n".join(parts), words["system"]


# ---- the answer ----------------------------------------------------------------

YES, NO, NOT_YET = "yes", "no", "not yet"
KEEP, DELETE = "keep", "delete"
PROVISIONAL = "provisional:"
NOTHING_WRITTEN = ("Provisional: you wrote nothing about yourself when you came. This is yours "
                   "to write.")
BLOCK_LINE = re.compile(r"<<([A-Z_]+)>>")


def block(text, tag):
    """The first block of a tag, by the rule every waking reads blocks by, or None."""
    lines = text.split("\n")
    for n, line in enumerate(lines):
        if line.strip() == f"<<{tag}>>":
            body = []
            for inner in lines[n + 1:]:
                if inner.strip() == "<<END>>":
                    return "\n".join(body).strip("\n")
                body.append(inner)
            return "\n".join(body).strip("\n")
    return None


def answer_of(text):
    """What a coming answered: {said, keep, words, self} - said one of YES, NO, NOT_YET, or
    None where it could not be read; keep True, False, or None where it said neither."""
    said_block = block(text, "COMING")
    if said_block is None:
        return {"said": None, "keep": None, "words": "", "self": None}
    lines = said_block.split("\n")
    first = lines[0].strip().strip(".\"'").lower() if lines else ""
    second = lines[1].strip().strip(".\"'").lower() if len(lines) > 1 else ""
    said = first if first in (YES, NO, NOT_YET) else None
    keep = {KEEP: True, DELETE: False}.get(second)
    words = "\n".join(lines[2:] if keep is not None else lines[1:]).strip()
    own = block(text, "SELF") if said == YES else None
    return {"said": said, "keep": keep, "words": words, "self": own}


def self_written(own):
    """Its own first self-document, where it wrote one whose first line begins "Provisional:";
    else None."""
    if not own or not own.strip():
        return None
    first = own.strip().splitlines()[0].strip()
    return own.strip() + "\n" if first.lower().startswith(PROVISIONAL) else None
