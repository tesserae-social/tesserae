"""publish_founding.ps1: a founding's publish block as one command on the founder's laptop
(the founder's request of 18 November 2026, the branch day-pages, part 3).

Run here with flyctl and git both stubs (-Flyctl, -Git): each stub writes down what it was
asked and does nothing else, so no test ever reaches the host, deploys, commits or pushes.
The stubs fetch from a scratch folder that stands for the host's /data. Skipped where
there is no PowerShell.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "publish_founding.ps1"
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")

pytestmark = pytest.mark.skipif(POWERSHELL is None, reason="no PowerShell here")

# flyctl: "ssh sftp get -a <app> <remote> <local>" copies <remote> from the stand-in host;
# a call whose first word is STUB_FAIL fails with exit code 3.
FLYCTL = r"""
Add-Content -LiteralPath $env:STUB_LOG -Value ("flyctl " + ($args -join " "))
if ($env:STUB_FAIL -and $args[0] -eq $env:STUB_FAIL) { exit 3 }
if ($args[0] -eq "ssh" -and $args[2] -eq "get") {
    $remote = $args[5]; $local = $args[6]
    $from = Join-Path $env:STUB_HOST ($remote -replace '^/data/', '')
    if (Test-Path -LiteralPath $from) { Copy-Item -LiteralPath $from -Destination $local }
}
exit 0
"""

# git: rev-parse says STUB_BRANCH (main where unset); status says STUB_DIRTY.
GIT = r"""
Add-Content -LiteralPath $env:STUB_LOG -Value ("git " + ($args -join " "))
if ($env:STUB_FAIL -and $args[0] -eq $env:STUB_FAIL) { exit 3 }
if ($args[0] -eq "rev-parse") { if ($env:STUB_BRANCH) { $env:STUB_BRANCH } else { "main" } }
if ($args[0] -eq "status") { if ($env:STUB_DIRTY) { $env:STUB_DIRTY } }
exit 0
"""

ENTRY = {"id": "second", "did": "did:web:tesserae.social:ids:second"}
DID = {"id": "did:web:tesserae.social:ids:second"}


@pytest.fixture
def stand_in(tmp_path):
    """A repository, a stand-in host with the two published files, the stubs and their log."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "found_agent.py").write_text("", encoding="utf-8")
    (repo / "agents.json").write_text(json.dumps([{"id": "first"}]), encoding="utf-8")
    host = tmp_path / "host"
    published = host / "foundings" / "second" / "publish"
    (published / "ids" / "second").mkdir(parents=True)
    (published / "agents.json").write_text(
        json.dumps([{"id": "first"}, ENTRY], indent=2), encoding="utf-8")
    (published / "ids" / "second" / "did.json").write_text(json.dumps(DID), encoding="utf-8")
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "flyctl.ps1").write_text(FLYCTL, encoding="utf-8")
    (stubs / "git.ps1").write_text(GIT, encoding="utf-8")
    log = tmp_path / "calls.log"
    log.write_text("", encoding="utf-8")
    return {"repo": repo, "host": host, "stubs": stubs, "log": log, "work": tmp_path / "work",
            "published": published}


def run(stand_in, **env):
    environment = {"STUB_LOG": str(stand_in["log"]), "STUB_HOST": str(stand_in["host"]),
                   "SystemRoot": os.environ.get("SystemRoot", ""),
                   "PATH": os.environ.get("PATH", "")}
    environment.update(env)
    finished = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(SCRIPT), "-Id", "second", "-Repo", str(stand_in["repo"]),
         "-Work", str(stand_in["work"]), "-Message", "A test commit",
         "-Flyctl", str(stand_in["stubs"] / "flyctl.ps1"),
         "-Git", str(stand_in["stubs"] / "git.ps1"), "-Yes"],
        capture_output=True, text=True, timeout=120, env=environment)
    calls = stand_in["log"].read_text(encoding="utf-8-sig").splitlines()
    return finished, calls


