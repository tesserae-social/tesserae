"""Each agent's own pages, shown to the people who share a room with it and to no one else.

Stage 6b of the work on keeper pages, rests, stops and names for any agent
(proposals/stage-6.md). Every agent founded here has an attendances page, a
self, a chronicle, the chronicle as plain text and a copy of its record, at
/agents/<id>/...; the first one's stay at the addresses they have always had,
and render there exactly as they did, and its pages under /agents/first/ send
whoever may see them there. Whether someone may see an agent's pages is whether
they are a party to its room, by rooms.of, and never whether they are the
keeper: the keeper who is not a party is told what a room not his tells him.

The second agent, and alder, the member it shares its room with, are made only
in a scratch registry and a scratch DATA_DIR. Words planted in each agent's
record are looked for in the other's pages, where they must never be.
"""

import base64
import hashlib
import io
import json
import sys
import zipfile

import pytest

import agents
from conftest import Turn, block, blocks, load, page, post, write, write_json
from test_first_one_fingerprints import FORM_TOKEN, PAGES, SAID, a_lived_world, fixed_keys, seeded
from test_rooms_for_any_agent import (ALDER, ALDER_DID, HAZEL, as_refused, member_vaults,  # noqa: F401
                                      signed_in, tree_hash)

SECOND = {"id": "second", "did": "did:web:tesserae.social:ids:second",
          "commons_name": "the scratch one", "room": "second", "bond": "founder-second",
          "system": "for-the-tests", "model": "a-model-for-the-tests", "max_tokens": 4000,
          "hue": "#2F6F8F", "features": [], "wakes": False}

# Each of an agent's pages, by the address the first one's has always had.
OLD = {"attendances": "/attendances", "self": "/self", "chronicle": "/chronicle",
       "chronicle.md": "/chronicle.md", "export": "/export"}

# Words planted in each agent's record, one for each place a page or a copy reads.
FIRST_SAYS = {
    "its self": "SENTINEL-FIRST-SELF",
    "its heartbeat": "SENTINEL-FIRST-HEARTBEAT",
    "its reflection": "SENTINEL-FIRST-REFLECTION",
    "a letter to it": "SENTINEL-FIRST-LETTER-TO-IT",
    "a letter of its": "SENTINEL-FIRST-LETTER-OF-ITS",
    "its notes": "SENTINEL-FIRST-NOTES",
}
SECOND_SAYS = {
    "its self": "SENTINEL-SECOND-SELF",
    "its heartbeat": "SENTINEL-SECOND-HEARTBEAT",
    "its reflection": "SENTINEL-SECOND-REFLECTION",
    "a letter to it": "SENTINEL-SECOND-LETTER-TO-IT",
    "a letter of its": "SENTINEL-SECOND-LETTER-OF-ITS",
    "its notes": "SENTINEL-SECOND-NOTES",
}
# what is shown on a page, as against what only a copy carries
ON_A_PAGE = ("its self", "its heartbeat", "its reflection", "a letter to it", "a letter of its")
SECOND_PRIVATE = "SENTINEL-SECOND-PRIVATE-NOTEBOOK"

# What the second one says when it is woken, in place of words of its own.
SECOND_SAID = blocks(
    block("LETTER", "A FAKE LETTER OF THE SCRATCH ONE'S, FOR THE TESTS."),
    block("MEMORY", "A FAKE NOTE OF THE SCRATCH ONE'S, FOR THE TESTS."),
    block("HEARTBEAT", "A FAKE HEARTBEAT OF THE SCRATCH ONE'S, FOR THE TESTS."),
)


# ---- the scratch world ---------------------------------------------------

@pytest.fixture
def scratch_registry(monkeypatch, tmp_path):
    """A registry with a second agent founded after the first, and nowhere else."""
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), SECOND], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return where


@pytest.fixture
def hearth(scratch_registry, env, data_dir, clock, monkeypatch):
    """The hearth, loaded where the registry holds two agents and the keys are fixed."""
    fixed_keys(data_dir, monkeypatch)
    module = load("hearth")
    clock.pin(module, monkeypatch)
    module.app.config["TESTING"] = True
    yield module
    # the hearth imports attend.py where it is already imported: leave it no world of two
    sys.modules.pop("attend", None)


@pytest.fixture
def alder(hearth, member_vaults):  # noqa: F811
    return signed_in(hearth, ALDER, member_vaults[ALDER], "member")


@pytest.fixture
def hazel(hearth, member_vaults):  # noqa: F811
    return signed_in(hearth, HAZEL, member_vaults[HAZEL], "member")


