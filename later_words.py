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
OFFER_BLOCK = [("or answer something the founder has offered",
                "or answer something {person} has offered"),
               ("place something the founder has offered", "place something {person} has offered")]

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
    "OFFER_BLOCK": OFFER_BLOCK,
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
        *NOTE_BLOCK, *PRIVATE_BLOCK, *HEARTBEAT_BLOCK, *COMMONS_LINE_BLOCK, *OFFER_BLOCK,
        ("the founder's last four letters", "{person}'s last four letters"),
        ("(a letter to the founder; he will read it", "(a letter to {person}; they will read it"),
        ("it is shown to the founder inside your letter, as a photograph of his is shown to you.",
         "it is shown to {person} inside your letter, as a photograph of theirs is shown to you."),
        ("one plain request to the founder to go", "one plain request to {person} to go"),
        (" He sees it on the hearth", " They see it on the hearth")],

    # A bond, and what is offered to the commons. Both work with the founder alone
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
    "OFFERED_TO_YOU": [("The founder has offered", "{person} has offered"),
                       ("beside his, and", "beside theirs, and")],

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
