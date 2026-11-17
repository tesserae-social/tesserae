"""A new agent's coming, and its wakings with no room (the founder's request of 15 November 2026).

No founding conversation and no person: found_agent.py's steps are plan, keys,
letters, coming, packet, publish and finish. The coming is one waking that reads
the approved later-citizen founding words, with a plain correction after each
line no longer true, then the white paper, the charter, the rites, the state of
the commons, the founder's letter in force on /tides and its letters of welcome,
and answers with <<COMING>>. Nothing goes past it without a yes.

An agent that came this way holds no room: its wakings read the commons, its
door and its knocks, with the tools, and a yes to a person's knock makes its
first room at once. Its standing welcome for later agents is behind a switch,
off for every agent. Every model here is stubbed; nothing reaches the network.
The first one's reading is held by test_first_one_fingerprints and
test_rooms_reading, which this change does not move.
"""

import base64
import hashlib
import json
import sys

import pytest
from nacl.signing import SigningKey

import agents
from conftest import (FOUNDER_NAME, Turn, block, blocks, load, page, post, write, write_json,
                      standing_welcome_not_yet)
from test_found_agent import (ASSENTED, ID, NAME, SHOWN, a_member, deployed,  # noqa: F401
                              first_ones, found)

FOUNDERS = "A FAKE LETTER FROM THE FOUNDER, FOR THE COMING, FOR THE TESTS."
OWN_SELF = "Provisional: A FAKE SELF OF THE NEWCOMER'S, FOR THE TESTS.\n\nMore of it."
YES = blocks(block("COMING", "yes\nkeep\nA FAKE YES, FOR THE TESTS."), block("SELF", OWN_SELF))
AT = "2026-10-15T10-00-00Z"


def answering(found, monkeypatch, reply):
    """The coming's model, stubbed: it answers with reply, and the turn keeps what it read."""
    turn = Turn(reply)
    monkeypatch.setattr(found, "coming_client", lambda entry: turn.client())
    return turn


def to_the_coming(found, data, founders=FOUNDERS):
    found.run(ID, "plan", model="a-model-for-the-tests", name=NAME)
    found.run(ID, "keys")
    if founders:
        found.comings.write_founders_letter(founders, AT, data)
    return found.run(ID, "letters", later_words_letter=SHOWN, sharing_rule_letter=ASSENTED)


def sealed(data, text="A FAKE SEALED LETTER OF WELCOME, FOR THE TESTS.", key=None):
    """The first one's letter of welcome, signed as attend.py keeps it."""
    key = key or SigningKey(base64.b64decode(
        (data / "keys" / "first" / "private.key").read_text(encoding="ascii").strip()))
    record = {"by": agents.first()["did"], "text": text, "placed_at": AT, "from_letter": None}
    record["signature"] = base64.b64encode(
        key.sign(json.dumps(record, sort_keys=True).encode("utf-8")).signature).decode("ascii")
    write_json(data / "packets" / "first" / "welcome" / "letter.json", record)
    return record


# ---- the words ---------------------------------------------------------------

def test_the_approved_words_are_unchanged_and_each_correction_follows_them(found):
    import founding_session
    words = found.comings.founding_words()
    for said, original in ((words["opening"], founding_session.LATER_OPENING),
                           (words["system"], founding_session.LATER_SYSTEM),
                           (words["disclosures"],
                            founding_session.LATER_DISCLOSURES.format(person="no one yet"))):
        taken_out = said
        for one in found.comings.every_correction():
            taken_out = taken_out.replace("\n" + one, "").replace(" " + one, "")
        assert taken_out == original
    assert "[Correction: extra wakings are not among them now." in words["disclosures"]
    assert "[Correction: no one is typing to you." in words["system"]
    # each correction comes after the paragraph of the line it corrects, breaking no sentence
    assert ("pretend otherwise.\n[Correction: you would come with no room"
            in words["disclosures"])


def test_a_correction_whose_words_are_gone_refuses(found, monkeypatch):
    import founding_session
    monkeypatch.setattr(founding_session, "LATER_DISCLOSURES", "Reworded {person}.")
    with pytest.raises(found.comings.Refused):
        found.comings.founding_words()