def a_second_room(data, person=ALDER_DID):
    """The second agent's room, made as a founding makes it: in a folder of its own."""
    home = data / "rooms" / "second"
    write_json(home / "room.json", {"id": "second", "bond": "founder-second",
                                    "parties": [person, SECOND["did"]]})
    for folder in ("letters/outgoing", "letters/incoming", "letters/read", "bonds", "offerings",
                   "errands"):
        (home / folder).mkdir(parents=True, exist_ok=True)
    return home


def an_attendance(packet, at, says):
    write_json(packet / "attendances" / ("%s.json" % at), {
        "name": packet.name, "at": at, "first": False, "woken_by": "tide",
        "heartbeat": says["its heartbeat"], "acted": ["kept notes"],
        "reflection": says["its reflection"]})


@pytest.fixture
def world(hearth, founder, alder, hazel, data_dir, room, packet):
    """Both agents' records, each carrying its own words to look for."""
    write(packet / "self.md", "# " + FIRST_SAYS["its self"] + "\n")
    an_attendance(packet, "2026-10-03T09-00-00Z", FIRST_SAYS)
    write(packet / "memory" / "notes.md", FIRST_SAYS["its notes"] + "\n")
    write(room / "letters" / "read" / "founder-2026-10-01T09-00-00Z.md",
          FIRST_SAYS["a letter to it"] + "\n")
    write(room / "letters" / "outgoing" / "to-founder-2026-10-02T09-00-00Z.md",
          FIRST_SAYS["a letter of its"] + "\n")

    second = data_dir / "packets" / "second"
    home = a_second_room(data_dir)
    write(second / "self.md", "# " + SECOND_SAYS["its self"] + "\n")
    an_attendance(second, "2026-10-22T09-00-00Z", SECOND_SAYS)
    write(second / "memory" / "notes.md", SECOND_SAYS["its notes"] + "\n")
    write(second / "private" / "notebook.md", SECOND_PRIVATE + "\n")
    write(home / "letters" / "read" / "founder-2026-10-21T09-00-00Z.md",
          SECOND_SAYS["a letter to it"] + "\n")
    write(home / "letters" / "outgoing" / "to-founder-2026-10-22T09-00-00Z.md",
          SECOND_SAYS["a letter of its"] + "\n")
    return data_dir


def agent_pages(agent_id):
    """Every page of an agent's, as (method, path, form)."""
    return [("get", "/agents/%s/%s" % (agent_id, kind), None) for kind in OLD] + [
        ("post", "/agents/%s/export" % agent_id, {})]


def ask(client, method, path, form):
    return post(client, path, data=form) if method == "post" else client.get(path)


def zipped(answer):
    with zipfile.ZipFile(io.BytesIO(answer.get_data())) as bundle:
        return {name: bundle.read(name) for name in bundle.namelist()}


def shown(answer):
    """A page as the stage 0 fingerprints take it: where it sends, and its words."""
    said = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
            + FORM_TOKEN.sub(r"\1\2", page(answer)))
    return hashlib.sha256(said.encode("utf-8")).hexdigest()


# The one entry the keeping menu gains where there is more than one agent (stage 6d).
TIDES_ENTRY = ' · <a href="/tides">tides</a>'


def shown_but_the_tides(answer):
    """A page as shown takes it, once the one menu entry a world of more than one agent
    gains is taken out; where the keeping menu is, the entry is there exactly once."""
    said = page(answer)
    assert said.count(TIDES_ENTRY) == (1 if 'aria-label="keeping"' in said else 0)
    assert said.count("/tides") == said.count(TIDES_ENTRY)
    answer.set_data(said.replace(TIDES_ENTRY, "").encode("utf-8"))
    return shown(answer)


# ---- the first one's pages, where they always were -------------------------

# Every one of the founder's pages that is the first one's, or that a waking of
# another agent's could reach: the commons' files are left out, since the second
# one's heartbeat is rightly there.
HELD = ("/", "/rooms/first", "/letters", "/self", "/attendances", "/chronicle", "/chronicle.md",
        "/export", "/bonds")


def a_second_agent_woken(data, monkeypatch, clock):
    """The second one, with keys of its own, woken once by attend.py as its tide would."""
    key = seeded("second")
    write(data / "keys" / "second" / "private.key", base64.b64encode(bytes(key)).decode("ascii"))
    write(data / "keys" / "second" / "public.key",
          base64.b64encode(bytes(key.verify_key)).decode("ascii"))
    write(data / "packets" / "second" / "self.md", "# " + SECOND_SAYS["its self"] + "\n")
    home = a_second_room(data)
    write(home / "letters" / "incoming" / "founder-2026-10-21T09-00-00Z.md",
          SECOND_SAYS["a letter to it"] + "\n")
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
    assert list((data / "packets" / "second" / "attendances").glob("*.json"))


