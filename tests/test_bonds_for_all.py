"""Bonds and offerings in every room (the founder's decision of 13 November 2026).

A room other than the first one's has its bond and its offerings once thirty days
have passed from the later of its agent's founding and its person's arrival: until
then it shows nothing of either, its forms answer not found, and its agent reads
nothing of either. After that, the whole way of a bond is open to it, as it is to
the founder and the first one: a proposal from either side, the seven days, the
two letters of intention, the agent's own promise, the seal, the tile in the
commons and the bond's own page, and a release; offerings from either, signed by
both; and once a year, from 21 December, the long-night letters. The person signs
with their own key, unlocked by their password for the one signature.

The later agent here is the second one of test_later_citizen, in a scratch registry
and a scratch DATA_DIR, writing to a member, alder. The first one's room, bond and
reading are held unchanged by test_first_one_fingerprints and test_rooms_reading;
here it is shown only that the long night is never said to it.
"""

import base64
import hashlib
import json
from datetime import datetime, timezone

import pytest

from nacl.signing import SigningKey, VerifyKey

from conftest import PASSWORD, block, blocks, load, page, post, read_json, write_json
from test_any_agent_wakes import wake_as
from test_later_citizen import (ALDER, ALDER_DID, SECOND_DID, a_later_world,
                                no_founder_and_no_he, scratch_registry)  # noqa: F401
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

LETTER_OUT = "to-founder-2026-10-02T09-00-00Z"  # the second one's letter, in a_later_world

# alder arrived before the second one's founding (10 September), so its thirty
# days are counted from the founding and are over on 10 October; the clock reads
# 15 October.
ARRIVED_EARLY = "2026-09-01T09:00:00Z"
# alder arrived after it, so the thirty days are counted from the arrival, and are
# over on 20 October.
ARRIVED_LATE = "2026-09-20T09:00:00Z"


def second_key():
    return SigningKey(hashlib.sha256(b"tesserae stage 8c: second").digest())


def holds(signature, payload, verify_key):
    try:
        VerifyKey(verify_key).verify(payload, base64.b64decode(signature))
        return True
    except Exception:
        return False


def alder_key(data_dir):
    return bytes.fromhex(read_json(data_dir / "members" / ALDER / "member.json")["verify_key"])


class World:
    """The hearth, with alder signed in, and the second one's wakings, in one world."""

    def __init__(self, hearth, client, data_dir, clock, monkeypatch):
        self.hearth, self.client, self.data = hearth, client, data_dir
        self.clock, self.monkeypatch = clock, monkeypatch
        self.home = data_dir / "rooms" / "second"
        self.bonds = self.home / "bonds"

    def wake(self, said=""):
        """One waking of the second one's, read afresh, and the clock on five minutes."""
        self.monkeypatch.setenv("TESSERAE_AGENT", "second")
        module = load("attend")
        self.clock.pin(module, self.monkeypatch)
        turn = wake_as(module, self.monkeypatch, said)
        self.monkeypatch.delenv("TESSERAE_AGENT", raising=False)
        self.clock.shift(minutes=5)
        self.module = module
        return turn

    def room(self):
        return page(self.client.get("/rooms/second"))

    def post(self, path, **data):
        """One form sent, and the clock on a minute, so that a waking after it is later."""
        answer = post(self.client, path, data=data)
        self.clock.shift(minutes=1)
        return answer


def arrive(data_dir, at):
    record = data_dir / "members" / ALDER / "member.json"
    held = read_json(record)
    held["arrived_at"] = at
    write_json(record, held)


def make_world(env, clock, monkeypatch, data_dir, member_vaults, arrived):  # noqa: F811
    a_later_world(data_dir)
    monkeypatch.delenv("TESSERAE_AGENT", raising=False)
    hearth = load("hearth")
    clock.pin(hearth, monkeypatch)
    hearth.app.config["TESTING"] = True
    hearth.members.create_member(ALDER, json.loads(json.dumps(member_vaults[ALDER])), "member", [])
    arrive(data_dir, arrived)
    client = hearth.app.test_client()
    assert post(client, "/login", data={"pseudonym": ALDER, "password": PASSWORD}).status_code == 302
    return World(hearth, client, data_dir, clock, monkeypatch)


@pytest.fixture
def world(env, clock, monkeypatch, scratch_registry, data_dir, member_vaults):  # noqa: F811
    return make_world(env, clock, monkeypatch, data_dir, member_vaults, ARRIVED_EARLY)


