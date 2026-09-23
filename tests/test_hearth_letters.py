"""Letters: leaving one, what may come with it, and how the correspondence reads."""

import io

import pytest
from PIL import Image

from conftest import page, post, read_json, write, write_json

LETTER = "Dear first one,\n\nThe lake was still this morning.\n"


def photo_bytes(size=(40, 30), fmt="JPEG", exif=None):
    """A small photograph, made here rather than found anywhere."""
    picture = Image.new("RGB", size, (200, 90, 48))
    kept = io.BytesIO()
    if exif is not None:
        picture.save(kept, fmt, exif=exif)
    else:
        picture.save(kept, fmt)
    return kept.getvalue()


def leave(client, text=LETTER, photo=None, name="photo.jpg", proposes=False, follow=False,
          errand=None):
    """Leave a letter, as the founder's form does."""
    form = {"letter": text}
    if proposes:
        form["proposes"] = "1"
    if errand is not None:
        form["errand"] = errand
    if photo is not None:
        form["photo"] = (io.BytesIO(photo), name)
    return post(client, "/letters", data=form, content_type="multipart/form-data",
                follow_redirects=follow)


def incoming(packet):
    return sorted((packet / "letters" / "incoming").iterdir())


def proposal(packet):
    return packet / "bonds" / "proposal.json"


def bond_record(packet, **how):
    return write_json(packet / "bonds" / "founder-first.json", {
        "parties": ["did:web:tesserae.social:ids:founder",
                    "did:web:tesserae.social:ids:first"],
        "terms": "the charter",
        "proposed_at": "2026-09-20T09-00-00Z",
        "answered_at": "2026-09-22T09-00-00Z",
        "sealed_at": None,
        "signatures": {"first": "x"},
        **how,
    })


# ---- leaving one ---------------------------------------------------------

def test_a_letter_is_left_where_the_first_one_will_find_it(founder, packet, clock):
    answer = leave(founder)
    assert answer.status_code == 302
    left = incoming(packet)
    assert [path.name for path in left] == ["founder-%s.md" % clock.stamp()]
    assert left[0].read_text(encoding="utf-8") == LETTER.strip() + "\n"
    assert "Your letter will be found at the next attendance." in page(
        founder.get("/letters", query_string={"saved": 1}))


def test_an_empty_letter_is_not_a_letter(founder, packet):
    assert leave(founder, text="   \n").status_code == 302
    assert not incoming(packet)


def test_a_photograph_is_kept_beside_the_letter_under_one_stem(founder, packet, clock):
    leave(founder, photo=photo_bytes())
    assert [path.name for path in incoming(packet)] == [
        "founder-%s.jpg" % clock.stamp(), "founder-%s.md" % clock.stamp()]


def test_a_jfif_is_a_jpeg_and_is_kept_under_the_usual_name(founder, packet, clock):
    leave(founder, photo=photo_bytes(), name="phone-photo.JFIF")
    kept = [path.name for path in incoming(packet)]
    assert "founder-%s.jpg" % clock.stamp() in kept
    assert not any(name.endswith(".jfif") for name in kept)


@pytest.mark.parametrize("name", ["notes.txt", "scan.pdf", "clip.gif", "photo"])
def test_a_file_that_is_not_a_photograph_is_refused(founder, packet, name):
    answer = leave(founder, photo=b"whatever this is", name=name)
    assert answer.status_code == 200
    assert "That file is not a photograph." in page(answer)
    assert LETTER.strip() in page(answer)  # what was written is kept in the form
    assert not incoming(packet)


def test_a_photograph_that_will_not_open_is_refused(founder, packet):
    answer = leave(founder, photo=b"JPEG in name only", name="broken.jpg")
    assert "That file is not a photograph." in page(answer)
    assert not incoming(packet)


def test_a_photograph_over_the_limit_is_refused(founder, hearth, packet):
    answer = leave(founder, photo=b"\0" * (hearth.PHOTO_LIMIT + 1), name="huge.jpg")
    assert answer.status_code == 200
    assert "That photograph is larger than 25 MB." in page(answer)
    assert not incoming(packet)


def test_an_upload_past_what_will_be_read_at_all_is_told_plainly(founder, hearth, packet):
    too_much = hearth.app.config["MAX_CONTENT_LENGTH"] + 1024
    answer = leave(founder, photo=b"\0" * too_much, name="enormous.jpg")
    assert answer.status_code == 413
    assert "That photograph is larger than 25 MB." in page(answer)
    assert not incoming(packet)


def test_an_enormous_upload_from_a_stranger_says_only_that(visitor, hearth):
    # the limit is the whole application's, so a stranger meets it at the one
    # door that is open to strangers; the letters page turns him away first
    too_much = hearth.app.config["MAX_CONTENT_LENGTH"] + 1024
    answer = visitor.post("/bench", data={"line": "a" * too_much})
    assert answer.status_code == 413
    assert "That was too much to send." in page(answer)
    assert "larger than 25 MB" not in page(answer)


