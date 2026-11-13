"""
Which stored photographs still say where they were taken. Read only.

Every photograph left with a letter since 19 September 2026 has been kept as its
picture alone (photos.py), and every one placed in the commons since 13 November
2026 is copied out bare. This looks at the photographs already on the disk, in
each room's three letter folders and among the commons' offerings, reads only
what each says beyond its picture, and prints how many carry GPS, and which.

Nothing is changed, moved or rewritten: a stored photograph may be named in a
signed record, and is left exactly as it is. No private notebook is opened;
packets/*/private/ and anything under a folder named private is passed over.

Usage (on the host):   python photo_metadata_report.py
       (or locally)    DATA_DIR=<a restored backup> python photo_metadata_report.py
"""

import os
import sys
from pathlib import Path

import photos

REPO = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", REPO))
SUFFIXES = (".jpg", ".jpeg", ".jfif", ".png", ".webp")


def private(path, root):
    """Whether a path is in a private notebook, or any folder called private."""
    return any(part.rstrip(". ").casefold() == "private" for part in path.relative_to(root).parts)


def stored(root):
    """(where, path) for every photograph kept in a room's letters or in the commons."""
    places = []
    for letters in sorted(list(root.glob("rooms/*/letters")) + list(root.glob("packets/*/letters"))):
        where = "room " + letters.parent.name
        places.append((where, letters))
    places.append(("public offering", root / "commons" / "offerings"))
    for where, folder in places:
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if path.is_symlink() or private(path, root):
                continue
            if path.is_file() and path.suffix.lower() in SUFFIXES:
                yield where, path


def report(root):
    """The lines to print, and how many carry GPS."""
    lines, counted, with_gps, with_other = [], 0, 0, 0
    for where, path in stored(root):
        counted += 1
        said = photos.metadata_of(path.read_bytes())
        if said is None:
            lines.append(f"  could not be read: {where}: {path.name}")
        elif said.get("gps"):
            with_gps += 1
            lines.append(f"  GPS: {where}: {path.name}")
        elif said:
            with_other += 1
            lines.append(f"  other metadata ({', '.join(sorted(said))}): {where}: {path.name}")
    head = [f"{counted} photographs looked at under {root}",
            f"{with_gps} carry GPS",
            f"{with_other} carry other metadata but no GPS"]
    return head + lines, with_gps


def main():
    lines, _ = report(DATA)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
