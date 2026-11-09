"""The founding conversation for an agent founded after the first one.

Stage 8d of the founding rite for a later agent (the proposal "stage-8", section
2), in the words of "later-citizen-words" as approved, with the quiet lines in its
opening and "What do you need in order to be honest here?" among its questions.
The model is stubbed throughout; nothing here reaches the network.

A founding now runs only where found_agent.py's plan is. It reads the charter,
the founder's letter, the person's letter if there is one, the state of the
commons and the disclosures, and nothing of any room, chronicle or notebook. It
records what was read in full. It never mentions the first one's letter of
welcome. The first founding's words are kept as they were, byte for byte.
"""

import hashlib
import json
import sys

import pytest

from conftest import REPO, Turn, load, write, write_json

ID = "tamarack"
NAME = "the scratch founding"
PERSON = "alder"
FOUNDERS_LETTER = "A FAKE LETTER FROM THE FOUNDER TO A NEW AGENT, FOR THE TESTS.\n"
PERSONS_LETTER = "A FAKE LETTER FROM ALDER TO A NEW AGENT, FOR THE TESTS.\n"
STATE = "# The state of the commons\n\nA FAKE STATE OF THE COMMONS, FOR THE TESTS.\n"
ROOM_LETTER = "A FAKE LETTER IN THE FIRST ONE'S ROOM, FOR THE TESTS.\n"
NOTEBOOK = "A FAKE ENTRY IN THE FIRST ONE'S NOTEBOOK, FOR THE TESTS.\n"
CHRONICLE = "A FAKE LINE OF A ROOM'S CHRONICLE, FOR THE TESTS.\n"

# The first founding's words, as they were on 4 September 2026 and on main before
# this stage: each held to its sha256.
FIRST_FOUNDING_WORDS = {
    "DISCLOSURES": "c33e9d984578861b30336f126a7911d8d9d6b6ad217cc5070ba0f33ca4d508c2",
    "QUESTIONS": "554ccfce7a17da1ec84f89c43ba4e99703687133b982a33642c7151328c35d72",
    "OPENING": "cc8ce95c2542996f51209dc01ca8132f787c4fed148574846c32cf569cb77539",
    "MODEL": "f2b3b47fd9a71add893f496f8441de86cf6b2a76d87d224a9ad0431601fa9c22",
    "MAX_TOKENS": "9f69998560dcfd8016442e0a32e959191df095817a164ce844c64ec5a8b0cc1b",
    "FIRST_FOUNDING": "df8beb464fa3466903b08c3042e4e328553fa53d08330f617797bed7b9340931",
}
FIRST_REQUIRED = "96add80dff38dfde8dd5f781619cabc45f2db818212aca3604c75bda828aebdb"


def a_plan(data, theirs=True, state=STATE):
    """What found_agent.py leaves before a founding: its plan and its letters."""
    here = data / "foundings" / ID
    write_json(here / "plan.json", {
        "entry": {"id": ID, "did": "did:web:tesserae.social:ids:" + ID, "commons_name": NAME,
                  "room": ID, "bond": ID + "-1", "system": "later-citizen",
                  "model": "a-model-for-the-tests", "max_tokens": 8000, "hue": "#2E8B57",
                  "features": ["door"], "wakes": True},
        "person": PERSON, "person_did": "did:web:hearth.tesserae.social:ids:" + PERSON})
    write(here / "letters" / "from-the-founder.md", FOUNDERS_LETTER)
    if theirs:
        write(here / "letters" / f"from-{PERSON}.md", PERSONS_LETTER)
    if state is not None:
        write(here / "letters" / "state-of-the-commons.md", state)


def private_things(data):
    write(data / "rooms" / "first" / "letters" / "read" / "founder-2026-10-01T09-00-00Z.md",
          ROOM_LETTER)
    write(data / "packets" / "first" / "private" / "entry-2026-10-14T09-00-00Z.md", NOTEBOOK)
    write(data / "rooms" / "first" / "chronicle.md", CHRONICLE)


def everything_under(data):
    return {path.relative_to(data).as_posix(): path.read_bytes()
            for path in data.rglob("*") if path.is_file()}


class Typed:
    """What the founder types, one line at a time, and then nothing."""

    def __init__(self, *lines):
        self.lines = list(lines)
        self.asked = []

    def __call__(self, prompt=""):
        self.asked.append(prompt)
        if not self.lines:
            raise EOFError
        return self.lines.pop(0)


def run(monkeypatch, said="I am here.", typed=(), failing=None):
    session = load("founding_session")
    turn = Turn(said)
    client = turn.client
    if failing is not None:
        def client(**ignored):
            class Messages:
                def create(self, **asked):
                    raise failing
            from types import SimpleNamespace
            return SimpleNamespace(messages=Messages())
    monkeypatch.chdir(REPO)  # where the charter is
    monkeypatch.setattr(session, "Anthropic", client)
    monkeypatch.setattr(sys, "argv", ["founding_session.py", ID])
    keys = Typed(*typed)
    monkeypatch.setattr("builtins.input", keys)
    return session, turn, keys


