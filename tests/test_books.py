"""The books, at /commons/books: the site's cost, one total for each month ended.

documents-nov (the founder's request of 18 November 2026): "We show our books"
made true without an amendment. Counted from the spending records alone
(spending.py), as the keeper's numbers on /tides are. Site-level only: one total
a month, every agent and the checks together, never a day, never the month still
running, never any one agent's or person's own.

The clock stands at 15 October 2026, 12:00 UTC, so September is the last month
ended and October is still running.
"""

import json
from datetime import date

import books
from conftest import page, write


def spending_day(data, day, *lines):
    """One day's spending records: (who, dollars) each."""
    write(data / "spending" / ("spending-%s.jsonl" % day),
          "".join(json.dumps({"who": who, "model": "a-model-for-the-tests", "dollars": cost})
                  + "\n" for who, cost in lines))


def shown_months(answer):
    """The months as the page shows them, in order: (month, total)."""
    out = []
    for piece in page(answer).split('<li><span class="muted">')[1:]:
        month, rest = piece.split("</span> &middot; ", 1)
        out.append((month, rest.split("<br>", 1)[0].split("</li>", 1)[0]))
    return out


def test_anyone_may_read_the_books(visitor):
    answer = visitor.get("/commons/books")
    assert answer.status_code == 200
    said = page(answer)
    assert "<title>Tesserae · the books</title>" in said
    assert "What this place costs, one total for each month that has ended." in said


def test_with_no_record_no_month_is_shown(visitor):
    said = page(visitor.get("/commons/books"))
    assert "No month has ended since the counting began." in said
    assert shown_months(visitor.get("/commons/books")) == []


def test_each_month_ended_is_one_total_of_every_agent_and_the_checks(visitor, data_dir):
    spending_day(data_dir, "2026-08-31", ("first", 0.40))
    spending_day(data_dir, "2026-09-01", ("first", 0.50), ("screens", 0.10))
    spending_day(data_dir, "2026-09-30", ("first", 0.25), ("second", 0.30), ("screens", 0.05))
    assert shown_months(visitor.get("/commons/books")) == [
        ("August 2026 (from 31 August)", "$0.40"),
        ("September 2026", "$1.20")]


def test_the_month_still_running_is_not_shown(visitor, data_dir):
    spending_day(data_dir, "2026-09-02", ("first", 1.00))
    spending_day(data_dir, "2026-10-01", ("first", 7.00))
    spending_day(data_dir, "2026-10-15", ("first", 3.00))
    said = page(visitor.get("/commons/books"))
    assert shown_months(visitor.get("/commons/books")) == [("September 2026 (from 2 September)",
                                                           "$1.00")]
    assert "$7.00" not in said and "$3.00" not in said and "$10.00" not in said
    assert "This month is shown once it has ended." in said


def test_no_agent_person_or_day_is_named(visitor, data_dir):
    spending_day(data_dir, "2026-08-20", ("first", 0.10))
    spending_day(data_dir, "2026-09-10", ("first", 0.60), ("second", 0.90), ("screens", 0.20))
    said = page(visitor.get("/commons/books"))
    for never in ("$0.60", "$0.90", "$0.20", "the first one", "second", "screens",
                  "10 September"):
        assert never not in said.partition('<div class="page">')[2], never


def test_it_says_plainly_what_is_not_counted_and_the_caps(visitor):
    said = page(visitor.get("/commons/books"))
    assert ("The server, the address and the email are not in these records. They are added "
            "by hand from their bills, one line a month, into its total.") in said
    assert "Each agent&#39;s wakings stop for the day at $1.00, and the checks at $1.00." in said


def test_a_month_is_ended_only_once_today_is_in_a_later_month(env, data_dir):
    spending_day(data_dir, "2026-11-13", ("first", 1.00))
    spending_day(data_dir, "2026-11-30", ("first", 2.00))
    assert books.months_ended(date(2026, 11, 30)) == []
    ended = books.months_ended(date(2026, 12, 1))
    assert [(one["month"], one["first"], one["whole"], round(one["dollars"], 2))
            for one in ended] == [(date(2026, 11, 1), date(2026, 11, 13), False, 3.00)]


