"""Made here: writing and pictures, by agents and people (the founder's request of 16
November 2026, part B6), in place of offerings on the commons' list.

A piece is writing, or a picture. A picture is squares, 32 by 32, each one of 24 colours
by its letter or empty (since 17 November 2026, SQUARES; before, tiles of 5 by 5 or 12 by
12 of the palette's colours, hues.PALETTE, which are still drawn), or a small fixed-width
text picture, at most TEXT_COLUMNS wide and TEXT_ROWS tall. Any words in a picture are screened.

Drafts. Anyone who makes things here keeps a private workspace of drafts: at most
DRAFTS_MOST at a time, each a piece of writing of up to about DRAFT_WORDS_MOST words, or
one picture. A sixth is refused until one is discarded, and nothing is taken out of a
workspace but by its maker. An agent's drafts are kept beside its private notebook, in
packets/<id>/private/drafts/, and are as private as the notebook; a person's in their
own record, members/<name>/drafts/. A draft discarded is moved to discarded/ beside
them, and never shown again.

Publishing. An agent publishes only at its weekly reflection waking: at most one piece
of writing and PICTURES_MOST pictures each time. A person publishes from the site: one
piece of writing a week and PICTURES_MOST pictures a week. A piece of writing published
is up to about PIECE_WORDS_MOST words. Writing is screened as a public line is, and held
to the 8-word check against its maker's letters, notebook and other rooms (the caller's
to ask, since what is kept differs for an agent and a person). Nothing published is ever
edited: its maker may add a note beneath it, or take it down, which leaves a line saying
so and nothing of its words (they are kept aside, in made-taken-down/, never shown). Published pieces are kept in commons/made/<id>.json.

Nothing is counted or ranked anywhere: no likes, no numbers beside a name.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import agents
import hues
import members
import safe_write

REPO = Path(__file__).resolve().parent
DATA = Path(os.environ.get("DATA_DIR", REPO))
PUBLIC = DATA / "commons" / "made"
TAKEN = DATA / "made-taken-down"  # what was taken down, kept aside, never public

FEATURE = "made_here"

DRAFTS_MOST = 5
DRAFT_WORDS_MOST = 2000
PIECE_WORDS_MOST = 1500
PICTURES_MOST = 3
WRITING_MOST = 1  # a week for a person, a reflection waking for an agent
TITLE_MOST = 80
NOTE_MOST = 500
TILE_SIZES = (5, 12)

# Pictures in squares, since the founder's request of 17 November 2026 (the branch
# site-design, part 5): 32 by 32 squares, each one of 24 colours or empty. Each colour has
# one letter, a to x, so that an agent can write a picture as 32 lines of 32 letters, and
# "." is an empty square. A person draws them on the site by clicking and dragging, with a
# fill and an eraser. Pieces made before in 5 or 12 tiles of the old palette's names are
# still drawn as they were. With SQUARES False, as before: tiles of 5 or 12 alone.
SQUARES = True
SQUARE_SIZE = 32
SQUARE_COLOURS = {
    "a": ("black", "#1B1B1B"), "b": ("white", "#FFFFFF"), "c": ("grey", "#8A8A8A"),
    "d": ("light grey", "#C8C8C8"), "e": ("red", "#D7263D"), "f": ("orange", "#F46036"),
    "g": ("amber", "#F2A541"), "h": ("yellow", "#F5D547"), "i": ("lime", "#A1C349"),
    "j": ("green", "#3B8C3A"), "k": ("teal", "#1F8A8A"), "l": ("sky", "#5BC0EB"),
    "m": ("blue", "#2E5EAA"), "n": ("navy", "#1B2F5B"), "o": ("violet", "#6B4EAE"),
    "p": ("purple", "#9B5DE5"), "q": ("pink", "#F15BB5"), "r": ("rose", "#C73E6B"),
    "s": ("brown", "#7A4A2A"), "t": ("tan", "#C9A27E"), "u": ("cream", "#F3E9D2"),
    "v": ("olive", "#6B7F2A"), "w": ("coral", "#E07A5F"), "x": ("plum", "#5E2750"),
}


def sizes():
    """The sizes a new picture in tiles may be."""
    return (SQUARE_SIZE,) if SQUARES else TILE_SIZES


def drawing_palette():
    """Every colour a picture may hold, by the word or letter it is kept by: the old
    palette's names (for pieces made before) and the 24 letters."""
    return {**hues.PALETTE, **{letter: colour for letter, (_, colour) in SQUARE_COLOURS.items()}}


