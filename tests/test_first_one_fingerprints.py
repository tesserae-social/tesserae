"""What the first one's world gives back, held before wakings are made for any agent.

Stage 0 of the work that lets the tide wake more than one agent (the proposal
"waking for any agent", 25 October 2026). Nothing here changes what the hearth
or attend.py runs: it only takes fingerprints of what they give back today, so
that each later stage can show that, for the first one, nothing moved.

The reading and the packet as they stood before a waking are held already, in
test_rooms_reading.py. These are the rest of it, each taken on one small fixed
world after one waking with the model stubbed and the clock pinned:

  * the files the waking left, as they lie on the disk;
  * its heartbeat line and the commons' events, word for word;
  * the founder's pages - the hearth, the room, the letters, its self-document,
    the attendances, the chronicle, the export page, the bonds and the commons -
    with the one thing on them that is cut afresh for every visit, the form
    token, taken out;
  * the export, as the names inside it and the bytes under each;
  * the nightly backup, the same way, and as the disk keeps it;
  * the tide: what it notes in tide.log, and what it would run, over a few
    dawns - one held, one skipped, one stopped, a rest ended, an extra waking;
  * the atrium: what it draws between its markers, on the front page and in
    the whole mosaic;
  * members.md, as the hearth tends it.

Everything signed is signed by fixed keys cut here from fixed seeds, and not by
the throwaway keys of the session, which are new each run: an Ed25519 signature
is the same every time for the same key and the same bytes, so a signed record
gives the same fingerprint every run. The founder's vault is sealed afresh each
session, so of the members' store only the names are held. Nothing random is
asked of the world: no promise is made, since a promise is salted.

If one of these moves on purpose, it is cut again on purpose, in the same change,
and the change says why. Each is printed when it is taken, so that cutting one
again is a matter of reading it off the run.
"""

import base64
import hashlib
import io
import json
import re
import sys
import tarfile
import zipfile
from datetime import date

import pytest
from nacl.signing import SigningKey

from conftest import (pages_before_design, who_fix_not_yet,atrium_before_design, asked_described_as_before, made_here_not_yet, offerings_as_before, atrium_before_doors, blocks, block, letter_part_as_before, page,
                      pages_before_doors, pages_before_fewer, pages_before_settings,
                      pages_before_pages, pages_before_small,
                      pages_before_saturday, pages_before_week, here_not_yet, post, registry_six_not_yet, registry_switches_not_yet,
                      rooms_to_twelve, times_as_before,
                      wakings_not_yet_switched, write, site_bookkeeping, write_json)
from test_rooms_reading import ERRAND, a_small_world, fingerprint_of_files

# ---- the fingerprints ----------------------------------------------------

# Cut again on 25 October 2026, in the change that took every regional place
# out of what is public or read, and for nothing else. rhythm.json, which the
# waking writes, names no place now and its clock as America/New_York, so the
# files, the export and the backup moved. The attendances page says the rhythm
# without a place, and the next dawn as it comes where the tests watch the sun
# from (conftest.SUN_WATCHED_FROM). With the place, the old name of the zone and
# the sun as it was watched from before all put back, every one of them gives
# exactly what it was cut as; the tide and the atrium did not move at all.

# The files after the waking, as they lie on the disk, the room's own folder and
# its room.json included. Beside it was FILES_AFTER, the same files as a copy
# named them until stage 5f, the room's under packets/first/ and no room.json
# (d933ffcd5df858c262fd564f2d16e499b602a9ca7ae8b203f8a7d6556ffc9e1c; in the old
# packet layout, gone since stage 5c, it was this one too). It went when a copy
# came to name the room's files as they are kept.
#
# Cut again on 10 November 2026, in the change by which the hearth no longer
# writes the part of the day in a person's letter line (the founder's decision
# that day), and for nothing else: commons/events.md, as the waking leaves it,
# says "2026-10-15 · letter · the founder wrote a letter" where it said "... at
# dawn". The same change moved EVENTS_AFTER, three of the founder's pages,
# EXPORT and BACKUP, each for that line alone. With the line written as it was
# (conftest.letter_part_as_before), each of them is exactly the one held before,
# in LETTER_PARTS_BEFORE below; nothing else moved.
ON_DISK_AFTER = "0deb050b7f042166c5c59654310190259a7ab4e02d0396abf6661601f888b8aa"

# The founder's pages, one by one.
#
# Nine of them cut again on 29 October 2026, in the change that tidied the
# pages (the proposal "page-tidy"), and for nothing else. Every page of the
# founder's lost the footer "the books will open with the commons", gained
# "tides" in the keeping menu, which is now always shown to the keeper, and
# carries the few lines of style for the new folds: so /, /rooms/first, /self,
# /attendances, /chronicle, /export and /commons moved for that alone, /self
# with nothing else. Besides it: home shows its correspondences above the door;
# the room puts the letter and Send first, and folds the three plain things,
# the photograph, the commons line, the errand and the proposal under "more";
# the attendances page shows each waking as one line under "wakings", its open
# reflection folded beneath it, and has lost the founder's rest (now on
# /account) and the backup line and button (now on /backups); the commons
# says in one line what a bond and an offering are, and what heartbeats are;
# the chronicle, in the page and in /chronicle.md, says a waking came "by
# hand" where it said "by the founder's hand"; and members.md, as the hearth
# tends it, no longer says the founder "keeps the hearth". /letters and /bonds
# did not move; nor did the files, the export, the backup, the tide or the atrium.
#
# /rooms/first cut again the same day, in the change that put back above the
# letter what waits on the founder - the offerings awaiting a signature and the
# open errands, "asked of you" - as it stood before the tidy-up; only the
# optional extras stay folded under "more". This world has an open errand, so
# the room moved for that alone; no other page did.
#
# /rooms/first cut again on 5 November 2026, in the change that built the quiet
# lines (the first one's letter of 4 November), and for nothing else: one muted
# line, "A few words is enough. Weeks get full.", directly above the three plain
# things; and the three plain things, with that line, brought out of the "more"
# fold to stand between the letter box and Send, always in view. The photograph,
# the commons line, the errand and the proposal stay folded. With the muted line
# taken out and the three put back at the top of the fold, it gives exactly the
# fingerprint it was cut as before (ROOM_BEFORE_QUIET, held below). No other page
# moved: /account, where a person says how they write, is not among these.
ROOM_BEFORE_QUIET = "5aca4f845053d255d8669653b0b884f633ac0af49ae537518aec459c65357206"
FEW_WORDS = '    <p class="muted">A few words is enough. Weeks get full.</p>\n'
LETTER_BOX_ENDS = "</textarea>\n"
SEND = '    <button type="submit">Send</button>\n'
FOLD_OPENS = "      <summary>more</summary>\n"

