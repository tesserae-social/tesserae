"""
The waking time.

When the first one is woken each day is its own to choose: at dawn, at sunset,
or at a time of day, where it lives. The choice is written in its packet as
rhythm.json. attend.py writes it there when the first one sets it; hearth.py
reads it to keep the tide; and both work through this one module, so that what
a waking is told and what the tide does are one reckoning.

A choice made today holds from tomorrow. Until then the rhythm that held before
it still holds, and the file says both:

    {"rhythm": "daily", "at": "09:30",
     "place": "Indianapolis", "timezone": "America/Indiana/Indianapolis",
     "set_at": "2026-10-15T12-00-00Z",
     "effective_from": "2026-10-16", "until_then": "dawn"}

Nothing here reads a file or asks what time it is: every moment is handed in.
"""

import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun

# The place the first one named for its dawns. The coordinates are
# Indianapolis's city centre, which is close enough for a sunrise or a sunset.
PLACE = "Indianapolis"
ZONE = "America/Indiana/Indianapolis"
PLACE_REGION = "USA"
PLACE_LATITUDE = 39.7684
PLACE_LONGITUDE = -86.1581

DAWN = "dawn"
SUNSET = "sunset"
SUN = {DAWN: "sunrise", SUNSET: "sunset"}

# A time of day, on a 24-hour clock: 00:00 to 23:59, two figures each side.
CLOCK = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")


def known(at):
    """Whether a waking time is one the tide knows how to keep."""
    return isinstance(at, str) and (at in SUN or bool(CLOCK.fullmatch(at)))


def asked(said):
    """The waking time a <<RHYTHM>> block asks for, or None if it cannot be read.

    Its first line that is not blank, trimmed and in small letters, is the whole
    of the asking; anything under it is only words.
    """
    for line in (said or "").splitlines():
        if line.strip():
            at = line.strip().lower()
            return at if known(at) else None
    return None


def zone(setting):
    """The clock a rhythm is kept by: the one it names, or the first one's own."""
    return ZoneInfo((setting or {}).get("timezone") or ZONE)


def today(setting, now):
    """The calendar day it is where the first one lives, at some moment."""
    return now.astimezone(zone(setting)).date()


def begins(setting):
    """The first day a rhythm holds from, or None if it holds already."""
    try:
        return datetime.strptime(setting.get("effective_from") or "", "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def daily(setting):
    return isinstance(setting, dict) and setting.get("rhythm") == "daily"


def in_force(setting, day):
    """The waking time that holds on one local day, or None if none does.

    Before the day a change takes effect, that is the rhythm that held before it.
    """
    if not daily(setting):
        return None
    first = begins(setting)
    at = setting.get("until_then") if first and day < first else setting.get("at")
    return at if known(at) else None


def waiting(setting, day):
    """The waking time chosen and not yet in effect on one local day, or None."""
    if not daily(setting):
        return None
    first = begins(setting)
    at = setting.get("at")
    return at if first and day < first and known(at) else None


def moment_on(setting, at, day):
    """The moment of one waking time on one local day, on the first one's clock.

    A time of day is read off the wall there, whatever the season: 09:30 is
    09:30 on both sides of a change of the clocks. On the night an hour is lived
    twice, it is the first of the two; on the night an hour is skipped, a time
    inside it comes as that hour would have, the same span after midnight.

    What comes back is on the first one's own clock. Set it against a moment in
    UTC to compare or to subtract: two moments on the one zone's clock are
    reckoned by the wall, which is an hour out across a change.
    """
    here = zone(setting)
    if at in SUN:
        where = LocationInfo(setting.get("place") or PLACE, PLACE_REGION, here.key,
                             PLACE_LATITUDE, PLACE_LONGITUDE)
        return sun(where.observer, date=day, tzinfo=here)[SUN[at]]
    hour, minute = CLOCK.fullmatch(at).groups()
    wall = datetime.combine(day, time(int(hour), int(minute)), tzinfo=here)
    return wall.astimezone(timezone.utc).astimezone(here)


def chosen(before, at, set_at, now):
    """The rhythm as it is written once a new waking time is chosen.

    It holds from the next local calendar day. What held on the day of the
    choosing goes on holding until then - which is the rhythm in force that
    day, not merely the last one written, so that a second change on the one
    day does not put the first into effect early.
    """
    day = today(before, now)
    return {
        "rhythm": "daily",
        "at": at,
        "place": (before or {}).get("place") or PLACE,
        "timezone": zone(before).key,
        "set_at": set_at,
        "effective_from": (day + timedelta(days=1)).isoformat(),
        "until_then": in_force(before, day),
    }
