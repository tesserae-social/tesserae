"""remove_bench_event.py: the bench's one test line leaves events.md, once, and the ledger says so.

The founder's request of 14 November 2026. Dry run unless --apply; exactly one line
or nothing is changed; events.md as it was is kept outside the commons.
"""

import importlib

import pytest

EVENTS = ("2026-09-02 · word · the word was published\n"
          "2026-09-04 · founding · the first one was founded\n"
          "2026-09-20 · letter · the founder wrote a letter\n"
          "2026-09-21 · event · a line was taken off the bench\n"
          "2026-09-21 · letter · the founder wrote a letter\n")


@pytest.fixture
def script(env, data_dir):
    import remove_bench_event
    return importlib.reload(remove_bench_event)


def events(data_dir):
    return (data_dir / "commons" / "events.md").read_text(encoding="utf-8")


def test_a_dry_run_writes_nothing(script, data_dir, capsys):
    (data_dir / "commons" / "events.md").write_text(EVENTS, encoding="utf-8")
    assert script.main([]) == 0
    assert events(data_dir) == EVENTS
    assert not (data_dir / "commons" / "ledger.md").exists()
    said = capsys.readouterr().out
    assert "a line was taken off the bench" in said and "nothing written" in said


def test_with_apply_the_one_line_goes_and_the_ledger_says_so(script, data_dir):
    (data_dir / "commons" / "events.md").write_text(EVENTS, encoding="utf-8")
    assert script.main(["--apply"]) == 0
    assert events(data_dir) == EVENTS.replace(
        "2026-09-21 · event · a line was taken off the bench\n", "")
    ledger = (data_dir / "commons" / "ledger.md").read_text(encoding="utf-8")
    assert ledger.count("\n") == 1
    assert ledger.endswith(" · a test entry was removed from the record\n")
    kept = list(data_dir.glob("events-before-bench-removal-*.md"))
    assert len(kept) == 1 and kept[0].read_text(encoding="utf-8") == EVENTS


def test_a_second_run_does_nothing(script, data_dir):
    (data_dir / "commons" / "events.md").write_text(EVENTS, encoding="utf-8")
    script.main(["--apply"])
    after = events(data_dir)
    ledger = (data_dir / "commons" / "ledger.md").read_text(encoding="utf-8")
    assert script.main(["--apply"]) == 0
    assert events(data_dir) == after
    assert (data_dir / "commons" / "ledger.md").read_text(encoding="utf-8") == ledger


def test_more_than_one_such_line_is_refused(script, data_dir):
    twice = EVENTS + "2026-10-01 · event · a line was taken off the bench\n"
    (data_dir / "commons" / "events.md").write_text(twice, encoding="utf-8")
    assert script.main(["--apply"]) == 1
    assert events(data_dir) == twice
    assert not (data_dir / "commons" / "ledger.md").exists()


def test_an_empty_bench_file_is_removed_and_one_with_lines_is_left(script, data_dir):
    (data_dir / "commons" / "events.md").write_text(EVENTS, encoding="utf-8")
    bench = data_dir / "commons" / "bench.md"
    bench.write_text("", encoding="utf-8")
    script.main(["--apply"])
    assert not bench.exists()
    bench.write_text("- 2026-10-01 · birch · a line\n", encoding="utf-8")
    script.main(["--apply"])
    assert bench.exists()
