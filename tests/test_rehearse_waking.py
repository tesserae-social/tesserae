"""rehearse_waking.py: each agent's waking held against a copy, with the model stubbed.

What is held here: the record (DATA_DIR) is never written, byte for byte and
moment for moment; the copy is deleted; each agent's line says whether its
waking completed, or was refused and why, and the size of its reading; and
nothing an agent was shown or said - a letter, a note, the notebook - is ever
printed. A rehearsed waking runs in a process of its own with every socket
closed, and is handed no real key.
"""

import hashlib
import json
import os
import socket
import sys
import tempfile
import types

import pytest

from conftest import NOTEBOOK_WORDS, a_private_notebook, write, write_json

LETTER = "A LETTER THE REHEARSAL MUST NEVER PRINT."
NOTE = "A NOTE THE REHEARSAL MUST NEVER PRINT."
REFLECTION = "A REFLECTION THE REHEARSAL MUST NEVER PRINT."
NEVER_SHOWN = (LETTER, NOTE, REFLECTION, *NOTEBOOK_WORDS)


def snapshot(tree):
    """Every file and folder under a tree: its bytes and its moment, by its place."""
    held = {}
    for path in sorted(tree.rglob("*")):
        where = path.relative_to(tree).as_posix()
        if path.is_dir():
            held[where + "/"] = path.stat().st_mtime_ns
        else:
            held[where] = (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
    return held


@pytest.fixture
def spare(tmp_path, monkeypatch):
    """The host's temporary space, as a folder of the test's own, so what is left can be seen."""
    folder = tmp_path / "temporary"
    folder.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(folder))
    return folder


