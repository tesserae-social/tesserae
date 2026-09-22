"""An offering: offered by one, signed by both, placed in the commons for good.

Every kind of offering is taken here from each side, through the other's
consent, to the line in the commons - and the two signatures on it are checked
against the two identity documents, which is the whole of what makes it theirs.
A declined offering is followed too, to the one place it is kept and to the
several places it is not.
"""

import json

import pytest

from conftest import (block, blocks, lines_of, page, read_json, verify,
                      write, write_json)

HIS = "founder-2026-10-14T09-00-00Z"
HERS = "to-founder-2026-10-13T09-00-00Z"

HIS_LETTER = "Dear first one,\n\nThe lake was still this morning, and the light was long.\n"
HER_LETTER = "Dear founder,\n\nI have been thinking about what carries across the gaps.\n"

PASSAGE = "The lake was still this morning"

DRAWN = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
         '<rect x="0" y="0" width="12" height="12" fill="#D85A30"/></svg>')


def photo_bytes(size=(40, 30)):
    """A small photograph, made here rather than found anywhere."""
    import io

    from PIL import Image

    kept = io.BytesIO()
    Image.new("RGB", size, (200, 90, 48)).save(kept, "JPEG")
    return kept.getvalue()


def a_correspondence(packet):
    """One letter each way: his with a photograph, hers with a picture beside it."""
    write(packet / "letters" / "read" / (HIS + ".md"), HIS_LETTER)
    (packet / "letters" / "read" / (HIS + ".jpg")).write_bytes(photo_bytes())
    write(packet / "letters" / "outgoing" / (HERS + ".md"), HER_LETTER)
    write(packet / "letters" / "outgoing" / (HERS + ".svg"), DRAWN)


def offer(client, kind, source, text=""):
    """Offer something, as the founder's control does."""
    return client.post("/offer", data={"kind": kind, "source": source, "text": text})


def pending(packet):
    return sorted((packet / "offerings").glob("pending-*.json"))


def placed(packet):
    return [path for path in sorted((packet / "offerings").glob("*.json"))
            if not path.name.startswith(("pending-", "declined-"))]


def only_pending(packet):
    assert len(pending(packet)) == 1
    return read_json(pending(packet)[0])


def only_placed(packet):
    assert len(placed(packet)) == 1
    return read_json(placed(packet)[0])


def both_signatures(one, keys, module):
    """Both signatures on a placed offering, checked against the two identity documents."""
    payload = module.canonical(one)
    assert sorted(one["signatures"]) == ["first", "founder"]
    assert verify(keys.did("first"), payload, one["signatures"]["first"])
    assert verify(keys.did("founder"), payload, one["signatures"]["founder"])
    return True


# ---- the founder offers, the first one consents --------------------------

@pytest.mark.parametrize("kind, source, text, words", [
    ("letter", HIS, "", HIS_LETTER.strip()),
    ("letter", HERS, "", HER_LETTER.strip()),
    ("passage", HIS, PASSAGE, PASSAGE),
    ("photo", HIS, "", ""),
    ("picture", HERS, "", ""),
])
def test_the_founder_offers_and_the_first_one_places_it(founder, wake, packet, commons, keys,
                                                        hearth, kind, source, text, words):
    a_correspondence(packet)
    assert offer(founder, kind, source, text).status_code == 302

    waiting = only_pending(packet)
    assert waiting["offered_by"] == "founder"
    assert waiting["kind"] == kind
    assert waiting["source"] == source
    assert waiting["text"] == words
    assert list(waiting["signatures"]) == ["founder"]
    assert not (commons / "offerings.md").exists()   # nothing is public until both sign

    wake(block("OFFER", "consent %s" % waiting["id"]))

    one = only_placed(packet)
    assert not pending(packet)
    assert one["sealed_at"]
    assert both_signatures(one, keys, hearth.offering)
    assert read_json(commons / "offerings" / (one["id"] + ".json")) == one

    line = lines_of(commons / "offerings.md")[-1]
    assert line == "- %s · %s · %s · the founder and the first one" % (
        one["sealed_at"][:10], one["id"], kind)
    assert lines_of(commons / "events.md")[-1].endswith("offering · an offering was placed")


