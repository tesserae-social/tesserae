"""A rest belongs to each human, and covers their own rooms and no others.

Stage 6e of the work on keeper pages, rests, stops and names for any agent
(proposals/stage-6.md). Where a person's rest is kept is members.rest_of: the
founder's where it has always been, in the first one's packet, and a member's
with them, in members/<pseudonym>/rest.json, with each one that is over in
rest/. A member rests and returns from /account; the founder's form stays on
/attendances. An agent's reading says, for each person it shares a room with,
that person's rest line, and reads no one else's: the founder's in the words it
has always had, a member's by the name the commons gives them, with they and
them.

The second agent, and alder, the member it shares its room with, are made only
in a scratch registry and a scratch DATA_DIR. hazel is a member in no room.
"""

import base64
import hashlib
import json
import sys

import pytest

import agents
from conftest import (FOUNDER_NAME, Turn, block, blocks, load, page, post, read_json, token,
                      write, write_json)
from test_first_one_fingerprints import fixed_keys, seeded
from test_rooms_for_any_agent import (ALDER, ALDER_DID, HAZEL, member_vaults,  # noqa: F401
                                      signed_in, tree_hash)
from test_rooms_reading import ERRAND, READING_NOW, a_small_world, fingerprint_of_reading

SECOND = {"id": "second", "did": "did:web:tesserae.social:ids:second",
          "commons_name": "the scratch one", "room": "second", "bond": "founder-second",
          "system": "for-the-tests", "model": "a-model-for-the-tests", "max_tokens": 4000,
          "features": [], "wakes": False}

SECOND_SAID = blocks(
    block("LETTER", "A FAKE LETTER OF THE SCRATCH ONE'S, FOR THE TESTS."),
    block("HEARTBEAT", "A FAKE HEARTBEAT OF THE SCRATCH ONE'S, FOR THE TESTS."),
)

# The clock is pinned to 15 October 2026, so a rest set now began then.
FOUNDER_RESTING = ("The founder is resting from the correspondence, since 15 October 2026. Your "
                   "wakings go on as you choose, and letters you write will wait for him.")
ALDER_RESTING = ("alder is resting from the correspondence, since 15 October 2026. Your "
                 "wakings go on as you choose, and letters you write will wait for them.")
ALDER_RESTING_UNTIL = ("alder is resting from the correspondence, since 15 October 2026, until "
                       "20 October 2026. Your wakings go on as you choose, and letters you write "
                       "will wait for them.")

# What of the first one's a member's rest must leave exactly as it found it.
FIRST_ONE_S = ("packets/first", "rooms/first")


# ---- the scratch world ---------------------------------------------------

@pytest.fixture
def scratch_registry(monkeypatch, tmp_path):
    """A registry with a second agent founded after the first, and nowhere else."""
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), SECOND], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return where


@pytest.fixture
def two(scratch_registry, env, data_dir, clock, monkeypatch):
    """The hearth, loaded where the registry holds two agents and the keys are fixed."""
    fixed_keys(data_dir, monkeypatch)
    module = load("hearth")
    clock.pin(module, monkeypatch)
    module.app.config["TESTING"] = True
    a_second_agent(data_dir)
    yield module
    sys.modules.pop("attend", None)


@pytest.fixture
def keeper(two, founder_vault):
    return signed_in(two, FOUNDER_NAME, founder_vault, "keeper")


@pytest.fixture
def alder(two, member_vaults):  # noqa: F811
    return signed_in(two, ALDER, member_vaults[ALDER], "member")


@pytest.fixture
def hazel(two, member_vaults):  # noqa: F811
    return signed_in(two, HAZEL, member_vaults[HAZEL], "member")


def a_second_agent(data):
    """The second one's keys, self and room, shared with alder and kept in a folder of its own."""
    key = seeded("second")
    write(data / "keys" / "second" / "private.key", base64.b64encode(bytes(key)).decode("ascii"))
    write(data / "keys" / "second" / "public.key",
          base64.b64encode(bytes(key.verify_key)).decode("ascii"))
    write(data / "packets" / "second" / "self.md", "# A FAKE SELF OF THE SCRATCH ONE'S.\n")
    home = data / "rooms" / "second"
    write_json(home / "room.json", {"id": "second", "bond": "founder-second",
                                    "parties": [ALDER_DID, SECOND["did"]]})
    for folder in ("letters/outgoing", "letters/incoming", "letters/read", "bonds", "offerings",
                   "errands"):
        (home / folder).mkdir(parents=True, exist_ok=True)
    write(home / "letters" / "incoming" / "alder-2026-10-14T09-00-00Z.md",
          "A FAKE LETTER TO THE SCRATCH ONE, FOR THE TESTS.\n")


