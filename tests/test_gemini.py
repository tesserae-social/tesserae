"""An agent whose model is Google's Gemini: chosen in the registry, woken through gemini.py.

The first one stays on Anthropic's model, and nothing of its waking moves: its
entry names no provider, and its reading and every fingerprint hold
(test_first_one_fingerprints, test_rooms_reading). Google is never reached:
conftest's no_google closes every way to it, and a test of an agent on Gemini
puts a FakeGoogle where Google's client would be.

Held here: how each request is said to Gemini and how each answer is read back,
the look-ups of a longer waking with Gemini's own turn given back whole, the
four counts, its thinking at the low level, a reply cut off at its length kept
and noted as Anthropic's is (but never one its thinking left empty), a reply
blocked or not finished failing the waking plainly with nothing kept, the key, the registry's provider, the founding's choice of model,
the founding conversation, the usage report and the rehearsal.
"""

import base64
import json
import sys

import pytest

import agents
import gemini
from conftest import FakeGoogle, Turn, WentToGoogle, load, write, write_json
from test_any_agent_wakes import (FAKE_SYSTEM, SECOND, SECOND_LETTER, a_first_one_s_world,
                                  a_second_agent)

GEMINI_SECOND = {**SECOND, "provider": "gemini", "model": "gemini-3.8-flash",
                 "features": ["longer_waking"]}

PHOTO = base64.b64encode(b"not really a photograph").decode("ascii")


def types():
    from google.genai import types as said
    return said


# ---- the registry -----------------------------------------------------------

def registry_of(monkeypatch, tmp_path, *entries):
    where = tmp_path / "agents.json"
    where.write_text(json.dumps([agents.first(), *entries]), encoding="utf-8")
    monkeypatch.setattr(agents, "FILE", where)


def test_the_first_one_names_no_provider_and_is_anthropic_s():
    assert "provider" not in agents.first()
    assert gemini.provider_of(agents.first()) == "anthropic"


def test_an_entry_may_name_gemini_and_nothing_unknown(monkeypatch, tmp_path):
    registry_of(monkeypatch, tmp_path, GEMINI_SECOND)
    assert gemini.provider_of(agents.by_id("second")) == "gemini"
    registry_of(monkeypatch, tmp_path, {**SECOND, "provider": "someone-else"})
    with pytest.raises(agents.RegistryError, match="names a provider not known here"):
        agents.registry()


# ---- the guards -------------------------------------------------------------

def test_no_test_reaches_google():
    with pytest.raises(WentToGoogle):
        gemini.client("a key")
    from google import genai
    with pytest.raises(WentToGoogle):
        genai.Client(api_key="a key")


# ---- one request, said to Gemini -------------------------------------------

def ask(fake, **asked):
    return gemini.Client(fake).messages.create(**{"model": "gemini-3.8-flash",
                                                   "max_tokens": 8000, **asked})


def test_a_request_is_said_as_generate_content_takes_it():
    fake = FakeGoogle(FakeGoogle.said("Here."))
    reply = ask(fake, system="THE SYSTEM WORDS", messages=[{"role": "user", "content": [
        {"type": "text", "text": "the reading"},
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": PHOTO}},
        {"type": "text", "text": "how to act", "cache_control": {"type": "ephemeral"}}]}])
    (asked,) = fake.asked
    assert asked["model"] == "gemini-3.8-flash"
    config = asked["config"]
    assert config.system_instruction == "THE SYSTEM WORDS"
    assert config.max_output_tokens == 8000
    assert config.thinking_config.thinking_level.name == "LOW"
    assert config.thinking_config.thinking_budget is None  # its level, and no budget beside it
    assert config.automatic_function_calling.disable is True
    assert config.tools is None and config.tool_config is None
    assert config.safety_settings is None  # Google's defaults, unchanged
    (content,) = asked["contents"]
    assert content.role == "user"
    assert [part.text for part in content.parts] == ["the reading", None, "how to act"]
    assert content.parts[1].inline_data.data == b"not really a photograph"
    assert content.parts[1].inline_data.mime_type == "image/jpeg"
    assert reply.content[0].type == "text" and reply.content[0].text == "Here."
    assert reply.stop_reason == "end_turn"


