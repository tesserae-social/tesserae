<#
.SYNOPSIS
  The publish block of a founding or a coming, as one command, run by the founder in
  PowerShell on the laptop (the founder's request of 18 November 2026, the branch day-pages).

.DESCRIPTION
  Run it after "found_agent.py <id> publish" on the host, and before "finish". It does, in
  order, what the runbook's publish block did by hand:

    1. fetches publish/agents.json and publish/ids/<id>/did.json from the host (flyctl sftp)
    2. on main, pulled, with a clean tree, copies them in as agents.json and ids/<id>/did.json
    3. checks that each copy's hash matches the file fetched, and that agents.json holds <id>
    4. shows the change and asks once (unless -Yes)
    5. commits the two files
    6. deploys (flyctl deploy)
    7. pushes main
    8. checks the hashes again

  It stops at the first thing that isn't right, says what, and exits with a code that is not
  0. Nothing is undone for you: where it stopped is said plainly, and the runbook says what
  to do from there. Tests run it with -Flyctl and -Git pointed at stubs; flyctl runs only
  when the founder runs this.

.EXAMPLE
  .\publish_founding.ps1 -Id second
#>
param(
    [Parameter(Mandatory = $true)][string]$Id,
    [string]$App = "tesserae-hearth",
    [string]$Repo = $PSScriptRoot,
    [string]$Work = "C:\Users\natha\founding\publish",
    [string]$Message = "",
    [string]$Flyctl = "flyctl",
    [string]$Git = "git",
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

function Stop-Here([string]$What) {
    Write-Host ""
    Write-Host "STOPPED: $What" -ForegroundColor Red
    exit 1
}

function Say([string]$What) {
    Write-Host "-- $What"
}

function Invoke-Tool([string]$Tool, [string[]]$Arguments, [string]$What) {
    $global:LASTEXITCODE = 0
    & $Tool @Arguments
    if ($LASTEXITCODE -ne 0) {
        Stop-Here "$What (exit code $LASTEXITCODE)"
    }
}

function Get-Output([string]$Tool, [string[]]$Arguments, [string]$What) {
    $global:LASTEXITCODE = 0
    $said = & $Tool @Arguments
    if ($LASTEXITCODE -ne 0) {
        Stop-Here "$What (exit code $LASTEXITCODE)"
    }
    return (($said | Out-String).Trim())
}

function Get-Hash([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

if ($Id -notmatch '^[a-z][a-z0-9-]{0,30}$') {
    Stop-Here "'$Id' is not an agent's id (lower-case letters, digits and hyphens)."
}
if (-not (Get-Command $Flyctl -ErrorAction SilentlyContinue)) { Stop-Here "flyctl was not found." }
if (-not (Get-Command $Git -ErrorAction SilentlyContinue)) { Stop-Here "git was not found." }
if (-not (Test-Path -LiteralPath (Join-Path $Repo "found_agent.py"))) {
    Stop-Here "$Repo is not the tesserae repository (no found_agent.py)."
}
if ($Message -eq "") {
    $Message = "The founding of $Id, " + (Get-Date -Format "d MMMM yyyy") +
        ": its registry entry and its identity, as published"
}

# 1. fetch
Say "1. fetching the two files from the host"
if (Test-Path -LiteralPath $Work) { Remove-Item -Recurse -Force -LiteralPath $Work }
New-Item -ItemType Directory -Force -Path $Work | Out-Null
$fetchedAgents = Join-Path $Work "agents.json"
$fetchedDid = Join-Path $Work "did.json"
Invoke-Tool $Flyctl @("ssh", "sftp", "get", "-a", $App,
    "/data/foundings/$Id/publish/agents.json", $fetchedAgents) "fetching agents.json failed"
Invoke-Tool $Flyctl @("ssh", "sftp", "get", "-a", $App,
    "/data/foundings/$Id/publish/ids/$Id/did.json", $fetchedDid) "fetching did.json failed"
foreach ($one in @($fetchedAgents, $fetchedDid)) {
    if (-not (Test-Path -LiteralPath $one) -or (Get-Item -LiteralPath $one).Length -eq 0) {
        Stop-Here "$one was not fetched, or is empty. Has 'found_agent.py $Id publish' run on the host?"
    }
}
try {
    $registry = Get-Content -Raw -Encoding UTF8 -LiteralPath $fetchedAgents | ConvertFrom-Json
    Get-Content -Raw -Encoding UTF8 -LiteralPath $fetchedDid | ConvertFrom-Json | Out-Null
} catch {
    Stop-Here "a fetched file is not JSON: $($_.Exception.Message)"
}
$entries = @($registry)
if (-not ($entries | Where-Object { $_.id -eq $Id })) {
    Stop-Here "the fetched agents.json holds no agent '$Id'."
}

# 2. copy in, on main
Say "2. copying them in on main"
Set-Location -LiteralPath $Repo
Invoke-Tool $Git @("switch", "main") "git switch main failed"
$branch = Get-Output $Git @("rev-parse", "--abbrev-ref", "HEAD") "git rev-parse failed"
if ($branch -ne "main") { Stop-Here "the branch is '$branch', not main." }
Invoke-Tool $Git @("pull", "--ff-only") "git pull --ff-only failed"
$dirty = Get-Output $Git @("status", "--porcelain") "git status failed"
if ($dirty -ne "") { Stop-Here "the tree is not clean:`n$dirty" }
Copy-Item -LiteralPath $fetchedAgents -Destination (Join-Path $Repo "agents.json") -Force
$idDir = Join-Path $Repo "ids\$Id"
New-Item -ItemType Directory -Force -Path $idDir | Out-Null
$did = Join-Path $idDir "did.json"
Copy-Item -LiteralPath $fetchedDid -Destination $did -Force

# 3. hashes
Say "3. checking the hashes"
$didHash = Get-Hash $fetchedDid
$agentsHash = Get-Hash $fetchedAgents
if ((Get-Hash $did) -ne $didHash) { Stop-Here "ids\$Id\did.json does not match the file fetched." }
if ((Get-Hash (Join-Path $Repo "agents.json")) -ne $agentsHash) {
    Stop-Here "agents.json does not match the file fetched."
}
Write-Host "did.json  $didHash"
Write-Host "agents.json  $agentsHash"

# 4. look, and say yes
Say "4. the change"
Invoke-Tool $Git @("--no-pager", "diff", "--stat") "git diff failed"
Invoke-Tool $Git @("--no-pager", "diff", "agents.json") "git diff failed"
if (-not $Yes) {
    $answer = Read-Host "Commit, deploy and push this? This can't be undone. Type yes"
    if ($answer -ne "yes") { Stop-Here "not confirmed. Nothing was committed; the two files are copied in. 'git checkout -- agents.json' and removing ids\$Id put it back." }
}

# 5. commit
Say "5. committing"
Invoke-Tool $Git @("add", "agents.json", "ids/$Id/did.json") "git add failed"
Invoke-Tool $Git @("commit", "-m", $Message) "git commit failed"

# 6. deploy
Say "6. deploying"
Invoke-Tool $Flyctl @("deploy", "-a", $App) "flyctl deploy failed. The commit is made and not pushed; deploy again before 'finish'"

# 7. push
Say "7. pushing"
Invoke-Tool $Git @("push", "origin", "main") "git push failed. It is deployed; push again by hand"

# 8. hashes again
Say "8. checking the hashes again"
if ((Get-Hash $did) -ne $didHash) { Stop-Here "ids\$Id\did.json changed after the copy." }
if ((Get-Hash (Join-Path $Repo "agents.json")) -ne $agentsHash) { Stop-Here "agents.json changed after the copy." }
Write-Host "did.json  $didHash"
Write-Host ""
Write-Host "DONE: published, committed, deployed and pushed. Next, on the host: DATA_DIR=/data python found_agent.py $Id finish" -ForegroundColor Green
exit 0
