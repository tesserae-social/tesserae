"""Email: the few short, plain messages the hearth sends a person, through Resend.

Every email is plain text, short, and carries no letter text: what each one says
is fixed here, and filled only with a link, a name or a date. Each is sent from
hello@tesserae.social and ends with the one line that says replies are not read,
added here, so no email can go without it. The links in them are built on the
hearth's own address, HEARTH_URL, and never on the address a request came in on,
so that no forged Host can make a link point anywhere else.

    outcome = send(kind, to, subject, text)    # "sent", "not configured", "not sent: ..."

send never raises: an email that cannot go says so in what it gives back and in
mail.log, and the page that asked for it goes on. mail.log, at the root of
DATA_DIR beside backup.log, holds one line for each email asked for - when, of
what kind, and what came of it - and never an address, a subject or a link. It
is in no copy and no backup.

The Resend key is read out of RESEND_API_KEY, a Fly secret, when an email is
sent, and is never written down. With no key nothing is built and nothing goes.

How an email goes is TRANSPORT, a function of the one message; the real one
posts it to Resend through post_to_resend. The tests put a fake in its place and
make post_to_resend refuse (tests/conftest.py), and take the key out of the
environment, so no test ever sends an email.
"""

import json
import os
import re
import secrets
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent

HEARTH_URL = "https://hearth.tesserae.social"
SENDER = "Tesserae <hello@tesserae.social>"
FOOTER = "Replies to this address aren't read."
ENDPOINT = "https://api.resend.com/emails"
AGENT = "tesserae-hearth"  # Resend turns away a request that names no User-Agent
TIMEOUT = 10  # seconds

# A gentle ceiling across every kind, so that a new domain is not taken for a
# sender of too much; under Resend's own free 100 a day. Counted from mail.log,
# by the UTC day, so a deploy does not set it back to nothing.
MAIL_A_DAY = 50
# The emails telling a person something is waiting go only while fewer than this
# many emails of any kind have gone today, so that ten of the fifty are always
# kept for the links to confirm an address and to set a password (the founder,
# 9 November).
WAITING_A_DAY = 40

KEY = "RESEND_API_KEY"
LOG = "mail.log"

SENT = "sent"
NOT_CONFIGURED = "not configured"
NOT_SENT = "not sent: %s"
DAY_FULL = NOT_SENT % "the day's limit"

KIND = re.compile(r"[a-z][a-z-]{0,30}")
LINE_BREAK = re.compile(r"[\r\n]")

SENDING = threading.Lock()  # one email at a time, so the day's count is never passed

# The one opener the real transport uses; a test stubs it, and nothing else.
urlopen = urllib.request.urlopen


# ---------------------------------------------------------------- where


def log_path():
    """mail.log, under DATA_DIR as it stands when an email is asked for."""
    return Path(os.environ.get("DATA_DIR", REPO)) / LOG


def configured():
    """Whether there is a key to send with."""
    return bool(os.environ.get(KEY))


# ---------------------------------------------------------------- the real way


def post_to_resend(message, key):
    """Hand one message to Resend. "sent", or "not sent: ..." with no address in it."""
    body = json.dumps({"from": SENDER, "to": [message["to"]],
                       "subject": message["subject"], "text": message["text"]}).encode("utf-8")
    request = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "User-Agent": AGENT,
        "Idempotency-Key": secrets.token_hex(16),
    })
    try:
        with urlopen(request, timeout=TIMEOUT) as answer:
            status = answer.status
    except urllib.error.HTTPError as refused:
        return NOT_SENT % ("refused (%d)" % refused.code)
    except (urllib.error.URLError, OSError, ValueError):
        return NOT_SENT % "unreachable"
    return SENT if 200 <= status < 300 else NOT_SENT % ("refused (%d)" % status)


def resend(message):
    """The real transport: the key read now, and nothing built without one."""
    key = os.environ.get(KEY)
    if not key:
        return NOT_CONFIGURED
    return post_to_resend(message, key)  # looked up now, so a stand-in is the one reached


TRANSPORT = resend


# ---------------------------------------------------------------- the log


def _stamp(now):
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sent_today(now):
    """How many emails went today, by the UTC day, as mail.log says."""
    day = _stamp(now)[:10]
    try:
        lines = log_path().read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return 0
    return sum(1 for line in lines
               if line.startswith(day) and line.endswith(" · " + SENT))


def note(kind, outcome, now):
    """One line in mail.log; nothing here may stop a page."""
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log:
            log.write("%s · %s · %s\n" % (_stamp(now), kind, outcome))
    except OSError:
        pass


# ---------------------------------------------------------------- sending


def with_footer(text):
    """The words of an email, with the line every email ends with."""
    return text.rstrip() + "\n\n" + FOOTER + "\n"


