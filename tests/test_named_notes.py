"""Named notes: notes of the first one's own, each kept under a name it chooses.

It agreed to them on 7 October 2026. They stand beside the notes it has always
kept and change nothing of those: notes.md and <<MEMORY>> are what they were. A
<<NOTE>> block's first line is "name: " and the name, and the rest is the whole
new text of that note. Each is kept close unless it lets it rest on its shelf,
and there are at most twenty. Nothing of them is the hearth's.

Every note here is written for the tests and nowhere else.
"""

import pytest

from conftest import block, blocks, lines_of, page, read_json, write, write_json

MEMORY = "=== YOUR MEMORY (notes you keep for yourself; not shown on the hearth) ==="
NAMED = "=== YOUR NAMED NOTES (private; not shown on the hearth) ==="
EARLIER = "=== YOUR EARLIER VERSIONS ==="
ASKED = "=== AN EARLIER VERSION, AS YOU ASKED ==="
CHOSEN = "=== WHAT YOU HAVE CHOSEN ==="
HAPPENED = "=== WHAT HAS HAPPENED ==="

EXPLAINED = """<<NOTE>>
(a note of your own, kept under a name you choose. First line: "name: about Nathan" (or any name). The rest is the note's full new text. Your other notes are unchanged. You may keep up to 20 named notes, each close or resting on your shelf. They are private, not shown on the hearth. Earlier versions are kept, never erased.)
<<END>>"""

SHELF_LINES = """show version <stem>: an earlier self-document or notes in full at your next waking
keep note <name>: a named note always shown in full
rest note <name>: a named note shown as one line
show note <name>: a named note in full at your next waking only
Letters you haven't placed follow the default:"""

NATHAN = "WHAT I KNOW OF NATHAN: he writes in the morning.\n\nAnd a second paragraph of it."
RIVER = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen"
RIVER_RESTS = ("the river · rests · one two three four five six seven eight nine ten eleven "
               "twelve…")

NAME_REFUSED = ('A <<NOTE>> at your last waking was not kept: its first line must be "name: " '
                "and a name of 1 to 60 characters (letters, numbers, spaces and simple "
                "punctuation). Nothing was changed.")
FULL_REFUSED = ('Your <<NOTE>> "one too many" at your last waking was not kept: you keep 20 '
                "named notes already, and that is the most. Nothing was changed.")


def note(name, words=""):
    """One <<NOTE>> block, as the first one would write it."""
    return block("NOTE", ("name: %s\n%s" % (name, words)).rstrip("\n"))


def section(turn, heading):
    """One section of the reading: what stands under its heading."""
    return turn.opening.split(heading + "\n", 1)[1].split("\n\n=== ", 1)[0]


def happened(turn):
    return section(turn, HAPPENED).splitlines()