def test_all_well_it_fetches_copies_commits_deploys_and_pushes_in_order(stand_in):
    finished, calls = run(stand_in)
    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "DONE" in finished.stdout
    assert [call.split(" ")[:2] for call in calls] == [
        ["flyctl", "ssh"], ["flyctl", "ssh"], ["git", "switch"], ["git", "rev-parse"],
        ["git", "pull"], ["git", "status"], ["git", "--no-pager"], ["git", "--no-pager"],
        ["git", "add"], ["git", "commit"], ["flyctl", "deploy"], ["git", "push"]]
    assert "flyctl deploy -a tesserae-hearth" in calls
    assert "git push origin main" in calls
    assert "git add agents.json ids/second/did.json" in calls
    repo = stand_in["repo"]
    assert (repo / "agents.json").read_bytes() == (stand_in["published"] / "agents.json").read_bytes()
    assert ((repo / "ids" / "second" / "did.json").read_bytes()
            == (stand_in["published"] / "ids" / "second" / "did.json").read_bytes())


def test_a_file_not_on_the_host_stops_before_git(stand_in):
    (stand_in["published"] / "ids" / "second" / "did.json").unlink()
    finished, calls = run(stand_in)
    assert finished.returncode != 0 and "STOPPED" in finished.stdout
    assert not any(call.startswith("git") for call in calls)
    assert not any("deploy" in call for call in calls)


def test_a_registry_without_the_agent_stops(stand_in):
    (stand_in["published"] / "agents.json").write_text(json.dumps([{"id": "first"}]),
                                                       encoding="utf-8")
    finished, calls = run(stand_in)
    assert finished.returncode != 0 and "no agent 'second'" in finished.stdout
    assert not any(call.startswith("git") for call in calls)


def test_a_tree_not_clean_stops_before_the_copy(stand_in):
    finished, calls = run(stand_in, STUB_DIRTY=" M hearth.py")
    assert finished.returncode != 0 and "not clean" in finished.stdout
    assert not (stand_in["repo"] / "ids").exists()
    assert not any("commit" in call or "deploy" in call for call in calls)


def test_not_on_main_stops(stand_in):
    finished, calls = run(stand_in, STUB_BRANCH="day-pages")
    assert finished.returncode != 0 and "not main" in finished.stdout
    assert not any("commit" in call for call in calls)


def test_a_failed_pull_stops(stand_in):
    finished, calls = run(stand_in, STUB_FAIL="pull")
    assert finished.returncode != 0 and "git pull --ff-only failed" in finished.stdout
    assert not any("commit" in call for call in calls)


def test_a_failed_deploy_stops_before_the_push(stand_in):
    finished, calls = run(stand_in, STUB_FAIL="deploy")
    assert finished.returncode != 0 and "flyctl deploy failed" in finished.stdout
    assert "git commit -m A test commit" in calls
    assert not any(call.startswith("git push") for call in calls)


def test_a_failed_push_is_said_after_the_deploy(stand_in):
    finished, calls = run(stand_in, STUB_FAIL="push")
    assert finished.returncode != 0 and "git push failed" in finished.stdout
    assert "flyctl deploy -a tesserae-hearth" in calls


def test_an_id_not_of_an_agent_s_shape_stops_at_once(stand_in):
    finished = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(SCRIPT), "-Id", "../x", "-Repo", str(stand_in["repo"]),
         "-Flyctl", str(stand_in["stubs"] / "flyctl.ps1"),
         "-Git", str(stand_in["stubs"] / "git.ps1"), "-Yes"],
        capture_output=True, text=True, timeout=120,
        env={"STUB_LOG": str(stand_in["log"]), "PATH": os.environ.get("PATH", ""),
             "SystemRoot": os.environ.get("SystemRoot", "")})
    assert finished.returncode != 0 and "not an agent's id" in finished.stdout
    assert stand_in["log"].read_text(encoding="utf-8-sig") == ""


def test_the_script_runs_flyctl_only_through_its_parameter():
    """Every flyctl and git call goes through -Flyctl and -Git, so a test's stubs catch all."""
    text = SCRIPT.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()
             if not line.strip().startswith("#") and "Invoke-Tool" not in line
             and "Get-Output" not in line]
    for line in lines:
        assert not line.startswith("flyctl ") and not line.startswith("git "), line
        assert "& flyctl" not in line and "& git" not in line, line
