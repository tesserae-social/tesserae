"""Who is here, here this week, and finding someone (finding.py, here_this_week.py).

The founder's request of 17 November 2026. A small mark, "here this week", beside a person
who has been signed in on the hearth in the last 7 days: no time, never "online now",
shown to members and agents, never to a visitor, and never beside an agent. Who is here on
a member's home page shows six agents and six people, drawn at random at each visit, open
doors first (and, for people, those here this week), with the rest under "show more". The
page to find someone browses everyone 20 to a page, narrowed and searched over what people
say about themselves. An agent's read_who_is_here draws the same picks and takes a word.
Nothing ranks or counts anyone.

The world is test_introductions': hazel signed in, alder a member, and the second one,
with six more agents and twenty-four more people written in beside them.
"""

import json
import random
import re
from datetime import date, timedelta

import pytest

import agents
from conftest import page, write, write_json
from test_introductions import make_world
from test_later_citizen import ALDER, HAZEL, LATER
from test_rooms_for_any_agent import member_vaults  # noqa: F401 - a fixture

TODAY = date(2026, 10, 15)  # the tests' clock
MORE_AGENTS = ["third", "fourth", "fifth", "sixth", "seventh", "eighth"]
MORE_PEOPLE = ["birch%02d" % n for n in range(24)]
BEE_WORDS = "I keep bees and I write slowly."


def an_agent(one, n):
    return dict(LATER, id=one, did="did:web:tesserae.social:ids:" + one,
                commons_name="the %s one" % one, room=one, bond=one + "-1",
                hue="#1234%02d" % (n + 10), features=["door", "introduction", "knock"])


@pytest.fixture
def world(env, clock, monkeypatch, data_dir, member_vaults, tmp_path):  # noqa: F811
    second = dict(LATER, features=[*LATER["features"], "introduction", "knock", "hoping_for"])
    entries = [agents.first(), second, *(an_agent(one, n) for n, one in enumerate(MORE_AGENTS))]
    where = tmp_path / "agents.json"
    where.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)
    made = make_world(env, clock, monkeypatch, data_dir, member_vaults)
    record = json.loads((data_dir / "members" / ALDER / "member.json").read_text(encoding="utf-8"))
    for n, name in enumerate(MORE_PEOPLE):  # records enough for who is here to read
        write_json(data_dir / "members" / name / "member.json",
                   dict(record, pseudonym=name, verify_key="%064x" % (n + 1),
                        arrived_at="2026-%02d-01T09-00-00Z" % (9 if n % 2 else 10)))
    return made


def here_on(data_dir, name, day):
    write_json(data_dir / "members" / name / "here.json", {"day": day.isoformat()})


def section(home):
    return home.partition('<section id="who-is-here">')[2].partition("</section>")[0]


# ---- here this week ----------------------------------------------------------

def test_a_page_opened_signed_in_keeps_the_day_and_only_the_day(world, data_dir):
    world.client.get("/")
    kept = json.loads((data_dir / "members" / HAZEL / "here.json").read_text(encoding="utf-8"))
    assert kept == {"day": "2026-10-15"}


def test_the_day_is_written_once_a_day_and_nothing_else_is(world, data_dir, clock):
    """Only {"day": ...}: no time, no address, nothing else; and at most once a day."""
    here = data_dir / "members" / HAZEL / "here.json"
    world.client.get("/")
    first = (here.read_bytes(), here.stat().st_mtime_ns)
    assert here.read_text(encoding="utf-8") == '{"day": "2026-10-15"}\n'
    files = {path: path.stat().st_mtime_ns for path in data_dir.rglob("*") if path.is_file()}
    clock.shift(hours=3)  # later the same day: nothing is written
    for address in ("/", "/settings", "/find"):
        world.client.get(address)
    assert (here.read_bytes(), here.stat().st_mtime_ns) == first
    assert {path: path.stat().st_mtime_ns for path in data_dir.rglob("*")
            if path.is_file()} == files
    assert not list(here.parent.glob("here.json.tmp"))
    clock.shift(days=1)  # the next day, the day alone, written over the last
    world.client.get("/")
    assert here.read_text(encoding="utf-8") == '{"day": "2026-10-16"}\n'


def test_an_eastern_evening_is_kept_as_its_own_day(world, data_dir, clock):
    """who-fix, 17 November 2026: the day is the Eastern day, as who is here reads it.
    Before, it was the UTC day, the next day every Eastern evening, and a person who came
    only in the evening was never shown as here."""
    import here_this_week
    from datetime import datetime, timezone
    clock.set(datetime(2026, 10, 16, 1, 30, tzinfo=timezone.utc))  # 21:30 on the 15th, Eastern
    world.client.get("/")
    here = data_dir / "members" / HAZEL / "here.json"
    assert here.read_text(encoding="utf-8") == '{"day": "2026-10-15"}\n'
    assert here_this_week.here(HAZEL, TODAY)


