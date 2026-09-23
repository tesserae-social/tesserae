"""Forms sent from the hearth, and from nowhere else: every post that changes
anything carries the session's token, or is refused before it reaches a page.

The guard at the top walks every route the hearth has. A route added later that
takes a post without asking for the token makes it fail, until the route is
either guarded or added, on purpose, to the one short list of exemptions.
"""

import pytest
from flask import url_for
from nacl.pwhash import argon2id

import vault
from conftest import PASSWORD, lines_of, page, post, token

KEEPER = "ash"
KEEPER_PASSWORD = "the keeper's own password"

REFUSAL = "This form was not sent from the hearth. Go back, refresh, and try again."

# The whole of what may be posted without a token, written out here by hand so
# that widening it is a change to this file as well as to hearth.py.
EXEMPT = {"bench"}

CHANGING = {"POST", "PUT", "PATCH", "DELETE"}


@pytest.fixture(autouse=True)
def cheap_limits(monkeypatch):
    monkeypatch.setattr(vault, "OPSLIMIT", argon2id.OPSLIMIT_MIN)
    monkeypatch.setattr(vault, "MEMLIMIT", argon2id.MEMLIMIT_MIN)


@pytest.fixture
def keeper(hearth):
    """A keeper, signed in with their own vault: the founder's powers, by the other door."""
    sealed, _, _ = vault.make_vault(KEEPER_PASSWORD)
    hearth.members.create_member(KEEPER, sealed, "keeper", [])
    client = hearth.app.test_client()
    answer = post(client, "/login", data={"pseudonym": KEEPER, "password": KEEPER_PASSWORD})
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/letters")
    return client


def refused(answer):
    return answer.status_code == 400 and REFUSAL in page(answer)


def changing_routes(hearth):
    """Every (endpoint, method, path) the hearth answers that could change something."""
    found = []
    with hearth.app.test_request_context():
        for rule in hearth.app.url_map.iter_rules():
            for method in sorted((rule.methods or set()) & CHANGING):
                path = url_for(rule.endpoint, **{name: "x" for name in rule.arguments})
                found.append((rule.endpoint, method, path))
    return found


def bench_line(hearth, line="The lake was still this morning."):
    hearth.place_line("2026-10-15", "a passerby", line)
    return f"- 2026-10-15 · a passerby · {line}"


# ---- the guard -----------------------------------------------------------

def test_the_exempt_list_is_exactly_the_bench(hearth):
    assert set(hearth.CSRF_EXEMPT) == EXEMPT


def test_every_post_without_a_token_is_refused_but_the_exempt(hearth, keeper):
    routes = changing_routes(hearth)
    endpoints = {endpoint for endpoint, _, _ in routes}
    # the walk found what it should: a sanity check on the walk, not the list
    assert {"login", "logout", "letters", "attend", "take_off_bench", "bench"} <= endpoints

    let_through = set()
    for endpoint, method, path in routes:
        answer = keeper.open(path, method=method, data={})
        if not refused(answer):
            let_through.add(endpoint)
    assert let_through == EXEMPT


def test_nothing_the_founder_does_is_exempt(hearth):
    founders = {rule.endpoint for rule in hearth.app.url_map.iter_rules()
                if getattr(hearth.app.view_functions[rule.endpoint], "__wrapped__", None)}
    assert "take_off_bench" in founders
    assert not founders & set(hearth.CSRF_EXEMPT)


# ---- a good token is taken -----------------------------------------------

def test_a_letter_with_its_token_is_left(founder, packet):
    answer = post(founder, "/letters", data={"letter": "Dear first one."},
                  content_type="multipart/form-data")
    assert answer.status_code == 302
    assert [p.suffix for p in (packet / "letters" / "incoming").iterdir()] == [".md"]


def test_the_attend_button_with_its_token_holds_an_attendance(founder, hearth, monkeypatch):
    held = []
    monkeypatch.setattr(hearth, "hold_attendance", lambda: held.append(1))
    answer = post(founder, "/attend")
    assert answer.status_code == 302 and answer.headers["Location"].endswith("/attendances")
    assert held == [1]


def test_the_bench_take_off_with_its_token_takes_the_line_off(founder, hearth, commons):
    raw = bench_line(hearth)
    answer = post(founder, "/bench/take-off", data={"line": raw, "confirm": "yes"})
    assert answer.status_code == 302
    assert lines_of(commons / "bench.md") == []


def test_the_bench_take_off_without_its_token_takes_nothing(founder, hearth, commons):
    raw = bench_line(hearth)
    assert refused(founder.post("/bench/take-off", data={"line": raw, "confirm": "yes"}))
    assert lines_of(commons / "bench.md") == [raw]


