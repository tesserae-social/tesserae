"""A person's letter as a tile: one a day at most, toned by the part of the day it fell in.

The hearth writes the line when the founder leaves the day's first letter; the
atrium draws it; backfill_letter_tiles.py wrote the lines for the letters left
before the hearth did. What the line may say is fixed: that he wrote, and in
which part of the day. Never a word of the letter, the hour, or to whom.
"""

import datetime
import io

import pytest

import backfill_letter_tiles as backfill
from conftest import FOUNDING_LINE, WORD_LINE, lines_of, page, post, write

LETTER = "Dear first one,\n\nThe heron came back to the lake this morning.\n"


def leave(client, text=LETTER, **form):
    """Leave a letter, as the founder's form does."""
    return post(client, "/letters", data={"letter": text, **form},
                content_type="multipart/form-data")


def letter_lines(commons):
    return [line for line in lines_of(commons / "events.md") if " · letter · " in line]


# ---- the hearth writes one line a day ------------------------------------

def test_the_first_letter_of_the_day_writes_one_line(founder, commons, clock):
    # NOW is 12:00 UTC, eight in the morning where the citizen lives: dawn
    assert leave(founder).status_code == 302
    assert letter_lines(commons) == ["2026-10-15 · letter · the founder wrote a letter at dawn"]
    # and it is added after the lines already there, which stay as they were
    assert lines_of(commons / "events.md")[:2] == [WORD_LINE, FOUNDING_LINE]


def test_a_second_letter_the_same_day_writes_none(founder, commons, clock):
    leave(founder)
    clock.shift(hours=10)          # the evening of the same day there
    leave(founder, text="And again, later.")
    assert letter_lines(commons) == ["2026-10-15 · letter · the founder wrote a letter at dawn"]


def test_a_letter_the_next_day_writes_one(founder, commons, clock):
    leave(founder)
    clock.shift(days=1)
    leave(founder, text="The next morning.")
    assert letter_lines(commons) == [
        "2026-10-15 · letter · the founder wrote a letter at dawn",
        "2026-10-16 · letter · the founder wrote a letter at dawn"]


def test_the_day_is_the_citizen_s_and_not_the_utc_one(founder, commons, clock):
    """Two in the morning UTC is ten the evening before where the citizen lives."""
    clock.set("2026-10-16T02-00-00Z")
    leave(founder)
    assert letter_lines(commons) == ["2026-10-15 · letter · the founder wrote a letter at night"]


# every edge of the four parts, on the citizen's clock: October there is UTC-4
@pytest.mark.parametrize("stamp, said", [
    ("2026-10-15T07-59-59Z", "at night"),          # 03:59
    ("2026-10-15T08-00-00Z", "at dawn"),           # 04:00
    ("2026-10-15T12-59-59Z", "at dawn"),           # 08:59
    ("2026-10-15T13-00-00Z", "during the day"),    # 09:00
    ("2026-10-15T19-59-59Z", "during the day"),    # 15:59
    ("2026-10-15T20-00-00Z", "in the evening"),    # 16:00
    ("2026-10-16T00-59-59Z", "in the evening"),    # 20:59
    ("2026-10-16T01-00-00Z", "at night"),          # 21:00
    ("2026-10-16T03-59-59Z", "at night"),          # 23:59
])
def test_the_part_of_the_day_is_chosen_at_each_edge(founder, commons, clock, stamp, said):
    clock.set(stamp)
    leave(founder)
    assert letter_lines(commons) == ["2026-10-15 · letter · the founder wrote a letter %s" % said]


def test_the_part_is_the_first_letter_s_and_a_later_one_does_not_change_it(founder, commons,
                                                                           clock):
    clock.set("2026-10-15T14-00-00Z")   # ten in the morning there
    leave(founder)
    clock.set("2026-10-16T02-00-00Z")   # ten at night, the same day there
    leave(founder, text="Goodnight.")
    assert letter_lines(commons) == [
        "2026-10-15 · letter · the founder wrote a letter during the day"]


def photo_bytes():
    from PIL import Image
    kept = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 90, 48)).save(kept, "JPEG")
    return kept.getvalue()


@pytest.mark.parametrize("how", ["plain", "photo", "errand", "proposes"])
def test_every_kind_of_letter_writes_the_line_and_nothing_of_itself(founder, commons,
                                                                   clock, how, room):
    form = {}
    if how == "photo":
        form["photo"] = (io.BytesIO(photo_bytes()), "lake.jpg")
    if how == "errand":
        write(room / "errands" / "errand-2026-10-14T09-00-00Z.md", "Tell me about the heron.\n")
        form["errand"] = "errand-2026-10-14T09-00-00Z.md"
    if how == "proposes":
        form["proposes"] = "1"
    assert leave(founder, **form).status_code == 302

    events = (commons / "events.md").read_text(encoding="utf-8")
    assert letter_lines(commons) == ["2026-10-15 · letter · the founder wrote a letter at dawn"]
    # nothing of what the letter said, when it was left, or what came with it
    for word in ("heron", "lake", "Dear", "first one,", "photo", "errand", "bond", "jpg"):
        assert word not in events.split(FOUNDING_LINE)[1], word
    assert clock.stamp() not in events and "T12" not in events and ":" not in events
    # the one line it wrote is the whole of what was added
    assert events == "%s\n%s\n%s\n" % (WORD_LINE, FOUNDING_LINE, letter_lines(commons)[0])