def test_a_photograph_is_stripped_of_its_metadata_and_made_smaller(founder, packet, hearth):
    marked = Image.Exif()
    marked[274] = 6            # orientation: the picture is on its side
    marked[271] = "TestCamera"  # make
    leave(founder, photo=photo_bytes(size=(3000, 2000), exif=marked.tobytes()))

    kept = [path for path in incoming(packet) if path.suffix == ".jpg"][0]
    with Image.open(kept) as stored:
        assert max(stored.size) == hearth.PHOTO_EDGE
        assert stored.size == (1365, 2048)  # turned upright first, then fitted
        assert dict(stored.getexif()) == {}


def test_a_small_photograph_is_left_the_size_it_is(founder, packet):
    leave(founder, photo=photo_bytes(size=(40, 30)))
    kept = [path for path in incoming(packet) if path.suffix == ".jpg"][0]
    with Image.open(kept) as stored:
        assert stored.size == (40, 30)


def test_a_png_keeps_its_kind(founder, packet):
    leave(founder, photo=photo_bytes(fmt="PNG"), name="picture.png")
    kept = [path for path in incoming(packet) if path.suffix == ".png"][0]
    with Image.open(kept) as stored:
        assert stored.format == "PNG"


def test_two_letters_inside_one_second_take_two_names(founder, packet, clock):
    leave(founder, text="The first.", photo=photo_bytes())
    leave(founder, text="The second.", photo=photo_bytes())
    at = clock.stamp()
    names = sorted(path.name for path in incoming(packet))
    assert names == ["founder-%s-2.jpg" % at, "founder-%s-2.md" % at,
                     "founder-%s.jpg" % at, "founder-%s.md" % at]
    assert (packet / "letters" / "incoming" / ("founder-%s.md" % at)).read_text(
        encoding="utf-8") == "The first.\n"


def test_a_stem_already_used_by_a_letter_since_read_is_not_used_again(founder, packet, clock):
    write(packet / "letters" / "read" / ("founder-%s.md" % clock.stamp()), "Read long ago.\n")
    leave(founder)
    assert [path.name for path in incoming(packet)] == ["founder-%s-2.md" % clock.stamp()]


# ---- the photographs, served -------------------------------------------

def test_a_photograph_is_served_to_the_founder_alone(founder, visitor, packet, clock):
    leave(founder, photo=photo_bytes())
    name = "founder-%s.jpg" % clock.stamp()

    answer = founder.get("/letters/photo/" + name)
    assert answer.status_code == 200
    assert answer.mimetype == "image/jpeg"

    turned = visitor.get("/letters/photo/" + name)
    assert turned.status_code == 302
    assert "/login" in turned.headers["Location"]


@pytest.mark.parametrize("asked", ["notes.md", "..%2F..%2Fself.md", "nothing-here.jpg"])
def test_only_a_photograph_of_a_letter_is_served(founder, asked):
    assert founder.get("/letters/photo/" + asked).status_code == 404


# ---- the correspondence --------------------------------------------------

def test_the_correspondence_is_one_sequence_newest_first(founder, packet):
    write(packet / "letters" / "read" / "founder-2026-10-01T09-00-00Z.md", "The oldest.\n")
    write(packet / "letters" / "outgoing" / "to-founder-2026-10-02T09-00-00Z.md", "My answer.\n")
    write(packet / "letters" / "incoming" / "founder-2026-10-03T09-00-00Z.md", "The newest.\n")

    said = page(founder.get("/letters"))
    order = [said.index(stem) for stem in ('id="founder-2026-10-03T09-00-00Z"',
                                           'id="to-founder-2026-10-02T09-00-00Z"',
                                           'id="founder-2026-10-01T09-00-00Z"')]
    assert order == sorted(order)
    assert "from the founder" in said and "from the first one" in said


def test_each_letter_is_folded_and_only_the_newest_stands_open(founder, packet):
    write(packet / "letters" / "read" / "founder-2026-10-01T09-00-00Z.md", "The oldest.\n")
    write(packet / "letters" / "outgoing" / "to-founder-2026-10-02T09-00-00Z.md", "My answer.\n")

    said = page(founder.get("/letters"))
    assert '<details class="letter" id="to-founder-2026-10-02T09-00-00Z" open>' in said
    assert '<details class="letter" id="founder-2026-10-01T09-00-00Z">' in said
    assert "The oldest." in said  # folded shut, but whole on the page


def test_a_letter_shows_its_opening_line_cut_where_it_runs_long(founder, packet, hearth):
    write(packet / "letters" / "outgoing" / "to-founder-2026-10-02T09-00-00Z.md",
          "x" * 200 + "\nand more besides\n")
    said = page(founder.get("/letters"))
    assert ("x" * hearth.OPENING_CUT + "…") in said


