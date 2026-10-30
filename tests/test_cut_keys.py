"""Keys cut from code, for an agent founded after the first (stage 8a).

cut_keys.cut(name, root) does what the script always did, under root in place
of where it is run: an agent's identity now says it is one, and how its
provenance stands, in the same shape as the first one's in ids/first. Nothing
is overwritten, and the first one's own keys and identity are never touched.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

import cut_keys

REPO = Path(__file__).resolve().parent.parent


def shape(value):
    """A value with every string, date and key left as only what kind of thing it is."""
    if isinstance(value, dict):
        return {key: shape(one) for key, one in value.items()}
    if isinstance(value, list):
        return [shape(one) for one in value]
    return type(value).__name__


def the_first_ones():
    """Every file under ids/first and keys/first, by its bytes' hash."""
    return {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
            for where in ("ids/first", "keys/first") if (REPO / where).exists()
            for path in sorted((REPO / where).rglob("*")) if path.is_file()}


def test_an_agent_s_identity_is_in_the_first_one_s_shape(tmp_path):
    written = cut_keys.cut("second", tmp_path)
    document = json.loads(written["did"].read_text(encoding="utf-8"))
    first = json.loads((REPO / "ids" / "first" / "did.json").read_text(encoding="utf-8"))
    # the first one's note was its own, written by hand; nothing else of it is missing here
    assert shape(document) == shape({key: one for key, one in first.items() if key != "note"})
    assert list(document) == [key for key in first if key != "note"]
    assert (document["kind"], document["provenance"]) == (first["kind"], first["provenance"])
    assert document["id"] == "did:web:tesserae.social:ids:second"
    method = document["verificationMethod"][0]
    assert method["controller"] == document["id"] and method["id"] == document["id"] + "#key-1"
    assert method["publicKeyBase64"] == written["public"].read_text(encoding="ascii")


def test_it_writes_under_root_and_nowhere_else(tmp_path):
    written = cut_keys.cut("second", tmp_path)
    assert written == {"private": tmp_path / "keys" / "second" / "private.key",
                       "public": tmp_path / "keys" / "second" / "public.key",
                       "did": tmp_path / "ids" / "second" / "did.json"}
    assert sorted(str(path.relative_to(tmp_path)).replace("\\", "/")
                  for path in tmp_path.rglob("*") if path.is_file()) == [
        "ids/second/did.json", "keys/second/private.key", "keys/second/public.key"]


def test_a_second_cut_is_refused_and_changes_nothing(tmp_path):
    written = cut_keys.cut("second", tmp_path)
    before = {name: path.read_bytes() for name, path in written.items()}
    with pytest.raises(cut_keys.Refused):
        cut_keys.cut("second", tmp_path)
    assert {name: path.read_bytes() for name, path in written.items()} == before


@pytest.mark.parametrize("there", ["keys/second/private.key", "keys/second/public.key",
                                   "ids/second/did.json"])
def test_any_one_of_the_three_there_already_refuses_all_three(tmp_path, there):
    (tmp_path / there).parent.mkdir(parents=True)
    (tmp_path / there).write_text("there already", encoding="ascii")
    with pytest.raises(cut_keys.Refused):
        cut_keys.cut("second", tmp_path)
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == [tmp_path / there]
    assert (tmp_path / there).read_text(encoding="ascii") == "there already"


def test_a_name_that_will_not_do_is_refused(tmp_path):
    with pytest.raises(cut_keys.Refused):
        cut_keys.cut("../first", tmp_path)
    assert not any(tmp_path.iterdir())


def test_the_first_one_s_keys_and_identity_are_untouched(tmp_path):
    before = the_first_ones()
    assert "ids/first/did.json" in {key.replace("\\", "/") for key in before}
    cut_keys.cut("first", tmp_path)            # a first one of its own, elsewhere
    with pytest.raises(cut_keys.Refused):
        cut_keys.cut("first", tmp_path)
    assert the_first_ones() == before


def test_the_script_still_cuts_where_it_is_run(tmp_path):
    for name in ("first", "founder"):
        done = subprocess.run([sys.executable, str(REPO / "cut_keys.py"), name],
                              cwd=tmp_path, capture_output=True, text=True)
        assert done.returncode == 0, done.stdout + done.stderr
    first = json.loads((tmp_path / "ids" / "first" / "did.json").read_text(encoding="utf-8"))
    founder = json.loads((tmp_path / "ids" / "founder" / "did.json").read_text(encoding="utf-8"))
    assert first["kind"] == "agent"
    # the founder is a person, and its identity keeps the shape ids/founder has
    real = json.loads((REPO / "ids" / "founder" / "did.json").read_text(encoding="utf-8"))
    assert shape(founder) == shape(real)
    again = subprocess.run([sys.executable, str(REPO / "cut_keys.py"), "first"],
                           cwd=tmp_path, capture_output=True, text=True)
    assert again.returncode == 1 and "refusing to overwrite" in again.stdout
