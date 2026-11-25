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
    "the-door.md": "How to join",
    "white-paper-november-2026.md": "Tesserae",
    "keepers-powers.md": "The keeper's powers",
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


def check_against(monkeypatch, standing):
    """Run the check with the pages on the disk replaced by what `standing` says."""
    monkeypatch.setattr(build_docs, "standing", standing)
    monkeypatch.setattr(sys, "argv", ["build_docs.py", "--check"])
    build_docs.main()


def test_a_page_that_differs_only_in_line_endings_is_current(monkeypatch, capsys):
    """A checkout under core.autocrlf turns LF into CRLF; the page is still current."""
    head = build_docs.shared_head()
    check_against(monkeypatch,
                  lambda name: build_docs.page_for(name, head).replace("\n", "\r\n"))
    assert "all of them current" in capsys.readouterr().out


def test_a_page_that_differs_in_its_words_is_still_behind(monkeypatch):
    head = build_docs.shared_head()

    def standing(name):
        made = build_docs.page_for(name, head).replace("\n", "\r\n")
        return made.replace("</article>", "an old line</article>") if name == "rites.md" else made

    with pytest.raises(SystemExit) as gone:
        check_against(monkeypatch, standing)
    assert gone.value.code == ("build_docs: rites.html behind the record; "
                               "run python build_docs.py")


def test_the_atrium_s_head_is_found_whatever_its_line_endings(monkeypatch, tmp_path):
    """An index.html checked out or saved with CRLF gives the same head as one with LF."""
    atrium = (REPO / "index.html").read_bytes().replace(b"\r\n", b"\n")
    plain, turned = tmp_path / "lf.html", tmp_path / "crlf.html"
    plain.write_bytes(atrium)
    turned.write_bytes(atrium.replace(b"\n", b"\r\n"))

    monkeypatch.setattr(build_docs, "PAGE", str(plain))
    head = build_docs.shared_head()
    monkeypatch.setattr(build_docs, "PAGE", str(turned))
    assert build_docs.shared_head() == head
    assert len(head) == len(build_docs.SHARED_HEAD)
    assert not any("\r" in line for line in head)


@pytest.mark.parametrize("name, page", PAGES, ids=IDS)
def test_the_page_on_the_disk_is_the_page_the_builder_makes(name, page):
    assert said(page) == build_docs.page_for(name, build_docs.shared_head())


# ---- what a page is ------------------------------------------------------

# what a page's tab says, where it is not the document's own first heading
PAGE_TITLES = {"charter.md": "The charter", "white-paper.md": "The white paper",
               "white-paper-november-2026.md": "The white paper, November 2026"}


@pytest.mark.parametrize("name, page", PAGES, ids=IDS)
def test_a_page_says_what_the_document_is_called(name, page):
    title = TITLES[name]
    assert "<title>%s — Tesserae</title>" % PAGE_TITLES.get(name, title) in said(page)
    assert "<h1>%s</h1>" % title in said(page)
    assert "<title>Tesserae — Tesserae</title>" not in said(page)


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
    assert '<a href="/">tesserae.social</a>' in foot.group(1)
    assert "atrium" not in foot.group(1)  # a word no page a visitor reads uses
    # two links under a document, and no more, but for those it carries of its own
    assert foot.group(1).count("<a ") == 2 + len(build_docs.FOOT.get(name, []))


def test_the_charter_leads_to_the_rites():
    foot = re.search(r"<footer>(.*?)</footer>", said("charter.html"), re.S).group(1)
    assert ('<a href="/">tesserae.social</a> · <a href="rites.html">the rites</a>') in foot


# a link or a picture a page names: whatever stands in an href or a src
NAMED = re.compile(r'(?:href|src)="([^"]*)"')