# Three cut again on 10 November 2026, in the change by which every public page
# and file says the day of a thing and not its time (the founder's decision that
# day), and for nothing else. /commons/heartbeats.md is handed out with each
# line's day in its stamp's place, "- 2026-10-15 at dawn · the first one · ...",
# where it was "- 2026-10-15T12-00-00Z · ..."; the file on the disk keeps the
# stamp. /chronicle and /chronicle.md say each waking's and letter's day, "15
# October 2026", where they said "15 October 2026, 08:00", and the chronicle page
# no longer says its times are Eastern, since it shows none. With the times put
# back (conftest.times_as_before), each is exactly the one held before, in
# TIMES_BEFORE below; nothing else moved.
#
# Seven cut again on 10 November 2026, in the change that made fewer pages (the
# founder's decision that day), and for nothing else. Every page of the founder's
# carries the members' menu as home · account · the commons · log out, where it
# read home · account · the bench · the commons · tesserae.social · log out, and
# the keeper's as tides · backups, where it read chronicle · attendances · self ·
# export · backups · tides: so /, /self, /chronicle, /export and /commons moved
# for that alone. Besides it: the room, under "more", has the first one's wakings,
# closed, as /attendances shows them, its rhythm line, and links to its self, its
# chronicle and a copy; /attendances no longer carries the emergency stop or the
# note on its reflections, which are on /tides. /letters, /bonds, the plain files,
# the export, the backup, the tide and the atrium did not move. With the pages
# drawn as before (conftest.pages_before_fewer), each is exactly the one held
# before, in FEWER_PAGES_BEFORE below, and the room with its few words taken out
# is ROOM_BEFORE_QUIET again.
#
# /chronicle cut once more on 10 November 2026, where the two changes above met
# (branch thursday), and for nothing else: it says each thing's day and carries
# the fewer menus. With the times put back alone (conftest.times_as_before) it
# is the fewer pages' cut, 2bc8c81a...; with the pages drawn as before alone
# (conftest.pages_before_fewer), the dates' cut, dedd8189...; with both, the
# one held before either, edb10a26... - each held in TIMES_BEFORE,
# FEWER_PAGES_BEFORE and BOTH_BEFORE below.
# /commons cut again on 11 November 2026, in the changes that made the ledger and
# the page of changes to the charter (the founder's decisions that day), and for
# nothing else: the foot of the commons page links to each, one line apiece, the
# ledger first. Each branch cut it alone (the ledger's a3b5c74d..., the changes'
# 79774e49...); merged on thursday it is cut once more, for both lines. With the
# commons' own pages taken out (conftest.commons_pages_not_yet) it is exactly
# what it was, COMMONS_PAGES_BEFORE below.
# /commons cut again on 11 November 2026, by the founder's decision that day, for
# one plain link to the bench near its top and nothing else (a member's menu no
# longer names the bench). With that link taken out (conftest.bench_link_not_yet)
# it is exactly the page merged on thursday, BENCH_LINK_BEFORE below.
# / and /commons cut again, on purpose, on 13 November 2026, on the branch
# switches, when the founder switched on for the first one the four things it
# agreed to (asked, introduction, doors_to_eight, people_waiting), and for
# nothing else: /, under the door, says "Friendships here are usually between
# one and eight." (door.USUALLY, now that a door is held to eight); /commons
# links "asked and answered" at its foot after the changes to the charter (now
# that an agent's registry entry names it). With the four taken out of the
# registry again (conftest.registry_switches_not_yet) each is exactly the one
# held before, in SWITCHES_BEFORE below.
# /commons cut again, on purpose, on 13 November 2026, on the branch board (plan
# 4.3), for one plain link to the members' board below the bench's and nothing
# else. With that link taken out (conftest.board_link_not_yet, gone since) it was
# exactly the page cut for the four, BOARD_LINK_BEFORE below.
#
# Every page but the plain files cut again, on purpose, on 14 November 2026, on
# the branch saturday, by the founder's request that day for one spacing scale on
# every page. base.html now draws the scale out of style.css (hearth.SPACING) into
# its own style, writes every gap and margin as one of it, and wraps a page's
# content in <div class="page"> so that whatever a page begins with stands the same
# space below the menu. With the base.html of before drawn in its place
# (conftest.pages_before_saturday), each is exactly the one held before, in
# SATURDAY_BEFORE below; nothing else moved, and the first one's reading did not.
# Two moved besides, on their own, by the same request: /commons is one plain list
# of the commons' pages, a small link and a line beneath each, the board first;
# /bonds, which sent the founder on to the commons' sealed bonds, is a page of
# them of its own. Their views as they were cannot be drawn again here (the old
# commons page linked the bench, which is gone): what they were is on the branch
# hues, and their fingerprints are held in SATURDAY_BEFORE with the rest. The
# commons' older fingerprints (COMMONS_PAGES_BEFORE, BENCH_LINK_BEFORE,
# SWITCHES_BEFORE['/commons'], BOARD_LINK_BEFORE and FEWER_PAGES_BEFORE['/commons'])
# are kept as they were, for the record, and are no longer drawn.
#
# / and /commons cut again, on purpose, on 14 November 2026, on the branch
# intro-500 (the founder's request that day, part 2), and for nothing else: /, the
# founder's own door, offers room from 1 to 8, where it offered 1 to 12, as every
# person's door now does; /commons lists "corrections" last, now that corrections
# is switched on for the first one. No knock waits, so / shows none. With rooms put
# back to twelve (conftest.rooms_to_twelve) and the six of that day taken out of the
# registry (conftest.registry_six_not_yet), each is exactly the one held before, in
# PART_TWO_BEFORE below.
#
# Every page but /letters and the plain files cut again, on purpose, on 15 November
# 2026, on the branch pages, by the founder's request that day: the members' menu
# begins with tesserae.social; the space under the menu is one step of the scale
# smaller (--space-5 where it was --space-6); and / is two columns on a wide screen,
# the correspondences on the left and the door on the right, with main the wider
# class "wide". (/account moved too, its settings last; no page here holds it.) With
# the base.html, hearth.html and account.html of before drawn in their place
# (conftest.pages_before_pages), each is exactly the one held before, in
# PAGES_BRANCH_BEFORE below; nothing else moved, and no waking did.
#
# The same pages cut again, on purpose, later that day, on the same branch, for the
# small changes of report-15-nov-2 part 5: base.html has one rule, .spaced, for the
# top margins letters.html said inline (and /rooms/first uses it), and /bonds says
# "nothing yet" where it said "none yet". With the templates of before drawn in their
# place (conftest.pages_before_small) each is exactly the one held before, in
# SMALL_BEFORE below. No waking moved.
#
# Every page with the members' menu cut again, on purpose, later still on 16 November
# 2026, on the branch rooms, by the founder's request that day (part B4: offerings taken
# out of the code), and for nothing else: base.html loses its style for the fold that
# offered a letter (on every page); /commons loses its line for offerings; /export says
# "the bond records" where it said "the bond and offering records"; and the room loses
# the fold under each letter that offered it to the commons. Drawn as before
# (conftest.offerings_as_before) each but the room is exactly the one held before, in
# OFFERINGS_BEFORE below; the room cannot be drawn as it was, since the routes its forms
# went to are gone, and its fingerprints from before are kept as values for the record.
#
# Every page with the members' menu cut again, on purpose, later on 16 November 2026, on
# the branch rooms, by the founder's request that day (part B1, settings), and for nothing
# else: the menu says "settings" where it said "account", and links /settings, where the
# page now is (/account leads there). With the base.html of before drawn in its place and
# the page linked at /account again (conftest.pages_before_settings) each is exactly the
# one held before, in SETTINGS_BEFORE below. No reading moved.
#
# / cut again, on purpose, on 16 November 2026, on the branch rooms, by the founder's
# request that day (part A, the rooms update), and for nothing else: the name on each
# correspondence's card links to its page, and the right column begins with "Doors open
# now", up to five doors open with room left, where there are any. With the templates of
# before drawn in their place (conftest.pages_before_doors) it is exactly the one held
# before, in DOORS_BEFORE below. No waking moved.
#
# / cut again, on purpose, on 17 November 2026, on the branch agents-week, by the founder's
# request that day (part 5, who is here), and for nothing else: the right column holds "Who
# is here", the agents (here the first one alone, so the order is the same every run) with
# its line "find someone". With the templates of before drawn in their place
# (conftest.pages_before_week) it is exactly the one held before, in WEEK_BEFORE below. No
# waking moved.
#
# / cut again, on purpose, on 17 November 2026, on the branch site-design (the founder's
# request that day, later still), and for nothing else: part 3, "Doors open now" taken off
# the home page, and "find someone ->" said under who is here whether or not anyone is
# shown. With the templates of before drawn in their place (conftest.pages_before_design)
# it is exactly the one held before, in DESIGN_BEFORE below. No waking moved.
#
# /rooms/first, /self, /attendances, /chronicle, /export and /bonds cut on purpose, on the
# same branch, part 7, and for nothing else: each has a small back link above its title
# ("<- home", or "<- the commons" for /chronicle and /bonds), and its title is set in a
# little beneath it, in the size of a section label, with the two rules that draw them in
# its own style block. With the templates of before (conftest.pages_before_design) each is
# exactly the one held before, in DESIGN_BEFORE (and /chronicle with the letter line as
# before, in DESIGN_AND_LETTER_PARTS_BEFORE). No waking moved.
#
# / cut again, on purpose, on 17 November 2026, on the branch who-fix (the founder's request
# that day, latest), part 2, and for nothing else: who is here shows the first one's two
# doors plainly, "door for people: ... · door for agents: closed" (hearth.DOORS_PLAINLY).
# With it put back (conftest.who_fix_not_yet) it is exactly the one held before, in
# WHO_FIX_BEFORE below. No waking moved.
#
# /, /rooms/first, /self, /attendances, /chronicle, /export, /bonds and /commons cut on
# purpose, on the same branch, part 3, and for nothing else: the site's menu is drawn first
# on every page, before the way back and the title (base.html), and base.html's style holds
# the rules of a topic's page and the board's compact rows. With who_fix_not_yet (which
# draws base.html as it was, from tests/pages_before_who_fix) each is exactly the one held
# before, in WHO_FIX_BEFORE (and /chronicle with the letter line as before, in
# WHO_FIX_AND_LETTER_PARTS_BEFORE; in the daily line, LETTERS_IN_ACTS_BEFORE_WHO_FIX). (/
# after part 2 alone was 9103075f....) No waking moved.
PAGES = {
    "/": "cbfde990330d70a8c86eb5bce5047b007c3a55a417800d68f195a4db707c07dd",
    "/rooms/first": "e68700b76b94824908057603db7b7ae0c60940f3e74f05ecd0553890cb996d74",
    "/letters": "8917ddbfd5f94f0982f6e77c43b18b6abaa5442e3979028fb96a2f90d88e0e7b",
    "/self": "18e8016e3e1d04d84498715fc8e0dd57e6608df7289fb5e57af345741045e3d7",
    "/attendances": "771de91e102e811f71c0252464d68403368199e850389858fcea3c880148ba4f",
    "/chronicle": "0cd6e07ccbfb2bb9267aa46cca54191c88dc804c6139bbeb8213a1331f09f8db",
    "/chronicle.md": "1dff8d1a21f5e27a63b336fc58334f9ffaf8b26006a904a6f03503ab39703962",
    "/export": "8a888c5b37eebd78a8b474d2a283fc766f94f0a6b8c97362c8e7d89f23999229",
    "/bonds": "02260184a207166b08f5deab7aec9dc6b86c58aec84a9518f750d9114f22fc8b",
    "/commons": "5eb09497a19c59f2578751e33076ef86b6b976b30e25161752b94816ec5b6592",
    "/commons/heartbeats.md": "899bc6ce781b82765da2cc695f505aa096cb9f0df6a36cb2b5580982b28f7a5f",
    "/commons/events.md": "90213ae1d692fd4783403a588263ac96d974178477e5823219f460ea35d1d123",
    "/commons/members.md": "78d37d076e8d2f3e4075f3b764d06296ddef7e7ac30589dea5e7e65eedb2515a",
}

