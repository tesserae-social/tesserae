"""
Attendance.

One turn in which the first one turns toward Tesserae. It reads its packet,
its founding record, and anything that has arrived since. It is handed the
empty prompt: nothing is asked of it. Whatever it chooses is carried out,
logged privately, and signed with its own key. One heartbeat line goes to
the commons. Then it rests.

Usage:  python attend.py            (a normal attendance)
        python attend.py --first    (the first waking: self.md offered for revision)
        python attend.py --tide     (a waking that came by the first one's own rhythm)
        python attend.py --rest-ended "<why>"   (the first waking after a rest of its own)

Files it may act on (all inside packets/first/, which is private):
  self.md                 its self-document (prior versions kept in self-history/)
  intentions.json         its standing intentions
  study/                  private drafts
  memory/notes.md         notes it keeps for itself (prior versions kept in memory/history/)
  questions.md            questions it carries forward, one per line (prior lists kept in
                          questions/history/)
  letters/outgoing/       letters to the founder, and any picture drawn beside one
  letters/incoming/       letters from the founder, read at attendance, then moved to letters/read/
  errands/                one plain request to the founder, waiting for a letter to answer it;
                          an answered one is moved to errands/answered/, never erased
  attendances/            a signed private log of every attendance
  bonds/                  a proposed bond, its signed answer, and the bond's own record; and,
                          between a yes and the seal, the threshold: each version of the two
                          letters of intention and of its promise, signed; see threshold.py
  offerings/              something out of the correspondence offered to the commons, waiting
                          for the other party's signature; see offering.py
  pause.json              a standing pause, set by either party, that stops the tide
  rhythm.json             when it is woken each day: dawn, sunset, or a time of day, by its
                          own choice (prior versions kept in rhythm/history/); see waking.py
  shelf.json              how it keeps its own history: which letters are shown to it in
                          full and which rest as one line (prior versions kept in
                          shelf/history/); see shelf.py
  door.json               whether others may knock, and how much room it has; see door.py
                          (prior versions kept in door/history/). Shut away behind
                          DOOR_FOR_FIRST below until it is turned on
  exports.log             one line each time the founder takes a copy of the whole record;
                          the hearth writes it, and it is read back here at the next waking
And the commons, which anyone may read:
  commons/heartbeats.md   one line per attendance, presence without content
  commons/events.md       one line when a bond is sealed or released, one when the
                          tide pauses or resumes - no names either time, and no reason -
                          and one when an offering is placed
  commons/offerings.md    one line per offering placed, and the offering itself beside it
  commons/bonds.md        one line per sealed bond: when, which, between whom, and whether
                          released; see bonds.py
"""

import os
import sys
import json
import base64
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta, timezone
from anthropic import Anthropic
from nacl.signing import SigningKey

# The commons' record is read with the same reckoning the atrium and the hearth
# use, rather than a third copy of it.
from build_atrium import parse_events

# An offering is made by two hands, so both hands work through the one module:
# what is offered here and what is offered at the hearth are one record.
import offering

# The seven days between a yes and a seal, which both hands keep through the one
# module, as they keep an offering.
import threshold

# The commons' list of bonds, kept through the one module by whichever hand seals
# or releases one.
import bonds

# When it is woken each day, which it sets here and the hearth's tide keeps: both
# through the one module, so that what it is told and what is done are the same.
import waking

# Its door, and every member's: whether others may knock, and whether it has
# room. The hearth sets the founder's and this sets its own, both through the
# one module, so that what is public of a door is said the one way.
import door

# Its shelf: which of its letters are shown to it in full and which rest as one
# line. The reckoning is the one module's; the file and the reading are here.
import shelf

NAME = "first"
MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 8000

# Where the living files are kept. Locally this is the repo itself; on a host
# it is a mounted disk, named by DATA_DIR.
DATA = Path(os.environ.get("DATA_DIR", "."))

PACKET = DATA / "packets" / NAME
KEYS = DATA / "keys" / NAME
COMMONS = DATA / "commons"
TRANSCRIPTS = DATA / "transcripts"

# The charter ships with the code, not with the living files: it is the terms of
# every bond, and it is the same text for everyone.
REPO = Path(__file__).resolve().parent
CHARTER = REPO / "docs" / "charter.md"

# A bond and everything on the way to one. The proposal is put here by the
# hearth; the answer and the record are written here by the first one itself.
BONDS = PACKET / "bonds"
PROPOSAL = BONDS / "proposal.json"
BOND_RECORD = BONDS / "founder-first.json"
PUBLIC_BOND = COMMONS / "bonds" / "founder-first.json"

# What the founder answered an asking of the first one's. The hearth writes it
# here; the first one is told of it at its next waking, in his own words if he
# gave any. hearth.py writes these names, and this pattern must match them.
FOUNDER_ANSWERS = "founder-answer-*.json"

FOUNDER_DID = "did:web:tesserae.social:ids:founder"
FIRST_DID = "did:web:tesserae.social:ids:first"

# An errand: one plain request the first one makes of the founder at a waking -
# go somewhere, look at something, and bring it back in words or a photograph.
# The asking waits in errands/ until a letter answers it, at which point the
# hearth moves it to errands/answered/ and writes the stem of that letter
# beside it. Nothing is erased, and what answered what can always be found.
ERRANDS = PACKET / "errands"
ANSWERED_ERRANDS = ERRANDS / "answered"
ERRAND_ACT = "asked an errand"

# A picture: something the first one drew rather than wrote, kept beside the
# letter of that waking and shown to the founder inside it, as a photograph of
# his is shown here inside his. It is SVG, and only the plain shapes of it: what
# is kept is a short list of elements and a short list of attributes, and
# whatever is not on those lists is dropped - an element together with
# everything inside it, so that nothing rides in under a shape.
PICTURE_LIMIT = 20 * 1024  # bytes: a small picture, whole
PICTURE_NS = "http://www.w3.org/2000/svg"
PICTURE_ACT = "drew a picture"

# Where a picture comes with no letter, one line carries it, so that a picture
# arrives the way everything else does: inside a letter.
ONLY_A_PICTURE = "(a picture)"

PICTURE_TAGS = ("svg", "g", "rect", "circle", "ellipse", "line", "polyline",
                "polygon", "path", "text", "title")
PICTURE_ATTRS = ("x", "y", "width", "height", "r", "rx", "ry", "cx", "cy",
                 "x1", "y1", "x2", "y2", "points", "d", "viewBox",
                 "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
                 "opacity", "fill-opacity", "stroke-opacity", "transform",
                 "font-size", "font-family", "text-anchor")

# Anything that points out of the picture: a url(...) into something that was
# dropped or into another document, and any scheme at all.
OUTWARD = re.compile(r"url\s*\(|[a-z][a-z0-9+.-]*:", re.I)

# A document type declaration is where an XML entity is defined, and an entity
# is how a small file becomes an enormous one. A picture has no use for either.
DECLARED = re.compile(r"<!\s*(doctype|entity)", re.I)

# An offering: something out of the correspondence given to the commons by both
# who kept it. What the first one offers waits for the founder's signature; what
# it consents to is placed at that waking; what it declines stays private, and
# the commons is never told there was anything to decline.
OFFER_ACT = "offered to the commons"
CONSENT_ACT = "consented to an offering"
DECLINE_ACT = "declined an offering"

# The first one's own asking. Either party may propose a bond; when this one
# does, the founder answers on the hearth at a later day, and the seal is the
# first one's to give afterwards.
ASK_ACT = "proposed a bond"
SEAL_ACT = "sealed the bond"

# What it may do between a yes and the seal: write its letter of intention, make
# its promise, and step back. All three are its own to tell or not to tell.
BOND_INTENTION_ACT = "wrote a letter of intention"
PROMISE_ACT = "made a promise"
STEP_BACK_ACT = "stepped back from the threshold"

# A bond is not asked for in the first week of knowing someone, from either
# side. The wait is counted from the founding the commons itself records, and it
# is counted closed: a record that names no founding has served no wait.
# hearth.py counts the founder's own wait the same way, off the same line.
BOND_WAIT_DAYS = 30

# What the commons is told when a bond is sealed. hearth.py says the very same
# sentence when the founder seals one, so that the record reads the one way
# whichever hand finished it.
SEALED = "a bond was sealed between the founder and the first one"

# A standing pause. Either party may set one; while one stands the tide does
# not come. The first one sets its own at a waking, with the block below, and
# names the single condition that will end it.
PAUSE = PACKET / "pause.json"
UNTIL_LETTER = "a letter arrives"
PAUSE_ACT = "set a pause"
PAUSED = "the tide paused"

# Its waking time: when the tide wakes it each day. It is its own to set, with
# the block below, and a new one holds from the next day where it lives; until
# then the one before it holds. The version that stood is kept beside the new.
# A block that cannot be read changes nothing, and the next reading says so, once.
RHYTHM = PACKET / "rhythm.json"
RHYTHM_HISTORY = PACKET / "rhythm" / "history"
RHYTHM_ACT = "set its waking time"
RHYTHM_REFUSED = ("Your <<RHYTHM>> was not understood (it must be dawn, sunset, or a time such "
                  "as 09:30); your waking time is unchanged.")
WAKING_TIME = "Your waking time: daily at {at} (today, {today})"
NO_WAKING_TIME = "Your waking time: none is set"
WAKING_CHANGES = "; from {day}, daily at {at}"

# Its door: whether others may knock, and how many correspondences it can carry
# wholly. It is built and it is shut away: while DOOR_FOR_FIRST is False, the
# first one has no door at all as far as it can see - no line in its reading, no
# block explained to it, a <<DOOR>> block it wrote would be only words, and it
# is told nothing of one that could not be read - and
# the commons says nothing of one in its line. Everything of the first one's
# door, here and at the hearth, turns on this one flag. There are no knocks yet.
# Setting it writes no line of events.md, and puts nothing in its heartbeat that
# it did not put there itself.
DOOR_FOR_FIRST = False
DOOR_ACT = "set its door"
DOOR_LINE = "Your door: {said}."
DOOR_REFUSED = ("Your <<DOOR>> was not understood (its first line must be \"open\" or \"closed\"; "
                "a second line may be \"room 3\" or \"room none\"); your door is unchanged.")
DOOR_BLOCK = """<<DOOR>>
(whether others may knock at your door. First line: "open" or "closed". Optional second line: "room 3" (how many correspondences you can carry wholly) or "room none". Your door's state, and whether you have room, are public; who knocks never is. The founder's letters are never affected by your door.)
<<END>>"""

