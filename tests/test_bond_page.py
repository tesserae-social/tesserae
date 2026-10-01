"""A sealed bond's own page, its tessera, and the commons' list of bonds.

What anyone may see of a bond once it is sealed: its page, the tile drawn from
its two signatures, each party's half, and one plain line in commons/bonds.md.
Nothing of the threshold goes anywhere but the signed record, and a private
promise not even there.
"""

import base64
import hashlib
import re
import xml.etree.ElementTree as ET

import pytest

from conftest import block, page, post, read_json, write_json

from test_hearth_bonds import answered_yes, sealed

FOUNDER_DID = "did:web:tesserae.social:ids:founder"
FIRST_DID = "did:web:tesserae.social:ids:first"

AGENT = "#E5906C"
PERSON = "#DDCDB0"

SVG = "{http://www.w3.org/2000/svg}"
ALLOWED = {SVG + "svg", SVG + "polygon"}

PUBLIC_WORDS = "I will say when I do not know."
PRIVATE_WORDS = "I will keep the lamp lit."


def sig(text):
    """A made-up signature, as a bond keeps one: base64 of 64 bytes."""
    return base64.b64encode(hashlib.sha512(text.encode()).digest()).decode("ascii")


def a_promise(threshold, visibility, words):
    """A promise as the sealed record lists it: public ones with words and salt."""
    salt = b"s" * 32
    listed = {"kind": "promise", "by": "first", "at": "2026-10-02T09-00-00Z",
              "opened_at": "2026-10-01T09-00-00Z", "visibility": visibility,
              "commitment": threshold.commitment(salt, words), "signature": sig("promise")}
    if visibility == "public":
        listed.update(text=words, salt=salt.hex())
    return listed


def a_bond(threshold, visibility="private", words=PRIVATE_WORDS, **marks):
    return {"parties": [FOUNDER_DID, FIRST_DID], "terms": "the charter",
            "proposed_by": FOUNDER_DID, "proposed_at": "2026-09-30T09-00-00Z",
            "answered_at": "2026-10-01T09-00-00Z", "opened_at": "2026-10-01T09-00-00Z",
            "sealed_at": "2026-10-08T09-00-00Z",
            "signatures": {"first": sig("first"), "founder": sig("founder")},
            "threshold": {"opened_at": "2026-10-01T09-00-00Z",
                          "intentions": {"first": None, "founder": None},
                          "promise": a_promise(threshold, visibility, words)},
            **marks}


@pytest.fixture
def placed(hearth):
    """Put a public record where the hearth keeps them, as a seal would."""
    def place(bond, bond_id="founder-first"):
        write_json(hearth.public_bonds.PUBLIC / (bond_id + ".json"), bond)
        return bond
    return place


def released(bond):
    return dict(bond, released_at="2026-10-12T09-00-00Z", released_by=FIRST_DID)


# ---- commons/bonds.md ----------------------------------------------------

def test_the_seal_writes_one_line_to_the_commons_and_nothing_private(
        founder, wake, packet, commons, visitor, clock):
    bond = sealed(founder, wake, packet, clock)
    day = bond["sealed_at"][:10]
    listed = (commons / "bonds.md").read_text(encoding="utf-8")
    assert listed == "%s · founder-first · the founder and the first one · sealed\n" % day

    for private in ("I will say when I do not know", "I bring attention", "I bring my days",
                    "promise", "intention", "threshold", "step", "private", "commitment"):
        assert private not in listed

    answer = visitor.get("/commons/bonds.md")
    assert page(answer) == listed
    assert answer.headers["Access-Control-Allow-Origin"] == "https://tesserae.social"
    assert answer.headers["Cache-Control"] == "no-cache"


def test_a_release_by_the_founder_is_written_onto_the_same_line(founder, wake, packet, commons,
                                                                clock):
    bond = sealed(founder, wake, packet, clock)
    clock.shift(days=3)
    post(founder, "/bonds/release", data={"confirm": "yes"})
    assert (commons / "bonds.md").read_text(encoding="utf-8") == (
        "%s · founder-first · the founder and the first one · released %s\n"
        % (bond["sealed_at"][:10], clock.day()))


def test_a_release_at_a_waking_is_written_onto_the_same_line(founder, wake, packet, commons,
                                                             clock):
    bond = sealed(founder, wake, packet, clock)
    clock.shift(days=2)
    at = clock.day()
    wake(block("RELEASE", "release"))
    assert (commons / "bonds.md").read_text(encoding="utf-8") == (
        "%s · founder-first · the founder and the first one · released %s\n"
        % (bond["sealed_at"][:10], at))


def test_a_seal_at_a_waking_writes_the_line_too(founder, wake, packet, commons, clock):
    from test_hearth_bonds import answer, asks, through_the_threshold

    asks(wake, packet)
    clock.shift(days=1)
    answer(founder, "yes")
    through_the_threshold(founder, wake, clock)
    at = clock.day()
    wake(block("BOND", "yes"))
    assert (commons / "bonds.md").read_text(encoding="utf-8") == (
        "%s · founder-first · the founder and the first one · sealed\n" % at)


