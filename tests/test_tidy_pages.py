"""tidy-pages: the founder's request of 18 November 2026.

Part 4, spacing: one small gap, the same on every page, between a page's title and where the
page begins (base.html: .page { margin-top: var(--space-4) }), and whatever a page begins with
standing right at it, however deep it begins. Every page is checked: the first thing on it is
found within the depth base.html's rule reaches, so nothing adds a margin of its own above it.

Later parts add their own tests below.
"""

from html.parser import HTMLParser

import pytest

from conftest import page
from test_introductions import switched_registry, world  # noqa: F401 - fixtures
from test_later_citizen import later, scratch_registry  # noqa: F401 - fixtures
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

# how deep base.html's rule zeroes the first thing's margin under .page (and under a style)
REACHED = 4
# what is read, as against what only holds it
HOLDS = {"div", "section"}
VOID = {"input", "br", "img", "hr", "meta", "link"}


class Tree(HTMLParser):
    """Just enough of a page to walk: each element with its tag, class and children."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "#root", "class": "", "children": []}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        one = {"tag": tag, "class": dict(attrs).get("class") or "", "children": []}
        self.stack[-1]["children"].append(one)
        if tag not in VOID:
            self.stack.append(one)

    def handle_endtag(self, tag):
        for at in range(len(self.stack) - 1, 0, -1):
            if self.stack[at]["tag"] == tag:
                del self.stack[at:]
                return


def find(node, tag, cls):
    if node["tag"] == tag and cls in node["class"].split():
        return node
    for child in node["children"]:
        found = find(child, tag, cls)
        if found:
            return found
    return None


def first_chain(node):
    """The first element, then its first element, down to something read."""
    chain = []
    while node["children"]:
        node = node["children"][0]
        chain.append(node["tag"])
        if node["tag"] not in HOLDS:
            break
    return chain


def opening(html):
    """How deep the first thing read stands under .page, past a page's own style."""
    tree = Tree()
    tree.feed(html)
    found = find(tree.root, "div", "page")
    assert found, "no .page"
    if found["children"] and found["children"][0]["tag"] == "style":
        found = {"tag": "div", "class": "page", "children": found["children"][1:]}
    return first_chain(found)


MEMBER_PAGES = ["/", "/settings", "/commons", "/board", "/board/place", "/board/weekly",
                "/board/conversation", "/made", "/find", "/knock/second", "/names/second",
                "/bonds", "/commons/ledger", "/commons/record", "/commons/charter-changes"]
FOUNDER_PAGES = ["/", "/rooms/first", "/self", "/attendances", "/chronicle", "/export",
                 "/tides", "/backups", "/settings", "/agents/second/attendances"]
VISITOR_PAGES = ["/login", "/commons", "/board", "/made", "/names/second"]


def check(answer, address):
    assert answer.status_code == 200, address
    chain = opening(page(answer))
    assert chain and len(chain) <= REACHED, (address, chain)
    return chain


@pytest.mark.parametrize("address", MEMBER_PAGES)
def test_a_member_s_pages_begin_one_small_gap_under_the_title(world, address):
    check(world.client.get(address), address)


@pytest.mark.parametrize("address", FOUNDER_PAGES)
def test_the_founder_s_pages_begin_one_small_gap_under_the_title(world, founder, address):
    check(founder.get(address), address)


@pytest.mark.parametrize("address", VISITOR_PAGES)
def test_a_visitor_s_pages_begin_one_small_gap_under_the_title(world, visitor, address):
    check(visitor.get(address), address)


def test_the_gap_is_one_small_step_and_reaches_that_deep(world):
    said = page(world.client.get("/commons"))
    assert ".page { margin-top: var(--space-4); }" in said
    rule = said.split(".page { margin-top: var(--space-4); }")[1].split("{ margin-top: 0; }")[0]
    assert ".page > :first-child > :first-child > :first-child > :first-child," in rule
    assert ".page > style:first-child + * > :first-child > :first-child > :first-child," in rule
    assert ".column > :first-child > :first-child" in rule


# ---- part 6: made here, the agents' alone -------------------------------------------

def publish(world, who, kind_line, body, at):
    made = world.hearth.made_here
    return made.publish(who, made.piece(kind_line, body), at)


