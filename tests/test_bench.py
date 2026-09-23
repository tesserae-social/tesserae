"""The visitor's bench: one line from anyone passing, read once before it is placed.

The small utility model that reads a line is stubbed in every test here. It is
the only thing on the bench that would go out to the network, and it never does.
"""

import re
from types import SimpleNamespace

import pytest

from conftest import lines_of, page, post, write

LINE = "The lake was still this morning."


class Reader:
    """The small model that reads one line, stubbed: what it was asked, what it says."""

    def __init__(self, says="YES", breaks=False):
        self.says = says
        self.breaks = breaks
        self.asked = []

    def __call__(self, *args, **kwargs):
        reader = self

        class Messages:
            def create(self, **asked):
                reader.asked.append(asked)
                if reader.breaks:
                    raise RuntimeError("the model could not be reached")
                return SimpleNamespace(content=[SimpleNamespace(text=reader.says)])

        return SimpleNamespace(messages=Messages())


@pytest.fixture
def reader(hearth, monkeypatch):
    """The bench's reader, saying yes unless a test says otherwise."""
    said = Reader()
    monkeypatch.setattr(hearth, "Anthropic", said)
    return said


def leave(client, line=LINE, who=None, trap=None, address=None):
    form = {"line": line}
    if who is not None:
        form["as"] = who
    if trap is not None:
        form["url"] = trap
    where = {"environ_base": {"REMOTE_ADDR": address}} if address else {}
    return client.post("/bench", data=form, **where)


def bench_lines(commons):
    return lines_of(commons / "bench.md")


# ---- one line, placed ----------------------------------------------------

def test_a_line_in_good_spirit_is_placed(visitor, reader, commons, clock):
    answer = leave(visitor, who="a passing stranger")
    assert answer.status_code == 302
    assert "placed=1" in answer.headers["Location"]
    assert bench_lines(commons) == ["- %s · a passing stranger · %s" % (clock.day(), LINE)]
    assert "Your line is on the bench." in page(visitor.get("/bench", query_string={"placed": 1}))


def test_the_line_is_read_once_by_the_small_model_and_nothing_else(visitor, reader, hearth):
    leave(visitor)
    assert len(reader.asked) == 1
    asked = reader.asked[0]
    assert asked["model"] == hearth.BENCH_MODEL
    assert asked["max_tokens"] == hearth.BENCH_TOKENS
    assert asked["system"] == hearth.BENCH_SYSTEM
    assert asked["messages"] == [{"role": "user", "content": "<line>%s</line>" % LINE}]


def test_an_unsigned_line_is_signed_as_a_passerby(visitor, reader, commons, hearth):
    leave(visitor, who="   ")
    assert bench_lines(commons)[0].split(" · ")[1] == hearth.AS_DEFAULT


def test_the_name_a_visitor_signs_with_is_shown(visitor, reader):
    leave(visitor, who="Mira")
    said = page(visitor.get("/bench"))
    assert "Mira" in said
    assert LINE in said


def test_a_line_is_shown_on_the_bench_and_in_the_commons(visitor, reader, commons):
    leave(visitor)
    assert LINE in page(visitor.get("/bench"))
    assert LINE in page(visitor.get("/commons/bench.md"))


def test_an_empty_bench_says_so(visitor):
    said = page(visitor.get("/bench"))
    assert "The bench is empty. No one has left a line yet." in said
    assert "A line is read once by a small utility model before it is placed" in said


def test_the_form_says_which_field_may_be_left_alone(visitor):
    said = page(visitor.get("/bench"))
    assert '<label for="line">a line</label>' in said
    assert '<label for="as">signed as (optional)</label>' in said


def test_a_line_is_shown_as_words_and_never_as_markup(visitor, reader, commons):
    written = "<b>hello</b> & <script>alert(1)</script>"
    leave(visitor, line=written, who="<em>me</em>")
    said = page(visitor.get("/bench"))
    assert "&lt;b&gt;hello&lt;/b&gt;" in said
    assert "&lt;em&gt;me&lt;/em&gt;" in said
    assert "<b>hello</b>" not in said
    assert "<script>alert(1)</script>" not in said
    assert written in (commons / "bench.md").read_text(encoding="utf-8")  # kept as written


def test_a_line_of_exactly_the_limit_is_placed(visitor, reader, hearth, commons):
    leave(visitor, line="a" * hearth.BENCH_LIMIT)
    assert len(bench_lines(commons)) == 1


# ---- the seven refusals --------------------------------------------------

# the page escapes what it renders, so the one sentence is looked for as shown
REFUSAL = "The bench didn&#39;t take that line."


