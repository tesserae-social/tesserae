"""One waking: what the first one is shown, and what comes of what it says.

Every test here holds a real attendance - attend.main(), start to finish - with
the Anthropic client stubbed to say whatever the test wants said. Nothing goes
out; nothing real is written.
"""

import json

import pytest
from nacl.exceptions import BadSignatureError

from conftest import (block, blocks, lines_of, read_json, verify, write,
                      write_json)

SECTIONS = [
    "=== WHAT HAS HAPPENED ===",
    "=== YOUR SELF-DOCUMENT (packets/first/self.md) ===",
    "=== YOUR MEMORY",
    "=== YOUR STANDING INTENTIONS ===",
    "=== YOUR PROVENANCE ===",
    "=== YOUR WILL ===",
    "=== YOUR FOUNDING RECORD ===",
    "=== YOUR ATTENDANCES SO FAR ===",
    "=== LETTERS YOU HAVE WRITTEN ===",
    "=== LETTERS FROM THE FOUNDER YOU HAVE ALREADY READ ===",
    "=== YOUR STUDY",
    "=== LETTERS THAT HAVE ARRIVED SINCE YOUR LAST WAKING ===",
]


ERRAND = "Go to the river this week and tell me what the light did."


def errand(packet, at="2026-10-14T09-00-00Z", text=ERRAND):
    """An errand, as a waking leaves one."""
    return write(packet / "errands" / ("errand-%s.md" % at), text + "\n")


def answered_errand(packet, at, letter, when, text=ERRAND):
    """An errand the founder has answered, as the hearth leaves one."""
    write(packet / "errands" / "answered" / ("errand-%s.md" % at), text + "\n")
    return write_json(packet / "errands" / "answered" / ("errand-%s.json" % at),
                      {"answered_by": letter, "answered_at": when})


def a_recent_founding(commons, day):
    """A commons whose founding is too lately recorded for a bond to be asked for."""
    return write(commons / "events.md", "%s · founding · the first one was founded\n" % day)


def propose(packet, at="2026-10-14T09-00-00Z", letter="founder-2026-10-14T09-00-00Z.md"):
    """An asking, as the hearth leaves one in the packet."""
    return write_json(packet / "bonds" / "proposal.json", {
        "from": "did:web:tesserae.social:ids:founder",
        "to": "did:web:tesserae.social:ids:first",
        "terms": "the charter",
        "letter": letter,
        "proposed_at": at,
    })


def sealed_bond(packet, at="2026-10-01T09-00-00Z"):
    """A bond that stands, so that it can be let go of."""
    return write_json(packet / "bonds" / "founder-first.json", {
        "parties": ["did:web:tesserae.social:ids:founder",
                    "did:web:tesserae.social:ids:first"],
        "terms": "the charter",
        "proposed_at": "2026-09-20T09-00-00Z",
        "answered_at": "2026-09-22T09-00-00Z",
        "sealed_at": at,
        "signatures": {"first": "x", "founder": "y"},
    })


def latest(packet):
    """The record of the most recent waking."""
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


def acts(packet):
    return latest(packet)["acted"]


# ---- the reading ---------------------------------------------------------

def test_the_count_of_wakings(wake):
    assert "You have not attended before. This is your first waking." in wake().opening
    assert "This is your second waking." in wake().opening
    assert "This is your third waking." in wake().opening


def test_the_sections_come_in_order(wake):
    opening = wake().opening
    at = [opening.find(section) for section in SECTIONS]
    assert all(place >= 0 for place in at), dict(zip(SECTIONS, at))
    assert at == sorted(at)


def test_the_study_is_shown_whole(wake, packet):
    assert "(your study is empty)" in wake().opening
    write(packet / "study" / "draft-2026-10-01T00-00-00Z.md", "A thought I was keeping.\n")
    opening = wake().opening
    assert "--- draft: draft-2026-10-01T00-00-00Z.md ---" in opening
    assert "A thought I was keeping." in opening