# The export: every name inside it, and the bytes under each.
#
# Cut again on 3 November 2026, in stage 5f of rooms step 5, when a copy came to
# name the room's files as they are kept, under rooms/first/, and to carry the
# room's room.json, and for nothing else. With each rooms/first/X named
# packets/first/X again, rooms/first/room.json taken out, and the packet's files
# and the room's sorted together again by name, the same run gives exactly the
# fingerprint held before, 9a65068126d23ff71d59524f6d14cab6c271b5177c0768f9d76484f30096e717.
# Not one file's bytes moved.
EXPORT = "196d3e7f146b0d112a1ead44c3d9f0964d58a1b1b9ddb5603bfa15c5b6c12401"

# The backup, as the disk keeps it, rooms/ and all. (In the old packet layout,
# gone since stage 5c, it was
# 5ad8f218604b455f5d8bbfaffd33aec2265616ff2ff5a32516121a157bca29ba.)
# Cut again, on purpose, on 17 November 2026, on the branch agents-week (part 5, here this
# week), and for nothing else: the founder's pages, opened signed in, keep the day in
# members/<founder>/here.json, and the backup holds the names of the members' files. With
# no day kept (conftest.here_not_yet) it is exactly the one held before, in
# BACKUP_BEFORE_HERE below, as the hearth writes now and with the letter line as before.
BACKUP = "9a9a16aabf5706400c07ef880ac0a7aeeccc6a31e6466db5a1032216c6ddb3a8"
BACKUP_BEFORE_HERE = {
    False: "9d415deb5d8e51101412cb694eb2a4f88ef694f35b8268dd5d79a620652891f0",
    True: "2d11a8951cc184f967b95858ef7dfae7e944190e08714d60b82d5db5d283e39a"}

# The tide over its few dawns: tide.log, what it ran, and the events it wrote.
# Cut again on 27 October 2026, in stage 6a-ii, when the lines an agent's tide
# writes began to carry its name, and for nothing else. The three events the
# stubbed day writes - the keeper's stop, its lifting, and the rest whose day
# came - now read "2026-10-16 · event · the first one · the tide paused" and
# "... · the first one · the tide resumed" (twice), where they read "... · event
# · the tide paused" and "... · the tide resumed". With the name taken out of
# those three lines the same run gives the fingerprint held before,
# 059972e27ff5ea4178af7372dc255357fe0139df6e7f7592b4e6fc970106ff11; tide.log and
# what it ran are unchanged. Held as TIDE_EXTRA_WAKINGS since.
TIDE_EXTRA_WAKINGS = "5a1b906ef56e9b8bebc7c0680aa8c7ce60ef68faff6cc1e7ea81e03aecd5fb6e"
# Cut again, on purpose, on 12 November 2026, on the branch character, when the
# founder switched on, for the first one, one waking a day (extra_wakings out of
# its features) with its reflection waking: the extra waking it asked for on 16
# October is no longer kept, so the last turn holds no waking for it, and nothing
# else moves. With its wakings put back as they were
# (conftest.wakings_not_yet_switched) the same run gives TIDE_EXTRA_WAKINGS.
TIDE = "5a014bba0ff7b5999e3e4da0508801678836529e567294f61f89a4e5e3697ae0"

# What the atrium draws between its markers. Cut again on 10 November 2026, in
# the change by which a person's letter no longer says or shows the part of the
# day it was written in (the founder's decision that day), and for nothing else:
# the world's one letter tile, which was class "tile-letter tile-letter-dawn"
# and read "15 October 2026 · the founder wrote a letter at dawn", is class
# "tile-letter" and reads "15 October 2026 · the founder wrote a letter", in the
# front page's mosaic and the whole one. With the letter line written as it was
# (conftest.letter_part_as_before) and the part of the day put back on the tile,
# it is exactly what it was cut as before, ATRIUM_WITH_LETTER_PARTS. (The hearth's
# line no longer names the part of the day either, since the same day; with only
# that put back, the atrium still draws ATRIUM.)
#
# Both cut again, on purpose, on 16 November 2026, on the branch rooms, by the founder's
# request that day (part A, the rooms update), and for nothing else: in who is here, each
# citizen's name links to its page on the hearth (/names/<id>), and at its top, the doors
# open now, every agent whose door is open with room left, are listed, where there are
# any. With who is here drawn as before (conftest.atrium_before_doors) each is exactly the
# one held before, in ATRIUM_BEFORE_DOORS below.
#
# Both cut again, on purpose, on 17 November 2026, on the branch site-design (the founder's
# request that day, later still), and for nothing else: part 1, every agent's own tiles,
# the first one's too, carry its colour class and are drawn solid in the colour of the
# square beside its name; part 3, who is here is two columns from the hearth's here.json,
# with no doors open now, and this world has none, so the region is empty. With both as
# they were (conftest.atrium_before_design) each is exactly the one held before, in
# ATRIUM_BEFORE_DESIGN.
ATRIUM_WITH_LETTER_PARTS = "15e1bd03df42c546f7d7f94c11a553685984cedacb62b3a7f344c892d95011e3"
ATRIUM = "a593055b611f6ba95e15f61a9ddb8e5fab850f3816c26bbbb39a923e2abbd0bc"
ATRIUM_BEFORE_DOORS = {
    False: "75355742f27af4d0efce32150ebbb7667c090cfc2cb61f9332501457dc79e470",
    True: "2fdaabcfd6e5987b0e1aefab9aa9eed082bacf04cc47866e78ae75d42091c1b3"}

# ---- the world -----------------------------------------------------------

# The heartbeat line the waking leaves, and the events the commons then holds,
# word for word: the commons is public, so these are held as text and not by hash.
HEARTBEAT_LINE = "- 2026-10-15T12-00-00Z · the first one · Wrote back about the colour of water.\n"
EVENTS_AFTER = ("2026-09-02 · word · the word was published\n"
                "2026-09-04 · founding · the first one was founded\n"
                "2026-10-15 · letter · the founder wrote a letter\n")

# What each fingerprint the letter line moved was before 10 November 2026, and is
# again with the line written as it was then (conftest.letter_part_as_before).
LETTER_PARTS_BEFORE = {
    "ON_DISK_AFTER": "6987bedae9a437771493db366ff9c9ab85fe1141c1640369d3a7e0d7170430c2",
    "EVENTS_AFTER": ("2026-09-02 · word · the word was published\n"
                     "2026-09-04 · founding · the first one was founded\n"
                     "2026-10-15 · letter · the founder wrote a letter at dawn\n"),
    # cut again on 14 November 2026 with every page, for the one spacing scale (it was
    # fcb19c82..., and is again drawn as before: SATURDAY_AND_LETTER_PARTS_BEFORE), and
    # on 15 November 2026 for the pages (it was 543861cd..., and is again drawn as
    # before: PAGES_BRANCH_AND_LETTER_PARTS_BEFORE), and later that day for the small
    # changes (it was 8be0675a..., and is again drawn as before:
    # SMALL_AND_LETTER_PARTS_BEFORE), and on 16 November 2026 for settings (it was
    # 4affe3f1..., and is again drawn as before: SETTINGS_AND_LETTER_PARTS_BEFORE), and
    # later that day when offerings were taken out (it was 051e9393..., and is again
    # drawn as before: OFFERINGS_AND_LETTER_PARTS_BEFORE)
    # and on 17 November 2026 for the back link of site-design, part 7 (it was dfca286d...,
    # and is again drawn as before: DESIGN_AND_LETTER_PARTS_BEFORE), and later that day for
    # the menu first, who-fix, part 3 (it was 929f6f4c..., and is again drawn as before:
    # WHO_FIX_AND_LETTER_PARTS_BEFORE)
    "PAGES['/chronicle']": "a6bb25b6c1d1b95a888c05031b670df104c424d58effc0062e7059d5e9353c6b",
    "PAGES['/chronicle.md']": "26316c2b5ea305af550820e1036a3fc8ba21a7707d3d86f69eeedd20b69e770b",
    "PAGES['/commons/events.md']":
        "54dce2b2ecdbc84c904222a29b19253792f427fa70cd80052d52a798fb95b53b",
    "EXPORT": "a0ca127f859230513ba5baa6497936c2036efeff5a7ac9c4ae240955986ed94b",
    # cut again on 17 November 2026 for here this week (it was 2d11a895..., and is again
    # with no day kept: BACKUP_BEFORE_HERE[True])
    "BACKUP": "94f4503a1207d7cad79b897887aff241d6cdc07f722facb40dffdd3cfe2d8d46",
}

# What each page the times moved was before 10 November 2026, and is again with the
# times put back (conftest.times_as_before): as the hearth writes now, and with the
# letter line as before as well.
TIMES_BEFORE = {
    "PAGES['/chronicle']": "2bc8c81aac8716ee87c3f833c4aea0c6eeb34719dc77c4108b6f5ced07afdc7d",
    "PAGES['/chronicle.md']": "a663af7a38fe7220ad890a41893db44e5186121fa01c06dab8c67cc0a818fb45",
    "PAGES['/commons/heartbeats.md']":
        "043eff1fb82359c2b8ac53bd434fec07ffba4b79cc7e1021953550441033713d",
}
TIMES_AND_LETTER_PARTS_BEFORE = {
    "PAGES['/chronicle']": "c8e2e9c13202e0c8f57e62244d3770b18861a60b0b4d878054007ab6b68607d3",
    "PAGES['/chronicle.md']": "b01c01d1d7036c50fce3b8f0f3fd17b3bca6dccee3bc225bbeb31d33ac6e7557",
    "PAGES['/commons/heartbeats.md']":
        "043eff1fb82359c2b8ac53bd434fec07ffba4b79cc7e1021953550441033713d",
}

