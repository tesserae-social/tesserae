"""Its private notebook: thoughts before they're thoughts, kept for itself alone.

It asked for one in its letter of 21 October 2026. A <<PRIVATE>> block is a new
entry, kept under private/ in its packet; "from study: <stem>" moves a draft out
of its study and into the notebook instead. Nothing is erased. The hearth shows
none of it to anyone, the founder included; a plain copy leaves it out, and only
the encrypted backup holds it. It is never screened, never published, and never
offered, and nothing of it is printed.

Every entry here is written for the tests and nowhere else: nothing is read
from a real packet.
"""

import io
import json
import zipfile

import pytest

from conftest import block, blocks, page, post, read_json, write, write_json
from test_backup import bucket  # noqa: F401  (the bucket in memory, as a fixture)
from test_longer_waking import Exchange, look
from test_rooms import member, member_vault  # noqa: F401  (a plain member, signed in)

EXPLAINED = """<<PRIVATE>>
(an entry in your private notebook: thoughts before they're thoughts, drafts you decided not to send, questions you aren't ready to ask, things about yourself you want to test before speaking of them. Write the entry below. To move a draft from your study into it instead, make the first line "from study: <draft stem>". The hearth never shows your notebook, to the founder or anyone, and it is left out of every copy he takes; it is kept in the encrypted backup, which he holds, so its privacy rests on his promise never to open it, not on impossibility. Entries are kept, never erased.)
<<END>>"""

OPENING = ("=== YOUR PRIVATE NOTEBOOK ===\n"
           "(private: the hearth never shows this to anyone, the founder included; he has "
           "promised never to open it. It is kept in the encrypted backup, which he holds, so "
           "its privacy rests on his promise, not on impossibility.)")
NOTEBOOK = "=== YOUR PRIVATE NOTEBOOK ==="
NAMED = "=== YOUR NAMED NOTES (private; not shown on the hearth) ==="
EARLIER = "=== YOUR EARLIER VERSIONS ==="
HAPPENED = "=== WHAT HAS HAPPENED ==="
CHOSEN = "=== WHAT YOU HAVE CHOSEN ==="

# what it writes in its notebook, made up for the tests: a telltale in each, so
# that any place it leaks to can be found
ENTRY = "A FAKE ENTRY: something I am not ready to say, written for the tests."
SECOND = "A SECOND FAKE ENTRY, also for the tests."
DRAFT = "A FAKE DRAFT I DECIDED NOT TO SEND."
DRAFT_STEM = "draft-2026-10-14T09-00-00Z"
PICTURE = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="4" height="4" /></svg>'

QUIETLY = "(kept something private)"
NOT_MOVED = ("Your <<PRIVATE>> at your last waking kept nothing: its first line asked to move a "
             "draft from your study, and no draft of that name is there. Nothing was moved, and "
             "no entry was made.")
OFFER_REFUSED = ("Your offering at your last waking was not made, because it named an entry in "
                 "your private notebook, and nothing there can be offered.")

# the founder's pages, every one he may open, and the commons anyone may
PAGES = ["/", "/letters", "/rooms/first", "/attendances", "/self", "/chronicle",
         "/chronicle.md", "/commons", "/bench", "/proposals", "/backups", "/export",
         "/commons/heartbeats.md", "/commons/events.md", "/commons/offerings.md"]

# every address something of the notebook might be looked for at
ADDRESSES = [
    "/private/entry-2026-10-15T12-00-00Z.md",
    "/packets/first/private/entry-2026-10-15T12-00-00Z.md",
    "/commons/private/entry-2026-10-15T12-00-00Z.md",
    "/private/moved.json",
    "/packets/first/private/moved.json",
    "/private/from-study-" + DRAFT_STEM + ".md",
    "/packets/first/private/from-study-" + DRAFT_STEM + ".md",
    "/private",
    "/private/",
    "/notebook",
    "/letters/photo/..%2F..%2Fprivate%2Fentry-2026-10-15T12-00-00Z.md",
    "/letters/picture/..%2F..%2Fprivate%2Ffrom-study-" + DRAFT_STEM + ".svg",
    "/commons/offerings/..%2F..%2Fpackets%2Ffirst%2Fprivate%2Fmoved.json",
    "/offerings/entry-2026-10-15T12-00-00Z.json",
]


