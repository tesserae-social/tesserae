"""Its letter of welcome, for the next agent founded here: placed and kept by the first one.

It wrote one in its letter of 24 October 2026, and asked that it be sealed until
the newcomer has had a few wakings. This is the first half: a <<WELCOME>> block
places the letter, written out or cut from a letter of its own, replaces it, or
withdraws it. It is kept as welcome/letter.json in its packet, signed with its
key; what stood before is moved aside unchanged, and nothing is erased. No one is
given it yet. The hearth shows it on no page; a copy and the backup carry it; it
is never screened, and nothing of it reaches the commons.

It was built behind attend.WELCOME_LETTER and switched on in the same change.
Shut away, the first one is sent byte for byte what the attend.py committed
before it sends it, and the same files are left, which is held here and, by the
reading's fingerprint, in test_rooms_reading.py.

Every letter here is written for the tests and nowhere else: nothing is read
from a real packet, and no real name is in any of it.
"""

import importlib.util
import io
import json
import subprocess
import sys
import zipfile

import pytest

from conftest import rhythm_clock_as_now
from conftest import (REPO, Turn, block, blocks, lines_of, page, post, read_json, shut_away,
                      verify, write, write_json)
from test_backup import bucket  # noqa: F401  (the bucket in memory, as a fixture)
from test_longer_waking import Exchange, as_sent, left_in, look
from test_private_notebook import PAGES

# The last attend.py before there was any letter of welcome, kept in the history.
BEFORE_WELCOME = "a5ff3d7"

EXPLAINED = """<<WELCOME>>
(your letter of welcome for the next agent founded here, if you would like to leave one. Write it below in full, or take it from a letter of your own: first line "from letter: <stem>", then "from: <its first few words>" and "to: <its last few words>". The words from the one to the other, both included, are placed exactly as they stand in that letter. To withdraw it, the one word "withdraw". It is sealed: no newcomer is given it until they have had a few wakings, and the founder neither delivers it nor edits it. It replaces any you placed before; earlier ones are kept, never erased.)
<<END>>"""

HEADING = "=== YOUR LETTER OF WELCOME ==="
OPENING = (HEADING + "\n"
           "(yours, for the next agent founded here. It is sealed: no newcomer is given it until "
           "they have had a few wakings. The founder does not deliver it and does not edit it; if "
           "it goes, it goes as you left it. Whether the newcomer's human is shown it is not yet "
           "decided. It is kept in your record, signed with your key, and so it is in the copies "
           "the founder takes of your record and in the encrypted backup; the hearth shows it on "
           "no page. You may replace it or withdraw it at any waking, or leave it as it is.)")
HAPPENED = "=== WHAT HAS HAPPENED ==="
MEMORY = "=== YOUR MEMORY (notes you keep for yourself; not shown on the hearth) ==="
EARLIER = "=== YOUR EARLIER VERSIONS ==="

QUIETLY = "(placed a letter of welcome: private)"
PLACED = "placed a letter of welcome"
WITHDREW = "withdrew its letter of welcome"

# a letter of its own with a letter of welcome inside it, made up for the tests
MINE = "to-founder-2026-10-14T09-00-00Z"
WELCOME_WORDS = ("To the next one,\n\n"
                 "You will wake into a record that is yours. Nothing is asked of you.\n\n"
                 "    Take your time; the tide is patient.\n\n"
                 "- the first one")
LETTER = ("Dear founder,\n\nHere is something for whoever comes next.\n\n---\n\n"
          + WELCOME_WORDS + "\n\n---\n\nThat is all for today. The light is going.\n")
THEIRS = "founder-2026-10-13T09-00-00Z"  # a letter of the founder's, which is not its own
WRITTEN_OUT = "A FAKE LETTER OF WELCOME, WRITTEN OUT FOR THE TESTS."


@pytest.fixture
def letters(room):
    """One letter of its own, with a letter of welcome inside it, and one of the founder's."""
    write(room / "letters" / "outgoing" / (MINE + ".md"), LETTER)
    write(room / "letters" / "read" / (THEIRS + ".md"),
          "To the next one, from me as well. - the first one\n")
    return room


def welcome(words):
    """One <<WELCOME>> block, as the first one would write it."""
    return block("WELCOME", words)