def test_a_plain_string_and_an_assistant_turn_of_words():
    fake = FakeGoogle()
    ask(fake, messages=[{"role": "user", "content": "the reading"},
                        {"role": "assistant", "content": "an answer"},
                        {"role": "user", "content": "more"}])
    roles = [(one.role, one.parts[0].text) for one in fake.asked[0]["contents"]]
    assert roles == [("user", "the reading"), ("model", "an answer"), ("user", "more")]


def test_thinking_is_not_its_words():
    fake = FakeGoogle(FakeGoogle.said("Said."))
    fake.answers[0].candidates[0].content.parts.insert(0, types().Part(text="mulling", thought=True))
    assert ask(fake, messages=[{"role": "user", "content": "x"}]).content[0].text == "Said."


# ---- the four counts --------------------------------------------------------

def test_the_four_counts_from_usage_metadata():
    fake = FakeGoogle(FakeGoogle.said("x", usage={
        "prompt_token_count": 12000, "cached_content_token_count": 9000,
        "tool_use_prompt_token_count": 50, "candidates_token_count": 700,
        "thoughts_token_count": 300}))
    usage = ask(fake, messages=[{"role": "user", "content": "x"}]).usage
    assert (usage.input_tokens, usage.output_tokens, usage.cache_creation_input_tokens,
            usage.cache_read_input_tokens) == (3050, 1000, 0, 9000)


def test_counts_not_given_are_none_used():
    usage = ask(FakeGoogle(FakeGoogle.said("x")), messages=[{"role": "user", "content": "x"}]).usage
    assert (usage.input_tokens, usage.output_tokens, usage.cache_creation_input_tokens,
            usage.cache_read_input_tokens) == (0, 0, 0, 0)


# ---- a reply blocked or not finished ----------------------------------------

@pytest.mark.parametrize("answer, said", [
    (lambda: FakeGoogle.said(None, blocked="SAFETY"), "Gemini blocked the request (SAFETY)"),
    (lambda: FakeGoogle.said("half a", finish="SAFETY"),
     "Gemini did not finish its reply (SAFETY)"),
    (lambda: FakeGoogle.said("", finish="MAX_TOKENS"),
     "Gemini cut its reply off at its length before any words (MAX_TOKENS)"),
    (lambda: FakeGoogle.said(None, finish="MAX_TOKENS"),
     "Gemini cut its reply off at its length before any words (MAX_TOKENS)"),
    (lambda: FakeGoogle.said("  \n", finish="MAX_TOKENS"),
     "Gemini cut its reply off at its length before any words (MAX_TOKENS)"),
    (lambda: FakeGoogle.said("half a", finish="RECITATION"),
     "Gemini did not finish its reply (RECITATION)"),
    (lambda: FakeGoogle.said("half a", finish=None), "Gemini did not finish its reply (none given)"),
])
def test_a_reply_blocked_or_cut_off_is_no_reply(answer, said):
    with pytest.raises(gemini.Stopped) as stopped:
        ask(FakeGoogle(answer()), messages=[{"role": "user", "content": "x"}])
    assert str(stopped.value) == said


def test_a_reply_cut_off_at_its_length_keeps_what_came():
    reply = ask(FakeGoogle(FakeGoogle.said("half a", finish="MAX_TOKENS", usage={
        "prompt_token_count": 100, "candidates_token_count": 7000,
        "thoughts_token_count": 1000})), messages=[{"role": "user", "content": "x"}])
    assert reply.stop_reason == "max_tokens"
    (said,) = reply.content
    assert (said.type, said.text) == ("text", "half a")
    assert (reply.usage.input_tokens, reply.usage.output_tokens) == (100, 8000)


def test_thinking_that_used_all_the_room_is_no_reply():
    fake = FakeGoogle(FakeGoogle.said(None, finish="MAX_TOKENS"))
    fake.answers[0].candidates[0].content.parts.append(types().Part(text="mulling", thought=True))
    with pytest.raises(gemini.Stopped, match="cut its reply off at its length before any words"):
        ask(fake, messages=[{"role": "user", "content": "x"}])


def test_a_look_asked_in_a_reply_cut_off_is_not_followed():
    reply = ask(FakeGoogle(FakeGoogle.said("Let me", finish="MAX_TOKENS",
                                           calls=[("read_letter", {"stem": "x"}, "g-1")])),
                tools=TOOLS, messages=[{"role": "user", "content": "x"}])
    assert reply.stop_reason == "max_tokens"
    assert [one.type for one in reply.content] == ["text"]