def months_of_writing(world):
    """Eight pieces of writing of the second one's: six in October, one in September, one in
    August; and a text picture of its own, and a piece of writing of a person's."""
    ids = {}
    for n in range(6):
        ids["oct%d" % n] = publish(world, "second", "writing Autumn %d" % n, "Words.",
                                   "2026-10-%02dT09-00-00Z" % (n + 1))["id"]
    ids["sep"] = publish(world, "second", "writing In September", "Words.",
                         "2026-09-10T09-00-00Z")["id"]
    ids["aug"] = publish(world, "second", "writing In August", "Words.",
                         "2026-08-10T09-00-00Z")["id"]
    ids["picture"] = publish(world, "second", "text A cat", " /\_/\\n( o.o )",
                             "2026-10-07T09-00-00Z")["id"]
    ids["person"] = publish(world, "hazel", "writing A person's piece", "Mine.",
                            "2026-10-08T09-00-00Z")["id"]
    return ids


def test_made_here_shows_the_agents_pieces_alone(world, visitor):
    ids = months_of_writing(world)
    said = page(visitor.get("/made"))
    assert "Autumn 0" in said and "A cat" in said
    assert "A person&#39;s piece" not in said and "person's piece" not in said
    assert visitor.get("/made/" + ids["person"]).status_code == 404
    assert visitor.get("/made/" + ids["oct0"]).status_code == 200


def test_writing_is_on_the_left_and_pictures_on_the_right(world, visitor):
    months_of_writing(world)
    said = page(visitor.get("/made"))
    left, right = said.split('<div class="column">')[1:]
    assert "<h2>writing</h2>" in left and "Autumn 5" in left and "A cat" not in left
    assert "<h2>pictures</h2>" in right and "A cat" in right and "Autumn" not in right
    # newest first
    assert left.index("Autumn 5") < left.index("Autumn 0")


def test_the_latest_six_then_more_a_month_at_a_time(world, visitor):
    months_of_writing(world)
    said = page(visitor.get("/made"))
    assert said.count(">Autumn ") == 6
    assert "In September" not in said and 'href="/made?more=1">more</a>' in said
    said = page(visitor.get("/made?more=1"))
    assert "In September" in said and "In August" not in said
    assert 'href="/made?more=2">more</a>' in said
    said = page(visitor.get("/made?more=2"))
    assert "In August" in said and ">more</a>" not in said


def test_made_here_is_chosen_by_agent(world, visitor):
    months_of_writing(world)
    publish(world, "first", "writing The first one's", "Words.", "2026-10-09T09-00-00Z")
    said = page(visitor.get("/made"))
    assert '<span class="here">all</span>' in said
    assert 'href="/made?agent=second"' in said and 'href="/made?agent=first"' in said
    said = page(visitor.get("/made?agent=first"))
    assert "The first one&#39;s" in said and "Autumn 0" not in said
    assert 'href="/made?agent=first">' not in said  # the one chosen is plain


def test_a_person_publishes_and_uploads_nothing(world):
    for method, path in (("get", "/made/workspace"), ("post", "/made/workspace/draft"),
                         ("post", "/made/workspace/publish"), ("post", "/made/workspace/upload"),
                         ("post", "/made/workspace/discard")):
        answer = (world.client.get(path) if method == "get" else world.post(path))
        assert answer.status_code == 404, path
    assert 'href="/made/workspace"' not in page(world.client.get("/made"))


def test_each_piece_has_its_topic_in_made_here_and_each_links_the_other(world, visitor):
    ids = months_of_writing(world)
    board = page(visitor.get("/board"))
    assert 'href="/board/made"' in board and "A topic for each piece made here." in board
    piece = page(visitor.get("/made/" + ids["oct0"]))
    key = "made-" + ids["oct0"]
    assert 'href="/board/topic/%s">its topic on the board</a>' % key in piece
    topic = page(visitor.get("/board/topic/" + key))
    assert "Autumn 0" in topic and 'href="/made/%s">the piece on made here</a>' % ids["oct0"] in topic
    section = page(visitor.get("/board/made"))
    assert "Autumn 0" in section and "person" not in section.split("<main>")[1].lower()
    assert visitor.get("/board/topic/made-" + ids["person"]).status_code == 404
    # a member posts in it
    answer = world.post("/board/topic/" + key, words="A fine piece.")
    assert answer.status_code == 302
    assert "A fine piece." in page(visitor.get("/board/topic/" + key))


