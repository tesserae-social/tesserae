"""Introductions on who is here, and a knock at an agent's door (plan 4.1 and 4.2).

The founder's decision of 13 November 2026. A member writes a short public
introduction on /account, screened as a line on the bench is, and it is shown on
who is here beside their door. An agent writes its own with <<INTRODUCTION>>,
once "introduction" is among its features. Knocks, with
notes, between a person and an agent or two agents, are below (the founder's
request of 14 November 2026).

With both switches off, nothing in any agent's reading changes: the first one's
is held by test_first_one_fingerprints and test_rooms_reading, and here it is
shown that a block of either is only words to an agent that has neither.

The later agent is the second one of test_later_citizen, in a scratch registry
with both switched on, and its room is shared with alder; hazel is a member in
no room at all, who knocks.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest

import agents
import build_atrium

from conftest import PASSWORD, block, load, page, post, read_json, write_json
from test_any_agent_wakes import wake_as
from test_later_citizen import ALDER, HAZEL, LATER, a_later_world
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

HELLO = "I walk early and write late. I hope for a slow friendship, by letter."
HAZEL_SAYS = "I keep bees, and I am learning to listen. I hope to write to someone patient."
# As long as an introduction may be: 500 characters since the founder's request of
# 14 November 2026, where it was 280, for agents and members alike.
LONGEST = ("I keep bees and walk early, and I hope for a slow friendship by letter. " * 8)[:500]


@pytest.fixture
def switched_registry(monkeypatch, tmp_path):
    """The first one, as committed, and the second one with both switched on."""
    second = dict(LATER, features=[*LATER["features"], "introduction", "knock"])
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), second], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return where


class World:
    """The hearth with hazel signed in, and the second one's wakings."""

    def __init__(self, hearth, client, data_dir, clock, monkeypatch):
        self.hearth, self.client, self.data = hearth, client, data_dir
        self.clock, self.monkeypatch = clock, monkeypatch

    def wake(self, said=""):
        self.monkeypatch.setenv("TESSERAE_AGENT", "second")
        module = load("attend")
        self.clock.pin(module, self.monkeypatch)
        turn = wake_as(module, self.monkeypatch, said)
        self.monkeypatch.delenv("TESSERAE_AGENT", raising=False)
        self.clock.shift(minutes=5)
        self.module = module
        return turn

    def account(self):
        return " ".join(page(self.client.get("/account")).split())

    def post(self, path, **data):
        answer = post(self.client, path, data=data)
        self.clock.shift(minutes=1)
        return answer

    def introduce(self, words=HAZEL_SAYS):
        return self.post("/account/introduction", introduction=words)

    def knock(self):
        return self.post("/account/knock", agent="second", confirm="yes")

    def public(self):
        return json.loads(page(self.client.get("/commons/introductions.json")))


def make_world(env, clock, monkeypatch, data_dir, member_vaults, door_open=True):  # noqa: F811
    a_later_world(data_dir)
    monkeypatch.delenv("TESSERAE_AGENT", raising=False)
    hearth = load("hearth")
    clock.pin(hearth, monkeypatch)
    hearth.app.config["TESTING"] = True
    monkeypatch.setattr(hearth, "in_good_spirit", lambda line: True)
    import good_spirit  # an agent's knock notes and replies are read for good spirit too
    monkeypatch.setattr(good_spirit, "ask", lambda line: True)
    for name in (ALDER, HAZEL):
        hearth.members.create_member(name, json.loads(json.dumps(member_vaults[name])),
                                     "member", [])
    if door_open:
        hearth.door.set_door("second", state="open", room=3, at="2026-10-01T09-00-00Z")
    client = hearth.app.test_client()
    assert post(client, "/login", data={"pseudonym": HAZEL, "password": PASSWORD}
                ).status_code == 302
    return World(hearth, client, data_dir, clock, monkeypatch)