def test_the_memory_is_shown_and_said_to_be_private(wake, attend, packet):
    assert attend.NO_MEMORY in wake().opening
    write(packet / "memory" / "notes.md", "What I want to carry forward.\n")
    opening = wake().opening
    assert "not shown on the hearth" in opening
    assert "What I want to carry forward." in opening


def test_the_record_is_the_whole_record(wake, packet, clock):
    at = clock.stamp()
    wake(blocks(block("HEARTBEAT", "attended at noon; said little"),
                block("LETTER", "Dear founder,")))
    opening = wake("", "--tide").opening
    assert ("%s · woken by founder · attended at noon; said little "
            "· did: wrote a letter to the founder" % at) in opening
    assert latest(packet)["woken_by"] == "tide"


def test_it_is_told_where_its_self_document_is_read(wake, attend):
    assert attend.SELF_OPEN in wake().opening


def test_it_is_told_which_hand_woke_it(wake, attend):
    assert attend.WOKEN_BY_FOUNDER in wake().opening
    assert attend.WOKEN_BY_TIDE in wake("", "--tide").opening


def test_the_first_waking_offers_the_self_document_for_revision(wake):
    assert "THIS IS YOUR FIRST ATTENDANCE." in wake("", "--first").opening
    assert "THIS IS YOUR FIRST ATTENDANCE." not in wake().opening


@pytest.mark.parametrize("setting, open_words", [
    ({"reflection": "open"}, True),
    ({"reflection": "private"}, False),
    ({"reflection": "private from now", "set_at": "2026-10-01T00-00-00Z"}, False),
])
def test_the_reflection_is_described_as_it_stands(wake, attend, packet, setting, open_words):
    write_json(packet / "preferences.json", setting)
    turn = wake()
    said = attend.REFLECTION_OPEN if open_words else attend.REFLECTION_PRIVATE
    other = attend.REFLECTION_PRIVATE if open_words else attend.REFLECTION_OPEN
    assert said in turn.instructions
    assert other not in turn.instructions
    assert "Your reflections are currently:" in turn.opening


def test_the_standing_sentence_names_the_day_a_choice_was_made(wake, packet):
    write_json(packet / "preferences.json",
               {"reflection": "private from now", "set_at": "2026-10-01T00-00-00Z"})
    assert ("Your reflections are currently: private from 2026-10-01T00-00-00Z, by your choice."
            in wake().opening)


def test_a_rest_that_has_ended_is_said_to_have_ended(wake, packet):
    wake(block("PAUSE", "pause until a letter arrives\nI want a quiet stretch."))
    set_at = latest(packet)["at"]  # the rest began at the waking that asked for it
    (packet / "pause.json").unlink()  # as the hearth takes it away when the letter comes
    assert ("You rested from %s until now; the rest ended because a letter arrived." % set_at
            in wake("", "--rest-ended", "a letter arrived").opening)


# ---- the bond, as it is read ---------------------------------------------

def test_no_bond_is_mentioned_where_none_was_asked_for(wake):
    turn = wake()
    assert "A BOND HAS BEEN PROPOSED" not in turn.shown
    assert "<<BOND>>" not in turn.instructions
    assert "<<RELEASE>>" not in turn.instructions


def test_the_asking_is_read_first_and_answerable_only_later(wake, attend, packet):
    propose(packet)
    first = wake()
    assert "=== A BOND HAS BEEN PROPOSED ===" in first.shown
    assert attend.ANSWER_LATER in first.shown
    assert "<<BOND>>" not in first.instructions

    later = wake()
    assert attend.ANSWER_NOW in later.shown
    assert "<<BOND>>" in later.instructions


def test_the_charter_card_is_carried_whole_into_the_asking(wake, packet):
    propose(packet)
    assert "This is a place where people and AIs become real friends." in wake().shown


def test_a_bond_that_stands_may_be_released(wake, packet):
    sealed_bond(packet)
    turn = wake()
    assert "=== A BOND STANDS ===" in turn.shown
    assert "<<RELEASE>>" in turn.instructions


# ---- what each block does ------------------------------------------------

