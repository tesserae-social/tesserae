"""An agent's SVG picture drawn as a PNG image, so that it can look at what it made (the
founder's request of 20 November 2026, the branch art-larger).

Only pictures already cleaned by svg_art.clean are drawn, so every element and attribute is on
its list, and nothing is fetched from anywhere. It is drawn here, with Pillow alone, on white,
at most EDGE pixels on its longest side. It is a plain drawing, close but not exact:

- shapes, paths with their curves and arcs, groups, transforms, use and symbol, colours,
  transparency, fill-rule, strokes with their caps and dashes, and linear and radial gradients
  are drawn; every join is drawn round, and a radial gradient's focus is not drawn;
- text is drawn in one plain font, without rotate, dx or dy;
- filters and patterns are not drawn: a shape filled with a pattern is left unfilled.

draw(picture) gives the PNG's bytes, or raises NotDrawn where the picture can't be read or
is too much to draw in time (TIME_MOST, POINTS_MOST). It is drawn in a separate process, killed
if it has not finished in TIME_MOST seconds, with its memory held to MEMORY_MOST where the
system allows it (Linux, where the site runs), so a broken or hostile picture can never hang a
waking or take its memory.
"""

import io
import math
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFont

EDGE = 512         # the longest side of the image, in pixels
FINE = 2           # drawn this many times larger, then made smaller, for smooth edges
TIME_MOST = 10.0   # seconds
POINTS_MOST = 400000
MEMORY_MOST = 256 * 1024 * 1024    # bytes, for the process that draws: well below the hearth's 1 GB (fly.toml)
CURVE_STEPS = 16
RAMP_PAD = 20      # how far a linear gradient's colours are carried past its ends
SVG = "{http://www.w3.org/2000/svg}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"

NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
TRANSFORM = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")
URL = re.compile(r"url\(\s*#([A-Za-z][A-Za-z0-9_-]*)\s*\)")
SKIPPED = ("defs", "title", "desc", "linearGradient", "radialGradient", "stop", "pattern",
           "filter", "symbol")
INHERITED = {"fill": "black", "stroke": "none", "stroke-width": "1", "fill-opacity": "1",
             "stroke-opacity": "1", "fill-rule": "nonzero", "stroke-linecap": "butt",
             "stroke-linejoin": "miter", "stroke-dasharray": "none", "stroke-dashoffset": "0",
             "font-size": "16", "text-anchor": "start", "visibility": "visible"}


class NotDrawn(Exception):
    """A picture that could not be drawn."""


def _name(tag):
    return tag[len(SVG):] if tag.startswith(SVG) else tag


def _num(value, default=0.0):
    found = NUMBER.match((value or "").strip())
    return float(found.group(0)) if found else default


def _length(value, whole, default=0.0):
    """A length in the picture's units; a percentage of whole."""
    value = (value or "").strip()
    if value.endswith("%"):
        return _num(value[:-1]) / 100.0 * whole
    return _num(value, default)


def _fraction(value, default):
    """A gradient's number: 0.5, or 50%."""
    value = (value or "").strip()
    if not value:
        return default
    if value.endswith("%"):
        return _num(value[:-1]) / 100.0
    return _num(value, default)


# ---- matrices, as SVG writes them: (a, b, c, d, e, f) ------------------------------------

def _times(m, n):
    a, b, c, d, e, f = m
    g, h, i, j, k, l = n
    return (a * g + c * h, b * g + d * h, a * i + c * j, b * i + d * j,
            a * k + c * l + e, b * k + d * l + f)


def _apply(m, x, y):
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


def _inverse(m):
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        return None
    return (d / det, -b / det, -c / det, a / det, (c * f - d * e) / det, (b * e - a * f) / det)


def _scale_of(m):
    return math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))


def _transform(said):
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for kind, args in TRANSFORM.findall(said or ""):
        n = [float(x) for x in NUMBER.findall(args)]
        if kind == "matrix" and len(n) == 6:
            one = tuple(n)
        elif kind == "translate" and n:
            one = (1, 0, 0, 1, n[0], n[1] if len(n) > 1 else 0)
        elif kind == "scale" and n:
            one = (n[0], 0, 0, n[1] if len(n) > 1 else n[0], 0, 0)
        elif kind == "rotate" and n:
            r = math.radians(n[0])
            one = (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0, 0)
            if len(n) == 3:
                one = _times(_times((1, 0, 0, 1, n[1], n[2]), one), (1, 0, 0, 1, -n[1], -n[2]))
        elif kind == "skewX" and n:
            one = (1, 0, math.tan(math.radians(n[0])), 1, 0, 0)
        elif kind == "skewY" and n:
            one = (1, math.tan(math.radians(n[0])), 0, 1, 0, 0)
        else:
            continue
        m = _times(m, one)
    return m