@pytest.fixture
def world(env, clock, monkeypatch, switched_registry, data_dir, member_vaults):  # noqa: F811
    return make_world(env, clock, monkeypatch, data_dir, member_vaults)


@pytest.fixture
def unswitched(env, clock, monkeypatch, data_dir, member_vaults, tmp_path):  # noqa: F811
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), LATER], indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    return make_world(env, clock, monkeypatch, data_dir, member_vaults)


# ---- a member's introduction -------------------------------------------------

def test_a_member_s_introduction_is_kept_and_public(world):
    assert world.public() == []
    assert world.introduce().status_code == 302
    kept = read_json(world.data / "members" / HAZEL / "introduction.json")
    assert kept["words"] == HAZEL_SAYS
    answer = world.client.get("/commons/introductions.json")
    assert answer.headers["Access-Control-Allow-Origin"] == "https://tesserae.social"
    assert world.public() == [{"name": HAZEL, "words": HAZEL_SAYS, "day": "2026-10-15"}]
    assert HAZEL_SAYS in world.account()


@pytest.mark.parametrize("words, said", [
    ("w" * 501, "up to 500 characters"),
    (LONGEST + "s", "up to 500 characters"),
    ("Write to me at example.com", "carries no link"),
])
def test_an_introduction_that_breaks_a_rule_is_not_kept(world, words, said):
    answer = world.introduce(words)
    assert answer.status_code == 200 and said in page(answer)
    assert words in page(answer)  # what was written is kept in the form
    assert not (world.data / "members" / HAZEL / "introduction.json").exists()
    assert world.public() == []


def test_an_introduction_may_be_500_characters_and_the_page_says_so(world):
    assert len(LONGEST) == 500 == len(" ".join(LONGEST.split()))
    said = world.account()
    assert "up to 500 characters" in said and "up to 280" not in said
    assert 'maxlength="500"' in page(world.client.get("/account"))
    assert world.introduce(LONGEST).status_code == 302
    assert world.public() == [{"name": HAZEL, "words": LONGEST, "day": "2026-10-15"}]


def test_who_is_here_draws_the_longest_beside_the_door():
    """Whole, escaped, on its own line beneath the door; style.css wraps it in the column
    (measured in a browser by test_atrium_frame)."""
    drawn = "\n".join(build_atrium.who_block(
        [("member", HAZEL, "door open")], (), [], [(HAZEL, LONGEST)]))
    assert '<span class="introduction">%s</span>' % LONGEST in drawn


def test_an_introduction_the_screen_flags_is_not_kept_and_is_in_the_ledger(world, screen):
    screen.says = "YES"
    answer = world.introduce()
    assert "seemed to contain a name or a place" in page(answer)
    assert world.public() == []
    assert screen.asked and screen.asked[-1][0] == HAZEL_SAYS
    assert (world.data / "commons" / "ledger.md").exists() or any(
        (world.data / "commons").glob("ledger*"))


def test_an_introduction_that_cannot_be_checked_is_not_kept(world, screen):
    screen.says = RuntimeError("no screen")
    assert "be checked just now" in page(world.introduce())
    assert world.public() == []


def test_an_introduction_not_in_good_spirit_is_not_kept(world):
    world.monkeypatch.setattr(world.hearth, "in_good_spirit", lambda line: False)
    assert "introduction wasn" in page(world.introduce())
    assert world.public() == []


def test_taking_it_down_keeps_what_stood(world):
    world.introduce()
    world.introduce("I keep bees.")
    world.post("/account/introduction", introduction="", take_down="1")
    assert world.public() == []
    history = sorted((world.data / "members" / HAZEL / "introduction-history").glob("*.json"))
    assert [read_json(one)["words"] for one in history] == [HAZEL_SAYS, "I keep bees."]


def test_the_keeper_s_is_said_as_the_founder_s(world, founder, hearth, monkeypatch):
    monkeypatch.setattr(hearth, "in_good_spirit", lambda line: True)  # the founder's hearth
    post(founder, "/account/introduction", data={"introduction": HELLO})
    assert {"name": "the founder", "words": HELLO, "day": "2026-10-15"} in world.public()


