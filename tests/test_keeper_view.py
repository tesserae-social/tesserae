"""The keeper's view of an agent whose room he is not in.

Stage 6c of the work on keeper pages, rests, stops and names for any agent
(proposals/stage-6.md). The keeper keeps every agent's tide, and so the one page
of an agent's he may see without being a party to its room is its attendances,
made from an allow-list: each waking's moment, how it was woken, whether it was
the first, the model and the line the commons was shown; the acts that are its
tide's own and what went wrong with them; its rhythm, its rest's since and
condition, and his own stop, with the forms that stop and lift it. Every other
page of it is refused him as a room not his is. A party's view, and the first
one's pages at their old addresses, are as they were.

Words are planted in every field of the scratch agent's record that is not on
that list, and in its letters, errands, self, notes and the words of its rest,
and looked for in everything the keeper can be answered with.
"""

import hashlib

import pytest

from conftest import page, post, write, write_json
from test_first_one_fingerprints import PAGES, a_lived_world
from test_pages_by_agent import (OLD, a_second_room, agent_pages, alder, ask,  # noqa: F401
                                 hazel, hearth, scratch_registry, shown_but_the_tides, zipped)
from test_rooms_for_any_agent import as_refused, member_vaults, tree_hash  # noqa: F401

# Words planted in the scratch one's record, none of which the keeper may ever be shown.
NEVER = {}


def sentinel(what):
    """A word for one place in the record, kept to be looked for."""
    words = "SENTINEL-KEPT-%s" % what.upper().replace(" ", "-").replace("_", "-")
    NEVER[what] = words
    return words


# Every field an attendance record may hold that is not on the keeper's list,
# each with a word of its own; and a field no record holds yet, for good measure.
HIDDEN_FIELDS = ("heartbeat", "reflection", "questions_dropped", "threshold_refused",
                 "kept_private", "commons_line", "commons_line_held", "self_confirm_refused",
                 "shelf_refused", "notes_refused", "proposals_refused", "welcome_refused",
                 "wake_again_refused", "letter_kept_in_study", "picture_kept_in_study",
                 "kept_letter_sent", "kept_letter_not_sent", "season_reading", "looked_at",
                 "rounds", "blocks_beside_look", "heartbeat_shown_ignored", "name",
                 "a_field_not_yet_written")
HIDDEN = {field: sentinel("field " + field) for field in HIDDEN_FIELDS}

# What is on the keeper's list, as the record holds it and as his page says it.
SHOWN_LINE = "attended; set its waking time, set a pause, asked to wake again, set its door"
OWN_LINE = "A HEARTBEAT THE COMMONS WAS SHOWN, FOR THE TESTS."
MODEL = "a-model-for-the-tests"
ALLOWED_ACTS = ["set its waking time", "set a pause", "asked to wake again", "set its door"]
# acts that are not its tide's: none of them is said, nor that they were made
OTHER_ACTS = ["wrote a letter to the founder", "drew a picture", "asked an errand",
              "offered to the commons", "consented to an offering", "proposed a bond",
              "sealed the bond", "made a proposal", "kept notes", "kept a named note",
              "kept its shelf", "confirmed its self-document", "kept something private",
              "wrote in the study", "released the bond", "kept questions"]