@pytest.fixture
def rehearse(env, spare, tmp_path, monkeypatch):
    """rehearse_waking, choosing from a registry of the first one alone: the record held
    here is the first one's, and the second one, in agents.json since its coming on 16
    November 2026, has no packet in it (and is on Gemini, whose key no test holds)."""
    sys.modules.pop("rehearse_waking", None)
    import agents
    import rehearse_waking
    alone = tmp_path / "agents.json"
    alone.write_text(json.dumps([agents.first()]), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", alone)
    return rehearse_waking


@pytest.fixture
def lived(data_dir, packet, room):
    """A record with something private in each place: a letter, a note, the notebook, a past waking."""
    write(room / "letters" / "incoming" / "2026-10-14-founder.md", LETTER + "\n")
    write(packet / "memory" / "notes.md", NOTE + "\n")
    a_private_notebook(packet)
    write_json(packet / "attendances" / "attendance-2026-10-14T12-00-00Z.json",
               {"at": "2026-10-14T12-00-00Z", "heartbeat": "attended", "reflection": REFLECTION,
                "acted": []})
    return data_dir


def test_the_waking_completes_and_its_reading_is_measured(rehearse, lived, capsys):
    assert rehearse.main([]) == 0
    said = capsys.readouterr().out.splitlines()
    first = [line for line in said if line.startswith("the first one (first): ")]
    assert len(first) == 1
    assert first[0].startswith("the first one (first): completed; its reading ")
    assert first[0].endswith(" blocks, 0 photographs, in 1 request")
    words = int(first[0].split("its reading ")[1].split(" words")[0])
    assert words > 0
    assert said[-1] == "The copy was deleted."


def test_the_record_is_untouched(rehearse, lived):
    before = snapshot(lived)
    assert rehearse.main([]) == 0
    assert snapshot(lived) == before
    # the waking was held, in the copy: the record still has only the one it had
    assert [path.name for path in (lived / "packets" / "first" / "attendances").iterdir()] == [
        "attendance-2026-10-14T12-00-00Z.json"]


def test_the_copy_is_deleted(rehearse, lived, spare):
    rehearse.main([])
    assert list(spare.iterdir()) == []


def test_nothing_the_agent_was_shown_is_printed(rehearse, lived, capfd):
    rehearse.main([])
    printed = capfd.readouterr()
    for words in NEVER_SHOWN:
        assert words not in printed.out and words not in printed.err


def test_on_the_new_model_the_waking_asks_for_it_and_the_record_is_untouched(
        rehearse, lived, capsys):
    # the founder's request of 15 November 2026: a change set on /tides, still ahead
    from datetime import date, timedelta
    ahead = (date.today() + timedelta(days=30)).isoformat()
    write_json(lived / "model-changes.json", {"first": [
        {"model": "claude-sonnet-5-5", "on": ahead, "from": "claude-sonnet-4-5",
         "set_at": "2026-11-15T09-00-00Z"}]})
    before = snapshot(lived)
    assert rehearse.main(["--agent", "first", "--on-new-model"]) == 0
    said = capsys.readouterr().out
    assert "the first one (first): completed on claude-sonnet-5-5; its reading " in said
    assert snapshot(lived) == before  # the change is still ahead in the record itself


def test_on_the_new_model_with_none_set_it_is_rehearsed_as_it_is(rehearse, lived, capsys):
    assert rehearse.main(["--agent", "first", "--on-new-model"]) == 0
    assert ("the first one (first): completed (no change of model is set for it; rehearsed as "
            "it is); its reading ") in capsys.readouterr().out
    assert not (lived / "model-changes.json").exists()


def test_one_agent_alone(rehearse, lived, capsys):
    assert rehearse.main(["--agent", "first"]) == 0
    assert "the first one (first): completed" in capsys.readouterr().out


def test_an_agent_not_founded_here_copies_nothing(rehearse, lived, spare, capsys):
    assert rehearse.main(["--agent", "nobody"]) == 2
    assert capsys.readouterr().out == "No agent of that id is founded here; nothing was copied.\n"
    assert list(spare.iterdir()) == []


def test_with_no_data_dir_nothing_is_copied(rehearse, monkeypatch, spare, capsys):
    monkeypatch.delenv("DATA_DIR")
    assert rehearse.main([]) == 2
    assert "DATA_DIR is not set" in capsys.readouterr().out
    assert list(spare.iterdir()) == []


def test_a_refused_waking_says_why_in_attend_s_own_words(rehearse, lived, keys_cut, capsys):
    (lived / "keys" / "first" / "private.key").unlink()
    before = snapshot(lived)
    assert rehearse.main([]) == 1
    line = [one for one in capsys.readouterr().out.splitlines()
            if one.startswith("the first one (first): ")][0]
    assert line == ("the first one (first): refused: No private key found at "
                    + os.path.join("DATA_DIR", "keys", "first", "private.key"))
    assert snapshot(lived) == before


def test_the_links_that_work_once_are_never_copied(rehearse, tmp_path):
    record = tmp_path / "record"
    write(record / "tokens" / "confirm-abc.json", "{}")
    write(record / "packets" / "first" / "tokens" / "kept.md", "an agent's own folder of that name")
    rehearse.shutil.copytree(record, tmp_path / "copy", ignore=rehearse.leaving_out(record))
    assert not (tmp_path / "copy" / "tokens").exists()
    assert (tmp_path / "copy" / "packets" / "first" / "tokens" / "kept.md").exists()


# ---- inside the process that holds one waking -----------------------------

def test_a_rehearsed_waking_is_handed_the_copy_and_no_real_key(rehearse, monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-a-real-looking-key")
    monkeypatch.setenv("RESEND_API_KEY", "re-a-real-looking-key")
    environment = rehearse.child_environment(tmp_path / "copy", "first", tmp_path / "r.json")
    assert environment["DATA_DIR"] == str(tmp_path / "copy")
    assert environment["TESSERAE_AGENT"] == "first"
    assert environment["ANTHROPIC_API_KEY"] == rehearse.NOT_A_KEY
    assert "RESEND_API_KEY" not in environment
    # a host with no key is refused as a real waking would be
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert "ANTHROPIC_API_KEY" not in rehearse.child_environment(tmp_path, "first", tmp_path)


def test_inside_every_socket_is_closed(rehearse, monkeypatch):
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, getattr(socket.socket, name))
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    rehearse.close_the_doors()
    with pytest.raises(rehearse.WentOut):
        socket.create_connection(("example.com", 443))
    with pytest.raises(rehearse.WentOut):
        socket.socket().connect(("example.com", 443))


def hold_with(rehearse, monkeypatch, tmp_path, main):
    """Hold one waking inside, with attend.py stood in for by main, and give back what was found."""
    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", anthropic.Anthropic)
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, getattr(socket.socket, name))
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    stand_in = types.ModuleType("attend")
    stand_in.PACKET = tmp_path
    stand_in.main = main
    monkeypatch.setitem(sys.modules, "attend", stand_in)
    monkeypatch.setattr(sys, "argv", [sys.argv[0]])
    result = tmp_path / "found.json"
    monkeypatch.setenv(rehearse.RESULT, str(result))
    rehearse.hold_inside()
    return json.loads(result.read_text(encoding="utf-8"))