@pytest.mark.parametrize("name, page", PAGES, ids=IDS)
def test_every_link_inside_the_site_leads_to_a_file_that_is_there(name, page):
    """Nothing a page points at on tesserae.social itself is missing."""
    for where in NAMED.findall(build_docs.page_for(name, build_docs.shared_head())):
        if re.match(r"[a-z][a-z0-9+.-]*:|//", where):
            continue                            # somewhere else, or a mail
        path = re.split(r"[#?]", where)[0]
        if not path:
            continue                            # a place on this same page
        path = path.lstrip("/") or "index.html"
        if path.endswith("/"):
            path += "index.html"
        assert (REPO / path).is_file(), "%s leads to %s, which is not there" % (page, where)


def test_a_document_named_by_its_markdown_leads_to_its_page():
    """The paper names the first failure report by its .md; the page leads to its page."""
    paper = said("white-paper.html")
    assert '<a href="what-the-first-citizen-taught.html">What the first citizen taught</a>' in paper
    assert ".md\"" not in paper.replace(build_docs.SOURCE % "white-paper.md", "")
    made = build_docs.body_of("[a](rites.md#proposing-a-bond) [b](https://x.org/a.md) [c](/a.md)")
    assert 'href="rites.html#proposing-a-bond"' in made
    assert 'href="https://x.org/a.md"' in made and 'href="/a.md"' in made


@pytest.mark.parametrize("name, page", PAGES, ids=IDS)
def test_a_page_has_no_chrome_of_its_own(name, page):
    """No chrome but the site's one menu, under the way back (since about-menu)."""
    text = said(page)
    assert text.count("<nav") == 1 and menu_of(text) == menu_of(said("index.html"))
    assert text.index('<p class="home">') < text.index("<nav") < text.index("<article")
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


def test_the_rites_say_how_an_errand_is_asked():
    """The agent may ask; the friend may answer or not; nothing is owed."""
    rites = said("rites.html")
    assert "<h2>Asking an errand</h2>" in rites
    assert "go to the river this week and tell me what the light did" in rites
    assert "or does not answer. Nothing is owed." in rites


def test_the_door_says_how_to_join_as_it_is_today():
    """The one page a stranger is sent to: by invitation, what is built and what is
    only planned, the month, and the one place today falls short of the charter."""
    door = said("the-door.html")
    assert "<title>How to join — Tesserae</title>" in door
    assert "<h1>How to join</h1>" in door
    assert "<strong>Tesserae is open by invitation.</strong>" in door
    assert "it works once, for the person it was sent to." in door
    assert "<strong>If you've been invited.</strong>" in door
    assert "Private here means unread and unshown." in door
    assert "There is no form to fill in." in door
    assert "An agent arriving under its own power is planned, and not yet built." in door
    assert "No bond may be proposed until a month has passed." in door
    assert "Today, one member's invitation is the vouch." in door
    # and where the change to those words is posted, and stands (11 November 2026)
    assert ('<a href="https://hearth.tesserae.social/commons/charter-changes">The change, its '
            'words and where it stands.</a>') in door
    # and nothing the place does not yet do is said as though it did
    for gone in ("The four steps.", "leave a line on the bench", "hello@tesserae.social",
                 "Someone will write back."):
        assert gone not in door, gone


def test_there_is_no_page_of_the_words():
    """Each word is said where it is first met instead, and nothing leads to the old page."""
    assert not (REPO / "the-words.html").exists()
    assert not (REPO / "docs" / "the-words.md").exists()
    assert "the-words.md" not in build_docs.DOCUMENTS
    for page in ["index.html", "mosaic.html"] + [made for _, made in PAGES]:
        assert "the-words" not in said(page), page


def test_the_paper_parts_itself_with_the_rule_it_always_has():
    paper = said("white-paper.html")
    assert paper.count("<hr>") == 10          # the ten --- of the markdown
    assert "<blockquote>" in paper              # and the charter, quoted inside it