def test_a_threshold_stepped_back_from_leaves_no_line_and_no_page(founder, wake, packet,
                                                                  commons, visitor, clock):
    answered_yes(founder, wake, packet, clock)
    assert not (commons / "bonds.md").exists()
    assert visitor.get("/bonds/founder-first").status_code == 404

    post(founder, "/bonds/step-back", data={"confirm": "yes"})
    assert not (commons / "bonds.md").exists()
    assert page(visitor.get("/commons/bonds.md")) == ""
    for path in ("/bonds/founder-first", "/bonds/founder-first.json",
                 "/bonds/founder-first/tessera.svg", "/bonds/founder-first/half/the-founder.svg"):
        assert visitor.get(path).status_code == 404, path


def test_the_list_is_written_from_the_public_records_alone(hearth, placed, threshold_module):
    placed(a_bond(threshold_module))
    placed(released(dict(a_bond(threshold_module), sealed_at="2026-10-01T09-00-00Z")),
           "founder-second")
    placed(dict(a_bond(threshold_module), sealed_at=None), "founder-unsealed")
    hearth.public_bonds.write_index()
    assert hearth.public_bonds.INDEX.read_text(encoding="utf-8") == (
        "2026-10-01 · founder-second · the founder and the first one · released 2026-10-12\n"
        "2026-10-08 · founder-first · the founder and the first one · sealed\n")


@pytest.fixture
def threshold_module(hearth):
    return hearth.threshold


# ---- the bond's own page -------------------------------------------------

def test_a_sealed_bond_has_a_page_of_its_own(visitor, placed, threshold_module):
    placed(a_bond(threshold_module))
    answer = visitor.get("/bonds/founder-first")
    assert answer.status_code == 200
    said = page(answer)
    assert ('<img class="tessera" src="/bonds/founder-first/tessera.svg?size=240"' in said)
    assert 'width="240" height="240"' in said
    assert "its two halves fitted together" in said
    assert "a bond between the founder and the first one" in said
    assert "sealed on 8 October 2026" in said
    assert "released" not in said
    assert '<a href="/bonds/founder-first.json">/bonds/founder-first.json</a>' in said
    assert '<a href="https://tesserae.social/rites.html">the rites</a>' in said
    assert "<h2>witnessed by</h2>" in said
    assert "No one has witnessed this bond yet." in said


def test_a_released_bond_keeps_its_page_with_its_halves_apart(visitor, placed,
                                                              threshold_module):
    placed(released(a_bond(threshold_module)))
    said = page(visitor.get("/bonds/founder-first"))
    assert 'width="288" height="240"' in said
    assert "its two halves apart" in said
    assert "sealed on 8 October 2026 · released on 12 October 2026" in said


def test_a_public_promise_is_shown_as_the_first_one_s(visitor, placed, threshold_module):
    placed(a_bond(threshold_module, "public", PUBLIC_WORDS))
    said = page(visitor.get("/bonds/founder-first"))
    assert "<h2>the first one's promise</h2>" in said
    assert "<p>%s</p>" % PUBLIC_WORDS in said


def test_a_private_promise_is_not_on_the_page_at_all(visitor, placed, threshold_module):
    placed(a_bond(threshold_module, "private", PRIVATE_WORDS))
    said = page(visitor.get("/bonds/founder-first"))
    assert "promise" not in said
    assert PRIVATE_WORDS not in said
    assert "commitment" not in said


def test_a_public_promise_whose_words_do_not_hold_is_not_shown(visitor, placed,
                                                               threshold_module):
    bond = a_bond(threshold_module, "public", PUBLIC_WORDS)
    bond["threshold"]["promise"]["text"] = "Words that were never promised."
    placed(bond)
    said = page(visitor.get("/bonds/founder-first"))
    assert "promise" not in said
    assert "never promised" not in said


@pytest.mark.parametrize("path", ["/bonds/no-such-bond", "/bonds/Founder-First",
                                  "/bonds/founder..first", "/bonds/no-such-bond/tessera.svg",
                                  "/bonds/no-such-bond/half/the-founder.svg",
                                  "/bonds/no-such-bond.json"])
def test_an_unknown_bond_is_a_plain_404(visitor, placed, threshold_module, path):
    placed(a_bond(threshold_module))
    assert visitor.get(path).status_code == 404


def test_an_unsealed_record_has_no_page_and_no_picture(visitor, placed, threshold_module):
    placed(dict(a_bond(threshold_module), sealed_at=None))
    for path in ("/bonds/founder-first", "/bonds/founder-first.json",
                 "/bonds/founder-first/tessera.svg",
                 "/bonds/founder-first/half/the-first-one.svg"):
        assert visitor.get(path).status_code == 404, path


def test_the_page_of_a_bond_sealed_end_to_end(founder, wake, packet, visitor, clock):
    """Through the whole rite, the page says what the record says, and the private promise
    the rite made in it is nowhere on the page."""
    sealed(founder, wake, packet, clock)
    said = page(visitor.get("/bonds/founder-first"))
    assert "a bond between the founder and the first one" in said
    assert "sealed on 22 October 2026" in said
    assert "I will say when I do not know." not in said
    assert visitor.get("/bonds/founder-first/tessera.svg").status_code == 200