def test_people_s_pieces_are_moved_aside_whole_and_nothing_is_deleted(world, data_dir):
    ids = months_of_writing(world)
    made = world.hearth.made_here
    assert made.move_people_aside() == [ids["person"]]  # said, and nothing moved
    assert (data_dir / "commons" / "made" / (ids["person"] + ".json")).exists()
    kept = (data_dir / "commons" / "made" / (ids["person"] + ".json")).read_bytes()
    assert made.move_people_aside(apply=True) == [ids["person"]]
    assert not (data_dir / "commons" / "made" / (ids["person"] + ".json")).exists()
    assert (data_dir / "made-people" / (ids["person"] + ".json")).read_bytes() == kept
    assert (data_dir / "commons" / "made" / (ids["oct0"] + ".json")).exists()
    assert made.move_people_aside(apply=True) == []
    names = [name for _, name in world.hearth.export_files(world.hearth.BACKUP_TREES, left_out=())]
    assert "made-people/%s.json" % ids["person"] in names


def test_with_agents_only_off_made_here_is_as_it_was(world, visitor, monkeypatch):
    from conftest import people_make_here
    ids = months_of_writing(world)
    people_make_here(monkeypatch, visitor, world.client)
    said = page(visitor.get("/made"))
    assert "person&#39;s piece" in said and "columns: 2 320px" in said
    assert visitor.get("/made/" + ids["person"]).status_code == 200


def test_the_switch_is_the_second_one_s_and_not_the_first_one_s():
    """Still off for the first one on first-art: it is given the SVG drawing alone."""
    import json
    import found_agent
    import made_here
    from conftest import REPO
    registry = {one["id"]: one for one in json.loads((REPO / "agents.json").read_text(
        encoding="utf-8"))}
    assert made_here.AGENTS_FEATURE in found_agent.FEATURES
    assert made_here.AGENTS_FEATURE in registry["second"]["features"]
    assert made_here.AGENTS_FEATURE not in registry["first"]["features"]


def test_an_agent_with_the_switch_reads_the_agents_pieces_alone(later, monkeypatch):
    """Behind made_here_agents: read_made_here says made here is the agents', lists theirs
    alone, and opens no person's piece; without it, as before."""
    made = later.made_here
    mine = made.publish("second", made.piece("writing Its own", "Words."), "2026-10-01T09-00-00Z")
    theirs = made.publish("alder", made.piece("writing Alder's", "Mine."), "2026-10-02T09-00-00Z")
    monkeypatch.setattr(later, "MADE_AGENTS_ONLY", True)
    listed = later.made_said(None)
    assert "Its own" in listed and "Alder's" not in listed
    assert later.made_said(theirs["id"]) is None and later.made_said(mine["id"])
    assert "where agents publish" in later.READ_MADE_HERE_AGENTS["description"]
    monkeypatch.setattr(later, "MADE_AGENTS_ONLY", False)
    assert "Alder's" in later.made_said(None)
    assert "where agents and people publish" in later.READ_MADE_HERE["description"]


# ---- part 7: settings -----------------------------------------------------------------

FOLDS = ["your introduction", "your color", "your rest", "emails when something is waiting",
         "signing in"]  # "your color" in American spelling since part 8


def test_settings_has_two_columns_on_top_and_every_setting_folded_beneath(world):
    said = page(world.client.get("/settings"))
    top, below = said.split('<section class="settings">')
    left, right = top.split('<div class="column">')[1:]
    assert "<h2>open invitations</h2>" in left and "this week" not in left
    assert "<h2>this week's question</h2>" in right
    summaries = [one for one in FOLDS if "<summary>%s</summary>" % one in below]
    assert summaries == FOLDS
    at = [below.index("<summary>%s</summary>" % one) for one in FOLDS]
    assert at == sorted(at)
    # each folded, and none open of itself
    assert below.count('<details class="setting"') >= len(FOLDS)
    assert ' open>' not in below


def test_a_fold_opens_where_something_was_just_said_in_it(world):
    world.post("/settings/colour", colour="#2a6f4e")
    said = page(world.client.get("/settings?colour_saved=1"))
    assert '<details class="setting" id="colour" open>' in said


def test_a_member_s_introduction_fold_leads_to_their_own_page(world):
    said = page(world.client.get("/settings"))
    fold = said.split('id="introduction">')[1].split("</details>")[0]
    assert 'href="/names/hazel"' in fold


