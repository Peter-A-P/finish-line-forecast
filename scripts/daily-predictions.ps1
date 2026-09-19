# The prediction week, run each morning: today's list, today's file, the race page, the tag.
#
# Registered with Windows Task Scheduler as "FinishLine daily predictions"; see
# scripts/register-predictions-task.ps1 and publish/daily.py. From seven days before a live
# race with an entrant list to two days before, it publishes a daily file of the entrants no
# earlier file predicted; the day before, the final file with everyone and their places.
#
# Peter authorised this script to commit, tag and push the prediction files and race pages on
# 2026-09-19. It commits nothing else: only the file `freeze` wrote and the page `page` wrote,
# and `freeze` itself refuses to run with uncommitted code. A day with no new entrant writes
# no file and pushes nothing.
#
# Every run appends to data/cache/freeze/predictions.log, whether it worked or not.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$python = Join-Path $root '.venv\Scripts\python.exe'
$log = Join-Path $root 'data\cache\freeze\predictions.log'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null
$env:FINISHLINE_NOTICES_SENT = '1'
$env:PYTHONWARNINGS = 'ignore'

function Write-Log([string]$line) {
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    Add-Content -Path $log -Encoding utf8 -Value "$stamp  $line"
}

function Invoke-Checked([string]$what, [scriptblock]$command) {
    $output = & $command 2>&1
    foreach ($line in $output) { Add-Content -Path $log -Encoding utf8 -Value "    $line" }
    if ($LASTEXITCODE -ne 0) { throw "$what failed with exit $LASTEXITCODE" }
    return $output
}

try {
    $due = Invoke-Checked 'due' { & $python -m finishline.cli due }
    if (-not $due) { Write-Log 'no race in its prediction week'; exit 0 }

    Write-Log 'snapshot'
    Invoke-Checked 'snapshot' { & $python -m finishline.cli snapshot } | Out-Null

    foreach ($line in $due) {
        $race, $kind = "$line".Trim() -split '\s+'
        Write-Log "$race $kind"
        if ($kind -eq 'daily') {
            $out = Invoke-Checked "freeze $race --daily" { & $python -m finishline.cli freeze $race --daily }
        } else {
            $out = Invoke-Checked "freeze $race" { & $python -m finishline.cli freeze $race }
        }
        $wrote = ($out | Select-String -Pattern '^wrote (\S+):' | Select-Object -First 1)
        if (-not $wrote) { Write-Log "$race nothing new today"; continue }
        $path = $wrote.Matches[0].Groups[1].Value
        $digest = ($out | Select-String -Pattern '^sha256 (\S+)').Matches[0].Groups[1].Value
        $tag = ($out | Select-String -Pattern '^tag (\S+)').Matches[0].Groups[1].Value

        Invoke-Checked "page $race" { & $python -m finishline.cli page $race } | Out-Null
        $page = "docs/predictions/$race.md"
        Invoke-Checked 'git add' { git add -- $path $page } | Out-Null
        Invoke-Checked 'git commit' {
            git commit -m "Prediction: $race, $kind file $(Split-Path -Leaf $path)" -m "sha256 $digest" -- $path $page
        } | Out-Null
        Invoke-Checked 'git tag' { git tag -a $tag -m "sha256 $digest" } | Out-Null
        Invoke-Checked 'git push' { git push origin HEAD } | Out-Null
        Invoke-Checked 'git push tag' { git push origin $tag } | Out-Null
        Write-Log "$race published $path as $tag, sha256 $digest"
    }
} catch {
    Write-Log "failed: $($_.Exception.Message)"
    exit 1
}