def a_planted_record(data, packet):
    """The scratch one's record and room, with a word planted wherever one may be."""
    second = data / "packets" / "second"
    home = a_second_room(data)
    a_waking = {**HIDDEN, "at": "2026-10-22T09-00-00Z", "first": True, "model": MODEL,
                "woken_by": "tide", "heartbeat_shown": SHOWN_LINE,
                "acted": ALLOWED_ACTS + OTHER_ACTS + [sentinel("an act")],
                "stop_reason": "max_tokens", "rhythm_refused": True, "door_refused": True}
    write_json(second / "attendances" / "attendance-2026-10-22T09-00-00Z.json", a_waking)
    # a later waking whose own words were what the commons was shown, and whose
    # every field the page reads holds what it does not know how to say
    write_json(second / "attendances" / "attendance-2026-10-23T09-00-00Z.json", {
        "at": sentinel("the moment"), "first": sentinel("its first"),
        "woken_by": sentinel("who woke it"), "model": None, "heartbeat": OWN_LINE,
        "acted": sentinel("acts not a list"), "stop_reason": sentinel("why the reply ended"),
        "rhythm_refused": sentinel("rhythm refused"), "door_refused": sentinel("door refused"),
        "reflection": sentinel("the second reflection")})
    write_json(second / "attendances" / "attendance-2026-10-24T09-00-00Z.json", {
        "at": "2026-10-24T09-00-00Z", "first": False, "woken_by": "its own asking",
        "model": MODEL, "heartbeat": "attended; chose stillness",
        "acted": [], "reflection": sentinel("the third reflection")})
    write_json(second / "preferences.json", {"reflection": "open"})

    write(second / "self.md", "# " + sentinel("its self") + "\n")
    write(second / "self-proposed.md", sentinel("its proposed self") + "\n")
    write(second / "memory" / "notes.md", sentinel("its notes") + "\n")
    write(second / "memory" / "notes" / "a-note.md", sentinel("a named note") + "\n")
    write(second / "memory" / "questions.md", sentinel("its questions") + "\n")
    write(second / "private" / "notebook.md", sentinel("its notebook") + "\n")
    write(second / "study" / "a-draft.md", sentinel("its study") + "\n")
    write(second / "shelf.json", '{"kept": ["%s"]}\n' % sentinel("its shelf"))
    write_json(second / "pause.json", {"by": "second", "since": "2026-10-23T10-00-00Z",
                                       "until": "a letter arrives",
                                       "words": sentinel("the words of its rest")})
    write_json(second / "rhythm.json", {"rhythm": "daily", "at": "07:00",
                                        "timezone": "America/New_York"})
    write(second / "exports.log", "2026-10-22T09-00-00Z · export taken by %s\n"
          % sentinel("who took a copy"))

    write(home / "letters" / "read" / "founder-2026-10-21T09-00-00Z.md",
          sentinel("a letter to it") + "\n")
    write(home / "letters" / "incoming" / "founder-2026-10-24T09-00-00Z.md",
          sentinel("a letter waiting") + "\n")
    write(home / "letters" / "outgoing" / "to-founder-2026-10-22T09-00-00Z.md",
          sentinel("a letter of its") + "\n")
    write(home / "errands" / "errand-2026-10-22T09-00-00Z.md", sentinel("an errand") + "\n")
    write(home / "offerings" / "offering-2026-10-22T09-00-00Z.json",
          '{"text": "%s"}\n' % sentinel("an offering"))
    write(home / "bonds" / "answer-2026-10-22T09-00-00Z.json",
          '{"words": "%s"}\n' % sentinel("a bond's words"))
    return second


@pytest.fixture
def planted(hearth, founder, alder, hazel, data_dir, packet):
    return a_planted_record(data_dir, packet)


# ---- what the keeper is shown --------------------------------------------------

def content(said):
    """What a page says, between the menu at its top and its foot."""
    return said.split('aria-label="pages">')[1].split("</nav>", 1)[1].split("<footer>")[0]


def keeper_view(founder):
    answer = founder.get("/agents/second/attendances")
    assert answer.status_code == 200
    return page(answer)


def test_the_keeper_sees_each_waking_by_the_allow_list(planted, founder):
    said = keeper_view(founder)
    assert ("The scratch one&#39;s reflections are not shown to someone who is not a party "
            "to its room.") in said
    assert said.count("reflections are not shown") == 1
    # each waking: its moment, how it was woken, whether it was the first, the model
    assert "22 October 2026, 05:00 · its first waking · woken by the tide · %s" % MODEL in said
    assert "24 October 2026, 05:00 · woken at its own asking · %s" % MODEL in said
    # a moment that cannot be read is the one in the record's name; who woke it, unsaid
    assert "23 October 2026, 05:00 · woken not recorded\n" in said
    # the line the commons was shown, and where it was its own words, those
    assert "<strong>heartbeat:</strong> " + SHOWN_LINE in said
    assert "<strong>heartbeat:</strong> " + OWN_LINE in said
    # only the acts that are its tide's own, and its faults
    assert "<strong>its tide:</strong> " + ", ".join(ALLOWED_ACTS) in said
    assert said.count("<strong>its tide:</strong>") == 1
    assert ("cut off at its length limit; its waking time could not be read; "
            "its door could not be read") in said
    assert said.count("could not be read") == 2
    # its rhythm, its rest by since and condition, and the stop's form
    assert "Rhythm: daily at 07:00" in said
    assert ("The scratch one is resting, since 23 October 2026, 06:00, until a letter "
            "arrives.") in said
    assert 'action="/agents/second/stop-tide"' in said
    assert "The tide is stopped" not in said