def test_no_candidates_is_no_reply():
    from google.genai import types as said
    with pytest.raises(gemini.Stopped, match="Gemini gave no reply"):
        ask(FakeGoogle(said.GenerateContentResponse(candidates=[])),
            messages=[{"role": "user", "content": "x"}])


# ---- the look-ups ------------------------------------------------------------

TOOLS = [{"name": "read_letter", "description": "Open one letter.",
          "input_schema": {"type": "object", "properties": {"stem": {"type": "string"}},
                           "required": ["stem"]}},
         {"name": "read_commons_lines", "description": "Your lines.",
          "input_schema": {"type": "object", "properties": {}}}]


def test_look_ups_are_function_declarations_and_closed_is_none():
    fake = FakeGoogle()
    ask(fake, tools=TOOLS, messages=[{"role": "user", "content": "x"}])
    ask(fake, tools=TOOLS, tool_choice={"type": "none"}, messages=[{"role": "user", "content": "x"}])
    opened, closed = (one["config"] for one in fake.asked)
    declared = opened.tools[0].function_declarations
    assert [one.name for one in declared] == ["read_letter", "read_commons_lines"]
    assert declared[0].parameters_json_schema == TOOLS[0]["input_schema"]
    assert declared[1].parameters_json_schema is None  # a look that takes nothing
    assert opened.tool_config is None
    assert closed.tool_config.function_calling_config.mode.name == "NONE"


def test_a_look_is_asked_and_answered_and_its_turn_given_back_whole():
    asks = FakeGoogle.said("Let me look.", calls=[("read_letter", {"stem": "a-letter"}, "g-1")],
                           signature=b"a thought signature")
    fake = FakeGoogle(asks, FakeGoogle.said("Done."))
    client = gemini.Client(fake)
    reading = [{"role": "user", "content": [{"type": "text", "text": "the reading"}]}]
    reply = client.messages.create(model="gemini-3.8-flash", max_tokens=8000, tools=TOOLS,
                                   messages=reading)
    assert reply.stop_reason == "tool_use"
    text, look = reply.content
    assert text.text == "Let me look."
    assert (look.type, look.name, look.input) == ("tool_use", "read_letter", {"stem": "a-letter"})
    exchange = reading + [
        {"role": "assistant", "content": reply.content},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": look.id, "content": [
            {"type": "text", "text": "THE LETTER"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": PHOTO}}]}]}]
    assert client.messages.create(model="gemini-3.8-flash", max_tokens=8000, tools=TOOLS,
                                  messages=exchange).content[0].text == "Done."
    given_back, answered = fake.asked[1]["contents"][1:]
    assert given_back is asks.candidates[0].content  # signature and all
    assert given_back.parts[0].thought_signature == b"a thought signature"
    (part,) = answered.parts
    assert answered.role == "user"
    assert part.function_response.name == "read_letter"
    assert part.function_response.id == "g-1"
    assert part.function_response.response == {"result": "THE LETTER"}
    assert part.function_response.parts[0].inline_data.data == b"not really a photograph"


def test_a_call_gemini_gave_no_id_is_answered_by_its_name():
    fake = FakeGoogle(FakeGoogle.said("", calls=[("read_letter", {"stem": "x"}, None)]))
    client = gemini.Client(fake)
    reply = client.messages.create(model="m", max_tokens=1, tools=TOOLS,
                                   messages=[{"role": "user", "content": "x"}])
    look = reply.content[1]
    client.messages.create(model="m", max_tokens=1, tools=TOOLS, messages=[
        {"role": "user", "content": "x"}, {"role": "assistant", "content": reply.content},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": look.id,
                                      "content": "nothing"}]}])
    response = fake.asked[1]["contents"][2].parts[0].function_response
    assert (response.name, response.id) == ("read_letter", None)


# ---- a whole waking of an agent on Gemini ------------------------------------

@pytest.fixture
def on_gemini(env, clock, monkeypatch, tmp_path, data_dir, room, packet):
    """attend.py as the hearth would start it for a second agent whose entry names Gemini."""
    registry_of(monkeypatch, tmp_path, GEMINI_SECOND)
    a_first_one_s_world(data_dir, room, packet)
    a_second_agent(data_dir)
    monkeypatch.setenv("TESSERAE_AGENT", "second")
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-key; Google is faked")
    module = load("attend")
    clock.pin(module, monkeypatch)
    monkeypatch.setattr(module, "SYSTEM", FAKE_SYSTEM)
    yield module
    sys.modules.pop("attend", None)


