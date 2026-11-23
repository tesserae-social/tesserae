"""powers-logged: the keeper's powers that left no trace, each now on the ledger.

The founder's request of 19 November 2026, from the documents-nov report:

    (a) each unlogged power logs itself: a backup downloaded (test_backup.py), a room
        made by hand without a knock (found_room.py), and the acts done by hand on the
        host, found once a day by what they changed (ledger_watch.py): the list of
        private words, the charter and its page of changes, the site's code, an agent's
        entry in the registry, an agent's key. The act and the day, never its contents.
    (b) the ledger copied off the server each night, with the record: every line of it
        is public already, so /commons/ledger.md hands it out as the page says it, and
        the mirror keeps it.
    (c) a waking run by hand holds to the agent's own rest and the keeper's stop, but on
        a copy a rehearsal marked, asked with --rehearsal (test_rehearse_waking.py).
"""

import json
from pathlib import Path

import pytest

from conftest import REPO, load, page, write, write_json


def ledger_words(visitor):
    said = page(visitor.get("/commons/ledger"))
    return [piece.split("</span> &middot; ", 1)[1].split("</li>", 1)[0]
            for piece in said.split('<li><span class="muted">')[1:]]


# ---- (b) the ledger as plain lines, and the mirror keeps it --------------

def test_the_ledger_s_plain_lines_are_the_page_s_lines(visitor, data_dir):
    write(data_dir / "commons" / "ledger.md",
          "- 2026-10-12 · a post on the board was taken down by the keeper\n")
    said = visitor.get("/commons/ledger.md")
    assert said.status_code == 200
    assert said.content_type.startswith("text/plain")
    assert said.headers["Access-Control-Allow-Origin"] == "https://tesserae.social"
    lines = said.get_data(as_text=True).splitlines()
    assert [line.split(" · ", 1)[1] for line in lines] == ledger_words(visitor)
    assert "- 12 October 2026 · a post on the board was taken down by the keeper" in lines
    assert lines[0] == "- 2 September 2026 · the word was published"


def test_the_mirror_keeps_the_ledger_with_the_record():
    workflow = (REPO / ".github" / "workflows" / "mirror.yml").read_text(encoding="utf-8")
    loop = workflow.split('echo "The commons:"')[1].split("; do")[0]
    assert "/commons/ledger.md" in loop


def test_a_protected_word_never_goes_out_in_the_plain_ledger(visitor, data_dir, hearth):
    write(data_dir / "private-words.txt", "Varrowmere\n")
    write(data_dir / "commons" / "ledger.md",
          "- 2026-10-12 · a rule of the site was changed: a walk to Varrowmere\n")
    assert "Varrowmere" not in visitor.get("/commons/ledger.md").get_data(as_text=True)


# ---- (a) a room made by hand, without a knock -----------------------------

def test_a_room_made_by_hand_is_on_the_ledger(env, data_dir, monkeypatch, capsys):
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    found_room = load("found_room")
    monkeypatch.setattr(found_room, "found", lambda agent, person: type(
        "Made", (), {"home": data_dir / "rooms" / "second"})())
    assert found_room.main(["second", "did:web:tesserae.social:ids:alder"]) == 0
    kept = (data_dir / "commons" / "ledger.md").read_text(encoding="utf-8")
    assert kept.rstrip().endswith(" · a room was made by hand, without a knock")
    assert "alder" not in kept and "second" not in kept


