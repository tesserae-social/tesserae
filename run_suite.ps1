<#
Runs the whole test suite in chunks of test files, one process at a time.

Each chunk is its own pytest process, so the memory one chunk takes is given
back before the next starts. One line is printed per chunk, then a total, then
the name of every test that failed or errored.

    .\run_suite.ps1                      # every tests\test_*.py, 15 files a chunk
    .\run_suite.ps1 -ChunkSize 10
    .\run_suite.ps1 -From 4              # start at chunk 4 (after a stop)
    .\run_suite.ps1 -PytestArgs '--agents=absent'
    .\run_suite.ps1 -Match 'atrium'      # only the files whose names match
    .\run_suite.ps1 -Interpreter C:\path\to\python.exe   # another Python (a worktree has no .venv)

Each chunk's full output is kept in -LogDir (default: a folder in TEMP), so a
failure can be read in full. The exit code is 0 only when nothing failed.
#>
param(
    [int]$ChunkSize = 15,
    [int]$From = 1,
    [string]$LogDir = (Join-Path $env:TEMP "tesserae-suite"),
    [string]$PytestArgs = "",
    [string]$Match = "",       # only the files whose names match this pattern, e.g. 'atrium'
    [string]$Interpreter = ""  # the interpreter; by default .venv's beside this script
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = if ($Interpreter) { $Interpreter } else { Join-Path $root ".venv\Scripts\python.exe" }
if (-not (Test-Path $python)) { $python = (Get-Command python).Source }

$files = @(Get-ChildItem -Path (Join-Path $root "tests") -Filter "test_*.py" |
           Where-Object { -not $Match -or $_.Name -match $Match } |
           Sort-Object Name | ForEach-Object { "tests\" + $_.Name })
if ($files.Count -eq 0) { Write-Host "No test files found under tests\."; exit 1 }

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$chunks = [math]::Ceiling($files.Count / $ChunkSize)
Write-Host ("{0} test files, {1} chunks of up to {2}. Logs: {3}" -f $files.Count, $chunks, $ChunkSize, $LogDir)

$kinds = @("passed", "failed", "errors", "skipped", "xfailed", "xpassed")
$total = @{}
foreach ($kind in $kinds) { $total[$kind] = 0 }
$failing = New-Object System.Collections.Generic.List[string]
$broken = New-Object System.Collections.Generic.List[string]
$started = Get-Date

for ($n = $From; $n -le $chunks; $n++) {
    $first = ($n - 1) * $ChunkSize
    $last = [math]::Min($first + $ChunkSize, $files.Count) - 1
    $chunk = @($files[$first..$last])
    $out = Join-Path $LogDir ("chunk-{0:D2}.txt" -f $n)
    $err = Join-Path $LogDir ("chunk-{0:D2}.err.txt" -f $n)

    $arguments = @("-m", "pytest", "-q", "-rfE", "-p", "no:cacheprovider") + $chunk
    if ($PytestArgs) { $arguments += $PytestArgs.Split(" ", [StringSplitOptions]::RemoveEmptyEntries) }
    $clock = Get-Date
    $run = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root `
        -NoNewWindow -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
    $null = $run.Handle   # held, so the exit code can be read once it ends
    # the most memory the chunk's Python held at once, looked at twice a second. A venv's
    # python.exe is a launcher that starts the real interpreter as its child, so the
    # children are read too.
    $peak = 0
    $watched = @{}
    while (-not $run.HasExited) {
        try {
            foreach ($child in @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($run.Id)")) {
                $watched[[int]$child.ProcessId] = $true
            }
        } catch { }
        foreach ($id in @($run.Id) + @($watched.Keys)) {
            try { $peak = [math]::Max($peak, (Get-Process -Id $id -ErrorAction Stop).PeakWorkingSet64) } catch { }
        }
        Start-Sleep -Milliseconds 500
    }
    $run.WaitForExit()
    $peakMB = [int]($peak / 1MB)
    $seconds = [int]((Get-Date) - $clock).TotalSeconds

    $text = @(Get-Content -Path $out -Encoding UTF8)
    $counts = @{}
    foreach ($kind in $kinds) { $counts[$kind] = 0 }
    # the last line pytest writes: "3 failed, 120 passed, 2 skipped in 40.1s"
    $summary = $text | Where-Object { $_ -match "\d+ (passed|failed|error|errors|skipped)" -and $_ -match " in [\d.]+s" } |
               Select-Object -Last 1
    if ($summary) {
        foreach ($m in [regex]::Matches($summary, "(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)")) {
            $kind = $m.Groups[2].Value
            if ($kind -eq "error") { $kind = "errors" }
            $counts[$kind] += [int]$m.Groups[1].Value
        }
    }
    foreach ($kind in $kinds) { $total[$kind] += $counts[$kind] }
    foreach ($line in $text) {
        if ($line -match "^(FAILED|ERROR) (\S+)") { $failing.Add($Matches[1] + " " + $Matches[2]) }
    }

    $names = @($chunk | ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_) })
    $span = "{0} .. {1}" -f $names[0], $names[-1]
    if (-not $summary) {
        $broken.Add("chunk $n ($span): no summary, exit code $($run.ExitCode); see $out and $err")
        Write-Host ("chunk {0,2}/{1}  {2,-60} NO SUMMARY (exit {3}) {4}s, peak {5} MB" -f `
            $n, $chunks, $span, $run.ExitCode, $seconds, $peakMB)
    } else {
        Write-Host ("chunk {0,2}/{1}  {2,-60} {3} passed, {4} failed, {5} errors, {6} skipped  {7}s, peak {8} MB" -f `
            $n, $chunks, $span, $counts["passed"], $counts["failed"], $counts["errors"], $counts["skipped"], $seconds, $peakMB)
    }
}

$minutes = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
Write-Host ""
Write-Host ("TOTAL  {0} passed, {1} failed, {2} errors, {3} skipped, {4} xfailed, {5} xpassed  in {6} min" -f `
    $total["passed"], $total["failed"], $total["errors"], $total["skipped"], $total["xfailed"], $total["xpassed"], $minutes)

if ($failing.Count -gt 0) {
    Write-Host ""
    Write-Host "Failing tests:"
    $failing | Sort-Object -Unique | ForEach-Object { Write-Host "  $_" }
}
if ($broken.Count -gt 0) {
    Write-Host ""
    Write-Host "Chunks that ended without a summary:"
    $broken | ForEach-Object { Write-Host "  $_" }
}

if ($failing.Count -gt 0 -or $broken.Count -gt 0 -or $total["failed"] -gt 0 -or $total["errors"] -gt 0) { exit 1 }
exit 0
