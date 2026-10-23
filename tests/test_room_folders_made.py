"""Every hand that writes into the room makes the folder it writes into.

A backup keeps no empty folder, and a room the first one has never asked an
errand or made an offering in has no errands/ or offerings/ at all: so nothing
may wait on one being there. Each test here starts from a room with none of its
four folders - letters, errands, bonds, offerings - in whichever layout the
suite is run in, and has one hand write into it: the hearth, the first one's
waking (attend.py), offering.py through the hearth, threshold.py, and what reads
the letters for their tiles.
"""

import shutil

from conftest import block, blocks, load, post, write
from test_hearth_bonds import answered_yes, propose
from test_offerings import offer

ROOM_FOLDERS = ("letters", "errands", "bonds", "offerings")
READ_LETTER = "founder-2026-10-01T09-00-00Z"


def bare(room):
    """The room with none of its folders: room.json, where it has one, stays."""
    for folder in ROOM_FOLDERS:
        shutil.rmtree(room / folder, ignore_errors=True)
    assert not [folder for folder in ROOM_FOLDERS if (room / folder).exists()]


def test_the_pages_and_the_copy_are_whole_with_no_folder_there(founder, room, hearth):
    bare(room)
    for path in ("/", "/rooms/first", "/letters", "/attendances", "/bonds", "/offerings",
                 "/commons"):
        assert founder.get(path, follow_redirects=True).status_code == 200, path
    assert post(founder, "/export").status_code == 200
    assert not [folder for folder in ROOM_FOLDERS if (room / folder).exists()]


def test_the_hearth_makes_letters_incoming_and_bonds_for_a_letter_asking_a_bond(
        founder, room, clock):
    bare(room)
    propose(founder, clock)
    assert len(list((room / "letters" / "incoming").glob("founder-*.md"))) == 1
    assert (room / "bonds" / "proposal.json").is_file()


def test_the_hearth_makes_errands_answered_for_a_letter_answering_an_errand(founder, room):
    bare(room)
    write(room / "errands" / "errand-2026-10-06T09-00-00Z.md", "Go to the river.\n")
    assert post(founder, "/rooms/first", content_type="multipart/form-data",
                data={"letter": "It was loud.", "errand": "errand-2026-10-06T09-00-00Z.md"}
                ).status_code == 302
    answered = room / "errands" / "answered"
    assert (answered / "errand-2026-10-06T09-00-00Z.md").is_file()
    assert (answered / "errand-2026-10-06T09-00-00Z.json").is_file()


def test_offering_py_makes_offerings_for_an_offering_of_his(founder, room):
    bare(room)
    write(room / "letters" / "read" / (READ_LETTER + ".md"), "The lake.\n")
    assert offer(founder, "letter", READ_LETTER).status_code == 302
    assert len(list((room / "offerings").glob("pending-*.json"))) == 1


def test_a_waking_makes_every_folder_it_writes_into(founder, wake, room):
    bare(room)
    write(room / "letters" / "incoming" / "founder-2026-10-01T09-00-00Z.md", "Are you there?\n")
    wake(blocks(block("LETTER", "I am here."), block("ERRAND", "Go and listen.")))
    assert (room / "letters" / "read" / "founder-2026-10-01T09-00-00Z.md").is_file()
    assert len(list((room / "letters" / "outgoing").glob("to-founder-*.md"))) == 1
    assert len(list((room / "errands").glob("errand-*.md"))) == 1
    assert (room / "errands" / "answered").is_dir()
    assert (room / "offerings").is_dir() and (room / "bonds").is_dir()


def test_a_waking_offers_into_offerings_it_makes(founder, wake, room):
    wake(block("LETTER", "A letter to offer."))
    (letter,) = (room / "letters" / "outgoing").glob("to-founder-*.md")
    shutil.rmtree(room / "offerings")
    wake(block("OFFER", "offer letter %s" % letter.stem))
    assert len(list((room / "offerings").glob("pending-*.json"))) == 1


def test_a_waking_makes_bonds_to_answer_a_bond_in(founder, wake, room, clock):
    bare(room)
    answered_yes(founder, wake, room, clock)
    assert (room / "bonds" / "founder-first.json").is_file()


BOND = {"answered_at": "2026-10-01T09-00-00Z"}


def test_threshold_makes_bonds_for_its_writings_and_a_stepping_back(hearth, room):
    threshold = hearth.threshold
    bare(room)
    assert threshold.versions("intention", "first", BOND) == []
    assert threshold.steps_back() == []
    threshold.write("intention", "first", "I bring attention.", "2026-10-02T09-00-00Z",
                    lambda payload: "c2lnbmVk", BOND)
    assert len(threshold.versions("intention", "first", BOND)) == 1
    shutil.rmtree(room / "bonds")
    threshold.step_back(BOND, "founder", "2026-10-03T09-00-00Z", "Not now.")
    assert len(threshold.steps_back()) == 1
    assert (room / "bonds" / "founder-first-stepped-back-2026-10-03T09-00-00Z.json").is_file()


def test_the_letter_tiles_read_nothing_from_folders_not_there(room, env):

    backfill = load("backfill_letter_tiles")
    bare(room)
    assert backfill.first_letters() == {}