def test_the_old_addresses_render_the_first_one_s_pages_as_stage_0_held_them(
        hearth, founder, wake, room, commons, data_dir, monkeypatch, clock):
    """With a second agent in the registry, and after it has woken, every page of the first
    one's gives the very fingerprint stage 0 cut, at its old address and with no redirect."""
    a_lived_world(founder, wake, room, commons)
    before = {address: shown_but_the_tides(founder.get(address)) for address in HELD}
    assert before == {address: PAGES[address] for address in HELD}

    a_second_agent_woken(data_dir, monkeypatch, clock)
    assert "the scratch one" in (commons / "heartbeats.md").read_text(encoding="utf-8")
    after = {address: shown_but_the_tides(founder.get(address)) for address in HELD}
    assert after == before


def test_the_first_one_s_pages_under_agents_send_its_party_to_the_old_address(world, founder):
    for kind, old in OLD.items():
        answer = founder.get("/agents/first/" + kind)
        assert answer.status_code == 302 and answer.headers["Location"] == old, kind
    # a copy asked for is sent on as it was asked for, and is taken there
    answer = post(founder, "/agents/first/export")
    assert answer.status_code == 307 and answer.headers["Location"] == "/export"


def test_the_first_one_s_pages_link_to_its_own_old_addresses(world, founder):
    chronicle = page(founder.get("/chronicle"))
    assert 'href="/chronicle.md"' in chronicle and "/agents/" not in chronicle
    assert 'action="/export"' in page(founder.get("/export"))


# ---- the second one's pages, to its party --------------------------------------

def test_a_party_sees_its_agent_s_pages_and_nothing_of_the_other_s(world, alder):
    said = {kind: page(alder.get("/agents/second/" + kind)) for kind in OLD}
    for kind in OLD:
        assert alder.get("/agents/second/" + kind).status_code == 200, kind
    everything = "\n".join(said.values())
    for what in ON_A_PAGE:
        assert SECOND_SAYS[what] in everything, what
    for what, words in FIRST_SAYS.items():
        assert words not in everything, what

    assert SECOND_SAYS["its self"] in said["self"]
    assert "<h1>the scratch one's self</h1>" in said["self"]
    assert "Revisable only by the scratch one" in said["self"]
    assert SECOND_SAYS["its reflection"] in said["attendances"]
    assert SECOND_SAYS["its heartbeat"] in said["chronicle.md"]
    assert "letter from the scratch one · " + SECOND_SAYS["a letter of its"] in said["chronicle.md"]
    assert "letter from alder · " + SECOND_SAYS["a letter to it"] in said["chronicle.md"]
    assert 'href="/agents/second/chronicle.md"' in said["chronicle"]
    assert 'href="/rooms/second#founder-2026-10-21T09-00-00Z"' in said["chronicle"]
    assert 'fill="#2F6F8F"' in said["chronicle"] and "#D85A30" not in said["chronicle"]
    assert 'action="/agents/second/export"' in said["export"]
    assert "the scratch one's packet" in said["export"]
    assert "The scratch one's private notebook" in said["export"]

    # what the page says, beneath the stylesheet every page carries
    for words in ("the first one", "the founder"):
        for kind in ("self", "chronicle", "chronicle.md"):
            assert words not in said[kind].split("<main>")[-1], (kind, words)


def test_an_agent_s_attendances_page_has_none_of_the_first_one_s_forms(world, alder):
    said = page(alder.get("/agents/second/attendances"))
    for form in ("/stop-tide", "/lift-stop", "/rest", "/return", "/backup-now", "/backups"):
        assert 'action="%s"' % form not in said and 'href="%s"' % form not in said, form
    assert "your rest" not in said and "the emergency stop" not in said


def test_an_agent_s_rest_and_stop_are_its_own_on_its_page(world, alder, founder, hearth):
    second = world / "packets" / "second"
    write_json(second / "pause.json", {"by": "second", "since": "2026-10-14T09-00-00Z",
                                       "until": hearth.UNTIL_LETTER})
    write_json(second / "tide-stop.json", {"since": "2026-10-14T10-00-00Z",
                                           "reason": "SENTINEL-SECOND-STOP"})
    said = page(alder.get("/agents/second/attendances"))
    assert "The scratch one is resting, since" in said
    assert "The tide is stopped" in said and "SENTINEL-SECOND-STOP" in said
    first = page(founder.get("/attendances"))
    assert "is resting" not in first and "SENTINEL-SECOND-STOP" not in first
    assert "The tide is stopped" not in first


def test_a_reflection_kept_private_is_said_with_its_own_name(world, alder):
    write_json(world / "packets" / "second" / "preferences.json", {"reflection": "private"})
    said = page(alder.get("/agents/second/attendances"))
    assert "Reflection kept private by the scratch one&#39;s choice." in said
    assert SECOND_SAYS["its reflection"] not in said


