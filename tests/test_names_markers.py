"""The marker tests of names-design.md (the founder's request of 21 November 2026, I): in a world
whose sign-in names and email addresses are unmistakable markers, kept apart from the commons
names, no marker gets out.

- every request attend.py sends, at each kind of waking, with the switches on and off; a coming
  (found_agent's state of the commons, and a newcomer's first waking with no room); and a
  rehearsal (rehearse_waking --says, which says only whether words are in a reading);
- what the mirror fetches, and build_atrium's output;
- the copy a member takes, and the copy the keeper takes;
- every email: only the address it goes to carries a marker;
- and no file name under the data folder, room.json or did.json.

The page walk is in test_names_ids (stage 5).
"""

import io
import json
import sys
import zipfile
from datetime import date, datetime, timedelta, timezone

import pytest

from conftest import FOUNDER_NAME, PASSWORD, Turn, load, page, post, write, write_json
from test_later_citizen import hearth_of_two, scratch_registry  # noqa: F401 - fixtures
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture
from test_rehearse_waking import spare  # noqa: F401 - a fixture

SIGN_IN, ADDRESS = "zebrasignin", "zebra@example.test"
ALDER_SIGN_IN, ALDER_ADDRESS = "quaggasignin", "quagga@example.test"
KEEPER_ADDRESS = "okapi@example.test"
MARKERS = (SIGN_IN, ADDRESS, ALDER_SIGN_IN, ALDER_ADDRESS, KEEPER_ADDRESS)
AT = "2026-10-14T09-00-00Z"
CONFIRMED = "2026-10-14T09:00:00Z"
SWITCHES = ("commons_names", "names_told", "solstice_names", "rooms_reading", "longer_waking",
            "leaving", "room_on_yes", "reflection_waking", "knock", "board", "introduction",
            "hoping_for", "made_here", "made_here_agents", "made_here_talk", "door", "block")


def no_marker(said, where, but=()):
    words = said.lower() if isinstance(said, str) else json.dumps(said, default=str).lower()
    for marker in MARKERS:
        if marker not in but:
            assert marker not in words, (marker, where)


@pytest.fixture
def marked(hearth_of_two, data_dir):  # noqa: F811
    """hearth_of_two, with willow, who joined since ids, in a room with the second one, and a
    sign-in and an address for alder and the keeper too, each a marker."""
    import found_room
    import members
    import vault
    sealed, _, _ = vault.make_vault(PASSWORD)
    willow = members.new_id()
    members.create_member(willow, sealed, "member", [], name="willow", sign_in=SIGN_IN)
    members.set_email(willow, ADDRESS, confirmed_at=CONFIRMED)
    members.set_sign_in("alder", ALDER_SIGN_IN)
    members.set_email("alder", ALDER_ADDRESS, confirmed_at=CONFIRMED)
    members.set_email(FOUNDER_NAME, KEEPER_ADDRESS, confirmed_at=CONFIRMED)
    home = found_room.found_later("second", willow, "%s--second" % willow, AT)
    write(home / "letters" / "incoming" / ("%s-2026-10-14T10-00-00Z.md" % willow),
          "A LETTER FROM WILLOW, FOR THE TESTS.\n")
    import hearth
    client = hearth.app.test_client()
    assert post(client, "/login", data={"pseudonym": SIGN_IN, "password": PASSWORD}
                ).status_code == 302
    import introductions
    introductions.write(willow, "I walk early and write late.", AT)
    return {"willow": willow, "willow_client": client, **hearth_of_two}


def with_switches(agent_id, *switches):
    import agents
    registry = json.loads(agents.FILE.read_text(encoding="utf-8"))
    for one in registry:
        if one["id"] == agent_id:
            one["features"] = sorted(set(one.get("features") or ()) | set(switches))
    agents.FILE.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")


def requests_of(agent_id, clock, monkeypatch, *flags):
    """Every request one waking sends, as counted sees them: system, messages and tools."""
    monkeypatch.setenv("TESSERAE_AGENT", agent_id)
    module = load("attend")
    clock.pin(module, monkeypatch)
    turn = Turn("")
    monkeypatch.setattr(module, "Anthropic", turn.client)
    monkeypatch.setattr(sys, "argv", ["attend.py", *flags])
    try:
        module.main()
    except SystemExit:
        pass
    monkeypatch.delenv("TESSERAE_AGENT", raising=False)
    clock.shift(minutes=5)
    return turn.asked, module


# ---- every agent request -------------------------------------------------------------