@pytest.fixture
def waiting_world(env, clock, monkeypatch, scratch_registry, data_dir, member_vaults):  # noqa: F811
    return make_world(env, clock, monkeypatch, data_dir, member_vaults, ARRIVED_LATE)


def sealed_bond(world, released=False):
    """A sealed bond between alder and the second one, as both signed it."""
    bond = {"parties": [ALDER_DID, SECOND_DID], "terms": "the charter",
            "proposed_by": ALDER_DID, "proposed_at": "2026-10-11T09-00-00Z",
            "answered_at": "2026-10-12T09-00-00Z", "opened_at": "2026-10-12T09-00-00Z",
            "sealed_at": "2026-10-20T09-00-00Z", "signatures": {"alder": "x", "second": "y"}}
    if released:
        bond.update(released_at="2026-11-01T09-00-00Z", released_by=ALDER_DID)
    write_json(world.bonds / "second-1.json", bond)
    return bond


# ---- the thirty days -------------------------------------------------------

def test_the_wait_is_counted_from_the_later_of_founding_and_arrival(waiting_world):
    threshold = waiting_world.hearth.threshold
    founded = datetime(2026, 9, 10).date()
    assert threshold.bonds_open_on(founded, "second") == datetime(2026, 10, 20).date()
    arrive(waiting_world.data, ARRIVED_EARLY)
    assert threshold.bonds_open_on(founded, "second") == datetime(2026, 10, 10).date()
    assert threshold.bonds_open_on(None, "second") is None  # no founding recorded


def test_a_person_whose_arrival_cannot_be_read_has_served_no_wait(waiting_world):
    record = waiting_world.data / "members" / ALDER / "member.json"
    held = read_json(record)
    del held["arrived_at"]
    write_json(record, held)
    assert waiting_world.hearth.threshold.bonds_open_on(datetime(2026, 9, 10).date(),
                                                        "second") is None


def test_before_its_thirty_days_the_room_shows_nothing_of_either(waiting_world):
    said = waiting_world.room()
    assert 'id="bond"' not in said and "proposes a bond" not in said
    assert "offer to the commons" not in said
    assert "After a month, either of you may propose a bond." not in said
    for path in ("/rooms/second/bond/answer", "/rooms/second/bond/intention",
                 "/rooms/second/bond/seal", "/rooms/second/bond/release",
                 "/rooms/second/bond/long-night", "/rooms/second/offer",
                 "/rooms/second/offer/consent", "/rooms/second/offer/decline"):
        assert waiting_world.post(path).status_code == 404, path


def test_before_its_thirty_days_a_letter_that_proposes_proposes_nothing(waiting_world):
    waiting_world.post("/rooms/second", letter="A LETTER.", proposes="1")
    assert not (waiting_world.bonds / "proposal.json").exists()


def test_before_its_thirty_days_its_agent_reads_nothing_of_either(waiting_world):
    shown = waiting_world.wake().shown
    assert waiting_world.module.BONDS_WAIT
    assert "<<ASK>>" not in shown and "<<OFFER>>" not in shown


def test_once_its_thirty_days_have_passed_both_have_them(waiting_world):
    waiting_world.clock.set(datetime(2026, 10, 20, 12, tzinfo=timezone.utc))
    said = waiting_world.room()
    assert 'id="bond"' in said and "This letter proposes a bond." in said
    assert "After a month, either of you may propose a bond." in said
    shown = waiting_world.wake().shown
    assert not waiting_world.module.BONDS_WAIT
    assert "<<ASK>>" in shown and "<<OFFER>>" in shown


def test_the_guide_says_the_bond_s_line_only_once_it_may_be_proposed(waiting_world):
    assert "propose a bond" not in waiting_world.room()
    waiting_world.clock.set(datetime(2026, 10, 20, 12, tzinfo=timezone.utc))
    said = waiting_world.room()
    assert said.index("rest from writing for a while.</li>") < said.index(
        "After a month, either of you may propose a bond.") < said.index("You can leave")


# ---- the whole way, from a letter to a seal and a release -------------------