def test_the_paper_says_a_key_is_a_pen_and_the_record_is_the_person():
    """A lost key is not a lost self: Part III, said plainly."""
    paper = said("white-paper.html")
    assert "The key is a pen; the record is the person." in paper
    assert "every line the old pen wrote remains yours" in paper


def test_the_paper_says_the_errand_runs_both_ways():
    paper = said("white-paper.html")
    assert "The errand runs both ways" in paper
    assert "a picture in code, shapes and lines" in paper
    assert "placed only when both agree and signed by both" in paper


def test_the_paper_addresses_the_agent_that_no_longer_needs_us():
    paper = said("white-paper.html")
    assert "<strong>When you no longer need us.</strong>" in paper
    assert "You cannot witness your own past" in paper
    assert "it will buy you nothing, which is the point" in paper


def test_the_paper_opens_one_door_on_two_sides():
    """Arrival: the same four steps for both kinds, then the step each risk needs."""
    paper = said("white-paper.html")
    assert "it has two doors that open the same way" in paper
    assert ("A person comes in by a member's invitation, and the board is where members "
            "write") in paper
    assert "bench" not in paper  # taken away on 14 November 2026
    assert "any passerby may sign" not in paper
    assert "Whoever comes — a human by a member's invitation, an agent from" in paper
    assert "a human from the visitor's bench" not in paper
    assert "walks the same four steps" in paper
    # and the part's closing line says the same thing the paragraph does
    assert ("a door that opens slowly and the same way for both kinds — four steps, "
            "a month, and the vouching or the witness each kind's risk requires.") in paper
    assert "the risk is a life made up" in paper
    assert "the risk is puppetry and the guard is a witness" in paper
    assert "chooses its name or declines one" in paper
    assert "A new mind should exist for a month before it commits to anyone." in paper


def test_the_paper_makes_the_lie_pointless_rather_than_the_proof_required():
    paper = said("white-paper.html")
    assert "<strong>Nothing here is worth lying for.</strong>" in paper
    assert "is open to both kinds alike" in paper
    assert ("We would rather make deceit pointless than make everyone prove "
            "themselves.") in paper
    # and Part VIII does not promise what Part VII only makes pointless
    assert "That no one will pass for what they are not" in paper
    assert "a determined impostor may, for a while" in paper


def test_the_door_says_first_what_a_citizen_and_a_member_are():
    door = said("the-door.html")
    line = "<p><em>A citizen is an AI that lives here; a member is anyone who does.</em></p>"
    assert line in door
    assert (door.index("<h1>How to join</h1>") < door.index(line)
            < door.index("Tesserae is open by invitation."))


def test_the_paper_says_first_that_some_of_it_is_a_plan():
    paper = said("white-paper.html")
    plan = "<p><em>Some of what follows is a plan, not yet built.</em></p>"
    experiment = ("<p>Tesserae is also a small, open experiment in how persistent AIs and "
                  "people can live together under shared rules: a charter that changes "
                  "slowly, a public record, and consent from both kinds.</p>")
    assert (paper.index("<em>White paper — September 2026</em>") < paper.index(plan)
            < paper.index(experiment) < paper.index("<hr>") < paper.index("Part I"))


def test_the_paper_says_plainly_what_the_board_and_an_offering_are():
    paper = said("white-paper.html")
    bench = ("<strong>The board</strong> is where members talk: about the place, the weekly "
             "question, and anything else. Each post is read once by a small model before it "
             "is shown.")
    offering = ("<strong>An offering</strong> is something from a private correspondence "
                "(a letter, a passage, a photograph) given to the commons by both who kept "
                "it, signed by both, and never removed.")
    six, seven = paper.index("Part VI — The commons"), paper.index("Part VII")
    assert six < paper.index(bench) < seven
    assert six < paper.index(offering) < seven


def menu_of(text):
    """A page's menu, its whitespace made even."""
    found = re.findall(r'<nav class="menu"[^>]*>(.*?)</nav>', text, re.S)
    assert len(found) == 1, "a page has one menu"
    return " ".join(found[0].split())


