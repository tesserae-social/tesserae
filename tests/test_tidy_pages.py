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
