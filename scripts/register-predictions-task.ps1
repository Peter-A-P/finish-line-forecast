# Register (or re-register) the daily prediction run with Windows Task Scheduler.
#
#     powershell -File scripts\register-predictions-task.ps1
#
# To see it:     Get-ScheduledTask -TaskName 'FinishLine daily predictions'
# To remove it:  Unregister-ScheduledTask -TaskName 'FinishLine daily predictions' -Confirm:$false
#
# ⚠️ It runs at 06:15 local, so the final file on the day before an 8 am gun is tagged with
# more than 24 hours to spare even when the first run of the week has to sample the model
# (about 40 minutes). WakeToRun and StartWhenAvailable, because a day missed in the
# prediction week is a day of entrants published late, and the final file cannot be late at
# all. The daily snapshot task still runs in the evening; this one takes its own look first.

$ErrorActionPreference = 'Stop'

$name = 'FinishLine daily predictions'
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root 'scripts\daily-predictions.ps1'

if (-not (Test-Path $script)) { throw "not found: $script" }

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -Daily -At '06:15'

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew

try { Unregister-ScheduledTask -TaskName $name -Confirm:$false } catch {}

Register-ScheduledTask `
    -TaskName $name `
    -Description 'The Whole Field, Called Before the Gun, prediction week: snapshot the entrant list, freeze the daily or final prediction file, render the race page, commit, tag and push. Does nothing outside a prediction week.' `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings | Out-Null

$task = Get-ScheduledTask -TaskName $name
Write-Host "registered: $($task.TaskName)  state $($task.State)"
Write-Host "next run:   $((Get-ScheduledTaskInfo -TaskName $name).NextRunTime)"