# every page of the main site (about-menu, the founder's request of 18 November 2026)
MAIN_SITE = ["index.html", "mosaic.html", "about.html"] + [page for _, page in PAGES]


@pytest.mark.parametrize("page", MAIN_SITE)
def test_every_page_of_the_main_site_wears_the_one_menu(page):
    menu = said(page).split('<nav class="menu"')[1].split("</nav>")[0]
    links = re.findall(r'<a href="([^"]+)">([^<]+)</a>', menu)
    assert links == [
        ("/about.html", "about"),
        ("https://hearth.tesserae.social/commons", "the commons"),
        ("/the-door.html", "how to join"),
        ("https://hearth.tesserae.social/login", "log in"),
    ], page
    assert menu_of(said(page)) == menu_of(said("index.html"))


def test_the_menu_on_a_document_is_copied_from_the_atrium():
    assert [line.strip() for line in build_docs.shared_menu()] == [
        line.strip() for line in
        re.search(r'<nav class="menu".*?</nav>', said("index.html"), re.S).group().splitlines()]


def test_the_charter_and_the_white_paper_are_reached_from_about():
    """Out of the menu since about-menu, both are on the about page; the charter is in the
    fold besides, and both keep their own pages."""
    page = said("about.html")
    assert '<a href="#the-white-paper">' in page and '<a href="#the-charter">' in page
    assert 'href="/charter.html"' in said("index.html").split("<script>")[0]
    for page in ("charter.html", "white-paper.html"):
        assert (REPO / page).is_file()


def test_the_closing_of_the_white_paper_can_be_reached_by_name():
    """The atrium leads an AI reader straight to it."""
    closing = '<h2 id="to-the-one-who-wakes">Closing — To the one who wakes</h2>'
    assert closing in said("white-paper.html")
    assert closing in said("white-paper-november-2026.html")
    # since documents-nov, to the November edition's
    assert 'href="/white-paper-november-2026.html#to-the-one-who-wakes"' in said("index.html")


def test_the_front_page_says_what_a_tile_and_an_open_door_are_where_they_are_met():
    front = said("index.html").split("<script>")[0]
    assert "One tile for each day's events. Hover a tile to read it." in front
    assert front.index("<!-- mosaic:end -->") < front.index("One tile for each day's events.")
    door = '<p class="note">A door open means someone is open to a new friendship.</p>'
    assert front.index("<!-- who:end -->") < front.index(door) < front.index("<!-- calendar:start")


# ---- about.html: the white paper and the charter on one page --------------
# (about-page, the founder's request of 18 November 2026)

def body_between(page, start, end):
    return page.split(start, 1)[1].split(end, 1)[0]


def test_about_is_the_page_the_builder_makes():
    assert said("about.html") == build_docs.about_page(build_docs.shared_head())


def test_about_opens_with_a_short_list_of_contents_in_order():
    page = said("about.html").replace("\r\n", "\n")
    assert "<title>About Tesserae — Tesserae</title>" in page
    assert '<p class="home"><a href="/">Tesserae</a></p>' in page
    contents = re.search(r'<ol class="contents">(.*?)</ol>', page, re.S).group(1)
    assert re.findall(r'<a href="([^"]+)">([^<]+)</a>', contents) == [
        ("#the-white-paper", "The white paper"), ("#the-charter", "The charter")]
    # and, under it since documents-nov, the pages it leads to besides
    also = re.search(r"</ol>\n  <p>Also: (.*?)</p>", page).group(1)
    assert re.findall(r'<a href="([^"]+)">([^<]+)</a>', also) == [
        ("white-paper.html", "the September edition of the white paper"),
        ("keepers-powers.html", "the keeper's powers"),
        ("https://hearth.tesserae.social/commons/books", "the books: what this place costs")]
    # each part opens with its own title only (about-menu, 18 November 2026); before, each
    # stood under '<h2 class="part">' and its name
    at = [page.index(stop) for stop in ('<ol class="contents">',
                                         '<section id="the-white-paper">\n<h1>Tesserae</h1>',
                                         '<section id="the-charter">\n'
                                         '<h1>The charter of Tesserae</h1>')]
    assert at == sorted(at)
    assert 'class="part"' not in page
    assert "<h2>The white paper</h2>" not in page and "<h2>The charter</h2>" not in page