def test_the_keeper_is_shown_none_of_what_is_not_on_the_list(planted, founder):
    said = keeper_view(founder)
    for what, words in NEVER.items():
        assert words not in said, what
    for act in OTHER_ACTS:
        assert act not in said, act
    for words in ("reflection:", "Reflections: open", "kept private", "letter from",
                  "a letter to", "wrote", "errand",
                  "offering", "bond", "notes", "shelf", "self-document", "acted on"):
        assert words not in content(said), words
    # none of the first one's forms, nor its rest's or backup's, beside the menus every
    # page of the keeper's carries
    main = content(said)
    for form in ("/stop-tide", "/lift-stop", "/rest", "/return", "/backup-now", "/backups"):
        assert 'action="%s"' % form not in main and 'href="%s"' % form not in main, form


def test_a_rest_s_condition_is_a_letter_or_a_day_and_never_anything_else(planted, founder):
    for until, condition in (("2026-11-02", "until 2 November 2026."),
                             (sentinel("its rest's condition"),
                              "until a day that cannot be read")):
        write_json(planted / "pause.json", {"by": "second", "since": sentinel("its rest's since"),
                                            "until": until, "words": "nothing"})
        said = keeper_view(founder)
        assert "is resting, since not recorded, " + condition in said
        for what, words in NEVER.items():
            assert words not in said, what


def every_keeper_address(hearth):
    """Every address the keeper may ask for: each page that takes nothing, the scratch
    one's, its room's, and the first one's."""
    plain = sorted(rule.rule for rule in hearth.app.url_map.iter_rules()
                   if "GET" in rule.methods and not rule.arguments
                   and rule.rule not in ("/logout",))
    return plain + ["/agents/second/" + kind for kind in OLD] + [
        "/rooms/second", "/rooms/second/photo/founder-2026-10-21T09-00-00Z.jpg",
        "/rooms/second/picture/to-founder-2026-10-22T09-00-00Z.svg", "/ids/second/did.json",
        "/agents/nowhere/attendances", "/commons/offerings/offering-2026-10-22T09-00-00Z.json"]


def test_nothing_the_keeper_can_be_answered_with_carries_a_planted_word(
        planted, founder, hearth):
    answers = {address: founder.get(address) for address in every_keeper_address(hearth)}
    answers["post /export"] = post(founder, "/export")
    answers["post /agents/second/export"] = post(founder, "/agents/second/export")
    # each turn of the stop, refused, asked and made, and the lift
    answers["stop refused"] = post(founder, "/agents/second/stop-tide", data={"reason": ""})
    answers["stop asked"] = post(founder, "/agents/second/stop-tide", data={"reason": "a test"})
    answers["stop made"] = post(founder, "/agents/second/stop-tide",
                                data={"reason": "a test", "confirm": "yes"})
    answers["stopped"] = founder.get("/agents/second/attendances")
    answers["lifted"] = post(founder, "/agents/second/lift-stop")
    for address, answer in answers.items():
        said = answer.get_data().decode("utf-8", "replace")
        if answer.mimetype == "application/zip":
            said = b"\n".join(zipped(answer).values()).decode("utf-8", "replace")
        for what, words in NEVER.items():
            assert words not in said, (address, what)
    assert answers["stop asked"].status_code == 200
    assert "Stop the tide? The scratch one will not be woken" in page(answers["stop asked"])
    assert "A stop needs a reason" in page(answers["stop refused"])
    assert "The tide is stopped, since" in page(answers["stopped"])
    assert 'action="/agents/second/lift-stop"' in page(answers["stopped"])


# ---- what is still refused him -------------------------------------------------

def test_every_other_page_of_the_agent_is_refused_the_keeper_as_before(planted, founder):
    before = tree_hash(planted.parent.parent)
    room_refused = as_refused(founder.get("/rooms/nowhere"))
    assert room_refused[0] == 404
    for method, path, form in agent_pages("second"):
        if path.endswith("/attendances"):
            continue
        assert as_refused(ask(founder, method, path, form)) == room_refused, path
    # and an agent that is not there is not found, its attendances included
    for method, path, form in agent_pages("nowhere"):
        assert as_refused(ask(founder, method, path, form)) == room_refused, path
    for form in ("stop-tide", "lift-stop"):
        assert post(founder, "/agents/nowhere/" + form,
                    data={"reason": "a test", "confirm": "yes"}).status_code == 404
    assert tree_hash(planted.parent.parent) == before