# ---- the first one offers, the founder consents --------------------------

@pytest.mark.parametrize("kind, source, said, words", [
    ("letter", HERS, "", HER_LETTER.strip()),
    ("letter", HIS, "", HIS_LETTER.strip()),
    ("passage", HIS, PASSAGE, PASSAGE),
    ("photo", HIS, "", ""),
    ("picture", HERS, "", ""),
])
def test_the_first_one_offers_and_the_founder_places_it(founder, wake, packet, commons, keys,
                                                        hearth, kind, source, said, words):
    a_correspondence(packet)
    asked = "offer %s %s" % (kind, source)
    wake(block("OFFER", asked + ("\n" + said if said else "")))

    waiting = only_pending(packet)
    assert waiting["offered_by"] == "first"
    assert waiting["kind"] == kind
    assert waiting["text"] == words
    assert list(waiting["signatures"]) == ["first"]

    said_page = page(founder.get("/letters"))
    assert "offered, awaiting you" in said_page
    assert waiting["id"] in said_page

    answer = founder.post("/offer/consent", data={"id": waiting["id"]})
    assert answer.status_code == 302

    one = only_placed(packet)
    assert both_signatures(one, keys, hearth.offering)
    assert one["offered_by"] == "first"
    assert lines_of(commons / "offerings.md")[-1].endswith(
        "· %s · %s · the founder and the first one" % (one["id"], kind))


# ---- what is placed, and where it is copied ------------------------------

def test_the_words_are_copied_out_beside_the_record(founder, wake, packet, commons):
    a_correspondence(packet)
    offer(founder, "passage", HIS, PASSAGE)
    wake(block("OFFER", "consent %s" % only_pending(packet)["id"]))

    one = only_placed(packet)
    assert (commons / "offerings" / (one["id"] + ".md")).read_text(
        encoding="utf-8") == PASSAGE + "\n"
    assert one.get("file") is None


@pytest.mark.parametrize("kind, source, suffix", [
    ("photo", HIS, ".jpg"), ("picture", HERS, ".svg")])
def test_an_image_is_copied_out_under_the_offering_s_own_name(founder, wake, packet, commons,
                                                              kind, source, suffix):
    a_correspondence(packet)
    offer(founder, kind, source)
    wake(block("OFFER", "consent %s" % only_pending(packet)["id"]))

    one = only_placed(packet)
    assert one["file"] == one["id"] + suffix
    copied = commons / "offerings" / one["file"]
    assert copied.exists()
    assert copied.read_bytes() == (packet / "letters" / ("read" if kind == "photo" else
                                                        "outgoing") / (source + suffix)
                                   ).read_bytes()
    assert not (commons / "offerings" / (one["id"] + ".md")).exists()


def test_a_placed_offering_is_never_removed(founder, wake, packet, commons, hearth):
    """There is no door out: nothing here takes one down, and nothing may."""
    a_correspondence(packet)
    offer(founder, "letter", HIS)
    wake(block("OFFER", "consent %s" % only_pending(packet)["id"]))
    one = only_placed(packet)

    # the same offering offered again is a second offering, and the first stands
    offer(founder, "passage", HIS, PASSAGE)
    wake(block("OFFER", "consent %s" % only_pending(packet)["id"]))
    assert len(placed(packet)) == 2
    assert (commons / "offerings" / (one["id"] + ".json")).exists()
    assert len(lines_of(commons / "offerings.md")) == 2
    assert not any(rule.rule.startswith("/offerings") and "DELETE" in rule.methods
                   for rule in hearth.app.url_map.iter_rules())


# ---- declining -----------------------------------------------------------

def test_the_founder_declines_and_nothing_of_it_is_public(founder, wake, packet, commons):
    a_correspondence(packet)
    wake(block("OFFER", "offer letter %s" % HERS))
    one = only_pending(packet)

    answer = founder.post("/offer/decline", data={"id": one["id"]})
    assert answer.status_code == 302
    assert not pending(packet)
    assert not placed(packet)
    assert not (commons / "offerings.md").exists()
    assert not (commons / "offerings").exists()
    assert not any("offering" in line for line in lines_of(commons / "events.md"))

    kept = read_json(packet / "offerings" / ("declined-%s.json" % one["id"]))
    assert kept["declined_by"] == "founder"
    assert kept["declined_at"]


