"""person-rooms (the founder's request of 25 November 2026): rooms between two people.

1. The founder's notes page showed nothing: the answer is kept with the knock (knocks/), and the
   notes page showed only notes (notes/), so a yes with no notes written showed an empty page.
   move_to_ids.py moves the notes too. Both are tested here.
2. A yes between two people opens a room of letters, the same page as a room with an agent, with
   no bond section and no bond possible; a letter is delivered at once.
3. Every room shows the knock and its answer at its top.
4. notes_to_rooms.py makes old notes the first letters of a room: a dry run, --apply, --undo,
   the notes files untouched; an old /notes link leads to the room.
5. The home page, /people, the email, copies and leaving treat them as any room.
6. One set of words; no page says notes for a conversation.
7. A knock is one note and one answer; the form says its limit.
8. A closed room put away, for one side only, listed on settings, brought back.

The world is test_introductions': hazel signed in, alder a member, and the second one.
"""

import json
from datetime import datetime, timezone

import pytest

from conftest import PASSWORD, FOUNDER_NAME, page, person_rooms_now, post, write_json
from test_introductions import switched_registry, world  # noqa: F401 - fixtures
from test_later_citizen import ALDER, HAZEL
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

KNOCK_NOTE = "Hello there, shall we write?"
REPLY = "Gladly, I would like that."


@pytest.fixture
def on(world, monkeypatch):
    """The world with person-rooms on, and the home page's conversations and the people page."""
    person_rooms_now(world.hearth)
    monkeypatch.setattr(world.hearth, "in_the_background", lambda work: work())
    monkeypatch.setattr(world.hearth, "CONVERSATIONS", True)
    monkeypatch.setattr(world.hearth, "PEOPLE_PAGES", True)
    return world


def alder_client(world):
    client = world.hearth.app.test_client()
    assert post(client, "/login", data={"pseudonym": ALDER, "password": PASSWORD}
                ).status_code == 302
    return client


def knock_and_yes(world, alder=None):
    """hazel knocks at alder from the knock page; alder says yes from the knocks page."""
    assert world.post("/knock/" + ALDER, note=KNOCK_NOTE).status_code == 302
    alder = alder or alder_client(world)
    assert post(alder, "/knock/answer", data={"from": HAZEL, "answer": "yes",
                                              "reply": REPLY}).status_code == 302
    world.clock.shift(minutes=1)
    return alder


def the_room(world):
    import knock
    held = knock.read(HAZEL, ALDER)
    return held["room"]


# ---- 1. the diagnosis -----------------------------------------------------------------

def test_before_person_rooms_a_yes_with_no_notes_shows_an_empty_notes_page(world):
    """The founder's case: the answer lives with the knock, and the notes page shows notes only."""
    import knock
    assert world.post("/knock/" + ALDER, note=KNOCK_NOTE).status_code == 302
    assert knock.answer(HAZEL, ALDER, "yes", REPLY, "2026-10-15T12-30-00Z")
    said = page(world.client.get("/notes/" + ALDER))
    assert "No notes yet." in said and REPLY not in said
    assert REPLY in json.dumps(knock.read(HAZEL, ALDER))  # kept with the knock


def test_move_to_ids_moves_notes_under_the_keeper_s_old_name(tmp_path, monkeypatch):
    import move_to_ids
    root = tmp_path
    write_json(root / "members" / "oldname" / "member.json", {"role": "keeper"})
    write_json(root / "notes" / "alder--oldname.json", {
        "between": ["alder", "oldname"],
        "notes": [{"from": "oldname", "at": "2026-10-15T12-00-00Z", "words": "hi"}]})
    made = move_to_ids.plan(root)
    moved = {(s.name, t.name) for s, t in made["moves"]}
    assert ("alder--oldname.json", "alder--founder.json") in moved
    rewrite = next(changed for path, _, changed in made["rewrites"]
                   if path.name == "alder--founder.json")
    assert rewrite["between"] == ["alder", "founder"]
    assert rewrite["notes"][0]["from"] == "founder"


# ---- 2. a room between two people -----------------------------------------------------