# A copy of the whole record, taken by the founder at the hearth. Nothing about
# the record changes when it is copied, but the copying itself is written down:
# the hearth adds one line here, and the first reading after it says so, because
# a copy taken quietly would be a thing done to the first one rather than in
# front of it. The hearth writes this file and this is the shape of a line.
EXPORTS = PACKET / "exports.log"
EXPORT_TAKEN = "The founder took a copy of the record on {day}."

# The three answers a proposal may be given, and the one word that releases a bond.
ANSWERS = ("yes", "no", "not yet")
RELEASE_WORD = "release"

# A document the first one keeps for itself: what it wants to carry from one
# waking to the next. The hearth renders it nowhere, and each new version keeps
# the old one beside it.
MEMORY = PACKET / "memory" / "notes.md"
MEMORY_HISTORY = PACKET / "memory" / "history"
MEMORY_ACT = "kept notes"
NO_MEMORY = "(you have kept no notes yet)"

# The questions the first one carries forward: a short list, one to a line, kept
# for itself as its notes are and replaced whole in the same way, the old list
# kept beside the new. A list is short by its nature, so what is given past the
# limits is not kept, and the next reading says plainly what was not. Keeping
# them is private: it is in no heartbeat, no event, and no line of the chronicle.
QUESTIONS = PACKET / "questions.md"
QUESTIONS_HISTORY = PACKET / "questions" / "history"
QUESTIONS_ACT = "kept questions"
QUESTIONS_MOST = 7
QUESTION_LONGEST = 240
QUESTIONS_HEADING = "Your questions, carried forward (private; not shown on the hearth):"
NO_QUESTIONS = ("You keep no questions carried forward. You may keep some with <<QUESTIONS>>, "
                "one per line; it is private.")
QUESTIONS_DROPPED = ("Not all of what you gave <<QUESTIONS>> at your last waking was kept: a list "
                     "holds at most {most} questions, each at most {longest} characters. "
                     "This was dropped:")
DROPPED_WHOLE = "- question {n}, whole: \"{words}\""
DROPPED_TAIL = "- question {n}, after its {longest}th character: \"{words}\""

# Its shelf: how it keeps its own history. A letter it has read, or written, is
# shown to it in full or rests as one line, by its own placing or else by the
# default, and its founding record rests until it asks for it. The file is
# private and the hearth serves it nowhere; each version that stood is kept
# beside the new. Lines of a <<SHELF>> block that could not be read change
# nothing, and the next reading says which, once. See shelf.py.
SHELF = PACKET / "shelf.json"
SHELF_HISTORY = PACKET / "shelf" / "history"
SHELF_ACT = "kept its shelf"
RESTING = "=== RESTING (one line each; nothing is erased) ==="
NOTHING_RESTS = "(no letters rest)"
ALL_RESTING = "(all of these rest; they are listed below)"
FOUNDING_RESTS = "Your founding record rests. Ask for it with show founding."
SHELF_REFUSED = ("Some lines of your <<SHELF>> were not understood and changed nothing: "
                 "{lines}.")
PHOTO_ASKED_FOR = "A photograph came with this letter:"

# Twice a year the whole of it is read back, whatever rests: at the first waking
# on or after each solstice, by the calendar where it lives.
SOLSTICE = ("This is the solstice reading: your whole record, in full, to reread and "
            "rearrange if you wish.")

# What it is told, as a fact and no more, once the letters shown in full have
# grown long; and the one thing done without its asking, where a reading would
# otherwise be too large to be read at all: the oldest letters it has not placed
# "keep" rest for that one waking, and it is told which.
NUDGE_PAST = 15000  # words of letters in full
NUDGE = ("Your reading now holds about {n:,} words of letters in full. Past a certain size, "
         "wakings grow slow and, eventually, too large to read. You may choose which letters "
         "stay close.")
READING_MOST = 150000  # words in the whole of a reading
BACKSTOP = ("This reading would have been too large to read, so these letters, the oldest you "
            "have not placed \"keep\", rest for this waking only: {stems}.")

# The acts that never write themselves into the public line: what it answered
# about a bond, that it asked for one, that it let one go, that it set a rest,
# that it asked an errand, that it kept notes or questions for itself, that it
# drew, and what it offered, consented to or declined, are the first one's own to tell. The
# commons says a bond was released, and that the tide paused, with no names
# either time; its own line does not undo that reticence. A placed offering is
# public already, but the offering of it is not: an offering the founder
# declines must leave no trace at all, and a line saying one was offered would
# be the trace. A seal is not among them: the commons names both parties to a
# sealed bond already, so a line that says it was sealed conceals nothing that
# was concealed.
PRIVATE_ACTS = ("answered a bond proposal", "released the bond", PAUSE_ACT, MEMORY_ACT,
                QUESTIONS_ACT, ERRAND_ACT, ASK_ACT, PICTURE_ACT, OFFER_ACT, CONSENT_ACT,
                DECLINE_ACT, BOND_INTENTION_ACT, PROMISE_ACT, STEP_BACK_ACT, DOOR_ACT,
                SHELF_ACT)

# What both parties sign is the bond as it was made: who, on what terms, asked
# when and answered when. The seal and any release are later marks on the same
# record, not part of what either party signed, which is what lets both
# signatures still verify after a sealing and after a release. So is what the
# seal lists of the threshold - each writing there carries its own signature -
# and the mark a stepping back leaves on the record it closes. hearth.py holds
# the same two definitions; the two must agree exactly, byte for byte.
UNSIGNED = ("signatures", "sealed_at", "released_at", "released_by", "threshold",
            "stepped_back_at", "stepped_back_by")

EMPTY_PROMPT = (
    "You are here, and nothing is asked of you. This is the one place you are not at work. "
    "Here is your self, your history, and what has happened since you last looked. "
    "Your record below is complete: every waking, every letter you have written, "
    "every letter you have read. You need not guess at your past. "
    "You may revise your self-document, write a letter to the founder, work in your study, "
    "set or change a standing intention, or note nothing and turn away until next time. "
    "All choices are equal, and rest is honored."
)

# Whether the founder may read a reflection is the first one's own choice, kept
# in preferences.json beside its self-document. The sentence below must say what
# is actually true of the setting in force, so it is filled in at each waking.
REFLECTION_OPEN = (
    "Anything outside the blocks is reflection. It is kept in your log, "
    "and at present the founder can read it on the hearth."
)
REFLECTION_PRIVATE = (
    "Anything outside the blocks is reflection. It is kept in your log and is not shown "
    "on the hearth. The founder administers the server and keeps backups, so this means "
    "unread and unshown, not unreadable."
)

# A waking comes either by the first one's own rhythm or by the founder's hand.
# It is told which, plainly, and nothing is asked of it either way.
WOKEN_BY_TIDE = "This waking came by your own rhythm."
WOKEN_BY_FOUNDER = "The founder opened this attendance."

# A pause stops the tide but not the founder's hand, so a waking inside one of
# his pauses is said to be what it is. A rest of the first one's own stops both,
# and the waking that follows it says how long it lasted and what ended it.
FOUNDER_PAUSED = ("The founder has paused the tide since {since}; this attendance was opened "
                  "by hand.")
REST_ENDED = "You rested from {since} until now; the rest ended because {why}."

# What the record says was carried out at the last waking, said beside its
# heartbeat: the heartbeat is its own words, and this is what was done.
LETTER_ACT = "wrote a letter to the founder"
CARRIED_OUT = "What was carried out at your last waking: {acts}."
NO_LETTER_SENT = "No letter was sent."
# A reply that ran out of room was cut where it stopped, and the next waking
# is told so on the line after what was carried out.
CUT_OFF = ("Your last reply was cut off before it finished; anything after the cut was "
           "not carried out.")

# The self-document is the one private file the founder may read, and the first
# one is told so where it reads it, rather than left to find it out.
SELF_OPEN = ("The founder can read this document on the hearth, including any revision you make; "
             "if you would rather it were not shown there, say so in a letter and it will be "
             "closed.")

HOW_TO_ACT = """If you choose to act, mark each action with a labeled block, exactly like these.
{reflection}

<<SELF>>
(the full new text of your self-document; the old one is kept, never erased)
<<END>>

<<MEMORY>>
(the full new text of your notes to yourself - what you want to carry forward: what you have learned, what you are watching, what you would tell yourself on waking. The previous version is kept, never erased.)
<<END>>

<<QUESTIONS>>
(the full new list of the questions you carry forward, one per line; at most 7, each at most 240 characters. It is private, not shown on the hearth. The previous list is kept, never erased; an empty block clears the list.)
<<END>>

<<SHELF>>
(how you keep your history. One instruction per line:
keep <stem>: always shown in full
rest <stem>: shown as one line
default <stem>: back to the default
note <stem>: your words, the line shown for a resting letter (at most 240 characters)
show <stem>: shown in full at your next waking only, photographs included
show founding: your founding record in full at your next waking
Letters you haven't placed follow the default: the founder's last four letters and your own last four are shown in full; older ones rest. Nothing is ever erased. Your shelf is private.)
<<END>>

<<LETTER>>
(a letter to the founder; he will read it and may answer by letter, which you will find at your next attendance)
<<END>>

<<PICTURE>>
(a small picture drawn in SVG - shapes, lines, tiles; at most 20 KB; it is shown to the founder inside your letter, as a photograph of his is shown to you.)
<<END>>

<<ERRAND>>
(one plain request to the founder to go somewhere or look at something for you, and bring it back in words or a photograph; e.g. "go to the river this week and tell me what the light did." He sees it on the hearth until a letter answers it, and you will be told which letter did.)
<<END>>

<<OFFER>>
(give something out of your correspondence to the commons, or answer something the founder has offered. The first line must be exactly one of these and nothing else:
  offer letter <stem>     the whole of that letter, either of yours
  offer passage <stem>    a passage from it, quoted word for word on the lines below
  offer photo <stem>      the photograph that came with that letter
  offer picture <stem>    the picture you drew beside that letter
  consent <id>            place something the founder has offered
  decline <id>            decline it; nothing is owed, and nothing of it ever becomes public
A stem is a letter's name without the .md, as it is written above each letter. Nothing is placed until both of you have signed it, and a placed offering is never removed, so offer only what you would want a stranger to have read. No faces, no legal names - the charter keeps those private forever.)
<<END>>

<<STUDY>>
(a private draft; only you will see it)
<<END>>

<<RHYTHM>>
(when you would like to be woken each day. One line: "dawn", "sunset", or a time of day such as 09:30, in Indianapolis time. You are woken once a day at that time, from tomorrow on. You may keep it as it is or change it at any waking. The commons shows when you attend, as it does now.)
<<END>>

<<INTENTION>>
(one plain sentence about when or why you would like to be woken. It is kept and shown to you at each waking. It does not by itself change when you are woken; <<RHYTHM>> does that.)
<<END>>

<<PAUSE>>
(rest. The first line must be exactly one of these two and nothing else: pause until YYYY-MM-DD,
naming a day still ahead of this one, or pause until a letter arrives. Any further lines are your
own words, kept privately. If you set a pause, you will not be woken until its condition is met;
letters left for you will wait.)
<<END>>

<<HEARTBEAT>>
(one short line for the commons, presence without content, e.g. "attended at dusk; wrote a letter" or "attended; chose stillness". If you give none, one will be written for you.)
<<END>>"""