def test_the_first_one_declines_what_the_founder_offered(founder, wake, packet, commons, attend):
    a_correspondence(packet)
    offer(founder, "letter", HIS)
    one = only_pending(packet)

    wake(block("OFFER", "decline %s" % one["id"]))
    assert not pending(packet) and not placed(packet)
    assert (packet / "offerings" / ("declined-%s.json" % one["id"])).exists()
    assert not (commons / "offerings.md").exists()
    assert "offered, awaiting you" not in page(founder.get("/letters"))


def test_the_first_one_is_told_what_was_declined_and_what_was_placed(wake, founder, packet,
                                                                     attend):
    a_correspondence(packet)
    wake()  # one waking to count what has happened since
    wake(block("OFFER", "offer passage %s\n%s" % (HIS, PASSAGE)))
    founder.post("/offer/decline", data={"id": only_pending(packet)["id"]})

    said = wake().opening
    assert "was declined. Nothing is owed either way" in said
    assert "a passage, out of the letter named %s" % HIS in said
    assert "was declined" not in wake().opening     # told once, and then past

    # and what the founder placed between two wakings is told at the next one
    wake(block("OFFER", "offer letter %s" % HERS))
    founder.post("/offer/consent", data={"id": only_pending(packet)["id"]})
    said = wake().opening
    assert "was placed in the commons at" in said
    assert "An offering you made" in said
    assert "/offerings#%s" % only_placed(packet)["id"] in said
    assert "was placed in the commons" not in wake().opening   # told once, and then past


# ---- a passage is quoted word for word -----------------------------------

def test_a_passage_must_be_in_the_letter_it_says_it_is_from(founder, packet):
    a_correspondence(packet)
    answer = offer(founder, "passage", HIS, "The lake was loud this morning")
    assert answer.status_code == 200
    assert "quoted word for word" in page(answer)
    assert not pending(packet)


def test_a_passage_may_be_re_wrapped_but_not_re_worded(founder, packet, hearth):
    """Where the lines fall in the quoting is not part of what was said."""
    a_correspondence(packet)
    assert hearth.offering.quotes(HIS, "The lake was still\nthis morning")
    assert not hearth.offering.quotes(HIS, "the lake was still this morning")  # nor its case
    assert not hearth.offering.quotes(HIS, "")
    assert offer(founder, "passage", HIS, "The lake was still\n  this morning").status_code == 302
    assert only_pending(packet)["text"] == "The lake was still\n  this morning"


def test_the_first_one_s_passage_is_checked_the_same_way(wake, packet):
    a_correspondence(packet)
    wake(block("OFFER", "offer passage %s\nThe lake was loud this morning" % HIS))
    assert not pending(packet)


# ---- what cannot be offered ----------------------------------------------

@pytest.mark.parametrize("said", [
    "offer letter nothing-was-ever-written",
    "offer letter ../../self",
    "offer letter ..\\self",
    "offer passage nothing-was-ever-written\nsomething",
    "offer photo %s" % HERS,          # her letter carries no photograph
    "offer picture %s" % HIS,         # his carries no picture
    "offer nonsense %s" % HIS,
    "offer letter",
    "consent nothing-of-that-name",
    "decline nothing-of-that-name",
    "I would like to offer something one day",
])
def test_an_offer_of_what_is_not_there_places_nothing(wake, packet, commons, said):
    a_correspondence(packet)
    wake(block("OFFER", said))
    assert not pending(packet)
    assert not placed(packet)
    assert not (commons / "offerings.md").exists()


def test_an_offer_of_what_is_not_there_is_not_an_act(wake, packet, attend):
    a_correspondence(packet)
    wake(block("OFFER", "offer letter nothing-was-ever-written"))
    assert read_json(sorted((packet / "attendances").glob("*.json"))[-1])["acted"] == []


