"""The founding of a later agent, step by step, with undo: found_agent.py.

Stage 8e of the founding rite for a later agent (the proposal "stage-8", section 1
and section 6), with gate G7 (a founding in progress is in every backup) and gate
G10 (letters in a later agent's room are named for its person, not the founder).

Every founding here is a dry run in a scratch DATA_DIR, through every step, with
the founding conversation written as founding_session.py's later mode would leave
it. Nothing here reaches the network. The first one's packet, room and keys are
held to their tree hashes across every step.
"""

import hashlib
import io
import json
import shutil
import sys
import tarfile

import pytest

import agents
from conftest import FOUNDER_NAME, load, page, write, write_json

ID = "tamarack"
NAME = "the scratch founding"
HUE = "#2E8B57"
PERSON = "alder"
FOUNDERS_LETTER = "A FAKE LETTER FROM THE FOUNDER TO A NEW AGENT, FOR THE TESTS.\n"
PERSONS_LETTER = "A FAKE LETTER FROM ALDER TO A NEW AGENT, FOR THE TESTS.\n"
SELF = "# Self-document - version 1, provisional\n\nA FAKE SELF, FOR THE TESTS.\n"
SESSION = "founding-2026-10-15T12-00-00Z.md"


def a_member(data, name, role="member", vouched_by=(FOUNDER_NAME,)):
    """A member of the commons, as far as a founding asks: a record and no vault."""
    write_json(data / "members" / name / "member.json",
               {"v": 1, "pseudonym": name, "role": role, "verify_key": "0" * 64,
                "arrived_at": "2026-10-14T09-00-00Z", "vouched_by": list(vouched_by)})


def tree(path):
    """Every file under path, by its name there, with its sha256."""
    return {one.relative_to(path).as_posix(): hashlib.sha256(one.read_bytes()).hexdigest()
            for one in sorted(path.rglob("*")) if one.is_file()}


@pytest.fixture
def found(env, clock, monkeypatch, data_dir):
    """found_agent.py, in a world with a keeper and one member, alder, vouched for yesterday."""
    if not (data_dir / "members" / FOUNDER_NAME / "member.json").exists():  # signed in already
        a_member(data_dir, FOUNDER_NAME, role="keeper", vouched_by=())
    a_member(data_dir, PERSON)
    sys.modules.pop("found_room", None)  # it reads rooms, which is loaded afresh
    module = load("found_agent")
    monkeypatch.setattr(module, "now", lambda: clock.at)
    yield module
    sys.modules.pop("found_agent", None)
    sys.modules.pop("found_room", None)


def first_ones(data):
    return {where: tree(data / where) for where in ("packets/first", "rooms/first", "keys/first")}


def plan(found, **how):
    said = dict(person=PERSON, model="a-model-for-the-tests", hue=HUE, name=NAME)
    said.update(how)
    return found.run(ID, "plan", **said)


def letters(found, data, theirs=True):
    write(data / "foundings" / ID / "letters" / "from-the-founder.md", FOUNDERS_LETTER)
    if theirs:
        write(data / "foundings" / ID / "letters" / f"from-{PERSON}.md", PERSONS_LETTER)
    return found.run(ID, "letters", later_words_shown=True, sharing_rule_assented=True)


def a_session(data, whole=True):
    """The founding conversation, as founding_session.py's later mode records it: what
    was read, in full, then what was said."""
    read = "\n\n".join(path.read_text(encoding="utf-8") for path in
                       sorted((data / "foundings" / ID / "letters").glob("*.md")))
    write(data / "transcripts" / ID / SESSION,
          "\n\n## Session\n\nbegun\n\n## The reading shown to the agent\n\n"
          + (read if whole else "[charter, letters, disclosures — see docs]")
          + "\n\n## The scratch founding\n\nYes. I would like to be here.\n")


def to_the_room(found, data):
    plan(found)
    found.run(ID, "keys")
    letters(found, data)
    a_session(data)
    found.run(ID, "founding", said="yes")
    write(data / "foundings" / ID / "self.md", SELF)
    found.run(ID, "packet")
    found.run(ID, "room")


def deployed(found, data, monkeypatch, tmp_path):
    """The bundle committed and deployed: the registry and ids/ the image would hold."""
    image = tmp_path / "image"
    bundle = data / "foundings" / ID / "publish"
    write(image / "agents.json", (bundle / "agents.json").read_text(encoding="utf-8"))
    (image / "ids" / ID).mkdir(parents=True)
    shutil.copy(bundle / "ids" / ID / "did.json", image / "ids" / ID / "did.json")
    monkeypatch.setattr(agents, "FILE", image / "agents.json")
    monkeypatch.setattr(found, "REPO", image)