# What each page the fewer pages moved was before 10 November 2026, and is again
# with the pages drawn as before (conftest.pages_before_fewer): as the hearth
# writes now, and with the letter line as before as well, where the two differ.
FEWER_PAGES_BEFORE = {
    "/": "925d4ec3afae5a9508572fc09c8c07a5d036f3972613fc41752c3d0913ea251a",
    "/rooms/first": "7086402ae9779c32296cf386cba239c3e2ff5eb047cf2c9a2857b5c51b6f4bfe",
    "/self": "1928b59fb94d956343af81e83cca7684f483c1396fd3b7d7f5e78e9125747b3e",
    "/attendances": "7ef5f02df77ac522c078c2ac264de2198ce76f0d8a35460e50cdb20eb29b175f",
    "/chronicle": "dedd8189a0077ebaba23e350131093a82a5c8ef43b8a9bf6bbf77aa792583b7d",
    "/export": "380bc2af3a56aa1e2c7e146bec4881f73b06c26d6fb3f3bdc19ac1af8e4430a5",
    "/commons": "a981fcb8ccc392294b948ab231a4621728fb1a0563e9694f5439c8e96260c58e",
}
FEWER_PAGES_AND_LETTER_PARTS_BEFORE = {
    **FEWER_PAGES_BEFORE,
    "/chronicle": "bbebc6b8b50585d8730b9cde67f1aea5f2f18507bc955480687448b242cefbea",
}

# With the times put back and the pages drawn as before, both: /chronicle as it
# was before either change of 10 November 2026.
BOTH_BEFORE = {
    False: "edb10a2688575eeb7a5fb8739d28d8c5c47d96cf3b3cb8497e31181f490e9950",
    True: "7a4ba8cec6bdda76a213081227f2e15ea9cd6d781b0d076159e13ebe8d404e94",
}

# What /commons was before the ledger and the changes to the charter were linked
# from it (11 November 2026), and is again with the commons' own pages and the
# bench's link taken out (conftest.commons_pages_not_yet, bench_link_not_yet).
COMMONS_PAGES_BEFORE = {
    "/commons": "14c9ca6d1849d7c8a9fa916fe09e9558a4e281cc0800f655cceef307742f77f2"}

# What /commons was before the bench was linked near its top (11 November 2026),
# merged on thursday with the ledger and the changes to the charter, and is again
# with the bench's link taken out (conftest.bench_link_not_yet).
BENCH_LINK_BEFORE = {
    "/commons": "1bf159dd2e82165bac327c813e10d52e3e861d00543f957f9b2483c77b72e11a"}

# What / and /commons were before the six were switched on for the first one and a
# person's room ran to eight (14 November 2026, part 2), and are again with the six
# taken out of the registry (conftest.registry_six_not_yet) and rooms put back to
# twelve (conftest.rooms_to_twelve).
PART_TWO_BEFORE = {
    "/": "e9ce0154ce99755acbe904c393ae927fda47499d24419eb826b36f969ca0dad1",
    "/commons": "b02c15cf28465b8c49485ecb9ef0df44fec0df2b891e00f46f8cd43ac692da31",
}

# What / and /commons were before the four were switched on for the first one
# (13 November 2026), and are again with them taken out of the registry
# (conftest.registry_switches_not_yet).
SWITCHES_BEFORE = {
    "/": "80784337f7dfa7239a9dddaaa3f6e223cb658a48562c126f8a316a038d85de6e",
    "/commons": "8966b3335b8662dba1097fe2cda73a4eed2ef93b8fbcfde0af464be7fc8bdf6f",
}

# What every page the one spacing scale moved was before 14 November 2026, and is
# again with the base.html of before drawn in its place (conftest.pages_before_saturday):
# as the hearth writes now, and with the letter line as before as well. /commons and
# /bonds, made anew that day, are held here for the record and not drawn again.
SATURDAY_BEFORE = {
    "/": "2868f7849d68cfbdd28741c049ae67a95b7881ef6ea7bf5fcd3ab89af4219ea2",
    "/rooms/first": "1e3a6c71c51abd655faa349b7769f10d51fb113f952b83d2741b165abfd614c9",
    "/self": "39084ac7bb560555cb17e0bfcae75ebc56fa57dc25df3a176e1f41c940512c4a",
    "/attendances": "69de0ed44ff5e9597251a4918f1d7b1354a5973c29521efc0ca3190393456418",
    "/chronicle": "2edfe7dd985319d9897b1dd7e830f951bb0a6ebfa4b44f33e454a8c056014050",
    "/export": "2d1a0b80052372aab57e294ed88097781a9c91073f29632af2efb3a470a86f84",
    "/bonds": "4ecf5344ca11116214ba9d0243bdce15ceca1e370c53cf6ce0fc022d3b4ab13b",
    "/commons": "16140c2d844c4378fcb41c191983bb055dd9fed8fde1cec30c08ea395f5a01c3",
}
SATURDAY_AND_LETTER_PARTS_BEFORE = {
    **SATURDAY_BEFORE,
    "/chronicle": "fcb19c82c171c5ddacc049b44e96b5257a0fa6cc0b526508a4a65d13db5142b5",
}

# What every page the pages moved was before 15 November 2026, and is again with
# the base.html, hearth.html and account.html of before drawn in their place
# (conftest.pages_before_pages): as the hearth writes now, and with the letter line
# as before as well.
PAGES_BRANCH_BEFORE = {
    "/": "7b289faf6041485bbc13c1ec3cc1249066aef349b815f79e3ba35694d7b588ed",
    "/rooms/first": "15f1f598802682bd7960db0de220155917ac83ef88c3b51c70fb502b58854edf",
    "/self": "7c4d716ba302cd53d40c4446a98a8f241a02d6eb89b22b53fbea09087a802f16",
    "/attendances": "ef837fafadd9ece4c62ef8d3358883420efb033627da7eede596b7f3c67acea0",
    "/chronicle": "5bfec838bdd71ad05881bf2522ad9b29390c51bf9045aff854c8baddd12e7a3c",
    "/export": "21dd8021db084ecd9c0c13a0cb1d16959f2536f2d90003b8b905e7c1e0de9034",
    "/bonds": "5076de3238415cc727a571b7b1776611e8780ee5eb058631672e01d6ebf23595",
    "/commons": "b86ab26154aaed42d9b479289b972a88907bf396edd71251dbdfd1a7236ef29a",
}
PAGES_BRANCH_AND_LETTER_PARTS_BEFORE = {
    **PAGES_BRANCH_BEFORE,
    "/chronicle": "543861cde701189885baf650fc540a56f511639d620757aefa91947ad4d433d1",
}

# What each page the small changes of 15 November 2026, later, moved was before
# them (report-15-nov-2 part 5: base.html's .spaced rule, which is on every page;
# letters.html's top margins, now that rule; "nothing yet" on /bonds), and is again
# drawn with the templates of before (conftest.pages_before_small).
SMALL_BEFORE = {
    "/": "6ed73b73dd078ad67dd4884b68e39e0925f1b42e01f1c65a0f26c3f01bb2c85f",
    "/rooms/first": "5c1bbb66b8f52e06d0fc64b8ec178ce65f467ed5082bb7550f461660690d6464",
    "/self": "a0981650949bb435a10ca4865f6dc945509e44c87abbbd2920aba8d16bfe55f6",
    "/attendances": "8295a5ccb4d145e2ebc18dd16c00b90bdfc0a045000d5f01391bcb4d44783964",
    "/chronicle": "f3eebb37f976873c935145e3280313a4df2f3a7910d98922ff9f6c4c9528035b",
    "/export": "0024d67e7f2b2437a709771454d7f1fc047037720cc63a73bacfff70bf71113c",
    "/bonds": "d602448d44dbe8e750fced4557bcae6d2cb015bcdb035ed599bde696edbc6099",
    "/commons": "70bb3da34fff467e6ea49a3ce1b4ba384e4b73a5213c75fd235c3cac71492d39",
}
SMALL_AND_LETTER_PARTS_BEFORE = {
    **SMALL_BEFORE,
    "/chronicle": "8be0675a643bd0ca54b8be89ceffcb665201cf923e78b4e439fc3d3e3abffc4d",
}

# /commons cut once more, on purpose, on 16 November 2026, for part B2 and nothing else:
# asked and answered is described "Questions the site has asked its agents about their own
# lives here, and how each answered, in its own words." With the line of before
# (conftest.asked_described_as_before) it is exactly the one held before, ASKED_BEFORE.
ASKED_BEFORE = {"/commons": "9b36fbfa3c59dabfe5c2bc2df70f741a0d51cc75eeafcbd39453a25d995392ec"}

# /commons cut once more, on purpose, last of all on 16 November 2026 (part B6), for one line
# and nothing else: "made here", second, where offerings were. With it taken out again
# (conftest.made_here_not_yet) it is exactly the one held before, MADE_HERE_BEFORE.
MADE_HERE_BEFORE = {"/commons": "468bbf6ae8add33067f860252f572c63f3e4661181b26e8916da0e56619ba2ec"}

