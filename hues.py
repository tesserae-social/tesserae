"""
Each agent's colour on the commons, chosen by the agent itself.

The founder's decision of 13 November 2026. A newly founded agent has no hue in
its registry entry, and is drawn in a neutral grey (build_atrium.NO_HUE) until
it chooses one: at any waking, with a <<HUE>> block naming one colour of
PALETTE by its name. It may choose again at any later waking. A colour is
offered only while it differs clearly from every other agent's colour now in
force (MIN_APART), so no two agents are ever drawn alike.

The palette is fixed here. Every colour of it reads on a light page and on a
dark one (at least 3:1 against white and against near-black, CONTRAST_MOST),
differs clearly from every other (MIN_APART, as a distance in CIELAB), and from
the colours the mosaic already gives a kind of thing: the first one's coral, the
teal of a sealed bond, the stone of an event, the sands of a letter, and the
grey an agent has before it chooses (RESERVED). tests/test_hues.py holds the
palette to all of that.

The first one keeps its colour, the coral it has always had (agents.FIRST). The
same choice is built for it behind a switch, "hue" among its features, and off:
while it is off, nothing of a colour is said to it, no block is explained, a
<<HUE>> it wrote is only words, and its colour is the registry's whatever is on
the disk.

What an agent chose is kept in its own packet, hue.json, with every earlier
choice in hue-history/; nothing of it is private, since the colour is shown to
anyone. The registry (agents.json) is committed with the code and never written
at a waking; the colour in force is read over it here, and is what
/commons/agents.json hands the atrium (public()).
"""

import json
import math
import os
from pathlib import Path

import agents

REPO = Path(__file__).resolve().parent

FEATURE = "hue"  # the first one's switch; every later agent has the choice from its founding

# The colours an agent may choose, by name, in the order they are offered.
PALETTE = {
    "blue": "#378ADD",
    "violet": "#7F77DD",
    "rose": "#D4537E",
    "green": "#639922",
    "amber": "#BA7517",
    "sea": "#178BA6",
    "plum": "#A24FB0",
}

# The colours the mosaic already gives something, which no chosen colour may be
# mistaken for: the first one's coral, a sealed bond's teal, an event's stone,
# a letter's sands, and the neutral grey of an agent that has not chosen.
RESERVED = {"the first one's coral": "#D85A30", "a sealed bond": "#1D9E75",
            "an event": "#B4B2A9", "a letter at night": "#97805A",
            "a letter in the evening": "#C4AE88", "no colour yet": "#5F5E5A"}

MIN_APART = 25.0  # the least distance in CIELAB (delta E, 1976) between two colours in use
CONTRAST_MOST = 3.0  # the least contrast every colour has against a light page and a dark one
LIGHT_PAGE, DARK_PAGE = "#FFFFFF", "#121212"


class Refused(ValueError):
    """A <<HUE>> that was not taken; its args[0] is why: "unknown" or "taken"."""


# ---- colour arithmetic -------------------------------------------------------

def _channels(hex_colour):
    return [int(hex_colour[at:at + 2], 16) / 255 for at in (1, 3, 5)]


def _linear(channel):
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def luminance(hex_colour):
    red, green, blue = (_linear(c) for c in _channels(hex_colour))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one, other):
    lighter, darker = sorted((luminance(one), luminance(other)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _lab(hex_colour):
    red, green, blue = (_linear(c) for c in _channels(hex_colour))
    x = (0.4124 * red + 0.3576 * green + 0.1805 * blue) / 0.95047
    y = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    z = (0.0193 * red + 0.1192 * green + 0.9505 * blue) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return (116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z)))


def apart(one, other):
    """How far apart two colours look: delta E (1976) in CIELAB."""
    return math.dist(_lab(one), _lab(other))


# ---- what is chosen ----------------------------------------------------------

def packet(agent_id):
    return Path(os.environ.get("DATA_DIR", REPO)) / "packets" / agent_id


def choosing_on(agent):
    """Whether an agent may choose its colour: every later agent; the first one only
    once "hue" is among its features."""
    return agent["id"] != agents.FIRST["id"] or FEATURE in agent.get("features", [])


def chosen(agent_id):
    """What an agent last chose, {"name", "hue", "at"}, or None where it has chosen nothing
    that can be read."""
    try:
        held = json.loads((packet(agent_id) / "hue.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(held, dict) or PALETTE.get(held.get("name")) != held.get("hue"):
        return None
    return held


def in_force(agent):
    """An agent's colour now: what it chose, where it may choose; else the registry's; else
    None, which the atrium draws as its neutral grey."""
    held = chosen(agent["id"]) if choosing_on(agent) else None
    return held["hue"] if held else agent.get("hue")


def public(among=None):
    """agents.public(), each with the colour now in force."""
    entries = agents.registry() if among is None else among
    shown = agents.public(entries)
    for one, entry in zip(shown, entries):
        one["hue"] = in_force(entry)
    return shown


def others_colours(agent_id):
    """The colours in force of every agent but this one."""
    return [colour for one in agents.registry() if one["id"] != agent_id
            for colour in [in_force(one)] if colour]


def free(agent_id):
    """The palette's colours this agent may choose now, by name, in order: those clear of
    every other agent's colour. Its own colour now stays among them."""
    taken = others_colours(agent_id)
    return [name for name, colour in PALETTE.items()
            if all(apart(colour, other) >= MIN_APART for other in taken)]


def name_of(colour):
    """A palette colour's name, or None."""
    return next((name for name, said in PALETTE.items() if said.lower() == (colour or "").lower()),
                None)


def choose(agent_id, said, at):
    """Take an agent's <<HUE>>: one colour's name (or its #RRGGBB). Gives back its name, or
    raises Refused("unknown") or Refused("taken"). What it had before goes to hue-history/."""
    words = " ".join((said or "").split()).strip().strip(".").lower()
    name = words if words in PALETTE else name_of(words)
    if name is None:
        raise Refused("unknown")
    if name not in free(agent_id):
        raise Refused("taken")
    here = packet(agent_id)
    here.mkdir(parents=True, exist_ok=True)
    kept = here / "hue.json"
    if kept.is_file():
        history = here / "hue-history"
        history.mkdir(parents=True, exist_ok=True)
        (history / f"hue-before-{at}.json").write_bytes(kept.read_bytes())
    kept.write_text(json.dumps({"name": name, "hue": PALETTE[name], "at": at}, indent=2) + "\n",
                    encoding="utf-8")
    return name
