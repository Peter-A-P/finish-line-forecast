# Take the daily look at the two Athletics NorthEAST entrant lists.
#
# Registered with Windows Task Scheduler as "FinishLine daily entrant snapshot"; see
# scripts/register-snapshot-task.ps1 and docs/data-terms.md. Run it by hand any time; it
# is safe to run twice in a day, because an unchanged list writes no second file.
#
# The log is appended to data/entrants/snapshot.log, which is gitignored with the rest of
# data/entrants/. A silent scheduled task that has been failing for a fortnight is worse
# than no task at all, so every run writes a line whether it worked or not.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$log = Join-Path $root 'data\entrants\snapshot.log'

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')

try {
    $output = & $python -m finishline.cli snapshot --notices-sent 2>&1
    $status = if ($LASTEXITCODE -eq 0) { 'ok' } else { "exit $LASTEXITCODE" }
} catch {
    $output = $_.Exception.Message
    $status = 'failed'
}

Add-Content -Path $log -Encoding utf8 -Value "$stamp  $status"
foreach ($line in $output) { Add-Content -Path $log -Encoding utf8 -Value "    $line" }
if ($status -ne 'ok') { exit 1 }