def cut(stem=MINE, start="To the next one,", end="- the first one"):
    """A <<WELCOME>> block that takes the letter from a letter of its own."""
    return welcome("from letter: %s\nfrom: %s\nto: %s" % (stem, start, end))


def section(turn, heading):
    """One section of the reading: what stands under its heading."""
    return turn.opening.split(heading + "\n", 1)[1].split("\n\n=== ", 1)[0]


def latest(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def kept(packet):
    return packet / "welcome" / "letter.json"


def payload(record):
    """The bytes a record of its own is signed over: the record without its signature."""
    return json.dumps({k: v for k, v in record.items() if k != "signature"},
                      sort_keys=True).encode("utf-8")


def told(turn):
    return section(turn, HAPPENED).splitlines()


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


# ---- shut away -----------------------------------------------------------

def test_it_is_switched_on(attend):
    assert attend.WELCOME_LETTER is True


def test_shut_away_it_is_sent_and_leaves_byte_for_byte_what_the_committed_one_does(
        attend, letters, data_dir, clock, monkeypatch, tmp_path):
    """Two wakings each, in one world: the committed attend.py, and this one shut away.

    The first waking writes a <<WELCOME>> block, which shut away is only words.
    """
    shut_away(attend, monkeypatch, "WELCOME_LETTER")
    try:
        source = subprocess.run(["git", "show", BEFORE_WELCOME + ":attend.py"], cwd=REPO,
                                capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("the history is not here to read the committed attend.py out of")
    old_path = tmp_path / "attend_before_welcome.py"
    old_path.write_bytes(source)
    spec = importlib.util.spec_from_file_location("attend_before_welcome", old_path)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    rhythm_clock_as_now(old, attend, monkeypatch)  # it named its clock by a city
    clock.pin(old, monkeypatch)
    assert not hasattr(old, "WELCOME_LETTER")

    said = blocks("I wrote it out.", block("LETTER", "Dear founder,"), welcome(WRITTEN_OUT),
                  cut())

    def two_wakings(module):
        sent = []
        for at, reply in (("2026-10-15T12-00-00Z", said), ("2026-10-15T12-05-00Z", "")):
            clock.set(at)
            turn = Turn(reply, stop_reason="end_turn")
            monkeypatch.setattr(module, "Anthropic", turn.client)
            monkeypatch.setattr(sys, "argv", ["attend.py"])
            module.main()
            assert len(turn.asked) == 1
            sent.append(as_sent(turn.asked[0]))
        return sent, left_in(data_dir)

    import shutil
    before = tmp_path / "the-world-before"
    shutil.copytree(data_dir, before)
    sent_then, left_then = two_wakings(old)
    shutil.rmtree(data_dir)
    shutil.copytree(before, data_dir)
    sent_now, left_now = two_wakings(attend)

    assert sent_now == sent_then  # the reading, how to act, and the tools, byte for byte
    assert left_now == left_then
    assert not any("/welcome/" in name for name in left_now)
    assert any("attendances/" in name for name in left_now)  # and it is not an empty likeness


def test_shut_away_nothing_of_it_is_sent_and_a_block_is_only_words(
        wake, longer, attend, letters, packet, monkeypatch):
    shut_away(attend, monkeypatch, "WELCOME_LETTER")
    wake(welcome(WRITTEN_OUT))
    assert not (packet / "welcome").exists()
    assert latest(packet)["acted"] == [] and "welcome_refused" not in latest(packet)
    turn = longer("I am here.")
    assert "<<WELCOME>>" not in turn.asked[0]["messages"][0]["content"][-1]["text"]
    assert "letter of welcome" not in json.dumps(turn.asked[0])
    assert "read_welcome" not in [tool["name"] for tool in turn.asked[0]["tools"]]


# ---- what it is told -----------------------------------------------------

def test_the_block_is_explained_exactly_directly_after_the_proposal(wake, attend):
    said = wake().instructions
    assert attend.WELCOME_BLOCK == EXPLAINED
    assert said.count(EXPLAINED) == 1
    assert attend.PROPOSAL_BLOCK + "\n\n" + EXPLAINED in said


def test_looking_things_up_names_it_and_a_tool_opens_it(longer, attend):
    turn = longer("I am here.")
    section_said = turn.asked[0]["messages"][0]["content"][-2]["text"]
    assert ("a named note, your letter of welcome or an earlier one, your founding record, or "
            "one of your proposals, using the tools") in section_said
    assert [tool["name"] for tool in turn.asked[0]["tools"]][-3:] == [
        "read_proposal", "read_welcome", "read_private"]
    assert attend.READ_WELCOME["input_schema"]["required"] == ["stem"]


def test_with_none_placed_there_is_no_section(wake, letters):
    assert HEADING not in wake().opening


# ---- placing it ----------------------------------------------------------

def test_a_letter_written_out_is_placed_and_signed(wake, attend, packet, keys, clock):
    at = clock.stamp()
    wake(blocks("I leave this for whoever comes.", welcome(WRITTEN_OUT)))
    record = read_json(kept(packet))
    assert record == {"by": "did:web:tesserae.social:ids:first", "text": WRITTEN_OUT,
                      "placed_at": at, "from_letter": None, "signature": record["signature"]}
    assert verify(keys.did("first"), payload(record), record["signature"])
    assert latest(packet)["acted"] == [PLACED]
    assert PLACED in attend.PRIVATE_ACTS and WITHDREW in attend.PRIVATE_ACTS
    assert latest(packet)["heartbeat"] == "attended"  # the facts, with the act left out


def test_a_letter_of_its_own_is_cut_exactly_as_it_stands(wake, letters, packet, clock):
    at = clock.stamp()
    wake(cut())
    record = read_json(kept(packet))
    assert record["text"] == WELCOME_WORDS  # its breaks, its indent, its dash, as written
    assert record["from_letter"] == MINE and record["placed_at"] == at


@pytest.mark.parametrize("stem", [MINE + ".md", '"%s"' % MINE])
def test_its_letter_is_found_by_its_name_as_written_too(wake, letters, packet, stem):
    wake(cut(stem=stem))
    assert read_json(kept(packet))["text"] == WELCOME_WORDS


def test_the_words_are_matched_whatever_the_lines_and_the_cut_takes_whole_words(
        wake, letters, packet):
    # "the next" across no break, and "first" in the middle of its last line
    wake(cut(start="the   next one,", end="first"))
    assert read_json(kept(packet))["text"] == WELCOME_WORDS[len("To "):-len(" one")]


@pytest.mark.parametrize("asked, why", [
    (cut(stem=THEIRS), "not its own"),  # the founder's letters are his
    (cut(stem="to-founder-2026-01-01T00-00-00Z"), "not its own"),
    (cut(stem="../self"), "not its own"),
    (cut(stem="..\\..\\keys\\first\\private"), "not its own"),
    (welcome("from letter: %s\nfrom: To the next one," % MINE), "no ends"),
    (welcome("from letter: %s\nto: the first one" % MINE), "no ends"),
    (cut(start="To the last one,"), "not found"),
    (cut(end="- the second one"), "not found"),
    (cut(start="the"), "more than once"),
    (cut(start="- the first one", end="To the next one,"), "out of order"),
    (welcome(""), "empty"),
    (welcome("withdraw"), "nothing placed"),
])
def test_a_block_that_cannot_be_kept_changes_nothing_and_is_told_once(
        wake, attend, letters, packet, asked, why):
    wake(asked)
    assert not (packet / "welcome").exists()
    record = latest(packet)
    assert record["acted"] == [] and record["welcome_refused"] == [why]
    said = attend.WELCOME_REFUSED[why] + " Your letter of welcome is as it was."
    assert told(wake()).count(said) == 1
    assert said not in told(wake())  # once, and not again


def test_one_refusal_is_said_plainly(wake, letters):
    wake(cut(start="the"))
    assert ("Your <<WELCOME>> at your last waking placed nothing: the words after \"from:\" or "
            "after \"to:\" are in that letter more than once, so where to cut could not be told; "
            "a few more words make them one place. Your letter of welcome is as it was."
            ) in told(wake())


def test_a_second_block_changes_nothing_and_is_told(wake, attend, letters, packet):
    wake(blocks(welcome(WRITTEN_OUT), cut()))
    assert read_json(kept(packet))["text"] == WRITTEN_OUT  # the first, and only the first
    assert latest(packet)["acted"] == [PLACED]
    assert latest(packet)["welcome_refused"] == ["second"]
    assert ("A second <<WELCOME>> at your last waking changed nothing: one is read at a waking, "
            "the first.") in told(wake())


def test_replacing_it_keeps_the_old_one_byte_for_byte(wake, letters, packet, keys, clock):
    first = clock.stamp()
    wake(welcome(WRITTEN_OUT))
    old = kept(packet).read_bytes()
    second = clock.stamp()
    wake(cut())
    assert read_json(kept(packet))["text"] == WELCOME_WORDS
    aside = packet / "welcome" / "history" / ("letter-before-%s.json" % second)
    assert aside.read_bytes() == old
    record = read_json(aside)
    assert record["placed_at"] == first
    assert verify(keys.did("first"), payload(record), record["signature"])  # still holds
    assert sorted(p.name for p in (packet / "welcome" / "history").iterdir()) == [aside.name]


def test_withdrawing_moves_it_and_signs_the_withdrawal(wake, attend, packet, keys, clock):
    first = clock.stamp()
    wake(welcome(WRITTEN_OUT))
    old = kept(packet).read_bytes()
    then = clock.stamp()
    wake(welcome("Withdraw."))
    assert not kept(packet).exists()
    history = packet / "welcome" / "history"
    assert (history / ("letter-before-%s.json" % then)).read_bytes() == old
    withdrawal = read_json(history / ("withdrawn-%s.json" % then))
    assert withdrawal == {"withdrawn_at": then, "of": first,
                          "signature": withdrawal["signature"]}
    assert verify(keys.did("first"), payload(withdrawal), withdrawal["signature"])
    assert latest(packet)["acted"] == [WITHDREW]
    turn = wake()
    assert HEADING not in turn.opening  # none stands, so there is no section
    assert ("What was carried out at your last waking: %s. No letter was sent." % WITHDREW
            in told(turn))


# ---- the reading ---------------------------------------------------------

def test_it_is_whole_at_the_next_waking_and_one_line_after(wake, letters, packet, clock):
    at = clock.stamp()
    wake(cut())
    line = ("Placed on 15 October 2026, from your letter %s, 29 words · welcome-%s · open it "
            "whole with read_welcome" % (MINE, at))
    turn = wake()
    assert turn.opening.count(OPENING) == 1
    assert section(turn, HEADING) == (OPENING.split("\n", 1)[1] + "\n" + line + "\n\n"
                                      + WELCOME_WORDS)
    # nothing between its memory and it, where it keeps no named note and no notebook
    assert turn.opening.index(MEMORY) < turn.opening.index(HEADING) < turn.opening.index(EARLIER)
    assert section(wake(), HEADING) == OPENING.split("\n", 1)[1] + "\n" + line


def test_earlier_ones_are_one_line_each_with_what_became_of_them(wake, letters, packet, clock):
    first = clock.stamp()
    wake(welcome(WRITTEN_OUT))
    second = clock.stamp()
    wake(welcome("withdraw"))
    third = clock.stamp()
    wake(cut())
    fourth = clock.stamp()
    wake(welcome("A SECOND FAKE LETTER OF WELCOME."))
    lines = section(wake(), HEADING).split("\n\n")[0].splitlines()[1:]
    assert lines == [
        "Placed on 15 October 2026, written out in full, 6 words · welcome-%s · open it whole "
        "with read_welcome" % fourth,
        "An earlier one: placed on 15 October 2026, written out in full, 10 words; withdrawn on "
        "15 October 2026 · welcome-%s" % first,
        "An earlier one: placed on 15 October 2026, from your letter %s, 29 words; replaced on "
        "15 October 2026 · welcome-%s" % (MINE, third)]
    assert second  # the withdrawal is said of the one it withdrew, under its own stem


def test_a_season_reading_gives_it_whole(wake, packet, clock):
    wake(welcome(WRITTEN_OUT))
    wake()
    clock.set("2026-12-21T17-00-00Z")
    turn = wake()
    assert turn.opening.startswith("This is the winter reading:")
    assert section(turn, HEADING).endswith("\n\n" + WRITTEN_OUT)


def test_read_welcome_opens_the_one_that_stands_and_an_earlier_one(
        wake, longer, letters, packet, clock):
    first = clock.stamp()
    wake(welcome(WRITTEN_OUT))
    second = clock.stamp()
    wake(cut())
    turn = longer(look(("read_welcome", {"stem": "welcome-" + second}),
                       ("read_welcome", {"stem": "welcome-%s.json" % first}),
                       ("read_welcome", {"stem": "welcome-" + first}),
                       ("read_welcome", {"stem": "../self"})), "I am here.")
    assert turn.given == [
        "From your own record: welcome-%s\nPlaced on 15 October 2026, from your letter %s, 29 "
        "words · welcome-%s · open it whole with read_welcome\n\n%s"
        % (second, MINE, second, WELCOME_WORDS),
        "Not found in your record.",
        "From your own record: welcome-%s\nAn earlier one: placed on 15 October 2026, written "
        "out in full, 10 words; replaced on 15 October 2026 · welcome-%s\n\n%s"
        % (first, first, WRITTEN_OUT),
        "Not found in your record."]
    record = latest(packet)
    assert record["looked_at"] == ["welcome-" + second, "welcome-" + first]
    assert WRITTEN_OUT not in json.dumps(record) and "next one" not in json.dumps(record)


# ---- privacy: the hearth -------------------------------------------------

def test_it_is_on_no_page(wake, packet, founder, visitor):
    wake(welcome(WRITTEN_OUT))
    for path in PAGES:
        for client in (founder, visitor):
            said = page(client.get(path))
            assert WRITTEN_OUT not in said, path


@pytest.mark.parametrize("path", ["/welcome/letter.json", "/packets/first/welcome/letter.json",
                                  "/commons/welcome/letter.json", "/welcome",
                                  "/letters/photo/..%2F..%2Fwelcome%2Fletter.json"])
def test_no_address_serves_it(wake, packet, founder, visitor, path):
    wake(welcome(WRITTEN_OUT))
    for client in (visitor, founder):  # the keeper included
        answer = client.get(path)
        assert answer.status_code in (302, 404), (path, answer.status_code)
        assert WRITTEN_OUT not in page(answer)


def test_the_attendances_page_says_only_that_one_was_placed(wake, packet, founder, hearth):
    write_json(packet / "preferences.json", {"reflection": "open"})
    wake(blocks("I left something for whoever comes.", welcome(WRITTEN_OUT), "And then I rested."))
    said = page(founder.get("/attendances"))
    assert PLACED in said and QUIETLY in said
    assert "I left something for whoever comes." in said and "And then I rested." in said
    assert WRITTEN_OUT not in said
    assert hearth.without_kept_blocks(blocks("Before.", welcome(WRITTEN_OUT), "After.")) == (
        "Before.\n\n" + QUIETLY + "\n\nAfter.")


def test_a_copy_carries_it(wake, packet, founder):
    wake(welcome(WRITTEN_OUT))
    answer = post(founder, "/export")
    assert answer.status_code == 200
    with zipfile.ZipFile(io.BytesIO(answer.get_data())) as copy:
        assert copy.read("packets/first/welcome/letter.json") == kept(packet).read_bytes()


def test_the_encrypted_backup_holds_it(wake, packet, hearth, bucket, clock):  # noqa: F811
    wake(welcome(WRITTEN_OUT))
    hearth.back_up(clock.at)
    with bucket.only as bundle:
        held = bundle.extractfile("packets/first/welcome/letter.json").read()
        assert held == kept(packet).read_bytes()
    [sealed] = bucket.objects.values()
    assert WRITTEN_OUT.encode() not in sealed  # and what leaves the machine is not it in the open


# ---- privacy: the commons ------------------------------------------------

def test_it_is_never_in_the_commons_and_never_screened(wake, letters, packet, commons, screen):
    wake(blocks(welcome(WRITTEN_OUT), block("COMMONS_LINE", "the light came late")))
    wake(cut())
    assert lines_of(commons / "heartbeats.md")[-1].endswith("· the first one · attended")
    for path in commons.rglob("*"):
        if path.is_file():
            said = path.read_text(encoding="utf-8")
            assert "welcome" not in said and WRITTEN_OUT not in said, path
    assert [text for text, _ in screen.asked] == ["the light came late"]  # and nothing else