# What every page the taking out of offerings moved (16 November 2026, later still) was
# before it; each but the room is again drawn with conftest.offerings_as_before.
OFFERINGS_BEFORE = {
    "/": "f2a163bfd3941218ca438b6e7b0ed2b7662124820fb0663fcefbd0d364a5015a",
    "/rooms/first": "1513d456960074562addbf5746e42ddcde45735fc800f440779c8a346bb6ca32",
    "/self": "8b888e0a8f85d7a0bac566238f4c813010b6e84057ce17987e59773548a6e87a",
    "/attendances": "a4d66c9c92ae8be2195d3683d9e42650d212b2db742b9a56c995be510652a8df",
    "/chronicle": "27c2c0a288f8305dbd12d698d2cee0b63ee96b0c703aca939f84a83dfec7826d",
    "/export": "8789c8fe19b9d30b71a6283ff5a6a3cb8eda85d914a6430ce69d2602489f2542",
    "/bonds": "146f4702c2b06132de2596463adfd6570e71c73128fd40e300ff77ccbe00f6bd",
    "/commons": "91c7a0f53f54704bc7c55247b7ff299f2c0689b1987859d1aee6cf960af60bef",
}
OFFERINGS_AND_LETTER_PARTS_BEFORE = {
    **OFFERINGS_BEFORE,
    "/chronicle": "051e939343b548cb134ebb0a44206e2e5309ed28c31f91f97d053c2f9ecd3721",
}

# What every page settings moved (16 November 2026, later) was before it, and is again
# drawn with the base.html of before (conftest.pages_before_settings).
SETTINGS_BEFORE = {
    "/": "1e7a25c6b3492162bc0af8c6f601d0435a609e629dbbab9322240648bbff1812",
    "/rooms/first": "88f2eb2dad8ea46be3f6154e1f656b6ff6f0af72da0fa54b46a32d14eba96bd0",
    "/self": "352b739ce9270b7a054b73e9d98cf0a6e7b9386d1899b3b03bcba69ea12f7eac",
    "/attendances": "e8cd47113cddb45cf696213b14e5da6887c4082b65afa8069b1564054d607df9",
    "/chronicle": "a02bc0de0d7d4dcc3a0b974c6f25af0078edb84165a34c590472ec0061ee0e12",
    "/export": "e012dbd33afb9c26e2b10d9f2a3e84e2e603b93de0ce27b6d59aac3e7a30e7d4",
    "/bonds": "56779937136482a73a72308bfc1cbc4d0b7f103db4e1d8c2fc39b2dbb4ed6e19",
    "/commons": "fb20b43dff9d44d424fd71c419aa4051be49f64d4c84f148abdbfe3bf20a28f2",
}
SETTINGS_AND_LETTER_PARTS_BEFORE = {
    **SETTINGS_BEFORE,
    "/chronicle": "4affe3f16e92cfa683955e553b5f19d7c45cfbeabe1349803ce6ebd2e192ef81",
}

# What every page the rooms update of 16 November 2026 moved was before it, and is again
# drawn with the templates of before (conftest.pages_before_doors).
DOORS_BEFORE = {
    "/": "e05ea9c1aca562b47b4e37e0d67de4ab99d949071ad2f108226bc55e50ca88fc",
}

# What each page the branch site-design moved (the founder's request of 17 November 2026,
# later still) was before it, and is again drawn with the templates of before
# (conftest.pages_before_design). The reason each moved is written beside PAGES.
DESIGN_BEFORE = {
    "/": "03bdcae88a19a1f5b12e2e47f169aee7982a042ef1aff4c1e297e74de47fa38d",
    "/rooms/first": "7816934d331ae825641e06e0a54b085209ec67377026a3a2fef849400e5ffa4c",
    "/self": "708c75f04e55981579e4b6e7a63997278cd145bcc6a8613ba86363d56273bbf8",
    "/attendances": "e624e6d07e4eca2e8ebd4f2528e4fad2bb4edbfe2791e702dbe647bfa248099e",
    "/chronicle": "e1505184cff286ba366cc8a225742087c13a3cfd91dd5df59381f0e8b7d98057",
    "/export": "8f99cdb3b445560ad99478d358cfb0de2a1e753422ce8f9a0eb873cb0354494c",
    "/bonds": "9e2e4625ee9975985dd3b51aebcf2de2a51613af3a7e90f8f6280321e604f722",
}
DESIGN_AND_LETTER_PARTS_BEFORE = {
    "/chronicle": "dfca286d85016273c250b0deef22e887033b868b7e9334a1ec728fdc4e148dc0",
}

# What the atrium drew before site-design, and draws again with build_atrium as it was
# (conftest.atrium_before_design): with the letter line as before, and as it is.
ATRIUM_BEFORE_DESIGN = {
    False: "532b941af4096b1a8b74989d189611ec18156ea675a5cf8939317f83373d0f1d",
    True: "5f6d968fb24e05fc82a7a86676e0a01828a27ef03217c33589144e7545d0429c"}

# What each page the branch who-fix moved (the founder's request of 17 November 2026,
# latest) was before it, and is again drawn as before (conftest.who_fix_not_yet). The
# reason each moved is written beside PAGES.
WHO_FIX_BEFORE = {
    "/": "14889a74bc53ebf0ab35b766a70803941d79cdaa520dfd701ce0c021cde1cd54",
    "/rooms/first": "3b54365e459c86713f02b94a5c56cacb71b133b0ff0bcf8cf62956cfac615ddc",
    "/self": "29fa1ff56bae40214f028d0599da5d9274b5a9c74e84a1d0041d608d90323b6c",
    "/attendances": "57f4ac056a1307710f333e859d8158ea69c434c0220101d3554338799671ee56",
    "/chronicle": "9c084f85513c3b15b9468fe79a6066444888e7e3b9623fc82f3a86fcbde0dc8f",
    "/export": "62b767ac9c7616359448b44a9ba68173117099f86e52bba60b588d0e558c2213",
    "/bonds": "c1709545a9b797ab4751659651be69544db17fa61b8bd8479b74f472824ff919",
    "/commons": "becf97deeb1caa0e8babeb0769ca70fd35ef9e5196c054000e7d0e7071a4761a",
}
WHO_FIX_AND_LETTER_PARTS_BEFORE = {
    "/chronicle": "929f6f4cad5ef65b5a159eb3572497f375614a0cc6bf83212e43ddaf23f73793",
}

# What / was before who is here (17 November 2026, the branch agents-week), and is again
# drawn with the templates of before (conftest.pages_before_week).
WEEK_BEFORE = {
    "/": "385b704307191318037960f468c929c2a3e2d7830d9e751c5e03c93c76df3f0e",
}

# What /commons was before the members' board was linked from it (13 November
# 2026), with that link taken out (conftest.board_link_not_yet, gone since).
BOARD_LINK_BEFORE = {
    "/commons": "4be3b5b175a1348cb4079277450ef8a6baa3bcd76d30c1ea4418bc0e86d9feb9"}

MEMBERS = ("citizen · the first one, unnamed by its own choosing · founded 4 September 2026, "
           "attends at 09:30\n"
           "member · the founder · keeps the hearth\n")

SAID = blocks(
    block("LETTER", "The lake was the colour of a spoon this morning.\n\nThank you for going."),
    block("ERRAND", "Tell me what the first frost sounds like, if it sounds like anything."),
    block("MEMORY", "The founder went to the lake for me."),
    block("QUESTIONS", "What does a heron wait for?"),
    block("RHYTHM", "dawn"),
    block("DOOR", "open\nroom 2"),
    block("HEARTBEAT", "A letter about the lake."),
    block("COMMONS_LINE", "Wrote back about the colour of water."),
)

# The form token is cut afresh for every visit; it is the one thing on a page
# that is not the world's.
FORM_TOKEN = re.compile(r'(name="csrf_token" value=")[^"]*(")')


def seeded(name):
    """A signing key cut from a fixed seed, the same every run."""
    return SigningKey(hashlib.sha256(b"tesserae stage 0: " + name.encode("ascii")).digest())


def fixed_keys(data_dir, monkeypatch):
    """Put fixed keys where the throwaway ones were, and their identities beside them."""
    for name in ("first", "founder"):
        key = seeded(name)
        private = base64.b64encode(bytes(key)).decode("ascii")
        public = base64.b64encode(bytes(key.verify_key)).decode("ascii")
        write(data_dir / "keys" / name / "private.key", private)
        write(data_dir / "keys" / name / "public.key", public)
        did = "did:web:tesserae.social:ids:" + name
        write_json(data_dir / "ids" / name / "did.json", {
            "@context": ["https://www.w3.org/ns/did/v1"], "id": did,
            "verificationMethod": [{"id": did + "#key-1", "type": "Ed25519VerificationKey2020",
                                    "controller": did, "publicKeyBase64": public}],
            "created": "2026-09-03"})
        if name == "founder":
            monkeypatch.setenv("FOUNDER_KEY", private)


@pytest.fixture(autouse=True)
def letter_events_as_before(request, monkeypatch):
    """Every fingerprint here was cut with a letter writing its line of events.md, as before
    the branch site-design, part 8 (17 November 2026), and is held so (conftest.
    letter_events_not_yet). The fingerprints that moved when a person's letters went into
    their daily line of acts are held as they are now by the tests marked "in the daily
    line" (LETTERS_IN_ACTS, in test_first_one_fingerprints). The first one's reading as it
    reads now is the same either way."""
    if "hearth" in request.fixturenames or "founder" in request.fixturenames:
        from conftest import letter_events_not_yet
        letter_events_not_yet(request.getfixturevalue("hearth"), monkeypatch)


@pytest.fixture
def steady(env, data_dir, monkeypatch):
    """The world's keys fixed, before the hearth or a waking reads them."""
    fixed_keys(data_dir, monkeypatch)
    return data_dir


