"""The long night for the founder and the first one, behind its switch, and the one
public trace of a long night on a bond's own page.

The founder's answers of 12 November 2026: the founder and the first one have
long-night letters too, behind a switch, "long_night" in the first one's features,
off by default and switched on before 21 December once the first one has been
told; and only the fact is ever public, on the bond's page, as "chosen again,
<day>", once both have chosen to continue. The letters stay private.

The first one's reading with the switch off and on is held in test_rooms_reading
(READING_SEALED_IN_WINTER, READING_LONG_NIGHT). Here: the founder's room, his form,
the letters each way, and the bond's page.
"""

from datetime import datetime, timezone

import pytest

from conftest import block, long_night_switched_on, page, post, read_json, verify, write_json
from test_bond_page import a_bond

LONG_NIGHT_DAY = datetime(2026, 12, 21, 18, tzinfo=timezone.utc)


@pytest.fixture
def sealed(hearth, attend, room):
    """The founder and the first one's bond, sealed, in the room and in public."""
    bond = a_bond(hearth.threshold)
    write_json(room / "bonds" / "founder-first.json", bond)
    write_json(hearth.public_bonds.PUBLIC / "founder-first.json", bond)
    return bond


@pytest.fixture
def switched(hearth, attend, monkeypatch, tmp_path):
    where = tmp_path / "agents.json"
    long_night_switched_on(attend, monkeypatch, where)
    long_night_switched_on(hearth, monkeypatch, where)


def founder_room(founder):
    return page(founder.get("/rooms/first"))


def test_switched_off_the_founder_s_room_shows_nothing_and_the_form_is_not_found(
        founder, sealed, clock, wake, room):
    clock.set(LONG_NIGHT_DAY)
    assert "long night" not in founder_room(founder)
    answer = post(founder, "/bonds/long-night", data={"answer": "continue", "letter": "IT COST."})
    assert answer.status_code == 404
    assert not list((room / "bonds").glob("long-night-*"))
    shown = wake(block("LONG_NIGHT", "continue\nIT COST LITTLE.")).shown
    assert "LONG NIGHT" not in shown and "LONG_NIGHT" not in shown
    assert not list((room / "bonds").glob("long-night-*"))


def test_switched_on_it_is_said_from_21_december_and_not_before(
        founder, sealed, switched, clock, wake):
    clock.set(datetime(2026, 12, 20, 18, tzinfo=timezone.utc))
    assert "long night" not in founder_room(founder)
    assert "THE LONG NIGHT" not in wake().shown
    clock.set(LONG_NIGHT_DAY)
    said = founder_room(founder)
    assert "<h2>the long night</h2>" in said and "21 December" not in said.split("long night")[0]
    assert "The first one's long-night letter: not yet written." in said
    shown = wake().shown
    assert "=== THE LONG NIGHT ===\nIt is the long night of 2026" in shown
    assert "You will not see the founder's letter until you have written yours" in shown
    assert "only the founder reads it" in shown


def test_switched_on_each_writes_one_and_reads_the_other_s_after(
        founder, sealed, switched, clock, wake, room, keys, hearth):
    clock.set(LONG_NIGHT_DAY)
    wake(block("LONG_NIGHT", "continue\nIT COST LITTLE."))
    its = read_json(room / "bonds" / "long-night-2026-first.json")
    assert verify(keys.did("first"), hearth.threshold.payload(its), its["signature"])
    assert "IT COST LITTLE." not in founder_room(founder)  # not until his own is written

    answer = post(founder, "/bonds/long-night", data={"answer": "", "letter": "IT COST TIME."})
    assert "says continue, change or complete" in page(answer)
    assert not (room / "bonds" / "long-night-2026-founder.json").exists()
    assert post(founder, "/bonds/long-night",
                data={"answer": "continue", "letter": "IT COST TIME."}).status_code == 302
    mine = read_json(room / "bonds" / "long-night-2026-founder.json")
    assert verify(keys.did("founder"), hearth.threshold.payload(mine), mine["signature"])
    said = founder_room(founder)
    assert "IT COST LITTLE." in said and "IT COST TIME." in said
    # written once, and not rewritten
    post(founder, "/bonds/long-night", data={"answer": "complete", "letter": "AGAIN."})
    assert read_json(room / "bonds" / "long-night-2026-founder.json")["text"] == "IT COST TIME."

    shown = wake().shown
    assert "the founder's long-night letter" in shown and "IT COST TIME." in shown
    assert "long-night" not in (room.parent.parent / "commons" / "events.md").read_text(
        encoding="utf-8")


