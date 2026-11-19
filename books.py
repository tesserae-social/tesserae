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
not in those records, so they are not in this total, and the page says so.

Site-level only, never per agent or per person: one total for each month, every
agent and the checks together. Nothing is said of a day, and the month still
running is not shown until it has ended, so that no one can watch the total
move across a day and read from it what any one agent's waking cost. The
first month counted is said from the first day a record was kept.
"""

import re
from datetime import date

import spending

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


def months_ended(today):
    """Each month that has ended and has a record, oldest first, as
    {"month": its first day, "first": the first day counted in it, "whole": whether
    every day of it could have been counted, "dollars": everything that month}.

    A month is ended once today is in a later month. The first month kept may
    begin part of the way through; it is said from its first day counted.
    """
    this_month = today.replace(day=1)
    kept = days_kept()
    months = {}
    for day in kept:
        month = day.replace(day=1)
        if month >= this_month:
            continue
        months.setdefault(month, {"month": month, "first": day, "dollars": 0.0})
        months[month]["dollars"] += sum(spending.spent_on(day.isoformat()).values())
    began = kept[0] if kept else None
    shown = []
    for month in sorted(months):
        held = months[month]
        held["whole"] = not (began and began.replace(day=1) == month and began.day > 1)
        shown.append(held)
    return shown