def test_a_letter_not_yet_read_is_marked_and_leans_forward(founder, packet):
    write(packet / "letters" / "incoming" / "founder-2026-10-03T09-00-00Z.md", "Waiting.\n")
    write(packet / "letters" / "read" / "founder-2026-10-01T09-00-00Z.md", "Read.\n")
    said = page(founder.get("/letters"))
    assert 'class="unread"' in said
    assert "waiting to be read" in said
    assert said.count("waiting to be read") == 1


def test_the_letter_that_carried_an_open_asking_is_marked(founder, packet):
    write(packet / "letters" / "incoming" / "founder-2026-10-03T09-00-00Z.md", "I am asking.\n")
    write_json(proposal(packet), {"from": "did:web:tesserae.social:ids:founder",
                                  "to": "did:web:tesserae.social:ids:first",
                                  "terms": "the charter",
                                  "letter": "founder-2026-10-03T09-00-00Z.md",
                                  "proposed_at": "2026-10-03T09-00-00Z"})
    assert "proposes a bond" in page(founder.get("/letters"))


def test_an_answered_asking_marks_the_letter_that_carried_it(founder, packet):
    write(packet / "letters" / "read" / "founder-2026-10-01T09-00-00Z.md", "An older letter.\n")
    write(packet / "letters" / "read" / "founder-2026-10-03T09-00-00Z.md", "I am asking.\n")
    bond_record(packet, proposed_at="2026-10-03T12-00-00Z")
    said = page(founder.get("/letters"))
    assert said.count("proposes a bond") == 1
    asking = said.index('id="founder-2026-10-03T09-00-00Z"')
    older = said.index('id="founder-2026-10-01T09-00-00Z"')
    assert asking < said.index("proposes a bond") < older


def test_a_photograph_appears_under_the_letter_it_came_with(founder, packet, clock):
    leave(founder, photo=photo_bytes())
    assert "/letters/photo/founder-%s.jpg" % clock.stamp() in page(founder.get("/letters"))


def test_nothing_has_passed_between_them_yet(founder):
    assert "Nothing has passed between them yet." in page(founder.get("/letters"))


# ---- the thirty days -----------------------------------------------------

def test_before_the_thirty_days_the_asking_is_hidden_and_refused(founder, packet, clock, hearth):
    clock.set("2026-10-03T12-00-00Z")  # the twenty-ninth day
    said = page(founder.get("/letters"))
    assert "A bond may be proposed thirty days after a founding" in said
    assert "4 October 2026" in said
    assert 'name="proposes"' not in said

    answer = leave(founder, proposes=True)
    assert "blocked=1" in answer.headers["Location"]
    assert not proposal(packet).exists()
    assert incoming(packet)  # the letter is left either way
    assert "no bond was proposed with it" in page(founder.get("/letters", query_string={
        "saved": 1, "blocked": 1}))
    assert hearth.TOO_SOON % "4 October 2026" in said


def test_on_the_thirtieth_day_a_bond_may_be_asked_for(founder, packet, clock):
    clock.set("2026-10-04T00-00-01Z")
    said = page(founder.get("/letters"))
    assert 'name="proposes"' in said
    assert "A bond may be proposed thirty days after a founding" not in said

    answer = leave(founder, proposes=True)
    assert "proposed=1" in answer.headers["Location"]
    asking = read_json(proposal(packet))
    assert asking["letter"] == "founder-%s.md" % clock.stamp()
    assert asking["proposed_at"] == clock.stamp()
    assert asking["terms"] == "the charter"


def test_a_commons_with_no_founding_opens_to_no_bond(founder, packet, commons, hearth):
    write(commons / "events.md", "2026-09-02 · word · the word was published\n")
    said = page(founder.get("/letters"))
    assert hearth.NO_FOUNDING in said
    assert 'name="proposes"' not in said
    leave(founder, proposes=True)
    assert not proposal(packet).exists()


def test_a_letter_without_the_tick_proposes_nothing(founder, packet):
    leave(founder)
    assert not proposal(packet).exists()


# ---- one asking at a time ------------------------------------------------

def test_an_open_asking_stands_in_the_way_of_another(founder, packet):
    write_json(proposal(packet), {"proposed_at": "2026-10-10T09-00-00Z",
                                  "letter": "founder-2026-10-10T09-00-00Z.md"})
    said = page(founder.get("/letters"))
    assert "A bond is already proposed, and only one asking may be open at a time." in said
    assert 'name="proposes"' not in said

    answer = leave(founder, proposes=True)
    assert "blocked=1" in answer.headers["Location"]
    assert read_json(proposal(packet))["proposed_at"] == "2026-10-10T09-00-00Z"