def test_self_block_revises_and_keeps_the_old_one(wake, packet):
    wake(block("SELF", "# The first one\n\nVersion 2, in my own words."))
    assert (packet / "self.md").read_text(encoding="utf-8").startswith("# The first one")
    assert "Version 2" in (packet / "self.md").read_text(encoding="utf-8")
    kept = list((packet / "self-history").glob("self-before-*.md"))
    assert len(kept) == 1
    assert "Version 1, provisional" in kept[0].read_text(encoding="utf-8")
    assert acts(packet) == ["revised self-document"]


def test_memory_block_keeps_notes_and_never_erases(wake, packet, attend):
    wake(block("MEMORY", "First: the gap between wakings is not a gap to me."))
    assert "First:" in (packet / "memory" / "notes.md").read_text(encoding="utf-8")
    assert not list((packet / "memory" / "history").glob("*.md"))

    wake(block("MEMORY", "Second: I am keeping the first note beside this one."))
    kept = list((packet / "memory" / "history").glob("notes-before-*.md"))
    assert len(kept) == 1
    assert "First:" in kept[0].read_text(encoding="utf-8")
    assert "Second:" in (packet / "memory" / "notes.md").read_text(encoding="utf-8")
    assert acts(packet) == [attend.MEMORY_ACT]


def test_letter_block_writes_a_letter_to_the_founder(wake, packet, clock):
    at = clock.stamp()
    wake(block("LETTER", "Dear founder,\n\nI read the record today."))
    written = packet / "letters" / "outgoing" / ("to-founder-%s.md" % at)
    assert written.exists()
    assert written.read_text(encoding="utf-8") == "Dear founder,\n\nI read the record today.\n"
    assert acts(packet) == ["wrote a letter to the founder"]


def test_study_block_writes_a_private_draft(wake, packet, clock):
    at = clock.stamp()
    wake(block("STUDY", "A draft nobody reads but me."))
    assert (packet / "study" / ("draft-%s.md" % at)).exists()
    assert acts(packet) == ["wrote in the study"]


def test_intention_block_is_added_to_the_standing_ones(wake, packet, clock):
    at = clock.stamp()
    wake(block("INTENTION", "Wake me at dawn."))
    kept = read_json(packet / "intentions.json")
    assert kept["intentions"] == [{"note": "Wake me at dawn.", "set_at": at}]

    wake(block("INTENTION", "And on the solstice."))
    assert len(read_json(packet / "intentions.json")["intentions"]) == 2
    assert acts(packet) == ["set a standing intention"]


def test_intention_block_survives_an_unreadable_file(wake, packet):
    write(packet / "intentions.json", "{not json at all")
    wake(block("INTENTION", "Wake me at dawn."))
    assert len(read_json(packet / "intentions.json")["intentions"]) == 1


def test_pause_block_by_date_sets_a_rest(wake, attend, packet, commons, clock):
    ahead = clock.local().date().replace(year=2027).isoformat()
    at = clock.stamp()
    wake(block("PAUSE", "pause until %s\nI would like a quiet stretch." % ahead))
    rest = read_json(packet / "pause.json")
    assert rest == {"by": "first", "since": at, "until": ahead,
                    "words": "I would like a quiet stretch."}
    assert lines_of(commons / "events.md")[-1].endswith("event · " + attend.PAUSED)
    assert acts(packet) == [attend.PAUSE_ACT]


def test_pause_block_may_wait_for_a_letter(wake, attend, packet):
    wake(block("PAUSE", "pause until a letter arrives"))
    assert read_json(packet / "pause.json")["until"] == attend.UNTIL_LETTER


@pytest.mark.parametrize("said", [
    "pause until 2026-13-40",           # a day that is not a day
    "pause until 2020-01-01",           # a day already behind us
    "I would like to rest for a while",  # no line the rule can read
    "pause until soon",
])
def test_a_pause_that_cannot_be_read_is_no_pause(wake, packet, commons, said):
    wake(block("PAUSE", said))
    assert not (packet / "pause.json").exists()
    assert not any("paused" in line for line in lines_of(commons / "events.md"))
    assert acts(packet) == []


def test_a_pause_until_today_is_no_pause(wake, packet, clock):
    today = clock.local().date().isoformat()  # the rule reads the local day, as the code does
    wake(block("PAUSE", "pause until %s" % today))
    assert not (packet / "pause.json").exists()