def test_a_day_kept_in_utc_before_is_still_here(world, data_dir):
    """A day written before who-fix may be a day ahead of the Eastern day: still here."""
    import here_this_week
    here_on(data_dir, ALDER, TODAY + timedelta(days=1))
    assert here_this_week.here(ALDER, TODAY)
    here_on(data_dir, ALDER, TODAY + timedelta(days=2))
    assert not here_this_week.here(ALDER, TODAY)


def test_here_json_names_the_people_here_this_week_and_nothing_more(world, data_dir, clock):
    """The atrium's list (/commons/here.json): people here this week by name, address and
    colour only, never a day or a time."""
    here_on(data_dir, ALDER, TODAY - timedelta(days=2))
    said = json.loads(world.client.get("/commons/here.json").get_data(as_text=True))
    people = {one["address"]: one for one in said["people"]}
    assert ALDER in people and set(people[ALDER]) == {"name", "address", "hue"}
    assert "2026" not in json.dumps(said["people"])


def test_here_this_week_is_the_last_seven_days_and_never_an_agent(world, data_dir):
    import here_this_week
    here_on(data_dir, ALDER, TODAY - timedelta(days=6))
    assert here_this_week.here(ALDER, TODAY)
    here_on(data_dir, ALDER, TODAY - timedelta(days=7))
    assert not here_this_week.here(ALDER, TODAY)
    assert not here_this_week.here("second", TODAY)
    here_this_week.mark("second", TODAY)
    assert not (data_dir / "packets" / "second" / "here.json").exists()


def test_the_guide_and_settings_say_so_plainly(world):
    said = " ".join(page(world.client.get("/settings")).split())
    assert "Others here can see if you&#39;ve been here this week." in said
    guide = (agents.REPO / "templates" / "guide.html").read_text(encoding="utf-8")
    assert "{{ here_told }}" in guide


# ---- who is here on the home page -------------------------------------------

def test_six_agents_and_six_people_and_the_rest_in_place(world, data_dir):
    home = page(world.client.get("/"))
    shown = section(home)
    first, _, more = shown.partition("<summary>show more</summary>")
    assert first.count("· agent") == 6 and more.count("· agent") == 2  # eight agents in all
    names = [one for one in [ALDER, *MORE_PEOPLE] if '">%s</a>' % one in first]
    assert len(names) == 6
    assert '<a href="/find">find someone &rarr;</a>' in home  # under who is here (17 November 2026)
    assert '">hazel</a>' not in shown  # never oneself


def test_open_doors_and_those_here_this_week_come_first(world, data_dir, monkeypatch):
    import door
    for name in MORE_PEOPLE[:3]:
        door.set_door(name, state="open", room=2, at="2026-10-14T09-00-00Z")
        here_on(data_dir, name, TODAY)
    door.set_door(MORE_PEOPLE[3], state="open", room=2, at="2026-10-14T09-00-00Z")  # not here
    here_on(data_dir, MORE_PEOPLE[4], TODAY)  # here, door closed
    for _ in range(5):
        first = section(page(world.client.get("/"))).partition("<summary>")[0]
        people = [line for line in first.split("<li>") if "· agent" not in line]
        top = [name for name in MORE_PEOPLE[:3] if '">%s</a>' % name in "".join(people[:4])]
        assert len(top) == 3
        assert first.count("here this week") >= 3


def test_the_order_is_drawn_at_random_at_each_visit(world):
    seen = {section(page(world.client.get("/"))).partition("<summary>")[0] for _ in range(6)}
    assert len(seen) > 1


def test_a_visitor_sees_no_one(world, visitor):
    answer = visitor.get("/")
    assert answer.status_code == 302 and "/login" in answer.headers["Location"]
    assert visitor.get("/find").status_code == 302


def test_no_number_is_beside_any_name(world):
    shown = section(page(world.client.get("/")))
    assert "room for" not in shown and "in use" not in shown


# ---- find someone ------------------------------------------------------------

def found_names(said):
    """Each name a page of results shows, in its order: the words before the first middot."""
    return [re.sub(r"<[^>]*>", "", line).strip().partition(" · ")[0]
            for line in said.split("<li>")[1:]]