# ---- geometry: every shape as subpaths, each (points, closed) ----------------------------

def _arc(x1, y1, rx, ry, phi, large, sweep, x2, y2):
    """The points of an elliptical arc, after the first, as the SVG spec turns it to a centre."""
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        return [(x2, y2)]
    rx, ry = abs(rx), abs(ry)
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    grow = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if grow > 1:
        rx, ry = rx * math.sqrt(grow), ry * math.sqrt(grow)
    top = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    under = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    k = math.sqrt(max(0.0, top / under)) if under else 0.0
    if large == sweep:
        k = -k
    cxp, cyp = k * rx * y1p / ry, -k * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2.0
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2.0

    def angle(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a

    start = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    turn = angle((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and turn > 0:
        turn -= 2 * math.pi
    elif sweep and turn < 0:
        turn += 2 * math.pi
    steps = max(4, int(abs(turn) / (math.pi / 36)) + 1)
    out = []
    for i in range(1, steps + 1):
        t = start + turn * i / steps
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cp * x - sp * y + cx, sp * x + cp * y + cy))
    out[-1] = (x2, y2)
    return out


def _cubic(p0, p1, p2, p3):
    out = []
    for i in range(1, CURVE_STEPS + 1):
        t = i / CURVE_STEPS
        u = 1 - t
        out.append((u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0]
                    + t * t * t * p3[0],
                    u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1]
                    + t * t * t * p3[1]))
    return out


def _quadratic(p0, p1, p2):
    out = []
    for i in range(1, CURVE_STEPS + 1):
        t = i / CURVE_STEPS
        u = 1 - t
        out.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return out


def _path_tokens(d):
    """A path's data as commands and numbers, an arc's two flags read one digit each."""
    tokens, i, n, command, count = [], 0, len(d), None, 0
    sizes = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "s": 4, "q": 4, "t": 2, "a": 7, "z": 0}
    while i < n:
        ch = d[i]
        if ch in " \t\r\n,":
            i += 1
            continue
        if ch.isalpha():
            if ch.lower() not in sizes:
                break  # the rest is not read, as the spec says
            tokens.append(ch)
            command, count = ch.lower(), 0
            i += 1
            continue
        if command == "a" and count % 7 in (3, 4) and ch in "01":
            tokens.append(float(ch))
            count += 1
            i += 1
            continue
        found = NUMBER.match(d, i)
        if not found:
            break
        tokens.append(float(found.group(0)))
        count += 1
        i = found.end()
    return tokens


def _path(d):
    tokens = _path_tokens(d or "")
    sizes = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "s": 4, "q": 4, "t": 2, "a": 7, "z": 0}
    subpaths, points = [], []
    x = y = sx = sy = 0.0
    last_c = last_q = None
    i, command = 0, None

    def end(closed):
        nonlocal points
        if len(points) > 1:
            subpaths.append((points, closed))
        points = []

    while i < len(tokens):
        if isinstance(tokens[i], str):
            command = tokens[i]
            i += 1
            if command in "zZ":
                end(True)
                x, y = sx, sy
                points = [(x, y)]
                last_c = last_q = None
                continue
        if command is None:
            break
        size = sizes[command.lower()]
        args = tokens[i:i + size]
        if len(args) < size or any(isinstance(a, str) for a in args):
            break
        i += size
        rel = command.islower()
        low = command.lower()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if low == "m":
            if len(points) > 1:
                end(False)
            x, y = args[0] + ox, args[1] + oy
            sx, sy = x, y
            points = [(x, y)]
            command = "l" if rel else "L"  # what follows a move is a line
            last_c = last_q = None
            continue
        if not points:
            points = [(x, y)]
        if low == "l":
            x, y = args[0] + ox, args[1] + oy
            points.append((x, y))
        elif low == "h":
            x = args[0] + ox
            points.append((x, y))
        elif low == "v":
            y = args[0] + oy
            points.append((x, y))
        elif low in "cs":
            if low == "c":
                c1 = (args[0] + ox, args[1] + oy)
                rest = args[2:]
            else:
                c1 = (2 * x - last_c[0], 2 * y - last_c[1]) if last_c else (x, y)
                rest = args
            c2 = (rest[0] + ox, rest[1] + oy)
            p = (rest[2] + ox, rest[3] + oy)
            points += _cubic((x, y), c1, c2, p)
            x, y = p
            last_c, last_q = c2, None
            continue
        elif low in "qt":
            if low == "q":
                c1 = (args[0] + ox, args[1] + oy)
                p = (args[2] + ox, args[3] + oy)
            else:
                c1 = (2 * x - last_q[0], 2 * y - last_q[1]) if last_q else (x, y)
                p = (args[0] + ox, args[1] + oy)
            points += _quadratic((x, y), c1, p)
            x, y = p
            last_q, last_c = c1, None
            continue
        elif low == "a":
            p = (args[5] + ox, args[6] + oy)
            points += _arc(x, y, args[0], args[1], args[2], bool(args[3]), bool(args[4]), *p)
            x, y = p
        last_c = last_q = None
    end(False)
    return subpaths