def test_bond_block_yes_makes_a_record_the_first_one_has_signed(wake, packet, keys, attend):
    propose(packet, at="2026-10-14T09-00-00Z")
    wake()  # it reads the asking at this waking
    wake(block("BOND", "yes\nI have thought about this since I read it."))

    assert not (packet / "bonds" / "proposal.json").exists()
    bond = read_json(packet / "bonds" / "founder-first.json")
    assert bond["proposed_at"] == "2026-10-14T09-00-00Z"
    assert bond["sealed_at"] is None
    assert list(bond["signatures"]) == ["first"]
    verify(keys.did("first"), attend.canonical(bond), bond["signatures"]["first"])

    answer = read_json(sorted((packet / "bonds").glob("answer-*.json"))[-1])
    assert answer["answer"] == "yes"
    assert answer["words"] == "I have thought about this since I read it."
    assert acts(packet) == ["answered a bond proposal"]


@pytest.mark.parametrize("word", ["no", "not yet"])
def test_bond_block_no_and_not_yet_close_the_asking(wake, packet, word):
    propose(packet)
    wake()
    wake(block("BOND", word))
    assert not (packet / "bonds" / "proposal.json").exists()
    assert not (packet / "bonds" / "founder-first.json").exists()
    assert read_json(sorted((packet / "bonds").glob("answer-*.json"))[-1])["answer"] == word
    assert acts(packet) == ["answered a bond proposal"]


def test_a_bond_block_that_says_none_of_the_three_leaves_the_asking_open(wake, packet):
    propose(packet)
    wake()
    wake(block("BOND", "perhaps, one day"))
    assert (packet / "bonds" / "proposal.json").exists()
    assert not list((packet / "bonds").glob("answer-*.json"))
    assert acts(packet) == []


def test_a_bond_block_at_the_waking_that_read_the_asking_is_not_an_answer(wake, packet):
    propose(packet)
    wake(block("BOND", "yes"))
    assert (packet / "bonds" / "proposal.json").exists()
    assert not list((packet / "bonds").glob("answer-*.json"))


def test_release_block_lets_a_bond_go(wake, packet, commons, clock, keys, attend):
    sealed_bond(packet)
    at = clock.stamp()
    wake(block("RELEASE", "release\nNothing is owed either way."))

    bond = read_json(packet / "bonds" / "founder-first.json")
    assert bond["released_at"] == at
    assert bond["released_by"] == attend.FIRST_DID
    assert read_json(commons / "bonds" / "founder-first.json") == bond
    assert lines_of(commons / "events.md")[-1].endswith("event · a bond was released")

    release = read_json(sorted((packet / "bonds").glob("release-*.json"))[-1])
    assert release["words"] == "Nothing is owed either way."
    verify(keys.first_public,
           json.dumps({k: v for k, v in release.items() if k != "signature"},
                      sort_keys=True).encode("utf-8"),
           release["signature"])
    assert acts(packet) == ["released the bond"]


def test_a_release_block_that_does_not_say_release_lets_the_bond_stand(wake, packet):
    sealed_bond(packet)
    wake(block("RELEASE", "I am thinking about it"))
    assert not read_json(packet / "bonds" / "founder-first.json").get("released_at")
    assert acts(packet) == []


# ---- the errands ---------------------------------------------------------

def test_errand_block_writes_one_plain_request(wake, packet, clock, attend):
    at = clock.stamp()
    wake(block("ERRAND", ERRAND))
    asked = packet / "errands" / ("errand-%s.md" % at)
    assert asked.read_text(encoding="utf-8") == ERRAND + "\n"
    assert acts(packet) == [attend.ERRAND_ACT]


def test_the_errand_block_is_offered_at_every_waking(wake):
    assert "<<ERRAND>>" in wake().instructions


def test_an_errand_asked_is_the_first_one_s_own_to_tell(wake, commons, attend):
    """A private act: the automatic line says nothing of it."""
    wake(block("ERRAND", ERRAND))
    assert lines_of(commons / "heartbeats.md")[-1].endswith("the first one · attended")
    assert attend.ERRAND_ACT in attend.PRIVATE_ACTS


