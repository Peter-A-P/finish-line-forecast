# Weekly: read this year's results index again and fetch any results posted since.
#
# Registered with Windows Task Scheduler as "FinishLine weekly results crawl"; see
# scripts/register-crawl-task.ps1 and docs/data-terms.md. Safe to run by hand.
#
# It stands down from ten days before each race in data/live.toml to the day after
# (`finishline crawl --scheduled`), because a crawl that finds a new race makes the saved
# model backtest stale and `freeze` refuses without a matching one.
#
# The log is appended to data/cache/nlaa/crawl.log, gitignored with the rest of the cache.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$log = Join-Path $root 'data\cache\nlaa\crawl.log'

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $log) | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')

try {
    Push-Location $root
    $output = & $python -m finishline.cli crawl --notices-sent --refresh-index --scheduled 2>&1
    $status = if ($LASTEXITCODE -eq 0) { 'ok' } else { "exit $LASTEXITCODE" }
} catch {
    $output = $_.Exception.Message
    $status = 'failed'
} finally {
    Pop-Location
}

Add-Content -Path $log -Encoding utf8 -Value "$stamp  $status"
foreach ($line in $output) { Add-Content -Path $log -Encoding utf8 -Value "    $line" }
if ($status -ne 'ok') { exit 1 }
