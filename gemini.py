"""An agent whose model is Google's Gemini, woken through the same words as any other.

Which company's model an agent runs on is its registry entry's to say, in its
"provider": "anthropic", or "gemini". An entry that says none is Anthropic's,
as the first one's is and always has been, so nothing about the first one's
waking turns on this file: attend.py reaches here only for an agent whose entry
says "gemini", and Google's SDK is imported only then.

For such an agent, attend.py builds its reading, its system words and its
look-ups exactly as for any other, in the shape Anthropic's API takes, and asks
Client(...).messages.create(...) as it would ask Anthropic's client. Here that
one request is said again as Gemini's generate_content takes it, and Gemini's
answer is given back in the shape attend.py reads: text, any look it asks for,
why it stopped, and what it cost. So nothing an agent is shown is worded twice,
and no word of any agent's changes.

How each thing is said to Gemini (google-genai, generate_content):

  * the system words are its system_instruction; max_tokens its max_output_tokens;
  * a block of text is a text part, a photograph an inline part of its bytes;
    Anthropic's cache marks are left out, since Gemini caches by itself
    (implicit caching: a request that begins as an earlier one did reads that
    beginning again more cheaply, with nothing to ask for);
  * each look-up is a function declaration, with the same JSON schema; the
    SDK's automatic calling is off, so nothing is ever called but by attend.py;
    with its looks used up, function calling is set to NONE for that request,
    as Anthropic's tool_choice "none" is;
  * what it asked to look at is given back as function responses, a photograph
    with one as a part of the response; and its own turn that asked is given
    back exactly as Gemini sent it, so any thought signature goes with it.

What it cost is said in the four counts every attendance keeps
(attend.USAGE_COUNTS): input_tokens, what was read and not from the cache
(the prompt, less what was cached, with any tool-use prompt); output_tokens,
what it wrote, its thinking included, which Gemini bills as output;
cache_read_input_tokens, what the implicit cache gave; and
cache_creation_input_tokens, always 0, since nothing is written to a cache.

Its thinking is set to Gemini's low level (thinking_level LOW), and its
max_output_tokens is its entry's max_tokens, the first one's 8,000 for every
agent founded so far. Google's docs say the limit counts the thinking too ("the
maximum number of tokens a response can generate, including thought tokens"),
and a reply that reaches it while still thinking returns "truncated or empty
output"; so low thinking leaves most of the room for its words.

A reply cut off at that limit (MAX_TOKENS) is as one of Anthropic's cut off at
max_tokens: what came is kept, its stop_reason is "max_tokens", and the next
waking is told it was cut off (attend.CUT_OFF). Any look it began to ask for is
not followed, as attend.py follows none when a reply stopped for its length.
But a reply cut off with no words at all, its thinking having used the room,
is no reply, and is never kept as an empty one.

A reply Gemini blocked, or ended for any other reason than finishing or its
length (its safety, a recitation, anything), or cut off with no words, is no
reply: Stopped is raised, plainly saying which, and the waking fails before
anything of it is kept, as it would if Anthropic's API had answered with an
error. The tide notes it as it notes any failed waking, and the next waking
time tries again.

The key is GEMINI_API_KEY, a secret on the host, as ANTHROPIC_API_KEY is.
"""

import base64

ANTHROPIC = "anthropic"
GEMINI = "gemini"
PROVIDERS = (ANTHROPIC, GEMINI)

KEY = "GEMINI_API_KEY"

# Gemini's model ids begin so; a founding's plan is refused a Gemini model on
# Anthropic, and any other on Gemini.
MODEL_PREFIX = {GEMINI: "gemini-"}

# How long one request may take before it is given up, in milliseconds, as
# Anthropic's client waits ten minutes.
TIMEOUT_MS = 600_000

# A finish of its own accord; a reply cut off at its length, kept as Anthropic's
# is; anything else is a reply Gemini did not finish.
FINISHED = "STOP"
CUT_AT_LENGTH = "MAX_TOKENS"

# How much it thinks before it answers: Gemini's low level, the same for every
# agent on Gemini.
THINKING_LEVEL = "LOW"


def provider_of(agent):
    """Whose model an agent runs on: its entry's provider, or Anthropic's where it says none."""
    return agent.get("provider") or ANTHROPIC


class Stopped(Exception):
    """Gemini blocked a request, or did not finish its reply; nothing of it is kept."""


class Unsaid(Stopped):
    """A reply cut off at its length before any words, its thinking having used the room.

    A waking fails on it as on any Stopped; a founding conversation says so and
    lets the founder ask again (founding_session.py).
    """


def sdk():
    """Google's SDK, imported only when a Gemini agent is asked after."""
    from google import genai
    from google.genai import types
    return genai, types


def sdk_client(api_key):
    """Google's own client, with the key it is given and no other (tests put a fake here)."""
    genai, types = sdk()
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=TIMEOUT_MS))


def client(api_key):
    """A client attend.py and the founding ask as they ask Anthropic's."""
    return Client(sdk_client(api_key))


class Client:
    def __init__(self, google):
        self.messages = Messages(google)


class Text:
    """One reply's words, as attend.py reads a text block."""
    type = "text"

    def __init__(self, text):
        self.text = text


class Look:
    """One look it asked for, as attend.py reads a tool_use block."""
    type = "tool_use"

    def __init__(self, id, name, input):
        self.id, self.name, self.input = id, name, input