def test_a_letter_that_is_refused_writes_no_line(founder, commons):
    post(founder, "/letters", data={"letter": LETTER,
                                    "photo": (io.BytesIO(b"not a photo"), "x.jpg")},
         content_type="multipart/form-data")
    assert letter_lines(commons) == []


def test_a_line_the_backfill_wrote_counts_as_the_day_s_line(founder, commons, hearth):
    with (commons / "events.md").open("a", encoding="utf-8") as record:
        record.write("2026-10-15 · letter · the founder wrote a letter at night\n")
    leave(founder)
    assert letter_lines(commons) == ["2026-10-15 · letter · the founder wrote a letter at night"]


# ---- his own line beside it ------------------------------------------------

BESIDE = "the first frost, and coffee on the step"
FIELD = 'name="commons_line"'
CLOSED = "Today's letter tile is already written; a line goes"


def left(room):
    return sorted((room / "letters" / "incoming").glob("founder-*.md"))


def test_a_line_beside_the_first_letter_of_the_day_is_written_with_it(founder, commons, room,
                                                                     screen):
    assert leave(founder, commons_line="  %s  " % BESIDE).status_code == 302
    assert letter_lines(commons) == [
        "2026-10-15 · letter · the founder wrote a letter at dawn · %s" % BESIDE]
    # only the line was screened, and nothing of it is in the letter
    assert [text for text, _ in screen.asked] == [BESIDE]
    (letter,) = left(room)
    assert BESIDE not in letter.read_text(encoding="utf-8")


def test_no_word_of_the_letter_goes_into_the_line(founder, commons):
    leave(founder, commons_line=BESIDE)
    events = (commons / "events.md").read_text(encoding="utf-8")
    for word in ("heron", "lake", "Dear"):
        assert word not in events, word


def test_with_no_line_the_letter_line_is_as_it_was(founder, commons, screen):
    leave(founder, commons_line="   ")
    assert letter_lines(commons) == ["2026-10-15 · letter · the founder wrote a letter at dawn"]
    assert screen.asked == []


def test_the_field_is_offered_only_while_today_has_no_letter_tile(founder, clock):
    said = page(founder.get("/rooms/first"))
    assert FIELD in said and CLOSED not in said
    leave(founder)
    said = page(founder.get("/rooms/first"))
    assert FIELD not in said and CLOSED in said
    clock.shift(days=1)
    assert FIELD in page(founder.get("/rooms/first"))


def test_a_line_with_a_second_letter_the_same_day_leaves_nothing(founder, commons, room, clock):
    leave(founder)
    clock.shift(hours=1)
    answer = leave(founder, text="And again.", commons_line=BESIDE)
    assert answer.status_code == 200
    said = page(answer)
    assert "a line goes with the first letter of a day. Nothing was left." in said
    assert "And again." in said and BESIDE in said  # all that was typed comes back
    assert len(left(room)) == 1
    assert letter_lines(commons) == ["2026-10-15 · letter · the founder wrote a letter at dawn"]


def test_a_line_still_counts_as_the_day_s_line(founder, commons):
    leave(founder, commons_line=BESIDE)
    leave(founder, text="And again, later.")
    assert len(letter_lines(commons)) == 1


@pytest.mark.parametrize("says, told", [
    ("YES", "The line for the commons seemed to contain a name or a place; nothing was left."),
    (RuntimeError("the screen is down"),
     "This couldn&#39;t be checked just now; nothing was published. Please try again later."),
    ("Maybe", "This couldn&#39;t be checked just now; nothing was published. Please try again "
              "later.")])
def test_a_line_the_screen_does_not_pass_leaves_no_letter_and_keeps_every_draft(
        founder, commons, room, screen, says, told):
    screen.says = says
    answer = leave(founder, commons_line=BESIDE, thing=["cold hands", "", ""])
    assert answer.status_code == 200
    said = page(answer)
    assert told in said
    assert "The heron came back to the lake this morning." in said
    assert 'value="%s"' % BESIDE in said and 'value="cold hands"' in said
    assert left(room) == [] and letter_lines(commons) == []


