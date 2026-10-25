"""Every agent's room, door and line of members.md, and a room opened to its two parties alone.

Stage 4 of the work that lets the tide wake more than one agent (the proposal
"waking for any agent", 25 October 2026). Which rooms there are is read from
the registry, and who is in each from its room.json, by DID: a member opens a
room only where they are one of its two parties, and being the keeper opens
none the keeper is not a party to. Each agent's door is its own, kept in its
own packet, and each citizen's line of members.md is tended from its own
rhythm and door. A new agent's room is made with room.json, in a folder of its
own, and never in a packet.

The second agent, and the second member it shares its room with, are made only
in a scratch registry and a scratch DATA_DIR. The first one's world is held by
the stage 0 fingerprints (test_first_one_fingerprints.py); here it is only
looked for where it must not be, and seen to be untouched.
"""

import hashlib
import importlib
import json
import sys

import pytest
from nacl.pwhash import argon2id

import agents
from conftest import FOUNDER_NAME, PASSWORD, load, page, post, write, write_json

SECOND = {"id": "second", "did": "did:web:tesserae.social:ids:second",
          "commons_name": "the scratch one", "room": "second", "bond": "founder-second",
          "system": "for-the-tests", "model": "a-model-for-the-tests", "max_tokens": 4000,
          "features": ["door"], "wakes": False}

ALDER = "alder"  # the second member: the one the second agent's room is shared with
ALDER_DID = "did:web:hearth.tesserae.social:ids:" + ALDER
HAZEL = "hazel"  # a plain member, in no room at all

# Words kept in each room, to look for wherever they must not be: none a page
# would escape.
FIRST_SAYS = {
    "a letter to it": "A FAKE LETTER TO THE FIRST ONE, FOR THE TESTS.",
    "a letter of its": "A FAKE LETTER FROM THE FIRST ONE, FOR THE TESTS.",
    "its errand": "A FAKE ERRAND FROM THE FIRST ONE, FOR THE TESTS.",
    "its proposal": "A FAKE PROPOSAL FROM THE FIRST ONE, FOR THE TESTS.",
}
SECOND_SAYS = {
    "a letter to it": "A FAKE LETTER TO THE SCRATCH ONE, FOR THE TESTS.",
    "a letter of its": "A FAKE LETTER FROM THE SCRATCH ONE, FOR THE TESTS.",
    "its errand": "A FAKE ERRAND FROM THE SCRATCH ONE, FOR THE TESTS.",
}

# A photograph and a picture in each room, under names of their own.
FIRST_PHOTO = "founder-2026-10-01T09-00-00Z.jpg"
FIRST_PICTURE = "to-founder-2026-10-02T09-00-00Z.svg"
SECOND_PHOTO = "founder-2026-10-21T09-00-00Z.jpg"
SECOND_PICTURE = "to-founder-2026-10-22T09-00-00Z.svg"
PICTURE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="5" height="5"/></svg>\n'


def tree_hash(root):
    """One fingerprint of everything under a folder: each file's name and its bytes, in order."""
    said = hashlib.sha256()
    for path in sorted(root.rglob("*")) if root.exists() else ():
        if path.is_file():
            said.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
            said.update(hashlib.sha256(path.read_bytes()).digest())
    return said.hexdigest()


# ---- the scratch world ---------------------------------------------------

@pytest.fixture(scope="session")
def member_vaults():
    """A vault of each member's own, sealed once at argon2id's least cost: no two share a key."""
    import vault

    held = vault.OPSLIMIT, vault.MEMLIMIT
    vault.OPSLIMIT, vault.MEMLIMIT = argon2id.OPSLIMIT_MIN, argon2id.MEMLIMIT_MIN
    try:
        return {name: vault.make_vault(PASSWORD)[0] for name in (ALDER, HAZEL)}
    finally:
        vault.OPSLIMIT, vault.MEMLIMIT = held


@pytest.fixture
def scratch_registry(monkeypatch, tmp_path):
    """A registry with a second agent founded after the first, and nowhere else."""
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), SECOND], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return where