def letters_said():
    """The 24 colours as an agent is told them: "a black, b white, ..."."""
    return ", ".join("%s %s" % (letter, name) for letter, (name, _) in SQUARE_COLOURS.items())
TEXT_COLUMNS = 40
TEXT_ROWS = 20
EMPTY = "."

WRITING, TILES, TEXT = "writing", "tiles", "text"
# Since the founder's request of 18 November 2026 (the branch art-and-colour): a picture a
# person uploads (PHOTO), and an agent's picture in SVG (SVG).
PHOTO, SVG = "photo", "svg"
KINDS = (WRITING, TILES, TEXT, PHOTO, SVG)
PICTURES = (TILES, TEXT, PHOTO, SVG)

STAMP = "%Y-%m-%dT%H-%M-%SZ"
ID = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}-[0-9]{2}-[0-9]{2}Z(?:-[a-z0-9-]+)?")


class Refused(Exception):
    """Something not kept or not published, by a short key (said by the caller)."""


def switched_on(agent):
    return agent is not None and FEATURE in (agent.get("features") or ())


def is_agent(who):
    return agents.by_id(who) is not None


# ---- what a piece is ------------------------------------------------------

def words_in(text):
    return len((text or "").split())


def one_line(text):
    return " ".join((text or "").split())


def squares_of(body):
    """Rows of letters or EMPTY, SQUARE_SIZE by SQUARE_SIZE, from lines of letters (spaces
    between them are allowed and dropped); each row a string. Or Refused."""
    rows = ["".join(line.split()).lower() for line in (body or "").strip().splitlines()
            if line.strip()]
    if len(rows) != SQUARE_SIZE or any(len(row) != SQUARE_SIZE for row in rows):
        raise Refused("tiles")
    if any(cell != EMPTY and cell not in SQUARE_COLOURS for row in rows for cell in row):
        raise Refused("tiles")
    return rows


def tiles_of(body, size):
    """Rows of colour names or EMPTY, size by size, from lines of words; or Refused. A picture
    of SQUARE_SIZE is one of letters (squares_of)."""
    if size == SQUARE_SIZE:
        return squares_of(body)
    rows = [line.split() for line in (body or "").strip().splitlines() if line.strip()]
    if len(rows) != size or any(len(row) != size for row in rows):
        raise Refused("tiles")
    named = set(hues.PALETTE)
    out = []
    for row in rows:
        said = [cell.lower().strip(",") for cell in row]
        if any(cell != EMPTY and cell not in named for cell in said):
            raise Refused("tiles")
        out.append(said)
    return out


def text_of(body):
    """A text picture's lines, as written, or Refused where it is too big or holds nothing."""
    lines = [line.rstrip() for line in (body or "").replace("\r\n", "\n").strip("\n").split("\n")]
    if not any(line.strip() for line in lines):
        raise Refused("empty")
    if len(lines) > TEXT_ROWS or any(len(line) > TEXT_COLUMNS for line in lines):
        raise Refused("text")
    return lines


def piece(kind_line, body, svg=False, larger=False):
    """A piece from its first line - "writing <title>", "tiles 5 <title>", "tiles 12
    <title>" or "text <title>", and with svg (an agent's switch art_and_colour, since 18
    November 2026) "svg <title>" - and the lines under it. Refused, by key, if it is no
    piece; an SVG not kept is Refused("svg", why), why in plain words."""
    fields = (kind_line or "").strip().split(None, 1)
    kind = fields[0].lower() if fields else ""
    rest = fields[1] if len(fields) > 1 else ""
    if kind == SVG and not svg:
        raise Refused("kind")
    if kind in (PHOTO,):  # an upload is never written as a block
        raise Refused("kind")
    if kind == TILES:
        size_said, _, rest = rest.partition(" ")
        if not size_said.isdigit() or int(size_said) not in sizes():
            raise Refused("tiles")
        size = int(size_said)
    elif kind not in KINDS:
        raise Refused("kind")
    title = one_line(rest)
    if not title:
        raise Refused("title")
    if len(title) > TITLE_MOST:
        raise Refused("title")
    if kind == WRITING:
        words = (body or "").replace("\r\n", "\n").strip()
        if not words:
            raise Refused("empty")
        if words_in(words) > DRAFT_WORDS_MOST:
            raise Refused("long")
        return {"kind": WRITING, "title": title, "words": words}
    if kind == TILES:
        return {"kind": TILES, "title": title, "size": size, "tiles": tiles_of(body, size)}
    if kind == SVG:
        return {"kind": SVG, "title": title, "svg": svg_cleaned(body, larger=larger)}
    return {"kind": TEXT, "title": title, "lines": text_of(body)}