class Said(list):
    """A reply's blocks, its words first, carrying Gemini's own turn to be given back whole."""
    original = None


class Usage:
    def __init__(self, metadata):
        def count(name):
            said = getattr(metadata, name, None) if metadata is not None else None
            return said if type(said) is int else 0

        cached = count("cached_content_token_count")
        self.input_tokens = (count("prompt_token_count") - cached
                             + count("tool_use_prompt_token_count"))
        self.output_tokens = count("candidates_token_count") + count("thoughts_token_count")
        self.cache_creation_input_tokens = 0
        self.cache_read_input_tokens = cached


class Reply:
    def __init__(self, content, stop_reason, usage):
        self.content, self.stop_reason, self.usage = content, stop_reason, usage


def named(value):
    """An enum's name as Gemini gives it, or the plain value where it is no enum."""
    return getattr(value, "name", None) or (str(value) if value is not None else "none given")


class Messages:
    """messages.create, as Anthropic's client has it, made with Gemini's generate_content."""

    def __init__(self, google):
        self.google = google
        self.calls = {}  # each look's id as given to attend.py: (its name, Gemini's own id)

    def create(self, model, max_tokens, messages, system=None, tools=None, tool_choice=None,
               **ignored):
        _, types = sdk()
        config = {"max_output_tokens": max_tokens,
                  "thinking_config": types.ThinkingConfig(thinking_level=THINKING_LEVEL),
                  "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True)}
        if system:
            config["system_instruction"] = system
        if tools:
            config["tools"] = [types.Tool(function_declarations=[declared(one, types)
                                                                 for one in tools])]
            if (tool_choice or {}).get("type") == "none":
                config["tool_config"] = types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode="NONE"))
        response = self.google.models.generate_content(
            model=model, contents=[self.content(one, types) for one in messages],
            config=types.GenerateContentConfig(**config))
        return self.reply(response)

    def content(self, message, types):
        """One message of the exchange, as a Gemini content."""
        said = message["content"]
        if message["role"] == "assistant":
            if isinstance(said, Said) and said.original is not None:
                return said.original  # exactly as Gemini sent it, signatures and all
            role = "model"
        else:
            role = "user"
        if isinstance(said, str):
            return types.Content(role=role, parts=[types.Part.from_text(text=said)])
        parts = []
        for block in said:
            kind = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
            if kind == "text":
                text = block["text"] if isinstance(block, dict) else block.text
                parts.append(types.Part.from_text(text=text))
            elif kind == "image":
                parts.append(types.Part.from_bytes(data=base64.b64decode(block["source"]["data"]),
                                                   mime_type=block["source"]["media_type"]))
            elif kind == "tool_result":
                parts.append(self.response(block, types))
            else:
                raise ValueError("a block Gemini is not asked to read: %r" % kind)
        return types.Content(role=role, parts=parts)

    def response(self, block, types):
        """What one look gave, as the function response to the call that asked for it."""
        name, its_id = self.calls[block["tool_use_id"]]
        given = block["content"]
        given = [{"type": "text", "text": given}] if isinstance(given, str) else given
        text = "\n\n".join(one["text"] for one in given if one.get("type") == "text")
        photos = [types.FunctionResponsePart.from_bytes(
            data=base64.b64decode(one["source"]["data"]), mime_type=one["source"]["media_type"])
            for one in given if one.get("type") == "image"]
        part = types.Part.from_function_response(name=name, response={"result": text},
                                                 parts=photos or None)
        if its_id:
            part.function_response.id = its_id
        return part

    def reply(self, response):
        """Gemini's answer in the shape attend.py reads, or Stopped where there is none to read."""
        feedback = getattr(response, "prompt_feedback", None)
        if feedback is not None and getattr(feedback, "block_reason", None):
            raise Stopped("Gemini blocked the request (%s)" % named(feedback.block_reason))
        if not response.candidates:
            raise Stopped("Gemini gave no reply")
        candidate = response.candidates[0]
        finish = named(candidate.finish_reason)
        if finish not in (FINISHED, CUT_AT_LENGTH):
            raise Stopped("Gemini did not finish its reply (%s)" % finish)
        parts = (candidate.content.parts or []) if candidate.content else []
        words = "".join(part.text for part in parts
                        if isinstance(part.text, str) and not part.thought)
        if finish == CUT_AT_LENGTH:
            if not words.strip():  # its thinking used the room, and nothing was said
                raise Unsaid("Gemini cut its reply off at its length before any words (%s)"
                              % finish)
            # what came is kept, as Anthropic's is when cut off; no look is followed
            return Reply(Said([Text(words)]), "max_tokens",
                         Usage(getattr(response, "usage_metadata", None)))
        said = Said([Text(words)])
        said.original = candidate.content
        for part in parts:
            if part.function_call is not None:
                given = "gemini-call-%d" % (len(self.calls) + 1)
                self.calls[given] = (part.function_call.name, part.function_call.id)
                said.append(Look(given, part.function_call.name,
                                 dict(part.function_call.args or {})))
        return Reply(said, "tool_use" if len(said) > 1 else "end_turn",
                     Usage(getattr(response, "usage_metadata", None)))


def declared(tool, types):
    """One look-up, as Anthropic's API takes it, as a Gemini function declaration."""
    schema = tool.get("input_schema") or {}
    return types.FunctionDeclaration(
        name=tool["name"], description=tool.get("description"),
        parameters_json_schema=schema if schema.get("properties") else None)