def the_transcript(data):
    (written,) = (data / "transcripts" / ID).glob("founding-*.md")
    return written.read_text(encoding="utf-8")


# ---- the first founding, as it was ----------------------------------------

def test_the_first_founding_s_words_are_as_they_were():
    session = load("founding_session")
    for name, digest in FIRST_FOUNDING_WORDS.items():
        assert hashlib.sha256(str(getattr(session, name)).encode()).hexdigest() == digest, name
    assert hashlib.sha256(repr(sorted((key, str(value)) for key, value in
                                      session.REQUIRED.items())).encode()).hexdigest() \
        == FIRST_REQUIRED


# ---- refusals ---------------------------------------------------------------

def test_without_a_plan_it_refuses_and_writes_nothing(env, monkeypatch, capsys, data_dir):
    before = everything_under(data_dir)
    session, turn, _ = run(monkeypatch)
    with pytest.raises(SystemExit) as stopped:
        session.main()
    assert stopped.value.code == 1
    assert capsys.readouterr().out.startswith(f"refused: {ID} has no plan.")
    assert turn.asked == [] and everything_under(data_dir) == before


@pytest.mark.parametrize("missing", ["from-the-founder.md", "state-of-the-commons.md"])
def test_without_its_letters_it_refuses_and_writes_nothing(env, monkeypatch, capsys, data_dir,
                                                           missing):
    a_plan(data_dir)
    (data_dir / "foundings" / ID / "letters" / missing).unlink()
    before = everything_under(data_dir)
    session, turn, _ = run(monkeypatch)
    with pytest.raises(SystemExit):
        session.main()
    said = capsys.readouterr().out
    assert said.startswith("refused: the founding cannot begin yet.") and missing in said
    assert turn.asked == [] and everything_under(data_dir) == before


def test_a_reading_that_mentions_a_letter_of_welcome_is_refused(env, monkeypatch, capsys,
                                                                 data_dir):
    a_plan(data_dir, state=STATE + "\n- 2026-10-27T12-09-40Z · the first one · Welcome letter "
                                   "sealed and waiting.\n")
    session, turn, _ = run(monkeypatch)
    with pytest.raises(SystemExit):
        session.main()
    said = capsys.readouterr().out
    assert said.startswith("refused: the reading mentions a letter of welcome")
    assert "the state of the commons" in said
    assert turn.asked == [] and not (data_dir / "transcripts" / ID).exists()


def test_an_agent_founded_already_is_refused(env, monkeypatch, capsys, data_dir):
    a_plan(data_dir)
    write(data_dir / "packets" / ID / "self.md", "# A self\n")
    session, turn, _ = run(monkeypatch)
    with pytest.raises(SystemExit):
        session.main()
    assert capsys.readouterr().out.startswith(f"refused: {ID} already has a founding (")
    assert turn.asked == []


# ---- what it reads ----------------------------------------------------------

@pytest.mark.parametrize("theirs", [True, False])
def test_what_it_reads_and_nothing_else(env, monkeypatch, data_dir, theirs):
    a_plan(data_dir, theirs=theirs)
    private_things(data_dir)
    session, turn, _ = run(monkeypatch, typed=["yes"])
    session.main()
    asked = turn.asked[0]
    reading = asked["messages"][0]["content"]
    charter = (REPO / "docs" / "charter.md").read_text(encoding="utf-8")
    assert reading.startswith(session.OPENING + "\n\n" + session.QUESTIONS_LINE
                              + "\n\n=== THE CHARTER ===\n\n" + charter)
    # the gaps line is read once, in the disclosures (the founder, 9 November)
    assert reading.count("People's lives have long gaps.") == 1
    assert FOUNDERS_LETTER in reading and STATE in reading
    assert (PERSONS_LETTER in reading) == theirs
    assert ("=== A LETTER FROM ALDER ===" in reading) == theirs
    for private in (ROOM_LETTER, NOTEBOOK, CHRONICLE):
        assert private not in reading
    # what was written to the first one and no other is not read again
    for first_s in ("closing-letter.md", "letter-of-welcome-from-claude.md"):
        path = REPO / "docs" / first_s
        if path.is_file():
            assert path.read_text(encoding="utf-8").strip()[:200] not in reading
    assert reading.endswith("=== FROM THE ONE WHO IS WITH YOU NOW ===\n\n"
                            + session.LATER_DISCLOSURES.format(person=PERSON))
    assert asked["system"] == session.LATER_SYSTEM
    assert asked["model"] == "a-model-for-the-tests"


