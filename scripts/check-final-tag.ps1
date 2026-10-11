# The morning a final file is due: is its tag on GitHub, with time left to do it by hand?
#
# Registered with Windows Task Scheduler as "FinishLine final file check"; see
# scripts/register-final-check-task.ps1. It runs at 07:00, 45 minutes after the prediction
# task starts and an hour before the earliest deadline an 8 am gun gives. On any other day it
# does nothing.
#
# daily-predictions.ps1 already raises a notice when it fails. This covers what that cannot:
# a run that never started, one still going, or one that stopped without throwing. It also
# says so when the tag is there, because on this one morning silence is not an answer
# (PLAN.md 13 item 45). It reads GitHub and changes nothing.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
$log = Join-Path $root 'data\cache\freeze\predictions.log'
$env:PYTHONWARNINGS = 'ignore'
. (Join-Path $PSScriptRoot 'notify.ps1')

function Write-Log([string]$line) {
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    Add-Content -Path $log -Encoding utf8 -Value "$stamp  $line"
}

try {
    $ErrorActionPreference = 'Continue'
    $due = & $python -m finishline.cli due 2>$null
    if ($LASTEXITCODE -ne 0) { throw "due failed with exit $LASTEXITCODE" }
    foreach ($line in $due) {
        $race, $kind = "$line".Trim() -split '\s+'
        if ($kind -ne 'final') { continue }
        # The name `predictions.final_tag` gives a final file.
        $tag = "predictions/$race/final"
        $found = git ls-remote --tags origin $tag 2>$null
        if ($LASTEXITCODE -ne 0) { throw "could not read the tags on GitHub (exit $LASTEXITCODE)" }
        if ($found) {
            Write-Log "check: $tag is on GitHub"
            Send-Notice "FinishLine: $race final file is published" "$tag is on GitHub."
        } else {
            Write-Log "check: $tag is NOT on GitHub"
            Send-FailureNotice "$race final file" "$tag is not on GitHub and the deadline is 24 hours before the gun. Log: data/cache/freeze/predictions.log"
        }
    }
} catch {
    Write-Log "check failed: $($_.Exception.Message)"
    Send-FailureNotice 'final file check' "$($_.Exception.Message)"
    exit 1
}