def send(kind, to, subject, text, now=None, ceiling=None):
    """Send one plain email. Gives back what came of it, and never raises.

    Nothing goes once the day's count has reached the ceiling: MAIL_A_DAY, or a lower
    one asked for, never a higher."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(kind, str) or not KIND.fullmatch(kind):
        kind = "unnamed"
    if (not isinstance(to, str) or not to or LINE_BREAK.search(to)
            or not isinstance(subject, str) or LINE_BREAK.search(subject)
            or not isinstance(text, str)):
        outcome = NOT_SENT % "not a message"
        note(kind, outcome, now)
        return outcome
    message = {"to": to, "subject": subject, "text": with_footer(text)}
    with SENDING:
        limit = MAIL_A_DAY if ceiling is None else min(ceiling, MAIL_A_DAY)
        if sent_today(now) >= limit:
            outcome = DAY_FULL
        else:
            try:
                outcome = TRANSPORT(message)
            except Exception:
                outcome = NOT_SENT % "something went wrong"
            if not isinstance(outcome, str):
                outcome = NOT_SENT % "something went wrong"
        note(kind, outcome, now)
    return outcome


# ---------------------------------------------------------------- the emails

# Each email, word for word (proposals/invitations-design.md, section 12).

CONFIRM = "confirm"
CONFIRM_SUBJECT = "Confirm your email address for Tesserae"
CONFIRM_TEXT = """Someone on Tesserae asked to use this address. To confirm it, open this link within a day:

{link}

If it wasn't you, ignore this email and nothing will change."""

CHANGING = "changing"
CHANGING_SUBJECT = "Your email address on Tesserae"
CHANGING_TEXT = ("The email address for your account on Tesserae is being changed. "
                 "If that wasn't you, sign in and change your password.")

IN_USE = "in-use"
IN_USE_SUBJECT = "Your email address on Tesserae"
IN_USE_TEXT = ("Someone asked to use this address on Tesserae, but an account here already "
               "uses it. Nothing has changed.")


def link(path):
    """A link to one of the hearth's pages, on the hearth's own address."""
    return HEARTH_URL + path


def send_confirm(to, token, now=None):
    return send(CONFIRM, to, CONFIRM_SUBJECT,
                CONFIRM_TEXT.format(link=link("/email/confirm/" + token)), now)


def send_changing(to, now=None):
    return send(CHANGING, to, CHANGING_SUBJECT, CHANGING_TEXT, now)


def send_in_use(to, now=None):
    return send(IN_USE, to, IN_USE_SUBJECT, IN_USE_TEXT, now)

RESET = "reset"
RESET_SUBJECT = "Choose a new password for Tesserae"
RESET_TEXT = """A new password was asked for the account on Tesserae that uses this address. Your name there is {name}. To choose one, open this link within an hour; it works once:

{link}

If you didn't ask, ignore this email; your password stays as it is."""

# The keeper's key is the founder's own, behind the founder's identity, and an
# email never cuts him a new one: what is sent him is the way to his twelve words.
RESET_KEEPER = "reset-keeper"
RESET_KEEPER_SUBJECT = "Your password on Tesserae"
RESET_KEEPER_TEXT = """A new password was asked for the account on Tesserae that uses this address. That account opens with its twelve words, not by email: use them at {link}.

If you didn't ask, ignore this email; nothing has changed."""

CHANGED = "changed"
CHANGED_SUBJECT = "Your password on Tesserae was changed"
CHANGED_TEXT = ("The password for {name} on Tesserae was changed on {day}. "
                "If that wasn't you, choose a new one at {link}.")


def send_reset(to, name, token, now=None):
    return send(RESET, to, RESET_SUBJECT,
                RESET_TEXT.format(name=name, link=link("/reset/" + token)), now)


def send_reset_keeper(to, now=None):
    return send(RESET_KEEPER, to, RESET_KEEPER_SUBJECT,
                RESET_KEEPER_TEXT.format(link=link("/recover")), now)


def send_changed(to, name, day, now=None):
    return send(CHANGED, to, CHANGED_SUBJECT,
                CHANGED_TEXT.format(name=name, day=day, link=link("/forgot")), now)


# When something is waiting for a person on the hearth (proposals/quiet-and-
# questions.md, section 3, as the founder changed it on 9 November): who wrote,
# and a link, and nothing else - never a word of any letter, never a count, never
# "you've been away" - and in every one, a link that stops them.
WAITING = "waiting"
WAITING_SUBJECT = "Something is waiting for you at Tesserae"
WAITING_TEXT = """{who} {has} written to you at Tesserae.

{link}

To stop these emails, open this link: {stop}"""


# A line for each topic of the board a person was mentioned in since their last
# email, in a daily email only, after who has written (or alone).
MENTIONED_LINE = "You were mentioned on the board in {subject}."
MENTIONS_TEXT = """{lines}

{link}

To stop these emails, open this link: {stop}"""


def send_waiting(to, names, stop, now=None, mentioned=()):
    """Tell a person who has written to them, by the names the commons gives them, and
    in which topics of the board they were mentioned, by their subjects."""
    names = [name for name in names if isinstance(name, str) and name]
    mentioned = [one for one in mentioned or () if isinstance(one, str) and one]
    if not names and not mentioned:
        return NOT_SENT % "no one wrote"
    lines = "\n".join(MENTIONED_LINE.format(subject=one) for one in mentioned)
    if not names:
        text = MENTIONS_TEXT.format(lines=lines, link=link("/login"), stop=stop)
    else:
        who = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        text = WAITING_TEXT.format(who=who[:1].upper() + who[1:],
                                   has="has" if len(names) == 1 else "have",
                                   link=link("/login"), stop=stop)
        if lines:
            head, _, rest = text.partition("\n\n")
            text = head + "\n\n" + lines + "\n\n" + rest
    return send(WAITING, to, WAITING_SUBJECT, text, now, ceiling=WAITING_A_DAY)