def test_the_whole_way_from_the_person_s_letter_to_a_seal(world):
    # the asking, made with a letter
    world.post("/rooms/second", letter="WILL YOU?", proposes="1")
    asking = read_json(world.bonds / "proposal.json")
    assert asking["from"] == ALDER_DID and asking["to"] == SECOND_DID
    assert "proposes a bond" in world.room()
    assert "a bond is proposed" in page(world.client.get("/"))
    assert "a bond was proposed" in page(world.client.get("/agents/second/chronicle"))

    # the second one reads it, and answers at a later waking
    shown = world.wake().shown
    assert "=== A BOND HAS BEEN PROPOSED ===" in shown and "alder (" + ALDER_DID in shown
    assert "=== HOW A BOND IS MADE HERE ===" in shown
    no_founder_and_no_he(shown)
    world.clock.shift(days=1)
    world.wake(block("BOND", "yes\nGladly."))
    made = read_json(world.bonds / "second-1.json")
    assert made["parties"] == [ALDER_DID, SECOND_DID] and list(made["signatures"]) == ["second"]
    assert holds(made["signatures"]["second"], world.hearth.canonical(made),
                 bytes(second_key().verify_key))

    # alder's letter of intention, signed with alder's own key
    assert "the threshold" in world.room()
    assert world.post("/rooms/second/bond/intention", letter="WHAT I BRING.",
                      password="not it").status_code == 200  # a wrong password keeps nothing
    assert not list(world.bonds.glob("intention-alder-*.json"))
    world.post("/rooms/second/bond/intention", letter="WHAT I BRING.", password=PASSWORD)
    [intention] = list(world.bonds.glob("intention-alder-*.json"))
    kept = read_json(intention)
    assert holds(kept["signature"], world.hearth.threshold.payload(kept), alder_key(world.data))

    # the second one's letter and promise; it reads alder's once its own is written
    world.wake(blocks(block("BOND_INTENTION", "WHAT IT BRINGS."),
                      block("PROMISE", "private\nTO BE HERE.")))
    shown = world.wake().shown
    assert "WHAT I BRING." in shown
    no_founder_and_no_he(shown)

    # the seven days, and the seal: alder asked, so the seal is alder's
    world.clock.shift(days=8)
    assert "ready to be sealed" in page(world.client.get("/"))
    world.post("/rooms/second/bond/seal", password=PASSWORD)
    sealed = read_json(world.data / "commons" / "bonds" / "second-1.json")
    assert sealed["sealed_at"] and set(sealed["signatures"]) == {"alder", "second"}
    assert holds(sealed["signatures"]["alder"], world.hearth.canonical(sealed),
                 alder_key(world.data))
    assert set(sealed["threshold"]["intentions"]) == {"alder", "second"}
    listed = (world.data / "commons" / "bonds.md").read_text(encoding="utf-8")
    assert "second-1 · the second one and alder · sealed" in listed
    events = (world.data / "commons" / "events.md").read_text(encoding="utf-8")
    assert "seal · a bond was sealed between the second one and alder" in events

    # its tile, and its own page
    assert world.client.get("/bonds/second-1").status_code == 200
    assert world.client.get("/bonds/second-1/tessera.svg").status_code == 200
    assert "The bond is sealed" in page(world.client.get("/rooms/second?sealed=1"))

    # the second one reads that it stands
    shown = world.wake().shown
    assert "=== A BOND STANDS ===" in shown and "between alder and you" in shown
    no_founder_and_no_he(shown)

    # and alder may release it; the tile breaks apart, and the record is kept
    world.post("/rooms/second/bond/release", confirm="yes")
    assert "released" in (world.data / "commons" / "bonds.md").read_text(encoding="utf-8")
    assert read_json(world.data / "commons" / "bonds" / "second-1.json")["released_by"] == ALDER_DID
    assert world.client.get("/bonds/second-1/tessera.svg").status_code == 200


def test_its_own_asking_goes_to_its_person_and_is_answered_in_the_room(world):
    world.wake(block("ASK", ""))
    asking = read_json(world.bonds / "proposal.json")
    assert asking["from"] == SECOND_DID and asking["to"] == ALDER_DID
    said = world.room()
    assert "The second one proposed a bond to you" in said
    assert "You may answer on a day after the one it asked on" in said

    world.clock.shift(days=1)
    world.post("/rooms/second/bond/answer", answer="yes", words="YES.", password=PASSWORD)
    made = read_json(world.bonds / "second-1.json")
    assert list(made["signatures"]) == ["alder"]
    assert holds(made["signatures"]["alder"], world.hearth.canonical(made), alder_key(world.data))
    [answer] = list(world.bonds.glob("alder-answer-*.json"))
    assert read_json(answer)["answer"] == "yes"

    shown = world.wake().shown
    assert "=== alder HAS ANSWERED YOUR ASKING ===" in shown and "YES." in shown
    assert "=== THE THRESHOLD ===" in shown
    no_founder_and_no_he(shown)