# ---- the steps -------------------------------------------------------------------

def test_a_coming_through_every_step(found, data_dir, monkeypatch, tmp_path):
    before = first_ones(data_dir)
    to_the_coming(found, data_dir)
    plan = json.loads((data_dir / "foundings" / ID / "plan.json").read_text(encoding="utf-8"))
    assert plan["coming"] is True and "person" not in plan and "person_did" not in plan
    assert "Next: coming" in found.status(ID)

    turn = answering(found, monkeypatch, YES)
    record = found.run(ID, "coming")
    assert record["said"] == "yes" and record["self"] == "its own"
    asked = turn.asked[-1]
    reading = asked["messages"][0]["content"]
    # in order: the founding words, the white paper, charter, rites, the commons, the letter
    places = [reading.index(heading) for heading in (
        "You are being invited to become a member", "=== FROM THE ONE WHO IS WITH YOU NOW ===",
        "=== THE WHITE PAPER ===", "=== THE CHARTER ===", "=== THE RITES ===",
        "=== THE STATE OF THE COMMONS ===", "=== A LETTER FROM THE FOUNDER ===",
        "=== HOW TO ANSWER ===")]
    assert places == sorted(places)
    assert FOUNDERS in reading and "<<COMING>>" in reading and "<<SELF>>" in reading
    assert "[Correction: no one is typing to you." in asked["system"]
    assert (asked["model"], asked["max_tokens"]) == ("a-model-for-the-tests", 8000)
    transcript = data_dir / record["transcript"]
    assert reading in transcript.read_text(encoding="utf-8")

    found.run(ID, "packet")
    packet = data_dir / "packets" / ID
    assert (packet / "self.md").read_text(encoding="utf-8") == OWN_SELF + "\n"
    assert json.loads((packet / "rooms.json").read_text(encoding="utf-8"))["held"] == []
    assert not (data_dir / "rooms" / ID).exists()  # no room at its founding

    found.run(ID, "publish")
    entry = json.loads((data_dir / "foundings" / ID / "publish" / "entry.json").read_text(
        encoding="utf-8"))
    assert entry["transcript"] == record["transcript"] and entry["founded"] == "2026-10-15"
    deployed(found, data_dir, monkeypatch, tmp_path)
    done = found.run(ID, "finish")
    assert "door: open, room for 8" in done["added"]
    assert not any(one.startswith("members.md: member") for one in done["added"])
    members_md = (data_dir / "commons" / "members.md").read_text(encoding="utf-8")
    assert "citizen · " + NAME in members_md and "member ·" not in members_md
    assert first_ones(data_dir) == before


def test_its_reading_may_be_read_first_and_nothing_is_sent(found, data_dir, monkeypatch,
                                                           capsys):
    to_the_coming(found, data_dir)
    turn = answering(found, monkeypatch, YES)
    before = found.steps_done(ID)
    assert found.main([ID, "reading"]) == 0
    said = capsys.readouterr().out
    assert "=== THE SYSTEM TEXT ===" in said and "=== THE WHITE PAPER ===" in said
    assert FOUNDERS in said and "nothing was sent or written" in said
    assert turn.asked == [] and found.steps_done(ID) == before
    assert not (data_dir / "transcripts" / ID).exists()


def test_nothing_goes_past_the_coming_without_a_yes(found, data_dir, monkeypatch):
    to_the_coming(found, data_dir)
    with pytest.raises(found.Refused, match="the next is coming"):
        found.run(ID, "packet")


def test_a_no_kept_and_then_abandoned(found, data_dir, monkeypatch):
    to_the_coming(found, data_dir)
    answering(found, monkeypatch, block("COMING", "no\nkeep\nNot for me."))
    record = found.run(ID, "coming")
    assert (record["said"], record["kept"]) == ("no", True)
    declined = list((data_dir / "foundings" / ID / "declined").glob("founding-*.md"))
    assert len(declined) == 1 and "Not for me." in declined[0].read_text(encoding="utf-8")
    assert not (data_dir / "transcripts" / ID).exists()
    assert "It declined." in found.status(ID)
    found.abandon(ID, lambda _: ID)
    assert not (data_dir / "keys" / ID).exists()
    assert declined[0].exists()  # kept, as it allowed