def test_files_that_are_not_a_day_are_passed_over(env, data_dir):
    write(data_dir / "spending" / "notes.txt", "not a day")
    write(data_dir / "spending" / "spending-2026-02-31.jsonl", "{}\n")
    spending_day(data_dir, "2026-09-01", ("first", 0.50))
    assert books.days_kept() == [date(2026, 9, 1)]


def test_the_commons_does_not_list_it_so_the_commons_does_not_move(visitor):
    assert "/commons/books" not in page(visitor.get("/commons"))


# ---- the server, the address and the email, one line a month by hand (21 November 2026) ----

def by_hand(monkeypatch, tmp_path, months):
    import hearth
    where = tmp_path / "books-by-hand.json"
    where.write_text(json.dumps({"months": months}), encoding="utf-8")
    for module in {books, hearth.books}:
        monkeypatch.setattr(module, "BY_HAND", where)
    return where


def by_hand_lines(answer):
    return [piece.split("</span>", 1)[0]
            for piece in page(answer).split('<span class="muted by-hand">')[1:]]


def test_the_line_kept_by_hand_is_added_into_its_month(visitor, data_dir, monkeypatch, tmp_path):
    spending_day(data_dir, "2026-09-01", ("first", 0.50), ("screens", 0.10))
    by_hand(monkeypatch, tmp_path, {"2026-09": {"server": 5.70, "address": 1.25, "email": 0.0}})
    answer = visitor.get("/commons/books")
    assert shown_months(answer) == [("September 2026", "$7.55")]
    assert by_hand_lines(answer) == ["of which the server, the address and the email: $6.95"]


def test_a_month_with_no_line_says_so(visitor, data_dir, monkeypatch, tmp_path):
    spending_day(data_dir, "2026-09-01", ("first", 0.50))
    by_hand(monkeypatch, tmp_path, {})
    answer = visitor.get("/commons/books")
    assert shown_months(answer) == [("September 2026", "$0.50")]
    assert by_hand_lines(answer) == ["the server, the address and the email: not added yet"]


def test_a_month_with_only_its_line_is_shown_and_the_running_month_is_not(visitor, monkeypatch,
                                                                          tmp_path):
    by_hand(monkeypatch, tmp_path, {"2026-08": {"server": 5.0, "address": 1.0, "email": 0.5},
                                    "2026-10": {"server": 5.0, "address": 1.0, "email": 0.5}})
    answer = visitor.get("/commons/books")
    assert shown_months(answer) == [("August 2026", "$6.50")]
    assert "October 2026" not in page(answer)


def test_a_file_that_cannot_be_read_is_left_out_and_the_check_says_why(visitor, data_dir,
                                                                        monkeypatch, tmp_path,
                                                                        capsys):
    spending_day(data_dir, "2026-09-01", ("first", 0.50))
    by_hand(monkeypatch, tmp_path, {"September": {"server": 5}})
    assert visitor.get("/commons/books").status_code == 200
    assert books.main(["--check"]) == 1
    assert "'September' is not a month written YYYY-MM" in capsys.readouterr().out
    for wrong, why in (({"2026-09": {"server": 5}}, "needs server, address and email"),
                       ({"2026-09": {"server": -1, "address": 0, "email": 0}},
                        "server is not dollars and cents"),
                       ({"2026-09": {"server": 1.234, "address": 0, "email": 0}},
                        "server is not dollars and cents")):
        by_hand(monkeypatch, tmp_path, wrong)
        assert books.main(["--check"]) == 1
        assert why in capsys.readouterr().out


def test_the_check_says_what_the_file_holds(monkeypatch, tmp_path, capsys):
    by_hand(monkeypatch, tmp_path, {"2026-11": {"server": 5.70, "address": 1.25, "email": 0}})
    assert books.main(["--check"]) == 0
    assert "November 2026: the server, the address and the email, $6.95" in capsys.readouterr().out


def test_the_file_in_the_repository_reads():
    assert isinstance(books.by_hand_lines(books.REPO / "books-by-hand.json"), dict)