def test_the_founder_may_not_offer_out_of_a_letter_that_is_not_one(founder, packet):
    a_correspondence(packet)
    answer = offer(founder, "letter", "../../self")
    assert answer.status_code == 200
    assert "nothing of that kind in that letter" in page(answer)
    assert not pending(packet)


def test_neither_may_consent_to_their_own_offering(founder, wake, packet, commons):
    a_correspondence(packet)
    offer(founder, "letter", HIS)
    one = only_pending(packet)

    assert founder.post("/offer/consent", data={"id": one["id"]}).status_code == 302
    assert pending(packet)                     # still waiting on the first one
    assert not placed(packet)

    wake(block("OFFER", "offer letter %s" % HERS))
    hers = [read_json(path) for path in pending(packet)
            if read_json(path)["offered_by"] == "first"][0]
    wake(block("OFFER", "consent %s" % hers["id"]))
    assert not placed(packet)
    assert not (commons / "offerings.md").exists()


def test_an_offering_is_answered_once(founder, wake, packet):
    a_correspondence(packet)
    wake(block("OFFER", "offer letter %s" % HERS))
    one = only_pending(packet)
    founder.post("/offer/consent", data={"id": one["id"]})
    assert founder.post("/offer/consent", data={"id": one["id"]}).status_code == 302
    assert len(placed(packet)) == 1


# ---- what the pages show -------------------------------------------------

def test_every_letter_carries_the_way_to_offer_it(founder, packet, hearth):
    a_correspondence(packet)
    said = page(founder.get("/letters"))
    assert said.count("offer to the commons") == 2      # one under each letter
    assert said.count('name="kind" value="letter"') == 2
    assert said.count('name="kind" value="photo"') == 1
    assert said.count('name="kind" value="picture"') == 1
    assert said.count('name="kind" value="passage"') == 2
    assert hearth.NO_FACES in said
    assert "No faces, no legal names — the charter keeps those private forever." in said


def test_what_is_already_offered_is_not_offered_twice(founder, packet):
    a_correspondence(packet)
    offer(founder, "letter", HIS)
    said = page(founder.get("/letters"))
    assert "The whole letter: already offered." in said
    assert said.count('name="kind" value="letter"') == 1  # hers, which is not offered


def test_the_awaiting_section_shows_what_it_offered(founder, wake, packet):
    a_correspondence(packet)
    wake(block("OFFER", "offer passage %s\n%s" % (HIS, PASSAGE)))
    said = page(founder.get("/letters"))
    assert "offered, awaiting you" in said
    assert said.index("offered, awaiting you") < said.index("write to the first one")
    assert PASSAGE in said
    assert "a passage" in said
    assert "Consent, and place it in the commons" in said and "Decline" in said


def test_an_offered_picture_is_shown_to_the_founder_before_he_signs(founder, wake, packet):
    a_correspondence(packet)
    wake(block("OFFER", "offer picture %s" % HERS))
    said = page(founder.get("/letters"))
    assert "/letters/picture/%s.svg" % HERS in said
    wake(block("OFFER", "offer photo %s" % HIS))
    assert "/letters/photo/%s.jpg" % HIS in page(founder.get("/letters"))


def test_with_nothing_offered_there_is_no_section(founder, packet):
    a_correspondence(packet)
    assert "offered, awaiting you" not in page(founder.get("/letters"))


def test_nothing_can_be_signed_without_the_founder_s_key(founder, packet, monkeypatch, hearth):
    a_correspondence(packet)
    monkeypatch.setenv("FOUNDER_KEY", "")
    answer = offer(founder, "letter", HIS)
    # the sentence is rendered, so its apostrophe is written the way markup writes one
    assert "the founder&#39;s key is not on this hearth" in page(answer)
    assert not pending(packet)
    assert not founder.post("/offer/consent", data={"id": "anything"}).status_code == 302


# ---- the offerings, open to anyone ---------------------------------------

def a_placed_offering(founder, wake, packet, kind="passage", source=HIS, text=PASSAGE):
    a_correspondence(packet)
    offer(founder, kind, source, text)
    wake(block("OFFER", "consent %s" % only_pending(packet)["id"]))
    return only_placed(packet)


