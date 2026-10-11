# Register (or re-register) the final-file check with Windows Task Scheduler.
#
#     powershell -File scripts\register-final-check-task.ps1
#
# To see it:     Get-ScheduledTask -TaskName 'FinishLine final file check'
# To remove it:  Unregister-ScheduledTask -TaskName 'FinishLine final file check' -Confirm:$false
#
# It runs at 07:00 local every day and does nothing unless a final file is due that morning
# (scripts/check-final-tag.ps1). 07:00 is after the 06:15 prediction task has had time to
# sample, write, tag and push, and an hour before an 8 am gun's deadline.

$ErrorActionPreference = 'Stop'

$name = 'FinishLine final file check'
$root = Split-Path -Parent $PSScriptRoot
$script = Join-Path $root 'scripts\check-final-tag.ps1'

if (-not (Test-Path $script)) { throw "not found: $script" }

$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -Daily -At '07:00'

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

try { Unregister-ScheduledTask -TaskName $name -Confirm:$false } catch {}

Register-ScheduledTask `
    -TaskName $name `
    -Description 'The Whole Field, Called Before the Gun: on the morning a final prediction file is due, says whether its tag reached GitHub. Reads only; does nothing on any other day.' `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings | Out-Null

$task = Get-ScheduledTask -TaskName $name
Write-Host "registered: $($task.TaskName)  state $($task.State)"
Write-Host "next run:   $((Get-ScheduledTaskInfo -TaskName $name).NextRunTime)"