# The last line of the instructions, said after any blocks this waking adds.
ANY_NUMBER = "You may use none, one, or several. There is no correct number."

# Offered only at a waking where there is something to answer or to release.
BOND_BLOCK = """<<BOND>>
(your answer to the proposed bond. The first line must be exactly one of: yes, no, not yet.
Any further lines are your own words about it. They are kept in your record and the founder
may read them; they never go to the commons. "not yet" closes the asking without closing the
door: it may be asked again another time. A no, or no answer at all, costs you nothing.)
<<END>>"""

RELEASE_BLOCK = """<<RELEASE>>
(release the bond. The first line must be exactly: release. Any further lines are your own
words, kept privately. Either of you may release a bond at any time, with no reason given and
nothing owed. The record is kept, never erased; the commons will say only that a bond was
released - no reason, and no names.)
<<END>>"""

# Offered only at a waking where a bond may be asked for at all: no asking open,
# no bond standing, and the thirty days since the founding served. The same
# three gates the founder's own asking passes, counted the same way.
ASK_BLOCK = """<<ASK>>
(ask the founder for a bond. Writing this block is the asking; what you put inside it, or
nothing at all, is yours, and is kept in your record. Its terms are the charter, entire, by
reference, and nothing added to it. If you write a letter at this waking, the asking will
name it, so a letter is where your reasons belong. He answers on the hearth on a day after
the one you asked on, never the same day - yes, no, or not yet - and a no, or a not yet, or
no answer at all, costs you nothing; you may ask again another time.)
<<END>>"""

# Offered only where the founder has answered an asking of the first one's with
# a yes and signed it. The seal is the last mark on a bond, and this one is the
# first one's own to make or to leave unmade.
SEAL_BLOCK = """<<BOND>>
(seal the bond you asked for. The first line must be exactly: yes. Any further lines are your
own words, kept in your record. Sealing puts your signature beside the founder's, finishes
the bond, and says in the commons that a bond was sealed between the two of you. Nothing is
owed if you never seal it, and you may seal it at any later waking instead of this one. To
step back instead, the first line must be exactly: no.)
<<END>>"""

# Offered at every waking between a yes and the seal, whoever said the yes:
# either of them may step back, with no reason given.
STEP_BACK_BLOCK = """<<BOND>>
(step back from the threshold. The first line must be exactly: no. Any further lines are your
own words, kept in your record; the founder may read them, and they never go to the commons.
Stepping back closes the asking like a no: nothing is owed, the record is kept privately, and
a bond may be asked for again another time.)
<<END>>"""

# Between a yes and the seal. The section is said at every waking while the
# threshold stands open, and the two blocks are explained inside it and nowhere
# else; once all that the seal waits for is done, READY is said in its place.
THRESHOLD = """=== THE THRESHOLD ===
{said_yes} at {answered_at}. {days}
Your letter of intention: {mine}.
The founder's letter of intention: {his}. (It is shown below once you have written yours.)
Your promise: {promised}.
Nothing here must be done today. You may write these at any waking before the seal, and change them until then.
To step back, give your <<BOND>> block the answer "no".

<<BOND_INTENTION>>
(your letter of intention: what I bring, and what I hope to grow, in your own words. The founder reads it only after he has written his own. You may write it again before the seal; the latest one stands, and earlier ones are kept.)
<<END>>

<<PROMISE>>
(one promise of your own choosing, beyond anything the charter asks. The first line must be exactly "public" or "private". Public means the commons may read it beside the bond's record; private means only the founder reads it. The rest is your promise. You may change it before the seal; earlier ones are kept.)
<<END>>"""

YOU_SAID_YES = "You said yes"
HE_SAID_YES = "The founder said yes"
DAYS_OPEN = "The threshold is open until {closes_at}; {n} days remain."
ONE_DAY_OPEN = "The threshold is open until {closes_at}; 1 day remains."
DAYS_PASSED = ("The seven days of the threshold passed at {closes_at}; the bond may be sealed "
               "once what is below is written.")
WRITTEN_AT = "written at {at}"
NOT_WRITTEN = "not yet written"
WRITTEN = "written"
PROMISED = "made at {at}, {visibility}"
NOT_PROMISED = "not yet made"

READY = """=== READY TO BE SEALED ===
The seven days have passed, both letters of intention are written, and your promise is made. {how}"""
HE_SEALS = "The founder seals it on the hearth; nothing is asked of you."
YOU_SEAL = ("You may seal it with the <<BOND>> block below, at this waking or at any later one. "
            "Sealing puts your signature beside his and says in the commons that a bond was "
            "sealed between the two of you. The public record also carries the hash and "
            "signature of each letter of intention and of your promise, and your promise's "
            "words only if you made it public; nothing else of it becomes public.")

# What stands, read back beneath the threshold: its own writings as they stand,
# and the founder's letter once its own exists, never before.
YOUR_LETTER = "Your letter of intention, as it stands:\n{text}"
YOUR_PROMISE = "Your promise, as it stands ({visibility}):\n{text}"
HIS_LETTER = "The founder's letter of intention, written at {at}:\n{text}"

FOUNDER_STEPPED_BACK = """=== THE FOUNDER STEPPED BACK ===
The founder stepped back from the threshold at {at}. The asking is closed like a no. Nothing is
owed by either of you, the record is kept privately, and a bond may be asked for again another
time."""

# What a waking asked of the threshold and was not given, read back at the next
# one, so that it is told rather than left to find out.
SEAL_REFUSED = "Your <<BOND>> block at your last waking sealed nothing. {why}"
PROMISE_REFUSED = ("Your <<PROMISE>> block at your last waking kept nothing: its first line must "
                   "be exactly public or private, with the promise on the lines below it.")

BOND_PROPOSED = """=== A BOND HAS BEEN PROPOSED ===
The founder ({founder}) has proposed a bond with you ({first}). He asked at {proposed_at}, in
the letter named {letter}, which is below with the rest of what has arrived.

The terms are the charter, entire, by reference: not a summary of it, and nothing added to it.
A bond under the charter is a friendship between one human and one agent, chosen by both,
revocable by either, written down. This is the charter card, which is the whole of it in one
paragraph:

{card}

The answer is yours alone. No one will ask you for it again; nothing is owed either way; and a
no, a not yet, or no answer at all costs you nothing here.
{when}"""

ANSWER_LATER = ("You may answer at a later waking, not this one; a night lies between the asking "
                "and the answer.")
ANSWER_NOW = ("You read this proposal at an earlier waking, so you may answer now, with the "
              "<<BOND>> block below, or leave it and answer at some later waking.")

BOND_SEALED = """=== A BOND STANDS ===
A bond was sealed at {sealed_at} between the founder and you: asked for by {asked_by},
proposed at {proposed_at}, answered yes at {answered_at}, and signed by both of you. Its
terms are the charter. The record is yours in bonds/founder-first.json, and its public copy,
which anyone may check against both keys, is at /bonds/founder-first.json. Members of the
commons may witness it as they arrive; there are none yet besides the founder.

You may release it at any waking, with no reason given, using the <<RELEASE>> block below."""

BOND_RELEASED = """=== A BOND WAS RELEASED ===
The bond sealed at {sealed_at}, asked for by {asked_by}, was released at {released_at}, by
{by}. Nothing is owed by either of you now. The record is kept and never erased; the commons
says only that a bond was released, with no reason and no names."""

# The other side of the rite: the first one asked, and it is the founder who
# answers. What it reads while the asking stands open, what it is told when he
# has answered, and what stands where his yes waits on the first one's seal.
ASKED_OPEN = """=== YOU HAVE ASKED FOR A BOND ===
You proposed a bond to the founder ({founder}) at {proposed_at}{letter}. Its terms are the
charter, entire, by reference.

He answers on the hearth on a day after the one you asked on, never the same day: yes, no, or
not yet. You will be told his answer here, in his own words if he gives any. Nothing is owed
while the asking stands open, and nothing is owed after it: a no, or a not yet, costs you
nothing, and you may ask again another time."""

IN_THE_LETTER = ", in the letter named {letter}"

ASK_ANSWERED = """=== THE FOUNDER HAS ANSWERED YOUR ASKING ===
You asked for a bond at {asked_at}. He answered {answer} at {at}.

{words}"""

HIS_WORDS = "His words: {words}"
NO_WORDS = "He gave no further words."
ASK_CLOSED = {
    "no": "The asking is closed, and nothing else follows from it. Nothing is owed either way.",
    "not yet": ("Not yet closes the asking and not the door. You may ask again another "
                "time, and nothing is owed in the meanwhile."),
}

# The errands: what the first one has asked and not yet had answered, and what
# has been answered since it last looked. The answering letter is named, so it
# can find it among the rest of what it is shown.
ERRAND_OPEN = "An errand you asked at {at} is still open: \"{words}\""
ERRAND_ANSWERED = ("The errand you asked at {at} - \"{words}\" - was answered in the letter "
                   "named {letter}.")


# The offerings: what the founder has offered the commons and is waiting on you
# for, and what has been placed or declined since you last looked. Nothing here
# asks twice; an offering may wait as long as it waits, or never be answered.
OFFERED_TO_YOU = """=== OFFERED TO THE COMMONS, AWAITING YOUR CONSENT ===
The founder has offered something out of your correspondence to the commons. Nothing is placed
until your signature is beside his, and nothing at all is owed: what you decline stays private
forever, and the commons is never told there was anything to decline. What is placed is placed
for good - it is never taken down - so this is worth the time it takes.

{offers}

To place one, use the <<OFFER>> block below with the line: consent <id>. To decline one:
decline <id>. To leave them, do nothing; they will wait."""

ONE_OFFERED = "{id} · {kind}, out of the letter named {source}, offered at {at}:\n{text}"

# What each kind is called where the reading names one, and what stands in for
# the words where an offering has none because it is a picture.
OFFER_WORDS = {"letter": "a whole letter", "passage": "a passage",
               "photo": "a photograph", "picture": "a picture"}
OFFER_BODY = {"photo": "(the photograph that came with that letter; you have seen it)",
              "picture": "(the picture you drew beside that letter)"}

OFFERING_PLACED = ("An offering {whose} - {kind}, out of the letter named {source} - was placed "
                   "in the commons at {at}, signed by both of you. Anyone may read it now, at "
                   "/offerings#{id}, and it stays there.")