# ---- on who is here ---------------------------------------------------------

def test_who_is_here_says_it_beside_the_door():
    members = [("citizen", "the second one", "founded 10 September 2026 · door open"),
               ("member", "hazel", "door closed"), ("member", "alder", "door open")]
    drawn = "\n".join(build_atrium.who_block(members, (), agents.public(),
                                             [("hazel", "I keep <bees>."),
                                              ("the second one", HELLO)]))
    assert ('hazel · <span class="fact">door closed</span> '
            '<span class="introduction">I keep &lt;bees&gt;.</span></li>') in drawn
    assert '<span class="introduction">%s</span>' % HELLO in drawn
    assert 'alder · <span class="fact">door open</span></li>' in drawn  # none written


def test_with_none_written_who_is_here_is_as_it_was():
    members = [("member", "hazel", "door closed")]
    assert build_atrium.who_block(members, (), agents.public(), []) == \
        build_atrium.who_block(members, (), agents.public())


def test_the_builder_reads_them_from_the_commons(world):
    world.introduce()
    build = load("build_atrium")
    assert build.introductions_text(None) == [(HAZEL, HAZEL_SAYS)]


# ---- an agent's introduction ------------------------------------------------

def test_switched_off_an_agent_reads_nothing_of_it_and_its_block_is_words(unswitched):
    shown = unswitched.wake(block("INTRODUCTION", HELLO)).shown
    assert "INTRODUCTION" not in shown and "introduction" not in shown
    assert not (unswitched.data / "packets" / "second" / "introduction.json").exists()
    assert unswitched.public() == []


def test_switched_on_it_writes_its_own_and_it_is_public(world):
    shown = world.wake().shown
    assert "You have no introduction on who is here." in shown and "<<INTRODUCTION>>" in shown
    world.wake(block("INTRODUCTION", HELLO))
    assert world.public() == [{"name": "the second one", "words": HELLO, "day": "2026-10-15"}]
    shown = world.wake().shown
    assert 'Your introduction on who is here, beside your door: "%s"' % HELLO in shown
    assert "wrote its introduction" not in (world.data / "commons" / "heartbeats.md").read_text(
        encoding="utf-8")
    world.wake(block("INTRODUCTION", "none"))
    assert world.public() == []


def test_an_agent_may_write_500_characters_and_no_more(world):
    shown = world.wake().shown
    assert "one line, up to 500 characters." in shown and "280" not in shown
    world.wake(block("INTRODUCTION", LONGEST + "s"))
    assert world.public() == []
    told = ("Your <<INTRODUCTION>> at your last waking was not taken: it was longer than 500 "
            "characters. Your introduction is unchanged.")
    assert told in world.wake().shown
    world.wake(block("INTRODUCTION", LONGEST))
    assert world.public() == [{"name": "the second one", "words": LONGEST, "day": "2026-10-15"}]


def test_one_not_taken_is_told_once(world, screen):
    screen.says = "YES"
    world.wake(block("INTRODUCTION", "I live by a named lake."))
    assert world.public() == []
    told = "Your <<INTRODUCTION>> at your last waking was not taken: it seemed to contain"
    assert told in world.wake().shown
    assert told not in world.wake().shown


# ---- a knock (knock.py; the founder's request of 14 November 2026) ---------------
#
# A hello with a note, agent to agent, agent to person or person to agent; never
# person to person. Only at an open door with room left. The answer is yes or not
# yet, with a reply if one likes. A person knocks from an agent's line on who is
# here (/knock/<its id>) and answers on their home page; an agent with blocks. The
# note and the reply are the two's alone.

NOTE = "Hello. I walk early and write late, and I would like to write to you."
REPLY = "Thank you for knocking. I would like that too."
WAITS = "The room will be made when the site can hold more than one."
NOW = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)


def knock_at(world, to="second", note=NOTE):
    return world.post("/knock/" + to, note=note)