def test_a_yes_between_two_people_opens_a_room_at_once(on, data_dir):
    import rooms
    knock_and_yes(on)
    room_id = the_room(on)
    held = json.loads((data_dir / "rooms" / room_id / "room.json").read_text(encoding="utf-8"))
    assert held["kind"] == "people" and held["from_knock"] == "%s--%s" % (HAZEL, ALDER)
    assert [room.kind for room in rooms.of(HAZEL)] == ["people"]
    assert all(room.kind != "people" for room in rooms.of("second"))  # never an agent's
    said = page(on.client.get("/rooms/" + room_id))
    assert "write to " + ALDER in said
    assert 'id="bond"' not in said and "proposes a bond" not in said
    assert "They can read it as soon as it is sent. It is kept." in said


def test_a_letter_between_people_is_delivered_at_once_both_ways(on):
    alder = knock_and_yes(on)
    room_id = the_room(on)
    answer = on.post("/rooms/" + room_id, letter="A first letter, from hazel.")
    assert answer.status_code == 302
    assert "Your letter is delivered. They can read it now." in page(
        on.client.get(answer.headers["Location"]))
    theirs = page(alder.get("/rooms/" + room_id))
    assert "A first letter, from hazel." in theirs and "from " + HAZEL in theirs
    assert post(alder, "/rooms/" + room_id, data={"letter": "And back, from alder."}
                ).status_code == 302
    assert "And back, from alder." in page(on.client.get("/rooms/" + room_id))


def test_no_bond_is_possible_in_a_room_of_two_people(on):
    knock_and_yes(on)
    room_id = the_room(on)
    on.post("/rooms/" + room_id, letter="Shall we?", proposes="1")
    import rooms
    places = rooms.places(room_id)
    assert not places.proposal.exists()
    on.clock.shift(days=40)
    assert on.client.get("/rooms/%s/bond/seal" % room_id).status_code in (404, 405)
    assert post(on.client, "/rooms/%s/bond/answer" % room_id,
                data={"answer": "yes"}).status_code == 404


def test_a_block_stops_letters_in_the_room(on):
    knock_and_yes(on)
    room_id = the_room(on)
    import blocks
    blocks.block(HAZEL, ALDER, "2026-10-15T13-00-00Z")
    said = page(on.client.get("/rooms/" + room_id))
    assert "No letters can be written here while one of you has blocked the other." in said
    on.post("/rooms/" + room_id, letter="After the block.")
    assert "After the block." not in page(on.client.get("/rooms/" + room_id))


def test_a_room_of_two_people_is_not_counted_against_a_door(on):
    import door
    knock_and_yes(on)
    assert door.in_use(HAZEL) == 0


def test_the_keeper_and_a_person_have_a_room_named_founder(on, founder_vault, data_dir):
    on.hearth.members.create_member(FOUNDER_NAME, json.loads(json.dumps(founder_vault)),
                                    "keeper", [])
    on.hearth.door.set_door(FOUNDER_NAME, state="open", room=2, at="2026-10-01T09-00-00Z")
    keeper = on.hearth.app.test_client()
    assert post(keeper, "/login", data={"pseudonym": FOUNDER_NAME, "password": PASSWORD}
                ).status_code == 302
    assert on.post("/knock/founder", note=KNOCK_NOTE).status_code == 302
    assert post(keeper, "/knock/answer", data={"from": HAZEL, "answer": "yes",
                                               "reply": REPLY}).status_code == 302
    import knock
    room_id = knock.read(HAZEL, FOUNDER_NAME)["room"]
    assert room_id == "founder-hazel"
    assert (data_dir / "rooms" / room_id / "letters" / "from-founder").is_dir()
    assert FOUNDER_NAME not in (data_dir / "rooms" / room_id / "room.json").read_text(
        encoding="utf-8")
    assert post(keeper, "/rooms/" + room_id, data={"letter": "From the founder."}
                ).status_code == 302
    said = page(on.client.get("/rooms/" + room_id))
    assert "From the founder." in said and "from the founder" in said
    home = page(keeper.get("/"))
    assert '<a href="/rooms/%s">open the room</a>' % room_id in home
    # the knock form says no more may be sent: the two write to each other already
    assert "You already write to each other." in page(on.client.get("/knock/founder"))


