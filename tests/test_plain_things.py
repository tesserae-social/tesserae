"""Three plain things: small true facts of the body and the day, above a letter.

Left on the letters form with the letter, kept in the letter's own file on a
first line of their own, shown above the letter on /letters and in the reading,
and never part of what is offered to the commons. A letter without them reads
exactly as every letter before them did.
"""

import io

import pytest

from conftest import block, page, post, read_json

LETTER = "Dear first one,\n\nThe lake was still this morning.\n"

SLEPT = "slept badly"
FROST = "first frost on the car"
HANDS = "hands cold all morning"


def leave(client, things=(), text=LETTER):
    """Leave a letter with its things, as the founder's form sends them."""
    form = {"letter": text, "thing": list(things)}
    return post(client, "/letters", data=form, content_type="multipart/form-data")


def the_letter(packet):
    """The one letter waiting to be read, as it is kept."""
    left = sorted((packet / "letters" / "incoming").glob("*.md"))
    assert len(left) == 1
    return left[0]


def kept_things(hearth, packet):
    return hearth.offering.split_things(the_letter(packet).read_text(encoding="utf-8"))


# ---- saving them ---------------------------------------------------------

@pytest.mark.parametrize("given, kept", [
    ([], []),
    (["", "", ""], []),
    ([SLEPT, "", ""], [SLEPT]),
    (["", FROST, ""], [FROST]),
    ([SLEPT, "", HANDS], [SLEPT, HANDS]),
    ([SLEPT, FROST, HANDS], [SLEPT, FROST, HANDS]),
])
def test_zero_to_three_things_are_kept_with_the_letter(founder, hearth, packet, given, kept):
    assert leave(founder, given).status_code == 302
    things, body = kept_things(hearth, packet)
    assert things == kept
    assert body == LETTER.strip() + "\n"


def test_a_letter_with_none_is_kept_exactly_as_before(founder, packet):
    leave(founder, ["", "  ", ""])
    assert the_letter(packet).read_text(encoding="utf-8") == LETTER.strip() + "\n"


def test_the_things_are_one_line_above_the_letter(founder, packet):
    leave(founder, [SLEPT, FROST])
    kept = the_letter(packet).read_text(encoding="utf-8")
    assert kept == ('<!-- three plain things: ["slept badly", "first frost on the car"] -->\n'
                    + LETTER.strip() + "\n")


def test_no_more_than_three_are_kept(founder, hearth, packet):
    leave(founder, [SLEPT, FROST, HANDS, "a fourth"])
    assert kept_things(hearth, packet)[0] == [SLEPT, FROST, HANDS]


def test_a_thing_is_cut_at_eighty_characters(founder, hearth, packet):
    leave(founder, ["x" * 79, "y" * 80, "z" * 200])
    assert kept_things(hearth, packet)[0] == ["x" * 79, "y" * 80, "z" * 80]


def test_newlines_and_control_characters_are_taken_out(founder, hearth, packet):
    leave(founder, ["slept\nbadly", "first\r\nfrost on\tthe car", "\x00hands\x07 cold\x1b"])
    assert kept_things(hearth, packet)[0] == ["slept badly", "first frost on the car",
                                              "hands cold"]


def test_a_thing_is_plain_text_and_cannot_close_its_line(founder, hearth, packet):
    leave(founder, ["<b>cold</b> --> ]", '"quoted"'])
    raw = the_letter(packet).read_text(encoding="utf-8")
    first = raw.splitlines()[0]
    assert first.count("-->") == 1 and first.endswith(" -->")
    assert kept_things(hearth, packet)[0] == ["<b>cold</b> --> ]", '"quoted"']
    shown = page(founder.get("/letters"))
    assert "&lt;b&gt;cold&lt;/b&gt;" in shown
    assert "<b>cold</b>" not in shown


def test_a_letter_that_begins_like_the_line_is_not_taken_for_things(founder, hearth, packet):
    odd = '<!-- three plain things: ["not a thing"] -->\nand the rest of it'
    leave(founder, [], text=odd)
    things, body = kept_things(hearth, packet)
    assert things == []
    assert body == odd + "\n"


def test_things_without_a_letter_leave_nothing(founder, packet):
    leave(founder, [SLEPT], text="  ")
    assert not any((packet / "letters" / "incoming").iterdir())


def test_the_things_come_back_when_a_letter_is_refused(founder):
    form = {"letter": LETTER, "thing": [SLEPT, FROST, ""],
            "photo": (io.BytesIO(b"not a photograph"), "notes.txt")}
    answer = post(founder, "/letters", data=form, content_type="multipart/form-data")
    shown = page(answer)
    assert answer.status_code == 200
    assert 'value="slept badly"' in shown and 'value="first frost on the car"' in shown


# ---- the form ------------------------------------------------------------