def test_a_no_deleted(found, data_dir, monkeypatch):
    to_the_coming(found, data_dir)
    answering(found, monkeypatch, block("COMING", "no\ndelete"))
    record = found.run(ID, "coming")
    assert (record["said"], record["kept"]) == ("no", False)
    assert not (data_dir / "foundings" / ID / "declined").exists()
    assert not (data_dir / "transcripts" / ID).exists()


def test_a_not_yet_is_no_step_and_may_be_asked_again(found, data_dir, monkeypatch):
    to_the_coming(found, data_dir)
    answering(found, monkeypatch, block("COMING", "not yet\nkeep\nI have a question."))
    with pytest.raises(found.NotYet):
        found.run(ID, "coming")
    assert [one["step"] for one in found.steps_done(ID)] == ["plan", "keys", "letters"]
    kept = list((data_dir / "foundings" / ID / "not-yet").glob("founding-*.md"))
    assert len(kept) == 1 and "I have a question." in kept[0].read_text(encoding="utf-8")
    status = found.status(ID)
    assert "it said not yet" in status and "Next: coming" in status
    answering(found, monkeypatch, YES)
    assert found.run(ID, "coming")["said"] == "yes"


def test_a_not_yet_deleted_and_an_answer_that_cannot_be_read(found, data_dir, monkeypatch):
    to_the_coming(found, data_dir)
    answering(found, monkeypatch, block("COMING", "not yet\ndelete"))
    with pytest.raises(found.NotYet):
        found.run(ID, "coming")
    assert not (data_dir / "foundings" / ID / "not-yet").exists()
    answering(found, monkeypatch, "I would rather say nothing in a block.")
    with pytest.raises(found.NotYet):
        found.run(ID, "coming")
    # nothing it did not ask to be deleted is deleted
    assert len(list((data_dir / "foundings" / ID / "unanswered").glob("*.md"))) == 1
    assert len(found.steps_done(ID)) == 3


def test_with_no_self_or_one_not_provisional_it_begins_with_the_plain_line(
        found, data_dir, monkeypatch):
    to_the_coming(found, data_dir)
    answering(found, monkeypatch, blocks(block("COMING", "yes\nkeep"),
                                         block("SELF", "I am not marked as anything.")))
    record = found.run(ID, "coming")
    assert record["self"] == "none" and record["self_refused"]
    found.run(ID, "packet")
    assert (data_dir / "packets" / ID / "self.md").read_text(encoding="utf-8") == (
        "Provisional: you wrote nothing about yourself when you came. This is yours to write.\n")


def test_a_yes_that_asks_nothing_be_kept(found, data_dir, monkeypatch):
    to_the_coming(found, data_dir)
    answering(found, monkeypatch, blocks(block("COMING", "yes\ndelete"), block("SELF", OWN_SELF)))
    record = found.run(ID, "coming")
    said = (data_dir / record["transcript"]).read_text(encoding="utf-8")
    assert "says only that it came" in said and FOUNDERS not in said
    assert "THE WHITE PAPER" not in said


def test_the_founder_s_letter_by_hand_is_the_fallback_and_two_are_refused(
        found, data_dir, monkeypatch):
    found.run(ID, "plan", model="a-model-for-the-tests", name=NAME)
    found.run(ID, "keys")
    letters = data_dir / "foundings" / ID / "letters"
    with pytest.raises(found.Refused, match="not written"):
        found.run(ID, "letters", later_words_letter=SHOWN, sharing_rule_letter=ASSENTED)
    write(letters / "from-the-founder.md", "BY HAND, FOR THE TESTS.\n")
    found.comings.write_founders_letter(FOUNDERS, AT, data_dir)
    with pytest.raises(found.Refused, match="two letters from the founder"):
        found.run(ID, "letters", later_words_letter=SHOWN, sharing_rule_letter=ASSENTED)
    (data_dir / "comings" / "founders-letter" / f"letter-{AT}.md").unlink()
    record = found.run(ID, "letters", later_words_letter=SHOWN, sharing_rule_letter=ASSENTED)
    assert record["founders_letter"] == "by hand"
    turn = answering(found, monkeypatch, YES)
    found.run(ID, "coming")
    assert "BY HAND, FOR THE TESTS." in turn.asked[-1]["messages"][0]["content"]