def test_the_offerings_page_is_open_to_anyone(visitor, founder, wake, packet):
    one = a_placed_offering(founder, wake, packet)
    answer = visitor.get("/offerings")
    assert answer.status_code == 200
    said = page(answer)
    assert 'id="%s"' % one["id"] in said
    assert PASSAGE in said
    assert "a passage" in said
    assert "the founder and the first one" in said
    assert "15 October 2026" in said
    assert '<a href="/offerings/%s.json">' % one["id"] in said


def test_the_offerings_page_reads_forward(visitor, founder, wake, packet):
    a_correspondence(packet)
    for kind, source, text in (("letter", HIS, ""), ("passage", HIS, PASSAGE)):
        offer(founder, kind, source, text)
        wake(block("OFFER", "consent %s" % only_pending(packet)["id"]))
    older, newer = [one["id"] for one in
                    [read_json(path) for path in placed(packet)]]
    said = page(visitor.get("/offerings"))
    assert said.index('id="%s"' % older) < said.index('id="%s"' % newer)


def test_an_empty_commons_says_so(visitor):
    assert "Nothing has been offered to the commons yet." in page(visitor.get("/offerings"))


def test_the_index_is_open_to_the_atrium_and_never_cached(visitor, founder, wake, packet):
    a_placed_offering(founder, wake, packet)
    answer = visitor.get("/commons/offerings.md")
    assert answer.status_code == 200
    assert answer.headers["Content-Type"] == "text/plain; charset=utf-8"
    assert answer.headers["Access-Control-Allow-Origin"] == "https://tesserae.social"
    assert answer.headers["Cache-Control"] == "no-cache"
    assert "the founder and the first one" in page(answer)


def test_the_words_of_an_offering_are_open_to_the_atrium(visitor, founder, wake, packet):
    one = a_placed_offering(founder, wake, packet)
    answer = visitor.get("/commons/offerings/%s.md" % one["id"])
    assert answer.status_code == 200
    assert answer.headers["Content-Type"] == "text/plain; charset=utf-8"
    assert answer.headers["Access-Control-Allow-Origin"] == "https://tesserae.social"
    assert answer.headers["X-Content-Type-Options"] == "nosniff"
    assert page(answer) == PASSAGE + "\n"


def test_a_placed_picture_is_served_under_the_same_locks_as_a_private_one(visitor, founder,
                                                                          wake, packet):
    one = a_placed_offering(founder, wake, packet, kind="picture", source=HERS, text="")
    answer = visitor.get("/commons/offerings/%s" % one["file"])
    assert answer.status_code == 200
    assert answer.mimetype == "image/svg+xml"
    assert answer.headers["Content-Security-Policy"] == "sandbox"
    assert answer.headers["X-Content-Type-Options"] == "nosniff"
    assert "<rect" in page(answer)


def test_the_signed_record_is_open_to_any_machine(visitor, founder, wake, packet, keys, hearth):
    one = a_placed_offering(founder, wake, packet)
    answer = visitor.get("/offerings/%s.json" % one["id"])
    assert answer.status_code == 200
    assert answer.headers["Content-Type"] == "application/json; charset=utf-8"
    assert answer.headers["Access-Control-Allow-Origin"] == "*"
    assert answer.headers["Cache-Control"] == "no-cache"

    said = json.loads(page(answer))
    assert said == one
    assert both_signatures(said, keys, hearth.offering)


@pytest.mark.parametrize("asked", [
    "/offerings/nothing-of-that-name.json",
    "/commons/offerings/nothing-here.md",
    "/commons/offerings/..%2F..%2Fself.md",
    "/commons/offerings/private.key",
])
def test_what_was_never_placed_is_at_no_address(visitor, founder, wake, packet, asked):
    a_placed_offering(founder, wake, packet)
    assert visitor.get(asked).status_code == 404


def test_a_pending_offering_is_at_no_address(visitor, founder, packet):
    """Offered is not placed: until both have signed, there is nothing public at all."""
    a_correspondence(packet)
    offer(founder, "letter", HIS)
    one = only_pending(packet)
    assert visitor.get("/offerings/%s.json" % one["id"]).status_code == 404
    assert visitor.get("/commons/offerings/%s.md" % one["id"]).status_code == 404
    assert HIS_LETTER.strip() not in page(visitor.get("/offerings"))