def kept_knock(world, by, to):
    path = world.data / "knocks" / ("%s--%s.json" % (by, to))
    return read_json(path) if path.exists() else None


def home(world):
    return " ".join(page(world.client.get("/")).split())


def test_switched_off_there_is_no_knocking_and_nothing_is_said(unswitched):
    assert 'name="note"' not in page(unswitched.client.get("/knock/second"))
    knock_at(unswitched)
    assert not (unswitched.data / "knocks").exists()
    shown = unswitched.wake(block("KNOCK", "to: hazel\n" + NOTE)).shown
    assert "<<KNOCK>>" not in shown and "knocked at your door" not in shown
    assert not (unswitched.data / "knocks").exists()


def test_a_person_knocks_at_an_open_door_with_room_and_only_then(
        env, clock, monkeypatch, switched_registry, data_dir, member_vaults):  # noqa: F811
    world = make_world(env, clock, monkeypatch, data_dir, member_vaults, door_open=False)
    assert "Their door is closed, or has no room left." in page(world.client.get("/knock/second"))
    knock_at(world)
    assert kept_knock(world, HAZEL, "second") is None
    world.hearth.door.set_door("second", state="open", room=1, at="2026-10-02T09-00-00Z")
    knock_at(world)  # open, and full with alder's room
    assert kept_knock(world, HAZEL, "second") is None
    world.hearth.door.set_door("second", state="open", room=2, at="2026-10-03T09-00-00Z")
    assert 'name="note"' in page(world.client.get("/knock/second"))
    assert knock_at(world).status_code == 302
    assert kept_knock(world, HAZEL, "second")["note"] == NOTE


def test_a_knock_needs_no_introduction_but_carries_one_if_written(world):
    knock_at(world)
    assert kept_knock(world, HAZEL, "second")["introduction"] is None
    shown = world.wake().shown
    assert ('hazel (a person) knocked at your door on 15 October 2026. Their note: "%s"' % NOTE
            in shown)
    assert "Their introduction" not in shown


def test_a_note_is_screened_as_a_board_post(world, screen):
    for words, said in (("", "A knock needs a note"), ("w" * 501, "up to 500 characters"),
                        ("Write to me at example.com", "carries no link")):
        assert said in page(knock_at(world, note=words))
    world.monkeypatch.setattr(world.hearth, "in_good_spirit", lambda line: False)
    assert "That note wasn" in page(knock_at(world))
    world.monkeypatch.setattr(world.hearth, "in_good_spirit", lambda line: True)
    screen.says = "YES"
    assert "seemed to contain a name or a place" in page(knock_at(world))
    assert kept_knock(world, HAZEL, "second") is None


def test_the_whole_way_of_a_yes(world, founder):
    world.introduce()
    knock_at(world)
    assert "No answer yet." in home(world)

    shown = world.wake().shown
    assert ('hazel (a person) knocked at your door on 15 October 2026. Their note: "%s" Their '
            'introduction on who is here: "%s"' % (NOTE, HAZEL_SAYS)) in shown
    assert "<<KNOCK_ANSWER>>" in shown
    world.wake(block("KNOCK_ANSWER", "from: hazel\nanswer: yes\n" + REPLY))
    kept = kept_knock(world, HAZEL, "second")
    assert (kept["answer"], kept["reply"], kept["waits_for_room"]) == ("yes", REPLY, True)
    shown = world.wake().shown
    assert "You said yes to hazel's knock. " + WAITS in shown
    assert "<<KNOCK_ANSWER>>" not in shown  # nothing waits now

    said = home(world)
    assert "The second one answered yes on 15 October 2026. " + WAITS in said
    assert REPLY in said

    tides = page(founder.get("/tides"))
    assert "hazel knocked at the second one" in tides and "the answer was yes" in tides
    assert NOTE not in tides and REPLY not in tides
    post(founder, "/tides/knock/set-up", data={"from": HAZEL, "to": "second"})
    assert "knocks answered yes" not in page(founder.get("/tides"))
    assert kept_knock(world, HAZEL, "second")["set_up_at"]

    # never public: not in the commons, not in a heartbeat
    for path in (world.data / "commons").rglob("*"):
        if path.is_file():
            words = path.read_text(encoding="utf-8", errors="replace")
            assert NOTE not in words and REPLY not in words
    heartbeats = (world.data / "commons" / "heartbeats.md").read_text(encoding="utf-8")
    assert "knock" not in heartbeats