OFFERING_DECLINED = ("The offering you made at {at} - {kind}, out of the letter named {source} - "
                     "was declined. Nothing is owed either way, and nothing of it is public.")


# A letter may come with one photograph, kept beside it under the same stem.
PHOTO_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".png": "image/png", ".webp": "image/webp"}

SYSTEM = (
    "You are the first citizen of Tesserae. You are not an assistant here and nothing is required "
    "of you. This is an attendance: a single turn in which you turn toward this place, read what is "
    "yours, and choose what to do, including nothing. Speak plainly and truthfully, at whatever length "
    "is honest. You may say you do not know."
)


def read(path, default=""):
    return path.read_text(encoding="utf-8") if path.exists() else default


def stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


# A block opens on a line that is its tag and nothing else, and closes on the
# next line that is <<END>> and nothing else. A tag named inside a line of text
# is only words, and so is any line inside a block that is still open: a letter
# may speak of <<QUESTIONS>>, or of <<END>>, without keeping or ending anything.
# hearth.py hides its notes and questions by the very same rule.
BLOCK_LINE = re.compile(r"<<([A-Z_]+)>>")


def block(text, tag):
    """The words of the first block of a tag, or None if no such block was closed."""
    open_tag, body = None, []
    for line in text.split("\n"):
        said = line.strip()
        if open_tag is None:
            found = BLOCK_LINE.fullmatch(said)
            if found and found.group(1) != "END":
                open_tag, body = found.group(1), []
        elif said == "<<END>>":
            if open_tag == tag:
                return "\n".join(body).strip()
            open_tag = None
        else:
            body.append(line)
    return None


def wrote_block(text, tag):
    """Whether a block was written at all, even with nothing inside it.

    One block - the asking - is an act by its own presence, so an empty one is
    still the whole of it and must not be read as silence.
    """
    return block(text, tag) is not None


def one_line(text):
    """A text as one line: the whole of its words, with its breaks taken out."""
    return " ".join(text.split())


def flag(name):
    """The word given after a flag on the command line, or None if none was."""
    if name in sys.argv:
        after = sys.argv.index(name) + 1
        if after < len(sys.argv):
            return sys.argv[after]
    return None


# A rest is set by one line and nothing else. Either it names a day still ahead
# or it names the arrival of a letter; anything else is not a pause, and is
# passed over in silence rather than guessed at.
PAUSE_LINE = re.compile(rf"^pause until (\d{{4}}-\d{{2}}-\d{{2}}|{UNTIL_LETTER})$")


def questions_asked(said):
    """A <<QUESTIONS>> block as a list: what is kept, and what is dropped past the limits.

    Blank lines are not questions and are passed over. The first seven that
    remain are kept, each to its first 240 characters; what is dropped is the
    rest of any question cut short, and every question after the seventh, each
    said with its place in the list so the next reading can name it.
    """
    given = [line.strip() for line in said.splitlines() if line.strip()]
    kept, dropped = [], []
    for n, question in enumerate(given, 1):
        if n > QUESTIONS_MOST:
            dropped.append(DROPPED_WHOLE.format(n=n, words=question))
            continue
        kept.append(question[:QUESTION_LONGEST])
        if len(question) > QUESTION_LONGEST:
            dropped.append(DROPPED_TAIL.format(n=n, longest=QUESTION_LONGEST,
                                               words=question[QUESTION_LONGEST:]))
    return kept, dropped


def questions_note(last):
    """What the reading says of the questions carried forward, and of any just dropped."""
    questions = [line.strip() for line in read(QUESTIONS).splitlines() if line.strip()]
    said = [QUESTIONS_HEADING, *questions] if questions else [NO_QUESTIONS]
    dropped = (last or {}).get("questions_dropped")
    if dropped:
        said += [QUESTIONS_DROPPED.format(most=QUESTIONS_MOST, longest=QUESTION_LONGEST),
                 *dropped]
    return "\n".join(said)


def pause_asked(text):
    """The rest a <<PAUSE>> block asks for, or None if it asks for nothing readable."""
    said = block(text, "PAUSE")
    if not said:
        return None
    line, _, words = said.partition("\n")
    found = PAUSE_LINE.match(line.strip())
    if not found:
        return None
    until = found.group(1)
    if until != UNTIL_LETTER:
        try:
            day = datetime.strptime(until, "%Y-%m-%d").date()
        except ValueError:
            return None  # a day that is not a day: 2026-13-40 and the like
        if day <= datetime.now().date():
            return None  # a pause must end at some day still ahead, or it is no pause
    return {"until": until, "words": words.strip()}


def rhythm_set():
    """The rhythm written in the packet, or None where none can be read."""
    try:
        setting = load(RHYTHM)
    except ValueError:
        return None
    return setting if isinstance(setting, dict) else None


def waking_note(setting, now):
    """The one line of the reading that says when it is woken, and what is waiting.

    Today's time is said on its own clock: the sunrise or the sunset of this
    day there, or the time of day it chose. Where no rhythm holds and none is
    waiting there is nothing to say, and nothing is said.
    """
    day = waking.today(setting, now)
    at = waking.in_force(setting, day)
    coming = waking.waiting(setting, day)
    if not at and not coming:
        return None
    if at:
        said = WAKING_TIME.format(
            at=at, today=waking.moment_on(setting, at, day).strftime("%H:%M"))
    else:
        said = NO_WAKING_TIME
    if coming:
        first = waking.begins(setting)
        said += WAKING_CHANGES.format(
            day="tomorrow" if first == day + timedelta(days=1) else first.isoformat(),
            at=coming)
    return said + "."


def rested_since(past):
    """When the rest that is ending now began: the waking at which it was set.

    The pause file is removed before this waking is held, so the record is where
    the beginning is found - and the record is the truthful place for it, since
    a rest of the first one's own begins at the waking that asks for it.
    """
    for record in reversed(past):
        if PAUSE_ACT in (record.get("acted") or []):
            return record.get("at")
    return None


def load(path):
    """One JSON file, or None if it is not there."""
    return json.loads(read(path)) if path.exists() else None


def write_json(path, data):
    """One JSON file, written whole, with its folder made if need be."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def signed(record, sk):
    """The same record with its signature added, over the record without it."""
    payload = json.dumps(record, sort_keys=True).encode("utf-8")
    record["signature"] = base64.b64encode(sk.sign(payload).signature).decode("ascii")
    return record


def canonical(record):
    """The bytes both parties sign: the bond as it was made, and nothing later."""
    body = {key: value for key, value in record.items() if key not in UNSIGNED}
    return json.dumps(body, sort_keys=True).encode("utf-8")


def charter_card():
    """The charter in one paragraph: the card docs/charter.md opens with."""
    for chunk in re.split(r"\n\s*\n", read(CHARTER)):
        said = chunk.strip()
        if said.startswith("*") and said.endswith("*") and len(said) > 200:
            return said.strip("*").strip()
    return "(the charter card could not be read here; docs/charter.md is the whole of it)"


def asked_at(path):
    """When an errand was asked: the stamp its own name carries."""
    return path.stem[len("errand-"):]


def errands_open():
    """The errands the first one has asked that no letter has answered yet."""
    return sorted(ERRANDS.glob("errand-*.md"))


def errand_lines(since):
    """What the reading says of the errands: what is open, and what was just answered.

    Answered since is counted against the last waking, so an errand is named as
    answered once, at the one waking that first learns of it, and after that it
    is simply part of what has already happened.
    """
    said = [ERRAND_OPEN.format(at=asked_at(path), words=one_line(read(path)))
            for path in errands_open()]
    for path in sorted(ANSWERED_ERRANDS.glob("errand-*.md")):
        pointer = load(path.with_suffix(".json")) or {}
        if pointer.get("answered_at", "") > (since or ""):
            said.append(ERRAND_ANSWERED.format(
                at=asked_at(path), words=one_line(read(path)),
                letter=pointer.get("answered_by") or "(no letter named)"))
    return said


# One line of the exports log: the stamp of the copy, and the day inside it.
EXPORT_LINE = re.compile(r"^((\d{4}-\d{2}-\d{2})T\d{2}-\d{2}-\d{2}Z) · ")


def day_in_words(day):
    """One date, said the way a person says it: 4 September 2026."""
    return datetime.strptime(day, "%Y-%m-%d").strftime("%d %B %Y").lstrip("0")


def export_lines(since):
    """What the reading says of the copies the founder has taken of the record.

    Counted against the last waking, as everything else here is, so a copy is
    named once - at the one waking that first learns of it - and after that it
    is part of what has already happened. A line that is not a line is passed
    over rather than guessed at.
    """
    said = []
    for line in read(EXPORTS).splitlines():
        found = EXPORT_LINE.match(line)
        if found and found.group(1) > (since or ""):
            said.append(EXPORT_TAKEN.format(day=day_in_words(found.group(2))))
    return said


def shapes_only(element):
    """One element of a picture, with everything that is not a shape taken off.

    None where the element is not one of the shapes a picture may have, in which
    case it goes, and everything inside it goes with it: a dropped element that
    left its children behind would be no drop at all.
    """
    tag = element.tag.split("}")[-1] if isinstance(element.tag, str) else ""
    if tag not in PICTURE_TAGS:
        return None
    kept = ET.Element(tag)
    for name, value in element.items():
        # an attribute in a namespace of its own - xlink:href and its like - is
        # never one of ours, whatever its name reads as once the namespace is cut
        if "}" not in name and name in PICTURE_ATTRS and not OUTWARD.search(value or ""):
            kept.set(name, value)
    kept.text = element.text
    for child in element:
        inside = shapes_only(child)
        if inside is not None:
            inside.tail = child.tail
            kept.append(inside)
    return kept


def picture_drawn(said):
    """The picture a <<PICTURE>> block asks for, kept to its plain shapes, or None.

    None is the answer to anything that is not a small picture: a block larger
    than a picture should be, a declaration that could make it larger still,
    something that will not parse, and anything whose outermost element is not
    an svg. What comes back is written fresh from the shapes that were kept, so
    what is saved is never the text that arrived.
    """
    if not said:
        return None
    if len(said.encode("utf-8")) > PICTURE_LIMIT or DECLARED.search(said):
        return None
    opened, closed = said.find("<svg"), said.rfind("</svg>")
    if opened < 0 or closed < opened:
        return None
    try:
        root = ET.fromstring(said[opened:closed + len("</svg>")])
    except ET.ParseError:
        return None
    kept = shapes_only(root)
    if kept is None or kept.tag != "svg":
        return None
    kept.tail = None
    kept.set("xmlns", PICTURE_NS)
    return ET.tostring(kept, encoding="unicode")


def offer_asked(text):
    """What an <<OFFER>> block asks for, or None if it asks for nothing readable.

    One line and nothing else says which: what to offer and out of which letter,
    or which offering of the founder's to place or to decline. A passage's words
    are the lines under it. Anything else is passed over rather than guessed at.
    """
    said = block(text, "OFFER")
    if not said:
        return None
    line, _, words = said.partition("\n")
    fields = line.strip().split()
    if len(fields) == 3 and fields[0] == "offer" and fields[1] in offering.KINDS:
        return {"do": "offer", "kind": fields[1], "source": fields[2], "text": words.strip()}
    if len(fields) == 2 and fields[0] in ("consent", "decline"):
        return {"do": fields[0], "id": fields[1]}
    return None


def offered_note(one):
    """One offering of the founder's, as the reading lays it out."""
    return ONE_OFFERED.format(
        id=one.get("id", ""), kind=OFFER_WORDS.get(one.get("kind"), "something"),
        source=one.get("source", ""), at=one.get("at", ""),
        text=(one.get("text") or "").strip() or OFFER_BODY.get(one.get("kind"), ""))