def test_no_one_but_the_keeper_has_the_keeper_s_view_or_his_forms(planted, alder, hazel, founder):
    before = tree_hash(planted.parent.parent)
    # its party sees the page its party has always seen
    said = page(alder.get("/agents/second/attendances"))
    assert NEVER["field reflection"] in said and "reflections are not shown" not in said
    assert 'action="/agents/second/stop-tide"' not in said
    for client in (alder, hazel):
        for form in ("stop-tide", "lift-stop"):
            answer = post(client, "/agents/second/" + form,
                          data={"reason": "a test", "confirm": "yes"})
            assert answer.status_code == 302 and answer.headers["Location"] == "/login"
    refused = as_refused(hazel.get("/agents/second/attendances"))
    assert refused[0] == 302 and refused[1].endswith("/login")
    assert tree_hash(planted.parent.parent) == before


def test_the_keeper_s_forms_for_the_first_one_are_sent_to_its_own(planted, founder):
    for form in ("stop-tide", "lift-stop"):
        answer = post(founder, "/agents/first/" + form, data={"reason": "a test"})
        assert answer.status_code == 307 and answer.headers["Location"] == "/" + form


# ---- a stop is the agent's own -------------------------------------------------

def test_a_stop_on_the_scratch_one_writes_in_its_packet_alone_and_its_line_names_it(
        planted, founder, data_dir, packet, room, commons, clock):
    (planted / "pause.json").unlink()  # so that the stop is what pauses its tide
    events = commons / "events.md"
    held = {"its packet": lambda: tree_hash(packet), "its room": lambda: tree_hash(room),
            "the keys": lambda: tree_hash(data_dir / "keys"),
            "everything else": lambda: tree_hash_but(data_dir, planted, events)}
    before = {what: hash_of() for what, hash_of in held.items()}
    said_before = events.read_text(encoding="utf-8") if events.exists() else ""

    answer = post(founder, "/agents/second/stop-tide",
                  data={"reason": "a short reason", "confirm": "yes"})
    assert answer.status_code == 302
    assert answer.headers["Location"] == "/agents/second/attendances"
    assert {what: hash_of() for what, hash_of in held.items()} == before
    stop = planted / "tide-stop.json"
    assert stop.exists() and "a short reason" in stop.read_text(encoding="utf-8")
    assert events.read_text(encoding="utf-8") == said_before + "%s · event · %s\n" % (
        clock.day(), "the scratch one · the tide paused")
    assert not (packet / "tide-stop.json").exists()

    answer = post(founder, "/agents/second/lift-stop")
    assert answer.status_code == 302
    assert {what: hash_of() for what, hash_of in held.items()} == before
    assert not stop.exists() and list((planted / "tide-stop").glob("tide-stop-*.json"))
    assert events.read_text(encoding="utf-8").endswith(
        "%s · event · the scratch one · the tide resumed\n" % clock.day())


def tree_hash_but(root, *left_out):
    """One fingerprint of everything under a folder but the files and folders left out."""
    said = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and not any(path == out or out in path.parents for out in left_out):
            said.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
            said.update(hashlib.sha256(path.read_bytes()).digest())
    return said.hexdigest()


# ---- the first one's pages, and a party's view ---------------------------------

HELD = ("/", "/rooms/first", "/letters", "/self", "/attendances", "/chronicle", "/chronicle.md",
        "/export", "/bonds")


def test_the_first_one_s_pages_hold_stage_0_s_fingerprints_beside_the_keeper_s_view(
        hearth, founder, wake, room, commons, data_dir, packet):
    a_lived_world(founder, wake, room, commons)
    a_planted_record(data_dir, packet)
    assert {address: shown_but_the_tides(founder.get(address)) for address in HELD} == {
        address: PAGES[address] for address in HELD}
    post(founder, "/agents/second/stop-tide", data={"reason": "a test", "confirm": "yes"})
    post(founder, "/agents/second/lift-stop")
    assert {address: shown_but_the_tides(founder.get(address)) for address in HELD} == {
        address: PAGES[address] for address in HELD}