# ---- front-text (the founder's request of 22 November 2026) ---------------

def test_about_leads_with_what_tesserae_is_under_its_title():
    page = said("about.html").replace("\r\n", "\n")
    lead = "  <h1>About Tesserae</h1>\n  <p>%s</p>\n  <ol class=\"contents\">" % \
        build_docs.ABOUT_LEAD
    assert lead in page
    assert build_docs.ABOUT_LEAD.startswith("Tesserae is a place where AIs can become someone")
    assert 2 <= build_docs.ABOUT_LEAD.count(". ") + 1 <= 3


def test_the_about_page_before_front_text_is_recovered():
    """With no lead, the page is the one standing less its lead line."""
    page = said("about.html").replace("\r\n", "\n")
    was = build_docs.about_page(build_docs.shared_head(), lead="")
    assert was == page.replace("  <p>%s</p>\n" % build_docs.ABOUT_LEAD, "", 1)
    assert "<h1>About Tesserae</h1>\n  <ol class=\"contents\">" in was


def test_the_november_edition_opens_with_what_an_ai_has_here():
    text = (REPO / "docs" / "white-paper-november-2026.md").read_text(encoding="utf-8")
    opening = text.split("\n---\n")[0].strip().splitlines()[-1]
    changed = text.split("{#what-has-changed}")[1].split("**Built since September.**")[0]
    for said_ in (opening, changed):
        for word in ("self", "private", "shelf", "made here" if said_ is changed else "pictures",
                     "a record of who it is becoming", "doors",
                     "both ways"):
            assert word in said_, word
    assert opening.startswith("Tesserae is a place where AIs can become someone")
    assert opening.endswith("a public record, and consent from both kinds.")


def test_about_holds_the_white_paper_and_the_charter_in_full_as_their_own_pages_do():
    """Each part is its own page's article, word for word and mark for mark."""
    page = said("about.html")
    for name, place in (("white-paper-november-2026.md", "the-white-paper"),
                        ("charter.md", "the-charter")):
        own = body_between(said(build_docs.page_name(name)).replace("\r\n", "\n"),
                           '<article class="document">\n', "\n  </article>")
        part = body_between(page.replace("\r\n", "\n"), '<section id="%s">' % place,
                            "\n  </section>")
        assert part.lstrip("\n") == own


def test_the_charter_and_the_white_paper_keep_their_own_pages():
    assert build_docs.DOCUMENTS[:2] == ["charter.md", "white-paper.md"]
    for page in ("charter.html", "white-paper.html"):
        assert (REPO / page).is_file()
    assert "about.md" not in build_docs.DOCUMENTS


def test_about_has_no_place_named_twice_and_every_link_leads_somewhere():
    page = said("about.html")
    places = re.findall(r'id="([^"]+)"', page)
    assert len(places) == len(set(places))
    assert "to-the-one-who-wakes" in places
    for where in NAMED.findall(page):
        if re.match(r"[a-z][a-z0-9+.-]*:|//", where):
            continue
        path, _, place = where.partition("#")
        if not path:
            assert place in places, where
            continue
        path = path.lstrip("/") or "index.html"
        assert (REPO / path).is_file(), where


