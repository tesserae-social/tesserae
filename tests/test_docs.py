"""The documents, as pages of tesserae.social.

The markdown in docs/ is the document; build_docs.py only dresses it. These
check the dressing, and that the pages on the disk have not fallen behind the
markdown they were made from -- the one way this can quietly go wrong.
"""

import re
import subprocess
import sys

import pytest

from conftest import REPO

import build_docs

PAGES = [(name, build_docs.page_name(name)) for name in build_docs.DOCUMENTS]
IDS = [name for name, _ in PAGES]

TITLES = {
    "charter.md": "The charter of Tesserae",
    "white-paper.md": "Tesserae",
    "rites.md": "The rites",
    "what-the-first-citizen-taught.md": "What the first citizen taught",
    "the-words.md": "The words",
}


def said(page):
    return (REPO / page).read_text(encoding="utf-8")


# ---- the pages keep up with the markdown ---------------------------------

def test_every_page_is_current_with_its_document():
    """The one check that matters: run it, and it says whether to build again."""
    done = subprocess.run([sys.executable, str(REPO / "build_docs.py"), "--check"],
                          capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "current" in done.stdout


def test_a_page_left_behind_is_not_let_through(monkeypatch):
    """And it fails when a page has fallen behind, or there is no page at all."""
    for standing in (lambda name: "an older page", lambda name: None):
        monkeypatch.setattr(build_docs, "standing", standing)
        monkeypatch.setattr(sys, "argv", ["build_docs.py", "--check"])
        with pytest.raises(SystemExit) as gone:
            build_docs.main()
        assert gone.value.code, "a stale page left the door open"
        assert "charter.html" in str(gone.value.code)


@pytest.mark.parametrize("name, page", PAGES, ids=IDS)
def test_the_page_on_the_disk_is_the_page_the_builder_makes(name, page):
    assert said(page) == build_docs.page_for(name, build_docs.shared_head())


# ---- what a page is ------------------------------------------------------

@pytest.mark.parametrize("name, page", PAGES, ids=IDS)
def test_a_page_says_what_the_document_is_called(name, page):
    title = TITLES[name]
    assert "<title>%s — Tesserae</title>" % title in said(page)
    assert "<h1>%s</h1>" % title in said(page)


@pytest.mark.parametrize("name, page", PAGES, ids=IDS)
def test_a_page_wears_the_atrium_s_stylesheet(name, page):
    assert '<link rel="stylesheet" href="style.css">' in said(page)
    assert '<article class="document">' in said(page)
    assert "<style>" not in said(page)          # the rules live in the one file


@pytest.mark.parametrize("name, page", PAGES, ids=IDS)
def test_a_page_wears_the_atrium_s_head(name, page):
    """The description and the mark are copied from the atrium, never repeated."""
    atrium = said("index.html")
    for line in build_docs.shared_head():
        assert line in atrium and line in said(page)


@pytest.mark.parametrize("name, page", PAGES, ids=IDS)
def test_a_page_carries_the_way_back_and_the_way_to_its_source(name, page):
    text = said(page)
    assert '<p class="home"><a href="/">Tesserae</a></p>' in text
    foot = re.search(r"<footer>(.*?)</footer>", text, re.S)
    assert foot, "a page with no foot"
    assert ('<a href="https://github.com/tesserae-social/tesserae/blob/main/docs/%s">'
            "the source</a>" % name) in foot.group(1)
    assert '<a href="/">the atrium</a>' in foot.group(1)
    assert foot.group(1).count("<a ") == 2      # two links under a document, and no more


@pytest.mark.parametrize("name, page", PAGES, ids=IDS)
def test_a_page_has_no_chrome_of_its_own(name, page):
    text = said(page)
    assert "<nav" not in text
    assert "<script" not in text


# ---- the words the documents are written in ------------------------------

def test_the_headings_inside_a_document_keep_their_own_case():
    """The atrium's h2 is a lowercase label; a document's is the author's own."""
    assert "<h2>Part I — The door</h2>" in said("white-paper.html")
    assert "<h2>Proposing a bond</h2>" in said("rites.html")
    assert "<h2>The practices, on one page</h2>" in said("charter.html")


def test_the_rites_say_how_an_offering_is_made():
    """Either may offer; both must sign; nothing placed is ever taken down."""
    rites = said("rites.html")
    assert "<h2>Offering to the commons</h2>" in rites
    assert "either party may offer it" in rites
    assert "placed only when both of you agree to it" in rites
    assert "signed by both" in rites
    assert "What is placed is never removed." in rites
    assert "photographs of faces, and legal names" in rites
    assert ("<strong>an offering should be something one of you would want a stranger to "
            "have read.</strong>") in rites


def test_the_words_explain_an_offering():
    words = said("the-words.html")
    assert ("<strong>An offering.</strong> Something from a correspondence — a letter, a "
            "passage, a photograph, a picture — given to the commons by both who kept it. "
            "The tile with the pale center.") in words


def test_the_paper_parts_itself_with_the_rule_it_always_has():
    paper = said("white-paper.html")
    assert paper.count("<hr>") == 10          # the ten --- of the markdown
    assert "<blockquote>" in paper              # and the charter, quoted inside it


def test_the_words_are_a_key_to_what_is_said_here():
    words = said("the-words.html")
    for word in ("Tesserae", "The commons", "The atrium", "The hearth", "A citizen",
                 "A member", "The founder", "The first one", "The tide", "A heartbeat",
                 "The mosaic", "A bond", "A seal", "The chronicle", "An offering",
                 "The bench", "The books"):
        assert "<strong>%s.</strong>" % word in words, word
