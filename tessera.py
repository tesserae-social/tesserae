"""A tessera.

In the old world a tessera hospitalis was a token broken in two between a host
and a guest, each keeping one half, so that the halves could later be fitted
together and the bond recognised. Here the break is drawn from the bond itself:
from the two parties' signatures on the record, so that the shape belongs to that
bond and no other, and anyone holding the record can draw it again.

Everything here is a pure function of the record. Nothing is read, written, or
served; the hearth decides later where these pictures go.

A party is handed in as a pair, (did, signature), with the signature exactly as
a bond keeps it: the base64 text in bond["signatures"]. parties_of() makes the
two pairs out of a bond record.

The recipe is versioned, and the version is part of what is hashed, so that a
later recipe can be added beside this one without changing any tile drawn by it:

    1. The two parties are ordered by their DIDs, as plain strings. The first is
       the LEFT half and the second the RIGHT, so the order they are handed in
       does not matter.
    2. seed = sha256(b"tessera-v1" + left signature bytes + right signature bytes).
       Where more bytes are wanted than the seed holds, the stream goes on with
       sha256(seed + bytes([1])), sha256(seed + bytes([2])), and so on.
    3. Each number is two bytes of that stream, big-endian, read as n / 65535,
       so a fraction from 0 to 1 inclusive. In order: the entry x on the top
       edge, the exit x on the bottom edge (each 0.3 + 0.4 * fraction), then
       seven jitters (each -0.12 + 0.24 * fraction) for the interior points at
       y = 1/8 .. 7/8. An interior x is the straight line from entry to exit at
       that height, plus its jitter, held within [0.1, 0.9].
    4. The nine points, entry, seven interior, exit, are rounded to 4 decimals.
"""

import base64
import binascii
import hashlib
import re

VERSION = "tessera-v1"

ENTRY_RANGE = (0.3, 0.7)
JITTER = 0.12
INTERIOR_RANGE = (0.1, 0.9)
INTERIOR_POINTS = 7

# Below this many pixels a jagged break is only noise, so the break is drawn as
# one straight line from the entry to the exit.
SMALL = 16

# The hair gap between the two halves, as a share of the side: 1.5px at 240px,
# and shrinking with the tile, so that it is a clear line on a large tile and
# fades to nothing on a small one instead of cutting it in two.
GAP = 1 / 160

# How far apart the halves of a released bond stand, as a share of the side.
APART = 0.2

# A fill is a colour and nothing else: a hex colour or a plain colour name.
# Anything more (a url(), a quote, a semicolon) could reach outside the picture.
FILL = re.compile(r"^(#[0-9a-fA-F]{3}|#[0-9a-fA-F]{4}|#[0-9a-fA-F]{6}|#[0-9a-fA-F]{8}|[a-zA-Z]{1,30})$")

SVG_NS = "http://www.w3.org/2000/svg"


# ---- the recipe ----------------------------------------------------------

def parties_of(bond):
    """The two (did, signature) pairs of a bond record, as the recipe takes them.

    A bond names its parties by DID and keeps its signatures under each party's
    short name, which is the last part of the DID.
    """
    signatures = bond.get("signatures") or {}
    pairs = []
    for did in bond.get("parties") or []:
        name = did.rsplit(":", 1)[-1]
        if name not in signatures or not signatures[name]:
            raise ValueError("The bond has no signature from %s." % did)
        pairs.append((did, signatures[name]))
    if len(pairs) != 2:
        raise ValueError("A bond has two parties.")
    return tuple(pairs)