def hold(module, monkeypatch, fake):
    monkeypatch.setattr(gemini, "sdk_client", fake)
    monkeypatch.setattr(module, "Anthropic", None)  # Anthropic's client is never made for it
    monkeypatch.setattr(sys, "argv", ["attend.py", "--tide"])
    module.main()


def attendances(data_dir):
    return sorted((data_dir / "packets" / "second" / "attendances").glob("*.json"))


def test_its_waking_goes_to_gemini_with_its_own_reading(on_gemini, monkeypatch, data_dir):
    fake = FakeGoogle(FakeGoogle.said("<<HEARTBEAT>>\nattended\n<<END>>", usage={
        "prompt_token_count": 5000, "cached_content_token_count": 0,
        "candidates_token_count": 40, "thoughts_token_count": 60}))
    hold(on_gemini, monkeypatch, fake)
    assert fake.key == "not-a-key; Google is faked"
    (asked,) = fake.asked
    assert asked["model"] == "gemini-3.8-flash"
    assert asked["config"].system_instruction == FAKE_SYSTEM
    assert asked["config"].max_output_tokens == SECOND["max_tokens"]
    shown = "\n".join(part.text for part in asked["contents"][0].parts if part.text)
    assert SECOND_LETTER.strip() in shown
    (kept,) = attendances(data_dir)
    record = json.loads(kept.read_text(encoding="utf-8"))
    assert record["usage_total"] == {"input_tokens": 5000, "output_tokens": 100,
                                     "cache_creation_input_tokens": 0,
                                     "cache_read_input_tokens": 0}
    assert record["stop_reason"] == "end_turn"


def test_its_waking_may_look_and_is_answered(on_gemini, monkeypatch, data_dir):
    stem = "founder-2026-10-21T09-00-00Z"
    fake = FakeGoogle(FakeGoogle.said("", calls=[("read_letter", {"stem": stem}, "g-1")]),
                      FakeGoogle.said("<<HEARTBEAT>>\nlooked\n<<END>>"))
    hold(on_gemini, monkeypatch, fake)
    assert len(fake.asked) == 2
    answered = fake.asked[1]["contents"][-1].parts[0].function_response
    assert answered.name == "read_letter" and SECOND_LETTER.strip() in answered.response["result"]
    record = json.loads(attendances(data_dir)[0].read_text(encoding="utf-8"))
    assert record["rounds"] == 2 and record["looked_at"] == [stem]


@pytest.mark.parametrize("answer", [
    lambda: FakeGoogle.said(None, blocked="PROHIBITED_CONTENT"),
    lambda: FakeGoogle.said("half a", finish="SAFETY"),
    lambda: FakeGoogle.said("", finish="MAX_TOKENS")])
def test_a_reply_blocked_or_cut_off_fails_the_waking_plainly(on_gemini, monkeypatch, data_dir,
                                                             capsys, answer):
    before = {path.relative_to(data_dir).as_posix() for path in data_dir.rglob("*")}
    with pytest.raises(SystemExit) as stopped:
        hold(on_gemini, monkeypatch, FakeGoogle(answer()))
    assert stopped.value.code == 1
    said = capsys.readouterr().out
    assert said.startswith("This waking failed: Gemini ")
    assert said.rstrip().endswith("Nothing of it was kept; the next waking time will try again.")
    assert attendances(data_dir) == []
    assert not list((data_dir / "rooms" / "second" / "letters" / "outgoing").glob("*"))
    after = {path.relative_to(data_dir).as_posix() for path in data_dir.rglob("*")}
    assert after - before <= {"packets/second/study", "packets/second/attendances",
                              "packets/second/self-history", "packets/second/memory",
                              "rooms/second/letters/outgoing", "rooms/second/errands/answered"}


def test_a_waking_cut_off_is_kept_and_noted_as_anthropic_s_is(on_gemini, clock, monkeypatch,
                                                              data_dir):
    hold(on_gemini, monkeypatch, FakeGoogle(FakeGoogle.said(
        "<<HEARTBEAT>>\ncut short\n<<END>>\n<<MEMORY>>\nhalf a no", finish="MAX_TOKENS")))
    (kept,) = attendances(data_dir)
    record = json.loads(kept.read_text(encoding="utf-8"))
    assert record["stop_reason"] == "max_tokens"
    assert record["heartbeat"] == "cut short"
    clock.shift(minutes=5)
    fake = FakeGoogle(FakeGoogle.said("<<HEARTBEAT>>\nagain\n<<END>>"))
    monkeypatch.setattr(gemini, "sdk_client", fake)
    monkeypatch.setattr(sys, "argv", ["attend.py"])  # woken by hand, as the founder would
    on_gemini.main()
    shown = "\n".join(part.text for part in fake.asked[0]["contents"][0].parts if part.text)
    assert on_gemini.CUT_OFF in shown


