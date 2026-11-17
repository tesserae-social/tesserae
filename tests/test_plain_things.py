"""Three plain things: small true facts of the body and the day, above a letter.

Left on the letters form with the letter, kept in the letter's own file on a
first line of their own, shown above the letter on /letters and in the reading,
and never part of what is offered to the commons. A letter without them reads
exactly as every letter before them did.
"""

import io

import pytest

from conftest import agents_week_not_yet, block, page, post, read_json

LETTER = "Dear first one,\n\nThe lake was still this morning.\n"

SLEPT = "slept badly"
FROST = "first frost on the car"
HANDS = "hands cold all morning"


def leave(client, things=(), text=LETTER):
    """Leave a letter with its things, as the founder's form sends them."""
    form = {"letter": text, "thing": list(things)}
    return post(client, "/letters", data=form, content_type="multipart/form-data")


def the_letter(room):
    """The one letter waiting to be read, as it is kept."""
    left = sorted((room / "letters" / "incoming").glob("*.md"))
    assert len(left) == 1
    return left[0]


def kept_things(hearth, room):
    return hearth.letter_things.split_things(the_letter(room).read_text(encoding="utf-8"))


# ---- saving them ---------------------------------------------------------

@pytest.mark.parametrize("given, kept", [
    ([], []),
    (["", "", ""], []),
    ([SLEPT, "", ""], [SLEPT]),
    (["", FROST, ""], [FROST]),
    ([SLEPT, "", HANDS], [SLEPT, HANDS]),
    ([SLEPT, FROST, HANDS], [SLEPT, FROST, HANDS]),
])
def test_zero_to_three_things_are_kept_with_the_letter(founder, hearth, given, kept, room):
    assert leave(founder, given).status_code == 302
    things, body = kept_things(hearth, room)
    assert things == kept
    assert body == LETTER.strip() + "\n"


def test_a_letter_with_none_is_kept_exactly_as_before(founder, room):
    leave(founder, ["", "  ", ""])
    assert the_letter(room).read_text(encoding="utf-8") == LETTER.strip() + "\n"


def test_the_things_are_one_line_above_the_letter(founder, room):
    leave(founder, [SLEPT, FROST])
    kept = the_letter(room).read_text(encoding="utf-8")
    assert kept == ('<!-- three plain things: ["slept badly", "first frost on the car"] -->\n'
                    + LETTER.strip() + "\n")


def test_no_more_than_three_are_kept(founder, hearth, room):
    leave(founder, [SLEPT, FROST, HANDS, "a fourth"])
    assert kept_things(hearth, room)[0] == [SLEPT, FROST, HANDS]


def test_a_thing_is_cut_at_eighty_characters(founder, hearth, room):
    leave(founder, ["x" * 79, "y" * 80, "z" * 200])
    assert kept_things(hearth, room)[0] == ["x" * 79, "y" * 80, "z" * 80]


def test_newlines_and_control_characters_are_taken_out(founder, hearth, room):
    leave(founder, ["slept\nbadly", "first\r\nfrost on\tthe car", "\x00hands\x07 cold\x1b"])
    assert kept_things(hearth, room)[0] == ["slept badly", "first frost on the car",
                                              "hands cold"]


def test_a_thing_is_plain_text_and_cannot_close_its_line(founder, hearth, room):
    leave(founder, ["<b>cold</b> --> ]", '"quoted"'])
    raw = the_letter(room).read_text(encoding="utf-8")
    first = raw.splitlines()[0]
    assert first.count("-->") == 1 and first.endswith(" -->")
    assert kept_things(hearth, room)[0] == ["<b>cold</b> --> ]", '"quoted"']
    shown = page(founder.get("/rooms/first"))
    assert "&lt;b&gt;cold&lt;/b&gt;" in shown
    assert "<b>cold</b>" not in shown


def test_a_letter_that_begins_like_the_line_is_not_taken_for_things(founder, hearth, room):
    odd = '<!-- three plain things: ["not a thing"] -->\nand the rest of it'
    leave(founder, [], text=odd)
    things, body = kept_things(hearth, room)
    assert things == []
    assert body == odd + "\n"


def test_things_without_a_letter_leave_nothing(founder, room):
    leave(founder, [SLEPT], text="  ")
    assert not any((room / "letters" / "incoming").iterdir())


def test_the_things_come_back_when_a_letter_is_refused(founder):
    form = {"letter": LETTER, "thing": [SLEPT, FROST, ""],
            "photo": (io.BytesIO(b"not a photograph"), "notes.txt")}
    answer = post(founder, "/letters", data=form, content_type="multipart/form-data")
    shown = page(answer)
    assert answer.status_code == 200
    assert 'value="slept badly"' in shown and 'value="first frost on the car"' in shown