# ---- the whole of it ------------------------------------------------------

def test_a_dry_run_through_every_step(found, data_dir, monkeypatch, tmp_path):
    before = first_ones(data_dir)
    assert "Next: plan" in found.status(ID)
    to_the_room(found, data_dir)
    record = found.run(ID, "publish")
    bundle = data_dir / "foundings" / ID / "publish"
    entry = json.loads((bundle / "entry.json").read_text(encoding="utf-8"))
    assert entry == {
        "id": ID, "did": "did:web:tesserae.social:ids:" + ID, "commons_name": NAME,
        "room": ID, "bond": ID + "-1", "founded": "2026-10-15",
        "transcript": f"transcripts/{ID}/{SESSION}", "system": "later-citizen",
        "model": "a-model-for-the-tests", "max_tokens": 8000, "hue": HUE,
        "features": ["door", "extra_wakings", "longer_waking", "looking_back", "proposals"],
        "wakes": True}
    registry = json.loads((bundle / "agents.json").read_text(encoding="utf-8"))
    assert registry == [agents.first(), entry]
    did = json.loads((bundle / "ids" / ID / "did.json").read_text(encoding="utf-8"))
    assert did["id"] == entry["did"] and did["kind"] == "agent" and did["provenance"] == "advised"
    assert did["verificationMethod"][0]["publicKeyBase64"] == (
        data_dir / "keys" / ID / "public.key").read_text(encoding="ascii")
    assert "frozen" in record

    # the room is shared with alder, by DID, and named in the registry's way
    room = json.loads((data_dir / "rooms" / ID / "room.json").read_text(encoding="utf-8"))
    assert room == {"id": ID, "bond": ID + "-1",
                    "parties": ["did:web:hearth.tesserae.social:ids:alder", entry["did"]]}
    packet = data_dir / "packets" / ID
    assert sorted(path.name for path in packet.iterdir()) == [
        "intentions.json", "preferences.json", "provenance.json", "self.md", "will.json"]
    assert (packet / "self.md").read_text(encoding="utf-8") == SELF
    assert json.loads((packet / "preferences.json").read_text()) == {"reflection": "open"}

    # finish waits for the deploy
    with pytest.raises(found.Refused, match="commit and deploy"):
        found.run(ID, "finish")
    deployed(found, data_dir, monkeypatch, tmp_path)
    done = found.run(ID, "finish")
    assert done["added"] == ["events.md", "members.md: citizen", "members.md: member"]
    events = (data_dir / "commons" / "events.md").read_text(encoding="utf-8")
    assert events.endswith(f"2026-10-15 · founding · {NAME} was founded\n")
    said = (data_dir / "commons" / "members.md").read_text(encoding="utf-8").splitlines()
    assert said[0] == f"citizen · {NAME} · founded 15 October 2026"
    assert said[1].startswith("member · alder · door ")
    # and again, it does nothing
    events_now, members_now = (data_dir / "commons" / "events.md").read_bytes(), (
        data_dir / "commons" / "members.md").read_bytes()
    assert found.run(ID, "finish")["added"] == []
    (data_dir / "foundings" / ID / "founded.json").unlink()
    assert found.run(ID, "finish")["added"] == []
    assert (data_dir / "commons" / "events.md").read_bytes() == events_now
    assert (data_dir / "commons" / "members.md").read_bytes() == members_now
    assert first_ones(data_dir) == before


