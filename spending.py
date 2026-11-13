"""
What the models have cost today, and the daily caps that stop them.

The founder's decision of 13 November 2026: each agent's wakings (its look-ups
inside a waking among them), and every screening call the site makes, stop for
the day once a daily limit is reached. The limits are set here, in one place:

    CAP_PER_AGENT   dollars a day for each agent's own requests
    CAP_SCREENS     dollars a day for every screening call, site-wide: the public
                    screen (public_screen.ask) and the bench's word on good spirit
                    (hearth.in_good_spirit), from a page or at a waking alike

Each request is counted with its provider's own usage numbers, as the reply
carries them: Anthropic's usage (input, output, cache writes, cache reads), and
Gemini's usage_metadata as gemini.py turns it into the same four counts. The
dollars are those counts at PRICES; a model not on the list is priced at
UNKNOWN_PRICE, higher than any listed, so that a cap can only come early, never
late.

The day is the UTC day. Each request is one line, appended, in
spending/spending-<day>.jsonl under DATA_DIR: who, which model, the four counts,
and the dollars. Appending a short line is whole on its own, so the hearth and
any attend.py it runs can count into the same day without a lock. Nothing of
any words, any name of a person, or any address is kept: who is an agent's id or
"screens". A day's file is never served; it is read here and by the founder.

A cap is checked before a thing begins, never in the middle of it: a waking
already begun is finished, and its cost is counted, so a day may end a little
over its cap, by at most one waking. Nothing is refused for a day over its cap
but the next thing of the same kind.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent

# The two caps, in US dollars a day.
CAP_PER_AGENT = 1.00
CAP_SCREENS = 1.00

SCREENS = "screens"  # who every screening call is counted as

COUNTS = ("input_tokens", "output_tokens",
          "cache_creation_input_tokens", "cache_read_input_tokens")

# Dollars per million tokens: input, output, cache write (5-minute), cache read.
# Anthropic's list prices as of November 2026; a cache write is 1.25x input and a
# read 0.1x. Gemini has no cache writes here (gemini.py counts none).
PRICES = {
    "claude-sonnet-4-5": (3.00, 15.00, 3.75, 0.30),
    "claude-sonnet-4-6": (3.00, 15.00, 3.75, 0.30),
    "claude-haiku-4-5": (1.00, 5.00, 1.25, 0.10),
    "claude-sonnet-5": (2.00, 10.00, 2.50, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.10),
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.01),
    "claude-opus-5-5": (4.00, 20.00, 5.00, 0.20),
    # Gemini 3.8 Flash at the rate it is said to go to on 1 January 2027 (twice its
    # introductory $0.75 / $3.75), so that the cap is right after the change too:
    # thinking is billed as output (gemini.py counts it there); cache reads 0.1x.
    "gemini-3.8-flash": (1.50, 7.50, 0.00, 0.15),
}
UNKNOWN_PRICE = (5.00, 25.00, 6.25, 0.50)  # higher than any listed: a cap comes early, not late


def folder():
    """Where each day's file is kept, read from DATA_DIR as it stands now."""
    return Path(os.environ.get("DATA_DIR", REPO)) / "spending"


def today(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%d")


def day_file(day):
    return folder() / f"spending-{day}.jsonl"


def counts_of(usage):
    """The four counts out of a reply's usage (an object or a dict); 0 for any not given."""
    def one(name):
        said = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        return said if type(said) is int and said > 0 else 0
    return {count: one(count) for count in COUNTS} if usage is not None else dict.fromkeys(COUNTS, 0)


def dollars(model, counts):
    """What these counts cost on this model, in dollars."""
    price = PRICES.get(model, UNKNOWN_PRICE)
    return sum(counts[count] * rate for count, rate in zip(COUNTS, price)) / 1_000_000


def record(who, model, usage, now=None):
    """Count one request: who it was for, on which model, with its provider's usage.

    Returns the dollars counted. Never raises: a count that cannot be written is
    not a reason for anything else to fail (the cap then reads what was written).
    """
    counts = counts_of(usage)
    cost = dollars(model, counts)
    line = {"who": str(who), "model": str(model), **counts, "dollars": round(cost, 6)}
    try:
        path = day_file(today(now))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as kept:
            kept.write(json.dumps(line, sort_keys=True) + "\n")
    except OSError:
        pass
    return cost


def spent(who, now=None):
    """The dollars counted for who on today's UTC day."""
    path = day_file(today(now))
    if not path.is_file():
        return 0.0
    total = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            held = json.loads(line)
        except ValueError:
            continue
        if isinstance(held, dict) and held.get("who") == who:
            cost = held.get("dollars")
            total += cost if isinstance(cost, (int, float)) else 0.0
    return total


def cap(who):
    """The daily cap for who: the screens' or an agent's."""
    return CAP_SCREENS if who == SCREENS else CAP_PER_AGENT


def spent_out(who, now=None):
    """Whether who has reached its cap for today, and nothing more of its kind may begin."""
    return spent(who, now) >= cap(who)


# What a waking refused for the cap is said as, in the agent's tide.log and so on
# /tides, plainly; it is tried again at its next waking time.
REFUSED_FOR_THE_CAP = ("not woken: today's spending limit of $%.2f was reached; "
                       "tried again at the next waking time")


def refused_note():
    return REFUSED_FOR_THE_CAP % CAP_PER_AGENT