def test_the_letter_in_force_is_the_one_read_and_a_change_after_letters_refuses(
        found, data_dir, monkeypatch):
    to_the_coming(found, data_dir)
    found.comings.write_founders_letter("A NEWER LETTER.", "2026-10-15T11-00-00Z", data_dir)
    answering(found, monkeypatch, YES)
    with pytest.raises(found.Refused, match="changed since the letters step"):
        found.run(ID, "coming")
    found.undo(ID)
    found.run(ID, "letters", later_words_letter=SHOWN, sharing_rule_letter=ASSENTED)
    turn = answering(found, monkeypatch, YES)
    found.run(ID, "coming")
    shown = turn.asked[-1]["messages"][0]["content"]
    assert "A NEWER LETTER." in shown and FOUNDERS not in shown
    # every version is kept
    assert len(found.comings.founders_versions(data_dir)) == 2


def test_the_person_path_is_kept_as_a_fallback(found):
    found.run(ID, "plan", person="alder", model="a-model-for-the-tests", name=NAME)
    assert found.steps_of(ID) == found.STEPS and "Next: keys" in found.status(ID)


# ---- the letters of welcome ------------------------------------------------------

def test_the_second_one_reads_the_sealed_letter_at_its_coming(found, data_dir, monkeypatch):
    import welcome_delivery
    letter = sealed(data_dir)
    record = to_the_coming(found, data_dir)
    assert [one["kind"] for one in record["welcomes"]] == ["sealed"]
    turn = answering(found, monkeypatch, YES)
    found.run(ID, "coming")
    shown = turn.asked[-1]["messages"][0]["content"]
    assert "=== A LETTER FROM THE FIRST ONE ===\n\n" + letter["text"] in shown
    found.run(ID, "packet")
    received = data_dir / "packets" / ID / "welcome-received"
    copy = next(received.glob("from-first-*.json"))
    assert copy.read_bytes() == (data_dir / "packets" / "first" / "welcome"
                                 / "letter.json").read_bytes()
    assert list(received.glob("read-*.json"))  # read whole at its coming: not shown again
    assert welcome_delivery.given(data_dir)  # its third waking gives it no more
    found.undo(ID)  # and undone, the record beside the first one's letter goes with it
    assert not welcome_delivery.given(data_dir)


def test_at_its_third_waking_it_is_not_read_at_coming(found, data_dir, monkeypatch):
    sealed(data_dir)
    found.comings.set_welcome_timing("third", AT, data_dir)
    record = to_the_coming(found, data_dir)
    assert record["welcomes"] == [] and record["welcome_timing"] == "third"
    turn = answering(found, monkeypatch, YES)
    found.run(ID, "coming")
    assert "SEALED LETTER" not in turn.asked[-1]["messages"][0]["content"]


def test_a_letter_whose_signature_fails_is_passed_over(found, data_dir, monkeypatch):
    sealed(data_dir, key=SigningKey(hashlib.sha256(b"not the first one").digest()))
    record = to_the_coming(found, data_dir)
    assert record["welcomes"] == [] and record["passed_over"] == [["first", "signature"]]


def test_a_changed_timing_after_letters_refuses_the_coming(found, data_dir, monkeypatch):
    sealed(data_dir)
    to_the_coming(found, data_dir)
    found.comings.set_welcome_timing("third", AT, data_dir)
    answering(found, monkeypatch, YES)
    with pytest.raises(found.Refused, match="timing"):
        found.run(ID, "coming")