def refused(answer):
    return answer.status_code == 200 and REFUSAL in page(answer)


def test_an_empty_line_is_refused(visitor, reader, commons):
    assert refused(leave(visitor, line="   \n  "))
    assert bench_lines(commons) == []


def test_a_line_past_the_limit_is_refused(visitor, reader, hearth, commons):
    assert refused(leave(visitor, line="a" * (hearth.BENCH_LIMIT + 1)))
    assert bench_lines(commons) == []


def test_a_name_past_its_limit_is_refused(visitor, reader, hearth, commons):
    assert refused(leave(visitor, who="n" * (hearth.AS_LIMIT + 1)))
    assert bench_lines(commons) == []


@pytest.mark.parametrize("linkish", [
    "come to http://example.com",
    "see www.example.com",
    "visit example.com for more",
    "my site is example.co.uk",
])
def test_anything_that_looks_like_a_link_is_refused(visitor, reader, commons, linkish):
    assert refused(leave(visitor, line=linkish))
    assert bench_lines(commons) == []


def test_a_link_in_the_name_is_refused_too(visitor, reader, commons):
    assert refused(leave(visitor, who="buy.example.com"))
    assert bench_lines(commons) == []


def test_the_fourth_line_in_a_day_is_refused(visitor, reader, hearth, commons):
    for _ in range(hearth.BENCH_A_DAY):
        assert leave(visitor).status_code == 302
    assert refused(leave(visitor))
    assert len(bench_lines(commons)) == hearth.BENCH_A_DAY


@pytest.mark.parametrize("says", ["NO", "no", "Yes, but", "", "I would rather not say"])
def test_a_line_the_model_does_not_say_yes_to_stays_where_it_was(visitor, hearth, monkeypatch,
                                                                 commons, says):
    monkeypatch.setattr(hearth, "Anthropic", Reader(says=says))
    assert refused(leave(visitor))
    assert bench_lines(commons) == []


def test_a_model_that_cannot_be_reached_leaves_the_line_unplaced(visitor, hearth, monkeypatch,
                                                                 commons):
    monkeypatch.setattr(hearth, "Anthropic", Reader(breaks=True))
    assert refused(leave(visitor))
    assert bench_lines(commons) == []


def test_a_refusal_keeps_what_was_written_and_says_no_more(visitor, hearth, monkeypatch):
    monkeypatch.setattr(hearth, "Anthropic", Reader(says="NO"))
    said = page(leave(visitor, line="a line that was turned away", who="Mira"))
    assert 'value="a line that was turned away"' in said
    assert 'value="Mira"' in said
    assert said.count(REFUSAL) == 1
    # the whole of what a visitor is told: the one sentence, and never which rule
    told = re.findall(r'<p class="error">(.*?)</p>', said, re.S)
    assert told == [REFUSAL]


def test_the_honeypot_is_shown_to_no_one(visitor):
    """It is not drawn at all, and the rule that says so is on the element itself."""
    said = page(visitor.get("/bench"))
    trap = re.search(r'<div class="trap"[^>]*>(.*?)</div>', said, re.S)
    assert trap, "the honeypot is no longer on the page"
    assert 'aria-hidden="true"' in trap.group(0)
    assert re.search(r'style="display: ?none"', trap.group(0))
    assert 'tabindex="-1"' in trap.group(1)
    assert 'autocomplete="off"' in trap.group(1)


def test_the_honeypot_is_told_nothing(visitor, reader, commons):
    answer = leave(visitor, trap="http://example.com")
    assert answer.status_code == 302
    assert "placed=1" in answer.headers["Location"]  # it is told its line was taken
    assert bench_lines(commons) == []               # and nothing was
    assert reader.asked == []                       # the model is not even asked


# ---- the counting, which keeps no addresses ------------------------------

def test_what_is_counted_is_a_hash_and_never_an_address(visitor, reader, hearth):
    leave(visitor, address="203.0.113.7")
    keys = list(hearth.BENCH_VISITS)
    assert len(keys) == 1
    assert len(keys[0]) == 64 and all(mark in "0123456789abcdef" for mark in keys[0])
    assert "203.0.113.7" not in keys[0]
    assert hearth.BENCH_VISITS[keys[0]] == 1


def test_each_visitor_is_counted_apart(visitor, reader, hearth, commons):
    for _ in range(hearth.BENCH_A_DAY):
        leave(visitor, address="203.0.113.7")
    assert refused(leave(visitor, address="203.0.113.7"))
    assert leave(visitor, address="203.0.113.8").status_code == 302
    assert len(bench_lines(commons)) == hearth.BENCH_A_DAY + 1


