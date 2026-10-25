"""The registry of agents, and what is derived from it.

Stage 1 of the work that lets the tide wake more than one agent (the proposal
"waking for any agent", 25 October 2026). Five modules now take from agents.py
what they once wrote out by hand, and each must come to exactly what it wrote:
with agents.json read, and with it absent. A registry with a second agent in it
is made only in a scratch file here, and only to show that its id is a name no
member can take.

The fingerprints of the first one's world (test_first_one_fingerprints.py, and
READING_NOW in test_rooms_reading.py) are held by their own tests, which are run
with --agents=file and --agents=absent alike.
"""

import importlib
import json
import sys

import pytest

import agents

# What each module wrote out by hand before there was a registry.
FOUNDER_DID = "did:web:tesserae.social:ids:founder"
OLD_FIRST_DID = "did:web:tesserae.social:ids:first"
OLD_NAMES = {FOUNDER_DID: "the founder", OLD_FIRST_DID: "the first one"}
OLD_AGENTS = frozenset({OLD_FIRST_DID})
OLD_RESERVED = frozenset({
    "founder", "first", "the-first-one", "keeper", "tesserae", "hearth",
    "commons", "bench", "admin", "root", "system",
})
OLD_SITE_NAMES = ("the founder", "the first one")

# The modules that derive something from the registry.
DERIVED = ("bonds", "rooms", "door", "members", "public_screen")

SECOND = {"id": "second", "did": "did:web:tesserae.social:ids:second",
          "commons_name": "the second one", "room": "second", "bond": "founder-second",
          "wakes": False}


def fresh():
    """The derived modules, imported afresh against the registry as it now stands."""
    for name in DERIVED:
        sys.modules.pop(name, None)
    return {name: importlib.import_module(name) for name in DERIVED}


@pytest.fixture
def registry(env, monkeypatch, tmp_path):
    """Read the registry from a file this test chooses; leave no module that read it behind."""
    def use(where):
        monkeypatch.setattr(agents, "FILE", where)
        return fresh()
    yield use
    for name in DERIVED:
        sys.modules.pop(name, None)


def write_registry(path, entries):
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    return path


@pytest.fixture(params=["file", "absent"])
def derived(request, registry, tmp_path):
    """The derived modules, with agents.json as committed and with no file there."""
    if request.param == "file":
        where = agents.REPO / "agents.json"
        assert where.is_file()
    else:
        where = tmp_path / "agents.json"
        assert not where.exists()
    return registry(where)


# ---- the file and the fallback are one -----------------------------------

def test_the_committed_file_is_the_first_one_alone():
    entries = json.loads((agents.REPO / "agents.json").read_text(encoding="utf-8"))
    assert entries == [agents.FIRST]


def test_with_no_file_the_registry_is_the_first_one_alone(monkeypatch, tmp_path):
    monkeypatch.setattr(agents, "FILE", tmp_path / "agents.json")
    assert agents.registry() == [agents.FIRST]
    assert agents.first() == agents.FIRST


def test_the_registry_handed_out_is_a_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(agents, "FILE", tmp_path / "agents.json")
    agents.first()["id"] = "changed"
    assert agents.first()["id"] == "first"


# ---- each derived value is what was written by hand ----------------------

def test_bonds(derived):
    bonds = derived["bonds"]
    assert bonds.FIRST_DID == OLD_FIRST_DID
    assert bonds.NAMES == OLD_NAMES
    assert list(bonds.NAMES) == list(OLD_NAMES)  # in_order turns on the order
    assert bonds.AGENTS == OLD_AGENTS


def test_rooms(derived):
    rooms = derived["rooms"]
    assert (rooms.FIRST, rooms.FIRST_ROOM, rooms.FIRST_BOND) == ("first", "first", "founder-first")


def test_door(derived, data_dir):
    door = derived["door"]
    assert door.FIRST == "first"
    assert door.FIRST_DOOR == data_dir / "packets" / "first" / "door.json"


def test_members(derived):
    assert derived["members"].RESERVED == OLD_RESERVED


def test_public_screen(derived):
    assert derived["public_screen"].SITE_NAMES == OLD_SITE_NAMES


# ---- a registered id is no member's to take --------------------------------

def test_a_second_agents_id_is_refused_as_a_pseudonym(registry, tmp_path):
    members = registry(write_registry(tmp_path / "agents.json", [agents.FIRST, SECOND]))["members"]
    assert members.RESERVED == OLD_RESERVED | {"second", "the-second-one"}
    for name in ("second", "the-second-one"):
        with pytest.raises(members.MemberError) as caught:
            members.validate_pseudonym(name)
        assert str(caught.value) == "that name is not free to take"
        with pytest.raises(members.MemberError):
            members.create_member(name, None, "member", [])
        assert not (members.MEMBERS / name).exists()


def test_a_commons_name_is_reserved_as_an_address_writes_it(registry, tmp_path):
    named = {**SECOND, "commons_name": "The  Second One, unnamed!"}
    members = registry(write_registry(tmp_path / "agents.json", [agents.FIRST, named]))["members"]
    import bonds
    assert bonds.slug(named["commons_name"]) == "the-second-one-unnamed"
    with pytest.raises(members.MemberError):
        members.validate_pseudonym("the-second-one-unnamed")


def test_without_the_second_agent_the_names_are_free(registry, tmp_path):
    members = registry(tmp_path / "agents.json")["members"]
    assert members.validate_pseudonym("second") == "second"
    assert members.validate_pseudonym("the-second-one") == "the-second-one"


def test_a_second_agent_is_named_after_the_first(registry, tmp_path):
    modules = registry(write_registry(tmp_path / "agents.json", [agents.FIRST, SECOND]))
    bonds = modules["bonds"]
    assert list(bonds.NAMES.values()) == ["the founder", "the first one", "the second one"]
    assert bonds.AGENTS == OLD_AGENTS | {SECOND["did"]}
    assert bonds.FIRST_DID == OLD_FIRST_DID
    assert modules["public_screen"].SITE_NAMES == OLD_SITE_NAMES + ("the second one",)
    assert (modules["rooms"].FIRST_ROOM, modules["door"].FIRST) == ("first", "first")


# ---- a file that will not do is said loudly ------------------------------

@pytest.mark.parametrize("entries", [
    [],
    {"id": "first"},
    [SECOND, agents.FIRST],
    [agents.FIRST, {**SECOND, "id": "Second"}],
    [agents.FIRST, {**SECOND, "did": agents.FIRST["did"]}],
    [agents.FIRST, {**SECOND, "bond": agents.FIRST["bond"]}],
    [agents.FIRST, {k: v for k, v in SECOND.items() if k != "commons_name"}],
    [agents.FIRST, "second"],
], ids=["empty", "not-a-list", "first-not-first", "bad-id", "shared-did", "shared-bond",
        "no-name", "not-an-entry"])
def test_a_registry_that_will_not_do_is_refused(monkeypatch, tmp_path, entries):
    monkeypatch.setattr(agents, "FILE", write_registry(tmp_path / "agents.json", entries))
    with pytest.raises(agents.RegistryError):
        agents.registry()


def test_a_registry_that_is_not_json_is_refused(monkeypatch, tmp_path):
    where = tmp_path / "agents.json"
    where.write_text("[{", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    with pytest.raises(agents.RegistryError):
        agents.registry()