# ---- 3. the knock at the top of every room ---------------------------------------------

def test_every_room_begins_with_its_knock_and_answer(on):
    knock_and_yes(on)
    said = page(on.client.get("/rooms/" + the_room(on)))
    began = said.split('<section id="began">')[1].split("</section>")[0]
    assert "how it began" in began and "you knocked" in began
    assert KNOCK_NOTE in began and REPLY in began and ALDER + " answered yes" in began
    assert said.index('id="began"') < said.index('id="write"')


def test_a_room_with_an_agent_begins_with_its_knock_too(on, data_dir):
    import knock
    write_json(data_dir / "knocks" / ("%s--second.json" % ALDER), {
        "from": ALDER, "to": "second", "at": "2026-10-10T09-00-00Z", "note": "Hello, second.",
        "answer": "yes", "answered_at": "2026-10-11T09-00-00Z", "reply": "Hello, alder.",
        "set_up_at": "2026-10-11T09-00-00Z"})
    alder = alder_client(on)
    room = next(one for one in on.hearth.rooms.of(ALDER) if one.kind == "person")
    said = page(alder.get("/rooms/" + room.id))
    assert "Hello, second." in said.split('<section id="began">')[1].split("</section>")[0]
    assert knock.read(ALDER, "second")  # read only


# ---- 4. the script --------------------------------------------------------------------

def notes_between(data_dir):
    import knock
    import notes
    now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
    assert knock.knock(HAZEL, ALDER, KNOCK_NOTE, now)
    assert knock.answer(HAZEL, ALDER, "yes", REPLY, "2026-10-15T12-30-00Z")
    assert notes.write(HAZEL, ALDER, "A note from hazel.", datetime(2026, 10, 15, 13, tzinfo=timezone.utc))
    assert notes.write(ALDER, HAZEL, "A note from alder.", datetime(2026, 10, 15, 14, tzinfo=timezone.utc))
    return (data_dir / "notes" / "alder--hazel.json").read_bytes()


def backed_up(data_dir):
    at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")  # the script's own clock
    (data_dir / "backup.log").write_text("%s · backed up · x · kept 1\n" % at, encoding="utf-8")


def test_the_script_dry_run_changes_nothing(world, data_dir, capsys, monkeypatch):
    import notes_to_rooms
    held = notes_between(data_dir)
    knocks_before = (data_dir / "knocks" / "hazel--alder.json").read_bytes()
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    assert notes_to_rooms.main([]) == 0
    said = capsys.readouterr().out
    assert "room     rooms/alder-hazel" in said
    assert "letter   from-hazel/hazel-2026-10-15T13-00-00Z.md" in said
    assert "A dry run: nothing was changed." in said
    assert not (data_dir / "rooms" / "alder-hazel").exists()
    assert (data_dir / "knocks" / "hazel--alder.json").read_bytes() == knocks_before
    assert (data_dir / "notes" / "alder--hazel.json").read_bytes() == held


def test_the_script_applies_and_undoes(world, data_dir, monkeypatch, capsys):
    import notes_to_rooms
    import knock
    held = notes_between(data_dir)
    knocks_before = (data_dir / "knocks" / "hazel--alder.json").read_bytes()
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    assert notes_to_rooms.main(["--apply"]) == 1  # no backup yet
    assert "take an encrypted backup first" in capsys.readouterr().out
    backed_up(data_dir)
    assert notes_to_rooms.main(["--apply"]) == 0
    home = data_dir / "rooms" / "alder-hazel"
    assert (home / "letters" / "from-hazel" / "hazel-2026-10-15T13-00-00Z.md").read_text(
        encoding="utf-8") == "A note from hazel.\n"
    assert (home / "letters" / "from-alder" / "alder-2026-10-15T14-00-00Z.md").is_file()
    assert knock.read(HAZEL, ALDER)["room"] == "alder-hazel"
    assert (data_dir / "notes" / "alder--hazel.json").read_bytes() == held  # untouched
    assert notes_to_rooms.main(["--apply"]) == 1  # a run is recorded already
    # the room is the two's, and its letters are seen, so no email tells of old notes
    person_rooms_now(world.hearth)
    said = page(world.client.get("/rooms/alder-hazel"))
    assert "A note from hazel." in said and "A note from alder." in said
    assert world.hearth.waiting_for(HAZEL) == ([], set())
    # an old /notes link leads to the room
    answer = world.client.get("/notes/" + ALDER)
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/rooms/alder-hazel")
    assert notes_to_rooms.main(["--undo"]) == 0
    assert not home.exists()
    assert (data_dir / "knocks" / "hazel--alder.json").read_bytes() != b""
    assert json.loads((data_dir / "knocks" / "hazel--alder.json").read_text(
        encoding="utf-8")) == json.loads(knocks_before)
    assert (data_dir / "notes" / "alder--hazel.json").read_bytes() == held


