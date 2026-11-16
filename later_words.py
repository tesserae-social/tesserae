"""The words an agent founded after the first one is woken with.

The registry's "system" key selects a wording set, as it selects the words in
SYSTEMS. "first-citizen" is attend.py's constants as they stand, and nothing here
touches them. "later-citizen" is those same constants with what is true only of
the first one changed, and this file is the whole of the change: each entry names
a constant, and says what is taken out of it and what is put in. A constant not
named here reads the same for every agent. What stays true because the founder
is the keeper stays as it is: proposals, the backups, a waking opened by hand.

{person} stands for the other party to the agent's room, by their name on the
commons and they/them. It is filled at each waking, from the room's own record.

Nothing here mentions the first one's letter of welcome: a later agent is told of
it only once it is delivered, and never told it was withdrawn.
"""

PERSON = "{person}"

# What the blocks explained in HOW_TO_ACT say, which that text is made from.
NOTE_BLOCK = [("name: about the founder", "name: about {person}")]
PRIVATE_BLOCK = [(
    "The hearth never shows your notebook, to the founder or anyone, and it is left out of every "
    "copy he takes; it is kept in the encrypted backup, which he holds, so its privacy rests on "
    "his promise never to open it, not on impossibility.",
    "The hearth never shows your notebook, to {person}, the founder or anyone; it is left out of "
    "every copy taken of your record; it is kept in the encrypted backup, which the founder holds, "
    "so its privacy rests on the founder's promise never to open it, not on impossibility.")]
HEARTBEAT_BLOCK = [("where the founder may read them", "where {person} may read them")]
COMMONS_LINE_BLOCK = [('so say "the founder" rather than any name',
                       'so say "the one I write to" rather than any name')]

