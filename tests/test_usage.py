"""What each waking costs: kept privately, in numbers, and read only on the host.

From 31 October 2026 an attendance keeps the four token counts of every request
it made, as "usage", and their sums, as "usage_total", wherever a reply carries
them. The test stubs carry none, so what they leave is what they always left,
which the stage 0 fingerprints hold. Here a stub that does carry them shows they
are kept exactly, and go nowhere else: not to the agent, not to a page, not to
the keeper. usage_report.py counts them, and prints labels and numbers alone.
"""

import json
import re
import shutil
import subprocess
import sys
from datetime import timedelta
from types import SimpleNamespace

import pytest

from conftest import REPO, load, page, post, read_json, shut_away, verify, write_json
from test_longer_waking import Exchange, look
from test_rooms_reading import ERRAND, READING_NOW, a_small_world, fingerprint_of_reading

COUNTS = ("input_tokens", "output_tokens",
          "cache_creation_input_tokens", "cache_read_input_tokens")

# a number that appears nowhere else, to be looked for
MARKED = 7654321


def cost(*numbers):
    return dict(zip(COUNTS, numbers))


class Costed(Exchange):
    """A stubbed waking whose replies each carry a usage, or None for none, in order."""

    def __init__(self, *replies, usages):
        super().__init__(*replies)
        self.usages = list(usages)

    def client(self, **ignored):
        costed, stubbed = self, super().client()

        class Messages:
            def create(self, **asked):
                reply = stubbed.messages.create(**asked)
                usage = costed.usages.pop(0)
                if usage is not None:
                    reply.usage = usage
                return reply

        return SimpleNamespace(messages=Messages())


def usage(*numbers, **more):
    return SimpleNamespace(**cost(*numbers), **more)


@pytest.fixture
def costed(attend, clock, monkeypatch):
    """Hold one attendance whose replies carry what they are given."""
    def hold(*replies, usages):
        exchange = Costed(*replies, usages=usages)
        monkeypatch.setattr(attend, "Anthropic", exchange.client)
        monkeypatch.setattr(sys, "argv", ["attend.py"])
        attend.main()
        clock.shift(minutes=5)
        return exchange
    return hold


def latest(packet):
    return read_json(sorted((packet / "attendances").glob("*.json"))[-1])


# ---- what a waking keeps ---------------------------------------------------

def test_every_round_of_a_longer_waking_is_kept_exactly(costed, packet):
    costed(look(("read_founding", {})), look(("read_founding", {})), "I am here.",
           usages=[usage(1000, 20, 900, 0), usage(1100, 30, 50, 900), usage(1200, 400, 60, 950)])
    record = latest(packet)
    assert record["rounds"] == 3
    assert record["usage"] == [cost(1000, 20, 900, 0), cost(1100, 30, 50, 900),
                               cost(1200, 400, 60, 950)]
    assert record["usage_total"] == cost(3300, 450, 1010, 1850)


def test_the_last_request_with_the_tools_closed_is_counted_too(costed, attend, packet):
    looks = [look(("read_founding", {}))] * attend.LOOKS_MOST
    costed(*looks, "I am here.", usages=[usage(n, 1, 0, 0) for n in range(1, 7)])
    assert [entry["input_tokens"] for entry in latest(packet)["usage"]] == [1, 2, 3, 4, 5, 6]


def test_a_waking_of_one_request_is_kept_as_one_entry(costed, attend, packet, monkeypatch):
    shut_away(attend, monkeypatch, "LONGER_WAKING")
    costed("I am here.", usages=[usage(5, 6, 7, 8)])
    assert latest(packet)["usage"] == [cost(5, 6, 7, 8)]
    assert latest(packet)["usage_total"] == cost(5, 6, 7, 8)