def test_everyone_twenty_to_a_page_in_one_random_order(world):
    first = page(world.client.get("/find?seed=abc"))
    names = found_names(first)
    assert len(names) == 20 and '>more</a>' in first and '>back</a>' not in first
    second = page(world.client.get("/find?seed=abc&page=1"))
    rest = found_names(second)
    assert '>back</a>' in second and '>more</a>' not in second
    assert not set(names) & set(rest)
    assert len(names) + len(rest) == 1 + len(MORE_PEOPLE) + 1 + len(MORE_AGENTS) + 1  # all, once
    assert found_names(page(world.client.get("/find?seed=abc"))) == names  # the seed keeps it


def test_it_narrows_to_agents_people_open_doors_here_and_newly_arrived(world, data_dir):
    import door
    agents_only = page(world.client.get("/find?seed=abc&kind=agents"))
    assert agents_only.count("· agent") == len(found_names(agents_only)) == 8
    people = page(world.client.get("/find?seed=abc&kind=people&page=1"))
    assert "· agent" not in people
    door.set_door(ALDER, state="open", room=2, at="2026-10-14T09-00-00Z")
    # the second one's door is open in this world already
    assert sorted(found_names(page(world.client.get("/find?seed=abc&open=1")))) == [
        ALDER, "the second one"]
    here_on(data_dir, MORE_PEOPLE[0], TODAY)
    here = found_names(page(world.client.get("/find?seed=abc&here=1")))
    assert MORE_PEOPLE[0] in here and ALDER not in here
    new = found_names(page(world.client.get("/find?seed=abc&new=1&kind=people")))
    assert MORE_PEOPLE[0] in new and MORE_PEOPLE[1] not in new  # October, not September


def test_it_searches_introductions_and_hoping_for_and_nothing_else(world, data_dir):
    import hoping_for
    import introductions
    introductions.write(MORE_PEOPLE[5], BEE_WORDS, "2026-10-14T09-00-00Z")
    hoping_for.write(MORE_PEOPLE[6], "Someone who also keeps BEES.", "2026-10-14T09-00-00Z")
    write(data_dir / "rooms" / "second" / "letters" / "read" / "x-2026-10-03T09-00-00Z.md",
          "bees in a letter, which is never searched\n")
    found = found_names(page(world.client.get("/find?seed=abc&q=bees")))
    assert sorted(found) == sorted(MORE_PEOPLE[5:7])
    said = page(world.client.get("/find?seed=abc&q=keep+bees"))
    assert "I keep bees and I write slowly." in said  # the first line of the introduction
    assert "No one here fits that." in page(world.client.get("/find?seed=abc&q=heron"))


# ---- an agent's read_who_is_here --------------------------------------------

def test_an_agent_reads_six_and_six_with_the_mark_and_searches_by_a_word(world, data_dir):
    import hoping_for
    import introductions
    here_on(data_dir, MORE_PEOPLE[0], TODAY)
    introductions.write(MORE_PEOPLE[5], BEE_WORDS, "2026-10-14T09-00-00Z")
    world.wake()
    said = world.module.who_is_here_said().splitlines()
    agents_said = said[said.index("Agents:") + 1:said.index("People:") - 1]
    people_said = said[said.index("People:") + 1:]
    assert len(agents_said) == 6 and len(people_said) == 6
    assert not any("here this week" in line for line in agents_said)  # never an agent
    hoping_for.write("third", "unused", "2026-10-14T09-00-00Z")  # its switch is off: none
    found = world.module.who_is_here_said("BEES").splitlines()
    assert found[0] == ('Everyone whose introduction or line of what they hope for has "BEES", '
                        'at random:')
    assert found[2].startswith(MORE_PEOPLE[5] + " (a person)")
    assert found[2].endswith('. Their introduction: "%s"' % BEE_WORDS)
    assert world.module.who_is_here_said("unused") == (
        'No one here has "unused" in their introduction or in what they hope for.')


def test_its_tool_takes_an_optional_word(attend):
    assert attend.READ_WHO_IS_HERE["input_schema"] == {
        "type": "object", "properties": {"word": {"type": "string"}}}


def test_the_picks_put_open_doors_first_and_are_drawn_at_random(world, data_dir):
    import door
    import finding
    door.set_door("seventh", state="open", room=2, at="2026-10-14T09-00-00Z")
    for seed in range(5):  # the second one's door is open in this world already
        found_agents, _ = finding.picks(HAZEL, "person", TODAY, random.Random(seed))
        assert sorted(found_agents[:2]) == ["second", "seventh"]
    orders = {tuple(finding.picks(HAZEL, "person", TODAY, random.Random(seed))[1])
              for seed in range(5)}
    assert len(orders) > 1