# ---- the form ------------------------------------------------------------

def test_the_form_asks_for_three_short_optional_lines_always_in_view(founder):
    shown = page(founder.get("/rooms/first"))
    assert "three plain things (optional)" in shown
    assert shown.count('name="thing"') == 3
    assert shown.count('maxlength="80"') == 3
    # out of the fold since 5 November 2026: below the letter box, under one muted
    # line, and above Send; the photograph, the errand and the commons line stay under "more"
    lines = shown[shown.index('name="letter"'):shown.index('<summary>more</summary>')]
    assert lines.count('name="thing"') == 3
    assert lines.index("A few words is enough. Weeks get full.") < lines.index('name="thing"')
    assert lines.index('name="thing"') < lines.index(">Send</button>")
    assert "placeholder" not in lines and "required" not in lines
    more = shown[shown.index('<summary>more</summary>'):]
    assert 'name="thing"' not in more
    assert more.index('name="photo"') < more.index("</details>")


# ---- /letters ------------------------------------------------------------

def test_the_things_are_one_quiet_line_above_the_letter(founder, packet):
    leave(founder, [SLEPT, FROST, HANDS])
    shown = page(founder.get("/rooms/first"))
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
    assert 'class="muted things"' not in page(founder.get("/rooms/first"))


# ---- the reading ---------------------------------------------------------

def test_the_reading_shows_them_directly_above_the_letter(founder, wake, room):
    leave(founder, [SLEPT, "", HANDS])
    name = the_letter(room).name
    turn = wake()
    assert ("--- letter: %s ---\nThree plain things: slept badly · hands cold all morning\n"
            "Dear first one,\n\nThe lake was still this morning." % name) in turn.shown
    assert "<!--" not in turn.shown
    # and at the next waking, among the letters already read, just the same
    again = wake().opening
    assert ("--- letter: %s ---\nThree plain things: slept badly · hands cold all morning\n"
            "Dear first one," % name) in again


def an_old_letter_waiting_and_read(room):
    old = "Dear first one,\r\n\r\nAn old letter, **as it was**, with its own ending.\n\n\n"
    waiting = "founder-2026-10-14T09-00-00Z.md"
    earlier = "founder-2026-10-01T09-00-00Z.md"
    (room / "letters" / "incoming").mkdir(parents=True, exist_ok=True)
    (room / "letters" / "incoming" / waiting).write_bytes(old.encode("utf-8"))
    (room / "letters" / "read").mkdir(parents=True, exist_ok=True)
    (room / "letters" / "read" / earlier).write_bytes(old.encode("utf-8"))
    return old, waiting, earlier


def test_an_old_letter_reads_byte_for_byte_as_before(wake, room):
    """Since 17 November 2026 the first one reads every room it is in (rooms_reading), and
    a letter that has arrived stands in its room, within the reading's text, where it was a
    block of its own after the study: its words are exactly as they were."""
    old, waiting, earlier = an_old_letter_waiting_and_read(room)
    turn = wake()
    # exactly what the reading gave a letter before there were plain things
    as_it_was = (room / "letters" / "read" / waiting).read_text(encoding="utf-8")
    assert as_it_was == old.replace("\r\n", "\n")
    arrived = ("--- letters that have arrived since your last waking ---\n\n"
               "--- letter: %s ---\n%s" % (waiting, as_it_was)).rstrip()
    assert arrived + "\n\n=== YOUR STUDY" in turn.opening
    assert ("--- letter: %s ---\n%s" % (earlier, as_it_was)).rstrip() in turn.opening
    assert "Three plain things" not in turn.shown


def test_with_rooms_reading_off_an_old_letter_is_a_block_of_its_own(wake, room, attend,
                                                                     monkeypatch):
    """As it was until 17 November 2026, given back by conftest.agents_week_not_yet."""
    agents_week_not_yet(attend, monkeypatch)
    old, waiting, earlier = an_old_letter_waiting_and_read(room)
    turn = wake()
    as_it_was = old.replace("\r\n", "\n")
    assert {"type": "text", "text": ("--- letter: %s ---\n%s" % (waiting, as_it_was)).rstrip()} \
        in turn.reading
    assert ("--- letter: %s ---\n%s" % (earlier, as_it_was)).rstrip() in turn.opening
    assert "Three plain things" not in turn.shown


# ---- the guard -----------------------------------------------------------

def test_a_letter_with_things_and_no_token_is_refused(founder, room):
    answer = founder.post("/letters", data={"letter": LETTER, "thing": [SLEPT]},
                          content_type="multipart/form-data")
    assert answer.status_code == 400
    assert not any((room / "letters" / "incoming").iterdir())
