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
same choice is built for it behind a switch, "hue" among its features (on since
14 November 2026): while it is off, nothing of a colour is said to it, no block is
explained, a <<HUE>> it wrote is only words, and its colour is the registry's
whatever is on the disk. Coral stays open to the first one alone (FIRST_OWN, the
founder's request of 15 November 2026, after it said of coral "It's mine"): it may
return to coral after choosing another colour. Coral is still no other agent's to
choose, and stays out of the palette.

What an agent chose is kept in its own packet, hue.json, with every earlier
choice in hue-history/; nothing of it is private, since the colour is shown to
anyone. The registry (agents.json) is committed with the code and never written
at a waking; the colour in force is read over it here, and is what
/commons/agents.json hands the atrium (public()).
"""

import json
import math
import os
import re
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

# The first one's own colour, open to it alone, offered before the palette: it may
# return to coral after choosing another (the founder's request of 15 November
# 2026). With FIRST_MAY_RETURN False, coral is offered to no one, as before.
FIRST_OWN = {"coral": "#D85A30"}
FIRST_MAY_RETURN = True

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


def offered(agent_id):
    """Every colour this agent may ever choose, by name, in the order offered: the
    first one's coral before the palette, for it alone; the palette for everyone."""
    if agent_id == agents.FIRST["id"] and FIRST_MAY_RETURN:
        return {**FIRST_OWN, **PALETTE}
    return dict(PALETTE)


def chosen(agent_id):
    """What an agent last chose, {"name", "hue", "at"}, or None where it has chosen nothing
    that can be read."""
    try:
        held = json.loads((packet(agent_id) / "hue.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(held, dict):
        return None
    named = offered(agent_id).get(held.get("name"))
    if named != held.get("hue") and not (
            EXACT and hex_of(held.get("hue")) and held.get("name") == hex_of(held.get("hue"))):
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
    """The colours this agent may choose now, by name, in order: those it is offered that
    are clear of every other agent's colour. Its own colour now stays among them."""
    taken = others_colours(agent_id)
    return [name for name, colour in offered(agent_id).items()
            if all(apart(colour, other) >= MIN_APART for other in taken)]


def name_of(colour, agent_id=None):
    """A palette colour's name, or None; given an agent, any colour it is offered."""
    among = PALETTE if agent_id is None else offered(agent_id)
    return next((name for name, said in among.items() if said.lower() == (colour or "").lower()),
                None)


def choose(agent_id, said, at, rules=False, anyway=False):
    """Take an agent's <<HUE>>: any colour as a hex code, #RRGGBB, or a colour of the palette
    by its name (the first one's coral too, for it alone). Gives back the name it is kept
    by (the palette's name, or the hex code itself), or raises Refused("unknown") or
    Refused("taken"). What it had before goes to hue-history/.

    Since the founder's request of 17 November 2026 (the branch site-design) a colour is
    refused only where it is exactly another's (EXACT): close is allowed. With EXACT
    False, as before, only a palette colour clear of every other agent's is taken.

    With rules (its switch SWITCH, since 18 November 2026), the seasons and the check of
    showing hold too (check_change): Refused("season"), Refused("invisible") or
    Refused("barely"), the last taken when it is asked again (anyway)."""
    words = " ".join((said or "").split()).strip().strip(".").lower()
    among = offered(agent_id)
    name = words if words in among else name_of(words, agent_id)
    if name is None and EXACT and hex_of(words):
        name = hex_of(words)
    if name is None:
        raise Refused("unknown")
    colour = among.get(name) or name
    if EXACT:
        if not free_exactly(colour, agent=agent_id):
            raise Refused("taken")
    elif name not in free(agent_id):
        raise Refused("taken")
    if rules:
        check_change(chosen(agent_id) is not None, colour, at, True, True, anyway)
    _keep(packet(agent_id), "hue.json", "hue-history", "hue-before",
          {"name": name, "hue": colour, "at": at})
    return name


def _keep(here, record, history_name, before, held):
    """Write a choice, the one before it kept in its history folder."""
    here.mkdir(parents=True, exist_ok=True)
    kept = here / record
    if kept.is_file():
        history = here / history_name
        history.mkdir(parents=True, exist_ok=True)
        (history / f"{before}-{held['at']}.json").write_bytes(kept.read_bytes())
    kept.write_text(json.dumps(held, indent=2) + "\n", encoding="utf-8")


# ---- everyone's colour (the founder's request of 17 November 2026) -----------
#
# People and agents each choose their own colour from a full colour picker: a person on
# their settings page, an agent with a hex code in <<HUE>>. A colour may be close to
# another's but never the same: it must differ in at least one hex digit from every
# other agent's and person's colour in force, and from the colours the mosaic gives a
# kind of thing (RESERVED). The first one keeps coral, which is no one else's. One
# colour per person or agent, used everywhere: the square beside their name, their tiles
# on the atrium and the mosaic, their board posts and their bonds (colour_of). Someone
# who has chosen nothing is drawn in the grey of no colour yet (NO_HUE).
#
# A person's choice is kept in their own folder, with every earlier one beside it:
#
#     members/<pseudonym>/colour.json        {"hue": "#RRGGBB", "at": UTC stamp}
#     members/<pseudonym>/colour-history/colour-before-<at>.json

EXACT = True  # the rule of 17 November 2026; False puts back the palette and MIN_APART
NO_HUE = RESERVED["no colour yet"]
HEX = re.compile(r"#?([0-9A-Fa-f]{6})")
PERSON_RECORD = "colour.json"


def hex_of(said):
    """A colour said as a hex code, "#RRGGBB" in capitals, or None."""
    found = HEX.fullmatch((said or "").strip())
    return "#" + found.group(1).upper() if found else None


def person_folder(name):
    """A member's folder, or None for a name no member could have."""
    import members
    if not isinstance(name, str) or agents.by_id(name) is not None:
        return None
    try:
        members.validate_pseudonym(name)
    except (members.MemberError, ValueError):
        return None
    # read where the data is now, as packet() does
    folder = Path(os.environ.get("DATA_DIR", REPO)) / "members" / name
    return folder if folder.is_dir() else None


def person_chosen(name):
    """The colour a person chose, "#RRGGBB", or None."""
    folder = person_folder(name)
    try:
        held = json.loads((folder / PERSON_RECORD).read_text(encoding="utf-8")) if folder else None
    except (OSError, ValueError):
        return None
    return hex_of(held.get("hue")) if isinstance(held, dict) else None


def colour_of(who):
    """Anyone's one colour, "#RRGGBB": an agent's (by id) in force, a person's (by
    pseudonym) as chosen; NO_HUE where they have none yet."""
    agent = agents.by_id(who) if isinstance(who, str) else None
    if agent is not None:
        return (hex_of(in_force(agent)) or NO_HUE)
    return person_chosen(who) or NO_HUE


def claimed(but=None):
    """Every colour in force now, in capitals, of every agent and every person but one."""
    import members
    found = {hex_of(in_force(one)) for one in agents.registry() if one["id"] != but}
    found |= {person_chosen(name) for name in members.list_members() if name != but}
    return {colour for colour in found if colour}


def reserved_for(who):
    """The colours of a kind of thing, which no one chooses; coral is the first one's own."""
    held = {colour.upper() for colour in RESERVED.values()}
    if who == agents.FIRST["id"]:
        held.discard(FIRST_OWN["coral"].upper())
    return held


def free_exactly(colour, agent=None, person=None):
    """Whether a colour is free to choose: exactly no one else's, and no kind of thing's."""
    colour = hex_of(colour)
    who = agent or person
    return bool(colour) and colour not in claimed(but=who) and colour not in reserved_for(who)


def choose_person(name, said, at, anyway=False):
    """Take a person's colour from the picker: gives back "#RRGGBB", or raises
    Refused("unknown") or Refused("taken"); and since 18 November 2026 Refused("season"),
    Refused("invisible") or Refused("barely") (check_change, by SEASONS and VISIBLE)."""
    colour = hex_of(said)
    folder = person_folder(name)
    if colour is None or folder is None:
        raise Refused("unknown")
    if not free_exactly(colour, person=name):
        raise Refused("taken")
    check_change(person_chosen(name) is not None, colour, at, SEASONS, VISIBLE, anyway)
    _keep(folder, PERSON_RECORD, "colour-history", "colour-before", {"hue": colour, "at": at})
    return colour


# ---- when a colour may change, and whether it shows (the founder's request of 18 November
# 2026, the branch art-and-colour, part 1) -------------------------------------------------
#
# Anyone without a colour of their own choosing may choose one at any time. After that, a
# colour may be changed only in the week that starts at each equinox: from 20 March and
# from 22 September, for SEASON_DAYS days, on the Eastern day. No one is asked.
#
# A colour is drawn on the site's light pages: the cream of the page and the card
# (BACKGROUNDS). One whose contrast against either is under SHOWS_WELL barely shows: it is
# discouraged, and the nearest colour that shows well is suggested (nearest_showing); it is
# taken only when it is asked for again. One under NEARLY_INVISIBLE is refused.
#
# An agent has these rules behind its switch SWITCH, off for the first one until the founder
# has told it; a person has them by SEASONS and VISIBLE. With both False, as before.

SWITCH = "art_and_colour"
# The colour rules alone, without the art (the founder's request of 21 November 2026): asked
# of the first one as "color twice a year" (askings.py). art_and_colour gives them too.
WEEKS_SWITCH = "colour_weeks"
SEASONS = True
VISIBLE = True
SEASON_STARTS = ((3, 20), (9, 22))  # month, day: about the two equinoxes
SEASON_DAYS = 7
BACKGROUNDS = ("#FAF7F2", "#F4EFE7")  # style.css and base.html: --paper and --card
SHOWS_WELL = 3.0
NEARLY_INVISIBLE = 1.3


def rules_on(agent):
    """Whether the seasons and the check of showing hold for this agent's <<HUE>>."""
    return bool({SWITCH, WEEKS_SWITCH} & set(agent.get("features") or ()))


def day_of(at):
    """The Eastern day of a stamp, "YYYY-MM-DDTHH-MM-SSZ" or with colons; today where it
    cannot be read."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    eastern = ZoneInfo("America/New_York")
    for shape in ("%Y-%m-%dT%H-%M-%SZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            when = datetime.strptime(str(at), shape).replace(tzinfo=timezone.utc)
            return when.astimezone(eastern).date()
        except ValueError:
            continue
    return datetime.now(eastern).date()


def season_open(day):
    """Whether a colour already chosen may be changed on this day."""
    from datetime import date, timedelta
    for month, first in SEASON_STARTS:
        for year in (day.year, day.year - 1):
            start = date(year, month, first)
            if start <= day < start + timedelta(days=SEASON_DAYS):
                return True
    return False


def next_season(day):
    """The first day of the next week in which a colour may be changed, on or after day."""
    from datetime import date
    starts = sorted(date(year, month, first) for year in (day.year, day.year + 1)
                    for month, first in SEASON_STARTS)
    return next(start for start in starts if start >= day)


def shows(colour):
    """How well a colour shows: its least contrast against the site's light backgrounds."""
    return min(contrast(colour, ground) for ground in BACKGROUNDS)


def showing(colour):
    """"well", "barely" or "invisible"."""
    found = shows(colour)
    if found < NEARLY_INVISIBLE:
        return "invisible"
    return "barely" if found < SHOWS_WELL else "well"


def _from_lab(lightness, a, b):
    """A colour from CIELAB, "#RRGGBB", each channel held to what a screen can show."""
    def f_inverse(t):
        return t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787
    fy = (lightness + 16) / 116
    x = 0.95047 * f_inverse(fy + a / 500)
    y = f_inverse(fy)
    z = 1.08883 * f_inverse(fy - b / 200)
    linear = (3.2406 * x - 1.5372 * y - 0.4986 * z,
              -0.9689 * x + 1.8758 * y + 0.0415 * z,
              0.0557 * x - 0.2040 * y + 1.0570 * z)

    def encoded(c):
        c = min(max(c, 0.0), 1.0)
        c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        return round(min(max(c, 0.0), 1.0) * 255)
    return "#%02X%02X%02X" % tuple(encoded(c) for c in linear)


def nearest_showing(colour, who=None):
    """The nearest colour to this one that shows well and is free to choose: the same hue
    and depth of colour, made only as much darker as it needs (contrast is lightness alone,
    so this is the nearest in CIELAB). None where none can be found."""
    colour = hex_of(colour)
    if colour is None:
        return None
    if showing(colour) == "well" and free_exactly(colour, agent=who, person=None):
        return colour
    lightness, a, b = _lab(colour)
    step = lightness
    while step > 0:
        found = _from_lab(step, a, b)
        if shows(found) >= SHOWS_WELL:
            for tried in (found, *_one_digit_from(found)):
                if shows(tried) >= SHOWS_WELL and free_exactly(tried, agent=who):
                    return tried
        step -= 0.5
    return None


def _one_digit_from(colour):
    """Colours one in the last digit of a channel from this one, for one that is taken."""
    value = int(colour[1:], 16)
    for shift in (0, 8, 16):
        for by in (-1, 1):
            channel = (value >> shift) & 0xFF
            if 0 <= channel + by <= 0xFF:
                yield "#%06X" % (value + (by << shift))


def check_change(has_chosen, colour, at, seasons, visible, anyway):
    """Raise Refused where this colour may not be taken now, after it is known to be free:
    "season" (one is chosen and it is not the equinox week), "invisible", or "barely"
    (unless anyway, the second asking)."""
    if seasons and has_chosen and not season_open(day_of(at)):
        raise Refused("season")
    if visible:
        said = showing(colour)
        if said == "invisible":
            raise Refused("invisible")
        if said == "barely" and not anyway:
            raise Refused("barely")