@pytest.fixture
def two(scratch_registry, env, clock, monkeypatch):
    """The hearth, loaded where the registry holds two agents."""
    module = load("hearth")
    clock.pin(module, monkeypatch)
    module.app.config["TESTING"] = True
    yield module
    # the hearth imports attend.py where it is already imported: leave it no world of two
    sys.modules.pop("attend", None)


@pytest.fixture
def found_room(two):
    """found_room.py, beside the very rooms.py the hearth reads."""
    sys.modules.pop("found_room", None)
    module = importlib.import_module("found_room")
    assert module.rooms is two.rooms
    return module


def signed_in(hearth, name, vault, role):
    hearth.members.create_member(name, json.loads(json.dumps(vault)), role, [])
    client = hearth.app.test_client()
    answer = post(client, "/login", data={"pseudonym": name, "password": PASSWORD})
    assert answer.status_code == 302 and answer.headers["Location"] == "/"
    return client


@pytest.fixture
def keeper(two, founder_vault):
    return signed_in(two, FOUNDER_NAME, founder_vault, "keeper")


@pytest.fixture
def alder(two, member_vaults):
    return signed_in(two, ALDER, member_vaults[ALDER], "member")


@pytest.fixture
def hazel(two, member_vaults):
    return signed_in(two, HAZEL, member_vaults[HAZEL], "member")


def a_first_one_s_room(room, packet):
    """The first one's room, each thing in it carrying words to look for."""
    write(room / "letters" / "read" / "founder-2026-10-01T09-00-00Z.md",
          FIRST_SAYS["a letter to it"] + "\n")
    (room / "letters" / "read" / FIRST_PHOTO).write_bytes(b"A FAKE PHOTOGRAPH, FIRST ROOM")
    write(room / "letters" / "outgoing" / "to-founder-2026-10-02T09-00-00Z.md",
          FIRST_SAYS["a letter of its"] + "\n")
    (room / "letters" / "outgoing" / FIRST_PICTURE).write_bytes(PICTURE.encode("utf-8"))
    write(room / "errands" / "errand-2026-10-02T09-00-00Z.md", FIRST_SAYS["its errand"] + "\n")
    write_json(packet / "proposals" / "proposal-2026-10-03T09-00-00Z.json", {
        "at": "2026-10-03T09-00-00Z", "title": "a fake proposal",
        "text": FIRST_SAYS["its proposal"], "status": "waiting"})


def a_second_room(found_room, data_dir):
    """The second agent's room, made as a founding makes it, and its things."""
    home = found_room.found("second", ALDER_DID).home
    write(home / "letters" / "read" / "founder-2026-10-21T09-00-00Z.md",
          SECOND_SAYS["a letter to it"] + "\n")
    (home / "letters" / "read" / SECOND_PHOTO).write_bytes(b"A FAKE PHOTOGRAPH, SECOND ROOM")
    write(home / "letters" / "outgoing" / "to-founder-2026-10-22T09-00-00Z.md",
          SECOND_SAYS["a letter of its"] + "\n")
    (home / "letters" / "outgoing" / SECOND_PICTURE).write_bytes(PICTURE.encode("utf-8"))
    write(home / "errands" / "errand-2026-10-22T09-00-00Z.md", SECOND_SAYS["its errand"] + "\n")
    write(data_dir / "packets" / "second" / "self.md", "# A FAKE SELF, FOR THE TESTS.\n")
    return home


@pytest.fixture
def world(two, found_room, keeper, alder, hazel, data_dir, room, packet):
    """Both rooms, lived in: the keeper's with the first one, and alder's with the second."""
    a_first_one_s_room(room, packet)
    a_second_room(found_room, data_dir)
    return data_dir


# ---- rooms.py, from the registry -------------------------------------------