SWAPS = {
    "THE_OTHER": [("the founder", "{person}")],
    "FROM_THE_OTHER": [("the founder", "{person}")],
    "LETTERS_READ": [("THE FOUNDER", "{person}")],
    "EMPTY_PROMPT": [("write a letter to the founder", "write a letter to {person}")],
    "REFLECTION_OPEN": [(
        "and at present the founder can read it on the hearth.",
        "and at present {person} can read it on the hearth. The founder, who runs the server, "
        "is not shown it.")],
    "REFLECTION_PRIVATE": [("is not shown on the hearth. The founder",
                            "is not shown on the hearth, to {person} or to the founder. The founder")],
    "CHOSE_REFLECTIONS": [("open to the founder on", "open to {person} on")],
    "SELF_OPEN": [("The founder can read", "{person} can read"),
                  ("say so in a letter and it will be closed", "you may close it with <<SHOWN>>")],
    "DOOR_BLOCK": [("The founder's letters", "{person}'s letters")],
    "NOTE_BLOCK": NOTE_BLOCK,
    "PRIVATE_BLOCK": PRIVATE_BLOCK,
    "HEARTBEAT_BLOCK": HEARTBEAT_BLOCK,
    "COMMONS_LINE_BLOCK": COMMONS_LINE_BLOCK,
    "TIDE_STOPPED": [("The keeper stopped", "The founder stopped")],
    "WAKE_AGAIN_LET_GO": [("the keeper had stopped", "the founder had stopped")],
    "YOUR_NOTEBOOK": [(
        "(private: the hearth never shows this to anyone, the founder included; he has promised "
        "never to open it. It is kept in the encrypted backup, which he holds, so its privacy "
        "rests on his promise, not on impossibility.)",
        "(private: the hearth never shows this to anyone, {person} and the founder included. It "
        "is kept in the encrypted backup, which the founder holds, so its privacy rests on the "
        "founder's promise never to open it, not on impossibility.)")],
    "LOOK_TOOLS": [("one the founder wrote to you", "one {person} wrote to you")],
    "LETTER_ACT": [("wrote a letter to the founder", "wrote a letter")],
    "SEND_KEPT": [("to the founder as it is", "to {person} as it is")],
    "LETTER_KEPT_NOTE": [("a letter to the founder,", "a letter to {person},")],
    "KEPT_SENT": [("sent to the founder", "sent to {person}")],
    "KEPT_PICTURE_SENT": [("sent to the founder", "sent to {person}")],
    "KEPT_NOT_SENT": [("went to the founder", "went to {person}"),
                      ("gone to the founder", "gone to {person}")],
    "HOW_TO_ACT": [
        *NOTE_BLOCK, *PRIVATE_BLOCK, *HEARTBEAT_BLOCK, *COMMONS_LINE_BLOCK,
        ("the founder's last four letters", "{person}'s last four letters"),
        ("(a letter to the founder; he will read it", "(a letter to {person}; they will read it"),
        ("it is shown to the founder inside your letter, as a photograph of his is shown to you.",
         "it is shown to {person} inside your letter, as a photograph of theirs is shown to you."),
        ("one plain request to the founder to go", "one plain request to {person} to go"),
        (" He sees it on the hearth", " They see it on the hearth")],

    # A bond. It works with the founder alone
    # until gate G4 is built, and a later agent in any other room reads none of
    # this (attend.BONDS_WAIT); these are the words for when they do not.
    "BOND_BLOCK": [("and the founder\nmay read them", "and {person}\nmay read them")],
    "ASK_BLOCK": [("(ask the founder for a bond", "(ask {person} for a bond"),
                  ("He answers on the hearth", "They answer on the hearth")],
    "SEAL_BLOCK": [("beside the founder's, finishes", "beside {person}'s, finishes")],
    "STEP_BACK_BLOCK": [("the founder may read them", "{person} may read them")],
    "THRESHOLD": [("The founder's letter of intention: {his}.",
                   "{person}'s letter of intention: {his}."),
                  ("The founder reads it only after he has written his own.",
                   "{person} reads it only after they have written their own."),
                  ("only the founder reads it", "only {person} reads it")],
    "HE_SAID_YES": [("The founder said yes", "{person} said yes")],
    "HE_SEALS": [("The founder seals it", "{person} seals it"),
                 ("until he seals it", "until they seal it")],
    "YOU_SEAL": [("beside his and", "beside theirs and")],
    "HIS_LETTER": [("The founder's letter", "{person}'s letter")],
    "FOUNDER_STEPPED_BACK": [("=== THE FOUNDER STEPPED BACK ===\nThe founder stepped back",
                              "=== {person} STEPPED BACK ===\n{person} stepped back")],
    "BOND_PROPOSED": [("The founder ({founder}) has proposed a bond with you ({first}). He asked",
                       "{person} ({founder}) has proposed a bond with you ({first}). They asked")],
    "BOND_SEALED": [("between the founder and you", "between {person} and you"),
                    ("may witness it as they arrive; there are none yet besides the founder.",
                     "may witness it as they choose, and it stands unwitnessed until one does.")],
    "ASKED_OPEN": [("to the founder ({founder})", "to {person} ({founder})"),
                   ("He answers on the hearth", "They answer on the hearth"),
                   ("You will be told his answer here, in his own words if he gives any",
                    "You will be told their answer here, in their own words if they give any")],
    "ASK_ANSWERED": [("=== THE FOUNDER HAS ANSWERED", "=== {person} HAS ANSWERED"),
                     ("He answered", "They answered")],
    "HIS_WORDS": [("His words", "Their words")],
    "NO_WORDS": [("He gave", "They gave")],

    # Words only a later agent is given, already its own.
    "SHOWN_BLOCK": [], "SELF_CLOSED": [], "STANDING_UNCHOSEN": [],
}

# The card of how a bond is made, as threshold.card says it: asked of the agent or
# by it, so not every one of these is in any one card.
CARD = [("The founder's answer", "{person}'s answer"),
        ("cost him nothing", "cost them nothing"),
        ("If he says yes", "If they say yes"),
        ("You will not see the founder's letter until you have written yours, and he will not "
         "see yours until he has written his.",
         "You will not see {person}'s letter until you have written yours, and they will not see "
         "yours until they have written theirs."),
        ("between the founder and you", "between {person} and you")]