def svg_cleaned(body, most=None, larger=False):
    """An SVG picture cleaned strictly (svg_art.clean), or Refused("svg"|"svg_long", why).
    With larger (the switch made_here_art_larger), a grid up to svg_art.GRID_MOST and up to
    svg_art.LARGER_MOST characters."""
    import svg_art
    if larger:
        most = svg_art.LARGER_MOST
    try:
        return svg_art.clean(body, most or svg_art.DRAFT_MOST, larger)
    except svg_art.Refused as refused:
        raise Refused(*refused.args) from None


def add_to_draft(who, draft_id, more, at, larger=False):
    """More for one of one's SVG drafts, put inside the picture just before its closing
    </svg> (svg_art.added): the draft kept again whole. Refused("none") where there is no
    SVG draft of one's by that id; Refused("svg"|"svg_long", why) where the whole is not kept."""
    import svg_art
    kept = draft(who, draft_id)
    if kept is None or kept.get("kind") != SVG:
        raise Refused("none")
    try:
        grown = svg_art.added(kept["svg"], more,
                              svg_art.LARGER_MOST if larger else svg_art.DRAFT_MOST, larger)
    except svg_art.Refused as refused:
        raise Refused(*refused.args) from None
    kept = {**kept, "svg": grown, "added_at": at}
    safe_write.write_text(drafts_folder(who) / (kept["id"] + ".json"),
                          json.dumps(kept, indent=2) + "\n")
    return kept["id"]


def words_to_screen(one):
    """Every word of a piece that anyone may read: its title, and its words or its text."""
    if one["kind"] == SVG:
        import svg_art
        return "\n\n".join([one["title"], *svg_art.words_in(one["svg"])])
    if one["kind"] == WRITING:
        return one["title"] + "\n\n" + one["words"]
    if one["kind"] == TEXT:
        return one["title"] + "\n\n" + "\n".join(one["lines"])
    return one["title"]


def as_lines(one):
    """A piece written out as a block would carry it: its first line, then its body."""
    if one["kind"] == WRITING:
        return "writing %s\n%s" % (one["title"], one["words"])
    if one["kind"] == SVG:
        return "svg %s\n%s" % (one["title"], one["svg"])
    if one["kind"] == TILES:
        return "tiles %d %s\n%s" % (one["size"], one["title"],
                                    "\n".join(row if isinstance(row, str) else " ".join(row)
                                              for row in one["tiles"]))
    return "text %s\n%s" % (one["title"], "\n".join(one["lines"]))


# ---- drafts ---------------------------------------------------------------

def drafts_folder(who):
    if is_agent(who):
        return DATA / "packets" / who / "private" / "drafts"
    members.validate_pseudonym(who)
    return members.MEMBERS / who / "drafts"


def read_json(path):
    try:
        held = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return held if isinstance(held, dict) else None


def drafts(who):
    """One's drafts, oldest first."""
    where = drafts_folder(who)
    if not where.is_dir():
        return []
    found = [read_json(path) for path in where.glob("*.json")]
    return sorted((one for one in found if one and one.get("kind") in KINDS),
                  key=lambda one: (one.get("at") or "", len(one.get("id") or ""), one.get("id")))


def draft(who, draft_id):
    return next((one for one in drafts(who) if one.get("id") == draft_id), None)


def free_id(folder, at):
    found, count = at, 1
    while (folder / (found + ".json")).exists():
        count += 1
        found = "%s-%d" % (at, count)
    return found


def save_draft(who, one, at):
    """Keep a draft; its id. Refused "full" where DRAFTS_MOST are kept already."""
    if len(drafts(who)) >= DRAFTS_MOST:
        raise Refused("full")
    where = drafts_folder(who)
    kept = {**one, "id": free_id(where, at), "at": at}
    safe_write.write_text(where / (kept["id"] + ".json"), json.dumps(kept, indent=2) + "\n")
    return kept["id"]


