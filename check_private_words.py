"""The commit guard: no protected word goes into the repository.

The repository is public, as the commons is, and what is committed is kept
for good. This reads the lines a commit would add - the staged content, as git
holds it - and refuses the commit if any of them carries a protected word.

The words are kept outside the repository, in a list of the same shape as the
host's (see private_words.py), by default at tesserae-private-words.txt in the
home folder; --list names another. Matching ignores case and takes whole words
only. What is printed is where each one is, by file and line, and never the
word itself, so that the guard's own output can be shown to anyone.

With no list there is nothing to guard against: it says so, once, and lets the
commit through.

Installed as .git/hooks/pre-commit, which runs it from the top of the repository:

    python check_private_words.py [--list PATH]
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

import private_words

LIST = Path.home() / "tesserae-private-words.txt"

# The start of a hunk in a diff with no context: where its added lines begin in the new file.
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
FILE_BEGINS = "diff --git "
NEW_FILE = "+++ "


def staged_diff():
    """The staged changes as a diff with no context lines, read as text."""
    return subprocess.run(
        ["git", "-c", "core.quotepath=off", "diff", "--cached", "-U0", "--no-color",
         "--no-ext-diff", "--diff-filter=ACMR"],
        capture_output=True, check=True).stdout.decode("utf-8", "replace")


def added_lines(diff):
    """Each line the diff adds, as (file, line number in the new file, the line)."""
    path, number, heading = None, 0, False
    for line in diff.splitlines():
        if line.startswith(FILE_BEGINS):  # a file's heading, until its first hunk
            path, heading = None, True
            continue
        if heading and line.startswith(NEW_FILE):
            name = line[len(NEW_FILE):]
            path = name[2:] if name.startswith("b/") else None
            continue
        found = HUNK.match(line)
        if found:
            number, heading = int(found.group(1)), False
            continue
        if path and not heading and line.startswith("+"):
            yield path, number, line[1:]
            number += 1


def found(diff, words):
    """Where the staged lines carry a protected word, as (file, line number)."""
    if not words:
        return []
    every = private_words.pattern(words)
    return [(path, number) for path, number, line in added_lines(diff) if every.search(line)]


def main(argv=None):
    asked = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    asked.add_argument("--list", type=Path, default=LIST,
                       help="the list of protected words (default: %(default)s)")
    listing = asked.parse_args(argv).list
    if not listing.is_file():
        print("check_private_words: no list of protected words at %s; nothing was checked."
              % listing, file=sys.stderr)
        return 0
    where = found(staged_diff(), private_words.listed(listing))
    if not where:
        return 0
    print("This commit would add a protected word, and was not made:", file=sys.stderr)
    for path, number in where:
        print("  %s:%d" % (path, number), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