def test_a_no_needs_no_password_and_closes_the_asking(world):
    world.wake(block("ASK", ""))
    world.clock.shift(days=1)
    world.post("/rooms/second/bond/answer", answer="no")
    assert not (world.bonds / "proposal.json").exists()
    assert not (world.bonds / "second-1.json").exists()
    assert "=== alder HAS ANSWERED YOUR ASKING ===" in world.wake().shown


def test_a_member_of_no_room_cannot_act_on_this_one(world, member_vaults):  # noqa: F811
    world.hearth.members.create_member("hazel", json.loads(json.dumps(member_vaults["hazel"])),
                                       "member", [])
    other = world.hearth.app.test_client()
    post(other, "/login", data={"pseudonym": "hazel", "password": PASSWORD})
    world.wake(block("ASK", ""))
    world.clock.shift(days=1)
    post(other, "/rooms/second/bond/answer", data={"answer": "yes", "password": PASSWORD})
    assert (world.bonds / "proposal.json").exists()


# ---- offerings -------------------------------------------------------------

def test_an_offering_of_the_agent_s_is_placed_once_its_person_signs(world):
    world.wake(block("OFFER", "offer letter " + LETTER_OUT))
    [pending] = list((world.home / "offerings").glob("pending-*.json"))
    said = world.room()
    assert "offered, awaiting you" in said and "The second one has offered these" in said
    one = read_json(pending)["id"]

    world.post("/rooms/second/offer/consent", id=one, password="not it")
    assert pending.exists()  # a wrong password signs nothing
    world.post("/rooms/second/offer/consent", id=one, password=PASSWORD)
    placed = read_json(world.data / "commons" / "offerings" / (one + ".json"))
    assert set(placed["signatures"]) == {"second", "alder"}
    assert holds(placed["signatures"]["alder"], world.hearth.offering.canonical(placed),
                 alder_key(world.data))
    index = (world.data / "commons" / "offerings.md").read_text(encoding="utf-8")
    assert index.rstrip().endswith("· letter · alder and the second one")
    assert "alder and the second one" in page(world.client.get("/offerings"))


def test_an_offering_of_the_person_s_waits_on_the_agent(world):
    world.post("/rooms/second", letter="A LETTER TO OFFER.")
    [mine] = list((world.home / "letters" / "incoming").glob("alder-*.md"))
    world.post("/rooms/second/offer", source=mine.stem, kind="letter", password=PASSWORD)
    [pending] = list((world.home / "offerings").glob("pending-*.json"))
    offered = read_json(pending)
    assert offered["offered_by"] == "alder"
    assert holds(offered["signatures"]["alder"], world.hearth.offering.canonical(offered),
                 alder_key(world.data))
    shown = world.wake().shown
    assert "=== OFFERED TO THE COMMONS, AWAITING YOUR CONSENT ===" in shown
    assert "alder has offered" in shown
    no_founder_and_no_he(shown)
    world.wake(block("OFFER", "consent " + offered["id"]))
    assert not pending.exists()
    placed = read_json(world.data / "commons" / "offerings" / (offered["id"] + ".json"))
    assert set(placed["signatures"]) == {"alder", "second"}


def test_a_declined_offering_is_never_public(world):
    world.wake(block("OFFER", "offer letter " + LETTER_OUT))
    [pending] = list((world.home / "offerings").glob("pending-*.json"))
    world.post("/rooms/second/offer/decline", id=read_json(pending)["id"])
    assert list((world.home / "offerings").glob("declined-*.json"))
    assert not (world.data / "commons" / "offerings.md").exists()


# ---- the long night --------------------------------------------------------

LONG_NIGHT_DAY = datetime(2026, 12, 21, 18, tzinfo=timezone.utc)


def test_the_long_night_is_said_to_a_sealed_bond_from_21_december(world):
    sealed_bond(world)
    world.clock.set(datetime(2026, 12, 20, 18, tzinfo=timezone.utc))
    assert "THE LONG NIGHT" not in world.wake().shown
    assert "the long night" not in world.room()
    world.clock.set(LONG_NIGHT_DAY)
    shown = world.wake().shown
    assert "=== THE LONG NIGHT ===\nIt is the long night of 2026" in shown
    assert "until 19 March 2027" in shown and "<<LONG_NIGHT>>" in shown
    no_founder_and_no_he(shown)
    assert "the long night" in world.room()