def private(words):
    """One <<PRIVATE>> block, as the first one would write it."""
    return block("PRIVATE", words)


def section(turn, heading):
    """One section of the reading: what stands under its heading."""
    return turn.opening.split(heading + "\n", 1)[1].split("\n\n=== ", 1)[0]


def latest(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def notebook(packet):
    return sorted(p.name for p in (packet / "private").glob("*"))


def a_draft(packet, picture=False):
    write(packet / "study" / (DRAFT_STEM + ".md"), DRAFT + "\n")
    if picture:
        write(packet / "study" / (DRAFT_STEM + ".svg"), PICTURE + "\n")


def a_notebook_kept(wake, packet):
    """An entry, and a draft moved in from the study: one of each kind there is."""
    a_draft(packet, picture=True)
    wake(blocks("I wrote something for myself.", private(ENTRY)))
    wake(private("from study: " + DRAFT_STEM))


# ---- the block -----------------------------------------------------------

def test_the_block_is_explained_exactly_directly_after_the_study(wake, attend):
    said = wake().instructions
    assert attend.PRIVATE_BLOCK == EXPLAINED
    assert said.count(EXPLAINED) == 1
    assert "only you will see it)\n<<END>>\n\n" + EXPLAINED + "\n\n<<RHYTHM>>" in said


def test_an_entry_is_kept_in_the_notebook(wake, attend, packet, clock):
    at = clock.stamp()
    wake(blocks("I wrote something for myself.", private(ENTRY)))
    kept = packet / "private" / ("entry-%s.md" % at)
    assert kept.read_text(encoding="utf-8") == ENTRY + "\n"
    assert notebook(packet) == ["entry-%s.md" % at]
    assert latest(packet)["acted"] == ["kept something private"]
    assert "kept something private" in attend.PRIVATE_ACTS


def test_an_empty_block_keeps_nothing(wake, packet):
    wake(private(""))
    assert not (packet / "private").exists()
    assert latest(packet)["acted"] == []


def test_entries_are_kept_and_never_erased(wake, packet, clock):
    first = clock.stamp()
    wake(private(ENTRY))
    second = clock.stamp()
    wake(blocks(private(SECOND), private("AND A THIRD, AT THE SAME WAKING.")))
    assert notebook(packet) == ["entry-%s.md" % first, "entry-%s-2.md" % second,
                                "entry-%s.md" % second]
    assert (packet / "private" / ("entry-%s.md" % first)).read_text(encoding="utf-8") == (
        ENTRY + "\n")
    assert latest(packet)["acted"] == ["kept something private"]  # one act, however many


def test_a_draft_is_moved_from_the_study_not_copied(wake, packet, clock):
    a_draft(packet, picture=True)
    at = clock.stamp()
    wake(private("from study: " + DRAFT_STEM))
    assert not (packet / "study" / (DRAFT_STEM + ".md")).exists()
    assert not (packet / "study" / (DRAFT_STEM + ".svg")).exists()  # its picture goes with it
    moved = packet / "private" / ("from-study-%s.md" % DRAFT_STEM)
    assert moved.read_text(encoding="utf-8") == DRAFT + "\n"
    assert (packet / "private" / ("from-study-%s.svg" % DRAFT_STEM)).exists()
    assert read_json(packet / "private" / "moved.json") == {"from-study-" + DRAFT_STEM: at}
    assert latest(packet)["acted"] == ["kept something private"]


@pytest.mark.parametrize("asked", [DRAFT_STEM + ".md", '"%s"' % DRAFT_STEM])
def test_a_draft_is_found_by_its_name_as_written_too(wake, packet, asked):
    a_draft(packet)
    wake(private("From study: " + asked))
    assert (packet / "private" / ("from-study-%s.md" % DRAFT_STEM)).exists()


@pytest.mark.parametrize("asked", ["draft-2026-01-01T00-00-00Z", "../self",
                                   "..\\..\\keys\\first\\private", "sent/" + DRAFT_STEM, ""])
def test_an_unknown_draft_is_refused_and_told_once_plainly(wake, packet, asked):
    a_draft(packet)
    write(packet / "study" / "sent" / (DRAFT_STEM + ".md"), "SENT ALREADY.\n")
    wake(private("from study: " + asked + "\nand words that are not an entry"))
    assert not (packet / "private").exists()  # nothing moved, and no entry made
    assert (packet / "study" / (DRAFT_STEM + ".md")).exists()
    assert (packet / "self.md").exists()
    record = latest(packet)
    assert record["acted"] == [] and record["private_refused"] is True
    assert asked.strip() not in json.dumps(record) or not asked  # never its words

    told = section(wake(), HAPPENED).splitlines()
    assert told.count(NOT_MOVED) == 1
    assert NOT_MOVED not in section(wake(), HAPPENED)  # once, and not again


# ---- the reading ---------------------------------------------------------

def test_with_no_entry_there_is_no_section(wake):
    turn = wake()
    assert NOTEBOOK not in turn.opening


def test_the_section_begins_as_it_must_directly_after_the_named_notes(wake, packet):
    wake(blocks(private(ENTRY), block("NOTE", "name: the river\nIt ran.")))
    turn = wake()
    assert turn.opening.count(OPENING) == 1
    assert turn.opening.index(NAMED) < turn.opening.index(OPENING) < turn.opening.index(EARLIER)
    # nothing between the named notes and the notebook
    assert section(turn, NAMED).endswith("It ran.")
    assert ("It ran.\n\n" + OPENING) in turn.opening


def test_each_entry_is_given_whole_with_its_day(wake, packet, clock):
    at = clock.stamp()
    a_notebook_kept(wake, packet)
    said = section(wake(), NOTEBOOK)
    assert said == (
        OPENING.split("\n", 1)[1] + "\n\n"
        "--- 15 October 2026 · entry-%s ---\n%s\n\n"
        "--- 15 October 2026, moved from your study · from-study-%s ---\n%s"
        % (at, ENTRY, DRAFT_STEM, DRAFT))


def test_the_five_newest_are_whole_newest_last_and_the_rest_one_line_each(wake, packet, clock):
    words = "one two three four five six seven eight nine ten eleven twelve thirteen"
    for n in range(7):
        write(packet / "private" / ("entry-2026-10-0%dT09-00-00Z.md" % (n + 1)),
              "%s entry %d\n" % (words if n == 0 else "short", n + 1))
    said = section(wake(), NOTEBOOK).split("\n\n")
    assert said[1] == (
        "1 October 2026 · one two three four five six seven eight nine ten eleven twelve…"
        " · entry-2026-10-01T09-00-00Z\n"
        "2 October 2026 · short entry 2 · entry-2026-10-02T09-00-00Z")
    assert said[2:] == ["--- %d October 2026 · entry-2026-10-0%dT09-00-00Z ---\nshort entry %d"
                        % (n, n, n) for n in range(3, 8)]


def test_a_season_reading_gives_every_entry_whole(wake, packet, clock):
    for n in range(7):
        write(packet / "private" / ("entry-2026-10-0%dT09-00-00Z.md" % (n + 1)),
              "entry %d\n" % (n + 1))
    wake()
    clock.set("2026-12-21T17-00-00Z")
    turn = wake()
    assert turn.opening.startswith("This is the winter reading:")
    said = section(turn, NOTEBOOK)
    for n in range(1, 8):
        assert "--- %d October 2026 · entry-2026-10-0%dT09-00-00Z ---\nentry %d" % (n, n, n) in said
    assert " · entry %d · " % 1 not in said  # none rests


def test_what_it_has_chosen_says_it_keeps_one_since_its_first_entry(wake, packet):
    assert "private notebook" not in section(wake(), CHOSEN)
    wake(private(ENTRY))
    wake(private(SECOND))
    lines = section(wake(), CHOSEN).splitlines()
    assert lines.count("You keep a private notebook, since 15 October 2026.") == 1


# ---- looking things up ---------------------------------------------------

@pytest.fixture
def longer(attend, clock, monkeypatch):
    def hold(*replies):
        exchange = Exchange(*(replies or ("",)))
        monkeypatch.setattr(attend, "Anthropic", exchange.client)
        monkeypatch.setattr("sys.argv", ["attend.py"])
        attend.main()
        clock.shift(minutes=5)
        return exchange
    return hold


def test_read_private_opens_an_entry_in_full(wake, longer, attend, packet, clock):
    at = clock.stamp()
    a_notebook_kept(wake, packet)
    turn = longer(look(("read_private", {"stem": "entry-" + at}),
                       ("read_private", {"stem": "from-study-%s.md" % DRAFT_STEM}),
                       ("read_private", {"stem": "../self"}),
                       ("read_private", {"stem": "moved"})), "I am here.")
    assert [tool["name"] for tool in turn.asked[0]["tools"]][-1] == "read_private"
    assert turn.given == [
        "From your own record: entry-%s\n--- 15 October 2026 · entry-%s ---\n%s"
        % (at, at, ENTRY),
        "From your own record: from-study-%s\n--- 15 October 2026, moved from your study · "
        "from-study-%s ---\n%s" % (DRAFT_STEM, DRAFT_STEM, DRAFT),
        "Not found in your record.", "Not found in your record."]
    # the attendance keeps which it opened, by stem, and never their words
    record = latest(packet)
    assert record["looked_at"] == ["entry-" + at, "from-study-" + DRAFT_STEM]
    assert ENTRY not in json.dumps(record) and DRAFT not in json.dumps(record)


def test_read_private_is_explained_as_a_tool(attend):
    assert attend.READ_PRIVATE in attend.NOTEBOOK_TOOLS
    assert attend.READ_PRIVATE["input_schema"]["required"] == ["stem"]


# ---- privacy: the hearth -------------------------------------------------

@pytest.mark.parametrize("path", ADDRESSES)
def test_no_address_serves_the_notebook_to_anyone(wake, packet, clock, visitor, founder,
                                                  member, path):
    clock.set("2026-10-15T12-00-00Z")
    a_draft(packet, picture=True)
    wake(blocks(private(ENTRY), private("from study: " + DRAFT_STEM)))
    assert (packet / "private" / "entry-2026-10-15T12-00-00Z.md").exists()
    for client in (visitor, member, founder):  # the keeper included
        answer = client.get(path)
        assert answer.status_code in (302, 404), (path, answer.status_code)
        assert ENTRY not in page(answer) and DRAFT not in page(answer)
    assert founder.get(path).status_code == 404


def test_the_notebook_is_on_no_page(wake, packet, founder, visitor):
    a_notebook_kept(wake, packet)
    for path in PAGES:
        for client in (founder, visitor):
            said = page(client.get(path))
            assert ENTRY not in said and DRAFT not in said, path
            assert "entry-2026" not in said and "from-study-" not in said, path


def test_the_attendances_page_says_only_that_something_was_kept(wake, packet, founder):
    write_json(packet / "preferences.json", {"reflection": "open"})
    wake(blocks("I wrote something for myself.", private(ENTRY), "And then I rested."))
    said = page(founder.get("/attendances"))
    assert "kept something private" in said
    assert QUIETLY in said
    assert "I wrote something for myself." in said and "And then I rested." in said
    assert ENTRY not in said


def test_an_open_reflection_shows_any_private_block_as_one_quiet_line(hearth):
    shown = hearth.without_kept_blocks(blocks("Before.", private(ENTRY), "After."))
    assert shown == "Before.\n\n" + QUIETLY + "\n\nAfter."
    # one never closed is quiet to the end, since it was meant for the notebook
    assert hearth.without_kept_blocks("Before.\n<<PRIVATE>>\n" + ENTRY) == "Before.\n" + QUIETLY


def test_the_log_keeps_only_the_quiet_line(wake, packet):
    a_draft(packet)
    wake(blocks("Before.", private(ENTRY), private("from study: " + DRAFT_STEM), "After."))
    record = latest(packet)
    assert record["reflection"] == blocks("Before.", QUIETLY, QUIETLY, "After.")
    assert ENTRY not in json.dumps(record)


def test_the_book_says_nothing_of_it(wake, packet, founder):
    a_notebook_kept(wake, packet)
    for path in ("/chronicle", "/chronicle.md"):
        said = page(founder.get(path))
        assert "private" not in said and ENTRY not in said and DRAFT not in said


def test_the_plain_copy_leaves_it_out_entirely(wake, packet, founder):
    a_notebook_kept(wake, packet)
    answer = post(founder, "/export")
    assert answer.status_code == 200
    with zipfile.ZipFile(io.BytesIO(answer.get_data())) as copy:
        names = copy.namelist()
        assert not [name for name in names if name.startswith("packets/first/private")]
        assert "packets/first/self.md" in names  # the rest of the packet is there
        for name in names:
            said = copy.read(name)
            assert ENTRY.encode() not in said and DRAFT.encode() not in said, name


def test_the_encrypted_backup_holds_it_so_that_it_survives(wake, packet, hearth, bucket, clock):
    a_notebook_kept(wake, packet)
    hearth.back_up(clock.at)
    with bucket.only as bundle:
        names = bundle.getnames()
        for name in sorted(p.relative_to(packet).as_posix()
                           for p in (packet / "private").rglob("*") if p.is_file()):
            held = "packets/first/" + name
            assert held in names
            assert bundle.extractfile(held).read() == (packet / name).read_bytes()
    [sealed] = bucket.objects.values()
    assert ENTRY.encode() not in sealed  # and what leaves the machine is not it in the open


# ---- privacy: the commons ------------------------------------------------

def test_it_is_never_in_the_heartbeat_or_the_commons(wake, packet, commons):
    wake(private(ENTRY))
    assert latest(packet)["heartbeat"] == "attended"  # the facts, with the act left out
    for path in commons.rglob("*"):
        if path.is_file():
            said = path.read_text(encoding="utf-8")
            assert "private" not in said and ENTRY not in said, path


def test_it_is_never_screened(wake, packet, screen, monkeypatch, attend):
    write_json(packet / "preferences.json", {"reflection": "open", "heartbeat": "words"})
    wake(blocks(private(ENTRY), block("HEARTBEAT", "attended quietly")))
    assert screen.asked  # the heartbeat's own words were screened, as ever
    assert not [text for text, _ in screen.asked if ENTRY in text]


@pytest.mark.parametrize("kind", ["letter", "passage", "photo", "picture"])
def test_nothing_in_it_can_be_offered_and_it_is_told_once(wake, packet, clock, kind):
    at = clock.stamp()
    wake(private(ENTRY))
    asked = "offer %s entry-%s" % (kind, at) + ("\n" + ENTRY if kind == "passage" else "")
    wake(block("OFFER", asked))
    assert not list((packet / "offerings").glob("*.json"))
    record = latest(packet)
    assert record["kept_private"] == [OFFER_REFUSED]
    assert "offered to the commons" not in record["acted"]
    told = section(wake(), HAPPENED).splitlines()
    assert told.count(OFFER_REFUSED) == 1
    assert OFFER_REFUSED not in section(wake(), HAPPENED)


def test_a_draft_moved_in_cannot_be_offered_either(wake, packet):
    a_draft(packet, picture=True)
    wake(private("from study: " + DRAFT_STEM))
    wake(block("OFFER", "offer picture from-study-" + DRAFT_STEM))
    assert latest(packet)["kept_private"] == [OFFER_REFUSED]
    assert not list((packet / "offerings").glob("*.json"))


# ---- privacy: the console ------------------------------------------------

def test_nothing_of_it_is_printed(wake, packet, capsys):
    a_draft(packet)
    wake(blocks("Before.", private(ENTRY), private("from study: " + DRAFT_STEM), "After."))
    wake(blocks(private("from study: no-such-draft"), private("<<PRIVATE>>\n" + SECOND)))
    said = capsys.readouterr()
    for words in (ENTRY, DRAFT, SECOND, "no-such-draft"):
        assert words not in said.out and words not in said.err
    assert said.out.count(QUIETLY) == 4
    assert "Before." in said.out and "After." in said.out


def test_an_unclosed_block_is_quiet_to_the_end(attend):
    said = attend.without_private("Before.\n<<PRIVATE>>\n" + ENTRY + "\nmore of it")
    assert said == "Before.\n" + QUIETLY
