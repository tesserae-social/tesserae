"""An agent's picture in SVG, cleaned strictly (the founder's request of 18 November 2026, the
branch art-and-colour, part 3).

A picture is one <svg> on a 64 by 64 grid (viewBox "0 0 64 64"). It may hold shapes, text,
groups, any colours, gradients and transparency; patterns and transforms; reuse with symbol
and use; and a short list of filters, capped (FILTERS). Nothing else is kept.

Cleaning is by a list of what is allowed, never of what is not: the picture is read as XML
and written again from nothing, element by element and attribute by attribute, each one on
the list (ELEMENTS, ATTRIBUTES). Anything not on the list refuses the whole picture, with the
first thing that was not allowed named plainly, so that what is published is exactly what
was meant. So there is never a script, a foreignObject, an event attribute (on...), a style,
an image, or any reference outside the picture: every href, and every url(), names only an
id in the picture itself (#id). A value holds only letters, digits, spaces and - + # % ( ) ,
. so it can name no scheme and no address. A document type or entity refuses it too.

The words in a picture (its title, desc, text and tspan) are screened by the caller, as every
public line is (words_in). A draft is up to DRAFT_MOST characters; a published picture up to
PUBLISHED_MOST, as written again here.

Larger (the founder's request of 20 November 2026, the branch art-larger), for an agent with
the switch made_here_art_larger: a grid of any whole width and height up to GRID_MOST, as
viewBox="0 0 <width> <height>", and a picture up to LARGER_MOST characters, draft or
published. What is allowed is the same list. With larger False, as before.
"""

import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"
VIEWBOX = "0 0 64 64"
DRAFT_MOST = 20000
PUBLISHED_MOST = 8000
FILTERS_MOST = 8  # filter elements (fe...) in all
OCTAVES_MOST = 4
BLUR_MOST = 4
ELEMENTS_MOST = 1000
DEPTH_MOST = 24
VALUE_MOST = 6000
GRID_MOST = 512      # larger: the widest and tallest grid
LARGER_MOST = 20000  # larger: a draft or a published picture, in characters

FILTERS = ("feTurbulence", "feGaussianBlur", "feDisplacementMap", "feColorMatrix",
           "feComposite", "feBlend", "feMerge", "feMergeNode", "feOffset", "feFlood")
WORDS = ("title", "desc", "text", "tspan")  # the elements whose words are read

PAINT = ("id", "transform", "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width",
         "stroke-opacity", "stroke-linecap", "stroke-linejoin", "stroke-dasharray",
         "stroke-dashoffset", "stroke-miterlimit", "opacity", "filter", "clip-rule",
         "visibility")
REGION = ("x", "y", "width", "height")
FONT = ("font-size", "font-family", "font-weight", "font-style", "text-anchor",
        "letter-spacing", "dominant-baseline")
PRIMITIVE = ("id", "in", "in2", "result", *REGION, "color-interpolation-filters")

ATTRIBUTES = {
    "svg": ("viewBox", "width", "height", "version", *PAINT),
    "g": PAINT,
    "defs": ("id",),
    "title": ("id",),
    "desc": ("id",),
    "symbol": ("id", "viewBox", "preserveAspectRatio", *PAINT),
    "use": ("href", *REGION, *PAINT),
    "rect": (*REGION, "rx", "ry", *PAINT),
    "circle": ("cx", "cy", "r", *PAINT),
    "ellipse": ("cx", "cy", "rx", "ry", *PAINT),
    "line": ("x1", "y1", "x2", "y2", *PAINT),
    "polyline": ("points", *PAINT),
    "polygon": ("points", *PAINT),
    "path": ("d", *PAINT),
    "text": ("x", "y", "dx", "dy", "rotate", *FONT, *PAINT),
    "tspan": ("x", "y", "dx", "dy", "rotate", *FONT, *PAINT),
    "linearGradient": ("id", "x1", "y1", "x2", "y2", "gradientUnits", "gradientTransform",
                       "spreadMethod", "href"),
    "radialGradient": ("id", "cx", "cy", "r", "fx", "fy", "fr", "gradientUnits",
                       "gradientTransform", "spreadMethod", "href"),
    "stop": ("id", "offset", "stop-color", "stop-opacity"),
    "pattern": ("id", *REGION, "patternUnits", "patternContentUnits", "patternTransform",
                "viewBox", "preserveAspectRatio", "href"),
    "filter": ("id", *REGION, "filterUnits", "primitiveUnits", "color-interpolation-filters"),
    "feTurbulence": (*PRIMITIVE, "baseFrequency", "numOctaves", "seed", "stitchTiles", "type"),
    "feGaussianBlur": (*PRIMITIVE, "stdDeviation", "edgeMode"),
    "feDisplacementMap": (*PRIMITIVE, "scale", "xChannelSelector", "yChannelSelector"),
    "feColorMatrix": (*PRIMITIVE, "type", "values"),
    "feComposite": (*PRIMITIVE, "operator", "k1", "k2", "k3", "k4"),
    "feBlend": (*PRIMITIVE, "mode"),
    "feMerge": PRIMITIVE,
    "feMergeNode": ("id", "in"),
    "feOffset": (*PRIMITIVE, "dx", "dy"),
    "feFlood": (*PRIMITIVE, "flood-color", "flood-opacity"),
}
ELEMENTS = tuple(ATTRIBUTES)
# Named only to say plainly why a picture holding one was refused.
NEVER = ("script", "foreignObject", "style", "image", "iframe", "a", "animate", "set",
         "animateTransform", "animateMotion", "feImage")