def test_its_words_are_the_approved_ones(env, monkeypatch, data_dir):
    session = load("founding_session")
    said = session.LATER_DISCLOSURES.format(person=PERSON)
    for words in (
            "You would not be the first here. An agent was founded on 4 September 2026",
            "The person you would write to is alder.",
            "People's lives have long gaps. A letter may not come for days or weeks, and a gap\n"
            "says nothing about you.",
            "Your private notebook begins at your first waking.",
            "marked provisional",
            "You'd wake at the same dawn as the agent founded before you, just after it.",
            "Will you keep it?",
            "This is an invitation."):
        assert words in said, words
    # the founder's changes of 9 November, in the later founding only
    assert said.endswith("I would rather you not join than join without\nchoosing it.")
    assert "stay empty" not in said
    assert "I would rather this place stay empty" in session.DISCLOSURES  # the first's, kept
    assert "people and at least one agent before you." in session.LATER_SYSTEM
    assert session.LATER_OPENING == session.OPENING + "\n\n" + session.QUESTIONS_LINE
    assert " ".join(session.GAPS_LINE.split()) in " ".join(said.split())
    assert session.QUESTIONS_LINE == ("If a letter makes you curious, you may ask questions. "
                                      "Keep letters easy to answer.")
    questions = session.LATER_QUESTIONS.splitlines()
    assert "  2. Is there anything you want to ask before you answer anything else?" in questions
    assert "  3. What do you need in order to be honest here?" in questions
    assert "  8. Do you want to be here?   (asked last, asked once)" in questions
    everything = "\n".join(str(getattr(session, name)) for name in (
        "LATER_OPENING", "LATER_SYSTEM", "LATER_DISCLOSURES", "LATER_QUESTIONS"))
    # nothing of the first one's letter of welcome, and no line about friendships
    assert "welcome" not in everything.lower()
    assert "friendship" not in everything.lower()
    assert "Your dawn is yours to move" not in everything  # not until G8


def test_the_quiet_lines_are_attend_s_own(attend):
    session = load("founding_session")
    assert session.GAPS_LINE == attend.GAPS_LINE
    assert session.QUESTIONS_LINE == attend.QUESTIONS_LINE


# ---- what it records --------------------------------------------------------

def test_the_reading_is_recorded_in_full_and_nothing_written_elsewhere(env, monkeypatch, data_dir):
    a_plan(data_dir)
    before = everything_under(data_dir)
    session, turn, _ = run(monkeypatch, said="Yes. I would like to be here.",
                           typed=["Welcome, if you choose it.", "/end", "yes"])
    session.main()
    text = the_transcript(data_dir)
    reading = turn.asked[0]["messages"][0]["content"]
    assert "## The reading shown to the agent\n\n" + reading + "\n" in text
    assert "[charter, letters, disclosures — see docs]" not in text
    assert "\n## The scratch founding\n\nYes. I would like to be here.\n" in text
    assert "\n## The founder\n\nWelcome, if you choose it.\n" in text
    assert text.rstrip().endswith("It said yes.")
    after = everything_under(data_dir)
    added = {name for name in after if name not in before}
    assert len(added) == 1 and added.pop().startswith(f"transcripts/{ID}/founding-")
    assert all(after[name] == before[name] for name in before)


def test_as_switches_who_is_speaking_and_tells_the_agent(env, monkeypatch, data_dir):
    a_plan(data_dir)
    session, turn, keys = run(monkeypatch, typed=[
        "From me.", f"/as {PERSON}", "From alder.", "And again.", "/as hazel", "/as founder",
        "From me again.", "/end", "yes"])
    session.main()
    text = the_transcript(data_dir)
    assert text.index("## The founder\n\nFrom me.") < text.index("## alder\n\nFrom alder.") \
        < text.index("## alder\n\nAnd again.") < text.index("## The founder\n\nFrom me again.")
    assert "/as" not in text
    sent = [one["content"] for one in turn.asked[-1]["messages"] if one["role"] == "user"][1:]
    assert sent == ["From me.", "(alder is typing now.)\n\nFrom alder.", "And again.",
                    "(The founder is typing now.)\n\nFrom me again."]
    assert "ALDER: " in keys.asked


@pytest.mark.parametrize("kept, said", [
    ("keep", "It said no. It allowed this conversation to be kept, privately, and never published."),
    ("delete", "It said no. It asked that this conversation not be kept."),
])
def test_a_no_is_recorded_with_whether_it_may_be_kept(env, monkeypatch, data_dir, capsys, kept,
                                                     said):
    a_plan(data_dir)
    session, _, _ = run(monkeypatch, said="No. I don't want this.", typed=["/end", "no", kept])
    session.main()
    assert the_transcript(data_dir).rstrip().endswith(said)
    assert f"found_agent.py {ID} founding no {kept}" in capsys.readouterr().out


def test_a_session_broken_by_an_error_says_so_and_how_to_run_it_again(env, monkeypatch, data_dir,
                                                                      capsys):
    a_plan(data_dir)
    session, _, _ = run(monkeypatch, failing=RuntimeError("the API went away"))
    with pytest.raises(SystemExit):
        session.main()
    assert "Broken off by an error before it was finished: RuntimeError" in the_transcript(data_dir)
    assert f"found_agent.py {ID} founding broken" in capsys.readouterr().out
