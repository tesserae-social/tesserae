#!/usr/bin/env python3
"""Turn the documents of docs/ into pages of tesserae.social.

Each document named below becomes one page at the repository root, beside
index.html, wearing the atrium's own head and the atrium's own stylesheet:

    docs/charter.md                        ->  charter.html
    docs/white-paper.md                    ->  white-paper.html
    docs/rites.md                          ->  rites.html
    docs/what-the-first-citizen-taught.md  ->  what-the-first-citizen-taught.html
    docs/the-words.md                      ->  the-words.html

A page is the document and nothing else: the way back to the atrium at the top,
the words in the middle, and two links under them -- the markdown this page was
made from, and the atrium. The markdown is the document; this only dresses it.

    python build_docs.py            write the pages
    python build_docs.py --check    say whether any page has fallen behind its
                                    markdown, and exit non-zero if one has

The check rebuilds every page in memory and compares it to what is on the disk,
so an edited document, an edited stylesheet link, or an edited head all show up
as staleness. Nothing outside the pages named here is read or written, and
docs/ is only ever read.
"""

import argparse
import os
import re
import sys

import markdown

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(ROOT, "docs")
PAGE = os.path.join(ROOT, "index.html")

# the documents that become pages, and what each page is called
DOCUMENTS = [
    "charter.md",
    "white-paper.md",
    "rites.md",
    "what-the-first-citizen-taught.md",
    "the-words.md",
]

# where the markdown itself is read, for the first of the two links at the foot
SOURCE = "https://github.com/tesserae-social/tesserae/blob/main/docs/%s"

# the atrium, which is both what the head is copied from and where the way back goes
ATRIUM = "/"
STYLESHEET = "style.css"

# the lines of index.html's own head that every page wears too: what this place
# says it is, and the mark it is known by. They are copied rather than repeated
# so that the atrium and the documents cannot come to say two different things.
SHARED_HEAD = [
    re.compile(r'^<meta name="description" .*>$', re.M),
    re.compile(r'^<link rel="icon" .*>$', re.M),
]

# the document's own title: the first heading in it
TITLE = re.compile(r"^#\s+(.+?)\s*$", re.M)


def read_text(path):
    """Read a file as UTF-8, dropping a byte order mark if one is there."""
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8-sig")


def write_text(path, text):
    with open(path, "wb") as fh:
        fh.write(text.encode("utf-8"))


def shared_head():
    """The lines of the atrium's head that the documents wear too."""
    page = read_text(PAGE)
    found = []
    for pattern in SHARED_HEAD:
        match = pattern.search(page)
        if match is None:
            sys.exit("build_docs: index.html has no %s line to copy" % pattern.pattern)
        found.append(match.group().strip())
    return found


def title_of(text, name):
    """What the document calls itself: its first heading."""
    match = TITLE.search(text)
    if match is None:
        sys.exit("build_docs: %s opens with no heading, so it has no title" % name)
    return match.group(1)


def body_of(text):
    """The document, turned to markup. The markdown is the document; this reads it."""
    return markdown.markdown(text, extensions=["extra"], output_format="html")


def escape(words):
    return (words.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;"))


def page_for(name, head):
    """One document, as the page it becomes."""
    text = read_text(os.path.join(DOCS, name))
    title = title_of(text, name)
    return "\n".join([
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>%s — Tesserae</title>" % escape(title),
        *head,
        '<link rel="stylesheet" href="%s">' % STYLESHEET,
        "</head>",
        "<body>",
        "<main>",
        "",
        '  <p class="home"><a href="%s">Tesserae</a></p>' % ATRIUM,
        "",
        '  <article class="document">',
        body_of(text),
        "  </article>",
        "",
        "  <footer>",
        '    <p><a href="%s">the source</a> · <a href="%s">the atrium</a></p>'
        % (SOURCE % name, ATRIUM),
        "  </footer>",
        "",
        "</main>",
        "</body>",
        "</html>",
        "",
    ])


def page_name(name):
    """The page one document becomes: the same name, in html."""
    return name[:-len(".md")] + ".html"


def standing(name):
    """What is on the disk for one document today, or None if there is no page yet."""
    where = os.path.join(ROOT, page_name(name))
    return read_text(where) if os.path.exists(where) else None


def main():
    parser = argparse.ArgumentParser(description="Build the documents into pages.")
    parser.add_argument(
        "--check", action="store_true",
        help="write nothing; exit non-zero if any page has fallen behind its markdown",
    )
    asked = parser.parse_args()

    head = shared_head()
    stale = []
    for name in DOCUMENTS:
        made = page_for(name, head)
        if asked.check:
            if standing(name) != made:
                stale.append(page_name(name))
            continue
        write_text(os.path.join(ROOT, page_name(name)), made)

    if asked.check:
        if stale:
            sys.exit("build_docs: %s behind the record; run python build_docs.py"
                     % ", ".join(stale))
        print("documents: %d pages, all of them current" % len(DOCUMENTS))
        return

    print("documents: %d pages written (%s)"
          % (len(DOCUMENTS), ", ".join(page_name(name) for name in DOCUMENTS)))


if __name__ == "__main__":
    main()