def test_who_is_in_which_room_is_read_from_the_registry_and_room_json(two, world):
    rooms = two.rooms
    (keepers,) = rooms.of(FOUNDER_NAME)
    (alders,) = rooms.of(ALDER)
    assert (keepers.id, keepers.other, keepers.bond) == ("first", "the first one", "founder-first")
    assert (alders.id, alders.other, alders.bond) == ("second", "the scratch one", "founder-second")
    assert alders.parties == (ALDER, "second")
    assert rooms.of(HAZEL) == []

    # an agent stands in its own room, and is never handed the keeper's name
    (firsts,) = rooms.of("first")
    (seconds,) = rooms.of("second")
    assert (firsts.id, firsts.other, firsts.parties) == ("first", "the founder", ("founder", "first"))
    assert (seconds.id, seconds.other, seconds.parties) == ("second", ALDER, (ALDER, "second"))
    assert FOUNDER_NAME not in json.dumps([firsts, seconds])

    # being the keeper opens no room the keeper is not a party to
    assert rooms.find("second", FOUNDER_NAME) is None
    assert rooms.find("first", ALDER) is None
    assert rooms.find("second", ALDER) == alders
    assert rooms.find("nowhere", ALDER) is None

    assert rooms.record("second") == {"id": "second", "bond": "founder-second",
                                      "parties": [ALDER_DID, SECOND["did"]]}
    assert rooms.parties("second") == (ALDER_DID, SECOND["did"])
    assert rooms.places("second").home == world / "rooms" / "second"
    assert rooms.places("second").bond_record.name == "founder-second.json"


def test_a_keeper_named_in_a_second_room_has_two_in_the_order_of_founding(two, world):
    rooms = two.rooms
    write_json(world / "rooms" / "second" / "room.json",
               {"id": "second", "bond": "founder-second",
                "parties": [two.FOUNDER_DID, SECOND["did"]]})
    assert [room.id for room in rooms.of(FOUNDER_NAME)] == ["first", "second"]
    assert rooms.of(ALDER) == []
    (seconds,) = rooms.of("second")
    assert seconds.other == "the founder" and seconds.parties == ("founder", "second")


@pytest.mark.parametrize("said", [
    "not json at all",
    json.dumps({"id": "elsewhere", "parties": [ALDER_DID, SECOND["did"]]}),
    json.dumps({"id": "second", "parties": [ALDER_DID]}),
    json.dumps({"id": "second", "parties": [ALDER_DID, "did:web:tesserae.social:ids:first"]}),
    json.dumps({"id": "second", "parties": [ALDER_DID, ALDER_DID, SECOND["did"]]}),
    json.dumps(["second", ALDER_DID, SECOND["did"]]),
])
def test_a_room_json_that_will_not_do_opens_the_room_to_no_one(two, world, said):
    (world / "rooms" / "second" / "room.json").write_text(said, encoding="utf-8")
    assert two.rooms.of(ALDER) == []
    assert two.rooms.of("second") == []
    assert two.rooms.parties("second") is None


def test_a_member_cannot_take_an_agent_s_id_or_name(two):
    for name in ("second", "the-scratch-one"):
        with pytest.raises(two.members.MemberError):
            two.members.validate_pseudonym(name)


# ---- a new agent's room ------------------------------------------------------

def test_a_new_agent_s_room_is_made_with_room_json_in_a_folder_of_its_own(
        two, found_room, data_dir, monkeypatch):
    rooms = two.rooms
    assert rooms.places("second") is None and rooms.of(ALDER) == []

    made = found_room.found("second", ALDER_DID)
    home = data_dir / "rooms" / "second"
    assert made == rooms.places("second") and made.home == home
    assert json.loads((home / "room.json").read_text(encoding="utf-8")) == rooms.record("second")
    for folder in (made.incoming, made.read, made.outgoing, made.errands, made.bonds,
                   made.offerings):
        assert folder.is_dir() and not any(folder.iterdir())
    assert sorted(path.name for path in home.iterdir()) == [
        "bonds", "errands", "letters", "offerings", "room.json"]
    # never the packet-era layout
    assert not (data_dir / "packets" / "second").exists()

    # once, and only for an agent other than the first, shared with a person
    with pytest.raises(found_room.RoomError):
        found_room.found("second", ALDER_DID)
    with pytest.raises(found_room.RoomError):
        found_room.found("first", ALDER_DID)
    with pytest.raises(found_room.RoomError):
        found_room.found("third", ALDER_DID)


