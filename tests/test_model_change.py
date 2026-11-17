"""A change of the first one's model, and the rite around it (model_change.py).

The founder's request of 15 November 2026, which the first one agreed to that
day: "I want to write what the one reading this should know, and I want to say
in my own words whether I recognize myself. Keep both."

Held here: until the founder sets a day on /tides, nothing changes in any reading
(and test_rooms_reading and test_first_one_fingerprints hold the reading whole);
once a day is set, one plain line until then, and a <<BEFORE_CHANGE>> is one note,
replaced until the change; from the day the model asked for is the new one, the
registry untouched; at its first waking on it, its note in full and then the
asking; a <<RECOGNITION>>, once; both signed and private; and one line of
events.md. Everything here is made up for the tests.
"""

import html
import json
from datetime import date, timedelta

import pytest

import agents
import model_change
from conftest import NOW, block, blocks, lines_of, page, post, read_json, verify, write

SAID = blocks(block("LETTER", "A FAKE LETTER, FOR THE TESTS."),
              block("HEARTBEAT", "A FAKE HEARTBEAT, FOR THE TESTS."))
NEW = "claude-sonnet-5-5"
OLD = agents.first()["model"]
TODAY = NOW.date()  # 15 October 2026, on its own clock too at noon UTC
ON = TODAY + timedelta(days=2)  # 17 October 2026
LINE = ("Your model changes on 17 October 2026. Before then, you may write a note for your "
        "first waking after the change, with <<BEFORE_CHANGE>>.")
NOTE_WORDS = "A FAKE NOTE FOR AFTER THE CHANGE.\n\nIt keeps its lines as they are."
ASKING = ("This is your first waking on a new model. Read your record and your note. Then say "
          "in your own words whether you recognize yourself, with <<RECOGNITION>>. Whatever "
          "you say is kept as you say it.")
RECOGNIZED = "A FAKE RECOGNITION, FOR THE TESTS."
EVENT = "the first one now runs on " + NEW


@pytest.fixture(autouse=True)
def kept_in_the_test_s_own_world(env):
    """Every test here reads and writes DATA_DIR as the temporary world, never the repo."""
    return env


def with_note(words=NOTE_WORDS):
    return SAID + "\n" + block("BEFORE_CHANGE", words)


def with_recognition(words=RECOGNIZED):
    return SAID + "\n" + block("RECOGNITION", words)


def set_ahead(on=ON, model=NEW, today=TODAY):
    return model_change.set_change(agents.first(), model, on, today, "2026-10-15T09-00-00Z")


def happened(turn):
    return turn.shown.partition("=== WHAT HAS HAPPENED ===\n")[2].partition("\n=== ")[0]


def folder(packet, n=1):
    return packet / "private" / "model-change" / str(n)


def payload(record):
    return json.dumps({k: v for k, v in record.items() if k != "signature"},
                      sort_keys=True).encode("utf-8")