def test_without_his_key_nothing_is_signed(founder, sealed, switched, clock, room, monkeypatch):
    clock.set(LONG_NIGHT_DAY)
    monkeypatch.delenv("FOUNDER_KEY")
    assert "Set FOUNDER_KEY to write one." in founder_room(founder)
    answer = post(founder, "/bonds/long-night", data={"answer": "continue", "letter": "IT COST."})
    assert "key is not on this hearth. Check FOUNDER_KEY." in page(answer)
    assert not (room / "bonds" / "long-night-2026-founder.json").exists()


# ---- the bond's page --------------------------------------------------------

def test_the_bond_s_page_says_chosen_again_once_both_say_continue(
        founder, sealed, switched, clock, wake, visitor):
    clock.set(LONG_NIGHT_DAY)
    before = page(visitor.get("/bonds/founder-first"))
    assert "chosen again" not in before
    wake(block("LONG_NIGHT", "continue\nIT COST LITTLE."))
    assert "chosen again" not in page(visitor.get("/bonds/founder-first"))  # one alone is not it
    clock.set(datetime(2026, 12, 23, 18, tzinfo=timezone.utc))
    post(founder, "/bonds/long-night", data={"answer": "continue", "letter": "IT COST TIME."})
    said = page(visitor.get("/bonds/founder-first"))
    assert "sealed on 8 October 2026 · chosen again, 23 December 2026" in said
    # the fact, and nothing else of it
    for private in ("IT COST", "long night", "long-night", "continue"):
        assert private not in said
    assert said.replace(" · chosen again, 23 December 2026", "", 1) == before
    public = page(visitor.get("/bonds/founder-first.json"))
    assert "long" not in public and "IT COST" not in public


def test_a_change_or_a_complete_leaves_the_bond_s_page_as_it_was(
        founder, sealed, switched, clock, wake, visitor):
    clock.set(LONG_NIGHT_DAY)
    before = page(visitor.get("/bonds/founder-first"))
    wake(block("LONG_NIGHT", "change\nIT COST LITTLE."))
    post(founder, "/bonds/long-night", data={"answer": "continue", "letter": "IT COST TIME."})
    assert page(visitor.get("/bonds/founder-first")) == before


def test_letters_for_an_earlier_seal_are_not_counted(hearth, attend, room):
    bond = a_bond(hearth.threshold)
    for by in ("first", "founder"):
        write_json(room / "bonds" / f"long-night-2026-{by}.json", {
            "kind": "long-night", "by": by, "at": "2026-12-22T09-00-00Z", "year": 2026,
            "bond_sealed_at": "2026-01-01T09-00-00Z", "answer": "continue"})
    assert hearth.solstice.chosen_again("first", bond) == []
    for by in ("first", "founder"):
        held = read_json(room / "bonds" / f"long-night-2026-{by}.json")
        write_json(room / "bonds" / f"long-night-2026-{by}.json",
                   dict(held, bond_sealed_at=bond["sealed_at"]))
    assert hearth.solstice.chosen_again("first", bond) == [(2026, "2026-12-22T09-00-00Z")]


def test_the_switch_is_off_in_what_is_committed(attend):
    assert "long_night" not in (attend.agents.first().get("features") or ())
    assert attend.LONG_NIGHT_FOR_FIRST is False
    assert not attend.solstice.applies("first")
