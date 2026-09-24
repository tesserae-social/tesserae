"""The identity documents in the repository, as GitHub Pages serves them: plain
UTF-8 with no byte-order mark, so that a strict JSON reader takes them as they are.
The documents in docs/ likewise carry no byte-order mark.
"""

import json
from pathlib import Path

import pytest

IDS = Path(__file__).resolve().parent.parent / "ids"
DOCUMENTS = sorted(path for path in IDS.rglob("*") if path.is_file())
DOCS = Path(__file__).resolve().parent.parent / "docs"
DOCS_PAGES = sorted(DOCS.glob("*.md"))


def test_there_are_documents_to_check():
    assert DOCUMENTS


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda path: path.relative_to(IDS).as_posix())
def test_no_identity_document_starts_with_a_byte_order_mark(path):
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda path: path.relative_to(IDS).as_posix())
def test_every_identity_document_parses_as_plain_utf8_json(path):
    json.loads(path.read_bytes().decode("utf-8"))


def test_there_are_docs_to_check():
    assert DOCS_PAGES


@pytest.mark.parametrize("path", DOCS_PAGES, ids=lambda path: path.name)
def test_no_docs_page_starts_with_a_byte_order_mark(path):
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")