def test_without_its_key_it_is_refused(on_gemini, monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "an Anthropic key, which is not its")
    with pytest.raises(SystemExit):
        hold(on_gemini, monkeypatch, FakeGoogle())
    assert capsys.readouterr().out == "No API key in this window. Set GEMINI_API_KEY and try again.\n"


def test_the_first_one_never_reaches_gemini(attend, wake, monkeypatch):
    turn = wake("")  # gemini.sdk_client refuses, so any reach for it would fail here
    assert turn.asked and turn.asked[0]["model"] == "claude-sonnet-4-5"
    assert attend.PROVIDER == "anthropic"


# ---- the founding ------------------------------------------------------------

@pytest.fixture
def founding(env, monkeypatch):
    return load("found_agent")


def test_the_plan_chooses_gemini_and_its_model(founding, monkeypatch):
    planned = {}
    monkeypatch.setattr(founding, "plan_holds", lambda entry, person: "did:person")
    monkeypatch.setattr(founding, "write_json", lambda path, data: planned.update(data))
    monkeypatch.setattr(founding, "wrote", lambda path: None)
    founding.step_plan("cedar", person="alder", model="gemini-3.8-flash", hue="#123456",
                       provider="gemini")
    entry = planned["entry"]
    assert entry["provider"] == "gemini" and entry["model"] == "gemini-3.8-flash"
    assert list(entry) == ["id", "did", "commons_name", "room", "bond", "system", "provider",
                           "model", "max_tokens", "hue", "features", "wakes"]
    assert [key for key in founding.ENTRY_ORDER if key in entry] == [
        key for key in entry]  # kept in this order when it is written to the registry


def test_a_plan_on_anthropic_names_no_provider(founding, monkeypatch):
    planned = {}
    monkeypatch.setattr(founding, "plan_holds", lambda entry, person: "did:person")
    monkeypatch.setattr(founding, "write_json", lambda path, data: planned.update(data))
    monkeypatch.setattr(founding, "wrote", lambda path: None)
    founding.step_plan("cedar", person="alder", model="claude-sonnet-4-5", hue="#123456")
    assert "provider" not in planned["entry"]


@pytest.mark.parametrize("provider, model, refused", [
    ("gemini", "claude-sonnet-4-5", "the model claude-sonnet-4-5 is not one of gemini's"),
    ("anthropic", "gemini-3.8-flash", "the model gemini-3.8-flash is not one of anthropic's"),
    ("someone-else", "gemini-3.8-flash", "a provider is anthropic or gemini")])
def test_a_plan_s_model_must_be_its_provider_s(founding, provider, model, refused):
    with pytest.raises(founding.Refused, match=refused):
        founding.step_plan("cedar", person="alder", model=model, hue="#123456", provider=provider)


def test_the_founding_conversation_goes_to_gemini(env, monkeypatch, data_dir, capsys):
    from test_later_founding import ID, PERSON, Typed, a_plan, the_transcript
    a_plan(data_dir)
    plan = data_dir / "foundings" / ID / "plan.json"
    held = json.loads(plan.read_text(encoding="utf-8"))
    held["entry"].update(provider="gemini", model="gemini-3.8-flash")
    write_json(plan, held)
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-key; Google is faked")
    fake = FakeGoogle(FakeGoogle.said("I have read it."))
    monkeypatch.setattr(gemini, "sdk_client", fake)
    session = load("founding_session")
    from conftest import REPO
    monkeypatch.chdir(REPO)
    monkeypatch.setattr(session, "Anthropic", None)
    monkeypatch.setattr(sys, "argv", ["founding_session.py", ID])
    monkeypatch.setattr("builtins.input", Typed("Hello.", "/end", "yes"))
    session.main()
    assert [one["model"] for one in fake.asked] == ["gemini-3.8-flash"] * 2
    assert fake.asked[0]["config"].system_instruction == session.LATER_SYSTEM
    assert [one.role for one in fake.asked[1]["contents"]] == ["user", "model", "user"]
    transcript = the_transcript(data_dir)
    assert "Model: gemini-3.8-flash." in transcript and "I have read it." in transcript