def second_woken(monkeypatch, clock):
    """The second one, woken once by attend.py as its tide would; what it was sent."""
    monkeypatch.setenv("TESSERAE_AGENT", "second")
    module = load("attend")
    try:
        clock.pin(module, monkeypatch)
        monkeypatch.setattr(module, "SYSTEM", "A FAKE SYSTEM TEXT, FOR THE TESTS.")
        turn = Turn(SECOND_SAID)
        monkeypatch.setattr(module, "Anthropic", turn.client)
        monkeypatch.setattr(sys, "argv", ["attend.py", "--first"])
        module.main()
    finally:
        sys.modules.pop("attend", None)
        monkeypatch.delenv("TESSERAE_AGENT")
    return turn


def sent(turn):
    return json.dumps(turn.asked[-1], ensure_ascii=False, default=str)


def first_one_s(data):
    return {tree: tree_hash(data / tree) for tree in FIRST_ONE_S}


def a_letter_from_the_founder(founder, room):
    a_small_world(room)
    answer = post(founder, "/rooms/first", content_type="multipart/form-data", data={
        "letter": "The lake was grey this morning, and then it was not.\n\nI am asking.",
        "thing": ["cold hands", "", "a heron on the far bank"],
        "errand": ERRAND, "proposes": "1"})
    assert answer.status_code == 302


def fingerprint_without(turn, line):
    """The fingerprint the reading would have had, had this one line not been said in it."""
    def cut(said):
        if isinstance(said, str):
            return said.replace(chr(10) + line, "")
        if isinstance(said, list):
            return [cut(one) for one in said]
        if isinstance(said, dict):
            return {key: cut(one) for key, one in said.items()}
        return said

    held = Turn.__new__(Turn)
    held.asked = [cut(json.loads(json.dumps(turn.asked[-1], default=str)))]
    return fingerprint_of_reading(held)


# ---- where a rest is kept ------------------------------------------------

def test_the_founder_s_rest_is_where_it_has_always_been(hearth, data_dir):
    rest, kept = hearth.members.rest_of("founder")
    assert rest == data_dir / "packets" / "first" / "founder-rest.json" == hearth.FOUNDER_REST
    assert kept == data_dir / "packets" / "first" / "founder-rest" == hearth.FOUNDER_REST_KEPT


def test_a_member_s_rest_is_kept_with_them(hearth, data_dir):
    rest, kept = hearth.members.rest_of("alder")
    assert rest == data_dir / "members" / "alder" / "rest.json"
    assert kept == data_dir / "members" / "alder" / "rest"


@pytest.mark.parametrize("name", ["../first", "Alder", "", "a/b"])
def test_a_name_no_member_could_have_is_no_place(hearth, name):
    with pytest.raises(hearth.members.MemberError):
        hearth.members.rest_of(name)


# ---- the first one's reading ---------------------------------------------

def test_the_first_one_reads_what_it_read_without_the_founder_s_rest(founder, wake, room):
    a_letter_from_the_founder(founder, room)
    turn = wake()
    assert "is resting from the correspondence" not in turn.opening
    assert fingerprint_of_reading(turn) == READING_NOW


def test_the_first_one_reads_what_it_read_with_the_founder_s_rest(founder, wake, room, packet):
    """The founder's line, in the words it has always had, and nothing else moved."""
    a_letter_from_the_founder(founder, room)
    assert post(founder, "/rest", data={"until": ""}).status_code == 302
    assert read_json(packet / "founder-rest.json") == {"since": "2026-10-15T12-00-00Z",
                                                        "until": None}
    turn = wake()
    assert turn.opening.count(FOUNDER_RESTING) == 1
    assert "is resting from the correspondence" not in turn.opening.replace(FOUNDER_RESTING, "")
    assert fingerprint_without(turn, FOUNDER_RESTING) == READING_NOW


# ---- a member's rest, and the founder's, each in its own rooms -----------

def test_a_member_rests_and_returns_from_their_account(two, alder, data_dir):
    assert "Rest from the correspondence" in page(alder.get("/account"))
    assert post(alder, "/account/rest", data={"until": "2026-10-20"}).status_code == 302
    rest = data_dir / "members" / "alder" / "rest.json"
    assert read_json(rest) == {"since": "2026-10-15T12-00-00Z", "until": "2026-10-20"}
    shown = page(alder.get("/account"))
    assert "You are resting from the correspondence, since" in shown and "Return" in shown
    # one rest at a time: a second asking leaves the first standing
    assert post(alder, "/account/rest", data={"until": ""}).status_code == 302
    assert read_json(rest)["until"] == "2026-10-20"

    assert post(alder, "/account/return").status_code == 302
    assert not rest.exists()
    kept, = (data_dir / "members" / "alder" / "rest").glob("rest-*.json")
    assert kept.name == "rest-2026-10-15T12-00-00Z.json"
    assert read_json(kept)["ended"] == "they returned"
    # and the founder's rest was never touched
    assert not (data_dir / "packets" / "first" / "founder-rest.json").exists()