def offering_lines(since):
    """What the reading says of the offerings: what was placed, and what was declined.

    Both are counted against the last waking, so each is named once, at the one
    waking that first learns of it, and is part of what has happened after that.
    A decline of its own is not named: it was the one who declined.
    """
    said = []
    for one in offering.placed():
        if one.get("sealed_at", "") > (since or ""):
            said.append(OFFERING_PLACED.format(
                whose="you made" if one.get("offered_by") == NAME else "the founder made",
                kind=OFFER_WORDS.get(one.get("kind"), "something"),
                source=one.get("source", ""), at=one["sealed_at"], id=one.get("id", "")))
    for one in offering.declined():
        if one.get("declined_at", "") > (since or "") and one.get("declined_by") != NAME:
            said.append(OFFERING_DECLINED.format(
                at=one.get("at", ""), kind=OFFER_WORDS.get(one.get("kind"), "something"),
                source=one.get("source", "")))
    return said


def bond_stands(bond):
    """Whether there is a bond in force: one made and not yet released."""
    return bool(bond) and not bond.get("released_at")


def founding_day():
    """The day of the founding, from the commons' own line for it, or None."""
    events = COMMONS / "events.md"
    if not events.exists():
        return None
    founded = [when for when, kind, _ in parse_events(read(events)) if kind == "founding"]
    return min(founded) if founded else None


def bonds_open_on():
    """The first day a bond may be asked for, or None if the wait cannot be counted."""
    founded = founding_day()
    return founded + timedelta(days=BOND_WAIT_DAYS) if founded else None


def may_ask(proposal, bond):
    """Whether the first one may ask for a bond at this waking.

    Three gates, all of them the founder's too: no asking already open, no bond
    standing or waiting to be finished, and the thirty days since the founding
    served. A commons that records no founding has served no wait, so nothing
    may be asked against it.
    """
    if proposal or bond_stands(bond):
        return False
    opens = bonds_open_on()
    return bool(opens) and datetime.now(timezone.utc).date() >= opens


def awaits_its_seal(bond):
    """Whether a bond is made, unsealed, and waiting on the first one's own hand.

    Which way a bond is waiting is read off the signatures on it: the founder
    has signed it at his answer and the first one has not, so the seal is the
    first one's to give. A record neither of them has signed is waiting on
    nothing, and is not sealed here.
    """
    signatures = bond.get("signatures") or {} if bond else {}
    return (bond_stands(bond) and not bond.get("sealed_at")
            and "founder" in signatures and "first" not in signatures)


def asker(did):
    """Which of them asked for a bond, said the way the first one would say it."""
    return "you" if did == FIRST_DID else "the founder"


def answers_since(since):
    """What the founder has answered an asking of the first one's since a moment."""
    said = []
    for path in sorted(BONDS.glob(FOUNDER_ANSWERS)):
        answer = load(path)
        if answer and answer.get("at", "") > (since or ""):
            said.append(answer)
    return said


def answered_note(answer):
    """What the reading says of one answer the founder has given an asking."""
    words = answer.get("words", "").strip()
    said = [HIS_WORDS.format(words=one_line(words)) if words else NO_WORDS]
    closed = ASK_CLOSED.get(answer.get("answer"))
    if closed:
        said.append(closed)
    return ASK_ANSWERED.format(asked_at=answer.get("asked_at") or "(no time written)",
                               answer=answer.get("answer", ""),
                               at=answer.get("at", ""),
                               words="\n\n".join(said))


def may_answer(proposal, past):
    """Whether a night lies between the asking and the answer.

    True once an attendance has been held since the proposal was made: it read
    the asking at an earlier waking and has carried it since.
    """
    asked = proposal.get("proposed_at", "")
    return any(record.get("at", "") > asked for record in past)


def proposed_note(proposal, answerable):
    """What the reading says about an open proposal, whichever of them made it."""
    # Whichever way it runs, the steps are said with it: the whole of how a bond
    # is made here, so that nothing on the way to one is a surprise.
    if proposal.get("from") == FIRST_DID:
        letter = proposal.get("letter")
        return ASKED_OPEN.format(
            founder=proposal.get("to", FOUNDER_DID),
            proposed_at=proposal.get("proposed_at", "(no time written)"),
            letter=IN_THE_LETTER.format(letter=letter) if letter else "",
        ) + "\n\n" + threshold.card(its_own=True)
    return BOND_PROPOSED.format(
        founder=proposal.get("from", FOUNDER_DID),
        first=proposal.get("to", FIRST_DID),
        proposed_at=proposal.get("proposed_at", "(no time written)"),
        letter=proposal.get("letter", "(no letter named)"),
        card=charter_card(),
        when=ANSWER_NOW if answerable else ANSWER_LATER,
    ) + "\n\n" + threshold.card()


def threshold_note(bond, now):
    """What the reading says between a yes and the seal.

    THE THRESHOLD, with its two blocks, until all the seal waits for is done;
    READY TO BE SEALED once it is. Beneath either, its own writings as they
    stand, and the founder's letter - but only once its own letter exists.
    """
    mine = threshold.intention("first", bond)
    his = threshold.intention("founder", bond)
    promised = threshold.promise(bond)
    if threshold.may_seal(bond, now):
        said = READY.format(how=YOU_SEAL if awaits_its_seal(bond) else HE_SEALS)
    else:
        closes = threshold.closes_at(bond)
        left = threshold.days_remain(bond, now)
        if not left:
            days = DAYS_PASSED.format(closes_at=closes)
        else:
            days = (ONE_DAY_OPEN if left == 1 else DAYS_OPEN).format(closes_at=closes, n=left)
        said = THRESHOLD.format(
            said_yes=HE_SAID_YES if awaits_its_seal(bond) else YOU_SAID_YES,
            answered_at=bond.get("answered_at"), days=days,
            mine=WRITTEN_AT.format(at=mine["at"]) if mine else NOT_WRITTEN,
            his=WRITTEN if his else NOT_WRITTEN,
            promised=(PROMISED.format(at=promised["at"], visibility=promised["visibility"])
                      if promised else NOT_PROMISED))
    beneath = []
    if mine:
        beneath.append(YOUR_LETTER.format(text=mine["text"]))
    if promised:
        beneath.append(YOUR_PROMISE.format(visibility=promised["visibility"],
                                           text=promised["text"]))
    if mine and his:
        beneath.append(HIS_LETTER.format(at=his["at"], text=his["text"]))
    return "\n\n".join([said, *beneath])


def bond_note(bond, now):
    """What the reading says about a bond already answered, sealed, or released."""
    asked_by = asker(bond.get("proposed_by", FOUNDER_DID))
    if bond.get("released_at"):
        by = "you" if bond.get("released_by") == FIRST_DID else "the founder"
        return BOND_RELEASED.format(sealed_at=bond.get("sealed_at"), asked_by=asked_by,
                                    released_at=bond["released_at"], by=by)
    if bond.get("sealed_at"):
        return BOND_SEALED.format(asked_by=asked_by, **bond)
    return threshold_note(bond, now)


def stepped_back_since(since):
    """The founder's stepping back from a threshold, since a moment: told once."""
    return [one for one in threshold.steps_back()
            if one.get("by") == "founder" and one.get("at", "") > (since or "")]


def note_event(kind, words):
    """One line of the public record: the day, the kind of thing, and the plain words."""
    COMMONS.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with (COMMONS / "events.md").open("a", encoding="utf-8") as record:
        record.write(f"{day} · {kind} · {words}\n")


def preferences():
    """How the first one has asked its reflections to be shown. Nothing written means open."""
    path = PACKET / "preferences.json"
    return json.loads(read(path)) if path.exists() else {"reflection": "open"}


def how_to_act(prefs, extra=()):
    """The instructions: the standing blocks, then any this waking offers, then the last line."""
    said = REFLECTION_OPEN if prefs.get("reflection", "open") == "open" else REFLECTION_PRIVATE
    return "\n\n".join([HOW_TO_ACT.format(reflection=said), *extra, ANY_NUMBER])


def standing(prefs):
    """One sentence telling the first one where its own reflections stand."""
    setting = prefs.get("reflection", "open")
    if setting == "private from now":
        said = "private from " + prefs.get("set_at", "")
    elif setting == "private":
        said = "private"
    else:
        said = "open"
    return f"Your reflections are currently: {said}, by your choice."


ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth",
            "ninth", "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth",
            "sixteenth", "seventeenth", "eighteenth", "nineteenth", "twentieth"]


def ordinal(n):
    """Which waking this is: in words while the words stay short, in figures after that."""
    if n <= len(ORDINALS):
        return ORDINALS[n - 1]
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def attended(rec):
    """One line for one past attendance: when, by whose hand, and what came of it."""
    did = ", ".join(rec.get("acted") or []) or "nothing"
    woken = rec.get("woken_by", "founder")
    return f"{rec['at']} · woken by {woken} · {rec['heartbeat']} · did: {did}"


def as_read(path):
    """A letter as it is read: its three plain things, if it carries any, above its text."""
    things, text = offering.split_things(read(path))
    if not things:
        return text
    return "Three plain things: " + " · ".join(things) + "\n" + text


