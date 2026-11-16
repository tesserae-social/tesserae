"""A file rewritten whole, so that a crash never leaves it cut short.

The founder's request of 15 November 2026 (audit-inventory-15-nov.md, c1 and
c3). The new text is written to a file beside the old one, flushed to the disk,
and then put in the old one's place in one step (os.replace), so that whoever
reads it finds either the file as it was or the file as it became, never half
of it. A file left beside it by a crash in the middle is passed over by every
reader, and the next write replaces it.
"""

import os
from pathlib import Path


def write_text(path, text):
    """Write text to path, in UTF-8, as Path.write_text would, but whole or not at all."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    beside = path.with_name(".%s.%d.writing" % (path.name, os.getpid()))
    try:
        with open(beside, "w", encoding="utf-8") as held:
            held.write(text)
            held.flush()
            os.fsync(held.fileno())
        os.replace(beside, path)
    finally:
        if beside.exists():
            beside.unlink()