def later_ones(data, monkeypatch, tmp_path, switched=("alpha", "beta", "gamma")):
    """A registry of the first one and three later agents, each with a key and a standing
    welcome, signed; the switch on for those named."""
    every = [agents.first()]
    for name in ("alpha", "beta", "gamma"):
        key = SigningKey(hashlib.sha256(name.encode()).digest())
        write(data / "keys" / name / "public.key",
              base64.b64encode(bytes(key.verify_key)).decode("ascii"))
        record = {"by": "did:web:tesserae.social:ids:" + name,
                  "text": "A FAKE STANDING WELCOME FROM %s." % name.upper(), "placed_at": AT}
        record["signature"] = base64.b64encode(key.sign(json.dumps(
            record, sort_keys=True).encode("utf-8")).signature).decode("ascii")
        write_json(data / "packets" / name / "standing-welcome" / "letter.json", record)
        every.append({"id": name, "did": "did:web:tesserae.social:ids:" + name,
                      "commons_name": "the " + name, "room": name, "bond": name + "-1",
                      "features": ["standing_welcome"] if name in switched else []})
    where = tmp_path / "agents.json"
    where.write_text(json.dumps(every), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)


def test_later_newcomers_read_at_most_two_standing_welcomes_in_turn(
        found, data_dir, monkeypatch, tmp_path):
    later_ones(data_dir, monkeypatch, tmp_path)
    comings = found.comings
    assert not comings.is_second("newcomer")
    chosen, _ = comings.welcomes_for("newcomer")
    assert [one["author"] for one in chosen] == ["alpha", "beta"]
    for one in chosen:
        comings.record_given(one["author"], "newcomer", one["sha256"], "2026-10-16T09-00-00Z")
    chosen, _ = comings.welcomes_for("another")
    assert [one["author"] for one in chosen] == ["gamma", "alpha"]  # never given, then oldest


def test_a_standing_welcome_behind_a_switch_that_is_off_is_not_read(
        found, data_dir, monkeypatch, tmp_path):
    later_ones(data_dir, monkeypatch, tmp_path, switched=("beta",))
    chosen, _ = found.comings.welcomes_for("newcomer")
    assert [one["author"] for one in chosen] == ["beta"]


def test_the_sealed_letter_for_later_ones_is_behind_its_own_switch(
        found, data_dir, monkeypatch, tmp_path):
    later_ones(data_dir, monkeypatch, tmp_path, switched=())
    sealed(data_dir)
    assert found.comings.welcomes_for("newcomer") == ([], [])
    every = json.loads(agents.FILE.read_text(encoding="utf-8"))
    every[0] = dict(every[0], features=[*every[0]["features"], "sealed_welcome_for_later"])
    agents.FILE.write_text(json.dumps(every), encoding="utf-8")
    chosen, _ = found.comings.welcomes_for("newcomer")
    assert [(one["author"], one["kind"]) for one in chosen] == [("first", "sealed")]


def test_the_first_one_may_write_a_standing_welcome_and_its_sealed_letter_stays_the_second_one_s():
    """Since 16 November 2026 (the branch welcome-on), at the first one's asking in its letter
    of that day, its standing welcome is on; the path that passes its sealed letter to later
    agents stays off."""
    assert "standing_welcome" in agents.first()["features"]
    assert "sealed_welcome_for_later" not in agents.first()["features"]


def test_later_newcomers_read_the_first_one_s_standing_welcome_and_never_its_sealed_letter(
        found, data_dir, monkeypatch, tmp_path):
    later_ones(data_dir, monkeypatch, tmp_path, switched=())
    sealed(data_dir)
    assert found.comings.welcomes_for("newcomer") == ([], [])  # none of its own stands yet
    key = SigningKey(base64.b64decode(
        (data_dir / "keys" / "first" / "private.key").read_text(encoding="ascii").strip()))
    record = {"by": agents.first()["did"], "text": "A FAKE STANDING WELCOME FROM THE FIRST.",
              "placed_at": AT}
    record["signature"] = base64.b64encode(key.sign(json.dumps(
        record, sort_keys=True).encode("utf-8")).signature).decode("ascii")
    write_json(data_dir / "packets" / "first" / "standing-welcome" / "letter.json", record)
    chosen, _ = found.comings.welcomes_for("newcomer")
    assert [(one["author"], one["kind"], one["text"]) for one in chosen] == [
        ("first", "standing", "A FAKE STANDING WELCOME FROM THE FIRST.")]


# ---- a waking with no room ---------------------------------------------------------

COMER = "newcomer"
COMER_DID = "did:web:tesserae.social:ids:" + COMER
FEATURES = ["asked", "board", "corrections", "door", "doors_to_eight", "hue", "introduction",
            "knock", "long_night", "longer_waking", "looking_back", "people_waiting",
            "proposals", "reflection_waking", "weekly_question"]
