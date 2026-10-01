# One-off, docs/todo.md 3c: put the 39 nlaa.ca pages fetched again on 2026-10-01 in place of the
# copies that lost their accented letters. Run AFTER the Turkey Tea final file and BEFORE the
# backtest Cape to Cabot will use: it moves the dataset fingerprint, which makes every saved
# backtest stale. Each staged page was checked to differ from its original only at those letters.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$staged = Join-Path $root 'data\cache\nlaa-refetch'
$live = Join-Path $root 'data\cache\nlaa'
$pages = Get-ChildItem (Join-Path $staged 'pages') -File
foreach ($page in $pages) { Copy-Item $page.FullName (Join-Path $live 'pages') -Force }
Get-Content (Join-Path $staged 'manifest.jsonl') -Encoding utf8 |
    Add-Content (Join-Path $live 'manifest.jsonl') -Encoding utf8
"replaced $($pages.Count) pages; the manifest records the second fetch of each"
