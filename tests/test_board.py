"""The members' board (plan 4.3; the founder's decision of 13 November 2026, reorganised
by his request of 14 November 2026).

Three sections: the place (with a topic for every change to the charter), the weekly
question (a topic each week, made automatically) and conversation. The place and the
weekly question are public; conversation is for members only. Only members post. A
topic has a subject and its posts, oldest first; a reply may name the post it answers,
with a short quote. @name mentions a member, at most three to a post, and shows on
their home page and in a daily email. A post may be taken down by whoever wrote it,
its words deleted for good; the keeper may take down anyone's, its words kept outside
the commons and a ledger line written. Nothing is edited. An agent may read and post
in the place only, behind "board" in its features, off for every agent in what is
committed: READING_NOW is held unmoved by test_rooms_reading.
"""

import html
import json
from datetime import datetime, timezone

import pytest
import vault
from nacl.pwhash import argon2id

import agents
from conftest import Reader, block, page, post, read_json, write_json

PASSWORD = "a member's own words, long enough"
NOV_13 = datetime(2026, 11, 13, 15, tzinfo=timezone.utc)
CHANGE = {"id": "invited-until-twenty", "section": "Selves", "old": "vouched for by two members",
          "new": "invited by a member", "posted": "2026-11-11", "answers": [], "outcome": None}
CHARTER_KEY = "charter-invited-until-twenty"


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


def text(answer):
    """A page's words, with what its markup escaped said as it is read."""
    return html.unescape(page(answer))


def said(client, path="/board"):
    return " ".join(text(client.get(path)).split())


def kept(data_dir):
    return read_json(data_dir / "commons" / "board.json")


def start(client, words="The first post.", subject="A subject", section="place"):
    return post(client, "/board/" + section, data={"subject": subject, "words": words})


def key_of(answer):
    """The topic a start was sent on to."""
    return answer.headers["Location"].split("#")[0].split("?")[0].rsplit("/", 1)[1]


def write(client, key, words, to=None):
    return post(client, "/board/topic/" + key,
                data={"words": words, **({"to": str(to)} if to else {})})


# ---- sections, and who may read them --------------------------------------------

def test_the_front_page_names_three_sections_and_who_may_read_each(world, visitor):
    shown = said(visitor)
    assert (shown.index('href="/board/place"') < shown.index('href="/board/weekly"')
            < shown.index('href="/board/conversation"'))
    for line in world.BOARD_WHO_READS.values():
        assert line in shown


@pytest.mark.parametrize("section", ["place", "weekly", "conversation"])
def test_the_top_of_each_section_says_plainly_who_may_read_it(world, visitor, section):
    assert world.BOARD_WHO_READS[section] in said(visitor, "/board/" + section)


def test_the_place_is_public_and_conversation_is_for_members(world, visitor, birch):
    open_key = key_of(start(birch, "Words anyone may read."))
    shut_key = key_of(start(birch, "Words for members.", "Among us", "conversation"))
    assert "Words anyone may read." in said(visitor, "/board/topic/" + open_key)
    answer = visitor.get("/board/topic/" + shut_key)
    assert answer.status_code == 403 and b"Words for members." not in answer.data
    assert world.BOARD_MEMBERS_READ.encode() in answer.data
    assert "Among us" not in said(visitor) and "Among us" not in said(visitor, "/board/conversation")
    assert "Among us" in said(birch)
    assert "Words for members." in said(birch, "/board/topic/" + shut_key)


def test_only_a_member_posts(world, visitor, birch, data_dir):
    assert start(visitor, "From no one.").status_code == 403
    assert write(visitor, CHARTER_KEY, "From no one either.").status_code == 403
    assert not (data_dir / "commons" / "board.json").exists()


def test_no_one_starts_a_topic_in_the_weekly_question(world, birch, data_dir):
    assert start(birch, "A topic of my own.", section="weekly").status_code == 403
    assert not (data_dir / "commons" / "board.json").exists()


# ---- topics and posts --------------------------------------------------------------

def test_a_topic_has_a_short_subject_and_its_posts_oldest_first(world, birch, alder, clock):
    key = key_of(start(birch, "The first post.", "Lanterns for the paths"))
    clock.shift(days=1)
    write(alder, key, "A second post.")
    write(birch, key, "A third post.")
    shown = said(birch, "/board/topic/" + key)
    assert "Lanterns for the paths" in shown
    assert (shown.index("The first post.") < shown.index("A second post.")
            < shown.index("A third post."))


