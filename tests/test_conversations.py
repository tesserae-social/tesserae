"""Conversations on a member's home page (small-builds, the founder's request of 23 November
2026): two columns, "They wrote last" and "You wrote last", each newest first; each a fold with
who, the start of the last message, who wrote it and when; opened, the whole exchange."""


from conftest import FOUNDER_NAME, page, write, write_json


def letters(packet):
    room = packet.parents[1] / "rooms" / "first"
    write(room / "letters" / "read" / "founder-2026-10-04T09-00-00Z.md",
          "MY FIRST LETTER, which runs on.\n")
    write(room / "letters" / "outgoing" / "to-founder-2026-10-05T09-00-00Z.md",
          "ITS ANSWER to the founder.\n\nAND A SECOND PARAGRAPH.\n")
    return room


def notes_with_wren(hearth, data_dir):
    import vault
    from nacl import pwhash
    held = vault.OPSLIMIT, vault.MEMLIMIT
    vault.OPSLIMIT, vault.MEMLIMIT = pwhash.argon2id.OPSLIMIT_MIN, pwhash.argon2id.MEMLIMIT_MIN
    try:
        sealed, _, _ = vault.make_vault("wren's own password")
    finally:
        vault.OPSLIMIT, vault.MEMLIMIT = held
    hearth.members.create_member("wren", sealed, "member", [])
    write_json(data_dir / "knocks" / ("wren--" + FOUNDER_NAME + ".json"),
               {"from": "wren", "to": FOUNDER_NAME, "at": "2026-10-06T09-00-00Z",
                "note": "WREN'S KNOCK", "introduction": None, "told_at": None,
                "answer": "yes", "answered_at": "2026-10-07T09-00-00Z", "reply": "COME IN",
                "answer_told_at": None, "waits_for_room": False, "set_up_at": None})
    write_json(data_dir / "notes" / "".join(
        "--".join(sorted(("wren", FOUNDER_NAME))) + ".json"),
        {"between": sorted(["wren", FOUNDER_NAME]),
         "notes": [{"from": "wren", "at": "2026-10-08T09-00-00Z", "words": "WREN'S NOTE"}]})


def test_two_columns_each_a_fold_with_the_whole_exchange(
        hearth, founder, packet, data_dir, conversations_shown):
    letters(packet)
    notes_with_wren(hearth, data_dir)
    said = page(founder.get("/"))
    assert said.index("They wrote last") < said.index("You wrote last")
    # both last wrote to the founder: the notes (8 October) before the room (5 October)
    theirs = said[said.index("They wrote last"):said.index("You wrote last")]
    assert theirs.index("WREN&#39;S NOTE") < theirs.index("ITS ANSWER")
    # the fold's line: who, the start of the last message, who wrote it, the day
    assert "&ldquo;ITS ANSWER to the founder. AND A SECOND PARAGRAPH.&rdquo;" in said
    assert "5 October 2026" in said
    # opened: the knock, the answer and the notes, each with its writer and day
    for line in ("you · 4 October 2026 · letter", "wren · 6 October 2026 · knock",
                 "you · 7 October 2026 · answer", "wren · 8 October 2026 · note"):
        assert line in said
    assert "Yes. COME IN" in said and "MY FIRST LETTER" in said
    assert 'class="post mine"' in said
    assert "open the room" in said and "open the notes" in said
    # no cards, and nothing counted
    assert "nothing is waiting" not in said and "overdue" not in said


def test_a_room_with_nothing_written_waits_on_the_left(founder, conversations_shown):
    said = page(founder.get("/"))
    if "no letters yet" in said:  # the founder's room with the first one, where it stands
        assert said.index("no letters yet") < said.index("You wrote last")


def test_where_the_member_wrote_last_it_is_on_the_right(founder, packet, conversations_shown):
    room = letters(packet)
    write(room / "letters" / "incoming" / "founder-2026-10-09T09-00-00Z.md", "MY LATEST.\n")
    said = page(founder.get("/"))
    assert said.index("You wrote last") < said.index("&ldquo;MY LATEST.&rdquo;")


def test_without_the_switch_the_cards_are_as_before(founder, packet):
    letters(packet)
    said = page(founder.get("/"))
    assert "They wrote last" not in said and "your correspondences" in said