def test_the_day_turning_empties_the_counting(visitor, reader, hearth, clock, commons):
    for _ in range(hearth.BENCH_A_DAY):
        leave(visitor)
    assert refused(leave(visitor))

    clock.shift(days=1)
    assert leave(visitor).status_code == 302
    assert hearth.BENCH_DAY == clock.day()
    assert len(hearth.BENCH_VISITS) == 1  # yesterday's counting is nobody's business
    assert len(bench_lines(commons)) == hearth.BENCH_A_DAY + 1


def test_a_line_carries_the_day_it_was_left(visitor, reader, commons, clock):
    clock.set("2026-10-20T23-30-00Z")
    leave(visitor)
    assert bench_lines(commons)[0].startswith("- 2026-10-20 · ")


def test_the_day_is_kept_short_and_said_long(visitor, reader, commons, clock):
    """The file sorts by 2026-10-20; the page says it the way the rest of the site does."""
    clock.set("2026-10-20T23-30-00Z")
    leave(visitor)
    said = page(visitor.get("/bench"))
    assert "20 October 2026" in said
    assert "2026-10-20" not in said
    assert bench_lines(commons)[0].startswith("- 2026-10-20 · ")   # and the file is unchanged


def test_a_day_that_is_no_day_is_left_as_it_was_written(visitor, commons):
    write(commons / "bench.md", "- nonsense · someone · a line all the same\n")
    said = page(visitor.get("/bench"))
    assert "nonsense" in said and "a line all the same" in said


# ---- taking one off ------------------------------------------------------

def test_only_the_founder_may_take_a_line_off(visitor, reader, commons):
    leave(visitor)
    raw = bench_lines(commons)[0]
    answer = post(visitor, "/bench/take-off", data={"line": raw, "confirm": "yes"})
    assert answer.status_code == 302
    assert answer.headers["Location"].endswith("/login")
    assert bench_lines(commons) == [raw]


def test_taking_a_line_off_takes_one_plain_question_first(founder, visitor, reader, commons):
    leave(visitor)
    raw = bench_lines(commons)[0]

    asked = post(founder, "/bench/take-off", data={"line": raw})
    assert "Take this line off the bench?" in page(asked)
    assert bench_lines(commons) == [raw]

    done = post(founder, "/bench/take-off", data={"line": raw, "confirm": "yes"})
    assert done.status_code == 302
    assert bench_lines(commons) == []


def test_what_is_taken_off_is_kept_outside_the_commons_and_the_commons_is_told(
        founder, visitor, reader, commons, data_dir, hearth):
    leave(visitor)
    raw = bench_lines(commons)[0]
    post(founder, "/bench/take-off", data={"line": raw, "confirm": "yes"})

    assert lines_of(data_dir / "bench-removed.md") == [raw]
    assert lines_of(commons / "events.md")[-1].endswith("event · " + hearth.TAKEN_OFF)
    assert LINE not in page(visitor.get("/bench"))
    assert LINE not in page(visitor.get("/commons/bench.md"))


def test_the_same_line_is_not_taken_off_twice(founder, visitor, reader, commons, hearth):
    leave(visitor)
    raw = bench_lines(commons)[0]
    post(founder, "/bench/take-off", data={"line": raw, "confirm": "yes"})
    post(founder, "/bench/take-off", data={"line": raw, "confirm": "yes"})
    told = [line for line in lines_of(commons / "events.md") if hearth.TAKEN_OFF in line]
    assert len(told) == 1


def test_the_lines_that_stay_are_left_as_they_were(founder, visitor, reader, commons):
    leave(visitor, line="The first line.")
    leave(visitor, line="The second line.")
    leave(visitor, line="The third line.")
    raw = bench_lines(commons)[1]
    post(founder, "/bench/take-off", data={"line": raw, "confirm": "yes"})
    kept = bench_lines(commons)
    assert len(kept) == 2
    assert "The first line." in kept[0] and "The third line." in kept[1]


def test_a_malformed_line_in_the_file_is_passed_over(visitor, commons):
    write(commons / "bench.md",
          "- 2026-10-01 · someone · A line as it should be\n"
          "not a line at all\n"
          "- 2026-10-02 · someone · \n")
    said = page(visitor.get("/bench"))
    assert "A line as it should be" in said
    assert "not a line at all" not in said


def test_the_bench_is_open_to_anyone_without_a_password(visitor):
    assert visitor.get("/bench").status_code == 200
    assert "log in" in page(visitor.get("/bench"))
