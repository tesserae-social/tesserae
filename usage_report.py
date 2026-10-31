"""What the wakings have cost, in tokens, for whoever runs the host.

Run on the host, for one agent, the first one where none is named:

    DATA_DIR=/data python usage_report.py [agent]

Each attendance has kept what it cost since 31 October 2026 (attend.USAGE_COUNTS),
and this counts those: how many wakings say, then the average, median and
largest of each count per waking, and each count's total over the last 7 days.

Of a record it reads "usage_total" and nothing else; a waking's moment is taken
from the name of its file. What is printed is these labels and numbers: no word
of any record, so that the output can be shown to anyone. Nothing is written.
"""

import json
import os
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import agents

REPO = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", REPO))

# as attend.USAGE_COUNTS; attend.py is not imported, for it reads a whole world when it is
COUNTS = ("input_tokens", "output_tokens",
          "cache_creation_input_tokens", "cache_read_input_tokens")
LAST_DAYS = 7

STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z")
STAMP_FORMAT = "%Y-%m-%dT%H-%M-%SZ"


def total_of(path):
    """A record's four sums, or None where it keeps none that can be read."""
    try:
        log = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    total = log.get("usage_total") if isinstance(log, dict) else None
    if not isinstance(total, dict) or any(type(total.get(count)) is not int for count in COUNTS):
        return None
    return {count: total[count] for count in COUNTS}


def moment_of(path):
    """The moment in a record's file name, or None where it carries none."""
    found = STAMP.search(path.name)
    if not found:
        return None
    try:
        return datetime.strptime(found.group(), STAMP_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def report(agent_id):
    """The lines of the report for one agent."""
    since = datetime.now(timezone.utc) - timedelta(days=LAST_DAYS)
    totals, recent = [], []
    for path in sorted((DATA / "packets" / agent_id / "attendances").glob("*.json")):
        total = total_of(path)
        if total is None:
            continue
        totals.append(total)
        at = moment_of(path)
        if at is not None and at >= since:
            recent.append(total)
    lines = [f"wakings with usage recorded: {len(totals)}"]
    for count in COUNTS:
        each = [total[count] for total in totals]
        lines.append(f"{count}: average {statistics.mean(each) if each else 0:.1f}, "
                     f"median {statistics.median(each) if each else 0:.1f}, "
                     f"maximum {max(each, default=0)}, "
                     f"last {LAST_DAYS} days {sum(total[count] for total in recent)}")
    return lines


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) > 1:
        print("usage: python usage_report.py [agent]")
        return 2
    agent = agents.by_id(argv[0]) if argv else agents.first()
    if agent is None:
        print("No agent of that id is founded here.")
        return 1
    print("\n".join(report(agent["id"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