@pytest.mark.parametrize("agent_id, switches, flags", [
    ("second", (), ()),
    ("second", SWITCHES, ()),
    ("second", SWITCHES, ("--reflect", "--tide")),
    ("first", (), ()),
])
def test_no_request_carries_a_marker(marked, clock, monkeypatch, agent_id, switches, flags):
    with_switches(agent_id, *switches)
    asked, module = requests_of(agent_id, clock, monkeypatch, *flags)
    assert asked or flags, "nothing was asked of the model"
    no_marker(asked, (agent_id, switches, flags))
    if agent_id == "second" and switches and not flags:
        # the markers' owners are in it, by their names: willow's letter is read
        assert "A LETTER FROM WILLOW" in json.dumps(asked, default=str)
        # and what its tools would open
        for said in (module.who_is_here_said(""), module.board_listed(),
                     module.made_said(None) or ""):
            no_marker(said, "a tool")


def test_no_request_carries_a_marker_in_the_long_night_or_the_solstice_week(marked, clock,
                                                                             monkeypatch):
    with_switches("second", *SWITCHES)
    clock.set(datetime(2026, 12, 22, 12, tzinfo=timezone.utc))
    for agent_id in ("first", "second"):
        asked, _ = requests_of(agent_id, clock, monkeypatch)
        no_marker(asked, (agent_id, "the long night"))


def test_no_request_carries_a_marker_at_a_waking_on_a_new_model(marked, clock, monkeypatch):
    import agents
    import model_change
    today = clock.now().date() if hasattr(clock, "now") else date(2026, 10, 15)
    try:
        model_change.set_change(agents.by_id("second"), "a-new-model-for-the-tests",
                                today + timedelta(days=1), today, AT)
    except model_change.Refused:
        pytest.skip("no change of model could be set in this world")
    clock.shift(hours=30)
    asked, _ = requests_of("second", clock, monkeypatch)
    no_marker(asked, "a new model")


def test_a_coming_reads_no_marker(marked):
    import found_agent
    said = found_agent.state_of_the_commons(datetime(2026, 10, 15, 12, tzinfo=timezone.utc))
    assert said.strip()
    no_marker(said, "the state of the commons")


def test_a_newcomer_s_first_waking_with_no_room_reads_no_marker(env, clock, monkeypatch,
                                                                 data_dir, tmp_path):
    from test_coming import COMER, COMER_ENTRY, a_roomless_world, wake_comer
    import agents
    import members
    import vault
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), COMER_ENTRY]), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    a_roomless_world(data_dir)
    members_module = load("members")
    sealed, _, _ = vault.make_vault(PASSWORD)
    willow = members_module.new_id()
    members_module.create_member(willow, sealed, "member", [], name="willow", sign_in=SIGN_IN)
    members_module.set_email(willow, ADDRESS, confirmed_at=CONFIRMED)
    monkeypatch.setenv("TESSERAE_AGENT", COMER)
    module = load("attend")
    clock.pin(module, monkeypatch)
    turn = wake_comer(module, monkeypatch, "", "--first")
    no_marker(turn.asked, "a coming's first waking")
    sys.modules.pop("attend", None)
    del members