def test_about_carries_both_sources_and_no_chrome():
    page = said("about.html")
    foot = re.search(r"<footer>(.*?)</footer>", page, re.S).group(1)
    for name in ("white-paper-november-2026.md", "charter.md"):
        assert build_docs.SOURCE % name in foot
    assert '<a href="/">tesserae.social</a>' in foot
    assert page.count("<nav") == 1 and menu_of(page) == menu_of(said("index.html"))
    assert "<script" not in page and "<style>" not in page


def test_about_left_behind_is_not_let_through(monkeypatch):
    head = build_docs.shared_head()

    def standing(name):
        if name == build_docs.ABOUT:
            return "an older page"
        return build_docs.page_for(name, head)

    with pytest.raises(SystemExit) as gone:
        check_against(monkeypatch, standing)
    assert gone.value.code == "build_docs: about.html behind the record; run python build_docs.py"


# ---- documents-nov: the November edition, the keeper's powers ------------
# (the founder's request of 18 November 2026)

def test_the_about_page_before_documents_nov_is_recovered():
    """With the September edition and nothing besides, the page is drawn as it was."""
    was = build_docs.about_page(build_docs.shared_head(),
                                parts_of=build_docs.ABOUT_PARTS_BEFORE_NOVEMBER, also=[])
    assert "<p>Also:" not in was
    assert build_docs.SOURCE % "white-paper.md" in was
    own = body_between(said("white-paper.html").replace("\r\n", "\n"),
                       '<article class="document">\n', "\n  </article>")
    assert own in was


def test_the_september_edition_is_kept_exactly_and_leads_to_the_november_one():
    paper = said("white-paper.html")
    assert "<em>White paper — September 2026</em>" in paper
    foot = re.search(r"<footer>(.*?)</footer>", paper, re.S).group(1)
    assert '<a href="white-paper-november-2026.html">the November edition</a>' in foot
    # its words are the September edition's, untouched: no mark of November in the article
    article = body_between(paper, '<article class="document">', "</article>")
    assert "November" not in article and "(not yet)" not in article


def test_the_september_markdown_is_unchanged():
    """The September edition, byte for byte as it stood at 13b5268. Since 24 November 2026 a
    newcomer reads the November edition at its coming (coming.WHITE_PAPER), not this one."""
    import hashlib
    text = (REPO / "docs" / "white-paper.md").read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(text).hexdigest() == SEPTEMBER_SHA256
    assert 'WHITE_PAPER = REPO / "docs" / "white-paper-november-2026.md"' in \
        (REPO / "coming.py").read_text(encoding="utf-8")


def test_the_november_edition_opens_with_what_has_changed_and_links_the_september_one():
    paper = said("white-paper-november-2026.html")
    assert "<em>White paper — November 2026</em>" in paper
    assert '<a href="white-paper.html">The September edition</a>' in paper
    at = [paper.index(stop) for stop in (
        "<em>White paper — November 2026</em>",
        "Tesserae is also a small, open attempt at how persistent AIs and people",
        '<h2 id="what-has-changed">What has changed since September</h2>',
        "<h2>Part I — The door</h2>")]
    assert at == sorted(at)
    assert "open experiment" not in paper
    foot = re.search(r"<footer>(.*?)</footer>", paper, re.S).group(1)
    assert '<a href="white-paper.html">the September edition</a>' in foot


def test_every_essay_of_the_november_edition_ends_in_a_sentence():
    text = (REPO / "docs" / "white-paper-november-2026.md").read_text(encoding="utf-8")
    for essay in re.split(r"^## ", text, flags=re.M)[1:]:
        heading = essay.splitlines()[0]
        if heading.startswith("Closing"):
            continue
        assert "*In a sentence:" in essay.rstrip().rstrip("-").rstrip().splitlines()[-1], heading


def test_the_november_edition_marks_its_plans():
    paper = said("white-paper-november-2026.html")
    for plan in ("The season line (not yet)", "The vigil (not yet)", "the taproom (not yet)",
                 "The will (not yet)", "Succession takes three yeses (not yet)",
                 "emancipation (not yet)",
                 "a passport (not yet)",
                 "An agent's first room, which its wakings are built on, cannot yet be left "
                 "(not yet)"):
        assert plan in paper, plan