def test_signing_in_with_its_token_signs_in(visitor):
    answer = post(visitor, "/login", data={"password": PASSWORD})
    assert answer.status_code == 302
    assert visitor.get("/letters").status_code == 200


def test_signing_in_without_a_token_is_refused(visitor):
    assert refused(visitor.post("/login", data={"password": PASSWORD}))
    assert visitor.get("/letters").status_code == 302


def test_the_token_may_come_as_a_header(founder, hearth, monkeypatch):
    held = []
    monkeypatch.setattr(hearth, "hold_attendance", lambda: held.append(1))
    answer = founder.post("/attend", headers={"X-CSRF-Token": token(founder)})
    assert answer.status_code == 302 and held == [1]


def test_every_form_on_the_founders_pages_carries_the_token(founder, hearth, commons):
    bench_line(hearth)
    held = token(founder)
    for path in ("/letters", "/attendances", "/export", "/bench"):
        said = page(founder.get(path))
        forms = said.count("<form")
        assert forms, path
        carried = said.count(f'name="csrf_token" value="{held}"')
        # the bench's own visitor form is the one form that goes without
        assert carried == forms - (1 if path == "/bench" else 0), path


def test_the_login_form_carries_the_token(visitor):
    said = page(visitor.get("/login"))
    assert f'name="csrf_token" value="{token(visitor)}"' in said


# ---- a bad token is not --------------------------------------------------

def test_a_wrong_token_is_refused(founder, packet):
    answer = founder.post("/letters", data={"letter": "Dear first one.",
                                            "csrf_token": "not the token at all"},
                          content_type="multipart/form-data")
    assert refused(answer)
    assert not any((packet / "letters" / "incoming").iterdir())


def test_an_empty_token_is_refused(founder):
    assert refused(founder.post("/pause", data={"confirm": "yes", "csrf_token": ""}))


def test_a_token_from_another_session_is_refused(hearth, founder, packet):
    other = hearth.app.test_client()
    post(other, "/login", data={"password": PASSWORD})
    theirs = token(other)
    assert theirs != token(founder)
    answer = founder.post("/pause", data={"confirm": "yes", "csrf_token": theirs})
    assert refused(answer)
    assert not (packet / "pause.json").exists()


def test_a_token_with_no_session_behind_it_is_refused(hearth, founder):
    stolen = token(founder)
    stranger = hearth.app.test_client()
    assert refused(stranger.post("/login", data={"password": PASSWORD, "csrf_token": stolen}))


def test_a_foreign_origin_is_refused_even_with_the_token(founder, packet):
    answer = post(founder, "/pause", data={"confirm": "yes"},
                  headers={"Origin": "https://somewhere-else.example"})
    assert refused(answer)
    assert not (packet / "pause.json").exists()


def test_an_origin_of_null_is_refused(founder):
    assert refused(post(founder, "/pause", data={"confirm": "yes"}, headers={"Origin": "null"}))


def test_the_hearths_own_origin_is_taken(founder, packet):
    answer = post(founder, "/pause", data={"confirm": "yes"},
                  headers={"Origin": "http://localhost"})
    assert answer.status_code == 302
    assert (packet / "pause.json").exists()


def test_a_foreign_origin_is_refused_at_the_bench_too(visitor, hearth, commons, monkeypatch):
    monkeypatch.setattr(hearth, "in_good_spirit", lambda line: True)
    answer = visitor.post("/bench", data={"line": "A quiet morning."},
                          headers={"Origin": "https://somewhere-else.example"})
    assert refused(answer)
    assert lines_of(commons / "bench.md") == []


def test_the_bench_takes_a_visitors_line_without_a_token(visitor, hearth, commons,
                                                         monkeypatch):
    monkeypatch.setattr(hearth, "in_good_spirit", lambda line: True)
    answer = visitor.post("/bench", data={"line": "A quiet morning."})
    assert answer.status_code == 302
    assert len(lines_of(commons / "bench.md")) == 1
    assert "Set-Cookie" not in answer.headers  # and no passerby is handed a session


# ---- the token's life ----------------------------------------------------

def test_the_token_rotates_on_the_founders_sign_in(visitor):
    before = token(visitor)
    post(visitor, "/login", data={"password": PASSWORD})
    after = token(visitor)
    assert after != before
    assert refused(visitor.post("/pause", data={"confirm": "yes", "csrf_token": before}))