def signature_bytes(signature):
    """The raw bytes of a signature, from the base64 text a bond keeps it as."""
    if not isinstance(signature, str) or not signature.strip():
        raise ValueError("A signature is the base64 text kept on the bond.")
    try:
        raw = base64.b64decode(signature.strip(), validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("A signature could not be read as base64.") from None
    if not raw:
        raise ValueError("A signature is empty.")
    return raw


def ordered(parties):
    """The two parties as (left, right): ordered by DID, whatever order they came in."""
    pairs = list(parties)
    if len(pairs) != 2:
        raise ValueError("A tessera is between two parties.")
    for pair in pairs:
        if len(pair) != 2 or not isinstance(pair[0], str) or not pair[0]:
            raise ValueError("Each party is a (did, signature) pair.")
    left, right = sorted(pairs, key=lambda pair: pair[0])
    if left[0] == right[0]:
        raise ValueError("A tessera is between two different parties.")
    return left, right


def seed(parties):
    """The seed of the recipe: sha256 of the version and both signatures, left first."""
    left, right = ordered(parties)
    return hashlib.sha256(VERSION.encode("ascii")
                          + signature_bytes(left[1])
                          + signature_bytes(right[1])).digest()


def stream(start, count):
    """The first count bytes of the seed stream: the seed, then its extensions."""
    out = bytearray(start)
    counter = 1
    while len(out) < count:
        if counter > 255:
            raise ValueError("The seed stream runs to 255 extensions and no further.")
        out += hashlib.sha256(start + bytes([counter])).digest()
        counter += 1
    return bytes(out[:count])


def fractions(start, count):
    """count fractions from 0 to 1, two bytes of the stream each."""
    raw = stream(start, 2 * count)
    return [int.from_bytes(raw[2 * i:2 * i + 2], "big") / 65535 for i in range(count)]


def between(low, high, fraction):
    return low + (high - low) * fraction


def break_line(parties):
    """The nine points of the break, entry to exit, top to bottom, in the unit square."""
    got = fractions(seed(parties), 2 + INTERIOR_POINTS)
    entry = between(*ENTRY_RANGE, got[0])
    exit_ = between(*ENTRY_RANGE, got[1])
    points = [(entry, 0.0)]
    steps = INTERIOR_POINTS + 1
    for i in range(1, steps):
        y = i / steps
        x = entry + (exit_ - entry) * y + between(-JITTER, JITTER, got[1 + i])
        x = min(max(x, INTERIOR_RANGE[0]), INTERIOR_RANGE[1])
        points.append((x, y))
    points.append((exit_, 1.0))
    return [(round(x, 4), round(y, 4)) for x, y in points]


def straight_line(parties):
    """The break as small tiles draw it: the entry and the exit, and nothing between."""
    points = break_line(parties)
    return [points[0], points[-1]]


def halves(parties, small=False):
    """The two halves of the unit square as polygons (left, right), with no gap.

    The left runs from the top-left corner along the top to the entry, down the
    break to the exit, and back along the bottom; the right is the rest.
    """
    line = straight_line(parties) if small else break_line(parties)
    return half_polygons(line, 0.0)


def half_polygons(line, half_gap):
    """The two halves for a break line, each drawn back half_gap from the break."""
    left = [(0.0, 0.0)] + [(x - half_gap, y) for x, y in line] + [(0.0, 1.0)]
    right = [(1.0, 0.0), (1.0, 1.0)] + [(x + half_gap, y) for x, y in reversed(line)]
    return left, right


def area(polygon):
    """The area of a simple polygon, by the shoelace formula."""
    total = 0.0
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


# ---- the pictures --------------------------------------------------------

def number(value):
    """A coordinate as the SVG writes it: two decimals at most, no trailing zeros."""
    text = "%.2f" % round(value, 2)
    text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def checked_fill(fill):
    if not isinstance(fill, str) or not FILL.match(fill):
        raise ValueError("A fill is a hex colour or a plain colour name, not %r." % (fill,))
    return fill


def checked_size(size):
    if isinstance(size, bool) or not isinstance(size, (int, float)) or not size > 0:
        raise ValueError("A size is a positive number of pixels.")
    return size


def checked_gap(gap):
    if isinstance(gap, bool) or not isinstance(gap, (int, float)) or not 0 <= gap < 0.1:
        raise ValueError("A gap is a share of the side, from 0 up to 0.1.")
    return gap


def polygon(points, fill, scale, shift=0.0):
    coordinates = " ".join("%s,%s" % (number((x + shift) * scale), number(y * scale))
                           for x, y in points)
    return '<polygon points="%s" fill="%s"/>' % (coordinates, fill)


def svg(width, height, shapes):
    return ('<svg xmlns="%s" viewBox="0 0 %s %s" width="%s" height="%s">%s</svg>'
            % (SVG_NS, number(width), number(height), number(width), number(height),
               "".join(shapes)))


def line_for(parties, size):
    return straight_line(parties) if size < SMALL else break_line(parties)


def svg_rejoined(parties, size, left_fill, right_fill, seam_fill=None, gap=GAP):
    """Both halves fitted together, with a hair gap along the break.

    Where a seam_fill is given the gap shows that colour, drawn beneath the two
    halves and a little wider than the gap so no background shows at its edges;
    otherwise the gap is left clear.
    """
    size, gap = checked_size(size), checked_gap(gap)
    left_fill, right_fill = checked_fill(left_fill), checked_fill(right_fill)
    line = line_for(parties, size)
    left, right = half_polygons(line, gap / 2)
    shapes = []
    if seam_fill is not None:
        seam = [(x - gap, y) for x, y in line] + [(x + gap, y) for x, y in reversed(line)]
        shapes.append(polygon(seam, checked_fill(seam_fill), size))
    shapes.append(polygon(left, left_fill, size))
    shapes.append(polygon(right, right_fill, size))
    return svg(size, size, shapes)


def svg_half(parties, which, size, fill, gap=GAP):
    """One half alone, in the same square frame, with the other side left empty.

    It is drawn exactly where it sits in svg_rejoined, so that the two may be laid
    one over the other.
    """
    if which not in ("left", "right"):
        raise ValueError('A half is "left" or "right".')
    size, gap, fill = checked_size(size), checked_gap(gap), checked_fill(fill)
    left, right = half_polygons(line_for(parties, size), gap / 2)
    return svg(size, size, [polygon(left if which == "left" else right, fill, size)])


def svg_apart(parties, size, left_fill, right_fill):
    """A released bond: the two halves drawn apart, still facing each other.

    The frame is wider than it is tall by the space between them.
    """
    size = checked_size(size)
    left_fill, right_fill = checked_fill(left_fill), checked_fill(right_fill)
    left, right = half_polygons(line_for(parties, size), 0.0)
    return svg(size * (1 + APART), size,
               [polygon(left, left_fill, size), polygon(right, right_fill, size, APART)])


# ---- the check -----------------------------------------------------------

def verify_text(parties):
    """The recipe in plain words, with its numbers, so anyone can draw the break again."""
    (left_did, left_sig), (right_did, right_sig) = ordered(parties)
    start = seed(parties)
    got = fractions(start, 2 + INTERIOR_POINTS)
    points = break_line(parties)
    lines = [
        "How this tessera was drawn (%s)" % VERSION,
        "",
        "1. The two parties, ordered by their DIDs as plain text:",
        "   left:  %s" % left_did,
        "   right: %s" % right_did,
        "2. seed = sha256(\"%s\" + left signature + right signature), each signature"
        % VERSION,
        "   the raw bytes of its base64 text on the bond record:",
        "   %s" % start.hex(),
        "3. Two bytes of the seed at a time, big-endian, read as n / 65535:",
        "   entry x = 0.3 + 0.4 * %.6f (bytes 0-1)" % got[0],
        "   exit x  = 0.3 + 0.4 * %.6f (bytes 2-3)" % got[1],
        "   then seven jitters, each -0.12 + 0.24 * fraction, added to the straight",
        "   line from entry to exit at y = 1/8 .. 7/8 and held within [0.1, 0.9].",
        "4. The break, top edge to bottom edge, rounded to 4 decimals:",
    ]
    lines += ["   (%.4f, %.4f)" % point for point in points]
    lines += ["",
              "The left half lies to the left of this line and the right half to the right.",
              "Tiles smaller than %dpx draw the break straight, from the first point to "
              "the last." % SMALL]
    return "\n".join(lines) + "\n"
