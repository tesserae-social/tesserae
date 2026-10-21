"""The commit guard: check_private_words.py, which the pre-commit hook runs.

Each test makes a small repository of its own, in a temporary folder, with a
list of its own beside it; the guard is run there as the hook runs it. The
names are made up, as in test_private_words.py.
"""

import subprocess
import sys

import pytest

from conftest import REPO

GUARD = REPO / "check_private_words.py"
LIST = "Quillon => the founder\n# a note\n\nVarrowmere\nthe Ostle\n"


def git(where, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                           "-c", "core.autocrlf=false", *args],
                          cwd=where, capture_output=True, check=True)


@pytest.fixture
def repository(tmp_path):
    where = tmp_path / "repository"
    where.mkdir()
    git(where, "init", "-q")
    return where


@pytest.fixture
def listing(tmp_path):
    path = tmp_path / "words.txt"
    path.write_text(LIST, encoding="utf-8")
    return path


def staged(where, name, text):
    path = where / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    git(where, "add", name)


def guard(where, listing):
    ran = subprocess.run([sys.executable, str(GUARD), "--list", str(listing)], cwd=where,
                         capture_output=True)
    return ran.returncode, ran.stdout.decode("utf-8") + ran.stderr.decode("utf-8")


def test_nothing_protected_is_let_through(repository, listing):
    staged(repository, "notes.md", "a quiet day\nnothing named\n")
    assert guard(repository, listing) == (0, "")


def test_a_protected_word_stops_the_commit_by_file_and_line_and_never_says_it(
        repository, listing):
    staged(repository, "notes.md", "a quiet day\nwalked to varrowmere\nhome again\n")
    staged(repository, "deep/er.py", "# QUILLON wrote this\n")
    code, said = guard(repository, listing)
    assert code == 1
    assert "notes.md:2" in said and "deep/er.py:1" in said
    assert "arrowmere" not in said.lower() and "quillon" not in said.lower()


def test_a_word_of_more_than_one_word_is_found(repository, listing):
    staged(repository, "notes.md", "back from the\tOstle today\n")
    assert guard(repository, listing)[0] == 1


@pytest.mark.parametrize("line", ["Quillonia", "Varrowmeres", "theOstle", "an ostler"])
def test_only_whole_words_are_protected(repository, listing, line):
    staged(repository, "notes.md", line + "\n")
    assert guard(repository, listing)[0] == 0


def test_only_the_lines_the_commit_adds_are_read_and_numbered_as_they_will_stand(
        repository, listing):
    staged(repository, "notes.md", "one\nQuillon, long ago\nthree\n")
    git(repository, "commit", "-q", "--no-verify", "-m", "before the guard")
    staged(repository, "notes.md", "one\nQuillon, long ago\nthree\nfour\n")
    assert guard(repository, listing)[0] == 0
    staged(repository, "notes.md", "one\nQuillon, long ago\nthree\nfour\nto Varrowmere\n")
    code, said = guard(repository, listing)
    assert code == 1 and "notes.md:5" in said and "notes.md:2" not in said


def test_what_is_not_staged_is_not_read(repository, listing):
    staged(repository, "notes.md", "a quiet day\n")
    (repository / "notes.md").write_text("a quiet day at Varrowmere\n", encoding="utf-8")
    (repository / "loose.md").write_text("Quillon\n", encoding="utf-8")
    assert guard(repository, listing)[0] == 0


def test_a_line_that_begins_like_a_file_s_heading_is_still_read(repository, listing):
    staged(repository, "notes.md", "++ Quillon\n")
    code, said = guard(repository, listing)
    assert code == 1 and "notes.md:1" in said


def test_with_no_list_it_warns_once_and_lets_the_commit_through(repository, tmp_path):
    staged(repository, "notes.md", "Quillon at Varrowmere\n")
    code, said = guard(repository, tmp_path / "no-such-list.txt")
    assert code == 0
    assert said.count("no list of protected words") == 1


def test_by_default_the_list_is_kept_outside_the_repository():
    import check_private_words
    assert check_private_words.LIST.name == "tesserae-private-words.txt"
    assert REPO not in check_private_words.LIST.parents