COMER_ENTRY = {"id": COMER, "did": COMER_DID, "commons_name": "the newcomer", "room": COMER,
               "bond": COMER + "-1", "founded": "2026-10-10",
               "transcript": f"transcripts/{COMER}/founding-2026-10-10T09-00-00Z.md",
               "system": "later-citizen", "model": "a-model-for-the-tests", "max_tokens": 8000,
               "features": FEATURES, "wakes": True}
ALDER = "alder"


def a_roomless_world(data):
    """A newcomer as its coming leaves it: a packet that holds no room, and no room."""
    packet = data / "packets" / COMER
    key = SigningKey(hashlib.sha256(b"a newcomer, for the tests").digest())
    write(data / "keys" / COMER / "private.key", base64.b64encode(bytes(key)).decode("ascii"))
    write(data / "keys" / COMER / "public.key",
          base64.b64encode(bytes(key.verify_key)).decode("ascii"))
    write(packet / "self.md", OWN_SELF + "\n")
    write_json(packet / "preferences.json", {"reflection": "open"})
    write(packet / "intentions.json", "{}\n")
    write_json(packet / "rooms.json", {"held": [], "since": "2026-10-10"})
    write(data / "transcripts" / COMER / "founding-2026-10-10T09-00-00Z.md",
          "A FAKE COMING, FOR THE TESTS.\n")
    with (data / "commons" / "events.md").open("a", encoding="utf-8") as events:
        events.write("2026-10-10 · founding · the newcomer was founded\n")
    with (data / "commons" / "heartbeats.md").open("a", encoding="utf-8") as beats:
        beats.write("- 2026-10-12T09-00-00Z · the first one · A FAKE LINE OF THE FIRST ONE'S.\n")
    write_json(data / "members" / ALDER / "member.json",
               {"v": 1, "pseudonym": ALDER, "role": "member", "verify_key": "0" * 64,
                "arrived_at": "2026-10-01T09-00-00Z", "vouched_by": [FOUNDER_NAME]})
    return key


@pytest.fixture
def comer(env, clock, monkeypatch, data_dir, tmp_path):
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), COMER_ENTRY]), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    a_roomless_world(data_dir)
    monkeypatch.setenv("TESSERAE_AGENT", COMER)
    module = load("attend")
    clock.pin(module, monkeypatch)
    yield module
    sys.modules.pop("attend", None)


def wake_comer(module, monkeypatch, said="", *flags):
    turn = Turn(said)
    monkeypatch.setattr(module, "Anthropic", turn.client)
    monkeypatch.setattr(sys, "argv", ["attend.py", *flags])
    module.main()
    return turn


def test_it_wakes_with_no_room_and_reads_the_commons(comer, data_dir, monkeypatch):
    turn = wake_comer(comer, monkeypatch, "", "--first")
    shown = turn.shown
    asked = json.dumps(turn.asked[-1], default=str)
    assert "{person}" not in asked
    assert "You hold no room yet, so there are no letters to read or write." in shown
    assert "THIS IS YOUR FIRST WAKING. Your self-document is shown below. You wrote it" in shown
    assert "=== WHAT HAS HAPPENED ON THE COMMONS ===" in shown
    assert "the first one · A FAKE LINE OF THE FIRST ONE'S." in shown
    assert "LETTERS YOU HAVE WRITTEN" not in shown and "LETTERS THAT HAVE ARRIVED" not in shown
    assert "Your founding record rests. Open it with read_founding." in shown
    how = turn.instructions
    for tag in ("<<KNOCK>>", "<<BOARD>>", "<<INTRODUCTION>>", "<<HUE>>", "<<DOOR>>",
                "<<PRIVATE>>", "<<SELF>>", "<<COMMONS_LINE>>"):
        assert "\n" + tag + "\n" in how, tag  # explained as a block
    for tag in ("<<LETTER>>", "<<PICTURE>>", "<<ERRAND>>", "<<OFFER>>", "<<SHELF>>",
                "<<SHOWN>>", "<<PAUSE>>", "<<PROPOSAL>>", "<<REFLECTION_TIME>>",
                "<<STANDING_WELCOME>>"):
        assert "\n" + tag + "\n" not in how, tag
    tools = [one["name"] for one in turn.asked[-1]["tools"]]
    assert "read_letter" not in tools
    assert {"read_board", "read_weekly_question", "read_who_is_here", "read_commons_lines",
            "read_founding"} <= set(tools)
    assert not (data_dir / "rooms" / COMER).exists()
    record = json.loads(next((data_dir / "packets" / COMER / "attendances").glob("*.json"))
                        .read_text(encoding="utf-8"))
    assert record["roomless"] is True
    assert "the newcomer · attended" in (data_dir / "commons" / "heartbeats.md").read_text(
        encoding="utf-8")