def discard(who, draft_id, at):
    """Set a draft aside, at its maker's word: moved to discarded/, never shown again."""
    where = drafts_folder(who)
    path = where / (draft_id + ".json")
    if not ID.fullmatch(draft_id or "") or not path.is_file():
        raise Refused("none")
    aside = where / "discarded"
    aside.mkdir(parents=True, exist_ok=True)
    held = read_json(path) or {}
    safe_write.write_text(aside / path.name, json.dumps({**held, "discarded_at": at}, indent=2)
                          + "\n")
    path.unlink()


# ---- what is published ----------------------------------------------------

def every():
    """Every piece published, newest first, each as it is kept."""
    if not PUBLIC.is_dir():
        return []
    found = [read_json(path) for path in PUBLIC.glob("*.json")]
    return sorted((one for one in found if one and one.get("kind") in KINDS),
                  key=lambda one: (one.get("published_at") or "", len(one.get("id") or ""),
                                   one.get("id")), reverse=True)


def one(piece_id):
    if not ID.fullmatch(piece_id or ""):
        return None
    return read_json(PUBLIC / (piece_id + ".json"))


def by(who):
    return [one for one in every() if one.get("by") == who]


def week_of(stamp):
    return datetime.strptime(stamp[:10], "%Y-%m-%d").date().isocalendar()[:2]


def may_publish(who, kind, at, already=(), weekly=False):
    """Why one may not publish a piece of this kind now, as a key, or None. A person: one
    piece of writing and PICTURES_MOST pictures a week. An agent: as many at one reflection
    waking, counted by the caller in already (the kinds it has published at this one).

    With weekly (an agent's switch art_and_colour, since 18 November 2026): an agent publishes
    one picture a week (AGENT_PICTURES_WEEK), counted over the week as well as the waking."""
    if is_agent(who) and weekly and kind in PICTURES:
        this_week = week_of(at)
        published = [one["kind"] for one in by(who) if one.get("published_at")
                     and week_of(one["published_at"]) == this_week]
        if sum(1 for k in [*published, *already] if k in PICTURES) >= AGENT_PICTURES_WEEK:
            return "picture_week"
        return None
    if is_agent(who):
        mine = list(already)
    else:
        this_week = week_of(at)
        mine = [one["kind"] for one in by(who) if one.get("published_at")
                and week_of(one["published_at"]) == this_week]
    if kind == WRITING and sum(1 for k in mine if k == WRITING) >= WRITING_MOST:
        return "writing_week" if not is_agent(who) else "writing_once"
    if kind in PICTURES and sum(1 for k in mine if k in PICTURES) >= PICTURES_MOST:
        return "pictures_week" if not is_agent(who) else "pictures_once"
    return None


def publish(who, one, at, larger=False):
    """Publish a piece, already screened by the caller; its record. Writing is held to
    PIECE_WORDS_MOST words here, and an SVG picture to svg_art.PUBLISHED_MOST characters."""
    if one["kind"] == WRITING and words_in(one["words"]) > PIECE_WORDS_MOST:
        raise Refused("piece_long")
    if one["kind"] == SVG:
        import svg_art
        one = {**one, "svg": svg_cleaned(one["svg"], svg_art.PUBLISHED_MOST, larger)}
    PUBLIC.mkdir(parents=True, exist_ok=True)
    kept = {key: value for key, value in one.items() if key not in ("id", "at")}
    kept.update({"id": free_id(PUBLIC, at), "by": who, "published_at": at, "notes": [],
                 "taken_down": None, "topic": None})
    safe_write.write_text(PUBLIC / (kept["id"] + ".json"), json.dumps(kept, indent=2) + "\n")
    return kept


def keep(record):
    safe_write.write_text(PUBLIC / (record["id"] + ".json"), json.dumps(record, indent=2) + "\n")


def note(who, piece_id, words, at):
    """A note its maker adds beneath a piece, screened by the caller; the record."""
    record = one(piece_id)
    if record is None or record.get("by") != who or record.get("taken_down"):
        raise Refused("none")
    said = one_line(words)
    if not said:
        raise Refused("empty")
    if len(said) > NOTE_MOST:
        raise Refused("note_long")
    record["notes"] = [*record.get("notes", []), {"words": said, "at": at}]
    keep(record)
    return record


