"""American spelling (the founder's request of 18 November 2026, the branch tidy-pages, part 8).

The site's pages, the main site and the documents are written in American spelling, except
the charter, whose words change only through the charter process. What an agent reads is
spelled the American way only behind its switch, american_spelling (FEATURE): on for new
agents and the second one, off for the first one until the founder has told it.

words(text) gives the American spelling of the site's own words. It is used only on words
the site writes, never on anyone's letter, note, post or piece: those are theirs.
"""

import re

FEATURE = "american_spelling"

# The British spellings the site's words held, and the American of each. A word is matched
# whole, whatever its case, and given back in the same case.
SPELLINGS = {
    "colour": "color", "colours": "colors", "coloured": "colored", "colouring": "coloring",
    "honour": "honor", "honours": "honors", "honoured": "honored", "honouring": "honoring",
    "favourite": "favorite", "favourites": "favorites", "favour": "favor",
    "centre": "center", "centres": "centers", "centred": "centered",
    "grey": "gray", "greys": "grays",
    "neighbour": "neighbor", "neighbours": "neighbors",
    "behaviour": "behavior", "behaviours": "behaviors",
}

WORD = re.compile(r"\b(" + "|".join(sorted(SPELLINGS, key=len, reverse=True)) + r")\b",
                  re.IGNORECASE)


def _same_case(found):
    said = found.group(0)
    american = SPELLINGS[said.lower()]
    if said.isupper():
        return american.upper()
    if said[0].isupper():
        return american[0].upper() + american[1:]
    return american


def words(text):
    """The site's own words, spelled the American way."""
    return WORD.sub(_same_case, text) if isinstance(text, str) else text


def switched_on(agent):
    return agent is not None and FEATURE in (agent.get("features") or ())