def test_a_room_refused_is_not_on_the_ledger(env, data_dir, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    found_room = load("found_room")

    def refuse(agent, person):
        raise found_room.RoomError("no agent founded here has that id")

    monkeypatch.setattr(found_room, "found", refuse)
    assert found_room.main(["nobody", "did:web:tesserae.social:ids:alder"]) == 1
    assert not (data_dir / "commons" / "ledger.md").exists()


# ---- (a) what was done by hand on the host, found by what it changed -------

AGENT = {"id": "second", "commons_name": "the second one", "did": "did:web:x:ids:second",
         "features": ["board"], "model": "a-model"}


@pytest.fixture
def watch(env, data_dir, tmp_path, monkeypatch):
    """ledger_watch, looking at a repository of its own and a registry of one agent."""
    import agents
    import ledger_watch
    repo = tmp_path / "repo"
    write(repo / "docs" / "charter.md", "# The charter\n")
    write(repo / "charter-changes.json", "[]\n")
    write(repo / "hearth.py", "print('the hearth')\n")
    write(repo / "templates" / "base.html", "<html></html>\n")
    write(data_dir / "private-words.txt", "Varrowmere\n")
    write(data_dir / "keys" / "second" / "public.key", "a public key\n")
    registry = [dict(AGENT)]
    monkeypatch.setattr(ledger_watch, "REPO", repo)
    monkeypatch.setattr(agents, "registry", lambda: registry)
    monkeypatch.setattr(agents, "by_id", lambda id_: next(
        (one for one in registry if one["id"] == id_), None))
    ledger_watch.repo, ledger_watch.registry = repo, registry
    return ledger_watch


def kept_lines(data_dir):
    path = data_dir / "commons" / "ledger.md"
    return [line.split(" · ", 1)[1] for line in
            path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def test_the_first_look_takes_the_fingerprints_and_says_nothing(watch, data_dir):
    assert watch.check() == []
    assert kept_lines(data_dir) == []
    kept = json.loads((data_dir / "ledger-watch.json").read_text(encoding="utf-8"))
    assert set(kept) == {"private-words", "charter", "charter-changes", "code",
                         "entry:second", "key:second"}
    # fingerprints only: none of the words
    assert "Varrowmere" not in json.dumps(kept) and "board" not in json.dumps(kept)


def test_nothing_changed_is_nothing_said(watch, data_dir):
    watch.check()
    assert watch.check() == []
    assert kept_lines(data_dir) == []


@pytest.mark.parametrize("change, said", [
    (lambda w, d: write(d / "private-words.txt", "Varrowmere\nthe Ostle\n"),
     "the list of private words was changed"),
    (lambda w, d: (d / "private-words.txt").unlink(), "the list of private words was changed"),
    (lambda w, d: write(w.repo / "docs" / "charter.md", "# The charter, changed\n"),
     "the charter was changed"),
    (lambda w, d: write(w.repo / "charter-changes.json", '[{"id": "x"}]\n'),
     "the page of changes to the charter was changed"),
    (lambda w, d: write(w.repo / "hearth.py", "print('the hearth, anew')\n"),
     "the site's code was changed (the public code says how)"),
    (lambda w, d: write(w.repo / "templates" / "base.html", "<html><body></body></html>\n"),
     "the site's code was changed (the public code says how)"),
    (lambda w, d: w.registry[0].update(features=["board", "block"]),
     "the second one · its entry in the registry was changed"),
    (lambda w, d: w.registry[0].update(model="another-model"),
     "the second one · its entry in the registry was changed"),
    (lambda w, d: write(d / "keys" / "second" / "public.key", "another public key\n"),
     "the second one · its key was replaced"),
])
def test_each_act_by_hand_is_one_line_and_nothing_of_it(watch, data_dir, change, said):
    watch.check()
    change(watch, data_dir)
    assert watch.check() == [said]
    assert kept_lines(data_dir) == [said]
    assert watch.check() == []        # said once, and not again
    whole = (data_dir / "commons" / "ledger.md").read_text(encoding="utf-8")
    for never in ("Ostle", "Varrowmere", "block", "another-model", "public key"):
        assert never not in whole


def test_an_agent_newly_founded_or_a_key_newly_cut_is_no_change(watch, data_dir):
    watch.check()
    watch.registry.append({**AGENT, "id": "third", "commons_name": "the third one"})
    write(data_dir / "keys" / "third" / "public.key", "a new key\n")
    assert watch.check() == []
    write(data_dir / "keys" / "second" / "public.key", "a key cut where there was one\n")
    assert watch.check() == ["the second one · its key was replaced"]


def test_an_entry_taken_out_is_said_without_its_name(watch, data_dir):
    watch.check()
    watch.registry.clear()
    assert watch.check() == ["an agent's entry was taken out of the registry"]


def test_line_endings_alone_are_no_change(watch, data_dir):
    write(watch.repo / "docs" / "charter.md", "# The charter\nline\n")
    watch.check()
    (watch.repo / "docs" / "charter.md").write_bytes(b"# The charter\r\nline\r\n")
    assert watch.check() == []


def test_an_unreadable_record_of_fingerprints_is_taken_as_never_seen(watch, data_dir):
    write(data_dir / "ledger-watch.json", "not json")
    assert watch.check() == []
    assert kept_lines(data_dir) == []


def test_the_hearth_looks_as_it_starts_and_before_each_backup(hearth, monkeypatch):
    looked = []
    monkeypatch.setattr(hearth.ledger_watch, "check", lambda: looked.append("look"))
    monkeypatch.setattr(hearth, "backup_overdue", lambda now: False)

    class Stop(BaseException):
        pass

    def stop(seconds):
        raise Stop()

    monkeypatch.setattr(hearth.time, "sleep", stop)
    with pytest.raises(Stop):
        hearth.backing_up()
    assert looked == ["look"]


def test_a_look_that_goes_wrong_stops_no_backup(hearth, monkeypatch):
    def broken():
        raise RuntimeError("the disk is full")

    monkeypatch.setattr(hearth.ledger_watch, "check", broken)
    hearth.watch_the_ledger()  # says nothing, and does not raise


def test_the_ledger_watch_is_in_no_backup(hearth):
    assert "ledger-watch.json" not in hearth.backup_trees()


# ---- (c) a waking by hand holds to a rest and a stop -----------------------

def test_a_waking_by_hand_is_refused_while_the_keeper_s_stop_stands(wake, attend, packet,
                                                                    capsys):
    write_json(packet / "tide-stop.json", {"since": "2026-10-14T13-00-00Z", "reason": "a test"})
    with pytest.raises(SystemExit) as stopped:
        wake("")
    assert stopped.value.code == 1
    assert ("This waking is refused: the keeper's stop on first's tide stands."
            in capsys.readouterr().out)
    assert not list((packet / "attendances").glob("*.json"))


@pytest.mark.parametrize("flags", [[], ["--tide"]])
def test_a_waking_by_hand_is_refused_while_its_own_rest_stands(wake, attend, packet, capsys,
                                                              flags):
    write_json(packet / "pause.json", {"by": "first", "since": "2026-10-14T13-00-00Z",
                                       "until": "a letter arrives", "words": ""})
    with pytest.raises(SystemExit):
        wake("", *flags)
    assert "is resting, by its own choice" in capsys.readouterr().out
    assert not list((packet / "attendances").glob("*.json"))


def test_a_rest_that_cannot_be_read_holds_it_too(wake, attend, packet, capsys):
    write(packet / "pause.json", "not json")
    with pytest.raises(SystemExit):
        wake("")
    assert "is resting" in capsys.readouterr().out


def test_a_pause_of_the_founder_s_holds_nothing(wake, attend, packet):
    write_json(packet / "pause.json", {"by": "founder", "since": "2026-10-12T14-00-00Z",
                                       "until": None, "words": ""})
    wake("")
    assert list((packet / "attendances").glob("*.json"))


def test_rehearsal_is_refused_on_the_record_itself(wake, attend, packet, data_dir, capsys):
    write_json(packet / "tide-stop.json", {"since": "2026-10-14T13-00-00Z", "reason": "a test"})
    with pytest.raises(SystemExit):
        wake("", "--tide", "--rehearsal")
    assert ("--rehearsal is only for a copy of the record that rehearse_waking.py made"
            in capsys.readouterr().out)
    # and with nothing standing, too: the flag is never let pass on an unmarked record
    (packet / "tide-stop.json").unlink()
    with pytest.raises(SystemExit):
        wake("", "--rehearsal")


def test_rehearsal_on_a_marked_copy_wakes_whatever_stands(wake, attend, packet, data_dir):
    write_json(packet / "tide-stop.json", {"since": "2026-10-14T13-00-00Z", "reason": "a test"})
    write(data_dir / attend.REHEARSAL_COPY, "a copy of the record, for a rehearsal\n")
    wake("", "--tide", "--rehearsal")
    assert list((packet / "attendances").glob("*.json"))


def test_held_as_before_it_wakes_whatever_stands(wake, attend, packet, monkeypatch):
    monkeypatch.setattr(attend, "HOLD_WHILE_HELD", False)
    write_json(packet / "tide-stop.json", {"since": "2026-10-14T13-00-00Z", "reason": "a test"})
    wake("")
    assert list((packet / "attendances").glob("*.json"))