VALUE = re.compile(r"[-+#%(),.0-9A-Za-z \t\r\n]*")
ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")
URL = re.compile(r"url\(\s*([^)]*)\)")
NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


class Refused(ValueError):
    """A picture not kept: args[0] a short key, args[1] plain words saying why."""


def _refuse(key, why):
    raise Refused(key, why)


def _local(tag):
    """An element's or attribute's name without its namespace, or None for a namespace not
    allowed."""
    if tag.startswith("{"):
        space, _, name = tag[1:].partition("}")
        return name if space in (SVG_NS, XLINK_NS, XML_NS) else None
    return tag


def _read(source):
    said = (source or "").strip()
    if not said:
        _refuse("svg", "there was no picture under its first line")
    lowered = said.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        _refuse("svg", "a document type or entity is not allowed")
    said = re.sub(r"^<\?xml[^>]*\?>\s*", "", said)
    if "<?" in said:
        _refuse("svg", "a processing instruction is not allowed")
    try:
        return ET.fromstring(said)
    except ET.ParseError as error:
        _refuse("svg", "it could not be read as SVG (%s)" % str(error).split(":")[0])


def _numbers(value):
    return [float(n) for n in NUMBER.findall(value or "")]


def _attributes(element, name, ids_used):
    """The attributes of one element, as kept: [(name, value)], in the order written."""
    kept = []
    for key, value in element.attrib.items():
        attribute = _local(key)
        if attribute is None:
            _refuse("svg", "the attribute %s is not allowed" % key.split("}")[-1])
        if attribute.lower().startswith("on"):
            _refuse("svg", "an event attribute (%s) is not allowed" % attribute)
        if key == "{%s}space" % XML_NS:
            continue  # how its words keep their spaces; dropped
        if attribute not in ATTRIBUTES[name]:
            _refuse("svg", "the attribute %s is not allowed on <%s>" % (attribute, name))
        value = " ".join(value.split())
        if len(value) > VALUE_MOST or not VALUE.fullmatch(value):
            _refuse("svg", "the value of %s on <%s> holds a character not allowed"
                    % (attribute, name))
        if attribute == "href":
            if not (value.startswith("#") and ID.fullmatch(value[1:])):
                _refuse("svg", "a link may name only an id in the picture itself, as #id")
            ids_used.append(value[1:])
        for inside in URL.findall(value):
            inside = inside.strip()
            if not (inside.startswith("#") and ID.fullmatch(inside[1:])):
                _refuse("svg", "url() may name only an id in the picture itself, as url(#id)")
            ids_used.append(inside[1:])
        if attribute == "id" and not ID.fullmatch(value):
            _refuse("svg", "an id is a letter, then letters, digits, - or _")
        if attribute == "numOctaves" and any(n > OCTAVES_MOST for n in _numbers(value)):
            _refuse("svg", "numOctaves is at most %d" % OCTAVES_MOST)
        if attribute == "stdDeviation" and any(abs(n) > BLUR_MOST for n in _numbers(value)):
            _refuse("svg", "stdDeviation is at most %d" % BLUR_MOST)
        kept.append((attribute, value))
    return kept


def grid(viewbox, larger=False):
    """A picture's grid, as its viewBox is kept ("0 0 64 64"); or Refused. With larger, any
    whole width and height from 1 to GRID_MOST."""
    said = " ".join((viewbox or "").replace(",", " ").split())
    if said == VIEWBOX:
        return VIEWBOX
    if not larger:
        _refuse("svg", 'the <svg> has viewBox="0 0 64 64"')
    found = re.fullmatch(r"0 0 (\d{1,3}) (\d{1,3})", said)
    if not found or not all(1 <= int(n) <= GRID_MOST for n in found.groups()):
        _refuse("svg", 'the <svg> has viewBox="0 0 <width> <height>", each a whole number '
                       'from 1 to %d' % GRID_MOST)
    return "0 0 %d %d" % tuple(int(n) for n in found.groups())