def test_what_it_keeps_is_numbers_and_nothing_else(costed, packet):
    """A count the API leaves empty is none used, and nothing else a usage carries is kept."""
    costed("I am here.", usages=[usage(5, 6, None, None, service_tier="WORDS NOT TO KEEP")])
    record = latest(packet)
    assert record["usage"] == [cost(5, 6, 0, 0)]
    assert list(record["usage"][0]) == list(COUNTS)
    assert b"WORDS NOT TO KEEP" not in next((packet / "attendances").glob("*.json")).read_bytes()


def test_a_reply_without_usage_writes_no_field(costed, wake, packet):
    costed("I am here.", usages=[None])
    assert not {"usage", "usage_total"} & set(latest(packet))
    wake("I am here.")
    assert not {"usage", "usage_total"} & set(latest(packet))


def test_it_is_inside_what_is_signed(costed, packet, keys):
    costed("I am here.", usages=[usage(5, 6, 7, 8)])
    record = latest(packet)
    signature = record.pop("signature")
    payload = json.dumps(record, sort_keys=True).encode("utf-8")
    assert verify(keys.first_public, payload, signature)


# ---- where it never goes ---------------------------------------------------

def test_the_reading_with_usage_is_the_reading_as_it_reads_now(founder, costed, attend, room):
    a_small_world(room)
    answer = post(founder, "/letters", content_type="multipart/form-data", data={
        "letter": "The lake was grey this morning, and then it was not.\n\nI am asking.",
        "thing": ["cold hands", "", "a heron on the far bank"],
        "errand": ERRAND, "proposes": "1"})
    assert answer.status_code == 302
    assert fingerprint_of_reading(costed("", usages=[usage(MARKED, 1, 2, 3)])) == READING_NOW


def test_a_waking_after_one_with_usage_reads_what_it_would_have_read(
        costed, clock, data_dir, packet, tmp_path, capsys):
    costed("I am here.", usages=[usage(MARKED, MARKED, MARKED, MARKED)])
    assert str(MARKED) not in capsys.readouterr().out  # nor is it printed at the waking
    held, when = tmp_path / "held", clock.at
    shutil.copytree(data_dir, held)

    with_usage = fingerprint_of_reading(costed("", usages=[None]))

    shutil.rmtree(data_dir)
    shutil.copytree(held, data_dir)
    clock.set(when)
    path = sorted((packet / "attendances").glob("*.json"))[-1]
    record = read_json(path)
    assert str(MARKED) in json.dumps(record)
    del record["usage"], record["usage_total"]
    write_json(path, record)
    turn = costed("", usages=[None])
    assert fingerprint_of_reading(turn) == with_usage
    assert str(MARKED) not in json.dumps(turn.asked[-1], default=str)


def test_no_page_shows_it_nor_the_keeper_s_list(hearth, founder, packet):
    write_json(packet / "attendances" / "attendance-2026-10-14T09-00-00Z.json", {
        "name": "first", "at": "2026-10-14T09-00-00Z", "acted": [], "heartbeat": "attended",
        "usage": [cost(MARKED, MARKED, MARKED, MARKED)],
        "usage_total": cost(MARKED, MARKED, MARKED, MARKED)})
    for path in ("/attendances", "/chronicle", "/self", "/"):
        said = page(founder.get(path))
        assert str(MARKED) not in said and "input_tokens" not in said
    first = hearth.agents.first()
    assert str(MARKED) not in repr(hearth.keeper_records(first))
    assert sorted(hearth.keeper_records(first)[0]) == [
        "acted", "at", "faults", "first", "heartbeat", "model", "woken"]


# ---- usage_report.py -------------------------------------------------------

@pytest.fixture
def report(env, clock, monkeypatch, capsys):
    """usage_report.py's main, as run for an agent, and what it printed."""
    module = load("usage_report")
    clock.pin(module, monkeypatch)

    def run(*argv):
        assert module.main(list(argv)) == 0
        return capsys.readouterr().out
    run.module = module
    return run


def a_waking(packet, stamp, *total, **more):
    return write_json(packet / "attendances" / ("attendance-%s.json" % stamp),
                      {"usage_total": cost(*total), **more})