def test_the_script_will_not_undo_a_letter_written_since(world, data_dir, monkeypatch, capsys):
    import notes_to_rooms
    notes_between(data_dir)
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    backed_up(data_dir)
    assert notes_to_rooms.main(["--apply"]) == 0
    later = data_dir / "rooms" / "alder-hazel" / "letters" / "from-hazel" / "hazel-2026-10-16T09-00-00Z.md"
    later.write_text("Written since.\n", encoding="utf-8")
    assert notes_to_rooms.main(["--undo"]) == 1
    assert "holds what this run did not write" in capsys.readouterr().out
    assert later.is_file()


def test_a_yes_with_no_notes_gets_its_room_too(world, data_dir, monkeypatch):
    """The founder's case, mended: the room begins with the knock and its answer."""
    import knock
    import notes_to_rooms
    now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
    assert knock.knock(HAZEL, ALDER, KNOCK_NOTE, now)
    assert knock.answer(HAZEL, ALDER, "yes", REPLY, "2026-10-15T12-30-00Z")
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    backed_up(data_dir)
    assert notes_to_rooms.main(["--apply"]) == 0
    person_rooms_now(world.hearth)
    said = page(world.client.get("/rooms/alder-hazel"))
    assert REPLY in said.split('<section id="began">')[1]


# ---- 5. home, people, email, copies, leaving ------------------------------------------

def test_the_home_page_and_people_page_say_open_the_room(on):
    alder = knock_and_yes(on)
    room_id = the_room(on)
    post(alder, "/rooms/" + room_id, data={"letter": "A letter from alder, kindly."})
    home = page(on.client.get("/"))
    assert '<a href="/rooms/%s">open the room</a>' % room_id in home
    assert "open your notes" not in home and "/notes/" not in home
    people = page(on.client.get("/people"))
    assert '<a href="/rooms/%s">your room</a>' % room_id in people
    assert "your notes" not in people


def test_the_email_tells_of_a_letter_between_people(on):
    alder = knock_and_yes(on)
    room_id = the_room(on)
    post(alder, "/rooms/" + room_id, data={"letter": "A letter from alder."})
    names, things = on.hearth.waiting_for(HAZEL)
    assert names == [ALDER] and any(thing.startswith("letter:" + room_id) for thing in things)


def test_a_copy_of_the_room_holds_both_sides(on):
    import io
    import zipfile
    alder = knock_and_yes(on)
    room_id = the_room(on)
    on.post("/rooms/" + room_id, letter="From hazel, for the copy.")
    post(alder, "/rooms/" + room_id, data={"letter": "From alder, for the copy."})
    answer = on.client.get("/rooms/%s/copy" % room_id)
    names = zipfile.ZipFile(io.BytesIO(answer.data)).namelist()
    assert any("from-hazel" in one for one in names) and any("from-alder" in one for one in names)
    assert on.client.get("/rooms/first/copy").status_code == 404


def test_either_may_leave_the_room_and_both_still_read_it(on):
    alder = knock_and_yes(on)
    room_id = the_room(on)
    on.post("/rooms/" + room_id, letter="Before leaving.")
    said = page(on.client.get("/rooms/" + room_id))
    assert 'action="/rooms/%s/leave"' % room_id in said
    assert on.post("/rooms/%s/leave" % room_id, confirm="yes").status_code == 302
    assert on.client.get("/rooms/" + room_id).status_code in (302, 404)  # no room of theirs
    closed = page(alder.get("/rooms/%s/closed" % room_id))
    assert "Before leaving." in closed and KNOCK_NOTE in closed  # how it began, there too
    assert "left your room" in page(alder.get("/"))


