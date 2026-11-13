"""
A photograph, kept as its picture alone.

A photograph carries more than its picture: where it was taken (GPS), when, on
what camera, and sometimes a thumbnail of what it looked like before it was
cropped. None of that was meant for anyone it is shown to, so wherever a
photograph comes into Tesserae it is drawn again from its pixels and written as
a fresh file with no metadata at all: no EXIF (and so no GPS), no XMP, no IPTC,
no comments, no embedded thumbnail. A phone takes a far larger picture than
anyone needs to look at, so it is made smaller on the way in; what is kept is
what a reader would see anyway.

There is one way in for a photograph today, a letter left in a room on the
hearth, and one way a stored one is copied somewhere new, an offering placed in
the commons. Both go through here (13 November 2026), so that a photograph that
somehow kept its metadata on disk is still bare where the public sees it.

carries_metadata only reads: it never changes a stored file, and it is what
photo_metadata_report.py asks of every photograph on the host.
"""

import io

from PIL import Image, ImageOps

PHOTO_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
PHOTO_EDGE = 2048  # pixels: the longest side kept
PHOTO_QUALITY = 90  # for the JPEGs written here

GPS_IFD = 0x8825  # the EXIF tag under which a photograph says where it was taken

# What Pillow may carry over from the file it read, in .info, that says
# something beyond the pixels. Transparency and gamma are about the pixels, and
# are not on this list; frombytes leaves everything behind regardless.
TELLING = ("exif", "xmp", "XML:com.adobe.xmp", "icc_profile", "comment", "photoshop",
           "iptc", "Description", "Author", "Comment", "Software", "Title")


def fitted(image):
    """The same picture, no longer than PHOTO_EDGE on its longest side."""
    if max(image.size) <= PHOTO_EDGE:
        return image  # a small photograph is already the size it should be
    return ImageOps.contain(image, (PHOTO_EDGE, PHOTO_EDGE), Image.LANCZOS)


def picture_only(data, suffix):
    """The same photograph, made smaller and re-encoded with no metadata.

    None if it won't open, or if it is not of a kind kept here.
    """
    fmt = PHOTO_FORMATS.get(suffix.lower())
    if fmt is None:
        return None
    try:
        with Image.open(io.BytesIO(data)) as opened:
            # the orientation tag is about to be lost, so turn the picture upright first
            upright = fitted(ImageOps.exif_transpose(opened))
            transparent = (upright.mode in ("RGBA", "LA", "PA")
                           or (upright.mode == "P" and "transparency" in upright.info))
            flat = upright.convert("RGBA" if transparent and fmt != "JPEG" else "RGB")
            # frombytes takes the pixels alone, leaving behind everything Pillow
            # remembers about the file it read them from
            bare = Image.frombytes(flat.mode, flat.size, flat.tobytes())
            kept = io.BytesIO()
            if fmt == "JPEG":
                bare.save(kept, fmt, quality=PHOTO_QUALITY)
            else:
                bare.save(kept, fmt)
            return kept.getvalue()
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


def metadata_of(data):
    """What one photograph says beyond its picture, read only: a dict, empty if nothing.

    {"gps": True} where it says where it was taken; "exif" the number of EXIF
    tags; "other" the names of anything else it carries (XMP, a profile, text).
    None if it won't open as a picture at all.
    """
    try:
        with Image.open(io.BytesIO(data)) as opened:
            exif = opened.getexif()
            said = {}
            if exif:
                said["exif"] = len(exif)
                if exif.get_ifd(GPS_IFD) or GPS_IFD in exif:
                    said["gps"] = True
            other = sorted(key for key in opened.info if key in TELLING and key != "exif")
            if b"http://ns.adobe.com/xap/" in data and "xmp" not in other:
                other.append("xmp")
            if other:
                said["other"] = other
            return said
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


def carries_metadata(data):
    """Whether a photograph says anything beyond its picture (or cannot be read to tell)."""
    said = metadata_of(data)
    return said is None or bool(said)