def test_the_report_says_each_count(report, packet, clock):
    recent = clock.at - timedelta(days=3)
    a_waking(packet, recent.strftime("%Y-%m-%dT%H-%M-%SZ"), 600, 60, 6, 0)
    a_waking(packet, "2026-10-08T12-00-00Z", 200, 40, 2, 10)  # seven days to the moment
    a_waking(packet, "2026-10-08T11-59-59Z", 100, 30, 1, 20)  # one second more
    write_json(packet / "attendances" / "attendance-2026-10-09T09-00-00Z.json", {"at": "no usage"})
    assert report().splitlines() == [
        "wakings with usage recorded: 3",
        "input_tokens: average 300.0, median 200.0, maximum 600, last 7 days 800",
        "output_tokens: average 43.3, median 40.0, maximum 60, last 7 days 100",
        "cache_creation_input_tokens: average 3.0, median 2.0, maximum 6, last 7 days 8",
        "cache_read_input_tokens: average 10.0, median 10.0, maximum 20, last 7 days 10",
    ]


def test_the_report_with_nothing_recorded_says_so_in_numbers(report):
    assert report().splitlines()[0] == "wakings with usage recorded: 0"
    assert "average 0.0, median 0.0, maximum 0, last 7 days 0" in report()


LINE = re.compile(r"wakings with usage recorded: \d+|(%s): average \d+\.\d, median \d+\.\d, "
                  r"maximum \d+, last 7 days \d+" % "|".join(COUNTS))


def test_the_report_prints_only_numbers(env, packet):
    """Run as it is on the host, on a record with words wherever words may be."""
    words = "WORDS THAT ARE NEVER PRINTED"
    a_waking(packet, "2026-10-14T09-00-00Z", 1, 2, 3, 4, reflection=words, heartbeat=words,
             acted=[words], usage=[{"input_tokens": words}])
    write_json(packet / "attendances" / "attendance-2026-10-14T10-00-00Z.json",
               {"usage_total": {"input_tokens": words}})
    (packet / "attendances" / "attendance-2026-10-14T11-00-00Z.json").write_text(words)
    done = subprocess.run([sys.executable, str(REPO / "usage_report.py"), "first"],
                          capture_output=True, text=True)
    assert done.returncode == 0 and done.stderr == ""
    lines = done.stdout.splitlines()
    assert len(lines) == 5 and all(LINE.fullmatch(line) for line in lines)
    assert lines[0] == "wakings with usage recorded: 1"


def test_the_report_reads_no_other_field(report, packet, monkeypatch):
    a_waking(packet, "2026-10-14T09-00-00Z", 1, 2, 3, 4, reflection="words", at="words")
    read = []

    class Watched(dict):
        def _read(self, key):
            read.append(key)

        def get(self, key, default=None):
            self._read(key)
            return super().get(key, default)

        def __getitem__(self, key):
            self._read(key)
            return super().__getitem__(key)

        def __iter__(self):
            raise AssertionError("a record was walked")

        items = keys = values = __iter__

    real = json.loads

    def watched(text, **how):  # the registry, a list, is read this way too, and is left
        said = real(text, **how)
        return Watched(said) if isinstance(said, dict) else said

    monkeypatch.setattr(report.module.json, "loads", watched)
    report()
    assert read == ["usage_total"]


def test_the_report_counts_the_same_four_attend_keeps(report, attend):
    assert report.module.COUNTS == attend.USAGE_COUNTS == COUNTS


def test_the_report_is_for_the_agent_named_and_refuses_one_not_founded(report, packet, capsys):
    a_waking(packet, "2026-10-14T09-00-00Z", 1, 2, 3, 4)
    assert report("first") == report()
    assert report.module.main(["../first"]) == 1
    assert report.module.main(["no-such-agent"]) == 1
    assert "no-such-agent" not in capsys.readouterr().out
