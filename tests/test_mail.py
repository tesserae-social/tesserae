"""Email, as mail.py sends it: plain, short, from hello@tesserae.social, through Resend,
and always ending with the line that says replies are not read.

No test sends an email. conftest's outbox takes the key out of the environment,
puts a fake where the transport is, and makes the real post to Resend refuse;
the one test here that builds the real request puts the real post back, against
an opener stubbed to answer as Resend would, and nothing reaches the network.
"""

import io
import json
import os
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

import mail
from conftest import SentEmail

TO = "someone@example.org"
NOW = datetime(2026, 11, 10, 14, 2, 11, tzinfo=timezone.utc)
FOOTER = "Replies to this address aren't read."


@pytest.fixture
def log(env):
    return env / "mail.log"


def message(to=TO):
    return {"to": to, "subject": "A subject", "text": mail.with_footer("Some words.")}


# ---- the guards ------------------------------------------------------------

def test_no_test_has_a_key_and_none_reaches_resend(outbox):
    assert "RESEND_API_KEY" not in os.environ
    assert mail.TRANSPORT is outbox
    with pytest.raises(SentEmail):
        mail.post_to_resend(message(), "a key")


def test_with_no_key_the_real_transport_builds_nothing(outbox, monkeypatch):
    asked = []
    monkeypatch.setattr(mail, "urlopen", lambda *a, **k: asked.append(a))
    assert outbox.real_transport(message()) == mail.NOT_CONFIGURED
    assert not mail.configured()
    assert asked == []


# ---- what is sent ----------------------------------------------------------

def test_every_email_ends_with_the_line_about_replies(outbox, log):
    assert mail.send("confirm", TO, "A subject", "Some words.\n\n", NOW) == mail.SENT
    [sent] = outbox.sent
    assert sent == {"to": TO, "subject": "A subject",
                    "text": "Some words.\n\n" + FOOTER + "\n"}


def test_each_email_it_knows_ends_so_and_links_to_the_hearth_alone(outbox, log):
    token = "t" * 43
    mail.send_confirm(TO, token, NOW)
    mail.send_changing(TO, NOW)
    mail.send_in_use(TO, NOW)
    assert [sent["subject"] for sent in outbox.sent] == [
        "Confirm your email address for Tesserae", "Your email address on Tesserae",
        "Your email address on Tesserae"]
    for sent in outbox.sent:
        assert sent["text"].endswith("\n\n" + FOOTER + "\n")
        assert sent["text"].count("@") == 0  # no address in the words, only in "to"
    assert ("https://hearth.tesserae.social/email/confirm/" + token + "\n") in outbox.sent[0]["text"]
    assert outbox.sent[0]["text"].startswith(
        "Someone on Tesserae asked to use this address. To confirm it, open this link within a day:")


def test_the_log_says_when_what_and_how_and_never_who(outbox, log):
    mail.send_confirm(TO, "t" * 43, NOW)
    outbox.says = "not sent: unreachable"
    mail.send_in_use(TO, NOW)
    assert log.read_text(encoding="utf-8") == (
        "2026-11-10T14:02:11Z · confirm · sent\n"
        "2026-11-10T14:02:11Z · in-use · not sent: unreachable\n")


def test_a_line_break_in_the_address_or_subject_sends_nothing(outbox, log):
    assert mail.send("confirm", TO + "\nBcc: x@example.org", "s", "w", NOW).startswith("not sent")
    assert mail.send("confirm", TO, "s\r\nBcc: x", "w", NOW).startswith("not sent")
    assert mail.send("confirm", "", "s", "w", NOW).startswith("not sent")
    assert outbox.sent == []


def test_a_transport_that_fails_stops_no_page(outbox, log, monkeypatch):
    def broken(message):
        raise RuntimeError("down")
    monkeypatch.setattr(mail, "TRANSPORT", broken)
    assert mail.send("confirm", TO, "s", "w", NOW) == "not sent: something went wrong"


def test_the_day_has_a_ceiling_kept_in_the_log(outbox, log, monkeypatch):
    monkeypatch.setattr(mail, "MAIL_A_DAY", 3)
    yesterday = NOW - timedelta(days=1)
    log.write_text("%s · confirm · sent\n" % yesterday.strftime("%Y-%m-%dT%H:%M:%SZ") * 5
                   + "2026-11-10T01:00:00Z · confirm · not sent: unreachable\n"
                   + "2026-11-10T02:00:00Z · confirm · sent\n" * 2, encoding="utf-8")
    assert mail.send("confirm", TO, "s", "w", NOW) == mail.SENT
    assert mail.send("confirm", TO, "s", "w", NOW) == mail.DAY_FULL
    assert len(outbox.sent) == 1


# ---- the request Resend would be sent --------------------------------------

class Answer:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_real_transport_builds_resend_s_request(outbox, monkeypatch):
    asked = []

    def opener(request, timeout):
        asked.append((request, timeout))
        return Answer(200)

    monkeypatch.setenv("RESEND_API_KEY", "re_not_a_real_key")
    monkeypatch.setattr(mail, "post_to_resend", outbox.real_post)
    monkeypatch.setattr(mail, "urlopen", opener)
    assert outbox.real_transport(message()) == mail.SENT
    [(request, timeout)] = asked
    assert request.full_url == "https://api.resend.com/emails"
    assert request.get_method() == "POST"
    assert timeout == mail.TIMEOUT
    assert request.get_header("Authorization") == "Bearer re_not_a_real_key"
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("User-agent") == "tesserae-hearth"
    assert len(request.get_header("Idempotency-key")) == 32
    assert json.loads(request.data) == {
        "from": "Tesserae <hello@tesserae.social>", "to": [TO],
        "subject": "A subject", "text": "Some words.\n\n" + FOOTER + "\n"}


@pytest.mark.parametrize("trouble, said", [
    (urllib.error.HTTPError("u", 403, "no", {}, io.BytesIO(b"")), "not sent: refused (403)"),
    (urllib.error.URLError("no route"), "not sent: unreachable"),
    (TimeoutError("slow"), "not sent: unreachable"),
])
def test_a_refusal_or_silence_from_resend_is_said_without_the_address(
        outbox, monkeypatch, trouble, said):
    def opener(request, timeout):
        raise trouble

    monkeypatch.setenv("RESEND_API_KEY", "re_not_a_real_key")
    monkeypatch.setattr(mail, "post_to_resend", outbox.real_post)
    monkeypatch.setattr(mail, "urlopen", opener)
    outcome = outbox.real_transport(message())
    assert outcome == said and TO not in outcome
