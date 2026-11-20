#!/usr/bin/env python3
"""Move the keeper's files from their sign-in name to the id "founder" (names-design.md, part 2
and 6; the founder's request of 20 November 2026).

Today the keeper's folder, knocks, blocks, notes, invitations and board posts are kept under
their sign-in name, while the rooms, bonds and letters name them "founder". Two names for one
keeper is the leave bug, and it puts the sign-in name where it could be shown. This moves
every unsigned place that holds the sign-in name to "founder", and the sign-in name becomes
the keeper's private sign-in (members/sign-in.json).

    python move_to_ids.py              a dry run: lists every move, changes nothing
    python move_to_ids.py --apply      makes the moves, and keeps a record of each
    python move_to_ids.py --undo       puts back every move the record holds

--apply refuses unless an encrypted backup was taken in the last FRESH_HOURS (backup.log, as
the hearth writes it), and refuses while the record of an earlier move stands. Run it with the
hearth stopped, or straight after a backup with nothing else going on. The keeper signs in
again afterwards, with the same sign-in name and password.

What moves (unsigned, keyed by the name):
  members/<name>/ whole, as members/founder/, its member.json saying id and pseudonym
  "founder" and sign_in <name>; knocks/, knocks/history/ and knocks/taken-back/ files
  named by it, and their "from" and "to"; notes/<a>--<b>.json, named again in order, and
  their "between" and each note's "from"; every "who" in every blocks.json (members' and
  agents'); invitations' "by", "withdrawn_by" and "used_by"; members' "vouched_by";
  commons/board.json's "by" and "mentions"; weekly-questions.json's "by"; proposals'
  "answered_by" and "built_by" member; tokens' "name"; askings/people/<name>.json.

What stays, and is listed: anything signed (bonds, witness marks, DIDs: the keeper's DID is
the founder's already), public lines already written (commons/*.md), letter file names
(founder-<stamp>, which never held the name), and any room made as <agent>-<name>, whose id is
its bond's id (choice 6).

Every file changed is kept whole before its change in moved-to-ids.json, beside the members,
with every folder or file moved, so --undo puts each back as it was. The record is private: it
holds the sign-in name.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KEEPER_ID = "founder"
FRESH_HOURS = 6
RECORD = "moved-to-ids.json"
SEP = "--"


class Refused(Exception):
    """The move will not be made, and nothing was changed."""


def utc_now():
    return datetime.now(timezone.utc)


def data():
    return Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent))


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def keeper_name(root):
    """The keeper's folder name, from the members' records: the one whose role is keeper."""
    folder = root / "members"
    found = []
    if folder.is_dir():
        for one in sorted(folder.iterdir()):
            record = read_json(one / "member.json") if one.is_dir() else None
            if isinstance(record, dict) and record.get("role") == "keeper":
                found.append(one.name)
    if len(found) != 1:
        raise Refused("there must be exactly one keeper; found %d" % len(found))
    return found[0]


def fresh_backup(root, now):
    """The moment of the newest whole backup in backup.log, if it is fresh; else Refused."""
    log = root / "backup.log"
    newest = None
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            parts = [part.strip() for part in line.split("·")]
            if len(parts) == 4 and parts[1] == "backed up" and parts[3].startswith("kept "):
                try:
                    newest = datetime.strptime(parts[0], "%Y-%m-%dT%H-%M-%SZ").replace(
                        tzinfo=timezone.utc)
                except ValueError:
                    continue
    if newest is None or now - newest > timedelta(hours=FRESH_HOURS):
        raise Refused("take an encrypted backup first: none was taken in the last %d hours"
                      % FRESH_HOURS)
    return newest


# ---- the plan: what would change, worked out from the disk, changing nothing --------------

def swapped(value, old):
    """A name, or a list of names, with old as KEEPER_ID."""
    if value == old:
        return KEEPER_ID
    if isinstance(value, list):
        return [KEEPER_ID if one == old else one for one in value]
    return value


def renamed_pair(stem, old):
    """A <a>--<b> file stem with old as KEEPER_ID, or None where it holds no old."""
    sides = stem.split(SEP)
    if len(sides) != 2 or old not in sides:
        return None
    return SEP.join(KEEPER_ID if side == old else side for side in sides)


def knocks_plan(root, old):
    moves, rewrites = [], []
    for folder in (root / "knocks", root / "knocks" / "history", root / "knocks" / "taken-back"):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            held = read_json(path)
            stem = path.stem
            new_stem = renamed_from_start(stem, old)
            changed = dict(held) if isinstance(held, dict) else None
            if changed is not None:
                for key in ("from", "to"):
                    changed[key] = swapped(changed.get(key), old)
            if new_stem != stem:
                moves.append((path, path.with_name(new_stem + ".json")))
            if changed is not None and changed != held:
                rewrites.append((path.with_name(new_stem + ".json"), held, changed))
    return moves, rewrites


STAMPED = re.compile(r"(.+)(-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z)")


def renamed_from_start(stem, old):
    """A knock's file stem, <from>--<to>, or <from>--<to>-<at> in history/ and taken-back/,
    with old as KEEPER_ID."""
    found = STAMPED.fullmatch(stem)
    pair, at = (found.group(1), found.group(2)) if found else (stem, "")
    renamed = renamed_pair(pair, old)
    return (renamed + at) if renamed else stem


def notes_plan(root, old):
    moves, rewrites = [], []
    folder = root / "notes"
    if not folder.is_dir():
        return moves, rewrites
    for path in sorted(folder.glob("*.json")):
        sides = path.stem.split(SEP)
        if len(sides) != 2 or old not in sides:
            continue
        new = path.with_name(SEP.join(sorted(KEEPER_ID if one == old else one
                                             for one in sides)) + ".json")
        held = read_json(path)
        if isinstance(held, dict):
            changed = dict(held)
            changed["between"] = swapped(held.get("between"), old)
            if isinstance(changed["between"], list):
                changed["between"] = sorted(changed["between"])
            if isinstance(held.get("notes"), list):
                changed["notes"] = [dict(one, **({"from": KEEPER_ID} if isinstance(one, dict)
                                                 and one.get("from") == old else {}))
                                    if isinstance(one, dict) else one for one in held["notes"]]
            if changed != held:
                rewrites.append((new, held, changed))
        if new != path:
            moves.append((path, new))
    return moves, rewrites


def deep_swapped(value, old, keys):
    """A JSON value with every one of keys that holds old (or a list holding it) swapped."""
    if isinstance(value, dict):
        return {key: (swapped(inner, old) if key in keys else deep_swapped(inner, old, keys))
                for key, inner in value.items()}
    if isinstance(value, list):
        return [deep_swapped(one, old, keys) for one in value]
    return value


def json_plan(paths, old, keys):
    rewrites = []
    for path in paths:
        held = read_json(path)
        if held is None:
            continue
        changed = deep_swapped(held, old, keys)
        if changed != held:
            rewrites.append((path, held, changed))
    return rewrites


def proposals_plan(root, old):
    rewrites = []
    for path in sorted((root / "packets").glob("*/proposals/*.json")):
        if "private" in path.parts:
            continue
        held = read_json(path)
        if not isinstance(held, dict):
            continue
        changed = dict(held)
        for key in ("answered_by", "built_by"):
            one = held.get(key)
            if isinstance(one, dict) and one.get("member") == old:
                changed[key] = dict(one, member=KEEPER_ID)
        if changed != held:
            rewrites.append((path, held, changed))
    return rewrites


def plan(root=None):
    """Every move and rewrite, and what is left as it is: changing nothing."""
    root = data() if root is None else root
    old = keeper_name(root)
    if old == KEEPER_ID:
        raise Refused("the keeper's id is founder already: there is nothing to move")
    if (root / "members" / KEEPER_ID).exists():
        raise Refused("members/founder is there already, and is not the keeper's")
    moves, rewrites = [], []
    member = root / "members" / old
    record = read_json(member / "member.json")
    moves.append((member, root / "members" / KEEPER_ID))
    rewrites.append((root / "members" / KEEPER_ID / "member.json", record,
                     dict(record, pseudonym=KEEPER_ID, id=KEEPER_ID, sign_in=old)))
    index = root / "members" / "sign-in.json"
    held_index = read_json(index) if index.is_file() else None
    if isinstance(held_index, dict) and held_index.get(old) not in (None, old):
        raise Refused("the keeper's sign-in name is someone else's sign-in")
    rewrites.append((index, held_index,
                     {**{k: v for k, v in (held_index or {}).items() if v != old},
                      old: KEEPER_ID}))
    knock_moves, knock_rewrites = knocks_plan(root, old)
    note_moves, note_rewrites = notes_plan(root, old)
    moves += knock_moves + note_moves
    rewrites += knock_rewrites + note_rewrites
    asked = root / "askings" / "people" / (old + ".json")
    if asked.is_file():
        moves.append((asked, asked.with_name(KEEPER_ID + ".json")))
    blocks = [*sorted((root / "members").glob("*/blocks.json")),
              *sorted((root / "packets").glob("*/blocks.json"))]
    after = {str(path): str(path).replace(str(member), str(root / "members" / KEEPER_ID), 1)
             for path in blocks}
    for path, held, changed in json_plan(blocks, old, ("who",)):
        rewrites.append((Path(after[str(path)]), held, changed))
    vouched = [path for path in sorted((root / "members").glob("*/member.json"))
               if path.parent.name != old]
    rewrites += json_plan(vouched, old, ("vouched_by",))
    rewrites += json_plan(sorted((root / "invitations").glob("*.json")), old,
                          ("by", "withdrawn_by", "used_by"))
    rewrites += json_plan([root / "commons" / "board.json"], old, ("by", "mentions"))
    rewrites += json_plan([root / "weekly-questions.json"], old, ("by",))
    rewrites += json_plan(sorted((root / "tokens").glob("*.json")), old, ("name",))
    rewrites += proposals_plan(root, old)
    rooms = [path.name for path in sorted((root / "rooms").glob("*-" + old))]
    return {"old": old, "moves": moves, "rewrites": rewrites, "rooms_left": rooms}


def said(root, step):
    step = Path(step)
    return step.relative_to(root).as_posix() if str(step).startswith(str(root)) else str(step)


def listed(root, made):
    lines = ["The keeper's files move from their sign-in name to \"founder\"."]
    for source, target in made["moves"]:
        lines.append("move     %s -> %s" % (said(root, source), said(root, target)))
    for path, _, _ in made["rewrites"]:
        lines.append("rewrite  %s" % said(root, path))
    for room in made["rooms_left"]:
        lines.append("left     rooms/%s (its id is its bond's id; choice 6)" % room)
    lines.append("left     every signed record, every public line, every letter's file name")
    return lines


# ---- apply and undo -------------------------------------------------------------------------

def write_json(path, value):
    import safe_write
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_write.write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def apply(root=None, now=None):
    root = data() if root is None else root
    now = now or utc_now()
    record_path = root / "members" / RECORD
    if record_path.exists():
        raise Refused("a move is recorded already (%s): undo it first" % said(root, record_path))
    fresh_backup(root, now)
    made = plan(root)
    done = {"at": now.strftime("%Y-%m-%dT%H-%M-%SZ"), "old": made["old"], "moves": [],
            "rewrites": []}
    for source, target in made["moves"]:
        if target.exists():
            raise Refused("%s is there already" % said(root, target))
    for source, target in made["moves"]:
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
        done["moves"].append([str(source), str(target)])
        write_json(record_path, done)
    for path, held, changed in made["rewrites"]:
        done["rewrites"].append({"path": str(path), "before": held})
        write_json(record_path, done)
        if changed is None:
            continue
        write_json(path, changed)
    write_json(record_path, done)
    return done


def undo(root=None):
    root = data() if root is None else root
    record_path = root / "members" / RECORD
    done = read_json(record_path)
    if not isinstance(done, dict):
        raise Refused("there is no move recorded to undo")
    for one in reversed(done.get("rewrites") or []):
        path = Path(one["path"])
        if one["before"] is None:
            if path.exists():
                path.unlink()
        else:
            write_json(path, one["before"])
    for source, target in reversed(done.get("moves") or []):
        os.replace(target, source)
    record_path.unlink()
    return done


def main(argv=None):
    parser = argparse.ArgumentParser(description="Move the keeper's files to the id founder.")
    parser.add_argument("--apply", action="store_true", help="make the moves")
    parser.add_argument("--undo", action="store_true", help="put back the moves recorded")
    args = parser.parse_args(argv)
    root = data()
    try:
        if args.undo:
            done = undo(root)
            print("Undone: %d moves and %d files put back as they were."
                  % (len(done["moves"]), len(done["rewrites"])))
            return 0
        made = plan(root)
        print("\n".join(listed(root, made)))
        if not args.apply:
            print("A dry run: nothing was changed. Run again with --apply to make the moves.")
            return 0
        done = apply(root)
        print("Done: %d moves and %d files rewritten. The record is members/%s. The keeper "
              "signs in again with the same sign-in name and password."
              % (len(done["moves"]), len(done["rewrites"]), RECORD))
        return 0
    except Refused as refused:
        print("Refused:", refused)
        return 1


if __name__ == "__main__":
    sys.exit(main())