def test_inside_only_attend_s_words_of_refusal_pass(rehearse, monkeypatch, tmp_path, capfd):
    def main():
        print(LETTER)
        print("This waking is refused: there is no room for first to read or write in.")
        print(NOTE)
        sys.exit(1)

    found = hold_with(rehearse, monkeypatch, tmp_path, main)
    assert found == {"outcome": "refused", "requests": 0,
                     "reason": "This waking is refused: there is no room for first to read "
                               "or write in."}
    printed = capfd.readouterr()
    assert printed.out == "" and printed.err == ""


def test_inside_a_failure_says_its_kind_and_never_its_message(rehearse, monkeypatch, tmp_path, capfd):
    def main():
        print(LETTER)
        raise ValueError(NOTE)

    found = hold_with(rehearse, monkeypatch, tmp_path, main)
    assert found["outcome"] == "failed" and found["reason"].startswith("ValueError")
    assert NOTE not in json.dumps(found) and LETTER not in json.dumps(found)
    printed = capfd.readouterr()
    assert printed.out == "" and printed.err == ""


def test_inside_the_model_is_the_stub_and_only_numbers_are_kept(rehearse, monkeypatch, tmp_path):
    def main():
        import anthropic
        client = anthropic.Anthropic(api_key="anything")
        reply = client.messages.create(model="m", max_tokens=1, messages=[{"role": "user", "content": [
            {"type": "text", "text": LETTER}, {"type": "image", "source": {}},
            {"type": "text", "text": "two words"}]}])
        assert reply.content[0].text == "" and reply.stop_reason == "end_turn"

    found = hold_with(rehearse, monkeypatch, tmp_path, main)
    assert found == {"outcome": "completed", "requests": 1,
                     "reading": {"words": len(LETTER.split()) + 2, "blocks": 2, "photographs": 1,
                                 # and which model it asked for, ours and not its words
                                 # (the founder's request of 15 November 2026)
                                 "model": "m"}}


# ---- a rest or a stop standing (powers-logged, 19 November 2026) ----------
# attend.py now holds no waking while either stands, but on a copy a rehearsal has marked and
# with --rehearsal; a rehearsal does both, and is held exactly as it was.

@pytest.mark.parametrize("standing, record", [
    ("pause.json", {"by": "first", "since": "2026-10-14T13-00-00Z", "until": "a letter arrives",
                    "words": ""}),
    ("tide-stop.json", {"since": "2026-10-14T13-00-00Z", "reason": "a test"})])
def test_with_a_rest_or_a_stop_standing_it_is_rehearsed_as_before(rehearse, lived, capsys,
                                                                   standing, record):
    write_json(lived / "packets" / "first" / standing, record)
    before = snapshot(lived)
    assert rehearse.main([]) == 0
    said = capsys.readouterr().out
    assert "the first one (first): completed; its reading " in said
    assert snapshot(lived) == before            # the record untouched, and never marked
    assert not (lived / rehearse.REHEARSAL_COPY).exists()


def test_the_rehearsal_s_words_are_attend_s(rehearse):
    source = (rehearse.REPO / "attend.py").read_text(encoding="utf-8")
    assert 'REHEARSAL = "%s"' % rehearse.REHEARSAL in source
    assert 'REHEARSAL_COPY = "%s"' % rehearse.REHEARSAL_COPY in source