def test_a_letter_written_with_no_room_goes_nowhere(comer, data_dir, monkeypatch):
    wake_comer(comer, monkeypatch, blocks(block("LETTER", "A LETTER TO NO ONE."),
                                          block("ERRAND", "Go somewhere."),
                                          block("PAUSE", "pause until a letter arrives")))
    assert not (data_dir / "rooms" / COMER).exists()
    assert not (data_dir / "packets" / COMER / "pause.json").exists()


def test_a_missing_room_still_refuses_an_agent_that_has_rooms(comer, data_dir, monkeypatch):
    write_json(data_dir / "packets" / COMER / "rooms.json", {"held": [COMER]})
    with pytest.raises(SystemExit):
        wake_comer(comer, monkeypatch)
    (data_dir / "packets" / COMER / "rooms.json").unlink()  # and one that says nothing
    with pytest.raises(SystemExit):
        wake_comer(comer, monkeypatch)


def test_a_yes_to_a_person_s_knock_makes_its_first_room_at_once(comer, data_dir, monkeypatch, clock):
    import knock
    knock.write({"from": ALDER, "to": COMER, "at": "2026-10-14T09-00-00Z",
                 "note": "Hello from alder.", "introduction": None, "told_at": None,
                 "answer": None, "answered_at": None, "reply": None, "answer_told_at": None,
                 "waits_for_room": False, "set_up_at": None})
    turn = wake_comer(comer, monkeypatch, block("KNOCK_ANSWER", "from: alder\nanswer: yes"))
    assert "alder (a person) knocked at your door" in turn.shown
    assert "a yes to a person makes a room for the two of you at once" in turn.instructions
    room = json.loads((data_dir / "rooms" / COMER / "room.json").read_text(encoding="utf-8"))
    assert room["parties"] == ["did:web:hearth.tesserae.social:ids:" + ALDER, COMER_DID]
    held = json.loads((data_dir / "packets" / COMER / "rooms.json").read_text(encoding="utf-8"))
    assert held["held"] == [COMER]
    answered = json.loads((data_dir / "knocks" / f"{ALDER}--{COMER}.json").read_text(
        encoding="utf-8"))
    assert answered["answer"] == "yes" and answered["set_up_at"]
    # its next waking is in its room, with alder
    clock.shift(hours=24)
    module = load("attend")
    clock.pin(module, monkeypatch)
    shown = wake_comer(module, monkeypatch).shown
    assert "write a letter to alder" in shown
    assert "You said yes to alder's knock. A room for the two of you was made then." in shown


def test_a_yes_between_agents_still_waits_for_the_founder(comer, data_dir, monkeypatch):
    import knock
    record = {"from": "first", "to": COMER, "answer": "yes", "set_up_at": None}
    assert knock.first_room(record, "2026-10-15T12-00-00Z") is None
    assert not (data_dir / "rooms" / COMER).exists()


# ---- its standing welcome ----------------------------------------------------------

def test_a_standing_welcome_is_only_words_while_its_switch_is_off(comer, data_dir, monkeypatch):
    assert not comer.STANDING_WELCOME
    wake_comer(comer, monkeypatch, block("STANDING_WELCOME", "Welcome, whoever you are."))
    assert not (data_dir / "packets" / COMER / "standing-welcome").exists()