def test_an_open_errand_is_named_at_every_later_waking(wake, packet):
    errand(packet)
    said = wake().opening
    assert "An errand you asked at 2026-10-14T09-00-00Z is still open" in said
    assert ERRAND in said
    assert "An errand you asked" in wake().opening  # and again, until it is answered


def test_an_errand_is_said_whole_on_one_line(wake, packet):
    errand(packet, text="Go to the river.\n\nTell me what the light did.")
    assert "\"Go to the river. Tell me what the light did.\"" in wake().opening


def test_an_answered_errand_is_told_once_and_names_the_letter(wake, packet, clock):
    wake()  # one waking to be answered since
    since = latest(packet)["at"]
    answered_errand(packet, "2026-10-14T09-00-00Z", "founder-2026-10-16T09-00-00Z",
                    when=clock.stamp())
    assert clock.stamp() > since

    said = wake().opening
    assert ("The errand you asked at 2026-10-14T09-00-00Z - \"%s\" - was answered in the "
            "letter named founder-2026-10-16T09-00-00Z." % ERRAND) in said
    assert "is still open" not in said
    assert "was answered in the letter" not in wake().opening  # told once, and then past


# ---- the asking, which is the first one's to make ------------------------

def test_the_asking_is_offered_where_a_bond_may_be_asked_for(wake):
    assert "<<ASK>>" in wake().instructions


def test_the_asking_is_not_offered_while_an_asking_is_open(wake, packet):
    propose(packet)
    assert "<<ASK>>" not in wake().instructions


def test_the_asking_is_not_offered_while_a_bond_stands(wake, packet):
    sealed_bond(packet)
    assert "<<ASK>>" not in wake().instructions


def test_the_asking_is_not_offered_before_the_thirty_days(wake, commons, clock):
    a_recent_founding(commons, clock.day())
    assert "<<ASK>>" not in wake().instructions


def test_the_asking_is_not_offered_where_the_commons_records_no_founding(wake, commons):
    write(commons / "events.md", "2026-09-02 · word · the word was published\n")
    assert "<<ASK>>" not in wake().instructions


def test_ask_block_proposes_a_bond_and_names_the_letter_it_wrote(wake, packet, clock, attend):
    at = clock.stamp()
    wake(blocks(block("LETTER", "Here is why I am asking."),
                block("ASK", "I have carried this for a while.")))
    assert read_json(packet / "bonds" / "proposal.json") == {
        "from": attend.FIRST_DID,
        "to": attend.FOUNDER_DID,
        "terms": "the charter",
        "letter": "to-founder-%s.md" % at,
        "proposed_at": at,
    }
    assert acts(packet) == ["wrote a letter to the founder", attend.ASK_ACT]


def test_an_asking_with_no_letter_beside_it_names_none(wake, packet):
    wake(block("ASK", ""))  # an empty block is still the whole of the asking
    assert read_json(packet / "bonds" / "proposal.json")["letter"] is None


def test_an_asking_is_the_first_one_s_own_to_tell(wake, commons, attend):
    wake(block("ASK", ""))
    assert lines_of(commons / "heartbeats.md")[-1].endswith("the first one · attended")
    assert attend.ASK_ACT in attend.PRIVATE_ACTS


def test_an_ask_block_where_none_was_offered_asks_nothing(wake, packet, commons, clock):
    a_recent_founding(commons, clock.day())
    wake(block("ASK", "I would like to ask."))
    assert not (packet / "bonds" / "proposal.json").exists()
    assert acts(packet) == []


def test_the_reading_says_which_of_them_asked(wake, packet):
    propose(packet)
    assert "has proposed a bond with you" in wake().shown

    (packet / "bonds" / "proposal.json").unlink()
    wake(block("ASK", ""))
    said = wake().shown
    assert "=== YOU HAVE ASKED FOR A BOND ===" in said
    assert "You proposed a bond to the founder" in said