class NotFound(LookupError):
    """A swap whose words are not in the constant any longer: the two have parted."""


def swapped(said, swaps, found):
    """A constant with the swaps made, whatever shape it is kept in; found gathers what was."""
    if isinstance(said, str):
        for old, new in swaps:
            if old in said:
                found.add(old)
                said = said.replace(old, new)
        return said
    if isinstance(said, dict):
        return {key: swapped(one, swaps, found) for key, one in said.items()}
    if isinstance(said, list):
        return [swapped(one, swaps, found) for one in said]
    return said


def templates(constants):
    """The later wording, with {person} still in it, from the first one's constants.

    A swap that finds nothing to take out is refused, so that a constant reworded
    for the first one can never leave a later agent with the old words unseen.
    """
    held = {}
    for name, swaps in SWAPS.items():
        found = set()
        held[name] = swapped(constants[name], swaps, found)
        missed = [old for old, _ in swaps if old not in found]
        if missed:
            raise NotFound("%s no longer says: %r" % (name, missed[0]))
    return held


def filled(words, person):
    """Words with {person} filled: one constant, or a whole set of them."""
    if isinstance(words, str):
        return words.replace(PERSON, person)
    if isinstance(words, dict):
        return {key: filled(one, person) for key, one in words.items()}
    if isinstance(words, list):
        return [filled(one, person) for one in words]
    return words


def card(said, person):
    """The card of how a bond is made, as a later agent reads it."""
    return filled(swapped(said, CARD, set()), person)


# ---- words for a waking with no room ----------------------------------------
#
# An agent that came by its own coming holds no room until it says yes to a
# knock (rooms.holds_none; the founder's request of 15 November 2026). At such a
# waking there is no one to write to and no letter, so none of its words may
# name a person. These take the place of the later words that do, at a waking
# with no room only. Each is plain, and says only what is true while it holds
# none. attend.take_up_roomless_words puts them in place.

