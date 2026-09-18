# Register (or re-register) the weekly results crawl with Windows Task Scheduler.
#
#     pwsh -File scripts\register-crawl-task.ps1
#
# To see it:     Get-ScheduledTask -TaskName 'FinishLine weekly results crawl'
# To remove it:  Unregister-ScheduledTask -TaskName 'FinishLine weekly results crawl' -Confirm:$false
#
# Results are posted a few days after each race and the cached index cannot show them. Once
# a week is plenty for a calendar of about one race a week, and each run costs one index
# request plus one per new results page, one a second.
#
# It runs Sundays at 03:17 with StartWhenAvailable, so a laptop that was asleep runs it when
# it wakes. The pause around live races is in the command, not the trigger, so it follows
# data/live.toml without re-registering.

$ErrorActionPreference = 'Stop'

$name = 'FinishLine weekly results crawl'
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root 'scripts\weekly-crawl.ps1'

if (-not (Test-Path $script)) { throw "not found: $script" }

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '03:17'

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

try { Unregister-ScheduledTask -TaskName $name -Confirm:$false } catch {}

Register-ScheduledTask `
    -TaskName $name `
    -Description 'Weekly crawl of newly posted NLAA road results for Finish Line Forecast. One request a second, identifying user agent, nothing committed. Pauses around live races.' `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings | Out-Null

$task = Get-ScheduledTask -TaskName $name
Write-Host "registered: $($task.TaskName)  state $($task.State)"
Write-Host "next run:   $((Get-ScheduledTaskInfo -TaskName $name).NextRunTime)"

