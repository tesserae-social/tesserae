"""A photograph is kept as its picture alone: no EXIF, no GPS, wherever it comes in.

Every photograph here is made in the test, with a place written into it, and
followed to where it is kept: beside a letter left on the hearth, and in the
commons when one is placed there. photo_metadata_report.py is asked of a disk
holding one of each, and is seen to change nothing.
"""

import io

import pytest
from PIL import Image

import photos
from conftest import post, write

# a place, made up, written where a phone writes where it was
SOMEWHERE = {1: "N", 2: (41.0, 52.0, 3.0), 3: "W", 4: (87.0, 37.0, 1.0)}

KINDS = [("JPEG", ".jpg"), ("PNG", ".png"), ("WEBP", ".webp")]


def located(fmt="JPEG", size=(50, 40)):
    """A photograph that says where it was taken, and on what camera."""
    exif = Image.Exif()
    exif[271] = "TestCamera"
    exif[306] = "2026:11:13 08:00:00"
    exif.get_ifd(photos.GPS_IFD).update(SOMEWHERE)
    kept = io.BytesIO()
    Image.new("RGB", size, (200, 90, 48)).save(kept, fmt, exif=exif.tobytes())
    return kept.getvalue()


def bare(fmt="JPEG"):
    kept = io.BytesIO()
    Image.new("RGB", (50, 40), (200, 90, 48)).save(kept, fmt)
    return kept.getvalue()


@pytest.mark.parametrize("fmt,suffix", KINDS)
def test_a_located_photograph_is_seen_to_say_where_it_was(fmt, suffix):
    said = photos.metadata_of(located(fmt))
    assert said["gps"] is True
    assert photos.carries_metadata(located(fmt))


@pytest.mark.parametrize("fmt,suffix", KINDS)
def test_a_bare_photograph_says_nothing_beyond_its_picture(fmt, suffix):
    assert photos.metadata_of(bare(fmt)) == {}
    assert not photos.carries_metadata(bare(fmt))


@pytest.mark.parametrize("fmt,suffix", KINDS)
def test_picture_only_takes_out_every_word_of_where_and_when(fmt, suffix):
    kept = photos.picture_only(located(fmt), suffix)
    assert photos.metadata_of(kept) == {}
    with Image.open(io.BytesIO(kept)) as opened:
        assert opened.format == fmt
        assert opened.size == (50, 40)
        assert dict(opened.getexif()) == {}
    assert b"TestCamera" not in kept


def test_xmp_and_a_comment_are_taken_out_too():
    kept = io.BytesIO()
    Image.new("RGB", (20, 20)).save(kept, "JPEG", comment=b"taken at home",
                                    xmp=b"<x:xmpmeta xmlns:x='adobe:ns:meta/'/>")
    data = kept.getvalue()
    assert photos.carries_metadata(data)
    cleaned = photos.picture_only(data, ".jpg")
    assert photos.metadata_of(cleaned) == {}
    assert b"taken at home" not in cleaned and b"xmpmeta" not in cleaned


def test_what_will_not_open_is_not_kept():
    assert photos.picture_only(b"not a picture", ".jpg") is None
    assert photos.picture_only(located(), ".gif") is None
    assert photos.metadata_of(b"not a picture") is None
    assert photos.carries_metadata(b"not a picture")


@pytest.mark.parametrize("fmt,suffix", KINDS)
def test_a_letter_s_photograph_is_kept_with_no_place_in_it(founder, room, fmt, suffix):
    form = {"letter": "Dear first one,\n\nThe lake.\n",
            "photo": (io.BytesIO(located(fmt)), "photo" + suffix)}
    post(founder, "/letters", data=form, content_type="multipart/form-data")
    kept = [p for p in (room / "letters" / "incoming").iterdir() if p.suffix == suffix]
    assert len(kept) == 1
    assert photos.metadata_of(kept[0].read_bytes()) == {}


def test_a_photograph_placed_in_the_commons_is_bare_though_its_letter_s_copy_is_not(
        env, tmp_path):
    import offering

    beside = tmp_path / "beside.jpg"
    beside.write_bytes(located())
    to = tmp_path / "placed.jpg"
    offering.copy_out(beside, to, "photo")
    assert photos.metadata_of(to.read_bytes()) == {}
    assert photos.metadata_of(beside.read_bytes())["gps"] is True  # never changed


def test_a_bare_photograph_placed_is_copied_byte_for_byte(env, tmp_path):
    import offering

    beside = tmp_path / "beside.jpg"
    beside.write_bytes(bare())
    to = tmp_path / "placed.jpg"
    offering.copy_out(beside, to, "photo")
    assert to.read_bytes() == beside.read_bytes()


def test_the_report_counts_gps_and_changes_nothing(tmp_path):
    import photo_metadata_report as report

    read = tmp_path / "rooms" / "first" / "letters" / "read"
    read.mkdir(parents=True)
    (read / "founder-2026-10-01T00-00-00Z.jpg").write_bytes(located())
    (read / "founder-2026-10-02T00-00-00Z.jpg").write_bytes(bare())
    offerings = tmp_path / "commons" / "offerings"
    offerings.mkdir(parents=True)
    (offerings / "offering-1.jpg").write_bytes(located("PNG"))
    hidden = tmp_path / "packets" / "first" / "private"
    hidden.mkdir(parents=True)
    write(hidden / "never.jpg", "never read")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}

    lines, with_gps = report.report(tmp_path)

    assert with_gps == 2
    assert lines[0].startswith("3 photographs looked at")
    assert "  GPS: room first: founder-2026-10-01T00-00-00Z.jpg" in lines
    assert "  GPS: public offering: offering-1.jpg" in lines
    assert not any("never" in line for line in lines)
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before
