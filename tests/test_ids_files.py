"""The identity documents in the repository, as GitHub Pages serves them: plain
UTF-8 with no byte-order mark, so that a strict JSON reader takes them as they are.
"""

import json
from pathlib import Path

import pytest

IDS = Path(__file__).resolve().parent.parent / "ids"
DOCUMENTS = sorted(path for path in IDS.rglob("*") if path.is_file())


def test_there_are_documents_to_check():
    assert DOCUMENTS


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda path: path.relative_to(IDS).as_posix())
def test_no_identity_document_starts_with_a_byte_order_mark(path):
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda path: path.relative_to(IDS).as_posix())
def test_every_identity_document_parses_as_plain_utf8_json(path):
    json.loads(path.read_bytes().decode("utf-8"))