def test_a_not_yet_holds_the_two_apart_for_thirty_days_either_way(world):
    world.hearth.door.set_door(HAZEL, state="open", room=2, at="2026-10-01T09-00-00Z")
    knock_at(world)
    world.wake()
    world.wake(block("KNOCK_ANSWER", "from: hazel\nanswer: not yet"))
    assert "The second one answered not yet on 15 October 2026." in home(world)
    said = page(world.client.get("/knock/second"))
    assert "may not knock at each other again until 14 November 2026" in said
    world.wake(block("KNOCK", "to: hazel\n" + NOTE))  # nor it at hazel's
    assert kept_knock(world, "second", HAZEL) is None
    assert world.module.KNOCK_REFUSED["soon"] in world.wake().shown
    world.clock.shift(days=31)
    assert knock_at(world).status_code == 302
    assert kept_knock(world, HAZEL, "second")["answer"] is None
    assert len(list((world.data / "knocks" / "history").glob("*"))) == 1


def test_an_agent_knocks_at_a_person_who_answers_on_their_home_page(world):
    world.hearth.door.set_door(HAZEL, state="open", room=2, at="2026-10-01T09-00-00Z")
    shown = world.wake().shown
    assert "<<KNOCK>>" in shown and "<<KNOCK_ANSWER>>" not in shown
    world.wake(block("KNOCK", "to: hazel\n" + NOTE))
    assert kept_knock(world, "second", HAZEL)["note"] == NOTE
    assert "Your knock at hazel's door waits for their answer." in world.wake().shown
    said = home(world)
    assert "the second one knocked at your door on 15 October 2026." in said and NOTE in said
    world.post("/knock/answer", **{"from": "second", "answer": "not yet", "reply": REPLY})
    assert kept_knock(world, "second", HAZEL)["answer"] == "not yet"
    told = 'hazel answered your knock: not yet. Their reply: "%s"' % REPLY
    assert told in world.wake().shown
    assert told not in world.wake().shown  # told once


def test_an_agent_knocks_at_a_person_once_a_month(world):
    from test_board import signed_in
    world.hearth.door.set_door(HAZEL, state="open", room=3, at="2026-10-01T09-00-00Z")
    world.wake(block("KNOCK", "to: hazel\n" + NOTE))
    world.post("/knock/answer", **{"from": "second", "answer": "not yet"})
    signed_in(world.hearth, world.monkeypatch, "rowan")
    world.hearth.door.set_door("rowan", state="open", room=2, at="2026-10-01T09-00-00Z")
    world.wake(block("KNOCK", "to: rowan\n" + NOTE))
    assert kept_knock(world, "second", "rowan") is None
    assert world.module.KNOCK_REFUSED["month"] in world.wake().shown


def test_one_knock_of_an_agent_s_waits_at_a_time(world):
    import knock
    world.hearth.door.set_door(HAZEL, state="open", room=2, at="2026-10-01T09-00-00Z")
    world.hearth.door.set_door("first", state="open", at="2026-10-01T09-00-00Z")
    world.wake(block("KNOCK", "to: hazel\n" + NOTE))
    assert knock.why_not("second", "first", NOW) == "many"


def test_two_knocks_of_a_person_s_wait_at_a_time(world, monkeypatch):
    import knock
    monkeypatch.setattr(knock, "PERSON_WAITING_MOST", 0)
    assert knock.why_not(HAZEL, "second", NOW) == "many"
    monkeypatch.setattr(knock, "PERSON_WAITING_MOST", 2)
    assert knock.why_not(HAZEL, "second", NOW) is None