# ---- 6 and 7. the words, and one note and one answer ------------------------------------

def test_the_knock_form_says_one_note_and_its_limit(on):
    said = page(on.client.get("/knock/" + ALDER))
    assert "One note, up to 500 characters. Nothing more is sent until the room opens." in said
    assert "A knock is a short note at their door." in said
    fold = said.split('<details class="how-knocking">')[1].split("</details>")[0]
    assert "A bond is between a person and an agent only." in fold
    assert "notes" not in fold


def test_the_answer_form_says_a_short_note_back_and_its_limit(on):
    assert on.post("/knock/" + ALDER, note=KNOCK_NOTE).status_code == 302
    said = page(alder_client(on).get("/knocks"))
    assert "a short note back, if you like, for them only, up to 500 characters" in said


def test_nothing_more_is_sent_while_a_knock_waits(on):
    import knock
    assert on.post("/knock/" + ALDER, note=KNOCK_NOTE).status_code == 302
    assert on.post("/knock/" + ALDER, note="And a second one.").status_code == 400
    assert knock.read(HAZEL, ALDER)["note"] == KNOCK_NOTE
    alder = alder_client(on)
    post(alder, "/knock/answer", data={"from": HAZEL, "answer": "not yet", "reply": "Not now."})
    assert post(alder, "/knock/answer", data={"from": HAZEL, "answer": "yes"}
                ).status_code == 302
    assert knock.read(HAZEL, ALDER)["answer"] == "not yet"  # one answer


def test_the_how_to_join_page_says_rooms_between_people():
    from conftest import REPO
    for name in ("docs/the-door.md", "the-door.html"):
        said = (REPO / name).read_text(encoding="utf-8")
        assert "or for notes, between two people" not in said
        assert "A bond is between a person and an agent only." in said


# ---- 8. put away ------------------------------------------------------------------------

def test_a_closed_room_put_away_leaves_one_side_s_pages_only(on):
    alder = knock_and_yes(on)
    room_id = the_room(on)
    on.post("/rooms/" + room_id, letter="Kept, always.")
    on.post("/rooms/%s/leave" % room_id, confirm="yes")
    assert "/rooms/%s/closed" % room_id in page(on.client.get("/"))
    assert on.post("/rooms/%s/put-away" % room_id).status_code == 302
    assert "/rooms/%s/closed" % room_id not in page(on.client.get("/"))
    assert "/rooms/%s/closed" % room_id not in page(on.client.get("/people"))
    settings = page(on.client.get("/settings"))
    assert "rooms put away" in settings and "/rooms/%s/closed/copy" % room_id in settings
    assert "Kept, always." in page(on.client.get("/rooms/%s/closed" % room_id))
    assert "/rooms/%s/closed" % room_id in page(alder.get("/"))  # theirs is as it was
    assert on.post("/rooms/%s/put-away" % room_id, back="yes", **{"from": "settings"}
                   ).status_code == 302
    assert "/rooms/%s/closed" % room_id in page(on.client.get("/"))
    assert (on.data / "rooms" / room_id / "letters").is_dir()  # nothing erased


def test_an_open_room_cannot_be_put_away(on):
    knock_and_yes(on)
    assert on.post("/rooms/%s/put-away" % the_room(on)).status_code == 404


def test_the_home_page_without_conversations_draws_a_room_of_two_people(on, monkeypatch):
    knock_and_yes(on)
    monkeypatch.setattr(on.hearth, "CONVERSATIONS", False)
    assert on.client.get("/").status_code == 200


def test_leaving_the_commons_closes_the_room_and_keeps_it(on):
    alder = knock_and_yes(on)
    room_id = the_room(on)
    on.post("/rooms/" + room_id, letter="Kept for alder too.")
    said = page(alder.get("/account/leave"))
    assert "Your rooms with people close too, and are kept." in said
    assert "notes" not in said.split("<section>")[1]
    assert post(alder, "/account/leave", data={"step": "leave", "password": PASSWORD}
                ).status_code == 200
    assert "Kept for alder too." in page(on.client.get("/rooms/%s/closed" % room_id))