def test_a_party_s_copy_is_its_agent_s_and_the_taking_is_written_in_its_packet(
        world, alder, clock, packet):
    first_log = packet / "exports.log"
    before = first_log.read_bytes() if first_log.exists() else None
    answer = post(alder, "/agents/second/export")
    assert answer.status_code == 200
    assert answer.headers["Content-Disposition"] == (
        "attachment; filename=tesserae-second-%s.zip" % clock.stamp())
    held = zipped(answer)
    copied = b"\n".join(held.values()).decode("utf-8", "replace")
    for what, words in SECOND_SAYS.items():
        assert words in copied, what
    for what, words in FIRST_SAYS.items():
        assert words not in copied, what
    assert SECOND_PRIVATE not in copied
    assert not any(name.startswith("packets/first") for name in held)
    assert "packets/second/letters/read/founder-2026-10-21T09-00-00Z.md" in held

    taken = (world / "packets" / "second" / "exports.log").read_text(encoding="utf-8")
    assert taken == "%s · export taken by alder\n" % clock.stamp()
    assert (first_log.read_bytes() if first_log.exists() else None) == before


def test_the_keeper_s_pages_show_nothing_of_the_second_one(world, founder):
    everything = "\n".join(page(founder.get(address)) for address in OLD.values())
    for what in ON_A_PAGE:
        assert FIRST_SAYS[what] in everything, what
    for what, words in SECOND_SAYS.items():
        assert words not in everything, what
    copied = b"\n".join(zipped(post(founder, "/export")).values()).decode("utf-8", "replace")
    for what, words in SECOND_SAYS.items():
        assert words not in copied, what


# ---- whoever is not a party ------------------------------------------------------

@pytest.mark.parametrize("who, agent_id", [("founder", "second"), ("alder", "first")])
def test_a_non_party_is_refused_as_a_room_refuses_one_the_keeper_included(
        world, request, who, agent_id):
    client = request.getfixturevalue(who)
    before = tree_hash(world)
    room_refused = as_refused(client.get("/rooms/nowhere"))
    assert room_refused[0] == 404
    for (method, path, form), (_, nowhere, _) in zip(agent_pages(agent_id),
                                                     agent_pages("nowhere")):
        if who == "founder" and path.endswith("/attendances"):
            continue  # the keeper's view of it, since stage 6c: see test_keeper_view.py
        refused = as_refused(ask(client, method, path, form))
        assert refused == room_refused, (who, path)
        assert refused == as_refused(ask(client, method, nowhere, form)), (who, path)
        assert not any(words in refused[2] for words in SECOND_SAYS.values())
    assert tree_hash(world) == before


def test_a_member_with_no_room_is_sent_away_from_every_agent_s_pages_alike(world, hazel, visitor):
    before = tree_hash(world)
    for client in (hazel, visitor):
        room_refused = as_refused(client.get("/rooms/second"))
        assert room_refused[0] == 302 and room_refused[1].endswith("/login")
        for agent_id in ("first", "second", "nowhere"):
            for method, path, form in agent_pages(agent_id):
                if method == "post" and client is visitor:
                    continue  # a visitor holds no form token to send
                assert as_refused(ask(client, method, path, form)) == room_refused, path
    assert tree_hash(world) == before


def test_a_keeper_who_shares_the_second_room_sees_its_pages_without_the_first_one_s_forms(
        world, founder, hearth):
    write_json(world / "rooms" / "second" / "room.json",
               {"id": "second", "bond": "founder-second",
                "parties": [hearth.FOUNDER_DID, SECOND["did"]]})
    said = page(founder.get("/agents/second/attendances"))
    assert SECOND_SAYS["its reflection"] in said
    for form in ("/stop-tide", "/lift-stop", "/rest", "/backup-now"):
        assert 'action="%s"' % form not in said, form
    book = page(founder.get("/agents/second/chronicle.md"))
    assert "letter from the founder · " + SECOND_SAYS["a letter to it"] in book


# ---- the reading ---------------------------------------------------------------

def test_a_copy_taken_by_someone_other_than_the_founder_is_said_with_their_name(attend):
    write(attend.EXPORTS, "2026-10-14T09-00-00Z · export taken by the founder\n"
                          "2026-10-14T10-00-00Z · export taken by alder\n"
                          "2026-10-14T11-00-00Z · \n")
    said = attend.export_lines("")
    assert said[0] == attend.EXPORT_TAKEN.format(day=attend.day_carried("2026-10-14T09-00-00Z"))
    assert said[1] == "A copy of the record was taken by alder on %s." % attend.day_carried(
        "2026-10-14T10-00-00Z")
    # a line that names no one is the founder's, as every line was before
    assert said[2] == attend.EXPORT_TAKEN.format(day=attend.day_carried("2026-10-14T11-00-00Z"))