def test_a_subject_is_up_to_eighty_characters(world, birch, data_dir):
    assert "A subject is up to 80 characters" in text(start(birch, "Words.", "x" * 81))
    assert "A topic needs a subject" in text(start(birch, "Words.", ""))
    assert not (data_dir / "commons" / "board.json").exists()
    assert start(birch, "Words.", "x" * 80).status_code == 302


def test_the_front_page_lists_topics_by_their_last_post_with_no_counts(world, birch, alder,
                                                                       clock):
    first = key_of(start(birch, "One.", "The older topic"))
    clock.shift(days=1)
    start(alder, "Two.", "The newer topic")
    clock.shift(days=1)
    write(alder, first, "A post that brings it back up.")
    shown = said(alder)
    assert shown.index("The older topic") < shown.index("The newer topic")
    assert "15 November 2026" in shown  # the day of its last post
    lowered = text(alder.get("/board")).lower().partition("<main")[2]
    for word in ("replies", "1 post", "2 posts", "views", "trending", "popular"):
        assert word not in lowered


def test_fifteen_to_a_page_and_older_below(world, birch):
    for n in range(16):
        world.board.start("place", "birch", "Topic number %d" % n, "Words %d." % n, "2026-11-13")
    shown = said(birch)
    assert "Topic number 15" in shown and "Topic number 0 " not in shown + " "
    assert 'href="/board?page=2">older' in text(birch.get("/board"))
    later = said(birch, "/board?page=2")
    assert "Topic number 0" in later and world.BOARD_END in later


def test_a_reply_names_who_it_answers_with_a_short_quote(world, birch, alder, data_dir):
    key = key_of(start(birch, "Shall we plant a hedge along the north side? " * 4))
    write(alder, key, "Yes, a hedge.", to=1)
    shown = said(alder, "/board/topic/" + key)
    assert "replying to birch" in shown
    reply = shown.partition("replying to birch")[2]
    assert "Shall we plant a hedge along the north side?" in reply.partition("Yes, a hedge.")[0]
    assert kept(data_dir)["topics"][0]["posts"][1]["to"] == 1


def test_a_reply_to_a_post_that_is_not_there_is_not_kept(world, birch, data_dir):
    key = key_of(start(birch))
    assert world.BOARD_REFUSED["closed"] in text(write(birch, key, "To nothing.", to=7))
    assert "To nothing." not in json.dumps(kept(data_dir))


@pytest.mark.parametrize("words, why", [
    ("x" * 501, "A post is up to 500 characters"),
    ("See example.com for more.", "A post carries no link"),
    ("", "There was nothing to post"),
])
def test_what_is_turned_away_is_said_and_kept_in_the_form(world, birch, data_dir, words, why):
    answer = start(birch, words)
    assert answer.status_code == 200 and why in text(answer)
    assert not (data_dir / "commons" / "board.json").exists()


def test_a_post_not_in_good_spirit_is_not_posted(world, birch, data_dir):
    world.reader.says = "NO"
    answer = start(birch, "Something unkind.")
    assert "The board didn't take that." in text(answer)
    assert "Something unkind." in text(answer)  # kept in the form
    assert not (data_dir / "commons" / "board.json").exists()


def test_a_post_that_names_someone_is_not_posted(world, birch, data_dir, screen):
    screen.says = "YES"
    answer = start(birch, "Hollis Brandt says hello.")
    assert "seemed to contain a name or a place" in text(answer)
    assert not (data_dir / "commons" / "board.json").exists()


def test_five_a_day_and_no_more(world, birch, clock):
    key = key_of(start(birch, "One."))
    for n in range(4):
        write(birch, key, "More %d." % n)
    assert "That is all anyone may write on the board in a day" in text(
        write(birch, key, "The sixth."))
    clock.shift(days=1)
    assert write(birch, key, "The sixth, a day later.").status_code == 302


def test_nothing_is_ever_edited(world):
    rules = sorted(str(rule) for rule in world.app.url_map.iter_rules()
                   if str(rule).startswith("/board"))
    assert rules == ["/board", "/board/<section>", "/board/take-down", "/board/topic/<key>"]
    assert not any(hasattr(world.board, name) for name in ("edit", "change", "amend"))