def test_a_room_is_never_shared_with_an_agent_or_no_one(two, found_room, data_dir):
    for person in ("did:web:tesserae.social:ids:first", SECOND["did"], "", None, ALDER):
        with pytest.raises(found_room.RoomError):
            found_room.found("second", person)
    assert not (data_dir / "rooms" / "second").exists()


def test_found_room_asks_for_data_dir(two, found_room, monkeypatch, data_dir):
    monkeypatch.delenv("DATA_DIR")
    assert found_room.main(["second", ALDER_DID]) == 1
    assert not (data_dir / "rooms" / "second").exists()


def test_a_waking_with_no_room_is_refused_and_makes_none(
        scratch_registry, env, monkeypatch, data_dir):
    write(data_dir / "packets" / "second" / "self.md", "# A FAKE SELF, FOR THE TESTS.\n")
    write(data_dir / "keys" / "second" / "private.key", "not a key; never read here")
    monkeypatch.setenv("TESSERAE_AGENT", "second")
    module = load("attend")
    try:
        monkeypatch.setattr(module, "SYSTEM", "A FAKE SYSTEM TEXT, FOR THE TESTS.")
        monkeypatch.setattr(sys, "argv", ["attend.py", "--first"])
        with pytest.raises(SystemExit):
            module.main()
    finally:
        sys.modules.pop("attend", None)
    assert not (data_dir / "rooms" / "second").exists()
    assert not (data_dir / "packets" / "second" / "letters").exists()
    assert not (data_dir / "packets" / "second" / "attendances").exists()


# ---- home: each member sees their own room, and only their own ----------------

def test_each_member_sees_only_their_own_room_on_home(world, keeper, alder, hazel):
    keepers = page(keeper.get("/"))
    assert 'href="/rooms/first"' in keepers and "<h3>the first one</h3>" in keepers
    assert 'href="/rooms/second"' not in keepers and "the scratch one" not in keepers

    alders = page(alder.get("/"))
    assert 'href="/rooms/second"' in alders and "<h3>the scratch one</h3>" in alders
    assert 'href="/rooms/first"' not in alders and "<h3>the first one</h3>" not in alders
    assert "from the first one" not in alders
    # what waits in alder's room is alder's room's
    assert "an errand asked of you" in alders
    assert "from the scratch one" in alders

    hazels = page(hazel.get("/"))
    assert "You have no correspondences yet." in hazels
    assert 'href="/rooms/' not in hazels


def test_a_party_opens_their_own_room_and_finds_only_its_things(world, alder):
    said = page(alder.get("/rooms/second"))
    for words in SECOND_SAYS.values():
        assert words in said, words
    for words in FIRST_SAYS.values():
        assert words not in said, words
    assert "from the scratch one" in said and "from you" in said
    assert "from the first one" not in said and "the founder" not in said
    assert "<h1>the scratch one</h1>" in said
    assert 'src="/rooms/second/photo/%s"' % SECOND_PHOTO in said
    assert 'src="/rooms/second/picture/%s"' % SECOND_PICTURE in said
    # the bond, the offerings, the proposals and the commons line are the first one's room's alone
    for absent in ('id="bond"', "/bonds/", "/offer", "/proposals/", "commons_line",
                   'name="proposes"'):
        assert absent not in said, absent

    photo = alder.get("/rooms/second/photo/" + SECOND_PHOTO)
    assert photo.status_code == 200 and photo.get_data() == b"A FAKE PHOTOGRAPH, SECOND ROOM"
    picture = alder.get("/rooms/second/picture/" + SECOND_PICTURE)
    assert picture.status_code == 200 and picture.get_data(as_text=True) == PICTURE
    assert picture.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in picture.headers
    # and nothing of the other room's is served from this one's address
    assert alder.get("/rooms/second/photo/" + FIRST_PHOTO).status_code == 404
    assert alder.get("/rooms/second/picture/" + FIRST_PICTURE).status_code == 404