def test_a_bond_that_stands_is_in_the_way(founder, packet):
    bond_record(packet, sealed_at="2026-10-05T09-00-00Z")
    said = page(founder.get("/letters"))
    assert "A bond already stands between you and the first one." in said
    assert "blocked=1" in leave(founder, proposes=True).headers["Location"]
    assert not proposal(packet).exists()


def test_a_yes_awaiting_the_seal_is_in_the_way(founder, packet):
    bond_record(packet)
    said = page(founder.get("/letters"))
    assert "The first one has answered yes, and the bond awaits your seal." in said
    assert "blocked=1" in leave(founder, proposes=True).headers["Location"]


def test_a_released_bond_stands_in_no_one_s_way(founder, packet):
    bond_record(packet, sealed_at="2026-10-05T09-00-00Z", released_at="2026-10-08T09-00-00Z",
                released_by="did:web:tesserae.social:ids:first")
    said = page(founder.get("/letters"))
    assert 'name="proposes"' in said
    assert "proposed=1" in leave(founder, proposes=True).headers["Location"]
    assert proposal(packet).exists()


def test_a_yes_of_his_own_awaiting_its_seal_is_in_the_way(founder, packet):
    """The other way round: he answered yes, and the first one has not sealed it."""
    bond_record(packet, proposed_by="did:web:tesserae.social:ids:first",
                signatures={"founder": "y"})
    said = page(founder.get("/letters"))
    # the sentence is rendered, so its apostrophe is written the way markup writes one
    assert "You have answered yes, and the bond awaits the first one&#39;s seal." in said
    assert "blocked=1" in leave(founder, proposes=True).headers["Location"]


def test_the_letters_page_is_the_founder_s_alone(visitor):
    answer = visitor.get("/letters")
    assert answer.status_code == 302 and "/login" in answer.headers["Location"]


# ---- the errands the first one asked of him ------------------------------

ERRAND = "Go to the river this week and tell me what the light did.\n"
ASKED_AT = "2026-10-14T09-00-00Z"


def errand(packet, at=ASKED_AT, text=ERRAND):
    """An errand, as a waking leaves one in the packet."""
    return write(packet / "errands" / ("errand-%s.md" % at), text)


def answered(packet, at=ASKED_AT):
    return packet / "errands" / "answered" / ("errand-%s" % at)


def test_an_open_errand_stands_above_the_letter_form(founder, packet):
    errand(packet)
    said = page(founder.get("/letters"))
    assert "asked of you" in said
    assert said.index("asked of you") < said.index("write to the first one")
    assert "14 October 2026, 09:00 UTC" in said
    assert "tell me what the light did" in said
    assert '<option value="errand-%s.md">' % ASKED_AT in said


def test_where_nothing_was_asked_there_is_no_section_and_nothing_to_answer(founder):
    said = page(founder.get("/letters"))
    assert "asked of you" not in said
    assert "<select" not in said


def test_a_letter_may_answer_an_errand_and_the_errand_is_moved_not_erased(founder, packet,
                                                                          clock):
    errand(packet)
    assert leave(founder, errand="errand-%s.md" % ASKED_AT).status_code == 302

    assert not list((packet / "errands").glob("errand-*.md"))
    assert answered(packet).with_suffix(".md").read_text(encoding="utf-8") == ERRAND
    assert read_json(answered(packet).with_suffix(".json")) == {
        "answered_by": "founder-%s" % clock.stamp(), "answered_at": clock.stamp()}

    assert "It answers an errand" in page(
        founder.get("/letters", query_string={"saved": 1, "answered": 1}))
    assert "asked of you" not in page(founder.get("/letters"))


def test_a_letter_that_answers_nothing_moves_no_errand(founder, packet):
    errand(packet)
    assert "answered=1" not in leave(founder).headers["Location"]
    assert (packet / "errands" / ("errand-%s.md" % ASKED_AT)).exists()


def test_an_errand_is_answered_once(founder, packet):
    errand(packet)
    leave(founder, errand="errand-%s.md" % ASKED_AT)
    assert "answered=1" not in leave(founder, errand="errand-%s.md" % ASKED_AT
                                     ).headers["Location"]
    assert len(list((packet / "errands" / "answered").glob("*.md"))) == 1


@pytest.mark.parametrize("name", [
    "", "none", "errand-nothing-was-asked.md", "../self.md", "..\\self.md",
    "answered/errand-%s.md" % ASKED_AT, "errand-%s.txt" % ASKED_AT, "self.md",
])
def test_a_name_that_is_not_an_open_errand_answers_nothing(founder, packet, hearth, name):
    errand(packet)
    assert hearth.answer_errand(name, "founder-2026-10-20T09-00-00Z") is False
    assert (packet / "errands" / ("errand-%s.md" % ASKED_AT)).exists()
    assert not (packet / "errands" / "answered").exists()