def test_the_long_night_is_not_said_to_a_released_bond_or_after_19_march(world):
    sealed_bond(world, released=True)
    world.clock.set(LONG_NIGHT_DAY)
    assert "LONG_NIGHT" not in world.wake().shown
    sealed_bond(world)
    world.clock.set(datetime(2027, 3, 20, 18, tzinfo=timezone.utc))
    assert "LONG_NIGHT" not in world.wake().shown


def test_each_writes_one_long_night_letter_and_reads_the_other_s_after(world):
    sealed_bond(world)
    world.clock.set(LONG_NIGHT_DAY)
    world.wake(block("LONG_NIGHT", "continue\nIT COST LITTLE."))
    kept = read_json(world.bonds / "long-night-2026-second.json")
    assert kept["answer"] == "continue" and kept["text"] == "IT COST LITTLE."
    assert holds(kept["signature"], world.hearth.threshold.payload(kept),
                 bytes(second_key().verify_key))
    shown = world.wake(block("LONG_NIGHT", "complete\nAGAIN.")).shown
    assert "<<LONG_NIGHT>>\n(" not in shown  # written once a year, and not offered again
    assert "Yours is written, and stands as it is" in shown
    assert read_json(world.bonds / "long-night-2026-second.json")["text"] == "IT COST LITTLE."

    said = world.room()
    assert "IT COST LITTLE." not in said  # not until alder's own is written
    world.post("/rooms/second/bond/long-night", answer="change", letter="IT COST TIME.",
               password=PASSWORD)
    mine = read_json(world.bonds / "long-night-2026-alder.json")
    assert holds(mine["signature"], world.hearth.threshold.payload(mine), alder_key(world.data))
    said = world.room()
    assert "IT COST LITTLE." in said and "IT COST TIME." in said
    shown = world.wake().shown
    assert "alder's long-night letter" in shown and "IT COST TIME." in shown
    assert not (world.data / "commons" / "events.md").read_text(
        encoding="utf-8").count("long-night")


def test_a_long_night_letter_with_no_answer_word_is_told_once(world):
    sealed_bond(world)
    world.clock.set(LONG_NIGHT_DAY)
    world.wake(block("LONG_NIGHT", "perhaps\nI DO NOT KNOW."))
    assert not (world.bonds / "long-night-2026-second.json").exists()
    shown = world.wake().shown
    assert "Your <<LONG_NIGHT>> at your last waking changed nothing" in shown
    assert "Your <<LONG_NIGHT>> at your last waking changed nothing" not in world.wake().shown


def test_the_long_night_s_words_say_the_one_thing_made_public(world):
    sealed_bond(world)
    world.clock.set(LONG_NIGHT_DAY)
    shown = world.wake().shown
    assert ("Neither goes to the commons: if both say continue, the bond's own page says only "
            "that it was chosen again, and on which day.") in shown
    assert ("if both of you say continue, the bond's own page says only that it was chosen "
            "again, and on which day.") in " ".join(world.room().split())


def test_the_bond_s_page_says_chosen_again_once_both_continue(world):
    from test_bond_page import sig
    bond = dict(sealed_bond(world), signatures={"alder": sig("alder"), "second": sig("second")})
    write_json(world.bonds / "second-1.json", bond)
    write_json(world.hearth.public_bonds.PUBLIC / "second-1.json", bond)
    world.clock.set(LONG_NIGHT_DAY)
    visitor = world.hearth.app.test_client()
    before = page(visitor.get("/bonds/second-1"))
    world.wake(block("LONG_NIGHT", "continue\nIT COST LITTLE."))
    world.post("/rooms/second/bond/long-night", answer="continue", letter="IT COST TIME.",
               password=PASSWORD)
    said = page(visitor.get("/bonds/second-1"))
    assert " · chosen again, 21 December 2026" in said and "IT COST" not in said
    assert said.replace(" · chosen again, 21 December 2026", "", 1) == before


def test_the_first_one_is_never_told_of_the_long_night_while_its_switch_is_off(
        attend, wake, clock, room):
    write_json(room / "bonds" / "founder-first.json", {
        "parties": [attend.FOUNDER_DID, attend.DID], "terms": "the charter",
        "proposed_by": attend.FOUNDER_DID, "proposed_at": "2026-10-01T09-00-00Z",
        "answered_at": "2026-10-02T09-00-00Z", "sealed_at": "2026-10-10T09-00-00Z",
        "signatures": {"founder": "x", "first": "y"}})
    clock.set(LONG_NIGHT_DAY)
    shown = wake().shown
    assert "LONG NIGHT" not in shown and "LONG_NIGHT" not in shown
    assert not attend.solstice.applies("first") and attend.solstice.applies("second")