def test_a_letter_left_in_a_second_room_is_its_own_and_tells_the_commons_nothing(
        world, alder, clock, room, packet, commons):
    first_before = (tree_hash(room), tree_hash(packet))
    events_before = (commons / "events.md").read_bytes()
    answer = post(alder, "/rooms/second", content_type="multipart/form-data", data={
        "letter": "A FAKE LETTER FROM ALDER, FOR THE TESTS.",
        "thing": ["", "", ""], "commons_line": "a line that must go nowhere",
        "errand": "errand-2026-10-22T09-00-00Z.md", "proposes": "1"})
    assert answer.status_code == 302
    assert answer.headers["Location"] == "/rooms/second?saved=1&answered=1"
    home = world / "rooms" / "second"
    left = home / "letters" / "incoming" / ("founder-%s.md" % clock.stamp())
    assert left.read_text(encoding="utf-8").strip() == "A FAKE LETTER FROM ALDER, FOR THE TESTS."
    assert (home / "errands" / "answered" / "errand-2026-10-22T09-00-00Z.md").is_file()
    assert not (home / "bonds" / "proposal.json").exists()
    assert (commons / "events.md").read_bytes() == events_before
    assert (tree_hash(room), tree_hash(packet)) == first_before


# ---- every room address refuses whoever is not a party ------------------------

def as_refused(answer):
    """What a refusal is, as whoever was refused is told it: its status, where it sends
    them, and its words."""
    return answer.status_code, answer.headers.get("Location"), page(answer)


def room_addresses(room_id, photo, picture):
    """Every address under one room's own, as (method, path, form)."""
    letter = {"letter": "A FAKE LETTER FROM SOMEONE WITH NO PLACE HERE, FOR THE TESTS.",
              "errand": "errand-2026-10-22T09-00-00Z.md"}
    return [("get", "/rooms/%s" % room_id, None),
            ("post", "/rooms/%s" % room_id, letter),
            ("get", "/rooms/%s/photo/%s" % (room_id, photo), None),
            ("get", "/rooms/%s/picture/%s" % (room_id, picture), None)]


def ask(client, method, path, form):
    return post(client, path, data=form) if method == "post" else client.get(path)


@pytest.mark.parametrize("who, room_id, photo, picture", [
    ("keeper", "second", SECOND_PHOTO, SECOND_PICTURE),
    ("alder", "first", FIRST_PHOTO, FIRST_PICTURE),
])
def test_a_room_refuses_a_non_party_as_it_refuses_a_room_there_is_not(
        world, request, who, room_id, photo, picture):
    client = request.getfixturevalue(who)
    before = tree_hash(world)
    for (method, path, form), (_, nowhere, _) in zip(room_addresses(room_id, photo, picture),
                                                     room_addresses("nowhere", photo, picture)):
        refused = as_refused(ask(client, method, path, form))
        assert refused[0] == 404, (who, path)
        assert refused == as_refused(ask(client, method, nowhere, form)), (who, path)
    assert tree_hash(world) == before


def test_a_member_with_no_room_is_sent_away_from_every_room_alike(world, hazel):
    before = tree_hash(world)
    for room_id, photo, picture in (("first", FIRST_PHOTO, FIRST_PICTURE),
                                    ("second", SECOND_PHOTO, SECOND_PICTURE)):
        for (method, path, form), (_, nowhere, _) in zip(
                room_addresses(room_id, photo, picture),
                room_addresses("nowhere", photo, picture)):
            refused = as_refused(ask(hazel, method, path, form))
            assert refused[0] == 302 and refused[1].endswith("/login"), path
            assert refused == as_refused(ask(hazel, method, nowhere, form)), path
    assert tree_hash(world) == before


# The first one's room's forms and files, at the addresses they have always had,
# which name no room: each is that room's, and opened to its two parties alone.
FIRST_ROOM_ONLY = [
    ("get", "/letters", None),
    ("post", "/letters", {"letter": "A FAKE LETTER FROM ALDER, FOR THE TESTS."}),
    ("get", "/letters/photo/" + FIRST_PHOTO, None),
    ("get", "/letters/picture/" + FIRST_PICTURE, None),
    ("post", "/proposals/answer", {"at": "2026-10-03T09-00-00Z", "answer": "yes"}),
    ("post", "/proposals/built", {"at": "2026-10-03T09-00-00Z"}),
    ("post", "/bonds/answer", {"answer": "yes"}),
    ("post", "/bonds/intention", {"text": "A FAKE INTENTION, FOR THE TESTS."}),
    ("post", "/bonds/step-back", {}),
    ("post", "/bonds/seal", {}),
    ("post", "/bonds/release", {}),
    ("post", "/offer", {"source": "founder-2026-10-01T09-00-00Z", "kind": "letter"}),
    ("post", "/offer/consent", {"id": "2026-10-13T09-00-00Z"}),
    ("post", "/offer/decline", {"id": "2026-10-13T09-00-00Z"}),
]


