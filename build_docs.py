#!/usr/bin/env python3
"""Turn the documents of docs/ into pages of tesserae.social.

Each document named below becomes one page at the repository root, beside
index.html, wearing the atrium's own head and the atrium's own stylesheet:

    docs/charter.md                        ->  charter.html
    docs/white-paper.md                    ->  white-paper.html
    docs/rites.md                          ->  rites.html
    docs/what-the-first-citizen-taught.md  ->  what-the-first-citizen-taught.html
    docs/the-door.md                       ->  the-door.html

and one page made of two of them, which keep their own pages too:

    docs/white-paper.md + docs/charter.md  ->  about.html

"About Tesserae" is a short list of contents, then the white paper in full, then
the charter in full, each opening with its own title only, which the list of
contents leads to. Each is the same markup its own page has, word for word; the
two pages and their addresses stay as they were.

A page is the document and nothing else: the way back to the atrium at the top
with the site's menu under it (copied from index.html, so every page of the main
site wears the one menu that build_atrium.py writes), the words in the middle, and two links under them -- the markdown this page was
made from, and tesserae.social -- with a third under the charter, to the rites. The
markdown is the document; this only dresses it. Where one document links to
another by its markdown name, the page links to the other's page.

    python build_docs.py            write the pages
    python build_docs.py --check    say whether any page has fallen behind its
                                    markdown, and exit non-zero if one has

The check rebuilds every page in memory and compares it to what is on the disk,
so an edited document, an edited stylesheet link, or an edited head all show up
as staleness. Line endings alone do not: CRLF and LF are taken as the same, so
that a checkout which converts them leaves a current page current. Nothing outside the pages named here is read or written, and
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
    "the-door.md",
]

# where the markdown itself is read, for the first of the two links at the foot
SOURCE = "https://github.com/tesserae-social/tesserae/blob/main/docs/%s"

# the atrium, which is both what the head is copied from and where the way back goes
ATRIUM = "/"
STYLESHEET = "style.css"

# what a page carries under it besides its source and the front page: the charter
# says what the rites are for, and the rites are where it says to go for how
FOOT = {
    "charter.md": [("rites.html", "the rites")],
}

# a link from one document to another by its markdown name: no scheme, no
# leading slash, and a name ending .md, with perhaps a place in it after a #
LINK_TO_DOCUMENT = re.compile(r'href="(?![a-z][a-z0-9+.-]*:|/|#)([^"#?]+)\.md(#[^"]*)?"')

# the lines of index.html's own head that every page wears too: what this place
# says it is, and the mark it is known by. They are copied rather than repeated
# so that the atrium and the documents cannot come to say two different things.
SHARED_HEAD = [
    re.compile(r'^<meta name="description" .*>$', re.M),
    re.compile(r'^<link rel="icon" .*>$', re.M),
]

# the atrium's menu, which every page wears under its way back (about-menu, the
# founder's request of 18 November 2026)
MENU = re.compile(r'^[ \t]*<nav class="menu".*?</nav>', re.S | re.M)

# the document's own title: the first heading in it
TITLE = re.compile(r"^#\s+(.+?)\s*$", re.M)

# what a page is called where its first heading would not name it: the white
# paper opens with the name of the place, and "Tesserae — Tesserae" names nothing
PAGE_TITLE = {
    "charter.md": "The charter",
    "white-paper.md": "The white paper",
}


def read_text(path):
    """Read a file as UTF-8, dropping a byte order mark if one is there."""
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8-sig")


def write_text(path, text):
    with open(path, "wb") as fh:
        fh.write(text.encode("utf-8"))


def shared_head():
    """The lines of the atrium's head that the documents wear too.

    The atrium is read with its line endings made one kind, as the check reads a
    page: under CRLF a line ends in a carriage return, and none would be found.
    """
    page = same_lines(read_text(PAGE))
    found = []
    for pattern in SHARED_HEAD:
        match = pattern.search(page)
        if match is None:
            sys.exit("build_docs: index.html has no %s line to copy" % pattern.pattern)
        found.append(match.group().strip())
    return found


def shared_menu():
    """The atrium's menu, as lines set in under a page's way back."""
    found = MENU.search(same_lines(read_text(PAGE)))
    if found is None:
        sys.exit("build_docs: index.html has no menu to copy")
    lines = [line.strip() for line in found.group().split("\n")]
    return ["  " + lines[0]] + ["    " + line for line in lines[1:-1]] + ["  " + lines[-1]]


def top_of(menu):
    """The top of a page: the way back, and the site's menu under it."""
    return ['  <p class="home"><a href="%s">Tesserae</a></p>' % ATRIUM,
            *(shared_menu() if menu is None else menu)]


def title_of(text, name):
    """What the document calls itself: its first heading."""
    match = TITLE.search(text)
    if match is None:
        sys.exit("build_docs: %s opens with no heading, so it has no title" % name)
    return match.group(1)