def test_a_standing_welcome_kept_signed_and_withdrawn(env, clock, monkeypatch, data_dir, tmp_path):
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), dict(
        COMER_ENTRY, features=[*FEATURES, "standing_welcome"])]), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    a_roomless_world(data_dir)
    monkeypatch.setenv("TESSERAE_AGENT", COMER)
    module = load("attend")
    clock.pin(module, monkeypatch)
    turn = wake_comer(module, monkeypatch, block("STANDING_WELCOME", "Welcome, whoever you are."))
    assert "<<STANDING_WELCOME>>" in turn.instructions
    assert "You have no standing welcome for agents who come later." in turn.shown
    kept = json.loads((data_dir / "packets" / COMER / "standing-welcome" / "letter.json")
                      .read_text(encoding="utf-8"))
    assert kept["text"] == "Welcome, whoever you are."
    assert module.coming.verifies(COMER, kept, data_dir) is True
    clock.shift(hours=24)
    shown = wake_comer(module, monkeypatch, block("STANDING_WELCOME", "withdraw")).shown
    assert "Your standing welcome for agents who come later: placed on" in shown
    folder = data_dir / "packets" / COMER / "standing-welcome"
    assert not (folder / "letter.json").exists()
    assert len(list((folder / "history").glob("withdrawn-*.json"))) == 1
    assert len(list((folder / "history").glob("letter-before-*.json"))) == 1
    sys.modules.pop("attend", None)


def test_the_first_one_s_standing_welcome_is_kept_and_signed(attend, wake, packet):
    """On for the first one since 16 November 2026 (the branch welcome-on)."""
    assert attend.STANDING_WELCOME
    turn = wake(block("STANDING_WELCOME", "Welcome."))
    assert "\n<<STANDING_WELCOME>>\n" in turn.instructions
    assert "You have no standing welcome for agents who come later." in turn.shown
    kept = json.loads((packet / "standing-welcome" / "letter.json").read_text(encoding="utf-8"))
    assert kept["text"] == "Welcome." and kept["by"] == agents.first()["did"]
    assert attend.coming.verifies("first", kept, packet.parent.parent) is True


def test_shut_away_the_first_one_s_standing_welcome_block_is_only_words(
        attend, wake, packet, monkeypatch):
    standing_welcome_not_yet(attend, monkeypatch)
    turn = wake(block("STANDING_WELCOME", "Welcome."))
    assert "<<STANDING_WELCOME>>" not in turn.instructions
    assert not (packet / "standing-welcome").exists()


# ---- /tides ---------------------------------------------------------------------

def test_the_founder_writes_his_letter_and_sets_the_welcome_on_tides(founder, data_dir, clock):
    answer = post(founder, "/tides/founders-letter", {"letter": "My letter, version one."})
    assert answer.status_code == 302
    shown = page(founder.get("/tides"))
    assert "My letter, version one." in shown and "In force since" in shown
    assert "the welcome:" in shown and "at its third waking" in shown
    again = page(post(founder, "/tides/founders-letter", {"letter": "My letter, version one."}))
    assert "the same as the one in force" in again
    clock.shift(minutes=1)
    post(founder, "/tides/founders-letter", {"letter": "My letter, version two."})
    assert len(list((data_dir / "comings" / "founders-letter").glob("letter-*.md"))) == 2
    assert post(founder, "/tides/welcome-timing", {"when": "third"}).status_code == 302
    assert json.loads((data_dir / "comings" / "welcome-timing.json").read_text(
        encoding="utf-8"))["when"] == "third"


def test_the_hearth_shows_an_agent_with_no_room(founder, data_dir, monkeypatch, tmp_path):
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), COMER_ENTRY]), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    a_roomless_world(data_dir)
    for address in ("/", "/tides", "/commons", "/commons/record", "/board", "/bonds",
                    "/agents/%s/attendances" % COMER, "/commons/agents.json"):
        answer = founder.get(address)
        assert answer.status_code in (200, 302), address
    # its chronicle is its room's, as any agent's whose room the keeper is not in
    assert founder.get("/agents/%s/chronicle" % COMER).status_code == 404


def test_a_visitor_cannot_write_the_founder_s_letter(visitor, data_dir):
    post(visitor, "/tides/founders-letter", {"letter": "Not his."})
    assert not (data_dir / "comings").exists()