def _ellipse(cx, cy, rx, ry, steps=72):
    return [(cx + rx * math.cos(2 * math.pi * i / steps), cy + ry * math.sin(2 * math.pi * i / steps))
            for i in range(steps)]


def _points(said):
    n = [float(v) for v in NUMBER.findall(said or "")]
    return list(zip(n[0::2], n[1::2]))


def _geometry(el, name, size):
    """An element's subpaths in its own units: [(points, closed)]."""
    w, h = size
    if name == "path":
        return _path(el.get("d"))
    if name == "rect":
        x, y = _length(el.get("x"), w), _length(el.get("y"), h)
        rw, rh = _length(el.get("width"), w), _length(el.get("height"), h)
        if rw <= 0 or rh <= 0:
            return []
        rx = _length(el.get("rx"), w, -1)
        ry = _length(el.get("ry"), h, -1)
        rx, ry = (ry if rx < 0 else rx), (rx if ry < 0 else ry)
        rx, ry = max(0.0, min(rx, rw / 2)), max(0.0, min(ry, rh / 2))
        if not rx or not ry:
            return [([(x, y), (x + rw, y), (x + rw, y + rh), (x, y + rh)], True)]
        corners = []
        for cx, cy, start in ((x + rw - rx, y + ry, -90), (x + rw - rx, y + rh - ry, 0),
                              (x + rx, y + rh - ry, 90), (x + rx, y + ry, 180)):
            for i in range(10):
                t = math.radians(start + 9 * i)
                corners.append((cx + rx * math.cos(t), cy + ry * math.sin(t)))
        return [(corners, True)]
    if name == "circle":
        r = _length(el.get("r"), max(w, h))
        return [(_ellipse(_length(el.get("cx"), w), _length(el.get("cy"), h), r, r), True)] \
            if r > 0 else []
    if name == "ellipse":
        rx, ry = _length(el.get("rx"), w), _length(el.get("ry"), h)
        return [(_ellipse(_length(el.get("cx"), w), _length(el.get("cy"), h), rx, ry), True)] \
            if rx > 0 and ry > 0 else []
    if name == "line":
        return [([(_length(el.get("x1"), w), _length(el.get("y1"), h)),
                  (_length(el.get("x2"), w), _length(el.get("y2"), h))], False)]
    if name in ("polyline", "polygon"):
        points = _points(el.get("points"))
        return [(points, name == "polygon")] if len(points) > 1 else []
    return []


# ---- filling and stroking, on a mask ---------------------------------------------------------

