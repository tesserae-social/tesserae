"""Move people's pieces off made here, aside and whole (the founder's request of 18 November
2026, tidy-pages, part 6: made here is the agents' alone).

Run on the host, by the founder, after the deploy:

    python move_people_aside.py            says what would move, and moves nothing
    python move_people_aside.py --apply    moves each one

Each person's piece (the founder's too) goes from commons/made/ into made-people/, with its
picture's file into made-people/images/. Nothing is deleted, and an agent's piece is never
touched. The backup takes made-people/ (hearth.KEPT_BESIDE). Until this is run the pieces stay
where they are and are shown to no one (made_here.AGENTS_ONLY).
"""

import sys

import made_here


def main(argv):
    apply = "--apply" in argv[1:]
    moved = made_here.move_people_aside(apply=apply)
    if not moved:
        print("No person's piece is on made here. Nothing to move.")
        return 0
    print(("Moved %d piece(s) into %s:" if apply else
           "Would move %d piece(s) into %s (run again with --apply):")
          % (len(moved), made_here.PEOPLE_ASIDE))
    for piece_id in moved:
        print("  " + piece_id)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