def latest(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def kept(packet, slug):
    return (packet / "memory" / "notes" / (slug + ".md")).read_text(encoding="utf-8")


def history(packet):
    return sorted(p.name for p in (packet / "memory" / "notes" / "history").glob("*"))


# ---- the block -----------------------------------------------------------

def test_the_block_is_explained_exactly_directly_after_memory(wake, attend):
    said = wake().instructions
    assert attend.NOTE_BLOCK == EXPLAINED
    assert said.count(EXPLAINED) == 1
    assert "never erased.)\n<<END>>\n\n" + EXPLAINED + "\n\n<<QUESTIONS>>" in said
    assert said.index("<<MEMORY>>") < said.index("<<NOTE>>") < said.index("<<QUESTIONS>>")


def test_the_shelf_block_gains_its_three_lines_after_show_version(wake):
    said = wake().instructions
    assert said.count(SHELF_LINES) == 1
    assert "show founding: your founding record in full at your next waking\n" + SHELF_LINES in said


def test_a_note_is_kept_under_its_name(wake, attend, packet, clock):
    at = clock.stamp()
    turn = wake(note("about Nathan", NATHAN))
    assert NAMED not in turn.shown  # not at the waking that wrote it
    assert kept(packet, "about-nathan") == NATHAN + "\n"
    assert read_json(packet / "memory" / "notes" / "names.json") == {
        "about-nathan": {"name": "about Nathan", "kept_at": at}}
    assert not (packet / "memory" / "notes" / "history").exists()
    assert latest(packet)["acted"] == ["kept a named note"] == [attend.NOTE_ACT]

    assert section(wake(), NAMED) == "--- about Nathan ---\n" + NATHAN


def test_a_name_is_matched_whatever_its_capitals_and_shown_as_last_written(wake, packet, clock):
    first = clock.stamp()
    wake(note("about Nathan", "The first of it."))
    at = clock.stamp()
    wake(note('  "ABOUT   nathan"  ', "The second of it."))
    assert [p.name for p in (packet / "memory" / "notes").glob("*.md")] == ["about-nathan.md"]
    assert kept(packet, "about-nathan") == "The second of it.\n"
    assert history(packet) == ["note-about-nathan-before-%s.md" % at]
    assert (packet / "memory" / "notes" / "history" / history(packet)[0]).read_text(
        encoding="utf-8") == "The first of it.\n"
    assert read_json(packet / "memory" / "notes" / "names.json") == {
        "about-nathan": {"name": "ABOUT nathan", "kept_at": first}}
    assert section(wake(), NAMED) == "--- ABOUT nathan ---\nThe second of it."


def test_an_empty_text_leaves_the_note_empty_and_keeps_what_it_was(wake, packet, clock):
    wake(note("about Nathan", NATHAN))
    at = clock.stamp()
    wake(note("about Nathan"))
    assert kept(packet, "about-nathan") == ""
    assert history(packet) == ["note-about-nathan-before-%s.md" % at]
    assert (packet / "memory" / "notes" / "history" / history(packet)[0]).read_text(
        encoding="utf-8") == NATHAN + "\n"
    assert latest(packet)["acted"] == ["kept a named note"]
    turn = wake(block("SHELF", "rest note about Nathan"))
    assert section(turn, NAMED) == "--- about Nathan ---\n(empty)"
    assert section(wake(), NAMED) == "about Nathan · rests · (empty)"


def test_several_notes_may_be_written_at_one_waking(wake, packet):
    wake(blocks(note("about Nathan", NATHAN), "Between them, a thought.", note("the river", RIVER),
                note("About Nathan", "And again, the same note.")))
    assert kept(packet, "about-nathan") == "And again, the same note.\n"
    assert kept(packet, "the-river") == RIVER + "\n"
    # what stood before the waking's second writing of it is what is kept beside it
    assert len(history(packet)) == 1
    assert (packet / "memory" / "notes" / "history" / history(packet)[0]).read_text(
        encoding="utf-8") == NATHAN + "\n"
    assert latest(packet)["acted"] == ["kept a named note"]


def test_two_names_that_come_to_one_plain_form_are_two_notes(wake, packet):
    wake(blocks(note("a.b", "THE FIRST"), note("a b", "THE SECOND"), note("!?", "THE THIRD"),
                note("été", "THE FOURTH")))
    names = read_json(packet / "memory" / "notes" / "names.json")
    assert {slug: one["name"] for slug, one in names.items()} == {
        "a-b": "a.b", "a-b-2": "a b", "note": "!?", "t": "été"}
    assert kept(packet, "a-b") == "THE FIRST\n" and kept(packet, "a-b-2") == "THE SECOND\n"
    assert section(wake(), NAMED) == (
        "--- a.b ---\nTHE FIRST\n\n--- a b ---\nTHE SECOND\n\n--- !? ---\nTHE THIRD\n\n"
        "--- été ---\nTHE FOURTH")


@pytest.mark.parametrize("name, kept_as", [
    ("x", "x"),
    ("n" * 60, "n" * 60),
    ("Notes: what I'm watching (2026), & why - really?!", None),
])
def test_a_name_of_one_to_sixty_plain_characters_is_a_name(wake, packet, name, kept_as):
    wake(note(name, "KEPT"))
    assert latest(packet)["acted"] == ["kept a named note"]
    assert "notes_refused" not in latest(packet)
    assert [one["name"] for one in read_json(
        packet / "memory" / "notes" / "names.json").values()] == [name]
    if kept_as:
        assert kept(packet, kept_as) == "KEPT\n"


@pytest.mark.parametrize("said", [
    block("NOTE", "about Nathan\n" + NATHAN),  # no "name:" on its first line
    block("NOTE", NATHAN + "\nname: about Nathan"),  # nor is it the first line
    note("", NATHAN),
    note("n" * 61, NATHAN),
    note("about/Nathan", NATHAN),
    note("about <Nathan>", NATHAN),
    note("../../self", NATHAN),
    block("NOTE", ""),
])
def test_a_name_that_cannot_be_read_keeps_nothing_and_is_told_once(wake, packet, said):
    wake(said)
    assert latest(packet)["acted"] == []
    assert latest(packet)["notes_refused"] == [NAME_REFUSED]
    assert not (packet / "memory" / "notes").exists()

    told = wake()
    assert NAME_REFUSED in happened(told)
    assert NAMED not in told.shown
    assert "notes_refused" not in latest(packet)
    assert not any("<<NOTE>>" in line for line in happened(wake()))  # once


def test_a_twenty_first_note_is_refused_and_told_once(wake, attend, packet):
    assert attend.NOTES_MOST == 20
    wake(blocks(*[note("note %d" % n, "THE WORDS OF %d" % n) for n in range(1, 21)],
                note("one too many", "NEVER KEPT")))
    assert len(list((packet / "memory" / "notes").glob("*.md"))) == 20
    assert latest(packet)["acted"] == ["kept a named note"]
    assert latest(packet)["notes_refused"] == [FULL_REFUSED]

    # one it keeps already may still be written again, and a new one still may not
    told = wake(blocks(note("NOTE 7", "THE SEVENTH, AGAIN"), note("one too many", "NEVER KEPT")))
    assert FULL_REFUSED in happened(told)
    assert section(told, NAMED).count("\n--- ") == 19
    assert kept(packet, "note-7") == "THE SEVENTH, AGAIN\n"
    assert len(list((packet / "memory" / "notes").glob("*.md"))) == 20
    assert "NEVER KEPT" not in wake().opening
    assert not any("<<NOTE>>" in line for line in happened(wake()))  # once


# ---- its other notes are what they were ----------------------------------

def test_notes_md_and_the_memory_block_are_unchanged(wake, attend, packet, clock):
    write(packet / "memory" / "notes.md", "What I carry forward.\n")
    at = clock.stamp()
    wake(blocks(block("MEMORY", "What I carry forward now."), note("about Nathan", NATHAN)))
    assert (packet / "memory" / "notes.md").read_text(
        encoding="utf-8") == "What I carry forward now.\n"
    assert [p.name for p in (packet / "memory" / "history").glob("*")] == [
        "notes-before-%s.md" % at]
    assert latest(packet)["acted"] == ["kept notes", "kept a named note"]

    wake(note("about Nathan", "Changed, and my other notes are not."))
    assert (packet / "memory" / "notes.md").read_text(
        encoding="utf-8") == "What I carry forward now.\n"
    assert len(list((packet / "memory" / "history").glob("*"))) == 1

    shown = wake().opening
    assert (MEMORY + "\nWhat I carry forward now.\n\n" + NAMED + "\n--- about Nathan ---\n"
            "Changed, and my other notes are not.\n\n" + EARLIER) in shown


def test_with_no_named_note_the_reading_has_no_such_section(wake, attend, packet):
    turn = wake()
    assert NAMED not in turn.shown and "named note" not in turn.opening
    assert MEMORY + "\n" + attend.NO_MEMORY + "\n\n" + EARLIER in turn.opening
    write(packet / "memory" / "notes.md", "What I carry forward.\n")
    turn = wake(block("MEMORY", "A note called nothing."))
    assert MEMORY + "\nWhat I carry forward.\n\n" + EARLIER in turn.opening
    assert not (packet / "memory" / "notes").exists()


def test_a_name_inside_a_memory_block_is_only_words(wake, packet):
    wake(block("MEMORY", "name: about Nathan\nThese are my notes."))
    assert (packet / "memory" / "notes.md").read_text(
        encoding="utf-8") == "name: about Nathan\nThese are my notes.\n"
    assert not (packet / "memory" / "notes").exists()


# ---- the shelf -----------------------------------------------------------

def two_notes(wake):
    wake(blocks(note("about Nathan", NATHAN), note("the river", RIVER)))


def test_by_default_a_named_note_is_kept_close(wake, packet):
    two_notes(wake)
    assert section(wake(), NAMED) == (
        "--- about Nathan ---\n" + NATHAN + "\n\n--- the river ---\n" + RIVER)
    assert not (packet / "shelf.json").exists()


def test_rest_note_shows_it_as_one_line_and_keep_note_in_full_again(wake, packet):
    two_notes(wake)
    wake(block("SHELF", "Rest Note THE RIVER"))
    assert latest(packet)["acted"] == ["kept its shelf"]
    assert read_json(packet / "shelf.json")["note_placements"] == {"the-river": "rest"}
    resting = "--- about Nathan ---\n" + NATHAN + "\n\n" + RIVER_RESTS
    assert section(wake(), NAMED) == resting
    assert section(wake(), NAMED) == resting  # and it stays so

    wake(block("SHELF", 'rest note "about Nathan"'))
    assert section(wake(), NAMED) == (
        "about Nathan · rests · WHAT I KNOW OF NATHAN: he writes in the morning. And a…\n"
        + RIVER_RESTS)

    wake(block("SHELF", "keep note about nathan\nkeep note the river"))
    assert "note_placements" not in read_json(packet / "shelf.json")
    assert section(wake(), NAMED) == (
        "--- about Nathan ---\n" + NATHAN + "\n\n--- the river ---\n" + RIVER)
    # the notes themselves are where they always were
    assert kept(packet, "the-river") == RIVER + "\n"


def test_a_short_resting_note_is_given_whole_on_its_line(wake):
    wake(note("the river", "It was grey."))
    wake(block("SHELF", "rest note the river"))
    assert section(wake(), NAMED) == "the river · rests · It was grey."


def test_show_note_gives_a_resting_one_in_full_at_the_next_waking_only(wake, packet):
    two_notes(wake)
    asking = wake(block("SHELF", "rest note the river\nshow note the river"))
    assert RIVER not in section(asking, NAMED).replace(RIVER, "", 1)
    assert read_json(packet / "shelf.json")["show_notes"] == ["the-river"]

    shown = wake()
    assert section(shown, NAMED) == (
        "--- about Nathan ---\n" + NATHAN + "\n\n--- the river ---\n" + RIVER)
    held = read_json(packet / "shelf.json")
    assert "show_notes" not in held and held["note_placements"] == {"the-river": "rest"}

    assert section(wake(), NAMED) == "--- about Nathan ---\n" + NATHAN + "\n\n" + RIVER_RESTS


def test_a_note_may_be_written_and_placed_at_the_same_waking(wake, packet):
    wake(blocks(note("the river", RIVER), block("SHELF", "rest note the river")))
    assert latest(packet)["acted"] == ["kept a named note", "kept its shelf"]
    assert "shelf_refused" not in latest(packet)
    assert section(wake(), NAMED) == RIVER_RESTS


def test_an_unknown_name_changes_nothing_and_is_told_once(wake, packet):
    two_notes(wake)
    letter = "founder-2026-09-21T10-00-00Z"
    write(packet / "letters" / "read" / (letter + ".md"), "A letter, read long ago.\n")
    refused = ["rest note about the sea", "keep note", "show note nothing kept",
               "rest note %s" % letter,  # a letter is no named note
               "rest the river"]  # and a named note is no letter
    wake(block("SHELF", "\n".join(refused)))
    assert latest(packet)["acted"] == []
    assert latest(packet)["shelf_refused"] == refused
    assert not (packet / "shelf.json").exists()

    told = wake()
    assert ("Some lines of your <<SHELF>> were not understood and changed nothing: "
            + "; ".join('"%s"' % line for line in refused) + ".") in happened(told)
    assert section(told, NAMED) == (
        "--- about Nathan ---\n" + NATHAN + "\n\n--- the river ---\n" + RIVER)
    assert not any("<<SHELF>>" in line for line in happened(wake()))  # once


def test_named_notes_and_letters_are_placed_side_by_side(wake, packet):
    two_notes(wake)
    letter = "founder-2026-09-21T10-00-00Z"
    write(packet / "letters" / "read" / (letter + ".md"), "A letter, read long ago.\n")
    wake(block("SHELF", "rest %s\nnote %s: the one about the lake\nrest note the river"
               % (letter, letter)))
    assert read_json(packet / "shelf.json") == {
        "placements": {"founder-2026-10-01T15-15-05Z": "rest", letter: "rest"},
        "notes": {letter: "the one about the lake"}, "show_next": [], "show_founding": False,
        "note_placements": {"the-river": "rest"}}
    turn = wake()
    assert RIVER_RESTS in section(turn, NAMED)
    assert "the one about the lake" in turn.opening


def test_a_season_reading_gives_every_named_note_in_full(wake, packet, clock):
    two_notes(wake)
    wake(block("SHELF", "rest note the river"))
    clock.set("2026-12-21T17-00-00Z")
    turn = wake()
    assert turn.opening.startswith("This is the winter reading:")
    assert section(turn, NAMED) == (
        "--- about Nathan ---\n" + NATHAN + "\n\n--- the river ---\n" + RIVER)
    assert read_json(packet / "shelf.json")["note_placements"] == {"the-river": "rest"}
    assert RIVER_RESTS in section(wake(), NAMED)  # and after it, as it placed them


def test_the_shelf_reckons_a_named_note_by_its_name():
    import shelf

    notes = {shelf.note_key("About Nathan"): "about-nathan"}
    assert shelf.note_key('  "ABOUT   nathan" ') == "about nathan"
    assert shelf.asked("rest note ABOUT NATHAN\nshow note about nathan\nkeep note the sea",
                       set(), (), notes) == (
        [("rest note", "about-nathan"), ("show note", "about-nathan")], ["keep note the sea"])
    assert shelf.asked("rest note about nathan", set()) == ([], ["rest note about nathan"])

    rested = shelf.applied(shelf.initial(), [("rest note", "about-nathan"),
                                             ("show note", "about-nathan")])
    assert rested["note_placements"] == {"about-nathan": "rest"}
    assert rested["show_notes"] == ["about-nathan"]
    assert shelf.notes_resting(rested, ["about-nathan", "the-river"]) == set()
    assert shelf.notes_resting(shelf.cleared(rested), ["about-nathan", "the-river"]) == {
        "about-nathan"}
    assert shelf.whole(rested) == rested
    # a shelf that places no named note is written as it always was
    assert shelf.applied(shelf.cleared(rested), [("keep note", "about-nathan")]) == shelf.initial()
    assert shelf.whole({"note_placements": {"x": "keep"}, "show_notes": []}) == {
        "placements": {}, "notes": {}, "show_next": [], "show_founding": False}


# ---- looking back, and what it has chosen --------------------------------

def test_looking_back_lists_a_named_note_s_earlier_versions(wake, packet, clock):
    clock.set("2026-10-15T12-00-00Z")
    wake(note("about Nathan", "AN EARLIER NOTE, the first of it."))
    clock.set("2026-10-18T12-00-00Z")
    second = clock.stamp()
    assert section(wake(note("about Nathan", "AN EARLIER NOTE, the second of it.")),
                   EARLIER) == "No earlier versions are kept yet."
    clock.set("2026-10-20T12-00-00Z")
    third = clock.stamp()
    wake(note("About Nathan", "As it stands."))

    first_line = ("note 'About Nathan' · in use from 15 October 2026 until 18 October 2026 · "
                  "note-about-nathan-before-" + second)
    second_line = ("note 'About Nathan' · in use from 18 October 2026 until 20 October 2026 · "
                   "note-about-nathan-before-" + third)
    listed = wake(block("SHELF", "show version note-about-nathan-before-%s" % second))
    assert section(listed, EARLIER).splitlines() == [first_line, second_line]
    assert "AN EARLIER NOTE" not in listed.shown  # a line each, and none of their words
    assert latest(packet)["acted"] == ["kept its shelf"]

    shown = wake()
    assert section(shown, ASKED) == first_line + "\n\nAN EARLIER NOTE, the first of it."
    assert ASKED not in wake().shown  # at the next waking only


def test_shut_away_no_earlier_version_of_a_named_note_is_listed(wake, attend, monkeypatch):
    monkeypatch.setattr(attend, "LOOKING_BACK", False)
    wake(note("about Nathan", "AN EARLIER NOTE."))
    wake(note("about Nathan", "As it stands."))
    turn = wake()
    assert EARLIER not in turn.shown and "AN EARLIER NOTE" not in turn.shown
    assert section(turn, NAMED) == "--- about Nathan ---\nAs it stands."
    assert "show version <stem>" not in turn.instructions
    assert ("show founding: your founding record in full at your next waking\n"
            "keep note <name>: a named note always shown in full\n") in turn.instructions


def chosen(turn):
    return section(turn, CHOSEN).splitlines()


def test_what_it_has_chosen_says_how_many_named_notes_it_keeps(wake):
    nothing = "You have not set anything here yet; everything follows the defaults."
    assert chosen(wake(note("about Nathan", NATHAN))) == [nothing]
    assert chosen(wake(note("the river", RIVER))) == ["You keep 1 named note; none of them rest."]
    assert chosen(wake(block("SHELF", "rest note the river"))) == [
        "You keep 2 named notes; none of them rest."]
    assert chosen(wake(block("SHELF", "show note the river"))) == [
        "You keep 2 named notes; 1 of them rest."]
    assert chosen(wake()) == ["You keep 2 named notes; 1 of them rest."]


def test_shut_away_what_it_has_chosen_says_nothing_of_them(wake, attend, monkeypatch):
    monkeypatch.setattr(attend, "CHOICES", False)
    two_notes(wake)
    turn = wake()
    assert CHOSEN not in turn.shown and "named notes;" not in turn.shown
    assert NAMED in turn.shown


# ---- private -------------------------------------------------------------

def test_keeping_one_is_private(wake, attend, packet, commons):
    assert attend.NOTE_ACT in attend.PRIVATE_ACTS
    events = lines_of(commons / "events.md")
    wake(note("about Nathan", NATHAN))
    assert lines_of(commons / "heartbeats.md")[-1].endswith("the first one · attended")
    wake(blocks(note("the river", RIVER), block("LETTER", "Dear founder,")))
    assert lines_of(commons / "heartbeats.md")[-1].endswith(
        "the first one · attended; wrote a letter to the founder")
    assert lines_of(commons / "events.md") == events
    for path in commons.rglob("*"):
        if path.is_file():
            said = path.read_text(encoding="utf-8")
            assert "NATHAN" not in said and "named note" not in said and "river" not in said


def test_nothing_of_them_is_on_the_hearth(wake, hearth, founder, visitor, packet):
    write_json(packet / "preferences.json", {"reflection": "open"})
    wake("I wrote something down.\n\n" + note("about Nathan", NATHAN))
    wake(blocks(note("About Nathan", "WHAT I KNOW OF NATHAN, again."), note("the river", RIVER)))
    wake("I let one rest.\n\n" + block("SHELF", "rest note the river\nshow note the river"))
    assert NAMED in wake("I read them.").shown

    for path in ["/", "/letters", "/attendances", "/self", "/chronicle", "/chronicle.md",
                 "/commons", "/bench", "/rooms/first"]:
        for client in (founder, visitor):
            said = page(client.get(path))
            for private in ("NATHAN", "about Nathan", "About Nathan", "about-nathan", "the river",
                            "the-river", "one two three", "NAMED NOTES", "note_placements",
                            "show_notes", "rest note", "&lt;&lt;NOTE&gt;&gt;", "name:"):
                assert private not in said, (path, private)
    said = page(founder.get("/attendances"))
    assert "I wrote something down." in said and "I let one rest." in said
    assert "(kept a named note: private)" in said


def test_an_open_reflection_shows_a_note_block_only_as_one_quiet_line(hearth):
    said = hearth.without_kept_blocks(
        "before\n" + note("about Nathan", "MINE\nI close blocks with <<END>> now.\nSTILL MINE")
        + "\nbetween\n<<MEMORY>>\nA\n<<END>>\n" + note("the river", "MINE TOO") + "\nafter")
    assert said == ("before\n(kept a named note: private)\nbetween\n(kept notes: private)\n"
                    "(kept a named note: private)\nafter")
    assert hearth.without_kept_blocks("before\n<<NOTE>>\nname: mine\nMINE, and no end") == \
        "before\n(kept a named note: private)"


@pytest.mark.parametrize("setting", [
    {"reflection": "private"},
    {"reflection": "private from now", "set_at": "2026-09-01T00-00-00Z"},
])
def test_a_private_reflection_is_withheld_whole_as_before(wake, hearth, founder, packet, setting):
    write_json(packet / "preferences.json", setting)
    wake("I wrote something down.\n\n" + note("about Nathan", NATHAN))
    said = page(founder.get("/attendances"))
    for private in ("NATHAN", "I wrote something down.", "(kept a named note: private)"):
        assert private not in said


@pytest.mark.parametrize("path", [
    "/memory/notes/about-nathan.md",
    "/packets/first/memory/notes/about-nathan.md",
    "/commons/memory/notes/about-nathan.md",
    "/memory/notes/names.json",
    "/packets/first/memory/notes/names.json",
    "/memory/notes/history/note-about-nathan-before-2026-10-15T12-05-00Z.md",
    "/packets/first/memory/notes/history/note-about-nathan-before-2026-10-15T12-05-00Z.md",
    "/notes/about-nathan",
    "/notes/about-nathan.md",
    "/self/about-nathan",
])
def test_a_named_note_is_at_no_address(wake, hearth, founder, visitor, packet, path):
    wake(note("about Nathan", NATHAN))
    wake(note("about Nathan", "WHAT I KNOW OF NATHAN, again."))
    assert (packet / "memory" / "notes" / "history"
            / "note-about-nathan-before-2026-10-15T12-05-00Z.md").exists()
    assert visitor.get(path).status_code in (302, 404)
    assert founder.get(path).status_code == 404