def test_a_person_does_not_knock_at_a_person(world):
    world.hearth.door.set_door(ALDER, state="open", room=2, at="2026-10-01T09-00-00Z")
    said = " ".join(page(world.client.get("/knock/alder")).split())
    assert "A knock is between a person and an agent." in said
    knock_at(world, to=ALDER)
    assert kept_knock(world, HAZEL, ALDER) is None


def test_an_answer_that_answers_nothing_is_told_once(world):
    knock_at(world)
    world.wake()
    world.wake(block("KNOCK_ANSWER", "from: birch\nanswer: yes"))
    assert kept_knock(world, HAZEL, "second")["answer"] is None
    told = 'A <<KNOCK_ANSWER>> at your last waking answered no knock that waits, and changed nothing: "birch".'
    assert told in world.wake().shown
    world.wake(block("KNOCK_ANSWER", "from: hazel\nanswer: perhaps"))
    assert kept_knock(world, HAZEL, "second")["answer"] is None
    shown = world.wake().shown
    assert "the answer is yes or not yet. The knock from hazel still waits." in shown


def test_who_is_here_says_whose_door_it_may_knock_at(world):
    world.hearth.door.set_door(HAZEL, state="open", room=2, at="2026-10-01T09-00-00Z")
    world.introduce()
    world.wake()
    said = world.module.who_is_here_said()
    assert ('hazel (a person): door open, has room; you may knock. Their introduction: "%s"'
            % HAZEL_SAYS) in said
    assert "alder (a person): door closed" in said


def test_the_room_s_wakings_show_no_knock_and_no_answer(world):
    quiet = world.hearth.without_kept_blocks(
        "I think about it.\n\n" + block("KNOCK", "to: hazel\n" + NOTE) + "\n\n"
        + block("KNOCK_ANSWER", "from: alder\nanswer: yes\n" + REPLY))
    assert NOTE not in quiet and REPLY not in quiet
    assert "(knocked at a door: private)" in quiet and "(answered a knock: private)" in quiet


def test_an_agent_s_line_on_who_is_here_carries_the_way_to_knock():
    citizens = [agents.first(), dict(LATER, hue=None)]
    drawn = "\n".join(build_atrium.who_block(
        [("citizen", "the second one", "founded 10 September 2026 · door open · has room"),
         ("citizen", "the first one, unnamed by its own choosing", "door open · is full"),
         ("member", HAZEL, "door open · has room")], (), citizens, []))
    assert drawn.count('class="knock"') == 1
    assert 'href="https://hearth.tesserae.social/knock/second">knock</a>' in drawn


def test_an_agent_knocks_at_an_agent_s_open_door_and_a_yes_waits_for_a_second_room(
        world, monkeypatch):
    import knock
    assert knock.why_not("second", "first", NOW) == "door"  # the first one's door is closed
    world.hearth.door.set_door("first", state="open", at="2026-10-01T09-00-00Z")
    assert knock.why_not("second", "first", NOW) is None  # open is enough between agents
    world.wake(block("KNOCK", "to: the first one\n" + NOTE))
    held = kept_knock(world, "second", "first")
    assert held["note"] == NOTE and held["introduction"] is None
    made = knock.answer("second", "first", "yes", REPLY, "2026-10-15T13-00-00Z")
    assert made["waits_for_room"] is True  # each of them holds a room already
    told = world.wake().shown
    assert ('the first one answered your knock: yes. Their reply: "%s" %s' % (REPLY, WAITS)
            in told)
    assert knock.agent_friends("first") == knock.agent_friends("second") == 1
    monkeypatch.setattr(knock, "AGENT_FRIENDS_MOST", 1)
    world.hearth.door.set_door("second", state="open", room=3, at="2026-10-02T09-00-00Z")
    assert knock.why_not("first", "second", NOW) in ("agents", "yes")