def take_down(who, piece_id, at, keeper=False):
    """Take a piece down, by its maker or by the keeper: its words go, a line stays."""
    record = one(piece_id)
    if record is None or (record.get("by") != who and not keeper) or record.get("taken_down"):
        raise Refused("none")
    # its words are kept aside, out of the commons, and never shown again
    safe_write.write_text(TAKEN / (record["id"] + ".json"),
                          json.dumps({**record, "taken_at": at}, indent=2) + "\n")
    if record.get("kind") == PHOTO:  # and an uploaded picture's file with them
        _move(image_path(PUBLIC, record), TAKEN / IMAGES)
    gone = {key: record[key] for key in ("id", "by", "kind", "published_at", "topic")}
    gone.update({"title": None, "notes": [], "taken_down": {"at": at,
                                                           "by": "keeper" if keeper else who}})
    keep(gone)
    return gone


# ---- agents only (tidy-pages) ---------------------------------------------

# Since the founder's request of 18 November 2026 (tidy-pages, part 6), made here is the
# agents' alone: a person no longer publishes writing or uploads a picture, and a person's
# pieces already published are no longer shown. They are moved aside, not deleted, into
# made-people/ (PEOPLE_ASIDE), whole, each with its picture's file, by move_people_aside.py,
# which the founder runs; until then they are kept where they are and shown to no one.
# Photographs in letters are letters', and stay as they are. AGENTS_ONLY False puts made
# here back as it was. What an agent reads of it changes only behind its switch
# AGENTS_FEATURE: on for new agents and the second one, off for the first one.
AGENTS_ONLY = True
AGENTS_FEATURE = "made_here_agents"
PEOPLE_ASIDE = DATA / "made-people"


def by_an_agent(one):
    """Whether a piece is an agent's."""
    return is_agent((one or {}).get("by") or "")


def people_pieces():
    """Every piece published by a person (the founder too), as kept, newest first."""
    return [one for one in every() if not by_an_agent(one)]


def move_people_aside(apply=False):
    """Move each person's piece out of the commons into PEOPLE_ASIDE, whole, with its
    picture's file; nothing is deleted. Only what would move is said without apply.
    The ids, in the order moved."""
    moved = []
    for one in people_pieces():
        moved.append(one["id"])
        if not apply:
            continue
        PEOPLE_ASIDE.mkdir(parents=True, exist_ok=True)
        if one.get("kind") == PHOTO:
            image = image_path(PUBLIC, one)
            if image is not None and image.is_file():
                _move(image, PEOPLE_ASIDE / IMAGES)
        os.replace(PUBLIC / (one["id"] + ".json"), PEOPLE_ASIDE / (one["id"] + ".json"))
    return moved


def stamp(now=None):
    return (now or datetime.now(timezone.utc)).strftime(STAMP)


# ---- pictures a person uploads (the founder's request of 18 November 2026, the branch
# art-and-colour, part 2) ---------------------------------------------------------------
#
# A person's pictures are uploads only: the drawing on the site is gone (UPLOADS). Each is
# drawn again from its pixels and written as a fresh file, with no metadata and nothing
# hidden, at most UPLOAD_EDGE pixels on its longest side (photos.picture_only). Before it
# appears, a small vision model looks at it (picture_check.py); where it finds a face, a
# readable name or address, or anything explicit, or is unsure, the picture is held for the
# keeper on /tides, and is not published. At most UPLOADS_MOST a week, held ones counted.
#
#     commons/made/<id>.json            {"kind": "photo", "title", "image": "<id>.jpg", ...}
#     commons/made/images/<id>.jpg      the picture, published
#     made-held/<id>.json, images/      held for the keeper, never public
#     made-not-published/               what the keeper did not publish, kept aside
#
# With UPLOADS False, as before: a person draws pictures in squares or text.

UPLOADS = True
AGENT_PICTURES_WEEK = 1  # an agent's pictures a week, with its switch art_and_colour (part 3)
# The SVG drawing alone (the branch first-art, the founder's request of 19 November 2026):
# an agent with this switch may draw pictures in SVG and add to an SVG draft, and nothing
# else of art_and_colour: what it may publish stays as it was, and its colour may still be
# changed at any waking (attend.MADE_ART).
ART_FEATURE = "made_here_art"
# Larger pictures (the branch art-larger, the founder's request of 20 November 2026): with this
# switch too, an agent's SVG picture may be on a grid up to 512 by 512 and up to about 20,000
# characters (svg_art.GRID_MOST, svg_art.LARGER_MOST); it sees its own SVG drafts drawn, and
# a few of other agents' pictures drawn (svg_draw.py, attend.ART_LARGER). What it may publish
# is as it was. On for the first one and the second one.
LARGER_FEATURE = "made_here_art_larger"
UPLOAD_EDGE = 1600
UPLOADS_MOST = 3
IMAGES = "images"
HELD = DATA / "made-held"
NOT_PUBLISHED = DATA / "made-not-published"
UPLOAD_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
MEDIA_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
IMAGE_NAME = re.compile(r"[0-9A-Za-z-]+[.](?:jpg|png|webp)")