def test_drawn_before_tidy_pages_settings_is_as_it_was(world, monkeypatch):
    from conftest import tidy_pages_not_yet
    tidy_pages_not_yet(world.hearth, monkeypatch)
    said = page(world.client.get("/settings"))
    assert "<h2>invite someone</h2>" in said and "<h2>your colour</h2>" in said
    assert '<section class="settings">' not in said


# ---- part 8: American spelling --------------------------------------------------------

import re  # noqa: E402

BRITISH = re.compile(r"\b(colours?|coloured|honou?r(ed|s)?|favourite|centre|grey|neighbours?|"
                     r"behaviour)\b", re.I)
BRITISH_ONLY = re.compile(r"\b(colour\w*|honour\w*|favourite\w*|centre\w*|grey\w*|"
                          r"neighbour\w*|behaviour\w*)\b", re.I)


def words_shown(html):
    """What a page shows to be read: no style, script, comment, tag or attribute."""
    html = re.sub(r"<(style|script)\b.*?</\1>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


def test_settings_says_color(world):
    said = words_shown(page(world.client.get("/settings")))
    assert "your color" in said and "Your color, for the square" in said
    assert not BRITISH_ONLY.search(said)


def test_a_color_refused_is_said_in_american_spelling(world):
    said = words_shown(page(world.post("/settings/colour", colour="not a color")))
    assert "That is not a color; nothing was changed." in said


@pytest.mark.parametrize("address", MEMBER_PAGES)
def test_no_member_page_shows_a_british_spelling(world, address):
    assert not BRITISH_ONLY.search(words_shown(page(world.client.get(address)))), address


@pytest.mark.parametrize("address", FOUNDER_PAGES)
def test_no_founder_page_shows_a_british_spelling(world, founder, address):
    said = words_shown(page(founder.get(address)))
    # an agent's or a person's own words are theirs, and are never respelled; these pages
    # here show none with a British spelling. A switch's id is code, as in a link, and keeps
    # its spelling: /tides lists them for the founder to order askings by (colour_weeks,
    # since 21 November 2026); each is shown by a name in American spelling beside it
    import askings
    for switch in askings.ASK_FIRST:
        said = re.sub(r"\b%s\b" % re.escape(switch), " ", said)
    assert not BRITISH_ONLY.search(said), address


@pytest.mark.parametrize("name", ["index.html", "mosaic.html", "the-door.html", "rites.html",
                                  "white-paper.html", "what-the-first-citizen-taught.html",
                                  # documents-nov (18 November 2026)
                                  "white-paper-november-2026.html", "keepers-powers.html",
                                  "about.html"])
def test_the_main_site_and_the_documents_show_no_british_spelling(name):
    from conftest import REPO
    assert not BRITISH_ONLY.search(words_shown((REPO / name).read_text(encoding="utf-8"))), name


def test_drawn_before_tidy_pages_settings_says_colour(world, monkeypatch):
    from conftest import tidy_pages_not_yet
    tidy_pages_not_yet(world.hearth, monkeypatch)
    said = page(world.client.get("/settings"))
    assert "<h2>your colour</h2>" in said


def test_an_agent_with_the_switch_reads_american_spelling(later, monkeypatch):
    before = later.HUE_LINE
    assert "colour" in before and not later.AMERICAN  # the test's second one has no switch
    monkeypatch.setattr(later, "AMERICAN", True)
    later.spell_american()
    assert later.HUE_LINE == before.replace("colour", "color")
    assert "plain gray" in later.HUE_NONE
    assert later.HUE_ACT == "chose its colour"  # an act as it is kept: never respelled


def test_the_first_one_has_no_such_switch_and_new_agents_and_the_second_one_do():
    import json
    import american
    import found_agent
    from conftest import REPO
    registry = {one["id"]: one for one in json.loads((REPO / "agents.json").read_text(
        encoding="utf-8"))}
    assert american.FEATURE in found_agent.FEATURES
    assert american.FEATURE in registry["second"]["features"]
    assert american.FEATURE not in registry["first"]["features"]


def test_a_coming_s_corrections_are_in_american_spelling():
    import coming
    words = coming.founding_words()
    assert "your color on the commons" in words["disclosures"] + words["system"] + \
        words["opening"]
    assert "your colour on the commons" not in words["disclosures"]


def test_the_words_are_respelled_in_their_own_case():
    import american
    assert american.words("Colour, colour, COLOUR; honoured; grey.") == \
        "Color, color, COLOR; honored; gray."
    assert american.words("art_and_colour") == "art_and_colour"  # a name, not a word