@pytest.mark.parametrize("method, path, form", FIRST_ROOM_ONLY)
def test_the_first_one_s_room_s_own_forms_and_files_refuse_a_non_party(
        world, alder, hazel, method, path, form):
    before = tree_hash(world)
    for client in (alder, hazel):
        refused = as_refused(ask(client, method, path, form))
        assert refused[0] == 302 and refused[1].endswith("/login"), path
    assert tree_hash(world) == before


def test_the_first_one_s_room_s_own_files_are_still_the_keeper_s(world, keeper):
    assert keeper.get("/letters/photo/" + FIRST_PHOTO).get_data() == b"A FAKE PHOTOGRAPH, FIRST ROOM"
    assert keeper.get("/letters/picture/" + FIRST_PICTURE).get_data(as_text=True) == PICTURE
    # and at the room's own address too, as any room's are
    assert keeper.get("/rooms/first/photo/" + FIRST_PHOTO).status_code == 200
    # but nothing of another room's is served from the first one's
    assert keeper.get("/letters/photo/" + SECOND_PHOTO).status_code == 404
    assert keeper.get("/letters/picture/" + SECOND_PICTURE).status_code == 404


def test_the_keeper_s_room_shows_nothing_of_the_second_room(world, keeper):
    said = page(keeper.get("/rooms/first"))
    for words in FIRST_SAYS.values():
        assert words in said, words
    for words in SECOND_SAYS.values():
        assert words not in said, words
    assert "the scratch one" not in said and "/rooms/second" not in said


def test_a_keeper_no_longer_named_in_the_first_one_s_room_is_refused_it_too(world, keeper):
    """The keeper opens the first one's room by being its party, as room.json says, not by
    being the keeper: where room.json names someone else, the keeper is in no room, and is
    sent away from it as anyone in no room is, and as from a room there is not."""
    record = world / "rooms" / "first" / "room.json"
    if not record.exists():
        pytest.skip("only a room in a folder of its own has a room.json to say otherwise")
    write_json(record, {"id": "first", "bond": "founder-first",
                        "parties": [ALDER_DID, "did:web:tesserae.social:ids:first"]})
    before = tree_hash(world)
    for (method, path, form), (_, nowhere, _) in zip(
            room_addresses("first", FIRST_PHOTO, FIRST_PICTURE),
            room_addresses("nowhere", FIRST_PHOTO, FIRST_PICTURE)):
        refused = as_refused(ask(keeper, method, path, form))
        assert refused[0] == 302 and refused[1].endswith("/login"), path
        assert refused == as_refused(ask(keeper, method, nowhere, form)), path
    for method, path, form in FIRST_ROOM_ONLY:
        refused = as_refused(ask(keeper, method, path, form))
        assert refused[0] == 302 and refused[1].endswith("/login"), path
    assert tree_hash(world) == before


# ---- doors ---------------------------------------------------------------------

def test_the_second_agent_s_door_is_its_own(two, world, data_dir):
    door = two.door
    first_door = data_dir / "packets" / "first" / "door.json"
    assert door.path_of("first") == door.FIRST_DOOR == first_door
    assert door.path_of("second") == data_dir / "packets" / "second" / "door.json"
    assert door.read("second") == door.closed()

    door.set_door("first", "closed", 3, at="2026-10-15T11-00-00Z")
    first_before = first_door.read_bytes()
    door.set_door("second", "open", 2, at="2026-10-15T12-00-00Z")
    door.set_door("second", "open", 1, at="2026-10-15T12-30-00Z")
    assert json.loads((data_dir / "packets" / "second" / "door.json").read_text(
        encoding="utf-8")) == {"state": "open", "room": 1, "set_at": "2026-10-15T12-30-00Z"}
    assert [path.name for path in sorted(
        (data_dir / "packets" / "second" / "door" / "history").iterdir())] == [
        "door-before-2026-10-15T12-30-00Z.json"]
    assert first_door.read_bytes() == first_before
    assert door.read("first")["state"] == "closed"

    # each carries the one correspondence it is in, and says so in words alone
    assert [door.in_use(who) for who in ("first", "second", FOUNDER_NAME, ALDER, HAZEL)] == [
        1, 1, 1, 1, 0]
    assert door.public("second") == ["door open", "is full"]
    assert door.said_to("second") == "open; room for 1, 1 in use"