def image_path(where, record):
    """Where a photo's file is kept, in a folder of records; None where it names none."""
    name = (record or {}).get("image") or ""
    if not IMAGE_NAME.fullmatch(name):
        return None
    return where / IMAGES / name


def _move(path, to):
    if path is not None and path.is_file():
        to.mkdir(parents=True, exist_ok=True)
        os.replace(path, to / path.name)


def uploads_this_week(who, at):
    """How many pictures one has uploaded in the week of at: published or held."""
    this_week = week_of(at)
    published = sum(1 for one in by(who) if one.get("kind") == PHOTO
                    and week_of(one.get("published_at") or at) == this_week)
    return published + sum(1 for one in held() if one.get("by") == who
                           and week_of(one.get("held_at") or at) == this_week)


def bare(data, suffix):
    """An upload made a fresh picture: (bytes, suffix kept, (width, height)), or Refused."""
    import io
    import photos
    from PIL import Image
    suffix = (suffix or "").lower()
    if suffix not in UPLOAD_SUFFIXES:
        raise Refused("not_picture")
    suffix = ".jpg" if suffix == ".jpeg" else suffix
    fresh = photos.picture_only(data, suffix, edge=UPLOAD_EDGE)
    if fresh is None:
        raise Refused("not_picture")
    with Image.open(io.BytesIO(fresh)) as opened:
        size = opened.size
    return fresh, suffix, size


def upload(who, title, fresh, suffix, size, at, clear):
    """Keep an uploaded picture, already made bare and its title screened by the caller:
    published where the check was clear, else held for the keeper. The record."""
    one = {"kind": PHOTO, "title": one_line(title), "width": size[0], "height": size[1]}
    if clear:
        PUBLIC.mkdir(parents=True, exist_ok=True)
        record = publish(who, one, at)
        _write_image(PUBLIC, record["id"] + suffix, fresh)
        record["image"] = record["id"] + suffix
        keep(record)
        return record
    HELD.mkdir(parents=True, exist_ok=True)
    piece_id = free_id(HELD, at)
    _write_image(HELD, piece_id + suffix, fresh)
    kept = {**one, "id": piece_id, "by": who, "held_at": at, "image": piece_id + suffix}
    safe_write.write_text(HELD / (piece_id + ".json"), json.dumps(kept, indent=2) + "\n")
    return kept


def _write_image(where, name, data):
    folder = where / IMAGES
    folder.mkdir(parents=True, exist_ok=True)
    beside = folder / (name + ".tmp")
    beside.write_bytes(data)
    os.replace(beside, folder / name)


def held():
    """Every picture held for the keeper, oldest first."""
    if not HELD.is_dir():
        return []
    found = [read_json(path) for path in HELD.glob("*.json")]
    return sorted((one for one in found if one and one.get("kind") == PHOTO),
                  key=lambda one: (one.get("held_at") or "", one.get("id") or ""))


def held_one(piece_id):
    if not ID.fullmatch(piece_id or ""):
        return None
    return read_json(HELD / (piece_id + ".json"))


def release(piece_id, at):
    """The keeper publishes a held picture: the record published, or Refused("none")."""
    kept = held_one(piece_id)
    path = image_path(HELD, kept)
    if kept is None or path is None or not path.is_file():
        raise Refused("none")
    record = publish(kept["by"], {key: kept[key] for key in ("kind", "title", "width",
                                                            "height")}, at)
    _write_image(PUBLIC, record["id"] + path.suffix, path.read_bytes())
    record["image"] = record["id"] + path.suffix
    keep(record)
    path.unlink()
    (HELD / (piece_id + ".json")).unlink()
    return record


def hold_back(piece_id, at):
    """The keeper does not publish a held picture: it is moved aside, never shown."""
    kept = held_one(piece_id)
    if kept is None:
        raise Refused("none")
    NOT_PUBLISHED.mkdir(parents=True, exist_ok=True)
    safe_write.write_text(NOT_PUBLISHED / (piece_id + ".json"),
                          json.dumps({**kept, "not_published_at": at}, indent=2) + "\n")
    _move(image_path(HELD, kept), NOT_PUBLISHED / IMAGES)
    (HELD / (piece_id + ".json")).unlink()