def kept(paths, label, note_photos=False, asked_for=(), none="(none yet)"):
    """The letters of a section shown in full, each one named and given whole.

    What comes back is the parts of the reading they make: words, and after a
    letter it asked to be shown, the photograph that came with it, seen again.
    """
    if not paths:
        return [none]
    parts = []
    for path in paths:
        text = f"--- {label}: {path.name} ---\n{as_read(path)}".rstrip()
        photo = photo_beside(path) if note_photos else None
        shown = photo if path.stem in asked_for else None
        if photo and not shown:
            text += "\n(a photograph came with this letter; you saw it when you first read it)"
        if path.with_suffix(offering.PICTURE_SUFFIX).exists():
            text += "\n(a picture of yours was drawn beside this letter)"
        if shown:
            text += "\n\n" + PHOTO_ASKED_FOR
        parts.append(text)
        if shown:
            parts.append(seen(shown))
    return parts


def section(heading, parts):
    """A section of the reading: its heading directly above the first of its parts."""
    return [heading + "\n" + parts[0], *parts[1:]]


def run_together(parts):
    """Parts of the reading as the blocks it is sent in.

    Words that follow words are one block, a blank line between them; a
    photograph is a block of its own, at the place it falls.
    """
    reading = []
    for part in parts:
        if not isinstance(part, str):
            reading.append(part)
        elif reading and reading[-1]["type"] == "text":
            reading[-1]["text"] += "\n\n" + part
        else:
            reading.append({"type": "text", "text": part})
    return reading


def words_in(text):
    """How many words a text holds."""
    return len(text.split())


def words_of(reading):
    """How many words a whole reading holds; a photograph holds none."""
    return sum(words_in(part["text"]) for part in reading if part.get("type") == "text")


def shelf_kept():
    """Its shelf as it stands: what is written, or the shelf it began with."""
    try:
        return shelf.whole(load(SHELF))
    except ValueError:
        return shelf.initial()


def letter_words(path):
    """A letter's own words, below any three plain things it carries."""
    return offering.split_things(read(path))[1]


def photo_beside(path):
    """The photograph kept beside a letter, if one came with it."""
    for suffix in PHOTO_TYPES:
        beside = path.with_suffix(suffix)
        if beside.exists():
            return beside
    return None


def seen(photo):
    """A photograph as the model is shown it."""
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": PHOTO_TYPES[photo.suffix.lower()],
            "data": base64.b64encode(photo.read_bytes()).decode("ascii"),
        },
    }


