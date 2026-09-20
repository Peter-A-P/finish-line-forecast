# Register (or re-register) the daily entrant-list snapshot with Windows Task Scheduler.
#
#     pwsh -File scripts\register-snapshot-task.ps1
#
# To see it:     Get-ScheduledTask -TaskName 'FinishLine daily entrant snapshot'
# To remove it:  Unregister-ScheduledTask -TaskName 'FinishLine daily entrant snapshot' -Confirm:$false
#
# Why a scheduled task and not something inside the tooling: the two lists are live pages
# with no archive anywhere, the race is weeks away, and a day not observed is a day gone.
# That needs something that survives a laptop reboot and does not depend on anyone
# remembering, which rules out anything living inside an editor session.
#
# ⚠️ It runs at 20:23 local rather than on the hour, and with StartWhenAvailable set, so a
# laptop that was closed at 20:23 takes the snapshot when it next wakes rather than
# skipping the day. It runs only on battery as well as mains: a missed day cannot be
# recovered, and one HTTPS request costs nothing worth saving.

$ErrorActionPreference = 'Stop'

$name = 'FinishLine daily entrant snapshot'
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root 'scripts\daily-snapshot.ps1'

if (-not (Test-Path $script)) { throw "not found: $script" }

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -Daily -At '20:23'

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

try { Unregister-ScheduledTask -TaskName $name -Confirm:$false } catch {}

Register-ScheduledTask `
    -TaskName $name `
    -Description 'Daily snapshot of the Athletics NorthEAST entrant lists for The Whole Field, Called Before the Gun. One request a second, identifying user agent, nothing committed.' `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings | Out-Null

$task = Get-ScheduledTask -TaskName $name
Write-Host "registered: $($task.TaskName)  state $($task.State)"
Write-Host "next run:   $((Get-ScheduledTaskInfo -TaskName $name).NextRunTime)"