# ---- the place: changes to the charter --------------------------------------------

def test_every_change_to_the_charter_has_its_own_topic_in_the_place(world, visitor, birch):
    shown = said(visitor, "/board/place")
    assert "a change to the charter, in Selves" in shown and "the site" in shown
    topic = text(visitor.get("/board/topic/" + CHARTER_KEY))
    assert "vouched for by two members" in topic and "invited by a member" in topic
    assert 'href="/commons/charter-changes#invited-until-twenty"' in topic
    assert write(birch, CHARTER_KEY, "I would welcome this.").status_code == 302
    assert "I would welcome this." in said(visitor, "/board/topic/" + CHARTER_KEY)


def test_the_charter_page_links_back_to_the_topic(world, visitor):
    assert ('href="/board/topic/%s"' % CHARTER_KEY) in text(visitor.get("/commons/charter-changes"))


def test_after_its_fourteen_days_the_change_takes_no_more_posts(world, birch, clock, data_dir):
    clock.shift(days=15)
    assert world.BOARD_REFUSED["closed"] in text(write(birch, CHARTER_KEY, "Too late."))
    assert not (data_dir / "commons" / "board.json").exists()


def test_a_change_not_yet_posted_has_no_topic(world, birch, clock):
    clock.set(datetime(2026, 11, 10, 12, tzinfo=timezone.utc))
    assert "a change to the charter" not in said(birch, "/board/place")
    assert birch.get("/board/topic/" + CHARTER_KEY).status_code == 404


# ---- the weekly question ------------------------------------------------------------

def test_the_weekly_question_has_its_topic_each_week(world, visitor, birch, data_dir):
    write_json(data_dir / "weekly-questions.json", {"waiting": [
        {"words": "What did you notice this week?", "by": "alder", "at": "2026-11-10T00:00:00Z"}],
        "weeks": {}})
    assert "the question for the week of 9 November" in said(visitor, "/board/weekly")
    topic = said(visitor, "/board/topic/week-2026-W46")
    assert "What did you notice this week?" in topic and "alder" not in topic
    assert write(birch, "week-2026-W46", "The light on the water.").status_code == 302
    assert "The light on the water." in said(visitor, "/board/topic/week-2026-W46")


def test_a_week_with_no_question_has_no_topic(world, visitor):
    assert world.BOARD_NO_TOPICS in said(visitor, "/board/weekly")
    assert visitor.get("/board/topic/week-2026-W46").status_code == 404


# ---- mentions --------------------------------------------------------------------------

def test_a_mention_shows_on_the_home_page_of_whoever_is_mentioned(world, birch, alder):
    start(birch, "What do you think, @alder?", "Lanterns")
    assert "You were mentioned on the board in Lanterns" in said(alder, "/")
    assert "You were mentioned" not in said(birch, "/")


def test_at_most_three_mentions_to_a_post(world, birch, monkeypatch, data_dir):
    for name in ("ash", "elm", "oak", "yew"):
        signed_in(world, monkeypatch, name)
    assert world.BOARD_REFUSED["mentions"] in text(start(birch, "@ash @elm @oak @yew, all of you."))
    assert start(birch, "@ash @elm @oak, the three of you.").status_code == 302
    assert kept(data_dir)["topics"][0]["posts"][0]["mentions"] == ["ash", "elm", "oak"]


def test_a_name_that_is_no_one_s_is_no_mention(world, birch, data_dir):
    start(birch, "Hello @nobody-here.")
    assert kept(data_dir)["topics"][0]["posts"][0]["mentions"] == []


def test_a_mention_joins_the_daily_email_and_no_other(world, birch, alder):
    world.members.set_email("alder", "alder@example.org", confirmed_at="2026-11-01T00:00:00Z")
    world.members.set_emails("alder", "daily")
    start(birch, "A word for @alder.", "Lanterns")
    at = datetime(2026, 11, 13, 18, tzinfo=timezone.utc)
    due = world.email_due("alder", at)
    assert due is not None and due[3] == ["Lanterns"]
    world.members.set_emails("alder", "weekly")
    assert world.email_due("alder", at) is None