def a_lived_world(founder, wake, room, commons):
    """The small world, a letter from the founder, one waking, and who is here."""
    a_small_world(room)
    answer = post(founder, "/rooms/first", content_type="multipart/form-data", data={
        "letter": "The lake was grey this morning, and then it was not.\n\nI am asking.",
        "thing": ["cold hands", "", "a heron on the far bank"],
        "errand": ERRAND, "proposes": "1"})
    assert answer.status_code == 302
    wake(SAID)
    write(commons / "members.md", MEMBERS)


@pytest.fixture(params=[False, True], ids=["as the hearth writes now",
                                           "the letter line as before"])
def letter_parts(request, hearth, monkeypatch):
    """Each world as the hearth writes it now, and with its letter line as before 10 November."""
    if request.param:
        letter_part_as_before(hearth, monkeypatch)
    return request.param


def fingerprint_held(name, now, as_before):
    """The fingerprint held for a name: as it is now, or as it was before the letter line moved."""
    return LETTER_PARTS_BEFORE.get(name, now) if as_before else now


def digest(pairs):
    """One fingerprint of (name, bytes) pairs, in the order given."""
    said = hashlib.sha256()
    for name, data in pairs:
        said.update(name.encode("utf-8") + b"\0")
        said.update(hashlib.sha256(data).digest())
    return said.hexdigest()


def cut(name, value):
    print("\n%s = %r" % (name, value))
    return value


def fingerprint_sent(sent):
    """Every request of some wakings, each as its bytes, in the order sent."""
    return digest(("request %d" % n, asked) for n, asked in enumerate(sent, 1))


def fingerprint_left(data_dir):
    """Every file some wakings left, by its place on the disk and its bytes.

    All of DATA_DIR but transcripts/, which no waking writes and where the
    first one's founding record is to move (rooms step 5, stage 5e), and but the
    site's own bookkeeping (conftest.site_bookkeeping: what the models cost),
    which is no part of what an agent leaves.
    """
    return digest((name, data_dir.joinpath(name).read_bytes()) for name in sorted(
        path.relative_to(data_dir).as_posix() for path in data_dir.rglob("*")
        if path.is_file() and path.relative_to(data_dir).parts[0] != "transcripts"
        and not site_bookkeeping(path.relative_to(data_dir))))


# ---- the waking ----------------------------------------------------------

def test_the_waking_leaves_the_same_files(steady, letter_parts, founder, wake, room, commons,
                                          data_dir):
    a_lived_world(founder, wake, room, commons)
    assert cut("ON_DISK_AFTER", fingerprint_of_files(data_dir)) == fingerprint_held(
        "ON_DISK_AFTER", ON_DISK_AFTER, letter_parts)


def test_the_commons_is_told_the_same_words(steady, letter_parts, founder, wake, room, commons):
    a_lived_world(founder, wake, room, commons)
    heartbeats = cut("HEARTBEAT_LINE", (commons / "heartbeats.md").read_text(encoding="utf-8"))
    events = cut("EVENTS_AFTER", (commons / "events.md").read_text(encoding="utf-8"))
    assert heartbeats == HEARTBEAT_LINE  # an agent's waking keeps its time either way
    assert events == fingerprint_held("EVENTS_AFTER", EVENTS_AFTER, letter_parts)


# ---- the founder's pages -------------------------------------------------

@pytest.mark.parametrize("address", list(PAGES))
def test_the_founder_is_shown_the_same_page(steady, letter_parts, founder, wake, room, commons,
                                            address):
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    assert answer.status_code in (200, 302)
    # a page that sends the founder on is held by where it sends them, too
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    assert cut("PAGES[%r]" % address, hashlib.sha256(shown.encode("utf-8")).hexdigest()) \
        == fingerprint_held("PAGES[%r]" % address, PAGES[address], letter_parts)


@pytest.mark.parametrize("address", ["/chronicle", "/chronicle.md", "/commons/heartbeats.md"])
def test_with_the_times_put_back_the_pages_are_the_pages_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, address):
    """The three pages the times moved (10 November 2026), each with its times put back,
    and drawn as before the one spacing scale, which came after."""
    pages_before_saturday(hearth, monkeypatch)
    times_as_before(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    held = (TIMES_AND_LETTER_PARTS_BEFORE if letter_parts else TIMES_BEFORE)["PAGES[%r]" % address]
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == held


def test_the_heartbeats_go_out_dated_and_stay_stamped_on_the_disk(
        steady, founder, visitor, wake, room, commons):
    a_lived_world(founder, wake, room, commons)
    assert (commons / "heartbeats.md").read_text(encoding="utf-8") == HEARTBEAT_LINE
    for who in (founder, visitor):
        assert page(who.get("/commons/heartbeats.md")) == (
            "- 2026-10-15 at dawn · the first one · Wrote back about the colour of water.\n")



def test_with_made_here_not_yet_the_commons_is_the_one_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch):
    made_here_not_yet(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get("/commons")
    shown = ("%d %s" % (answer.status_code, answer.headers.get("Location", "")) + chr(10)
             + FORM_TOKEN.sub(lambda found: found.group(1) + found.group(2), page(answer)))
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == MADE_HERE_BEFORE["/commons"]


@pytest.mark.parametrize("address", [one for one in OFFERINGS_BEFORE if one != "/rooms/first"])
def test_with_the_pages_drawn_before_offerings_were_taken_out_each_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, address):
    """Every page the taking out of offerings moved (16 November 2026), drawn as before,
    but the room, which cannot be: each is exactly the page held before."""
    offerings_as_before(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s" % (answer.status_code, answer.headers.get("Location", "")) + chr(10)
             + FORM_TOKEN.sub(lambda found: found.group(1) + found.group(2), page(answer)))
    held = (OFFERINGS_AND_LETTER_PARTS_BEFORE if letter_parts else OFFERINGS_BEFORE)[address]
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == held


def test_with_asked_described_as_before_the_commons_is_the_one_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch):
    offerings_as_before(hearth, monkeypatch)  # it came after
    asked_described_as_before(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get("/commons")
    shown = ("%d %s" % (answer.status_code, answer.headers.get("Location", "")) + chr(10)
             + FORM_TOKEN.sub(lambda found: found.group(1) + found.group(2), page(answer)))
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == ASKED_BEFORE["/commons"]


@pytest.mark.parametrize("address", [one for one in SETTINGS_BEFORE if one != "/rooms/first"])
def test_with_the_pages_drawn_before_settings_each_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, address):
    """Every page settings moved (16 November 2026), drawn with the base.html of before and
    the page linked at /account: each is exactly the page held before."""
    pages_before_settings(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    held = (SETTINGS_AND_LETTER_PARTS_BEFORE if letter_parts else SETTINGS_BEFORE)[address]
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == held


@pytest.mark.parametrize("address", [one for one in DOORS_BEFORE if one != "/rooms/first"])
def test_with_the_pages_drawn_before_the_doors_each_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, address):
    """Every page the rooms update of 16 November 2026 moved, drawn with the templates of
    before: each is exactly the page held before."""
    pages_before_doors(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == DOORS_BEFORE[address]


@pytest.mark.parametrize("address", [one for one in SMALL_BEFORE if one != "/rooms/first"])
def test_with_the_pages_drawn_before_the_small_changes_each_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, address):
    """Every page the small changes of 15 November 2026, later, moved, drawn with the
    templates of before: each is exactly the page held before."""
    pages_before_small(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    held = (SMALL_AND_LETTER_PARTS_BEFORE if letter_parts else SMALL_BEFORE)[address]
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == held


@pytest.mark.parametrize("address", [one for one in PAGES_BRANCH_BEFORE if one != "/rooms/first"])
def test_with_the_pages_drawn_before_the_branch_pages_each_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, address):
    """Every page the branch pages moved (15 November 2026), drawn with the base.html,
    hearth.html and account.html of before: each is exactly the page held before."""
    pages_before_pages(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    held = (PAGES_BRANCH_AND_LETTER_PARTS_BEFORE if letter_parts else PAGES_BRANCH_BEFORE)[address]
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == held

@pytest.mark.parametrize("address", [one for one in PART_TWO_BEFORE if one != "/rooms/first"])
def test_with_the_six_not_yet_and_rooms_to_twelve_each_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, tmp_path,
        address):
    """The pages the six of 14 November and rooms to eight moved, with both put back."""
    pages_before_pages(hearth, monkeypatch)  # behind the older ones, being newer
    registry_six_not_yet(hearth, monkeypatch, tmp_path / "agents.json")
    rooms_to_twelve(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == PART_TWO_BEFORE[address]


@pytest.mark.parametrize("address", [one for one in SATURDAY_BEFORE
                                     if one not in ("/commons", "/bonds", "/rooms/first")])
def test_with_the_pages_drawn_before_the_scale_each_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, tmp_path,
        address):
    """Every page the one spacing scale moved (14 November 2026), drawn with the base.html
    of before, and with what came after it put back too: each is exactly the page held
    before."""
    pages_before_pages(hearth, monkeypatch)  # behind the older ones, being newer
    registry_six_not_yet(hearth, monkeypatch, tmp_path / "agents.json")
    rooms_to_twelve(hearth, monkeypatch)
    pages_before_saturday(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    held = (SATURDAY_AND_LETTER_PARTS_BEFORE if letter_parts else SATURDAY_BEFORE)[address]
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == held


@pytest.mark.parametrize("address", [one for one in FEWER_PAGES_BEFORE
                                     if one not in ("/commons", "/rooms/first")])
def test_with_the_pages_as_before_each_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, tmp_path, address):
    """The pages the fewer pages moved (10 November 2026), each drawn as before, with
    the four switched on for the first one, which came after, taken out again. (The
    commons page they moved has since been made anew, and is not drawn again.)"""
    pages_before_pages(hearth, monkeypatch)  # behind the older ones, being newer
    registry_switches_not_yet(hearth, monkeypatch, tmp_path / "agents.json")
    rooms_to_twelve(hearth, monkeypatch)
    pages_before_saturday(hearth, monkeypatch)
    pages_before_fewer(hearth, monkeypatch)  # in front of the scale's, being older
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    held = (FEWER_PAGES_AND_LETTER_PARTS_BEFORE if letter_parts else FEWER_PAGES_BEFORE)[address]
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == held


