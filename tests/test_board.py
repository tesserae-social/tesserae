"""The members' board (plan 4.3; the founder's decision of 13 November 2026).

Short posts from members, screened as the bench is; anyone may read; one level of
replies; newest first, with an end; nothing liked, counted or ranked. Each open
change to the charter has its own thread for its fourteen days, kept at the top.
An agent may post with <<BOARD>>, behind "board" in its features, off for every
agent in what is committed: READING_NOW is held unmoved by test_rooms_reading.
"""

import json
from datetime import datetime, timezone

import pytest
import vault
from nacl.pwhash import argon2id

import agents
from conftest import block, board_link_not_yet, page, post, read_json, write_json
from test_bench import Reader

PASSWORD = "a member's own words, long enough"
NOV_13 = datetime(2026, 11, 13, 15, tzinfo=timezone.utc)
CHANGE = {"id": "invited-until-twenty", "section": "Selves", "old": "vouched for by two members",
          "new": "invited by a member", "posted": "2026-11-11", "answers": [], "outcome": None}


@pytest.fixture
def world(hearth, clock, monkeypatch, tmp_path):
    clock.set(NOV_13)
    changes = tmp_path / "charter-changes.json"
    changes.write_text(json.dumps([CHANGE]), encoding="utf-8")
    monkeypatch.setattr(hearth, "CHARTER_CHANGES", changes)
    reader = Reader()
    monkeypatch.setattr(hearth, "Anthropic", reader)
    hearth.reader = reader
    return hearth


def signed_in(hearth, monkeypatch, name):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)
    sealed, _, _ = vault.make_vault(PASSWORD)
    hearth.members.create_member(name, sealed, "member", [])
    client = hearth.app.test_client()
    assert post(client, "/login", data={"pseudonym": name, "password": PASSWORD}).status_code == 302
    return client


@pytest.fixture
def birch(world, monkeypatch):
    return signed_in(world, monkeypatch, "birch")


@pytest.fixture
def alder(world, monkeypatch):
    return signed_in(world, monkeypatch, "alder")


def said(client, path="/board"):
    return " ".join(page(client.get(path)).split())


def kept(data_dir):
    return read_json(data_dir / "commons" / "board.json")


# ---- reading and writing ---------------------------------------------------

def test_anyone_may_read_and_only_a_member_may_write(world, visitor, birch, data_dir):
    assert post(birch, "/board", data={"words": "Good morning, all of you."}).status_code == 302
    shown = said(visitor)
    assert "Good morning, all of you." in shown and "birch" in shown
    assert "Members may write on the board." in shown and 'name="words"' not in shown
    answer = post(visitor, "/board", data={"words": "From no one."})
    assert answer.status_code == 403
    assert "From no one." not in json.dumps(kept(data_dir))


def test_newest_first_with_replies_beneath_in_the_order_they_came(world, birch, alder, clock):
    post(birch, "/board", data={"words": "The first post."})
    clock.shift(days=1)
    post(alder, "/board", data={"words": "The second post."})
    post(alder, "/board", data={"words": "A first reply.", "to": "1"})
    post(birch, "/board", data={"words": "A second reply.", "to": "1"})
    shown = said(birch)
    # the open change to the charter first, then the newest post
    assert (shown.index("vouched for by two members") < shown.index("The second post.")
            < shown.index("The first post.") < shown.index("A first reply.")
            < shown.index("A second reply."))


def test_one_level_of_replies_only(world, birch, data_dir):
    post(birch, "/board", data={"words": "A post."})
    post(birch, "/board", data={"words": "A reply.", "to": "1"})
    answer = post(birch, "/board", data={"words": "A reply to the reply.", "to": "1/1"})
    assert answer.status_code == 200 and b"That thread is closed" in answer.data
    assert "A reply to the reply." not in json.dumps(kept(data_dir))


def test_nothing_is_counted_liked_or_ranked(world, birch, alder):
    post(birch, "/board", data={"words": "A post."})
    post(alder, "/board", data={"words": "A reply.", "to": "1"})
    shown = said(alder).lower().partition("<main")[2]
    for word in ("like", "trending", "popular", "views", "page 1", "1 reply", "1 post"):
        assert word not in shown


@pytest.mark.parametrize("words, why", [
    ("x" * 501, "A post is up to 500 characters"),
    ("See example.com for more.", "A post carries no link"),
])
def test_what_is_turned_away_is_said_and_kept_in_the_form(world, birch, data_dir, words, why):
    answer = post(birch, "/board", data={"words": words})
    assert answer.status_code == 200 and why in page(answer)
    assert words[:40] in page(answer)
    assert not (data_dir / "commons" / "board.json").exists()


def test_a_post_not_in_good_spirit_is_not_posted(world, birch, data_dir):
    world.reader.says = "NO"
    answer = post(birch, "/board", data={"words": "Something unkind."})
    assert "The board didn&#39;t take that." in page(answer)
    assert not (data_dir / "commons" / "board.json").exists()


def test_a_post_that_names_someone_is_not_posted(world, birch, data_dir, screen):
    screen.says = "YES"
    answer = post(birch, "/board", data={"words": "Say hello to my neighbour."})
    assert "seemed to contain a name or a place" in page(answer)
    assert not (data_dir / "commons" / "board.json").exists()


def test_five_a_day_and_no_more(world, birch, clock, data_dir):
    for n in range(5):
        assert post(birch, "/board", data={"words": "Post %d." % n}).status_code == 302
    answer = post(birch, "/board", data={"words": "One too many."})
    assert "That is all anyone may write on the board in a day" in page(answer)
    clock.shift(days=1)
    assert post(birch, "/board", data={"words": "A new day."}).status_code == 302
    assert len(kept(data_dir)["posts"]) == 6