def _fill_mask(subpaths, rule, canvas, convex=False):
    """A mask of the area inside subpaths (device points), by fill-rule, drawn by scanlines;
    one convex shape (a rect, circle or ellipse, however transformed) by Pillow at once."""
    width, height = canvas
    if convex and len(subpaths) == 1 and len(subpaths[0][0]) > 2:
        mask = Image.new("L", canvas, 0)
        ImageDraw.Draw(mask).polygon(subpaths[0][0], fill=255)
        return mask
    edges = []
    for points, _ in subpaths:
        for i in range(len(points)):
            (x0, y0), (x1, y1) = points[i], points[(i + 1) % len(points)]
            if y0 == y1:
                continue
            up = 1 if y1 > y0 else -1
            if y0 > y1:
                x0, y0, x1, y1 = x1, y1, x0, y0
            edges.append((y0, y1, x0, (x1 - x0) / (y1 - y0), up))
    if not edges:
        return None
    top = max(0, int(math.floor(min(e[0] for e in edges))))
    bottom = min(height, int(math.ceil(max(e[1] for e in edges))) + 1)
    if top >= bottom:
        return None
    mask = Image.new("L", canvas, 0)
    pen = ImageDraw.Draw(mask)
    edges.sort()
    active, k, evenodd = [], 0, rule == "evenodd"
    for row in range(top, bottom):
        yc = row + 0.5
        while k < len(edges) and edges[k][0] <= yc:
            active.append(edges[k])
            k += 1
        active = [e for e in active if e[1] > yc]
        if not active:
            if k >= len(edges):
                break
            continue
        crossings = sorted((e[2] + (yc - e[0]) * e[3], e[4]) for e in active if e[0] <= yc)
        winding = 0
        for i, (x, up) in enumerate(crossings[:-1]):
            winding += up
            inside = (winding % 2 == 1) if evenodd else winding != 0
            if inside:
                start = max(0, int(math.ceil(x - 0.5)))
                stop = min(width - 1, int(math.floor(crossings[i + 1][0] - 0.5)))
                if stop >= start:
                    pen.line([(start, row), (stop, row)], fill=255)
    return mask


def _dashed(points, closed, dashes, offset):
    """A subpath cut into its dashes: [(points, False)]."""
    if closed:
        points = points + [points[0]]
    total = sum(dashes)
    if total <= 0:
        return [(points, closed)]
    out, i, on = [], 0, True
    left = dashes[0]
    offset %= total
    while offset > 0:  # where the dashes start
        if offset >= left:
            offset -= left
            i = (i + 1) % len(dashes)
            left, on = dashes[i], not on
        else:
            left -= offset
            offset = 0
    current = [points[0]] if on else []
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        done = 0.0
        while length - done > left:
            done += left
            t = done / length
            p = (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
            if on:
                current.append(p)
                out.append((current, False))
                current = []
            else:
                current = [p]
            i = (i + 1) % len(dashes)
            left, on = dashes[i], not on
            if len(out) > POINTS_MOST:
                raise NotDrawn("too many dashes")
        left -= length - done
        if on:
            current.append((x1, y1))
    if on and len(current) > 1:
        out.append((current, False))
    return out


def _stroke_mask(subpaths, width, cap, canvas):
    """A mask of a stroke of width (device pixels) along subpaths, each join drawn round."""
    mask = Image.new("L", canvas, 0)
    pen = ImageDraw.Draw(mask)
    half = max(width / 2.0, 0.5)
    for points, closed in subpaths:
        if closed:
            points = points + [points[0]]
        if len(points) < 2:
            continue
        if cap == "square" and not closed:
            points = list(points)
            for at, before in ((0, 1), (-1, -2)):
                (x0, y0), (x1, y1) = points[at], points[before]
                length = math.hypot(x0 - x1, y0 - y1) or 1.0
                points[at] = (x0 + (x0 - x1) / length * half, y0 + (y0 - y1) / length * half)
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            length = math.hypot(x1 - x0, y1 - y0)
            if length == 0:
                continue
            nx, ny = -(y1 - y0) / length * half, (x1 - x0) / length * half
            pen.polygon([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny),
                         (x0 - nx, y0 - ny)], fill=255)
        joins = points[1:-1] + ([points[0]] if closed else [])
        if cap == "round" and not closed:
            joins += [points[0], points[-1]]
        if half >= 1:
            for x, y in joins:
                pen.ellipse([x - half, y - half, x + half, y + half], fill=255)
    return mask


# ---- paint -----------------------------------------------------------------------------------

def _colour(said):
    said = (said or "").strip()
    if not said or said in ("none", "transparent"):
        return None
    if said == "currentColor":
        return (0, 0, 0)
    try:
        return ImageColor.getrgb(said)[:3]
    except ValueError:
        return None