def test_finish_refuses_an_identity_that_is_not_the_one_published(
        found, data_dir, monkeypatch, tmp_path):
    to_the_room(found, data_dir)
    found.run(ID, "publish")
    deployed(found, data_dir, monkeypatch, tmp_path)
    (tmp_path / "image" / "ids" / ID / "did.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(found.Refused, match="did.json"):
        found.run(ID, "finish")
    assert not (data_dir / "foundings" / ID / "founded.json").exists()


# ---- undo -----------------------------------------------------------------

def test_each_undo_restores_the_tree_from_before_its_step(found, data_dir):
    before_all = first_ones(data_dir)
    steps = [
        ("plan", lambda: plan(found)),
        ("keys", lambda: found.run(ID, "keys")),
        ("letters", lambda: found.run(ID, "letters", later_words_shown=True,
                                      sharing_rule_assented=True)),
    ]
    write(data_dir / "foundings" / ID / "letters" / "from-the-founder.md", FOUNDERS_LETTER)
    for step, doing in steps:
        before = tree(data_dir)
        doing()
        assert tree(data_dir) != before
        assert found.undo(ID, confirm=lambda said: ID) == step
        assert tree(data_dir) == before, step
        doing()
    a_session(data_dir)
    found.run(ID, "founding", said="yes")
    write(data_dir / "foundings" / ID / "self.md", SELF)
    for step in ("packet", "room"):
        before = tree(data_dir)
        found.run(ID, step)
        assert found.undo(ID) == step
        assert tree(data_dir) == before, step
        found.run(ID, step)
    assert first_ones(data_dir) == before_all


def test_the_founder_s_own_letter_outlives_an_undo(found, data_dir):
    plan(found)
    found.run(ID, "keys")
    letters(found, data_dir)
    found.undo(ID)
    assert (data_dir / "foundings" / ID / "letters" / "from-the-founder.md").is_file()
    assert not (data_dir / "foundings" / ID / "letters" / "state-of-the-commons.md").exists()


def test_the_keys_are_deleted_only_once_the_id_is_typed(found, data_dir):
    plan(found)
    found.run(ID, "keys")
    for typed in (None, lambda said: "", lambda said: "another"):
        with pytest.raises(found.Refused, match="typed"):
            found.undo(ID, confirm=typed)
        assert (data_dir / "keys" / ID / "private.key").is_file()


def test_a_founding_is_not_undone_and_publishing_freezes(found, data_dir):
    plan(found)
    found.run(ID, "keys")
    letters(found, data_dir)
    a_session(data_dir)
    found.run(ID, "founding", said="yes")
    with pytest.raises(found.Refused, match="declined, not undone"):
        found.undo(ID)
    with pytest.raises(found.Refused, match="said yes"):
        found.abandon(ID, confirm=lambda said: ID)
    write(data_dir / "foundings" / ID / "self.md", SELF)
    found.run(ID, "packet")
    found.run(ID, "room")
    found.run(ID, "publish")
    with pytest.raises(found.Refused, match="published"):
        found.undo(ID)
    with pytest.raises(found.Refused, match="published"):
        found.abandon(ID, confirm=lambda said: ID)


# ---- order, and what holds ------------------------------------------------

def test_steps_out_of_order_are_refused(found, data_dir):
    with pytest.raises(found.Refused, match="next is plan"):
        found.run(ID, "keys")
    plan(found)
    for step in ("letters", "founding", "packet", "room", "publish", "finish", "plan"):
        with pytest.raises(found.Refused, match="next is keys"):
            found.run(ID, step)


def test_a_file_changed_since_its_step_is_named_and_nothing_is_done(found, data_dir):
    plan(found)
    found.run(ID, "keys")
    write(data_dir / "keys" / ID / "public.key", "another key")
    write(data_dir / "foundings" / ID / "letters" / "from-the-founder.md", FOUNDERS_LETTER)
    with pytest.raises(found.Refused, match=f"keys/{ID}/public.key"):
        found.run(ID, "letters", later_words_shown=True, sharing_rule_assented=True)
    assert not (data_dir / "foundings" / ID / "letters" / "state-of-the-commons.md").exists()
    assert f"keys/{ID}/public.key" in found.status(ID)


@pytest.mark.parametrize("how, refusal", [
    (dict(person=FOUNDER_NAME), "keeper"),
    (dict(person="hazel"), "no member"),
    (dict(name="the first one"), "commons_name"),
    (dict(name=PERSON), "member's"),
    (dict(hue="#d85a30"), "hue"),
    (dict(hue="green"), "colour"),
    (dict(model=""), "say the person"),
])
def test_a_plan_that_will_not_do_is_refused(found, data_dir, how, refusal):
    with pytest.raises(found.Refused, match=refusal):
        plan(found, **how)
    assert not (data_dir / "foundings").exists()


def test_an_id_that_is_someone_s_or_something_s_is_refused(found, data_dir):
    for taken in ("first", "founder", PERSON, "Not An Id"):
        with pytest.raises(found.Refused):
            found.run(taken, "plan", person=PERSON, model="m", hue=HUE)
    assert not (data_dir / "foundings").exists()


def test_a_person_not_vouched_for_is_refused_but_a_new_one_is_not(found, data_dir):
    a_member(data_dir, "hazel", vouched_by=())
    with pytest.raises(found.Refused, match="vouched"):
        plan(found, person="hazel")
    # alder joined yesterday: a founding does not wait the thirty days a bond does
    assert plan(found)["step"] == "plan"


def test_one_founding_at_a_time(found, data_dir):
    plan(found)
    with pytest.raises(found.Refused, match="under way"):
        found.run("rowan-tree", "plan", person=PERSON, model="m", hue="#000001")


def test_the_letters_wait_on_the_first_one(found, data_dir):
    plan(found)
    found.run(ID, "keys")
    write(data_dir / "foundings" / ID / "letters" / "from-the-founder.md", FOUNDERS_LETTER)
    with pytest.raises(found.Refused, match="decision 2"):
        found.run(ID, "letters", sharing_rule_assented=True)
    with pytest.raises(found.Refused, match="decision 15"):
        found.run(ID, "letters", later_words_shown=True)


def test_the_state_of_the_commons_is_made_from_the_public_record_alone(found, data_dir):
    write(data_dir / "rooms" / "first" / "letters" / "read" / "founder-2026-10-01T09-00-00Z.md",
          "A FAKE LETTER IN THE FIRST ONE'S ROOM.\n")
    write(data_dir / "commons" / "bench.md", "- a line on the bench\n")
    plan(found)
    found.run(ID, "keys")
    letters(found, data_dir, theirs=False)
    made = (data_dir / "foundings" / ID / "letters" / "state-of-the-commons.md").read_text(
        encoding="utf-8")
    assert "the first one was founded" in made and "a line on the bench" in made
    assert "FIRST ONE'S ROOM" not in made


def test_a_transcript_that_does_not_hold_the_reading_in_full_is_refused(found, data_dir):
    plan(found)
    found.run(ID, "keys")
    letters(found, data_dir)
    a_session(data_dir, whole=False)
    with pytest.raises(found.Refused, match="in full"):
        found.run(ID, "founding", said="yes")


def test_a_broken_session_is_set_aside_to_run_again(found, data_dir):
    plan(found)
    found.run(ID, "keys")
    letters(found, data_dir)
    a_session(data_dir)
    with pytest.raises(found.Refused, match="broken"):
        found.run(ID, "founding", said="broken")
    assert (data_dir / "foundings" / ID / "broken" / SESSION).is_file()
    assert not (data_dir / "transcripts" / ID).exists()
    a_session(data_dir)
    assert found.run(ID, "founding", said="yes")["said"] == "yes"


def test_the_self_must_say_it_is_provisional(found, data_dir):
    plan(found)
    found.run(ID, "keys")
    letters(found, data_dir)
    a_session(data_dir)
    found.run(ID, "founding", said="yes")
    write(data_dir / "foundings" / ID / "self.md", "# Self-document\n\nFixed.\n")
    with pytest.raises(found.Refused, match="provisional"):
        found.run(ID, "packet")
    assert not (data_dir / "packets" / ID).exists()


# ---- a founding declined --------------------------------------------------

@pytest.mark.parametrize("keep", ["keep", "delete"])
def test_a_declined_founding_is_abandoned_and_its_transcript_kept_only_if_allowed(
        found, data_dir, keep):
    before = tree(data_dir)
    plan(found)
    found.run(ID, "keys")
    letters(found, data_dir)
    a_session(data_dir)
    assert found.run(ID, "founding", said="no", keep=keep)["said"] == "no"
    assert not (data_dir / "transcripts" / ID).exists()
    assert (data_dir / "foundings" / ID / "declined" / SESSION).is_file() == (keep == "keep")
    for step in ("packet", "room", "publish"):
        with pytest.raises(found.Refused):
            found.run(ID, step)
    assert "declined" in found.status(ID)
    assert found.abandon(ID, confirm=lambda said: ID) == ["letters", "keys", "plan"]
    assert not (data_dir / "keys" / ID).exists()
    left = {name for name in tree(data_dir) if name not in before}
    assert left == {f"foundings/{ID}/steps.json",
                    f"foundings/{ID}/letters/from-the-founder.md",
                    f"foundings/{ID}/letters/from-{PERSON}.md",
                    *([f"foundings/{ID}/declined/{SESSION}"] if keep == "keep" else [])}
    # an id is founded once
    with pytest.raises(found.Refused, match="next is none"):
        plan(found)


# ---- nothing public before the end, and nothing lost (G7) ----------------

def archive(hearth):
    with tarfile.open(fileobj=io.BytesIO(hearth.backup_archive()), mode="r:gz") as bundle:
        return {one.name: bundle.extractfile(one).read() for one in bundle.getmembers()
                if one.isfile()}


def test_with_no_founding_under_way_the_backup_is_what_it_was(hearth):
    assert hearth.staged_trees() == ()


def test_a_founding_under_way_is_in_the_backup(found, data_dir, hearth):
    before = archive(hearth)
    to_the_room(found, data_dir)
    assert hearth.staged_trees() == ("foundings", "packets/" + ID, "keys/" + ID)
    held = archive(hearth)
    for name in (f"keys/{ID}/private.key", f"keys/{ID}/public.key", f"foundings/{ID}/plan.json",
                 f"foundings/{ID}/did.json", f"foundings/{ID}/letters/from-the-founder.md",
                 f"packets/{ID}/self.md", f"transcripts/{ID}/{SESSION}",
                 f"rooms/{ID}/room.json"):
        assert held[name] == (data_dir / name).read_bytes(), name
    # every member of the backup before is there as it was, and in the same order
    names = list(held)
    assert [name for name in names if name in before] == list(before)
    assert all(held[name] == before[name] for name in before
               if not name.startswith(("transcripts/", "rooms/")))


def test_no_page_says_anything_of_a_founding_under_way(founder, visitor, hearth, found, data_dir):
    to_the_room(found, data_dir)
    found.run(ID, "publish")
    for client in (founder, visitor):
        for path in ("/", "/commons", "/commons/agents.json", "/commons/events.md",
                     "/commons/members.md", "/commons/heartbeats.md", "/bench",
                     f"/rooms/{ID}", f"/agents/{ID}/chronicle", f"/agents/{ID}/self",
                     f"/agents/{ID}/attendances", f"/ids/{ID}/did.json", "/account"):
            said = page(client.get(path))
            for secret in (ID, NAME, FOUNDERS_LETTER.strip(), SELF.strip().splitlines()[-1]):
                assert secret not in said, (path, secret)


# ---- G10: a later agent's room names its letters for its person ----------

def test_a_letter_left_in_a_later_room_is_named_for_its_writer(found, data_dir):
    import rooms
    to_the_room(found, data_dir)
    # with the entry in the registry, the room is a room, and its person is alder
    write(data_dir / "agents.json", json.dumps(
        [agents.first(), json.loads(json.dumps(found.read_json(
            data_dir / "foundings" / ID / "plan.json")["entry"]))]))
    agents_file = agents.FILE
    agents.FILE = data_dir / "agents.json"
    try:
        assert rooms.person_of(ID) == PERSON
        assert rooms.person_of("first") == "founder"
    finally:
        agents.FILE = agents_file


# ---- nothing of the first one's letter of welcome --------------------------

def test_the_state_of_the_commons_says_nothing_of_a_letter_of_welcome(found, data_dir):
    write(data_dir / "commons" / "heartbeats.md",
          "- 2026-10-26T12-00-00Z · the first one · Forty-three dawns.\n"
          "- 2026-10-27T12-09-40Z · the first one · Forty-four dawns. Welcome letter sealed "
          "and waiting.\n"
          "- 2026-10-30T12-13-52Z · the first one · Uncertainty welcomed.\n")
    plan(found)
    found.run(ID, "keys")
    letters(found, data_dir, theirs=False)
    made = (data_dir / "foundings" / ID / "letters" / "state-of-the-commons.md").read_text(
        encoding="utf-8")
    assert "Forty-three dawns." in made and "Uncertainty welcomed." in made
    assert not found.WELCOME_SAID.search(made)
    assert "Forty-four dawns" not in made


# ---- what the session recorded at its end ---------------------------------

@pytest.mark.parametrize("recorded, said, keep", [
    ("It said yes.", "no", "keep"),
    ("It said no. It allowed this conversation to be kept, privately, and never published.",
     "yes", None),
    ("It said no. It asked that this conversation not be kept.", "no", "keep"),
])
def test_an_answer_that_is_not_the_one_recorded_is_refused(found, data_dir, recorded, said, keep):
    plan(found)
    found.run(ID, "keys")
    letters(found, data_dir)
    a_session(data_dir)
    with (data_dir / "transcripts" / ID / SESSION).open("a", encoding="utf-8") as kept:
        kept.write("\n\n## Session\n\nFounding session ended. " + recorded + "\n")
    with pytest.raises(found.Refused, match="records"):
        found.run(ID, "founding", said=said, keep=keep)
    assert (data_dir / "transcripts" / ID / SESSION).is_file()