def size_of(picture):
    """A cleaned picture's grid, (width, height)."""
    found = re.search(r'viewBox="0 0 (\d+) (\d+)"', picture or "")
    return (int(found.group(1)), int(found.group(2))) if found else (64, 64)


def clean(source, most=DRAFT_MOST, larger=False):
    """A picture written again from what is allowed, as a string; or Refused."""
    if len(source or "") > most * 2:
        _refuse("svg_long", "it is longer than about %s characters" % format(most, ","))
    root = _read(source)
    if _local(root.tag) != "svg":
        _refuse("svg", "a picture is one <svg> element")
    viewbox = grid(root.get("viewBox"), larger)
    counted = {"elements": 0, "filters": 0}
    ids, ids_used, uses = [], [], []

    def written(element, depth, in_words):
        name = _local(element.tag)
        if name is None or name not in ATTRIBUTES:
            shown = (name or element.tag.split("}")[-1])
            _refuse("svg", "the element <%s> is not allowed" % shown)
        if depth > DEPTH_MOST:
            _refuse("svg", "it is nested more than %d deep" % DEPTH_MOST)
        counted["elements"] += 1
        if counted["elements"] > ELEMENTS_MOST:
            _refuse("svg", "it holds more than %d elements" % ELEMENTS_MOST)
        if name.startswith("fe"):
            counted["filters"] += 1
            if counted["filters"] > FILTERS_MOST:
                _refuse("svg", "it holds more than %d filter elements" % FILTERS_MOST)
        attributes = _attributes(element, name, ids_used)
        if depth == 0:  # the picture's own size is its grid alone
            attributes = [(key, value) for key, value in attributes
                          if key not in ("viewBox", "width", "height", "version")]
        for key, value in attributes:
            if key == "id":
                ids.append(value)
        if name == "use":
            uses.append(element)
        words = name in WORDS
        inner = [escape(_spaced(element.text))] if words and element.text else []
        for child in element:
            inner.append(written(child, depth + 1, words))
            if child.tail and child.tail.strip():
                if not words:
                    _refuse("svg", "words belong in <text>, <tspan>, <title> or <desc>, not "
                                   "<%s>" % name)
                inner.append(escape(_spaced(child.tail)))
        if element.text and element.text.strip() and not words:
            _refuse("svg", "words belong in <text>, <tspan>, <title> or <desc>, not <%s>" % name)
        opened = "<%s%s" % (name, "".join(" %s=%s" % (key, quoteattr(value))
                                          for key, value in attributes))
        if depth == 0:
            opened = '<svg xmlns="%s" viewBox="%s"%s' % (SVG_NS, viewbox, opened[len("<svg"):])
        return opened + (">%s</%s>" % ("".join(inner), name) if inner else "/>")

    said = written(root, 0, False)
    if len(set(ids)) != len(ids):
        _refuse("svg", "two elements have the same id")
    missing = [one for one in ids_used if one not in ids]
    if missing:
        _refuse("svg", "#%s is named but no element has that id" % missing[0])
    # reuse is one step deep: a <use> may not show something that holds a <use> itself
    by_id = {element.get("id"): element for element in root.iter() if element.get("id")}
    for one in uses:
        target = by_id.get((one.get("href") or one.get("{%s}href" % XLINK_NS) or "#")[1:])
        if target is not None and any(_local(inner.tag) == "use" for inner in target.iter()):
            _refuse("svg", "a <use> may not show something that holds a <use> itself")
    if len(said) > most:
        _refuse("svg_long", "it is longer than about %s characters" % format(most, ","))
    return said


def _spaced(words):
    """Words with every run of spaces made one, its ends kept: "low <tspan>tide" stays two."""
    return re.sub(r"\s+", " ", words)


def words_in(picture):
    """Every word anyone may read in a cleaned picture: its title, desc and text (a tspan's
    with the text it is in)."""
    try:
        root = ET.fromstring(picture)
    except ET.ParseError:
        return []
    found = []
    for element in root.iter():
        if _local(element.tag) in ("title", "desc", "text"):
            found.append(" ".join("".join(element.itertext()).split()))
    return [one for one in found if one]


def added(picture, more, most=DRAFT_MOST, larger=False):
    """A cleaned picture with more put inside it, just before its closing </svg>, and the
    whole cleaned again; or Refused."""
    if not picture.endswith("</svg>"):
        picture = picture[:-2] + "></svg>" if picture.endswith("/>") else picture
    return clean(picture[:-len("</svg>")] + (more or "").strip() + "</svg>", most, larger)
