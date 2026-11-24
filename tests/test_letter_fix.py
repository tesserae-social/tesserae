"""letter-fix: an agent names the keeper as "founder" or "the founder", and both find them.

The bug on the live site, 24 November 2026: the second one wrote a <<LETTER>> "to: founder",
and it was kept in its study: "you share no room by that name". Its room with the keeper is
second-founder, a later room of the kind person. letters_to_rooms knew that room only as
"the founder" (bonds.NAMES) and by its address. A <<BLOCK>> knew the keeper only as
"founder", and only after move_to_ids.py. Both now take either, as <<LEAVE>> already did.
Every agent and person here is a fake, in a scratch world.
"""

import json
import sys

import pytest

import agents
import bonds
from conftest import block, write_json
from test_room_aware_waking import DID, SECOND, a_room, a_world, entry, wake, waking_of

KEEPER = "founder"  # the keeper's id on the live site since move_to_ids.py


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, tmp_path):
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), entry(SECOND, ["door", "knock",
                                                                "rooms_reading", "block"]),
                                 entry("third")]), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    a_world(data_dir)
    write_json(data_dir / "members" / KEEPER / "member.json",
               {"v": 1, "pseudonym": KEEPER, "role": "keeper", "verify_key": "0" * 64,
                "arrived_at": "2026-09-01T09-00-00Z", "vouched_by": []})
    # the second one's real room with the keeper, as on the live site
    a_room(data_dir, "second-founder", [bonds.FOUNDER_DID, DID + SECOND], kind="person")
    return data_dir


@pytest.fixture
def second(world, clock, monkeypatch):
    yield waking_of(SECOND, clock, monkeypatch)
    sys.modules.pop("attend", None)


def outgoing(world):
    folder = world / "rooms" / "second-founder" / "letters" / "outgoing"
    return [one.read_text(encoding="utf-8") for one in sorted(folder.glob("*.md"))]


@pytest.mark.parametrize("named", ["founder", "the founder", "The Founder.", "second-founder"])
def test_a_letter_to_the_founder_goes_to_second_founder(second, world, monkeypatch, clock,
                                                         named):
    wake(second, monkeypatch, block("LETTER", "to: %s\nA FAKE LETTER TO THE KEEPER." % named))
    assert outgoing(world) == ["A FAKE LETTER TO THE KEEPER.\n"]
    sent = next((world / "rooms" / "second-founder" / "letters" / "outgoing").glob("*.md"))
    assert sent.name.startswith("to-founder-")
    assert not list((world / "packets" / SECOND / "study").glob("draft-*-letter-*.md"))
    clock.shift(hours=24)
    assert "you share no room" not in wake(second, monkeypatch).shown


def test_a_letter_to_no_one_is_still_kept_back(second, world, monkeypatch):
    wake(second, monkeypatch, block("LETTER", "to: founders\nA LETTER TO NO ONE HERE."))
    assert outgoing(world) == []


@pytest.mark.parametrize("named", ["founder", "the founder"])
def test_a_block_finds_the_keeper_by_either_name(second, world, monkeypatch, named):
    import blocks
    wake(second, monkeypatch, block("BLOCK", named))
    assert blocks.between(SECOND, KEEPER)