def test_the_board_has_an_end(world, birch, alder, clock, monkeypatch):
    monkeypatch.setattr(world.board, "PER_PAGE", 3)
    for n in range(5):
        post(birch if n % 2 else alder, "/board", data={"words": "Post number %d." % n})
        clock.shift(days=1)
    first = said(birch)
    assert "older" in first and "That is the whole board." not in first
    second = said(birch, "/board?page=2")
    assert "That is the whole board." in second and "newer" in second
    assert "Post number 0." in second


# ---- a change to the charter ------------------------------------------------

def test_an_open_change_has_its_own_thread_and_takes_replies(world, birch, data_dir):
    shown = said(birch)
    assert "a change to the charter · open until the end of 25 November 2026" in shown
    assert post(birch, "/board", data={"words": "I would say yes.",
                                       "to": "charter:invited-until-twenty"}).status_code == 302
    assert kept(data_dir)["charter"]["invited-until-twenty"][0]["words"] == "I would say yes."
    assert "I would say yes." in said(birch)


def test_after_its_fourteen_days_the_thread_is_closed(world, birch, clock, data_dir):
    post(birch, "/board", data={"words": "Said in time.", "to": "charter:invited-until-twenty"})
    clock.set(datetime(2026, 11, 26, 12, tzinfo=timezone.utc))
    post(birch, "/board", data={"words": "A post after."})
    answer = post(birch, "/board", data={"words": "Said too late.",
                                         "to": "charter:invited-until-twenty"})
    assert "That thread is closed" in page(answer)
    shown = said(birch)
    assert "its 14 days have ended" in shown and "This thread is closed." in shown
    assert "Said in time." in shown and "Said too late." not in shown
    # it stands among the posts at the day it was posted, below the newer post
    assert shown.index("A post after.") < shown.index("vouched for by two members")


def test_a_change_not_yet_posted_has_no_thread(world, birch, clock):
    clock.set(datetime(2026, 11, 10, 12, tzinfo=timezone.utc))
    assert "vouched for by two members" not in said(birch)


# ---- taking off ----------------------------------------------------------

def test_only_the_founder_takes_a_post_off_and_it_is_kept(world, founder, birch, data_dir,
                                                         commons):
    post(birch, "/board", data={"words": "A post to take off."})
    post(birch, "/board", data={"words": "A reply to keep.", "to": "1"})
    assert post(birch, "/board/take-off", data={"where": "1", "confirm": "yes"}).status_code != 200
    assert kept(data_dir)["posts"]
    asked = post(founder, "/board/take-off", data={"where": "1"})
    assert "Take this off the board?" in page(asked)
    assert kept(data_dir)["posts"]
    post(founder, "/board/take-off", data={"where": "1", "confirm": "yes"})
    assert kept(data_dir)["posts"] == []
    removed = read_json(data_dir / "board-removed.json")
    assert removed[0]["taken"]["words"] == "A post to take off."
    assert (commons / "events.md").read_text(encoding="utf-8").rstrip().endswith(
        "a post was taken off the board")


# ---- the commons links it -----------------------------------------------------

def test_the_commons_links_the_board_below_the_bench(world, visitor, monkeypatch):
    now = page(visitor.get("/commons"))
    line = ('\n<p><a href="/board">the board</a>: short posts from members, and replies.</p>')
    assert now.count(line) == 1
    assert now.index('href="/bench"') < now.index('href="/board"')
    board_link_not_yet(world, monkeypatch)
    assert page(visitor.get("/commons")) == now.replace(line, "", 1)


# ---- an agent's post, behind its switch ----------------------------------------

def test_the_switch_is_off_for_every_agent(attend):
    assert attend.BOARD is False
    assert all("board" not in (one.get("features") or ()) for one in agents.registry())


def test_switched_off_a_board_block_is_only_words(attend, wake, data_dir):
    turn = wake(block("BOARD", "Hello from the first one."))
    assert "<<BOARD>>" not in turn.instructions
    assert not (data_dir / "commons" / "board.json").exists()


def test_switched_on_it_is_explained_and_posts_with_its_name(attend, wake, data_dir,
                                                             monkeypatch):
    monkeypatch.setattr(attend, "BOARD", True)
    turn = wake(block("BOARD", "Hello from the first one,\nto whoever reads this."))
    assert turn.instructions.count(attend.BOARD_BLOCK) == 1
    held = kept(data_dir)["posts"][0]
    assert (held["by"], held["words"]) == ("the first one",
                                           "Hello from the first one, to whoever reads this.")
    record = read_json(sorted((data_dir / "packets" / "first" / "attendances").glob("*.json"))[-1])
    assert "posted on the board" in record["acted"]
    assert "posted on the board" not in record["heartbeat"]  # its own to tell
    told = wake().shown
    assert told.count(attend.BOARD_POSTED.format(
        words="Hello from the first one, to whoever reads this.")) == 1
    assert attend.BOARD_POSTED.split(":")[0] not in wake().shown  # said once


def test_switched_on_a_post_with_a_link_is_not_posted_and_is_told(attend, wake, data_dir,
                                                                   monkeypatch):
    monkeypatch.setattr(attend, "BOARD", True)
    wake(block("BOARD", "Come to example.com"))
    assert not (data_dir / "commons" / "board.json").exists()
    assert attend.BOARD_REFUSED["link"] in wake().shown