def test_the_mention_email_says_where_and_nothing_of_the_words(world, outbox):
    import mail
    mail.send_waiting("a@example.org", [], "STOP", mentioned=["Lanterns"])
    mail.send_waiting("a@example.org", ["the first one"], "STOP", mentioned=["Lanterns"])
    mail.send_waiting("a@example.org", ["the first one"], "STOP")
    texts = [one["text"] for one in outbox.sent]
    assert texts[0].startswith("You were mentioned on the board in Lanterns.\n\n")
    assert texts[1].startswith("The first one has written to you at Tesserae.\n\n"
                               "You were mentioned on the board in Lanterns.\n\n")
    assert "mentioned" not in texts[2]


# ---- taking down -------------------------------------------------------------------------

def test_a_member_takes_down_their_own_post_and_its_words_are_gone(world, birch, alder, data_dir):
    key = key_of(start(birch, "Words I will take back.", "Second thoughts"))
    write(birch, key, "And a reply to keep.")
    write(alder, key, "Answering the first.", to=1)
    post(alder, "/board/take-down", data={"key": key, "n": "1", "confirm": "yes"})
    assert kept(data_dir)["topics"][0]["posts"][0]["words"] == "Words I will take back."
    assert "Its words will be deleted for good." in text(
        post(birch, "/board/take-down", data={"key": key, "n": "1"}))
    post(birch, "/board/take-down", data={"key": key, "n": "1", "confirm": "yes"})
    every = (data_dir / "commons" / "board.json").read_text(encoding="utf-8")
    assert "Words I will take back." not in every and "Second thoughts" not in every
    assert not (data_dir / "board-removed.json").exists()
    shown = said(alder, "/board/topic/" + key)
    assert "birch took this post down, 13 November 2026" in shown
    assert "(taken down)" in shown  # where alder quoted it
    assert "a topic whose first post was taken down" in shown
    assert "a topic whose first post was taken down" in said(alder, "/board/place")
    assert "And a reply to keep." in shown


def test_the_keeper_takes_down_anyone_s_and_keeps_the_words_privately(
        world, founder, birch, data_dir, commons):
    key = key_of(start(birch, "A post to take down."))
    assert "kept privately, outside the commons" in text(
        post(founder, "/board/take-down", data={"key": key, "n": "1"}))
    post(founder, "/board/take-down", data={"key": key, "n": "1", "confirm": "yes"})
    assert "A post to take down." not in (data_dir / "commons" / "board.json").read_text(
        encoding="utf-8")
    assert read_json(data_dir / "board-removed.json")[0]["taken"]["words"] == "A post to take down."
    assert "taken down by the keeper, 13 November 2026" in said(founder, "/board/topic/" + key)
    ledger = (commons / "ledger.md").read_text(encoding="utf-8")
    assert ledger.rstrip().endswith("a post on the board was taken down by the keeper")


# ---- the commons links it -------------------------------------------------------------

def test_the_commons_lists_the_board_first(world, visitor):
    shown = text(visitor.get("/commons"))
    assert shown.index('href="/board"') < shown.index('href="/offerings"')


# ---- a board kept before topics -------------------------------------------------------

def test_a_board_from_before_topics_is_read_as_topics_in_conversation(world, birch, visitor,
                                                                       data_dir):
    write_json(data_dir / "commons" / "board.json", {
        "posts": [{"n": 1, "by": "birch", "day": "2026-11-13", "words": "An old post.",
                   "replies": [{"n": 1, "by": "alder", "day": "2026-11-13",
                                "words": "An old reply."}]}],
        "charter": {"invited-until-twenty": [{"n": 1, "by": "birch", "day": "2026-11-12",
                                              "words": "An old word on the change."}]}})
    topic = said(birch, "/board/topic/1")
    assert "An old post." in topic and "An old reply." in topic
    assert "An old post." in said(birch, "/board/conversation")
    assert "An old post." not in said(visitor)
    assert "An old word on the change." in said(visitor, "/board/topic/" + CHARTER_KEY)


# ---- an agent, in the place only, behind its switch -------------------------------------

def test_the_switch_is_off_for_every_agent(attend):
    assert attend.BOARD is False
    assert all("board" not in (one.get("features") or ()) for one in agents.registry())