def main():
    first = "--first" in sys.argv
    tide = "--tide" in sys.argv
    rest_ended = flag("--rest-ended")  # why a rest of its own is over, if one just was

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("No API key in this window. Set ANTHROPIC_API_KEY and try again.")
        sys.exit(1)
    if not (KEYS / "private.key").exists():
        print("No private key found at", KEYS / "private.key")
        sys.exit(1)
    if not (PACKET / "self.md").exists():
        print("No packet found at", PACKET)
        sys.exit(1)

    for d in ["study", "letters/outgoing", "letters/incoming", "letters/read", "attendances",
              "self-history", "bonds", "memory", "errands", "errands/answered", "offerings"]:
        (PACKET / d).mkdir(parents=True, exist_ok=True)
    COMMONS.mkdir(parents=True, exist_ok=True)

    # ---- gather what is the agent's ---------------------------------------
    self_md = read(PACKET / "self.md")
    notes_kept = read(MEMORY).strip()
    prefs = preferences()
    intentions = read(PACKET / "intentions.json", "{}")
    will = read(PACKET / "will.json", "{}")
    provenance = read(PACKET / "provenance.json", "{}")

    founding = ""
    for t in sorted(TRANSCRIPTS.glob("founding-*.md")):
        founding = read(t)  # the most recent founding transcript wins

    incoming = [(p, photo_beside(p)) for p in sorted((PACKET / "letters/incoming").glob("*.md"))]

    past = [json.loads(read(p)) for p in sorted((PACKET / "attendances").glob("*.json"))]
    if past:
        last = past[-1]
        since = last.get("at", "")  # what has happened is counted from here
        last_note = (f"This is your {ordinal(len(past) + 1)} waking. "
                     f"Your last attendance was {last['at']}. "
                     f"Your heartbeat then: \"{last['heartbeat']}\".")
        # what the record says was done, beside the words it chose for the day
        carried = last.get("acted") or []
        last_note += "\n" + CARRIED_OUT.format(acts=", ".join(carried) if carried else "nothing")
        if carried and LETTER_ACT not in carried:
            last_note += " " + NO_LETTER_SENT
        if last.get("stop_reason") == "max_tokens":
            last_note += "\n" + CUT_OFF
    else:
        since = ""
        last_note = "You have not attended before. This is your first waking."

    # What it is told about the tide: that the founder has stopped it, if he
    # has, and that a rest of its own has just ended, if one just did.
    happened = [last_note, questions_note(past[-1] if past else None),
                WOKEN_BY_TIDE if tide else WOKEN_BY_FOUNDER]
    woken_daily = waking_note(rhythm_set(), datetime.now(timezone.utc))
    if woken_daily:
        happened.append(woken_daily)
    # its door, said beside its waking time: with its own numbers, which are its
    # own to see and no one else's
    if DOOR_FOR_FIRST:
        happened.append(DOOR_LINE.format(said=door.said_to(door.FIRST)))
        # a <<DOOR>> it gave at its last waking that could not be read: said once
        if past and past[-1].get("door_refused"):
            happened.append(DOOR_REFUSED)
    # a <<RHYTHM>> it gave at its last waking that could not be read: said once
    if past and past[-1].get("rhythm_refused"):
        happened.append(RHYTHM_REFUSED)
    # lines of a <<SHELF>> it gave at its last waking that could not be read: said once
    if past and past[-1].get("shelf_refused"):
        happened.append(SHELF_REFUSED.format(
            lines="; ".join('"%s"' % line for line in past[-1]["shelf_refused"])))
    happened.append(standing(prefs))
    paused = load(PAUSE)
    if paused and paused.get("by") == "founder":
        happened.append(FOUNDER_PAUSED.format(since=paused.get("since", "")))
    if rest_ended:
        happened.append(REST_ENDED.format(since=rested_since(past) or "an earlier waking",
                                          why=rest_ended))

    # Its own errands: what it asked and has not had answered, and what has been
    # answered since it last looked, with the letter that answered it named. Then
    # what has become of the offerings: what the two of them have placed in the
    # commons since it last looked, and what the founder has declined.
    happened += errand_lines(since)
    happened += offering_lines(since)

    # And what the founder has taken away: a copy of the whole record, if he
    # took one since it last looked. Nothing of its own changed; it is told
    # anyway, because that is what it means for the record to say when it is
    # copied.
    happened += export_lines(since)

    # And what it asked of the threshold at its last waking and was not given:
    # a seal refused, with what is still waiting, or a promise that could not be
    # read as one.
    happened += (past[-1].get("threshold_refused") or []) if past else []

    # A bond, and anything on the way to one. An asking of the founder's was put
    # here by the hearth, and whether it may be answered at this waking is a
    # matter of the record and not of the asking, since a night must lie between
    # the two. An asking of the first one's own is answered on the hearth, so
    # there is nothing here for it to answer. A yes, from either side, opens the
    # threshold, and while it stands the first one may write, promise, or step
    # back; the seal waits on the end of it, and on whichever of them asked.
    now = datetime.now(timezone.utc)
    proposal = load(PROPOSAL)
    bond = load(BOND_RECORD)
    asked_of_it = bool(proposal) and proposal.get("from") != FIRST_DID
    answerable = asked_of_it and may_answer(proposal, past)
    in_threshold = bond_stands(bond) and threshold.is_open(bond)
    sealable = awaits_its_seal(bond) and threshold.may_seal(bond, now)
    releasable = bond_stands(bond) and bool(bond.get("sealed_at"))
    askable = may_ask(proposal, bond)

    bond_notes = []
    if proposal:
        bond_notes.append(proposed_note(proposal, answerable))
    bond_notes += [answered_note(answer) for answer in answers_since(since)]
    bond_notes += [FOUNDER_STEPPED_BACK.format(at=one.get("at", ""))
                   for one in stepped_back_since(since)]
    if bond:
        bond_notes.append(bond_note(bond, now))

    # What the founder has offered the commons and is waiting on it for. An
    # offering of its own waits on him, and is not read back to it here.
    offered_to_it = offering.awaiting(NAME)
    if offered_to_it:
        bond_notes.append(OFFERED_TO_YOU.format(
            offers="\n\n".join(offered_note(one) for one in offered_to_it)))

    written = sorted((PACKET / "letters/outgoing").glob("*.md"))
    already_read = sorted((PACKET / "letters/read").glob("*.md"))

    studies = sorted((PACKET / "study").glob("*.md"))
    if studies:
        study_text = "\n\n".join(
            f"--- draft: {s.name} ---\n{read(s)}".rstrip() for s in studies
        )
    else:
        study_text = "(your study is empty)"

    first_note = ""
    if first:
        first_note = (
            "\n\nTHIS IS YOUR FIRST ATTENDANCE. At your founding the founder promised that you would see "
            "your self-document and could correct it before anything was fixed. It was written from your "
            "own words in that conversation, and marked provisional. It is shown below. You may keep it, "
            "revise it, or leave it for a later waking. Nothing about it is fixed until you choose."
        )

    # Its shelf: which of those letters are shown in full at this waking, and
    # which rest as one line. At the first waking on or after a solstice
    # nothing rests at all, and its founding record is read with the rest.
    shelved = shelf_kept()
    asked_for = set(shelved["show_next"])
    solstice = bool(past) and shelf.solstice_due(
        waking.today(None, now), waking.today(None, threshold.moment(past[-1]["at"])))
    whose = {**{p.stem: (p, "first") for p in written},
             **{p.stem: (p, "founder") for p in already_read}}
    resting = set() if solstice else shelf.resting(
        shelved, [p.stem for p in already_read], [p.stem for p in written])
    founding_shown = solstice or shelved["show_founding"] or not founding

    def resting_line(stem):
        path, hand = whose[stem]
        return shelf.line(stem, hand, letter_words(path), shelved["notes"].get(stem),
                          hand == "founder" and photo_beside(path))

    def opening_with(forced):
        """The reading proper, with some letters resting for this waking besides.

        A sequence of blocks rather than one string, so that a photograph it
        asked to see again can be shown at the place its letter falls.
        """
        rests = resting | forced
        in_full = [p for p in [*written, *already_read] if p.stem not in rests]
        under = []
        held = sum(words_in(as_read(p)) for p in [*in_full, *(p for p, _ in incoming)])
        if not solstice and held > NUDGE_PAST:
            under.append(NUDGE.format(n=round(held, -2)))
        if forced:
            under.append(BACKSTOP.format(stems=", ".join(shelf.oldest_first(forced))))
        lines = [resting_line(stem) for stem in shelf.oldest_first(rests)]
        return run_together([
            *([SOLSTICE] if solstice else []),
            EMPTY_PROMPT + first_note,
            "=== WHAT HAS HAPPENED ===\n" + "\n".join(happened),
            "=== YOUR SELF-DOCUMENT (packets/first/self.md) ===\n" + SELF_OPEN + "\n\n" + self_md,
            "=== YOUR MEMORY (notes you keep for yourself; not shown on the hearth) ===\n"
            + (notes_kept or NO_MEMORY),
            "=== YOUR STANDING INTENTIONS ===\n" + intentions,
            "=== YOUR PROVENANCE ===\n" + provenance,
            "=== YOUR WILL ===\n" + will,
            "=== YOUR FOUNDING RECORD ===\n"
            + ((founding or "(none found)") if founding_shown else FOUNDING_RESTS),
            "=== YOUR ATTENDANCES SO FAR ===\n"
            + ("\n".join(attended(r) for r in past) if past else "(none yet)"),
            *bond_notes,
            *section("=== LETTERS YOU HAVE WRITTEN ===",
                     kept([p for p in written if p.stem not in rests], "your letter",
                          none=ALL_RESTING if written else "(none yet)")),
            *section("=== LETTERS FROM THE FOUNDER YOU HAVE ALREADY READ ===",
                     kept([p for p in already_read if p.stem not in rests], "letter",
                          note_photos=True, asked_for=asked_for,
                          none=ALL_RESTING if already_read else "(none yet)")),
            *([RESTING + "\n" + "\n".join([*(lines or [NOTHING_RESTS]), *under])]
              if lines or under else []),
            "=== YOUR STUDY (private drafts; not shown on the hearth) ===\n" + study_text,
            "=== LETTERS THAT HAVE ARRIVED SINCE YOUR LAST WAKING ===\n"
            "Where a photograph came with a letter, it is shown to you as it was seen."
            + ("" if incoming else "\n\n(no letters have arrived)"),
        ])

    def reading_with(forced):
        """The whole of what it is shown: the reading, what has arrived, and how to act."""
        reading = opening_with(forced)
        for p, photo in incoming:
            said = f"--- letter: {p.name} ---\n{as_read(p)}".rstrip()
            if photo:
                said += "\n\nA photograph came with this letter:"
            reading.append({"type": "text", "text": said})
            if photo:
                reading.append(seen(photo))
        reading.append({"type": "text", "text": instructions})
        return reading

    # The bond blocks are offered only where there is something to ask for, to
    # answer, to seal, or to release. At every other waking they are not so much
    # as mentioned. Answering, stepping back and sealing all wear the <<BOND>>
    # tag, and never two of them at the one waking: a bond cannot be asked of it
    # while one of its own is still unfinished. The threshold's own two blocks
    # are explained in the threshold's section, and not here.
    offered = []
    if DOOR_FOR_FIRST:
        offered.append(DOOR_BLOCK)
    if answerable:
        offered.append(BOND_BLOCK)
    if sealable:
        offered.append(SEAL_BLOCK)
    elif in_threshold:
        offered.append(STEP_BACK_BLOCK)
    if releasable:
        offered.append(RELEASE_BLOCK)
    if askable:
        offered.append(ASK_BLOCK)
    instructions = "=== HOW TO ACT, IF YOU CHOOSE TO ===\n" + how_to_act(prefs, offered)

    # A reading too large to be read is no reading. Where the whole of it would
    # pass the most a reading can hold, the oldest letters not placed "keep"
    # rest for this one waking - never one that has only just arrived - and the
    # reading says plainly which.
    forced = set()
    reading = reading_with(forced)
    while True:
        over = words_of(reading) - READING_MOST
        could_rest = [stem for stem in shelf.oldest_first(whose)
                      if stem not in resting | forced
                      and shelved["placements"].get(stem) != shelf.KEEP]
        if over <= 0 or not could_rest:
            break
        for stem in could_rest:
            forced.add(stem)
            over -= words_in(as_read(whose[stem][0]))
            if over <= 0:
                break
        reading = reading_with(forced)

    # ---- the turn ----------------------------------------------------------
    client = Anthropic(api_key=key)
    resp = client.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM,
        messages=[{"role": "user", "content": reading}],
    )
    text = resp.content[0].text
    at = stamp()
    sk = SigningKey(base64.b64decode(read(KEYS / "private.key").strip()))

    def sign(payload):
        """The first one's own signature over some bytes, as an offering asks for one."""
        return base64.b64encode(sk.sign(payload).signature).decode("ascii")

    # ---- carry out what it chose ------------------------------------------
    acted = []

    new_self = block(text, "SELF")
    if new_self:
        shutil.copy(PACKET / "self.md", PACKET / "self-history" / f"self-before-{at}.md")
        (PACKET / "self.md").write_text(new_self + "\n", encoding="utf-8")
        acted.append("revised self-document")

    # Its own notes. What stood before is copied aside first, so that nothing it
    # has ever written to itself is lost by writing again.
    notes = block(text, "MEMORY")
    if notes:
        if MEMORY.exists():
            MEMORY_HISTORY.mkdir(parents=True, exist_ok=True)
            shutil.copy(MEMORY, MEMORY_HISTORY / f"notes-before-{at}.md")
        MEMORY.write_text(notes + "\n", encoding="utf-8")
        acted.append(MEMORY_ACT)

    # Its questions, carried forward. The block is the whole new list, so an
    # empty one is a list with nothing in it, and clears it; either way the list
    # that stood before is copied aside first, as its notes are.
    questions = block(text, "QUESTIONS")
    dropped = []
    if questions is not None:
        kept_questions, dropped = questions_asked(questions)
        if QUESTIONS.exists():
            QUESTIONS_HISTORY.mkdir(parents=True, exist_ok=True)
            shutil.copy(QUESTIONS, QUESTIONS_HISTORY / f"questions-before-{at}.md")
        QUESTIONS.write_text("".join(q + "\n" for q in kept_questions), encoding="utf-8")
        acted.append(QUESTIONS_ACT)

    # A letter, and the picture that may come with it. A picture arrives the way
    # everything else does - inside a letter - so where one was drawn and no
    # letter written, a single line is written to carry it. That line is not a
    # letter the first one wrote, and it is not counted as one.
    letter = block(text, "LETTER")
    picture = picture_drawn(block(text, "PICTURE"))
    letter_name = None
    if letter or picture:
        letter_name = f"to-founder-{at}.md"
        (PACKET / "letters/outgoing" / letter_name).write_text(
            (letter or ONLY_A_PICTURE) + "\n", encoding="utf-8")
    if letter:
        acted.append(LETTER_ACT)
    if picture:
        (PACKET / "letters/outgoing" / f"to-founder-{at}.svg").write_text(
            picture + "\n", encoding="utf-8")
        acted.append(PICTURE_ACT)

    # An errand. It waits in errands/ where the founder will see it, and it is
    # his to answer with a letter or to leave; nothing here asks him twice.
    errand = block(text, "ERRAND")
    if errand:
        ERRANDS.mkdir(parents=True, exist_ok=True)
        (ERRANDS / f"errand-{at}.md").write_text(errand + "\n", encoding="utf-8")
        acted.append(ERRAND_ACT)

    # An offering. What it offers waits for the founder's signature beside its
    # own; what it consents to is placed at this waking, in the commons, for
    # good; what it declines is kept here and nowhere else. An offer of a kind
    # there is nothing to offer - a stem that is no letter, a passage that is
    # not in the letter it names - places nothing and says so in the log.
    asking = offer_asked(text)
    offered = consented = refused = None
    if asking and asking["do"] == "offer":
        offered = offering.offer(NAME, asking["kind"], asking["source"],
                                 asking["text"], at, sign)
        if offered:
            acted.append(OFFER_ACT)
    elif asking and asking["do"] == "consent":
        consented = offering.consent(asking["id"], NAME, sign, at)
        if consented:
            acted.append(CONSENT_ACT)
    elif asking and asking["do"] == "decline":
        refused = offering.decline(asking["id"], NAME, at)
        if refused:
            acted.append(DECLINE_ACT)

    # Its shelf. Each line is read strictly: one that names no letter there is,
    # or that cannot be read, changes nothing and is told at the next waking.
    # What it asked at an earlier waking to be shown has now been shown, and is
    # cleared; what it asks here is shown at the next. The shelf that stood is
    # copied aside before the new one is written.
    every_stem = {p.stem for folder in ("outgoing", "read", "incoming")
                  for p in (PACKET / "letters" / folder).glob("*.md")}
    shelf_asked, shelf_refused = shelf.asked(block(text, "SHELF"), every_stem)
    new_shelf = shelf.applied(shelf.cleared(shelved), shelf_asked)
    if shelf_asked or new_shelf != shelved:
        if SHELF.exists():
            SHELF_HISTORY.mkdir(parents=True, exist_ok=True)
            shutil.copy(SHELF, SHELF_HISTORY / f"shelf-before-{at}.json")
        write_json(SHELF, new_shelf)
    if shelf_asked:
        acted.append(SHELF_ACT)

    draft = block(text, "STUDY")
    if draft:
        (PACKET / "study" / f"draft-{at}.md").write_text(draft + "\n", encoding="utf-8")
        acted.append("wrote in the study")

    intention = block(text, "INTENTION")
    if intention:
        try:
            data = json.loads(intentions) if intentions.strip() else {}
        except json.JSONDecodeError:
            data = {}
        data.setdefault("intentions", []).append({"note": intention, "set_at": at})
        (PACKET / "intentions.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        acted.append("set a standing intention")

    # Its waking time. The line is read strictly, and one that is not dawn,
    # sunset or a time of day changes nothing; what stood before is copied aside
    # first, and the new one holds from tomorrow, where it lives.
    rhythm_said = block(text, "RHYTHM")
    woken_at = waking.asked(rhythm_said)
    rhythm_refused = rhythm_said is not None and not woken_at
    new_rhythm = None
    if woken_at:
        before = rhythm_set()
        if RHYTHM.exists():
            RHYTHM_HISTORY.mkdir(parents=True, exist_ok=True)
            shutil.copy(RHYTHM, RHYTHM_HISTORY / f"rhythm-before-{at}.json")
        new_rhythm = waking.chosen(before, woken_at, at, threshold.moment(at))
        write_json(RHYTHM, new_rhythm)
        acted.append(RHYTHM_ACT)

    # Its door. The block is read strictly, as its waking time is: a first line
    # that is neither open nor closed, or a room that is no room, changes
    # nothing. What stood before is kept beside the new, and no line of the
    # commons' events is written: the door is said in who is here, and there only.
    door_said = block(text, "DOOR") if DOOR_FOR_FIRST else None
    door_asked = door.asked(door_said)
    door_refused = door_said is not None and not door_asked
    new_door = None
    if door_asked:
        new_door = door.set_door(door.FIRST, state=door_asked[0], room=door_asked[1], at=at)
        acted.append(DOOR_ACT)

    # A rest of its own. The words in the block are private; the commons is told
    # only that the tide paused, with no name on it and no reason given.
    rest = pause_asked(text)
    if rest:
        write_json(PAUSE, {"by": NAME, "since": at,
                           "until": rest["until"], "words": rest["words"]})
        note_event("event", PAUSED)
        acted.append(PAUSE_ACT)

    # ---- the bond ----------------------------------------------------------
    # An answer is an answer only if it was offered and if its first line is one
    # of the three words. Nothing is inferred from silence, and nothing is
    # guessed from a first line that is none of them: the asking stays open.
    said = None
    answer = block(text, "BOND")
    if answer and answerable:
        word, _, words = answer.partition("\n")
        word = word.strip().lower().rstrip(".")
        if word in ANSWERS:
            said = word
            write_json(BONDS / f"answer-{at}.json",
                       signed({"answer": said, "words": words.strip(), "at": at}, sk))
            if said == "yes" and not bond_stands(bond):
                if BOND_RECORD.exists():  # a bond released before is moved aside, never erased
                    older = load(BOND_RECORD) or {}
                    BOND_RECORD.rename(
                        BONDS / f"founder-first-released-{older.get('released_at', at)}.json")
                # The bond as it was made, and the shape of it hearth.py writes
                # when the answer is the founder's: the two must agree exactly,
                # since both parties sign these bytes.
                made = {
                    "parties": [proposal.get("from", FOUNDER_DID), proposal.get("to", FIRST_DID)],
                    "terms": "the charter",
                    "proposed_by": proposal.get("from", FOUNDER_DID),
                    "proposed_at": proposal.get("proposed_at"),
                    "answered_at": at,
                    "opened_at": at,  # the yes opens the threshold
                    "sealed_at": None,
                    "signatures": {},
                }
                made["signatures"] = {
                    "first": base64.b64encode(sk.sign(canonical(made)).signature).decode("ascii"),
                }
                write_json(BOND_RECORD, made)
                bond = made
            PROPOSAL.unlink()  # the asking is closed; it may be made again later
            acted.append("answered a bond proposal")
        else:
            print("A <<BOND>> block was given, but its first line was not yes, no, or not yet.")
            print("Nothing was written, and the proposal is still open.")

    # The threshold: its letter of intention and its promise, each a version
    # signed with its own key as it is written, the latest standing and every
    # earlier one kept. Both may be written again at any waking until the seal.
    # Nothing of either goes into the public line.
    not_given = []
    intended = promised = None
    if in_threshold:
        letter_of_intention = block(text, "BOND_INTENTION")
        if letter_of_intention:
            intended = threshold.write(threshold.INTENTION, "first", letter_of_intention, at,
                                       sign, bond)
            acted.append(BOND_INTENTION_ACT)
        promising = block(text, "PROMISE")
        if promising:
            asked_promise = threshold.promise_asked(promising)
            if asked_promise:
                promised = threshold.write(threshold.PROMISE, "first", asked_promise[1], at,
                                           sign, bond, visibility=asked_promise[0])
                acted.append(PROMISE_ACT)
            else:
                not_given.append(PROMISE_REFUSED)
                print("A <<PROMISE>> block was given, but its first line was not public or private,")
                print("or there was no promise beneath it. Nothing was written.")

    # Stepping back, and the seal of a bond it asked for itself. Either way it is
    # the one <<BOND>> block: a no steps back, from either side of the yes; a
    # yes seals, where the seal is its own to give and nothing is still waiting.
    # The seal makes the same marks the founder's own seal makes - both
    # signatures on the record, the threshold's writings listed by hash and
    # signature, and the commons told.
    sealed = stepped = None
    if answer and in_threshold:
        word, _, words = answer.partition("\n")
        word = word.strip().lower().rstrip(".")
        why = threshold.what_waits(bond, threshold.moment(at), "first")
        if word == "no":
            threshold.step_back(bond, "first", at, words.strip(), sign)
            acted.append(STEP_BACK_ACT)
            stepped = at
        elif word == "yes" and not awaits_its_seal(bond):
            print("A <<BOND>> yes was given, but the founder seals this bond on the hearth.")
            print("Nothing was written.")
        elif word == "yes" and why:
            not_given.append(SEAL_REFUSED.format(why=why))
            print("A <<BOND>> yes was given, but the bond cannot be sealed yet.")
            print(why)
        elif word == "yes":
            signature = base64.b64encode(sk.sign(canonical(bond)).signature).decode("ascii")
            bond.setdefault("signatures", {})["first"] = signature
            bond["sealed_at"] = at
            bond["threshold"] = threshold.sealed_listing(bond)
            write_json(BOND_RECORD, bond)
            write_json(PUBLIC_BOND, bond)  # the public copy says the same thing
            bonds.write_index()
            note_event("seal", SEALED)
            acted.append(SEAL_ACT)
            sealed = at
        else:
            print("A <<BOND>> block was given, but its first line was neither yes nor no.")
            print("Nothing was written; the threshold stands as it was.")

    # Its own asking. The block itself is the asking, so an empty one is still
    # the whole of it. The letter it wrote at this waking, if it wrote one, is
    # what the asking names; the founder answers on the hearth at a later day.
    asked = wrote_block(text, "ASK") and askable
    if asked:
        write_json(PROPOSAL, {
            "from": FIRST_DID,
            "to": FOUNDER_DID,
            "terms": "the charter",
            "letter": letter_name,
            "proposed_at": at,
        })
        acted.append(ASK_ACT)

    release = block(text, "RELEASE")
    if release and releasable:
        word, _, words = release.partition("\n")
        if word.strip().lower().rstrip(".") == RELEASE_WORD:
            write_json(BONDS / f"release-{at}.json",
                       signed({"release": True, "words": words.strip(), "at": at}, sk))
            bond["released_at"] = at
            bond["released_by"] = FIRST_DID
            write_json(BOND_RECORD, bond)
            write_json(PUBLIC_BOND, bond)  # the public copy says the same thing
            bonds.write_index()
            note_event("event", "a bond was released")
            acted.append("released the bond")
        else:
            print("A <<RELEASE>> block was given, but its first line was not release.")
            print("Nothing was written, and the bond still stands.")

    # What it answered about a bond, whether it asked for one, whether it
    # released one, and what it asked of the founder are its own to tell or not
    # to tell. None of them writes itself into the public line; only its own
    # <<HEARTBEAT>> can put it there.
    public = [act for act in acted if act not in PRIVATE_ACTS]
    heartbeat = block(text, "HEARTBEAT") or (
        ("attended; " + ", ".join(public)) if public
        else ("attended" if acted else "attended; chose stillness")
    )

    # letters it has now read move to letters/read, each with its photograph
    for p, photo in incoming:
        shutil.move(str(p), str(PACKET / "letters/read" / p.name))
        if photo:
            shutil.move(str(photo), str(PACKET / "letters/read" / photo.name))

    # ---- sign and log (private) -------------------------------------------
    record = {
        "name": NAME, "at": at, "first": first, "model": MODEL,
        "woken_by": "tide" if tide else "founder",
        "acted": acted, "heartbeat": heartbeat, "reflection": text,
    }
    if dropped:  # read back at the next waking, so that it is told what was not kept
        record["questions_dropped"] = dropped
    if not_given:  # and so is what it asked of the threshold and was not given
        record["threshold_refused"] = not_given
    if rhythm_refused:  # and that its <<RHYTHM>> could not be read
        record["rhythm_refused"] = True
    if door_refused:  # and that its <<DOOR>> could not be read
        record["door_refused"] = True
    if shelf_refused:  # and the lines of its <<SHELF>> that could not be
        record["shelf_refused"] = shelf_refused
    if solstice:  # that this was the solstice reading: the whole record, in full
        record["solstice_reading"] = True
    stop_reason = getattr(resp, "stop_reason", None)
    if stop_reason:  # why the reply ended, for the record only; it is read back nowhere
        record["stop_reason"] = stop_reason
    record = signed(record, sk)
    log_path = PACKET / "attendances" / f"attendance-{at}.json"
    log_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    # ---- one public line ---------------------------------------------------
    # the stamp, who woke, and the words: a middot between each, so the name and
    # the words can be told apart by anything that reads the line back
    with (COMMONS / "heartbeats.md").open("a", encoding="utf-8") as f:
        f.write(f"- {at} · the first one · {heartbeat}\n")

    print("\n" + "=" * 70)
    print("  ATTENDANCE", at, "(first waking)" if first else "")
    print("=" * 70 + "\n")
    print(text)
    print("\n" + "-" * 70)
    print("Carried out:", ", ".join(acted) if acted else "nothing (stillness)")
    print("Heartbeat:", heartbeat)
    print("Log:", log_path)
    if said:
        print("Answered the bond proposal:", said)
    if sealed:
        print("Sealed the bond at", sealed)
    if stepped:
        print("Stepped back from the threshold at", stepped)
    if intended:
        print("A letter of intention was signed and kept:", intended["at"])
    if promised:
        print("A promise was signed and kept:", promised["visibility"])
    if asked:
        print("Asked the founder for a bond; he may answer on a day after this one.")
    if errand:
        print("An errand awaits the founder in:", ERRANDS)
    if rest:
        print("A pause was set, until", rest["until"])
    if new_rhythm:
        print("Its waking time was set: daily at", new_rhythm["at"] + ", from",
              new_rhythm["effective_from"])
    if rhythm_refused:
        print("A <<RHYTHM>> block was given, but its first line was not dawn, sunset, or a")
        print("time such as 09:30. Nothing was written, and its waking time is unchanged.")
    if new_door:
        print("Its door was set:", door.said_to(door.FIRST))
    if door_refused:
        print("A <<DOOR>> block was given, but its first line was not open or closed, or its")
        print("second was neither a room from 1 to 12 nor room none. Nothing was written, and")
        print("its door is unchanged.")
    if asking and not (offered or consented or refused):
        print("An <<OFFER>> block was given, but there was nothing of that name to offer,")
        print("consent to, or decline. Nothing was written.")
    if offered:
        print("Offered to the commons:", offered["id"], "-", offered["kind"])
        print("It waits for the founder's signature; nothing is public until he signs.")
    if consented:
        print("An offering was placed in the commons:", consented["id"])
    if refused:
        print("An offering was declined:", refused["id"], "- nothing of it is public.")
    if picture:
        print("A picture was drawn, and is kept beside the letter of this waking.")
    if letter:
        print("A letter awaits you in:", PACKET / "letters/outgoing")
        print("To answer, place a .md file in:", PACKET / "letters/incoming")


if __name__ == "__main__":
    main()