def test_a_line_longer_than_240_characters_leaves_nothing_and_is_never_screened(
        founder, commons, room, screen):
    answer = leave(founder, commons_line="a" * 241)
    assert "The line for the commons is longer than 240 characters; nothing was left." in page(
        answer)
    assert left(room) == [] and letter_lines(commons) == [] and screen.asked == []
    leave(founder, commons_line="a" * 240)
    assert letter_lines(commons)[0].endswith(" · " + "a" * 240)


def test_a_line_with_a_protected_word_leaves_nothing(founder, commons, room, data_dir, screen):
    write(data_dir / "private-words.txt", "Quillon => the founder\n")
    answer = leave(founder, commons_line="Quillon on the step")
    assert ("The line for the commons seemed to contain a name or a place; nothing was left."
            in page(answer))
    assert left(room) == [] and letter_lines(commons) == [] and screen.asked == []


# ---- the atrium draws it -------------------------------------------------

@pytest.mark.parametrize("said, part", [
    ("at dawn", "dawn"), ("during the day", "day"),
    ("in the evening", "evening"), ("at night", "night"),
])
def test_a_letter_line_is_a_tile_toned_by_its_part_of_the_day(atrium, said, part):
    events = atrium.parse_events("2026-10-15 · letter · the founder wrote a letter %s\n" % said)
    assert events == [(datetime.date(2026, 10, 15), "letter",
                       "the founder wrote a letter %s" % said)]
    tiles = atrium.tiles_from(events, [])
    assert tiles == [(datetime.date(2026, 10, 15), "tile-letter tile-letter-%s" % part,
                      "15 October 2026 · the founder wrote a letter %s" % said, "")]
    cells = atrium.slots(tiles, datetime.date(2026, 10, 15))
    drawn = "".join(atrium.frame_block(cells))
    assert ('<li class="tile-letter tile-letter-%s" title="15 October 2026 · the founder '
            'wrote a letter %s" tabindex="0"></li>' % (part, said)) in drawn
    assert atrium.reading_text(cells) == "15 October 2026 · the founder wrote a letter %s" % said


def test_a_letter_line_with_his_line_beside_it_is_still_toned_and_still_the_day_s_line(atrium):
    said = "2026-10-15 · letter · the founder wrote a letter at dawn · %s\n" % BESIDE
    events = atrium.parse_events(said)
    assert events == [(datetime.date(2026, 10, 15), "letter",
                       "the founder wrote a letter at dawn · %s" % BESIDE)]
    (_, kind, words), = events
    assert atrium.letter_band(words) == "dawn" and atrium.is_letter_line(kind, words)
    tiles = atrium.tiles_from(events, [])
    assert tiles == [(datetime.date(2026, 10, 15), "tile-letter tile-letter-dawn",
                      "15 October 2026 · the founder wrote a letter at dawn · %s" % BESIDE, "")]
    # a line naming no part, with words beside it, is a letter line too
    assert atrium.is_letter_line("letter", "the founder wrote a letter · %s" % BESIDE)
    # and words that only begin like one are not
    assert not atrium.is_letter_line("letter", "the founder wrote a letter at dawnish")


def test_a_letter_line_naming_no_part_is_still_a_letter_tile(atrium):
    tiles = atrium.tiles_from(atrium.parse_events(
        "2026-10-15 · letter · the founder wrote a letter\n"), [])
    assert tiles[0][1] == "tile-letter"


def test_the_four_sands_are_in_the_stylesheet_pale_to_dark(atrium):
    from test_atrium import STYLE, stylesheet
    rules = stylesheet(STYLE)
    fills = {part: rules[".tile-letter-%s" % part]["background"]
             for part in ("dawn", "evening", "night")}
    assert fills == {"dawn": "#EEE5D5", "evening": "#C4AE88", "night": "#97805A"}
    shared = rules[".tile-letter, .tile-letter-dawn, .tile-letter-day, .tile-letter-evening"]
    assert shared == {"background": "#DDCDB0", "border": "1px solid #97805A"}
    assert rules[".tile-letter-night"]["border"] == "1px solid #6F5C3E"


# ---- the backfill --------------------------------------------------------

EVENTS = ("2026-09-02 · word · the word was published\n"
          "2026-09-04 · founding · the first one was founded\n"
          "2026-09-20 · event · the tide paused\n"
          "a note in the file that is no line at all\n"
          "2026-09-21 · event · a line was taken off the bench\n"
          "2026-09-25 · event · the tide resumed\n")


def letters_at(room, folder, *stamps):
    for stamp in stamps:
        write(room / "letters" / folder / ("founder-%s.md" % stamp), "private words\n")