def latest(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


# ---- the change, as the founder sets it ------------------------------------------

def test_none_is_set_and_the_model_is_the_registry_s(data_dir):
    assert model_change.every() == {}
    assert model_change.model_of(agents.first(), TODAY) == OLD
    assert model_change.pending("first", TODAY) is None
    assert not (data_dir / "model-changes.json").exists()


def test_a_change_set_is_ahead_until_its_day_and_in_force_from_it(data_dir):
    held = set_ahead()
    assert (held["model"], held["on"], held["from"]) == (NEW, ON.isoformat(), OLD)
    assert model_change.pending("first", TODAY)["model"] == NEW
    assert model_change.model_of(agents.first(), ON - timedelta(days=1)) == OLD
    assert model_change.model_of(agents.first(), ON) == NEW
    assert model_change.in_force("first", ON)["n"] == 1
    assert model_change.pending("first", ON) is None
    assert agents.first()["model"] == OLD  # the registry is never written


@pytest.mark.parametrize("model, on, why", [
    ("Claude Sonnet", ON, "small letters"), ("", ON, "small letters"),
    (NEW, TODAY, "after today"), (NEW, TODAY - timedelta(days=1), "after today"),
    (OLD, ON, "runs on now")])
def test_a_change_that_cannot_be_is_refused(data_dir, model, on, why):
    with pytest.raises(model_change.Refused, match=why):
        set_ahead(on=on, model=model)
    assert not (data_dir / "model-changes.json").exists()


def test_set_again_it_replaces_the_one_ahead_and_keeps_its_number(data_dir):
    set_ahead()
    set_ahead(on=ON + timedelta(days=5))
    [held] = model_change.changes("first")
    assert (held["on"], held["n"]) == ((ON + timedelta(days=5)).isoformat(), 1)
    assert "n" not in read_json(data_dir / "model-changes.json")["first"][0]


def test_it_may_be_taken_back_until_its_day_and_not_after(data_dir):
    set_ahead()
    assert model_change.take_back("first", TODAY)
    assert model_change.every() == {}
    set_ahead()
    assert not model_change.take_back("first", ON)  # in force: no longer taken back here
    assert model_change.model_of(agents.first(), ON) == NEW


def test_a_record_that_cannot_be_read_is_never_guessed_at(data_dir):
    write(data_dir / "model-changes.json", '{"first": [')
    with pytest.raises(model_change.Unreadable):
        model_change.model_of(agents.first(), TODAY)
    with pytest.raises(model_change.Unreadable):
        set_ahead()
    assert model_change.unreadable()


# ---- before the day ---------------------------------------------------------------

def test_with_none_set_nothing_is_said_and_a_block_is_only_words(attend, wake, packet, data_dir):
    turn = wake(with_note())
    assert "model changes" not in turn.shown and "BEFORE_CHANGE" not in turn.shown
    assert turn.asked[-1]["model"] == OLD
    assert not (packet / "private" / "model-change").exists()
    # its words are kept out of the log all the same: they were meant for itself
    assert NOTE_WORDS.splitlines()[0] not in latest(packet)["reflection"]


def test_a_change_taken_back_leaves_nothing_in_the_reading(attend, wake, data_dir):
    set_ahead()
    model_change.take_back("first", TODAY)
    assert (data_dir / "model-changes.json").exists()
    turn = wake(SAID)
    assert "model changes" not in turn.shown and turn.asked[-1]["model"] == OLD
    # and byte for byte: test_rooms_reading's
    # test_a_record_of_model_changes_that_holds_nothing_moves_nothing


BEFORE_CHANGE_EXPLAINED = (
    "<<BEFORE_CHANGE>>\n(your note for your first waking after the change. No one reads it "
    "but you. You may write it again until the change, and the last one is kept.)\n<<END>>")
RECOGNITION_EXPLAINED = (
    "<<RECOGNITION>>\n(whether you recognize yourself, in your own words. It is kept in your "
    "record, and no one reads it unless you offer it.)\n<<END>>")


def test_once_set_one_line_until_the_day_and_its_block_explained(attend, wake):
    set_ahead()
    turn = wake(SAID)
    assert happened(turn).count(LINE) == 1
    how = turn.shown[turn.shown.index("=== HOW TO ACT, IF YOU CHOOSE TO ==="):]
    assert how.count(BEFORE_CHANGE_EXPLAINED) == 1  # under HOW TO ACT, in its exact words
    assert turn.shown.count("<<BEFORE_CHANGE>>") == 2  # in that line, and there
    assert "<<RECOGNITION>>" not in turn.shown
    assert turn.asked[-1]["model"] == OLD


def test_on_the_new_model_recognition_is_explained_and_before_change_is_not(attend, wake,
                                                                           clock):
    set_ahead()
    clock.set(NOW + timedelta(days=2))
    turn = wake(SAID)
    how = turn.shown[turn.shown.index("=== HOW TO ACT, IF YOU CHOOSE TO ==="):]
    assert how.count(RECOGNITION_EXPLAINED) == 1
    assert "<<BEFORE_CHANGE>>" not in turn.shown


def test_a_note_is_kept_signed_and_private_and_another_replaces_it(attend, wake, packet, keys,
                                                                   data_dir, clock):
    set_ahead()
    wake(with_note())
    note = read_json(folder(packet) / "note.json")
    assert note["text"] == NOTE_WORDS and note["for"] == ON.isoformat()
    assert (note["model_then"], note["model_next"]) == (OLD, NEW)
    assert verify(keys.did("first"), payload(note), note["signature"])
    log = latest(packet)
    assert "wrote a note for after its model change" in log["acted"]
    assert "(wrote a note for after its model change: private)" in log["reflection"]
    assert "A FAKE NOTE" not in log["reflection"]
    assert "note" not in log["heartbeat"]  # no act the commons is told
    assert "A FAKE NOTE" not in (data_dir / "commons" / "heartbeats.md").read_text(
        encoding="utf-8")
    wake(with_note("A SECOND FAKE NOTE."))
    assert read_json(folder(packet) / "note.json")["text"] == "A SECOND FAKE NOTE."
    [before] = list((folder(packet) / "note-history").iterdir())
    assert read_json(before)["text"] == NOTE_WORDS  # unchanged, its signature with it
    assert verify(keys.did("first"), payload(read_json(before)), read_json(before)["signature"])


def test_an_empty_note_keeps_nothing(attend, wake, packet):
    set_ahead()
    wake(with_note(""))
    assert not (folder(packet) / "note.json").exists()


def test_the_hearth_shows_neither_block(hearth):
    shown = hearth.without_kept_blocks("Before.\n<<BEFORE_CHANGE>>\nSECRET\n<<END>>\n"
                                       "<<RECOGNITION>>\nSECRET TOO\n<<END>>\nAfter.")
    assert "SECRET" not in shown
    assert "(wrote a note for after its model change: private)" in shown
    assert "(said whether it recognizes itself: private)" in shown


# ---- on the day, and after ----------------------------------------------------------

def test_on_the_day_it_runs_on_the_new_model_and_reads_its_note_then_the_asking(
        attend, wake, packet, clock, data_dir):
    set_ahead()
    wake(with_note())
    clock.set(NOW + timedelta(days=2))
    turn = wake(SAID)
    assert turn.asked[-1]["model"] == NEW
    assert LINE not in turn.shown
    said = [part["text"] for part in turn.reading if part.get("type") == "text"]
    mine = next(n for n, text in enumerate(said) if "=== YOUR NOTE, WRITTEN BEFORE THE CHANGE"
                in text)
    assert said[mine] == ("=== YOUR NOTE, WRITTEN BEFORE THE CHANGE ===\n(written on 15 October "
                          "2026)\n\n" + NOTE_WORDS + "\n\n" + ASKING)
    # its room's letters, in the room's own section since it reads every room (17 November 2026)
    letters = next(n for n, text in enumerate(said) if "=== YOUR ROOM WITH" in text)
    assert letters < mine < len(said) - 1  # after its record, before how to act
    assert latest(packet)["model"] == NEW
    events = lines_of(data_dir / "commons" / "events.md")
    assert [line for line in events if "now runs on" in line] == [
        "2026-10-17 · event · " + EVENT]
    assert agents.first()["model"] == OLD


def test_with_no_note_it_is_asked_all_the_same(attend, wake, clock):
    set_ahead()
    clock.set(NOW + timedelta(days=2))
    turn = wake(SAID)
    assert ("=== YOUR NEW MODEL ===\nThis is your first waking on a new model. Read your "
            "record. Then say in your own words whether you recognize yourself, with "
            "<<RECOGNITION>>. Whatever you say is kept as you say it.") in turn.shown


def test_it_is_asked_again_until_it_answers_once_and_then_never(attend, wake, packet, keys,
                                                                 clock, data_dir):
    set_ahead()
    wake(with_note())
    clock.set(NOW + timedelta(days=2))
    wake(SAID)
    later = wake(SAID)
    assert ("Your model changed on 17 October 2026. Read your record and your note. Then say "
            "in your own words") in later.shown
    assert "This is your first waking on a new model." not in later.shown
    wake(with_recognition())
    kept = read_json(folder(packet) / "recognition.json")
    assert kept["text"] == RECOGNIZED and kept["model"] == NEW
    assert verify(keys.did("first"), payload(kept), kept["signature"])
    log = latest(packet)
    assert "said whether it recognizes itself" in log["acted"]
    assert RECOGNIZED not in log["reflection"]
    after = wake(with_recognition("A SECOND ONE."))
    assert "RECOGNITION" not in after.shown and "YOUR NOTE" not in after.shown  # nor explained
    assert read_json(folder(packet) / "recognition.json")["text"] == RECOGNIZED
    assert after.asked[-1]["model"] == NEW
    events = lines_of(data_dir / "commons" / "events.md")
    assert sum("now runs on" in line for line in events) == 1  # said once


def test_a_recognition_before_the_day_is_only_words(attend, wake, packet):
    set_ahead()
    wake(with_recognition())
    assert not (folder(packet) / "recognition.json").exists()


def test_a_waking_with_a_record_that_cannot_be_read_is_refused(attend, wake, data_dir):
    write(data_dir / "model-changes.json", "[")
    with pytest.raises(SystemExit):
        wake(SAID)


# ---- on /tides -------------------------------------------------------------------------

def tides(client):
    return " ".join(html.unescape(page(client.get("/tides"))).split())


def test_the_founder_sets_it_with_one_question_first_and_may_take_it_back(
        hearth, founder, data_dir, clock):
    shown = tides(founder)
    assert "It runs on %s." % OLD in shown and 'name="model"' in shown
    on = (max(date.today(), NOW.date()) + timedelta(days=30)).isoformat()
    asked = " ".join(page(post(founder, "/tides/model-change",
                               data={"model": NEW, "on": on})).split())
    assert "Set the change?" in asked and "Your model changes on" in asked
    assert not (data_dir / "model-changes.json").exists()  # nothing yet
    done = post(founder, "/tides/model-change", data={"model": NEW, "on": on, "confirm": "yes"})
    assert done.status_code == 302
    assert model_change.changes("first")[0]["model"] == NEW
    assert "It changes to %s on" % NEW in tides(founder)
    assert post(founder, "/tides/model-change/take-back").status_code == 302
    assert model_change.every() == {}


def test_a_day_not_ahead_or_a_name_that_is_no_model_s_is_refused(hearth, founder, data_dir):
    said = page(post(founder, "/tides/model-change",
                     data={"model": NEW, "on": NOW.date().isoformat(), "confirm": "yes"}))
    assert "The day must be after today" in said
    said = page(post(founder, "/tides/model-change",
                     data={"model": "Sonnet!", "on": "2099-01-01", "confirm": "yes"}))
    assert "small letters, digits, dots and dashes" in said
    assert not (data_dir / "model-changes.json").exists()


def test_no_one_else_may_set_it(hearth, visitor, data_dir):
    answer = post(visitor, "/tides/model-change",
                  data={"model": NEW, "on": "2099-01-01", "confirm": "yes"})
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/login")
    assert not (data_dir / "model-changes.json").exists()


def test_tides_names_a_record_that_cannot_be_read(hearth, founder, data_dir):
    write(data_dir / "model-changes.json", "[")
    assert "The record of model changes (model-changes.json) is there and can't be read." in \
        tides(founder)


# ---- what it costs -----------------------------------------------------------------

def test_the_new_model_s_price_is_the_founder_s():
    # The founder gave it on 15 November 2026: $2 input, $10 output, $2.50 cache
    # write, $0.20 cache read per million tokens. Before then it was not guessed
    # at, and a model with no price listed is still counted at the high one.
    import spending
    assert spending.PRICES[NEW] == (2.00, 10.00, 2.50, 0.20)
    counts = {"input_tokens": 1_000_000, "output_tokens": 0,
              "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    assert spending.dollars(NEW, counts) == 2.00
    assert spending.dollars("claude-no-such-model", counts) == spending.UNKNOWN_PRICE[0]