def test_switched_off_nothing_is_said_and_a_block_is_only_words(attend, wake, data_dir):
    turn = wake(block("BOARD", "subject: Hello\nHello from the first one."))
    assert "<<BOARD>>" not in turn.instructions and "THE PLACE" not in turn.shown
    assert not (data_dir / "commons" / "board.json").exists()


def test_switched_off_a_mention_of_it_is_not_told(attend, wake):
    attend.board.start("place", "birch", "Lanterns", "Hello @the first one.", "2026-10-15",
                       ["the first one"])
    assert "You were mentioned" not in wake().shown


def test_switched_on_it_reads_the_place_and_starts_a_topic(attend, wake, data_dir, monkeypatch):
    monkeypatch.setattr(attend, "BOARD", True)
    turn = wake(block("BOARD", "subject: Lanterns\nHello from the first one,\nto whoever reads this."))
    assert turn.instructions.count("<<BOARD>>") == 1
    assert turn.instructions.count("<<BOARD_TAKE_DOWN>>") == 1
    held = kept(data_dir)["topics"][0]
    assert (held["section"], held["subject"], held["by"]) == ("place", "Lanterns", "the first one")
    assert held["posts"][0]["words"] == "Hello from the first one, to whoever reads this."
    record = read_json(sorted((data_dir / "packets" / "first" / "attendances").glob("*.json"))[-1])
    assert "posted on the board" in record["acted"]
    assert "posted on the board" not in record["heartbeat"]  # its own to tell
    told = wake().shown
    assert "Your post at your last waking is on the board, in topic 1, as post 1" in told
    assert "topic 1: Lanterns (started by the first one)" in told


def test_switched_on_it_posts_in_a_topic_of_the_place_and_nowhere_else(attend, wake, data_dir,
                                                                       monkeypatch):
    monkeypatch.setattr(attend, "BOARD", True)
    attend.board.start("conversation", "birch", "Among us", "Members only.", "2026-10-15")
    attend.board.start("place", "birch", "Lanterns", "Shall we?", "2026-10-15")
    shown = wake().shown
    assert "Shall we?" in shown and "Members only." not in shown and "Among us" not in shown
    wake(block("BOARD", "topic: 1\nInto conversation."))
    assert "Into conversation." not in json.dumps(kept(data_dir))
    assert attend.BOARD_REFUSED["no_topic"] in wake().shown
    wake(block("BOARD", "topic: 2\nreplying to: 1\nYes, lanterns."))
    posts = kept(data_dir)["topics"][1]["posts"]
    assert (posts[-1]["words"], posts[-1]["to"], posts[-1]["by"]) == (
        "Yes, lanterns.", 1, "the first one")


def test_switched_on_it_is_told_where_it_was_mentioned(attend, wake, monkeypatch):
    monkeypatch.setattr(attend, "BOARD", True)
    attend.board.start("place", "birch", "Lanterns", "Hello @the first one.", "2026-10-15",
                       ["the first one"])
    assert ("You were mentioned on the board in topic 1 (Lanterns), post 1, by birch."
            in wake().shown)


def test_switched_on_it_takes_down_its_own_post_and_no_one_else_s(attend, wake, data_dir,
                                                                  monkeypatch):
    monkeypatch.setattr(attend, "BOARD", True)
    attend.board.start("place", "birch", "Lanterns", "Birch's words.", "2026-10-15")
    attend.board.add("1", "the first one", "My words.", "2026-10-15")
    wake(block("BOARD_TAKE_DOWN", "topic: 1\npost: 1"))
    assert kept(data_dir)["topics"][0]["posts"][0]["words"] == "Birch's words."
    wake(block("BOARD_TAKE_DOWN", "topic: 1\npost: 2"))
    gone = kept(data_dir)["topics"][0]["posts"][1]
    assert gone["words"] is None and gone["taken"]["by"] == "self"


def test_switched_on_a_post_with_a_link_is_not_posted_and_is_told(attend, wake, data_dir,
                                                                   monkeypatch):
    monkeypatch.setattr(attend, "BOARD", True)
    wake(block("BOARD", "subject: A link\nCome to example.com"))
    assert not (data_dir / "commons" / "board.json").exists()
    assert attend.BOARD_REFUSED["link"] in wake().shown