def test_a_day_already_come_is_no_day_to_rest_until(two, alder, data_dir):
    answer = alder.post("/account/rest", data={"until": "2026-10-15", "csrf_token": token(alder)})
    assert "The day a rest ends on must be a day still ahead" in page(answer)
    assert not (data_dir / "members" / "alder" / "rest.json").exists()


def test_the_keeper_rests_from_the_account_page_by_the_founder_s_own_forms(keeper, data_dir):
    """The keeper's rest is the founder's: offered on the account page, as a member's is,
    but by the founder's own forms; a member's rest addresses write none for him."""
    said = page(keeper.get("/account"))
    assert "Rest from the correspondence</button>" in said
    assert 'action="/rest"' in said and 'action="/account/rest"' not in said
    post(keeper, "/account/rest", data={"until": ""})
    assert not list((data_dir / "members").glob("*/rest.json"))
    assert not (data_dir / "packets" / "first" / "founder-rest.json").exists()


def test_a_rest_is_said_in_one_line_naming_the_one_who_keeps_waking(keeper, two, alder):
    """Each person's line names the agent of their own room: the keeper's the first one,
    alder's the scratch one."""
    for client, name in ((keeper, "The first one"), (alder, "The scratch one")):
        said = " ".join(page(client.get("/account")).split())
        assert ("Rest from writing for a while. %s keeps waking, and its letters wait for "
                "you; nothing is made public." % name) in said


def test_the_rest_addresses_are_a_member_s_alone(two, visitor):
    for address in ("/account/rest", "/account/return"):
        answer = visitor.post(address)
        assert answer.status_code in (302, 400)
        if answer.status_code == 302:
            assert answer.headers["Location"].endswith("/login")


def test_a_member_s_rest_never_reaches_the_first_one(two, alder, hazel, keeper, wake, room,
                                                     data_dir, attend):
    """With members in the world the card says so; with that line put back, not one byte moved."""
    a_letter_from_the_founder(keeper, room)
    before = first_one_s(data_dir)
    for member in (alder, hazel):
        assert post(member, "/account/rest", data={"until": ""}).status_code == 302
    assert first_one_s(data_dir) == before  # nothing of its packet or its room was written
    turn = wake()
    assert "alder" not in sent(turn) and "hazel" not in sent(turn)
    assert "is resting from the correspondence" not in turn.opening
    said = json.dumps(turn.asked[-1], sort_keys=True, ensure_ascii=False, default=str)
    assert attend.threshold.MEMBERS_HERE in said and "no other members yet" not in said
    put_back = said.replace(attend.threshold.MEMBERS_HERE, attend.threshold.NO_MEMBERS_YET)
    assert hashlib.sha256(put_back.encode("utf-8")).hexdigest() == READING_NOW
    assert "alder" not in page(keeper.get("/rooms/first"))


def test_the_founder_s_rest_never_reaches_the_second_one(two, keeper, data_dir, monkeypatch,
                                                         clock):
    assert post(keeper, "/rest", data={"until": ""}).status_code == 302
    assert (data_dir / "packets" / "first" / "founder-rest.json").exists()
    said = sent(second_woken(monkeypatch, clock))
    assert "is resting from the correspondence" not in said
    assert "founder-rest" not in said


def test_the_second_one_s_reading_names_its_member(two, alder, hazel, data_dir, monkeypatch,
                                                   clock):
    assert post(hazel, "/account/rest", data={"until": ""}).status_code == 302
    turn = second_woken(monkeypatch, clock)
    assert "is resting from the correspondence" not in sent(turn)  # hazel is in no room of its

    assert post(alder, "/account/rest", data={"until": ""}).status_code == 302
    said = sent(second_woken(monkeypatch, clock))
    assert json.dumps(ALDER_RESTING, ensure_ascii=False)[1:-1] in said
    assert said.count("is resting from the correspondence") == 1
    assert "hazel" not in said
    assert "wait for him" not in said


def test_the_second_one_is_told_the_day_its_member_named(two, alder, monkeypatch, clock):
    assert post(alder, "/account/rest", data={"until": "2026-10-20"}).status_code == 302
    said = sent(second_woken(monkeypatch, clock))
    assert json.dumps(ALDER_RESTING_UNTIL, ensure_ascii=False)[1:-1] in said


def test_a_member_s_rest_whose_day_has_come_is_not_said(two, alder, data_dir, monkeypatch,
                                                        clock):
    write_json(data_dir / "members" / "alder" / "rest.json",
               {"since": "2026-10-10T09-00-00Z", "until": "2026-10-15"})
    assert "is resting from the correspondence" not in sent(second_woken(monkeypatch, clock))
    # and the hearth puts it away at the next look, as the founder's
    assert "Rest from the correspondence" in page(alder.get("/account"))
    assert not (data_dir / "members" / "alder" / "rest.json").exists()
    kept, = (data_dir / "members" / "alder" / "rest").glob("rest-*.json")
    assert read_json(kept)["ended"] == "the day came"