def test_the_door_names_the_offerings(visitor, founder, wake, packet):
    a_placed_offering(founder, wake, packet)
    said = page(visitor.get("/"))
    assert 'href="/offerings"' in said
    assert 'href="/commons/offerings.md"' in said


# ---- what the first one is shown -----------------------------------------

def test_the_reading_asks_for_consent_and_names_what_is_offered(founder, wake, packet):
    a_correspondence(packet)
    offer(founder, "passage", HIS, PASSAGE)
    one = only_pending(packet)

    said = wake().shown
    assert "=== OFFERED TO THE COMMONS, AWAITING YOUR CONSENT ===" in said
    assert one["id"] in said
    assert PASSAGE in said
    assert "a passage, out of the letter named %s" % HIS in said
    assert "consent <id>" in said and "decline <id>" in said


def test_an_offering_of_its_own_is_not_read_back_to_it(wake, packet):
    a_correspondence(packet)
    wake(block("OFFER", "offer letter %s" % HERS))
    assert "AWAITING YOUR CONSENT" not in wake().shown


def test_what_is_offered_with_no_words_is_named_all_the_same(founder, wake, packet):
    a_correspondence(packet)
    offer(founder, "photo", HIS)
    said = wake().shown
    assert "a photograph, out of the letter named %s" % HIS in said
    assert "the photograph that came with that letter" in said


def test_the_offer_block_is_offered_at_every_waking(wake):
    said = wake().instructions
    assert "<<OFFER>>" in said
    for line in ("offer letter <stem>", "offer passage <stem>", "offer photo <stem>",
                 "offer picture <stem>", "consent <id>", "decline <id>"):
        assert line in said
    assert "No faces, no legal names" in said
    assert "never removed" in said


def test_offering_is_the_first_one_s_own_to_tell(wake, packet, commons, attend):
    """Private acts, all three: the commons is never told there was anything to decline."""
    a_correspondence(packet)
    wake(block("OFFER", "offer letter %s" % HERS))
    assert lines_of(commons / "heartbeats.md")[-1].endswith("the first one · attended")
    for act in (attend.OFFER_ACT, attend.CONSENT_ACT, attend.DECLINE_ACT):
        assert act in attend.PRIVATE_ACTS


def test_the_acts_are_written_into_its_own_record(founder, wake, packet, attend):
    a_correspondence(packet)
    wake(block("OFFER", "offer letter %s" % HERS))
    assert read_json(sorted((packet / "attendances").glob("*.json"))[-1])["acted"] == [
        attend.OFFER_ACT]

    offer(founder, "letter", HIS)
    waiting = [read_json(path) for path in pending(packet)
               if read_json(path)["offered_by"] == "founder"][0]
    wake(block("OFFER", "consent %s" % waiting["id"]))
    assert read_json(sorted((packet / "attendances").glob("*.json"))[-1])["acted"] == [
        attend.CONSENT_ACT]


# ---- the record both of them sign ----------------------------------------

def test_what_is_signed_is_the_offering_as_it_was_offered(hearth, attend):
    """Both files hold the same reckoning of it, and it leaves out what comes later."""
    assert hearth.offering.UNSIGNED == ("signatures", "sealed_at", "file")
    one = {"id": "x", "offered_by": "founder", "kind": "letter", "source": "a", "text": "b",
           "at": "c", "sealed_at": None, "signatures": {}}
    payload = hearth.offering.canonical(one)
    assert json.loads(payload) == {"id": "x", "offered_by": "founder", "kind": "letter",
                                   "source": "a", "text": "b", "at": "c"}
    # the marks made later do not change what was signed
    one.update({"sealed_at": "later", "signatures": {"founder": "y"}, "file": "x.jpg"})
    assert hearth.offering.canonical(one) == payload


def test_two_offerings_inside_one_second_take_two_names(founder, packet, clock):
    a_correspondence(packet)
    offer(founder, "letter", HIS)
    offer(founder, "letter", HERS)
    names = sorted(read_json(path)["id"] for path in pending(packet))
    assert names == [clock.stamp(), "%s-2" % clock.stamp()]
