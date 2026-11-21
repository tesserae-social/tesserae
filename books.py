"""
The books: what this place costs, one total a month, open to anyone.

The charter says "We show our books", and the white paper "every dollar
published in the books". This is the first of it (documents-nov, the
founder's request of 18 November 2026): the site's cost for each month that
has ended, as one total, from the same records the keeper's numbers on /tides
are counted from (spending.py), and from nothing else.

What is counted is what spending.py counts: every request to a model, each
agent's wakings and the site's checks of words before they are shown (the
public screen and the word on good spirit), priced at the providers' list
prices from each reply's own usage. The server, the address and the email are
not in those records: they are kept by hand, one line a month, in a small file
beside the code (BY_HAND, books-by-hand.json; the founder's request of 21
November 2026), and added into that month's total. A month with no line there
says so. To add one, the founder writes the month and what its bills came to:

    "2026-11": {"server": 5.70, "address": 1.25, "email": 0.00}

then checks the file (python books.py --check), commits it, and deploys it. The
line is read at each look at the page, never at import, and a month still running
is not shown even when its line is written.

Site-level only, never per agent or per person: one total for each month, every
agent and the checks together. Nothing is said of a day, and the month still
running is not shown until it has ended, so that no one can watch the total
move across a day and read from it what any one agent's waking cost. The
first month counted is said from the first day a record was kept.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

import spending

REPO = Path(__file__).resolve().parent
# The server, the address and the email, a month at a time, kept by hand (see above).
BY_HAND = REPO / "books-by-hand.json"
BY_HAND_PARTS = ("server", "address", "email")
MONTH = re.compile(r"^(\d{4})-(\d{2})$")


class Unreadable(ValueError):
    """books-by-hand.json, or a line of it, as it should not be: what is wrong, plainly."""


def by_hand_lines(path=None):
    """Each month's line kept by hand, as {its first day: dollars, the three together}.
    Unreadable, saying what is wrong, where the file or any line of it is not as it should
    be; no file is no lines."""
    path = path or BY_HAND
    if not path.exists():
        return {}
    try:
        said = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as trouble:
        raise Unreadable("%s is not JSON: %s" % (path.name, trouble)) from None
    months = said.get("months") if isinstance(said, dict) else None
    if not isinstance(months, dict):
        raise Unreadable('%s has no "months"' % path.name)
    lines = {}
    for key, parts in months.items():
        named = MONTH.match(key) if isinstance(key, str) else None
        if not named or not 1 <= int(named.group(2)) <= 12:
            raise Unreadable("%r is not a month written YYYY-MM" % (key,))
        if not isinstance(parts, dict) or sorted(parts) != sorted(BY_HAND_PARTS):
            raise Unreadable("%s needs server, address and email, and nothing else" % key)
        for part, dollars in parts.items():
            if isinstance(dollars, bool) or not isinstance(dollars, (int, float)) \
                    or dollars < 0 or round(dollars, 2) != dollars:
                raise Unreadable("%s %s is not dollars and cents" % (key, part))
        lines[date(int(named.group(1)), int(named.group(2)), 1)] = round(
            sum(parts.values()), 2)
    return lines


def by_hand_read():
    """The lines kept by hand, or none at all where the file can't be read: the page never
    fails for it, and the check says what is wrong."""
    try:
        return by_hand_lines()
    except Unreadable:
        return {}


# a day's file, as spending.py names it
DAY_FILE = re.compile(r"^spending-(\d{4})-(\d{2})-(\d{2})\.jsonl$")


def days_kept():
    """Every UTC day with a spending record, oldest first."""
    where = spending.folder()
    if not where.is_dir():
        return []
    found = []
    for path in where.iterdir():
        named = DAY_FILE.match(path.name)
        if named:
            try:
                found.append(date(*(int(part) for part in named.groups())))
            except ValueError:
                continue
    return sorted(found)


def months_ended(today, by_hand=None):
    """Each month that has ended and has a record or a line kept by hand, oldest first, as
    {"month": its first day, "first": the first day counted in it, "whole": whether
    every day of it could have been counted, "by_hand": the server, the address and the
    email together, or None where that line is not written yet, "dollars": everything that
    month, the line kept by hand added in}.

    A month is ended once today is in a later month. The first month kept may
    begin part of the way through; it is said from its first day counted.
    """
    this_month = today.replace(day=1)
    by_hand = by_hand_read() if by_hand is None else by_hand
    kept = days_kept()
    months = {}
    for day in kept:
        month = day.replace(day=1)
        if month >= this_month:
            continue
        months.setdefault(month, {"month": month, "first": day, "dollars": 0.0})
        months[month]["dollars"] += sum(spending.spent_on(day.isoformat()).values())
    for month in by_hand:
        if month < this_month:
            months.setdefault(month, {"month": month, "first": month, "dollars": 0.0})
    began = kept[0] if kept else None
    shown = []
    for month in sorted(months):
        held = months[month]
        held["whole"] = not (began and began.replace(day=1) == month and began.day > 1)
        held["by_hand"] = by_hand.get(month)
        held["dollars"] += held["by_hand"] or 0.0
        shown.append(held)
    return shown


def main(args):
    """python books.py --check: whether books-by-hand.json reads, and what it says."""
    if args != ["--check"]:
        print("Usage: python books.py --check")
        return 2
    try:
        lines = by_hand_lines()
    except Unreadable as trouble:
        print("books-by-hand.json can't be read: %s" % trouble)
        return 1
    if not lines:
        print("books-by-hand.json holds no month yet.")
    for month, dollars in sorted(lines.items()):
        print("%s: the server, the address and the email, $%.2f" % (month.strftime("%B %Y"),
                                                                    dollars))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