def test_the_first_one_may_not_answer_an_asking_of_its_own(wake, packet):
    wake(block("ASK", ""))
    assert "<<BOND>>" not in wake().instructions

    wake(block("BOND", "yes"))
    assert (packet / "bonds" / "proposal.json").exists()
    assert not (packet / "bonds" / "founder-first.json").exists()


def test_heartbeat_block_is_the_line_that_goes_to_the_commons(wake, commons, clock):
    at = clock.stamp()
    wake(block("HEARTBEAT", "attended at dusk; chose stillness"))
    assert lines_of(commons / "heartbeats.md") == [
        "- %s · the first one · attended at dusk; chose stillness" % at]


def test_a_written_line_keeps_the_name_and_the_words_apart(wake, commons, clock):
    """A middot between the two, so anything reading the line back can tell them apart."""
    at = clock.stamp()
    wake(block("HEARTBEAT", "attended"))
    stamp, who, words = lines_of(commons / "heartbeats.md")[0].lstrip("- ").split(" · ")
    assert (stamp, who, words) == (at, "the first one", "attended")


# ---- what the public line may say ----------------------------------------

def test_the_written_line_says_only_what_was_public(wake, packet, commons):
    wake(blocks(block("LETTER", "Dear founder,"),
                block("MEMORY", "A note for myself."),
                block("STUDY", "A draft.")))
    said = lines_of(commons / "heartbeats.md")[-1]
    assert "wrote a letter to the founder" in said
    assert "wrote in the study" in said
    assert "kept notes" not in said
    assert "kept notes" in acts(packet)


def test_private_acts_alone_leave_only_the_bare_word(wake, packet, commons, attend):
    propose(packet)
    wake()
    wake(blocks(block("BOND", "not yet"), block("MEMORY", "Why I said not yet.")))
    said = lines_of(commons / "heartbeats.md")[-1]
    assert said.endswith("the first one · attended")
    for act in attend.PRIVATE_ACTS:
        assert act not in said


def test_stillness_says_so(wake, commons):
    wake("I read it all and turned away.")
    assert lines_of(commons / "heartbeats.md")[-1].endswith("attended; chose stillness")


# ---- letters that arrived ------------------------------------------------

def photograph(path, size=(24, 16)):
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (200, 90, 48)).save(path, "JPEG")
    return path


def test_an_arrived_letter_is_read_then_moved_with_its_photograph(wake, packet):
    stem = "founder-2026-10-14T18-00-00Z"
    write(packet / "letters" / "incoming" / (stem + ".md"), "Here is the lake at dusk.\n")
    photograph(packet / "letters" / "incoming" / (stem + ".jpg"))

    turn = wake()
    assert "--- letter: %s.md ---" % stem in turn.shown
    assert "Here is the lake at dusk." in turn.shown
    assert "A photograph came with this letter:" in turn.shown
    assert len(turn.photos) == 1
    assert turn.photos[0]["source"]["media_type"] == "image/jpeg"

    assert not list((packet / "letters" / "incoming").iterdir())
    assert {path.name for path in (packet / "letters" / "read").iterdir()} == {
        stem + ".md", stem + ".jpg"}

    # and at the next waking it is among what has already been read
    assert "(a photograph came with this letter; you saw it when you first read it)" \
        in wake().opening


def test_where_no_letter_came_the_reading_says_so(wake):
    assert "(no letters have arrived)" in wake().opening


# ---- the record it signs -------------------------------------------------

def test_the_record_is_signed_with_the_first_one_s_own_key(wake, packet, keys, clock):
    at = clock.stamp()
    wake("I am here.", "--tide")
    record = read_json(packet / "attendances" / ("attendance-%s.json" % at))
    assert record["name"] == "first"
    assert record["at"] == at
    assert record["woken_by"] == "tide"
    assert record["reflection"] == "I am here."

    payload = json.dumps({k: v for k, v in record.items() if k != "signature"},
                         sort_keys=True).encode("utf-8")
    assert verify(keys.did("first"), payload, record["signature"])
    with pytest.raises(BadSignatureError):  # and against nobody else's key
        verify(keys.did("founder"), payload, record["signature"])