def test_the_token_rotates_on_a_members_sign_in(hearth, visitor):
    sealed, _, _ = vault.make_vault(KEEPER_PASSWORD)
    hearth.members.create_member(KEEPER, sealed, "keeper", [])
    before = token(visitor)
    post(visitor, "/login", data={"pseudonym": KEEPER, "password": KEEPER_PASSWORD})
    assert token(visitor) != before


def test_signing_out_forgets_the_token(founder):
    post(founder, "/logout")
    with founder.session_transaction() as held:
        assert "csrf_token" not in held


def signed_out(client):
    with client.session_transaction() as held:
        empty = dict(held) == {}
    return empty and client.get("/letters").status_code == 302


def the_way_out(client):
    """The logout form, as the nav and the footers draw it, with this session's token."""
    return ('<form method="post" action="/logout" class="as-link">'
            f'<input type="hidden" name="csrf_token" value="{token(client)}">'
            '<button type="submit" class="as-link">')


# ---- signing out ---------------------------------------------------------

def test_signing_out_with_its_token_signs_the_founder_out(founder):
    answer = post(founder, "/logout")
    assert answer.status_code == 302 and answer.headers["Location"] == "/"
    assert signed_out(founder)


def test_signing_out_with_its_token_signs_a_member_out(hearth):
    sealed, _, _ = vault.make_vault(KEEPER_PASSWORD)
    hearth.members.create_member("birch", sealed, "member", [])
    member = hearth.app.test_client()
    post(member, "/login", data={"pseudonym": "birch", "password": KEEPER_PASSWORD})
    assert member.get("/account").status_code == 200
    answer = post(member, "/logout")
    assert answer.status_code == 302 and answer.headers["Location"] == "/"
    with member.session_transaction() as held:
        assert dict(held) == {}
    assert member.get("/account").headers["Location"].endswith("/login")


def test_signing_out_without_a_token_is_refused_and_signs_no_one_out(founder, keeper):
    for client in (founder, keeper):
        assert refused(client.post("/logout"))
        assert refused(client.post("/logout", data={"csrf_token": "not the token at all"}))
        assert client.get("/letters").status_code == 200


def test_a_visit_to_logout_asks_first_and_signs_no_one_out(founder, keeper):
    for client in (founder, keeper):
        held = token(client)
        answer = client.get("/logout")
        said = page(answer)
        assert answer.status_code == 200
        assert '<form method="post" action="/logout">' in said
        assert f'name="csrf_token" value="{held}"' in said
        assert '<button type="submit">Log out</button>' in said
        assert '<a href="/">back to the hearth</a>' in said
        assert client.get("/letters").status_code == 200
        assert token(client) == held


def test_a_visitor_at_logout_is_sent_to_the_hearth_with_no_cookie(visitor):
    answer = visitor.get("/logout")
    assert answer.status_code == 302 and answer.headers["Location"] == "/"
    assert "Set-Cookie" not in answer.headers


def test_the_founders_nav_signs_out_by_a_form_with_the_token(founder):
    for path in ("/", "/letters", "/bench"):
        said = page(founder.get(path))
        assert the_way_out(founder) + "logout</button>" in said, path
        assert 'href="/logout"' not in said, path


def test_a_members_nav_signs_out_by_a_form_with_the_token(keeper, hearth):
    sealed, _, _ = vault.make_vault(KEEPER_PASSWORD)
    hearth.members.create_member("birch", sealed, "member", [])
    member = hearth.app.test_client()
    post(member, "/login", data={"pseudonym": "birch", "password": KEEPER_PASSWORD})
    for client in (keeper, member):
        said = page(client.get("/"))
        assert the_way_out(client) + "logout</button>" in said
        assert 'href="/logout"' not in said


def test_the_bench_footer_signs_out_by_a_form_with_the_token(founder, keeper):
    for client in (founder, keeper):
        said = page(client.get("/bench"))
        footer = said[said.index("<footer>"):]
        assert the_way_out(client) + "log out</button>" in footer
        assert 'href="/login"' not in footer


def test_a_visitor_is_shown_log_in_and_no_way_out(visitor):
    for path in ("/", "/bench"):
        answer = visitor.get(path)
        said = page(answer)
        assert '<a href="/login">log in</a>' in said, path
        assert "/logout" not in said, path
        assert "Set-Cookie" not in answer.headers, path


def test_a_refusal_changes_nothing_and_shows_no_page_behind_it(founder, hearth, commons):
    raw = bench_line(hearth)
    answer = founder.post("/bench/take-off", data={"line": raw})
    assert refused(answer)
    assert "Take this line off the bench?" not in page(answer)