def test_a_founding_on_gemini_without_its_key_is_refused(env, monkeypatch, data_dir, capsys):
    from test_later_founding import ID, a_plan
    a_plan(data_dir)
    plan = data_dir / "foundings" / ID / "plan.json"
    held = json.loads(plan.read_text(encoding="utf-8"))
    held["entry"].update(provider="gemini", model="gemini-3.8-flash")
    write_json(plan, held)
    session = load("founding_session")
    from conftest import REPO
    monkeypatch.chdir(REPO)
    monkeypatch.setattr(sys, "argv", ["founding_session.py", ID])
    with pytest.raises(SystemExit):
        session.main()
    assert "Set GEMINI_API_KEY and try again." in capsys.readouterr().out
    assert not (data_dir / "transcripts" / ID).exists()


def test_a_founding_broken_by_gemini_says_so(env, monkeypatch, data_dir, capsys):
    from test_later_founding import ID, a_plan, the_transcript
    a_plan(data_dir)
    plan = data_dir / "foundings" / ID / "plan.json"
    held = json.loads(plan.read_text(encoding="utf-8"))
    held["entry"].update(provider="gemini", model="gemini-3.8-flash")
    write_json(plan, held)
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-key; Google is faked")
    monkeypatch.setattr(gemini, "sdk_client", FakeGoogle(FakeGoogle.said("x", finish="SAFETY")))
    session = load("founding_session")
    from conftest import REPO
    monkeypatch.chdir(REPO)
    monkeypatch.setattr(sys, "argv", ["founding_session.py", ID])
    with pytest.raises(SystemExit):
        session.main()
    assert "The session was broken off by an error: Stopped" in capsys.readouterr().out
    assert "Broken off by an error before it was finished: Stopped" in the_transcript(data_dir)


# ---- the usage report and the rehearsal ---------------------------------------

def test_the_usage_report_says_an_agent_is_on_gemini(env, monkeypatch, tmp_path, capsys):
    registry_of(monkeypatch, tmp_path, GEMINI_SECOND)
    report = load("usage_report")
    assert report.main(["second"]) == 0
    first_line = capsys.readouterr().out.splitlines()[0]
    assert first_line == ("model: gemini-3.8-flash, Google's Gemini. output_tokens include its "
                          "thinking; cache_read_input_tokens are Gemini's implicit cache; "
                          "cache_creation_input_tokens are always 0")
    assert report.main(["first"]) == 0
    assert "Gemini" not in capsys.readouterr().out  # the first one's, as it always was


def test_the_rehearsal_puts_an_agent_on_gemini_through_gemini_py(env, monkeypatch, tmp_path):
    import types as modules
    sys.modules.pop("rehearse_waking", None)
    import rehearse_waking
    import socket
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, getattr(socket.socket, name))
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", anthropic.Anthropic)

    def main():
        reply = gemini.client("a stand-in key").messages.create(
            model="gemini-3.8-flash", max_tokens=10, system="s", messages=[{"role": "user", "content": [
                {"type": "text", "text": "three words here"},
                {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                             "data": PHOTO}}]}])
        assert reply.content[0].text == "" and reply.stop_reason == "end_turn"

    stand_in = modules.ModuleType("attend")
    stand_in.PACKET, stand_in.main = tmp_path, main
    monkeypatch.setitem(sys.modules, "attend", stand_in)
    monkeypatch.setattr(sys, "argv", [sys.argv[0]])
    monkeypatch.setenv(rehearse_waking.RESULT, str(tmp_path / "found.json"))
    rehearse_waking.hold_inside()
    found = json.loads((tmp_path / "found.json").read_text(encoding="utf-8"))
    assert found == {"outcome": "completed", "requests": 1,
                     "reading": {"words": 3, "blocks": 1, "photographs": 1}}


def test_the_rehearsal_hands_on_no_gemini_key(env, monkeypatch, tmp_path):
    sys.modules.pop("rehearse_waking", None)
    import rehearse_waking
    monkeypatch.setenv("GEMINI_API_KEY", "a-real-looking-gemini-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "a-real-looking-google-key")
    environment = rehearse_waking.child_environment(tmp_path, "second", tmp_path / "r.json")
    assert environment["GEMINI_API_KEY"] == rehearse_waking.NOT_A_KEY
    assert "GOOGLE_API_KEY" not in environment