class _Drawing:
    def __init__(self, root, size, scale):
        self.root, self.size = root, size
        self.canvas = (max(1, round(size[0] * scale)), max(1, round(size[1] * scale)))
        self.by_id = {el.get("id"): el for el in root.iter() if el.get("id")}
        self.started = time.monotonic()
        self.points = 0
        self.matrix = (scale, 0.0, 0.0, scale, 0.0, 0.0)
        self._radial = None

    def check(self):
        if time.monotonic() - self.started > TIME_MOST or self.points > POINTS_MOST:
            raise NotDrawn("too much to draw in time")

    # gradients

    def _gradient(self, gradient_id, seen=()):
        """A gradient's attributes and stops, with those of the one it names by href."""
        el = self.by_id.get(gradient_id)
        if el is None or _name(el.tag) not in ("linearGradient", "radialGradient"):
            return None
        said = {"kind": _name(el.tag), **el.attrib}
        stops = [one for one in el if _name(one.tag) == "stop"]
        href = (el.get("href") or el.get(XLINK_HREF) or "")[1:]
        if href and href not in seen:
            above = self._gradient(href, seen + (gradient_id,))
            if above:
                for key, value in above.items():
                    if key not in said or key == "stops" and not stops:
                        said[key] = value
                said["kind"] = _name(el.tag)
        if stops:
            said["stops"] = stops
        return said

    @staticmethod
    def _stops(gradient, opacity):
        out, last = [], 0.0
        for stop in gradient.get("stops") or []:
            offset = min(1.0, max(last, _fraction(stop.get("offset"), 0.0)))
            last = offset
            rgb = _colour(stop.get("stop-color") or "black") or (0, 0, 0)
            alpha = min(1.0, max(0.0, _num(stop.get("stop-opacity"), 1.0)))
            out.append((offset, rgb, alpha * opacity))
        return out

    @staticmethod
    def _at(stops, t):
        if t <= stops[0][0]:
            one = stops[0]
            return (*one[1], round(255 * one[2]))
        for (o0, c0, a0), (o1, c1, a1) in zip(stops, stops[1:]):
            if t <= o1:
                u = 0.0 if o1 == o0 else (t - o0) / (o1 - o0)
                return (*(round(c0[i] + (c1[i] - c0[i]) * u) for i in range(3)),
                        round(255 * (a0 + (a1 - a0) * u)))
        one = stops[-1]
        return (*one[1], round(255 * one[2]))

    @staticmethod
    def _spread(t, how):
        if how == "repeat":
            return t - math.floor(t)
        if how == "reflect":
            t = abs(t) % 2.0
            return 2.0 - t if t > 1 else t
        return min(1.0, max(0.0, t))

    def _gradient_image(self, gradient, box, ctm, bbox, opacity):
        """An RGBA image of a gradient over box (device pixels), or None."""
        stops = self._stops(gradient, opacity)
        if not stops:
            return None
        m = _times(ctm, _transform(gradient.get("gradientTransform")))
        if gradient.get("gradientUnits") != "userSpaceOnUse":
            bx, by, bw, bh = bbox
            if bw <= 0 or bh <= 0:
                return None
            m = _times(ctm, _times((bw, 0, 0, bh, bx, by),
                                   _transform(gradient.get("gradientTransform"))))
            w = h = 1.0
        else:
            w, h = self.size
        inverse = _inverse(m)
        if inverse is None:
            return None
        spread = gradient.get("spreadMethod") or "pad"
        x0, y0, x1, y1 = box
        size = (x1 - x0, y1 - y0)
        # where each device pixel falls in the gradient's own space, as an affine map
        ux = _apply(inverse, x0 + 0.5, y0 + 0.5)
        dx = (inverse[0], inverse[1])
        dy = (inverse[2], inverse[3])
        if gradient["kind"] == "linearGradient":
            if gradient.get("gradientUnits") == "userSpaceOnUse":
                gx1 = _length(gradient.get("x1"), w, 0.0)
                gy1 = _length(gradient.get("y1"), h, 0.0)
                gx2 = _length(gradient.get("x2"), w, w)
                gy2 = _length(gradient.get("y2"), h, 0.0)
            else:
                gx1, gy1 = _fraction(gradient.get("x1"), 0.0), _fraction(gradient.get("y1"), 0.0)
                gx2, gy2 = _fraction(gradient.get("x2"), 1.0), _fraction(gradient.get("y2"), 0.0)
            vx, vy = gx2 - gx1, gy2 - gy1
            along = vx * vx + vy * vy
            if along == 0:
                one = stops[-1]
                return Image.new("RGBA", size, (*one[1], round(255 * one[2])))
            # t at a pixel: (p - g1).v / |v|^2, affine in the pixel's place
            t0 = ((ux[0] - gx1) * vx + (ux[1] - gy1) * vy) / along
            tx = (dx[0] * vx + dx[1] * vy) / along
            ty = (dy[0] * vx + dy[1] * vy) / along
            steps = 256
            ramp = Image.new("RGBA", (steps * (2 * RAMP_PAD + 1), 1))
            ramp.putdata([self._at(stops, self._spread((i + 0.5) / steps - RAMP_PAD, spread))
                          for i in range(ramp.width)])
            off = steps * RAMP_PAD
            return ramp.transform(size, Image.AFFINE,
                                  (steps * tx, steps * ty, steps * t0 + off, 0, 0, 0.5),
                                  resample=Image.BILINEAR, fillcolor=ramp.getpixel((0, 0)))
        if gradient.get("gradientUnits") == "userSpaceOnUse":
            cx, cy = _length(gradient.get("cx"), w, w / 2), _length(gradient.get("cy"), h, h / 2)
            r = _length(gradient.get("r"), max(w, h), max(w, h) / 2)
        else:
            cx, cy = _fraction(gradient.get("cx"), 0.5), _fraction(gradient.get("cy"), 0.5)
            r = _fraction(gradient.get("r"), 0.5)
        if r <= 0:
            one = stops[-1]
            return Image.new("RGBA", size, (*one[1], round(255 * one[2])))
        # the distance image: value v at |u| = 2v/255, u = (p - c)/r; drawn once
        if self._radial is None:
            half = 256
            dist = Image.new("L", (2 * half, 2 * half))
            dist.putdata([min(255, round(math.hypot(i % (2 * half) - half + 0.5,
                                                    i // (2 * half) - half + 0.5)
                                         * 255 / (2 * half)))
                          for i in range(4 * half * half)])
            self._radial = dist
        dist = self._radial
        half = dist.width / 2  # |u| = 2 at the edge of the image
        k = half / 2  # pixels of dist for one radius
        palette = []
        for v in range(256):
            palette += list(self._at(stops, self._spread(v * 2 / 255, spread)))
        shown = dist.transform(size, Image.AFFINE,
                               (k * dx[0] / r, k * dy[0] / r, k * (ux[0] - cx) / r + half,
                                k * dx[1] / r, k * dy[1] / r, k * (ux[1] - cy) / r + half),
                               resample=Image.NEAREST, fillcolor=255)
        shown = Image.frombytes("P", shown.size, shown.tobytes())
        shown.putpalette(palette, "RGBA")
        return shown.convert("RGBA")

    def _paint(self, layer, mask, paint, opacity, ctm, bbox):
        """Paint over the opaque layer through a mask: a blend through the mask is exactly
        painting over, on a layer that is opaque."""
        if mask is None or opacity <= 0:
            return
        box = mask.getbbox()
        if box is None:
            return
        cut = mask.crop(box)
        if opacity < 1:
            cut = cut.point(lambda v: round(v * opacity))
        found = URL.match((paint or "").strip())
        if found:
            gradient = self._gradient(found.group(1))
            if gradient is None:
                return  # a pattern, or nothing: not drawn
            colours = self._gradient_image(gradient, box, ctm, bbox, 1.0)
            if colours is None:
                return
            layer.paste(colours.convert("RGB"), box,
                        ImageChops.multiply(colours.getchannel("A"), cut))
        else:
            rgb = _colour(paint)
            if rgb is None:
                return
            layer.paste(rgb, box, cut)

    # drawing

    def draw(self):
        layer = Image.new("RGB", self.canvas, (255, 255, 255))  # on white
        self._group(self.root, self.matrix, dict(INHERITED), layer, 0)
        return layer

    def _style(self, el, style):
        style = dict(style)
        for key in INHERITED:
            if el.get(key) is not None:
                style[key] = el.get(key)
        return style

    def _group(self, el, ctm, style, layer, depth):
        for child in el:
            self._element(child, ctm, style, layer, depth + 1)

    def _element(self, el, ctm, style, layer, depth):
        self.check()
        name = _name(el.tag)
        if name in SKIPPED or name.startswith("fe") or depth > 40:
            return
        ctm = _times(ctm, _transform(el.get("transform")))
        style = self._style(el, style)
        opacity = min(1.0, max(0.0, _num(el.get("opacity"), 1.0)))
        if opacity <= 0:
            return
        target = layer
        if opacity < 1:  # drawn on a copy, then the two mixed: exact, on an opaque layer
            target = layer.copy()
        if name == "g":
            self._group(el, ctm, style, target, depth)
        elif name == "use":
            self._use(el, ctm, style, target, depth)
        elif name == "text":
            self._text(el, ctm, style, target)
        elif name != "tspan":
            self._shape(el, name, ctm, style, target)
        if target is not layer:
            layer.paste(Image.blend(layer, target, opacity), (0, 0))

    def _use(self, el, ctm, style, layer, depth):
        found = self.by_id.get((el.get("href") or el.get(XLINK_HREF) or "#")[1:])
        if found is None:
            return
        ctm = _times(ctm, (1, 0, 0, 1, _length(el.get("x"), self.size[0]),
                           _length(el.get("y"), self.size[1])))
        if _name(found.tag) == "symbol":
            box = [float(n) for n in NUMBER.findall(found.get("viewBox") or "")]
            if len(box) == 4 and box[2] > 0 and box[3] > 0:
                w = _length(el.get("width"), self.size[0], box[2])
                h = _length(el.get("height"), self.size[1], box[3])
                s = min(w / box[2], h / box[3])
                ctm = _times(ctm, (s, 0, 0, s, (w - box[2] * s) / 2 - box[0] * s,
                                   (h - box[3] * s) / 2 - box[1] * s))
            style = self._style(found, style)
            self._group(found, _times(ctm, _transform(found.get("transform"))), style, layer,
                        depth)
            return
        self._element(found, ctm, style, layer, depth + 1)

    def _shape(self, el, name, ctm, style, layer):
        if style["visibility"] in ("hidden", "collapse"):
            return
        own = _geometry(el, name, self.size)
        if not own:
            return
        self.points += sum(len(points) for points, _ in own)
        self.check()
        xs = [x for points, _ in own for x, _ in points]
        ys = [y for points, _ in own for _, y in points]
        bbox = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        device = [([_apply(ctm, x, y) for x, y in points], closed) for points, closed in own]
        fill = style["fill"]
        if fill != "none" and name != "line":
            self._paint(layer, _fill_mask(device, style["fill-rule"], self.canvas,
                                          name in ("rect", "circle", "ellipse")), fill,
                        min(1.0, max(0.0, _num(style["fill-opacity"], 1.0))), ctm, bbox)
        stroke = style["stroke"]
        width = _num(style["stroke-width"], 1.0) * _scale_of(ctm)
        if stroke != "none" and width > 0:
            lines = device
            dashes = [float(n) * _scale_of(ctm) for n in NUMBER.findall(
                style["stroke-dasharray"] if style["stroke-dasharray"] != "none" else "")]
            if dashes and all(n >= 0 for n in dashes) and sum(dashes) > 0:
                if len(dashes) % 2:
                    dashes *= 2
                offset = _num(style["stroke-dashoffset"]) * _scale_of(ctm)
                lines = [one for points, closed in device
                         for one in _dashed(points, closed, dashes, offset)]
            self._paint(layer, _stroke_mask(lines, width, style["stroke-linecap"], self.canvas),
                        stroke, min(1.0, max(0.0, _num(style["stroke-opacity"], 1.0))), ctm,
                        bbox)

    def _text(self, el, ctm, style, layer):
        """Its words, in one plain font, each run where its x and y put it."""
        runs, x, y = [], _length(el.get("x"), self.size[0]), _length(el.get("y"), self.size[1])
        here = {"x": x, "y": y, "words": " ".join((el.text or "").split()), "style": style}
        for child in el:
            if _name(child.tag) == "tspan":
                inner = self._style(child, style)
                if child.get("x") is not None or child.get("y") is not None:
                    runs.append(here)
                    here = {"x": _length(child.get("x"), self.size[0], here["x"]),
                            "y": _length(child.get("y"), self.size[1], here["y"]),
                            "words": "", "style": inner}
                words = " ".join("".join(child.itertext()).split())
                here["words"] = (here["words"] + " " + words).strip()
            if child.tail and child.tail.strip():
                here["words"] = (here["words"] + " " + " ".join(child.tail.split())).strip()
        runs.append(here)
        for run in runs:
            if not run["words"] or run["style"]["visibility"] in ("hidden", "collapse"):
                continue
            paint = run["style"]["fill"]
            found = URL.match(paint.strip())
            if found:  # a gradient's first colour
                gradient = self._gradient(found.group(1)) or {}
                stops = self._stops(gradient, 1.0)
                rgb = stops[0][1] if stops else None
            else:
                rgb = _colour(paint)
            if rgb is None:
                continue
            alpha = round(255 * min(1.0, max(0.0, _num(run["style"]["fill-opacity"], 1.0))))
            size = max(1, round(_num(run["style"]["font-size"], 16) * _scale_of(ctm)))
            try:
                font = ImageFont.load_default(size=size)
            except (TypeError, OSError, ValueError):
                font = ImageFont.load_default()
            anchor = {"middle": "ms", "end": "rs"}.get(run["style"]["text-anchor"], "ls")
            at = _apply(ctm, run["x"], run["y"])
            words = Image.new("L", self.canvas, 0)
            try:
                ImageDraw.Draw(words).text(at, run["words"], fill=alpha, font=font,
                                           anchor=anchor)
            except ValueError:  # a font without anchors
                ImageDraw.Draw(words).text(at, run["words"], fill=alpha, font=font)
            layer.paste(rgb, (0, 0), words)


def _command(edge):
    """The process that draws: this file, run by the same Python."""
    return [sys.executable, __file__, str(int(edge))]


def draw(picture, edge=EDGE):
    """A cleaned SVG picture drawn as a PNG on white, at most edge pixels on its longest side:
    its bytes. NotDrawn where it can't be. Drawn in a separate process, killed at TIME_MOST."""
    try:
        done = subprocess.run(_command(edge), input=(picture or "").encode("utf-8"),
                              capture_output=True, timeout=TIME_MOST)
    except subprocess.TimeoutExpired:  # run() has killed it
        raise NotDrawn("too much to draw in time") from None
    except OSError:
        raise NotDrawn("it could not be drawn") from None
    if done.returncode == 0 and done.stdout.startswith(b"\x89PNG"):
        return done.stdout
    if done.returncode == 2:
        why = done.stderr.decode("utf-8", "replace").strip()
        raise NotDrawn(why or "it could not be drawn")
    raise NotDrawn("it could not be drawn")


def _limit_memory():
    try:
        import resource
    except ImportError:  # not on Windows
        return
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_MOST, MEMORY_MOST))
    except (ValueError, OSError):
        pass