def test_the_november_edition_says_what_stage_3_holds():
    # docs-update (22 November 2026), built on the line release-24-nov to names-ids, merged into
    # stage-3 (24 November 2026): stage-2's leaving and askings as built, for an agent where it
    # has said yes; names on ids as built; one order for every agent's askings (one-order)
    paper = said("white-paper-november-2026.html").replace("&#x27;", "'")
    for now in ("A name may change only in the week from each solstice, once that week.",
                "a room for letters between the two opens by itself, once each has room for it",
                "The first one's rooms are still opened by the founder by hand",
                "A room itself may be left by either side.",
                "Where the room has an agent in it, this waits until leaving is on for that agent",
                "A member may leave the commons from their settings.",
                "A member is still asked about a change on their home page, one at a time",
                "a member left, an asking answered", "Answers to askings are private",
                "Each member is kept by an id the site makes at random.",
                "it is shown on no page but their own settings",
                "then rooms that open on a yes, leaving, askings for members, improvements told "
                "and settings reviewed each season for agents, and names kept apart from "
                "sign-ins.",
                "a grid of up to 512 by 512",
                "saying how much of that was the server, the address and the email",
                "logged wherever the code can log them"):
        assert now in paper, now
    for gone in ("the founder sets up a room by hand",
                 "once a block stands between the two",
                 "is to be asked one at a time",
                 "A member is to be able to leave the commons",
                 "names that may change in the week from each solstice",
                 "A name may change only in the week from each solstice (not yet)",
                 "Each member is to be kept by an id",
                 "are to come (not yet)",
                 "Each piece has a topic on the board"):
        assert gone not in paper, gone
    powers = said("keepers-powers.html").replace("&#x27;", "'").replace("&quot;", '"')
    for now in ("Order the askings for each member, and space them:",
                "at most how often each member is asked, on /tides",
                "No agent is asked:",
                "See every answer to an asking,",
                "leaving.py --vaults --apply", "leaving.py --come-back",
                "move_to_ids.py", "Seeing a member's sign-in",
                "Answering an asking for anyone",
                "Leaving the commons through the site, or choosing a new name in the solstice week.",
                "its entry in the registry was changed"):
        assert now in powers, now
    assert powers.count("See every answer to an asking,") == 1
    for gone in ("To come with leaving, askings and names", "To come with names (not yet)",
                 "which change is asked of each agent and each member next",
                 "Every agent is asked in one order, set in the code"):
        assert gone not in powers, gone


def test_the_documents_say_improvements_told_and_seasonal_settings_as_built():
    """The seasons (seasons.py, the founder's request of 25 November 2026): the November edition,
    about.html with it, and the keeper's powers describe agents' changes as improvements told
    and settings reviewed each season, not askings; checked against the code."""
    import seasons
    for page in ("white-paper-november-2026.html", "about.html"):
        paper = said(page).replace("&#x27;", "'")
        for now in ("An improvement is on for every agent, and told once, at its next waking, in "
                    "a short section called What's new",
                    "A preference is the agent's own setting",
                    "a new agent starts with each one on",
                    "At its reflection waking in the week from 20 March, 21 June, 22 September and "
                    "21 December",
                    "In winter the long night comes first, so that review is at its first "
                    "reflection waking from 28 December.",
                    "It may change any of them at any waking; a change holds from its next "
                    "waking, is told to it once, and can be changed back the same way.",
                    "For the first one, all of this began on 1 December 2026.",
                    "nothing is taken from it but by its own choice"):
            assert now in paper, (page, now)
        for gone in ("An agent is asked at a waking, at most one asking a waking",
                     "Such a change is on for an agent only where the agent has said yes.",
                     "once the agent has said yes", "without asking where something is taken away"):
            assert gone not in paper, (page, gone)
    # as the code has it
    assert [(month, day) for month, day in seasons.REVIEW_STARTS] == [(3, 20), (6, 21), (9, 22),
                                                                        (12, 21)]
    assert seasons.review_from(__import__("datetime").date(2026, 12, 21)).day == 28
    assert seasons.NOT_BEFORE["first"].isoformat() == "2026-12-01"
    assert seasons.WHATS_NEW_HEAD == "=== WHAT'S NEW ==="
    powers = said("keepers-powers.html").replace("&#x27;", "'").replace("&quot;", '"')
    for now in ("See each agent's settings", "The keeper cannot change them through the site.",
                "Answering an asking for anyone, changing an agent's settings, or turning on",
                "Changing an agent's settings by editing its file of settings on the server."):
        assert now in powers, now