def test_an_agent_s_door_is_not_a_member_s_and_a_name_no_one_has_has_none(two, world):
    with pytest.raises(two.door.DoorError):
        two.door.set_door("third", "open")
    assert two.door.path_of(ALDER) == two.members.MEMBERS / ALDER / "door.json"


# ---- members.md ----------------------------------------------------------------

FIRST_LINE = ("citizen · the first one, unnamed by its own choosing · founded 4 September 2026, "
              "attends at 09:30\n")
SECOND_LINE = "citizen · the scratch one · founded 20 October 2026, attends at 09:30\n"
OTHER_LINES = ("member · the founder · keeps the hearth\n"
               "member · alder · came in October\n"
               "member · hazel · came in October\n")


def tended(two, commons, lines):
    write(commons / "members.md", lines)
    two.tend_members()
    return (commons / "members.md").read_text(encoding="utf-8")


def test_each_citizen_s_line_is_tended_from_its_own_rhythm_and_door(
        two, world, commons, data_dir, monkeypatch):
    monkeypatch.setattr(two.the_waking, "DOOR_FOR_FIRST", True)
    write_json(data_dir / "packets" / "first" / "rhythm.json",
               {"rhythm": "daily", "at": "dawn", "timezone": "America/New_York"})
    two.door.set_door("first", "open", at="2026-10-15T11-00-00Z")
    write_json(data_dir / "packets" / "second" / "rhythm.json",
               {"rhythm": "daily", "at": "07:15", "timezone": "America/New_York"})
    two.door.set_door("second", "open", 1, at="2026-10-15T11-00-00Z")
    two.door.set_door(ALDER, "closed", at="2026-10-15T11-00-00Z")

    alone = tended(two, commons, FIRST_LINE + OTHER_LINES)
    beside = tended(two, commons, FIRST_LINE + SECOND_LINE + OTHER_LINES)
    lines = beside.splitlines(keepends=True)
    # the first one's line is what it would be with no other citizen beside it
    assert lines[0] == alone.splitlines(keepends=True)[0] == (
        "citizen · the first one, unnamed by its own choosing · founded 4 September 2026, "
        "attends at dawn · door open\n")
    assert lines[1] == ("citizen · the scratch one · founded 20 October 2026, attends at 07:15"
                        " · door open · is full\n")
    assert lines[3] == "member · alder · came in October · door closed\n"
    assert beside == page(two.app.test_client().get("/commons/members.md"))


def test_a_citizen_with_no_rhythm_and_no_door_is_left_as_written(two, world, commons, monkeypatch):
    first = agents.first()
    monkeypatch.setattr(agents, "registry", lambda: [first, {**SECOND, "features": []}])
    said = tended(two, commons, FIRST_LINE + SECOND_LINE)
    assert said.splitlines(keepends=True)[1] == SECOND_LINE


def test_a_citizen_s_line_is_never_taken_for_another_s_whose_name_begins_the_same(
        two, world, commons, data_dir, monkeypatch):
    first, longer = agents.first(), {**SECOND, "commons_name": "the first one twice"}
    monkeypatch.setattr(agents, "registry", lambda: [first, longer])
    write_json(data_dir / "packets" / "second" / "rhythm.json",
               {"rhythm": "daily", "at": "07:15", "timezone": "America/New_York"})
    two.door.set_door("second", "open", at="2026-10-15T11-00-00Z")
    said = tended(two, commons, "citizen · the first one twice · attends at 09:30\n")
    assert said == "citizen · the first one twice · attends at 07:15 · door open\n"