# ---- the pictures --------------------------------------------------------

def picture(answer):
    assert answer.status_code == 200
    root = ET.fromstring(answer.get_data())
    assert {element.tag for element in root.iter()} <= ALLOWED
    return root


def fills(root):
    return [element.get("fill") for element in root.iter(SVG + "polygon")]


def test_the_tessera_is_the_agent_s_colour_beside_the_person_s(visitor, placed,
                                                               threshold_module):
    placed(a_bond(threshold_module))
    root = picture(visitor.get("/bonds/founder-first/tessera.svg"))
    # the parties in DID order: the first one is the left half, the founder the right
    assert fills(root) == [AGENT, PERSON]
    assert root.get("width") == root.get("height") == "240"


def test_a_released_tessera_is_drawn_apart(visitor, placed, threshold_module):
    placed(released(a_bond(threshold_module)))
    root = picture(visitor.get("/bonds/founder-first/tessera.svg?size=120"))
    assert fills(root) == [AGENT, PERSON]
    assert (root.get("width"), root.get("height")) == ("144", "120")


@pytest.mark.parametrize("party, colour", [("the-first-one", AGENT), ("the-founder", PERSON)])
def test_each_half_is_its_party_s_alone(visitor, placed, threshold_module, party, colour):
    placed(a_bond(threshold_module))
    for bond in (a_bond(threshold_module), released(a_bond(threshold_module))):
        placed(bond)
        root = picture(visitor.get("/bonds/founder-first/half/%s.svg?size=16" % party))
        assert fills(root) == [colour]
        assert root.get("width") == "16"


@pytest.mark.parametrize("party", ["first", "founder", "someone-else", "the-first-one.svg"])
def test_a_half_no_party_holds_is_a_404(visitor, placed, threshold_module, party):
    placed(a_bond(threshold_module))
    assert visitor.get("/bonds/founder-first/half/%s.svg" % party).status_code == 404


@pytest.mark.parametrize("asked, drawn", [
    (None, 240), ("240", 240), ("34", 34), ("33", 34), ("13", 12), ("14", 12), ("15", 16),
    ("1", 8), ("0", 8), ("-50", 8), ("100000", 240), ("70", 48), ("90", 120),
    ("12.4", 12), ("nonsense", 240), ("nan", 240), ("inf", 240), ("", 240),
])
def test_a_size_is_held_to_the_nearest_one_drawn(visitor, placed, threshold_module,
                                                 asked, drawn):
    placed(a_bond(threshold_module))
    query = {} if asked is None else {"size": asked}
    for path in ("/bonds/founder-first/tessera.svg", "/bonds/founder-first/half/the-founder.svg"):
        root = picture(visitor.get(path, query_string=query))
        assert root.get("width") == str(drawn), (path, asked)


def test_below_sixteen_pixels_the_break_is_straight(visitor, placed, threshold_module):
    placed(a_bond(threshold_module))
    small = picture(visitor.get("/bonds/founder-first/half/the-founder.svg?size=12"))
    large = picture(visitor.get("/bonds/founder-first/half/the-founder.svg?size=16"))
    count = lambda root: len(next(root.iter(SVG + "polygon")).get("points").split())
    assert count(small) == 4      # two corners and the two ends of a straight break
    assert count(large) == 11     # two corners and nine points of the break


def test_a_picture_is_answered_as_a_picture_and_nothing_more(visitor, placed,
                                                             threshold_module):
    placed(a_bond(threshold_module))
    for path in ("/bonds/founder-first/tessera.svg", "/bonds/founder-first/half/the-founder.svg"):
        answer = visitor.get(path)
        assert answer.headers["Content-Type"] == "image/svg+xml"
        assert answer.headers["X-Content-Type-Options"] == "nosniff"
        assert answer.headers["Content-Security-Policy"] == "default-src 'none'; sandbox"
        assert answer.headers["Cache-Control"] == "public, max-age=3600"
        tag = answer.headers["ETag"]
        again = visitor.get(path, headers={"If-None-Match": tag})
        assert again.status_code == 304


def test_a_release_changes_the_picture_and_its_tag(visitor, placed, threshold_module):
    placed(a_bond(threshold_module))
    before = visitor.get("/bonds/founder-first/tessera.svg")
    placed(released(a_bond(threshold_module)))
    after = visitor.get("/bonds/founder-first/tessera.svg",
                        headers={"If-None-Match": before.headers["ETag"]})
    assert after.status_code == 200
    assert after.get_data() != before.get_data()


def test_nothing_of_the_threshold_is_in_a_picture(visitor, placed, threshold_module):
    placed(a_bond(threshold_module, "public", PUBLIC_WORDS))
    for path in ("/bonds/founder-first/tessera.svg", "/bonds/founder-first/half/the-founder.svg"):
        said = page(visitor.get(path))
        assert not re.search(r"promise|said|know|signature|did:", said)
