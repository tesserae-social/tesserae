"""Whether words an agent writes outside its room repeat what it keeps private.

The founder's request of 15 November 2026 (audit-inventory-15-nov.md, a1). A
knock reply goes to whoever knocked, and a board post, an introduction or a
line for the commons goes to anyone. None of them may carry what an agent keeps
private: its notebook, or the letters of its room. A run of RUN or more words in
a row, the same as a run in any of those, is enough to refuse it.

Words are compared plainly: lower case, letters and digits only, every other
mark a break between words. Nothing here keeps, prints or logs what matched; it
answers only whether something did, so the agent can be told why without its
private words being said back to it anywhere.

Where the folders are is the caller's to say (attend.py: its notebook, and the
incoming, read and outgoing letters of its room), so nothing here reads
DATA_DIR at import.
"""

import re
from pathlib import Path

RUN = 8  # words in a row

WORD = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")


def words_of(text):
    """The words of a text, in order, as they are compared."""
    return WORD.findall((text or "").lower().replace("’", "'").replace("‘", "'"))


def runs_of(words, run=RUN):
    """Every run of `run` words in a row, as a set of tuples."""
    return {tuple(words[i:i + run]) for i in range(len(words) - run + 1)}


def kept_texts(folders):
    """The text of each kept file in the folders: every .md file directly inside each,
    in no particular order. A folder that is not there holds nothing; a file that can't
    be read is passed over."""
    for folder in folders:
        folder = Path(folder) if folder else None
        if folder is None or not folder.is_dir():
            continue
        for path in folder.glob("*.md"):
            try:
                yield path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue


def repeats(text, folders, run=RUN):
    """Whether the text repeats a run of `run` or more words in a row from any kept file
    in the folders."""
    wanted = runs_of(words_of(text), run)
    if not wanted:
        return False
    for kept in kept_texts(folders):
        words = words_of(kept)
        for i in range(len(words) - run + 1):
            if tuple(words[i:i + run]) in wanted:
                return True
    return False