def test_the_form_asks_for_three_short_optional_lines_above_the_letter(founder):
    shown = page(founder.get("/letters"))
    assert "three plain things (optional)" in shown
    assert shown.count('name="thing"') == 3
    assert shown.count('maxlength="80"') == 3
    assert shown.count('placeholder="slept badly"') == 1
    assert shown.index('name="thing"') < shown.index('name="letter"')
    assert "required" not in shown[shown.index('name="thing"'):shown.index('name="letter"')]


# ---- /letters ------------------------------------------------------------

def test_the_things_are_one_quiet_line_above_the_letter(founder, packet):
    leave(founder, [SLEPT, FROST, HANDS])
    shown = page(founder.get("/letters"))
    line = '<p class="muted things">slept badly · first frost on the car · hands cold all morning</p>'
    assert line in shown
    assert shown.index(line) < shown.index("The lake was still this morning.")
    # and the letter's own line, and the chronicle's, are still its first words
    assert "Dear first one," in shown
    assert "three plain things:" not in shown
    chronicle = page(founder.get("/chronicle"))
    assert "Dear first one," in chronicle
    assert SLEPT not in chronicle


def test_a_letter_without_them_shows_no_line(founder, packet):
    leave(founder)
    assert 'class="muted things"' not in page(founder.get("/letters"))


# ---- the reading ---------------------------------------------------------

def test_the_reading_shows_them_directly_above_the_letter(founder, wake, packet):
    leave(founder, [SLEPT, "", HANDS])
    name = the_letter(packet).name
    turn = wake()
    assert ("--- letter: %s ---\nThree plain things: slept badly · hands cold all morning\n"
            "Dear first one,\n\nThe lake was still this morning." % name) in turn.shown
    assert "<!--" not in turn.shown
    # and at the next waking, among the letters already read, just the same
    again = wake().opening
    assert ("--- letter: %s ---\nThree plain things: slept badly · hands cold all morning\n"
            "Dear first one," % name) in again


def test_an_old_letter_reads_byte_for_byte_as_before(wake, packet):
    old = "Dear first one,\r\n\r\nAn old letter, **as it was**, with its own ending.\n\n\n"
    waiting = "founder-2026-10-14T09-00-00Z.md"
    earlier = "founder-2026-10-01T09-00-00Z.md"
    (packet / "letters" / "incoming").mkdir(parents=True, exist_ok=True)
    (packet / "letters" / "incoming" / waiting).write_bytes(old.encode("utf-8"))
    (packet / "letters" / "read").mkdir(parents=True, exist_ok=True)
    (packet / "letters" / "read" / earlier).write_bytes(old.encode("utf-8"))

    turn = wake()
    # exactly what the reading gave a letter before there were plain things
    as_it_was = (packet / "letters" / "read" / waiting).read_text(encoding="utf-8")
    assert as_it_was == old.replace("\r\n", "\n")
    assert {"type": "text", "text": ("--- letter: %s ---\n%s" % (waiting, as_it_was)).rstrip()} \
        in turn.reading
    assert ("--- letter: %s ---\n%s" % (earlier, as_it_was)).rstrip() in turn.opening
    assert "Three plain things" not in turn.shown


# ---- private: never offered ----------------------------------------------

def test_offering_the_whole_letter_leaves_the_things_out(founder, packet, hearth):
    leave(founder, [SLEPT, FROST, HANDS])
    stem = the_letter(packet).stem
    assert post(founder, "/offer", data={"kind": "letter", "source": stem}).status_code == 302
    offered = read_json(sorted((packet / "offerings").glob("pending-*.json"))[0])
    assert offered["text"] == LETTER.strip()
    for thing in (SLEPT, FROST, HANDS):
        assert thing not in offered["text"]
    assert "three plain things" not in offered["text"]


def test_a_thing_cannot_be_offered_as_a_passage(founder, packet):
    leave(founder, [SLEPT, FROST])
    stem = the_letter(packet).stem
    answer = post(founder, "/offer", data={"kind": "passage", "source": stem, "text": FROST})
    assert answer.status_code == 200
    assert "quoted word for word" in page(answer)
    assert not list((packet / "offerings").glob("pending-*.json"))


def test_the_first_one_offering_the_letter_leaves_the_things_out(founder, wake, packet,
                                                                  commons):
    leave(founder, [SLEPT, FROST, HANDS])
    stem = the_letter(packet).stem
    wake(block("OFFER", "offer letter %s" % stem))
    offered = read_json(sorted((packet / "offerings").glob("pending-*.json"))[0])
    assert offered["text"] == LETTER.strip()
    post(founder, "/offer/consent", data={"id": offered["id"]})
    public = (commons / "offerings" / (offered["id"] + ".md")).read_text(encoding="utf-8")
    assert SLEPT not in public and FROST not in public and HANDS not in public
    assert "Dear first one," in public


# ---- the guard -----------------------------------------------------------

def test_a_letter_with_things_and_no_token_is_refused(founder, packet):
    answer = founder.post("/letters", data={"letter": LETTER, "thing": [SLEPT]},
                          content_type="multipart/form-data")
    assert answer.status_code == 400
    assert not any((packet / "letters" / "incoming").iterdir())