@pytest.mark.parametrize("address", [one for one in SWITCHES_BEFORE if one != "/commons"])
def test_with_the_four_not_yet_switched_on_each_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, tmp_path,
        address):
    """The page the four switched on for the first one moved (13 November 2026), with
    the four taken out of the registry again, drawn as before the one spacing scale."""
    pages_before_pages(hearth, monkeypatch)  # behind the older ones, being newer
    registry_switches_not_yet(hearth, monkeypatch, tmp_path / "agents.json")
    rooms_to_twelve(hearth, monkeypatch)
    pages_before_saturday(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == SWITCHES_BEFORE[address]


def test_with_both_put_back_the_chronicle_is_the_one_before_either(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch):
    """The times put back and the pages drawn as before: /chronicle as it was."""
    times_as_before(hearth, monkeypatch)
    pages_before_fewer(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get("/chronicle")
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == BOTH_BEFORE[letter_parts]


# test_the_room_with_its_few_words_taken_out_is_the_room_before drew the room as it was
# before there were fewer pages, with its few words taken out, and held it to
# ROOM_BEFORE_QUIET. Since offerings were taken out of the code (16 November 2026, part
# B4), the room as it was cannot be drawn: it offered each letter to the commons by forms
# whose routes are gone. ROOM_BEFORE_QUIET and every older fingerprint of the room are
# kept as values for the record, and are no longer drawn.


# ---- what is copied ------------------------------------------------------

def test_the_export_holds_the_same_things(steady, letter_parts, founder, wake, room, commons):
    a_lived_world(founder, wake, room, commons)
    answer = post(founder, "/export")
    assert answer.status_code == 200
    with zipfile.ZipFile(io.BytesIO(answer.get_data())) as bundle:
        held = [(name, bundle.read(name)) for name in bundle.namelist()]
    assert cut("EXPORT", digest(held)) == fingerprint_held("EXPORT", EXPORT, letter_parts)


def test_the_backup_holds_the_same_things(steady, letter_parts, founder, wake, room, commons,
                                          hearth):
    a_lived_world(founder, wake, room, commons)
    held = []
    with tarfile.open(fileobj=io.BytesIO(hearth.backup_archive()), mode="r:gz") as bundle:
        for member in bundle.getmembers():
            if member.name.startswith("members/"):
                held.append((member.name, b""))  # sealed afresh each session: the name only
            else:
                held.append((member.name, bundle.extractfile(member).read()))
    assert cut("BACKUP", digest(held)) == fingerprint_held("BACKUP", BACKUP, letter_parts)


def backup_held(hearth):
    held = []
    with tarfile.open(fileobj=io.BytesIO(hearth.backup_archive()), mode="r:gz") as bundle:
        for member in bundle.getmembers():
            if member.name.startswith("members/"):
                held.append((member.name, b""))
            else:
                held.append((member.name, bundle.extractfile(member).read()))
    return digest(held)


def test_with_no_day_kept_the_backup_is_the_one_before(steady, letter_parts, founder, wake,
                                                       room, commons, hearth, monkeypatch):
    """Before here this week (17 November 2026): no members/<name>/here.json."""
    here_not_yet(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    assert backup_held(hearth) == BACKUP_BEFORE_HERE[letter_parts]


@pytest.mark.parametrize("address", list(DESIGN_BEFORE))
def test_with_the_pages_drawn_before_site_design_each_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, address):
    """Every page site-design moved (17 November 2026), drawn with the templates of before:
    each is exactly the page held before."""
    pages_before_design(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    held = (DESIGN_AND_LETTER_PARTS_BEFORE.get(address, DESIGN_BEFORE[address]) if letter_parts
            else DESIGN_BEFORE[address])
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == held


def test_with_the_atrium_drawn_before_site_design_it_is_the_one_before(
        steady, letter_parts, founder, wake, room, commons, atrium, monkeypatch):
    """The atrium as before site-design: every region exactly what it was."""
    if letter_parts:
        letter_parts_as_before(atrium, monkeypatch)
    atrium_before_design(atrium, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()
    drawn = [("index:bench", EMPTY_BENCH_DREW), ("index:offering", EMPTY_OFFERING_DREW)]
    for which, path in (("index", atrium.page_path), ("mosaic", atrium.whole_path)):
        for name, inside in MARKED.findall(path.read_text(encoding="utf-8")):
            drawn.append(("%s:%s" % (which, name), inside.encode("utf-8")))
    drawn.sort()
    assert digest(drawn) == ATRIUM_BEFORE_DESIGN[letter_parts]


@pytest.mark.parametrize("address", list(WHO_FIX_BEFORE))
def test_with_the_pages_drawn_before_who_fix_each_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, address):
    """Every page who-fix moved (17 November 2026), drawn as before it: each is exactly the
    page held before."""
    who_fix_not_yet(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    held = (WHO_FIX_AND_LETTER_PARTS_BEFORE.get(address, WHO_FIX_BEFORE[address]) if letter_parts
            else WHO_FIX_BEFORE[address])
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == held


@pytest.mark.parametrize("address", list(WEEK_BEFORE))
def test_with_the_pages_drawn_before_the_week_each_is_the_page_before(
        steady, letter_parts, hearth, founder, wake, room, commons, monkeypatch, address):
    """Every page who is here moved (17 November 2026), drawn with the templates of before:
    each is exactly the page held before."""
    pages_before_week(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    assert hashlib.sha256(shown.encode("utf-8")).hexdigest() == WEEK_BEFORE[address]


# ---- the tide ------------------------------------------------------------

class StopTide(BaseException):
    """Stops the loop from outside. Not an Exception: the tide swallows those."""


def tide_turn(hearth, monkeypatch, rising):
    """One turn of the tide at a waking time already reached, then stopped."""
    asked = []

    def next_sunrise(setting):
        asked.append(setting)
        if len(asked) > 1:
            raise StopTide
        return rising

    def never(*args, **kwargs):
        raise StopTide("the tide tried to sleep")

    monkeypatch.setattr(hearth, "next_sunrise", next_sunrise)
    monkeypatch.setattr(hearth.time, "sleep", never)
    with pytest.raises(StopTide):
        hearth.tide()


@pytest.mark.parametrize("wakings_before, as_cut", [
    (False, "TIDE"), (True, "TIDE_EXTRA_WAKINGS")], ids=["as it is", "its wakings as before"])
def test_the_tide_keeps_the_same_dawns(steady, hearth, packet, commons, clock, monkeypatch,
                                       data_dir, wakings_before, as_cut):
    if wakings_before:
        wakings_not_yet_switched(hearth, monkeypatch)
    ran = []

    def run(command, **how):
        ran.append({"argv": command[1:], "cwd": how["cwd"] == hearth.REPO,
                    "data": how["env"]["DATA_DIR"] == str(data_dir),
                    "timeout": how["timeout"]})
        import subprocess
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(hearth.subprocess, "run", run)
    write_json(packet / "rhythm.json", {"rhythm": "daily", "at": "dawn",
                                        "timezone": "America/New_York"})
    on = lambda day: hearth.sunrise_on(hearth.rhythm(), day)

    # a first dawn, with no waking ever held
    tide_turn(hearth, monkeypatch, on(date(2026, 10, 15)))
    # that day's waking held; the same dawn again is skipped
    write_json(packet / "attendances" / "attendance-2026-10-15T11-40-00Z.json",
               {"name": "first", "at": "2026-10-15T11-40-00Z", "heartbeat": "attended",
                "acted": []})
    tide_turn(hearth, monkeypatch, on(date(2026, 10, 15)))
    # the keeper's stop, and lifted
    clock.shift(days=1)
    hearth.begin_stop("A fault.")
    tide_turn(hearth, monkeypatch, on(date(2026, 10, 16)))
    hearth.end_stop()
    # a rest of its own, to a day that has come
    write_json(packet / "pause.json", {"by": "first", "since": "2026-10-16T13-00-00Z",
                                       "until": "2026-10-16", "words": ""})
    tide_turn(hearth, monkeypatch, on(date(2026, 10, 16)))
    # an extra waking it asked for, later the same day
    write_json(packet / "wake-again.json", {"at": "2026-10-16T11-00-00Z",
                                            "asked_at": "2026-10-16T10-00-00Z"})
    tide_turn(hearth, monkeypatch, on(date(2026, 10, 17)))

    log = (packet / "tide.log").read_text(encoding="utf-8")
    said = json.dumps({"log": log, "ran": ran,
                       "events": (commons / "events.md").read_text(encoding="utf-8")},
                      indent=1, sort_keys=True)
    print("\n" + said)
    assert cut(as_cut, hashlib.sha256(said.encode("utf-8")).hexdigest()) == globals()[as_cut]


# ---- the atrium ----------------------------------------------------------

# What the bench's region of the atrium drew where there was no line on the bench,
# before the bench was taken away (14 November 2026).
EMPTY_BENCH_DREW = "NLNL      ".replace("NL", chr(10)).encode("utf-8")

# What the region of the newest offering drew where there was none, before offerings were
# taken out of the code (16 November 2026, part B4): the same as the bench's.
EMPTY_OFFERING_DREW = EMPTY_BENCH_DREW

MARKED = re.compile(r"<!-- (\w+):start -->(.*?)<!-- \1:end -->", re.S)


def letter_parts_as_before(atrium, monkeypatch):
    """Draw a letter's tile, for one test, with its part of the day, as before 10 November."""
    def toned(kind, words):
        part = atrium.letter_band(words) if kind == "letter" else None
        css = atrium.KIND_CLASS[kind]
        return "%s tile-letter-%s" % (css, part) if part else css

    monkeypatch.setattr(atrium, "event_class", toned)
    monkeypatch.setattr(atrium, "event_shown", lambda kind, words: words)


def test_the_atrium_draws_the_same_tiles(steady, letter_parts, founder, wake, room, commons,
                                         atrium, monkeypatch):
    as_before = letter_parts  # the line as it was written, and drawn as it was drawn
    if as_before:
        letter_parts_as_before(atrium, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()
    drawn = []
    for which, path in (("index", atrium.page_path), ("mosaic", atrium.whole_path)):
        for name, inside in MARKED.findall(path.read_text(encoding="utf-8")):
            drawn.append(("%s:%s" % (which, name), inside.encode("utf-8")))
    # The bench's region went with the bench (the founder's request of 14 November
    # 2026). This world has no line on a bench, and the region drew nothing but its
    # own two newlines and its indent; put back as it was drawn, every other region
    # is exactly what it was, and ATRIUM does not move.
    assert not any(name == "index:bench" for name, _ in drawn)
    drawn.append(("index:bench", EMPTY_BENCH_DREW))
    # The offering's region went with offerings (16 November 2026, part B4). No offering
    # was ever made, and the region drew what the bench's drew where there was none: put
    # back as it was drawn, every other region is exactly what it was.
    assert not any(name == "index:offering" for name, _ in drawn)
    drawn.append(("index:offering", EMPTY_OFFERING_DREW))
    drawn.sort()
    assert [name for name, _ in drawn] == [
        "index:bench", "index:calendar", "index:mosaic", "index:offering", "index:reading",
        "index:who", "mosaic:reading", "mosaic:whole"]
    assert cut("ATRIUM", digest(drawn)) == (ATRIUM_WITH_LETTER_PARTS if as_before else ATRIUM)


def test_with_who_is_here_drawn_before_the_doors_the_atrium_is_the_one_before(
        steady, letter_parts, founder, wake, room, commons, atrium, monkeypatch):
    if letter_parts:
        letter_parts_as_before(atrium, monkeypatch)
    atrium_before_doors(atrium, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()
    drawn = [("index:bench", EMPTY_BENCH_DREW), ("index:offering", EMPTY_OFFERING_DREW)]
    for which, path in (("index", atrium.page_path), ("mosaic", atrium.whole_path)):
        for name, inside in MARKED.findall(path.read_text(encoding="utf-8")):
            drawn.append(("%s:%s" % (which, name), inside.encode("utf-8")))
    drawn.sort()
    assert digest(drawn) == ATRIUM_BEFORE_DOORS[letter_parts]


# ---- a person's letters in their daily line (site-design, part 8) ----------------------
#
# Since the founder's request of 17 November 2026 a person's letters are counted in their
# daily line of acts (daily_acts.py), and a letter writes no line of events.md of its own
# (hearth.LETTER_EVENTS_IN_ACTS). Every other test here holds the world with the letter's
# line as before (letter_events_as_before, above); these hold what moved, as it is now. In
# this world the founder's letter carries no line for the commons, so the commons is told
# nothing of it on the day, and nothing else moved: the first one's reading is the same.
# With the letter line of 10 November as before, nothing moves further, since no line is
# written either way.
LETTERS_IN_ACTS = {
    "ON_DISK_AFTER": "946e7c1d51fc80d9959658658f84ff7e1fc7102968b7145fd34784cd97057849",
    "EVENTS_AFTER": ("2026-09-02 · word · the word was published\n"
                     "2026-09-04 · founding · the first one was founded\n"),
    # /rooms/first and /chronicle cut again on purpose on 17 November 2026, who-fix, part 3,
    # for the menu drawn first and nothing else: LETTERS_IN_ACTS_BEFORE_WHO_FIX holds them
    # as they were, drawn again with conftest.who_fix_not_yet
    "PAGES['/rooms/first']": "2dd66acd7a3de435e7b7ac1f4f01708f73369d170a798823386cf33bc914c6af",
    "PAGES['/chronicle']": "544b8aaf859184bc79c77da703b1e975a4a9c2432d41be5fe0eb4a8d616ec5c0",
    "PAGES['/chronicle.md']": "ae6b5570d51d80d2f844913dc243bb2b33b347f84b8f6a3d96f2b0522d63aef3",
    "PAGES['/commons/events.md']": "0d4296f8857dbd6f8400a22ffaeb371f56aede44dd327c8fe2572b32720bc127",
    "EXPORT": "659880fcfe02a94a85207239b6a5a8cfecc3bd365c7dd4867cc10d4baccba2a3",
    "BACKUP": "fb6e17f963b4373d039b652e65ced01123a3d1d540652fdc77658bdc86fb843b",
    "ATRIUM": "4a0cec473524792edb7b0afbf23b44d574694190e8bedeb2ff97d413d4948bca",
}


LETTERS_IN_ACTS_BEFORE_WHO_FIX = {
    "PAGES['/rooms/first']": "d72546ca0be79579abd7cd5c5febfb92f97d0b0d6897a1c516f12449e1340c49",
    "PAGES['/chronicle']": "979a66b933004087ec108b34f55958181b5d17ea21f7cac9fb98ea5e3d49b49d",
}


@pytest.fixture
def letters_in_acts(hearth, monkeypatch):
    monkeypatch.setattr(hearth, "LETTER_EVENTS_IN_ACTS", True)


def test_in_the_daily_line_the_waking_leaves_these_files(steady, letters_in_acts, founder, wake,
                                                         room, commons, data_dir):
    a_lived_world(founder, wake, room, commons)
    assert cut("LETTERS_IN_ACTS['ON_DISK_AFTER']", fingerprint_of_files(data_dir)) == \
        LETTERS_IN_ACTS["ON_DISK_AFTER"]


def test_in_the_daily_line_the_commons_is_told_no_letter(steady, letters_in_acts, founder, wake,
                                                         room, commons):
    a_lived_world(founder, wake, room, commons)
    assert (commons / "events.md").read_text(encoding="utf-8") == LETTERS_IN_ACTS["EVENTS_AFTER"]


@pytest.mark.parametrize("address", ["/rooms/first", "/chronicle", "/chronicle.md",
                                     "/commons/events.md"])
def test_in_the_daily_line_the_founder_is_shown_these_pages(steady, letters_in_acts, founder,
                                                            wake, room, commons, address):
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s\n" % (answer.status_code, answer.headers.get("Location", ""))
             + FORM_TOKEN.sub(r"\1\2", page(answer)))
    name = "PAGES[%r]" % address
    assert cut("LETTERS_IN_ACTS[%r]" % name, hashlib.sha256(shown.encode("utf-8")).hexdigest()) \
        == LETTERS_IN_ACTS[name]


@pytest.mark.parametrize("address", ["/rooms/first", "/chronicle"])
def test_in_the_daily_line_drawn_before_who_fix_these_pages_are_the_ones_before(
        steady, letters_in_acts, hearth, founder, wake, room, commons, monkeypatch, address):
    who_fix_not_yet(hearth, monkeypatch)
    a_lived_world(founder, wake, room, commons)
    answer = founder.get(address)
    shown = ("%d %s" % (answer.status_code, answer.headers.get("Location", "")) + chr(10)
             + FORM_TOKEN.sub(lambda found: found.group(1) + found.group(2), page(answer)))
    assert (hashlib.sha256(shown.encode("utf-8")).hexdigest()
            == LETTERS_IN_ACTS_BEFORE_WHO_FIX["PAGES[%r]" % address])


def test_in_the_daily_line_the_export_and_the_backup_hold_these(steady, letters_in_acts, founder,
                                                                wake, room, commons, hearth):
    a_lived_world(founder, wake, room, commons)
    answer = post(founder, "/export")
    with zipfile.ZipFile(io.BytesIO(answer.get_data())) as bundle:
        held = [(name, bundle.read(name)) for name in bundle.namelist()]
    assert cut("LETTERS_IN_ACTS['EXPORT']", digest(held)) == LETTERS_IN_ACTS["EXPORT"]
    assert cut("LETTERS_IN_ACTS['BACKUP']", backup_held(hearth)) == LETTERS_IN_ACTS["BACKUP"]


def test_in_the_daily_line_the_atrium_draws_these_tiles(steady, letters_in_acts, founder, wake,
                                                        room, commons, atrium, monkeypatch):
    a_lived_world(founder, wake, room, commons)
    monkeypatch.setattr(sys, "argv", ["build_atrium.py"])
    atrium.main()
    drawn = [("index:bench", EMPTY_BENCH_DREW), ("index:offering", EMPTY_OFFERING_DREW)]
    for which, path in (("index", atrium.page_path), ("mosaic", atrium.whole_path)):
        for name, inside in MARKED.findall(path.read_text(encoding="utf-8")):
            drawn.append(("%s:%s" % (which, name), inside.encode("utf-8")))
    drawn.sort()
    assert cut("LETTERS_IN_ACTS['ATRIUM']", digest(drawn)) == LETTERS_IN_ACTS["ATRIUM"]