def body_of(text):
    """The document, turned to markup. The markdown is the document; this reads it.

    A link to another document by its markdown name is pointed at the page that
    document becomes, so that it leads somewhere on tesserae.social.
    """
    made = markdown.markdown(text, extensions=["extra"], output_format="html")
    return LINK_TO_DOCUMENT.sub(lambda m: 'href="%s.html%s"' % (m.group(1), m.group(2) or ""),
                                made)


def foot_of(name):
    """The links under one document: its source, the front page, and any of its own."""
    links = [(SOURCE % name, "the source"), (ATRIUM, "tesserae.social")] + FOOT.get(name, [])
    return " · ".join('<a href="%s">%s</a>' % (where, words) for where, words in links)


def escape(words):
    return (words.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;"))


def page_for(name, head, menu=None):
    """One document, as the page it becomes; or, asked for about.html, that page."""
    if name == ABOUT:
        return about_page(head, menu)
    text = read_text(os.path.join(DOCS, name))
    title = title_of(text, name)
    return "\n".join([
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>%s — Tesserae</title>" % escape(PAGE_TITLE.get(name, title)),
        *head,
        '<link rel="stylesheet" href="%s">' % STYLESHEET,
        "</head>",
        "<body>",
        "<main>",
        "",
        *top_of(menu),
        "",
        '  <article class="document">',
        body_of(text),
        "  </article>",
        "",
        "  <footer>",
        "    <p>%s</p>" % foot_of(name),
        "  </footer>",
        "",
        "</main>",
        "</body>",
        "</html>",
        "",
    ])


# the one page made of two documents: what it is called, and its parts in order,
# each with the place on the page it is found at and what the list of contents
# calls it. A part opens with its own title only (about-menu, 18 November 2026);
# before, each stood under a heading of its own, '<h2 class="part">' and its name.
ABOUT = "about.html"
ABOUT_TITLE = "About Tesserae"
ABOUT_PARTS = [
    ("white-paper.md", "the-white-paper", "The white paper"),
    ("charter.md", "the-charter", "The charter"),
]


def about_page(head, menu=None):
    """The white paper and the charter on one page, under a short list of contents."""
    contents = ['  <ol class="contents">'] + [
        '    <li><a href="#%s">%s</a></li>' % (place, escape(heading))
        for _, place, heading in ABOUT_PARTS] + ["  </ol>"]
    parts = []
    for name, place, heading in ABOUT_PARTS:
        text = read_text(os.path.join(DOCS, name))
        parts += [
            "",
            '  <section id="%s">' % place,
            body_of(text),
            "  </section>",
        ]
    sources = [(SOURCE % name, "the source of %s" % heading.lower())
               for name, _, heading in ABOUT_PARTS] + [(ATRIUM, "tesserae.social")]
    foot = " · ".join('<a href="%s">%s</a>' % (where, words) for where, words in sources)
    return "\n".join([
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>%s — Tesserae</title>" % escape(ABOUT_TITLE),
        *head,
        '<link rel="stylesheet" href="%s">' % STYLESHEET,
        "</head>",
        "<body>",
        "<main>",
        "",
        *top_of(menu),
        "",
        '  <article class="document">',
        "  <h1>%s</h1>" % escape(ABOUT_TITLE),
        *contents,
        *parts,
        "  </article>",
        "",
        "  <footer>",
        "    <p>%s</p>" % foot,
        "  </footer>",
        "",
        "</main>",
        "</body>",
        "</html>",
        "",
    ])


def same_lines(text):
    """A page with its line endings made one kind, so that a checkout that turns
    LF into CRLF (core.autocrlf) does not make a current page look behind."""
    return text.replace("\r\n", "\n")


def page_name(name):
    """The page one document becomes: the same name, in html."""
    return name[:-len(".md")] + ".html"


def standing(name):
    """What is on the disk for one document today, or None if there is no page yet.
    The page made of two documents is asked for by its own page name."""
    where = os.path.join(ROOT, name if name == ABOUT else page_name(name))
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
            there = standing(name)
            if there is None or same_lines(there) != same_lines(made):
                stale.append(page_name(name))
            continue
        write_text(os.path.join(ROOT, page_name(name)), made)

    made = about_page(head)
    if asked.check:
        there = standing(ABOUT)
        if there is None or same_lines(there) != same_lines(made):
            stale.append(ABOUT)
    else:
        write_text(os.path.join(ROOT, ABOUT), made)

    written = [page_name(name) for name in DOCUMENTS] + [ABOUT]
    if asked.check:
        if stale:
            sys.exit("build_docs: %s behind the record; run python build_docs.py"
                     % ", ".join(stale))
        print("documents: %d pages, all of them current" % len(written))
        return

    print("documents: %d pages written (%s)" % (len(written), ", ".join(written)))


if __name__ == "__main__":
    main()