@pytest.fixture
def old_letters(room):
    """Letters left before the hearth wrote lines for them, as the host holds them."""
    # 19 September there: 19:11 is evening, and the later ones that night do not change it
    letters_at(room, "read", "2026-09-19T23-11-43Z", "2026-09-20T02-47-15Z",
               "2026-09-20T03-30-09Z")
    # 20 September there: 11:36 by day; one of them found in both folders
    letters_at(room, "read", "2026-09-20T15-36-32Z", "2026-09-20T20-34-37Z")
    letters_at(room, "incoming", "2026-09-20T20-34-37Z", "2026-09-21T00-22-30Z")
    # 21 September there: 15:19, by day; with a photograph beside it, which is not a letter
    letters_at(room, "incoming", "2026-09-21T19-19-54Z")
    write(room / "letters" / "incoming" / "founder-2026-09-21T19-19-54Z.jpg", "jpeg")
    # 23 September there: 05:00, dawn; one named -2, left in the same second as another
    letters_at(room, "incoming", "2026-09-23T09-00-00Z-2")
    # 27 September there, past every line in the file: 22:00, night
    letters_at(room, "incoming", "2026-09-28T02-00-00Z")
    # the first one's letters are not the founder's, and are passed over
    letters_at(room, "outgoing", "2026-09-22T12-00-00Z")
    write(room / "letters" / "outgoing" / "to-founder-2026-09-22T12-00-00Z.md", "hello\n")
    return room / "letters"


def run(commons, letters, capsys):
    added = backfill.main(str(commons / "events.md"), str(letters))
    return added, capsys.readouterr().out


def test_the_backfill_adds_the_right_days_in_order(commons, old_letters, capsys):
    write(commons / "events.md", EVENTS)
    added, said = run(commons, old_letters, capsys)
    assert added == 5 and said == "5\n"
    assert (commons / "events.md").read_text(encoding="utf-8").splitlines() == [
        "2026-09-02 · word · the word was published",
        "2026-09-04 · founding · the first one was founded",
        "2026-09-19 · letter · the founder wrote a letter in the evening",
        "2026-09-20 · event · the tide paused",
        "a note in the file that is no line at all",
        "2026-09-20 · letter · the founder wrote a letter during the day",
        "2026-09-21 · event · a line was taken off the bench",
        "2026-09-21 · letter · the founder wrote a letter during the day",
        "2026-09-23 · letter · the founder wrote a letter at dawn",
        "2026-09-25 · event · the tide resumed",
        "2026-09-27 · letter · the founder wrote a letter at night",
    ]


def test_the_backfill_keeps_every_original_line_in_its_order(commons, old_letters, capsys):
    write(commons / "events.md", EVENTS)
    run(commons, old_letters, capsys)
    after = (commons / "events.md").read_text(encoding="utf-8").splitlines()
    before = EVENTS.splitlines()
    kept = [line for line in after if line in before]
    assert kept == before                       # all of them, in the same relative order
    assert [line for line in after if line not in before] == [
        line for line in after if " · letter · " in line]  # and nothing new but letter lines


def test_the_backfill_is_safe_to_run_twice(commons, old_letters, capsys):
    write(commons / "events.md", EVENTS)
    run(commons, old_letters, capsys)
    once = (commons / "events.md").read_bytes()
    added, said = run(commons, old_letters, capsys)
    assert added == 0 and said == "0\n"
    assert (commons / "events.md").read_bytes() == once


def test_the_backfill_passes_over_a_day_that_has_its_line(commons, old_letters, capsys):
    write(commons / "events.md",
          EVENTS + "2026-09-21 · letter · the founder wrote a letter at night\n")
    added, _ = run(commons, old_letters, capsys)
    assert added == 4
    days = [line[:10] for line in lines_of(commons / "events.md") if " · letter · " in line]
    assert days.count("2026-09-21") == 1
    assert "2026-09-21 · letter · the founder wrote a letter at night" in lines_of(
        commons / "events.md")


def test_the_backfill_keeps_the_file_s_own_line_endings_and_mark(commons, old_letters, capsys):
    crlf = "﻿" + EVENTS.replace("\n", "\r\n").rstrip("\r\n")   # and no last newline
    (commons / "events.md").write_bytes(crlf.encode("utf-8"))
    run(commons, old_letters, capsys)
    raw = (commons / "events.md").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert "\n" not in text.replace("\r\n", "")
    assert "2026-09-25 · event · the tide resumed\r\n2026-09-27 · letter" in text


def test_the_backfill_reads_nothing_of_a_letter_but_its_name(commons, old_letters, capsys):
    write(commons / "events.md", EVENTS)
    run(commons, old_letters, capsys)
    assert "private words" not in (commons / "events.md").read_text(encoding="utf-8")


def test_with_no_letters_the_backfill_adds_nothing(commons, capsys, room):
    write(commons / "events.md", EVENTS)
    added, said = run(commons, room / "letters", capsys)
    assert added == 0 and said == "0\n"
    assert (commons / "events.md").read_text(encoding="utf-8") == EVENTS