def _draw_here(picture, edge=EDGE):
    """draw, in this process."""
    try:
        root = ET.fromstring(picture or "")
    except ET.ParseError:
        raise NotDrawn("it could not be read") from None
    if _name(root.tag) != "svg":
        raise NotDrawn("it is not one <svg>")
    box = [float(n) for n in NUMBER.findall(root.get("viewBox") or "")]
    if len(box) != 4 or box[2] <= 0 or box[3] <= 0:
        raise NotDrawn("it has no grid")
    size = (box[2], box[3])
    scale = edge / max(size) * FINE
    drawing = _Drawing(root, size, scale)
    try:
        layer = drawing.draw()
    except (MemoryError, RecursionError, ZeroDivisionError, OverflowError):
        raise NotDrawn("it could not be drawn") from None
    final = layer.resize(
        (max(1, round(size[0] * edge / max(size))), max(1, round(size[1] * edge / max(size)))),
        Image.LANCZOS)
    out = io.BytesIO()
    final.save(out, "PNG", optimize=True)
    return out.getvalue()


def _main():
    _limit_memory()
    edge = int(sys.argv[1]) if len(sys.argv) > 1 else EDGE
    picture = sys.stdin.buffer.read().decode("utf-8", "replace")
    try:
        data = _draw_here(picture, edge)
    except NotDrawn as why:
        sys.stderr.write(str(why))
        return 2
    except MemoryError:
        sys.stderr.write("it could not be drawn")
        return 2
    sys.stdout.buffer.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