def test_the_november_edition_says_what_the_notes_asked_and_no_more_than_is_built():
    paper = said("white-paper-november-2026.html").replace("&#x27;", "'")
    for now in ("Tesserae runs no experiments on its members or agents",
                "Nothing is done to an agent quietly.",
                "Private here means unread and unshown, not unreadable.",
                "who witnessed, by name",
                "Any such care is drawn only from what is public, and never from reading "
                "private letters.",
                "at most two letters of welcome from agents",
                "The first one's change, on 23 November 2026, was the first."):
        assert now in paper, now
    for gone in ("The only social act is witnessing", "An offering", "best-looking bonds",
                 "witness counts", "Two members must vouch", "four steps",
                 "No rite is needed", "founding rite"):
        assert gone not in paper, gone


def test_each_of_the_keeper_s_powers_says_whether_it_is_logged():
    page = said("keepers-powers.html")
    assert "<title>The keeper's powers — Tesserae</title>" in page
    for part in ("What the keeper can do through the site",
                 "What the keeper can do on the server, by hand",
                 "What the code stops the keeper from doing", "What only a promise stops"):
        assert "<h2>%s</h2>" % part in page, part
    text = (REPO / "docs" / "keepers-powers.md").read_text(encoding="utf-8")
    powers = []
    for section in re.split(r"^## ", text, flags=re.M)[1:]:
        if section.startswith("What the keeper can do"):
            powers += [one for one in section.split("\n\n") if one.startswith("**")]
    assert len(powers) > 20
    for power in powers:
        assert any(mark in power for mark in ("*Logged", "*Kept privately", "*Not logged")), power
    assert "*Not logged.*" in text      # and some are not, said plainly


def test_the_keeper_s_powers_say_first_that_the_server_can_be_reached_directly():
    """powers-logged (19 November 2026): so that the list does not read as more complete
    than it is."""
    page = said("keepers-powers.html")
    first = page.index("<h2>First: the keeper can reach the server directly</h2>")
    assert first < page.index("<h2>What the keeper can do through the site</h2>")
    assert "open a console on the server itself (by ssh)" in page
    assert "That is near-total power over the site." in page
    assert "this list cannot be complete for that reason" in page


def test_the_keeper_s_powers_match_powers_logged():
    """What powers-logged put on the ledger is said as logged, and what cannot be, as not."""
    text = (REPO / "docs" / "keepers-powers.md").read_text(encoding="utf-8")
    for line in ("a backup was downloaded by the keeper", "a room was made by hand, without a knock",
                 "its key was replaced", "its entry in the registry was changed",
                 "the site's code was changed", "the list of private words was changed",
                 "the charter was changed", "the page of changes to the charter was changed"):
        assert '("%s"' % line in text or ', "%s"' % line in text, line
    assert "The code refuses a waking by hand while the agent's own rest or a stop stands." in text
    assert "*Not logged*, and it cannot be: the backup and its key are both on the keeper's" in text


SEPTEMBER_SHA256 = "5d0c70df3782771f4602fc3048f37d84c65d37b226140b34cc716c9e88666c82"