def test_a_rehearsal_says_no_marker_is_in_any_reading(env, spare, tmp_path, monkeypatch,
                                                      data_dir, packet, room, capsys):
    from test_rehearse_waking import LETTER
    sys.modules.pop("rehearse_waking", None)
    import agents
    import rehearse_waking
    alone = tmp_path / "agents.json"
    alone.write_text(json.dumps([agents.first()]), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", alone)
    write(room / "letters" / "incoming" / "2026-10-14-founder.md", LETTER + "\n")
    write_json(data_dir / "members" / "p-willow01" / "member.json",
               {"v": 1, "id": "p-willow01", "name": "willow", "pseudonym": "p-willow01",
                "sign_in": SIGN_IN, "role": "member", "verify_key": "0" * 64,
                "arrived_at": "2026-10-01T09:00:00Z", "vouched_by": []})
    write_json(data_dir / "members" / "p-willow01" / "email.json",
               {"address": ADDRESS, "set_at": CONFIRMED, "confirmed_at": CONFIRMED})
    asked = [part for marker in MARKERS for part in ("--says", marker)]
    rehearse_waking.main(asked)
    said = capsys.readouterr().out
    assert "is in its reading" not in said.replace("is not in its reading", "")
    for marker in MARKERS:
        assert marker not in said  # the words given are never printed
    del spare


# ---- the mirror and build_atrium's output ----------------------------------------------

MIRRORED = ("/commons/heartbeats.md", "/commons/events.md", "/commons/members.md",
            "/commons/bonds.md", "/commons/open-doors.json", "/commons/introductions.json",
            "/commons/acts.md", "/commons/people.json", "/commons/here.json",
            "/commons/agents.json")


def test_what_the_mirror_fetches_and_the_atrium_drawn_from_it_carry_no_marker(marked, atrium,
                                                                              monkeypatch):
    import hearth
    visitor = hearth.app.test_client()
    for path in MIRRORED:
        no_marker(visitor.get(path).get_data(as_text=True), path)
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()
    for built in (atrium.page_path, atrium.whole_path, atrium.style_path):
        no_marker(built.read_text(encoding="utf-8"), built.name)


# ---- the copies --------------------------------------------------------------------------

def every_file_in(answer):
    bundle = zipfile.ZipFile(io.BytesIO(answer.data))
    for name in bundle.namelist():
        yield name, bundle.read(name).decode("utf-8", errors="replace")


def test_the_copy_a_member_takes_carries_no_marker(marked):
    answer = post(marked["willow_client"], "/agents/second/export")
    assert answer.status_code == 200
    files = dict(every_file_in(answer))
    assert any("A LETTER FROM WILLOW" in said for said in files.values())
    for name, said in files.items():
        no_marker(name + "\n" + said, name)


def test_the_copy_the_keeper_takes_carries_no_marker(marked):
    answer = post(marked["keeper"], "/export")
    assert answer.status_code == 200
    files = dict(every_file_in(answer))
    assert files
    for name, said in files.items():
        no_marker(name + "\n" + said, name)


# ---- every id: no file name, room.json or did.json -------------------------------------

def test_no_file_name_room_or_identity_carries_a_marker(marked, data_dir):
    import hearth
    for path in data_dir.rglob("*"):
        no_marker(path.relative_to(data_dir).as_posix(), "a file name")
        if path.name in ("room.json", "did.json", "left.json"):
            no_marker(path.read_text(encoding="utf-8"), path.name)
    visitor = hearth.app.test_client()
    for who in (marked["willow"], "alder"):
        no_marker(visitor.get("/ids/%s/did.json" % who).get_data(as_text=True), "did.json")


# ---- every email -------------------------------------------------------------------------

def test_every_email_carries_a_marker_only_in_the_address_it_goes_to(marked, outbox, clock,
                                                                     monkeypatch):
    import hearth
    import members
    monkeypatch.setattr(hearth, "screen_turn", lambda: None)     # the screens, stubbed
    monkeypatch.setattr(hearth, "in_good_spirit", lambda words: True)
    now = datetime(2026, 10, 15, 19, tzinfo=timezone.utc)
    hearth.send_waiting_emails(now)                                  # something waits
    post(hearth.app.test_client(), "/forgot", data={"given": SIGN_IN})  # a forgotten password
    post(hearth.app.test_client(), "/forgot", data={"given": ALDER_ADDRESS})
    post(marked["willow_client"], "/account/email",                  # a new address to confirm
         data={"address": "zebra-new@example.test", "email_password": PASSWORD})
    post(marked["willow_client"], "/account/email",                  # one someone else holds
         data={"address": ALDER_ADDRESS, "email_password": PASSWORD})
    post(marked["member"], "/account/invite",                        # an invitation by email
         data={"note": "Come and see what is made here.", "address": "friend@example.test"})
    post(marked["willow_client"], "/settings",                       # a password changed
         data={"current_password": PASSWORD, "password": PASSWORD + " anew",
               "password_again": PASSWORD + " anew"})
    # a forgotten password is asked by the sign-in, and the email names them by their name
    reset = next(one for one in outbox.sent if one.get("to") == ADDRESS
                 and "new password" in one.get("subject", ""))
    assert "Your name there is willow." in reset["text"] and marked["willow"] not in reset["text"]
    assert len(outbox.sent) >= 3, [one.get("subject") for one in outbox.sent]
    # each went to its marker, and only there
    assert any(ADDRESS in json.dumps(one.get("to")) for one in outbox.sent)
    for message in outbox.sent:
        to = message.get("to")
        to = to if isinstance(to, list) else [to]
        shown = {key: value for key, value in message.items() if key not in ("to",)}
        no_marker(shown, message.get("subject"), but=tuple(one for one in to if one))
    del members