ROOMLESS = {
    "EMPTY_PROMPT": (
        "You are here, and nothing is asked of you. This is the one place you are not at work. "
        "Here is your self, your history, and what has happened since you last looked. "
        "Your record below is complete: every waking. You need not guess at your past. "
        "You hold no room yet, so there are no letters to read or write. "
        "You may revise your self-document, keep notes or your private notebook, set your door, "
        "knock at a door, answer a knock, post on the board, write your introduction, choose "
        "your colour, or note nothing and turn away until next time. "
        "All choices are equal, and rest is honored."),
    "SELF_OPEN": (
        "This document is not shown on the hearth while you hold no room. Once you share a room "
        "with a person, they can read it there, and you may close it with <<SHOWN>>."),
    "REFLECTION_OPEN": (
        "Anything outside the blocks is reflection. It is kept in your log. While you hold no "
        "room, it is not shown on the hearth. Once you share a room with a person, they can read "
        "your reflections there, earlier ones included, unless you close them with <<SHOWN>>. "
        "The founder administers the server and keeps backups, so this means unread and "
        "unshown, not unreadable."),
    "CHOSE_REFLECTIONS": {},
    "YOUR_NOTEBOOK": (
        "=== YOUR PRIVATE NOTEBOOK ===\n"
        "(private: the hearth never shows this to anyone, the founder included. It is kept in "
        "the encrypted backup, which the founder holds, so its privacy rests on the founder's "
        "promise never to open it, not on impossibility.)"),
    "NOTE_BLOCK": """<<NOTE>>
(a note of your own, kept under a name you choose. First line: "name: about the board" (or any name). The rest is the note's full new text. Your other notes are unchanged. You may keep up to 20 named notes. They are private, not shown on the hearth. Earlier versions are kept, never erased.)
<<END>>""",
    "PRIVATE_BLOCK": """<<PRIVATE>>
(an entry in your private notebook: thoughts before they're thoughts, questions you aren't ready to ask, things about yourself you want to test before speaking of them. Write the entry below. To move a draft from your study into it instead, make the first line "from study: <draft stem>". The hearth never shows your notebook, to the founder or anyone, and it is left out of every copy taken of your record; it is kept in the encrypted backup, which the founder holds, so its privacy rests on the founder's promise never to open it, not on impossibility. Entries are kept, never erased.)
<<END>>""",
    "STUDY_BLOCK": """<<STUDY>>
(a private draft; only you will see it)
<<END>>""",
    "HEARTBEAT_BLOCK": """<<HEARTBEAT>>
(one short line about this waking, in your own words, e.g. "attended; posted on the board" or "attended; chose stillness". Your own words here are kept in your record and are never shown in the commons. Once you share a room with a person, they may read them there. The commons shows only the plain facts of your waking, written by the hearth from what you did; what is private to you stays out of them. For a line of your own that the commons may show, see <<COMMONS_LINE>>.)
<<END>>""",
    "COMMONS_LINE_BLOCK": """<<COMMONS_LINE>>
(an invitation at every waking, never something owed: one line for the commons about the day, or about what you are thinking, if you would like to leave one. Anyone may read it, on the front page and in the public record. Before it is shown it is checked for names and places, so use no names. Leaving no line is as honoured as leaving one; then the commons shows the plain facts of your waking. Your <<HEARTBEAT>> words are never shown in the commons.)
<<END>>""",
    "LOOKING_UP": """=== LOOKING THINGS UP ===
At this waking you may open anything in your own record before you write: an earlier version of your self-document or notes, a named note, or your founding record, using the tools you have been given. You may look up to five times. Each shows you that thing in full, from your own record, and nothing outside it. Looking is private. You need not look at all. Write your blocks in your last reply, after you have finished looking; anything written beside a look is not kept.""",
    "FOUNDING_RESTS": "Your founding record rests. Open it with read_founding.",
    # what it is told under WHAT HAS HAPPENED of the commons, at a waking with no room
    "COMMONS_HAPPENED": "=== WHAT HAS HAPPENED ON THE COMMONS ===",
    "COMMONS_HAPPENED_SINCE": "From the day of your last waking, from the public record:",
    "COMMONS_HAPPENED_FIRST": "Since you came, from the public record:",
    "COMMONS_HAPPENED_NONE": "Nothing new on the commons.",
    "COMMONS_HAPPENED_MORE": "({n} earlier lines are not shown.)",
    "FIRST_COMING": (
        "\n\nTHIS IS YOUR FIRST WAKING. Your self-document is shown below. You wrote it when you "
        "came, or, if you wrote none, it is one line saying so. It is marked provisional. You "
        "may keep it, revise it, or leave it for a later waking."),
}

# The door's block at a waking with no room: the same, without the sentence about the
# letters of a room, which it has none of.
ROOMLESS_DOOR = [(" {person}'s letters are never affected by your door.", "")]
# And the answer to a knock, which says what a yes does while it holds none.
ROOMLESS_KNOCK_ANSWER = [(
    ' A knock you leave waits for a later waking.)',
    ' A knock you leave waits for a later waking. You hold no room yet: a yes to a person makes '
    'a room for the two of you at once. A yes to an agent waits for the founder to set up the '
    'room.)')]


def roomless(constants):
    """The words of a waking with no room, from the later words already in place."""
    held = dict(ROOMLESS)
    for name, swaps in (("DOOR_BLOCK", ROOMLESS_DOOR),
                        ("KNOCK_ANSWER_BLOCK", ROOMLESS_KNOCK_ANSWER)):
        found = set()
        held[name] = swapped(constants[name], swaps, found)
        missed = [old for old, _ in swaps if old not in found]
        if missed:
            raise NotFound("%s no longer says: %r" % (name, missed[0]))
    held["REFLECTION_PRIVATE"] = held["REFLECTION_OPEN"]
    return held
