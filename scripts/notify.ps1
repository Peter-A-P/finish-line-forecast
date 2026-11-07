# A Windows notification when a scheduled task fails, dot-sourced by the four task scripts.
#
# The log alone was not enough: on 2026-10-03 the morning task failed to tag the Turkey Tea's
# final file, wrote "failed" to data/cache/freeze/predictions.log, and nobody read it for five
# days (PLAN.md 13 item 45). The tasks run in Peter's own session (LogonType Interactive), so a
# toast reaches the screen, and one shown while nobody is there waits in the notification
# centre. Showing it must never be what makes a task fail, so any error here is swallowed.

# ⚠️ **A toast alone was not seen either.** From 2026-11-04 to 2026-11-07 the morning task failed
# every day and raised a toast each time, at 05:15 with nobody at the screen, and Peter saw none
# of them: Run to Remember lost three daily files. So a failure now also leaves two things that
# wait for a person: a line in "FinishLine - action needed.txt" on the Desktop, and a message
# box that stays on the screen until it is closed. The box is shown by a separate process, so
# the task itself finishes and exits whether or not anyone is there to click it.
function Send-FailureNotice([string]$task, [string]$detail) {
    $title = "FinishLine: $task failed"
    Send-Notice $title $detail
    try {
        $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
        $desktop = [Environment]::GetFolderPath('Desktop')
        Add-Content -Path (Join-Path $desktop 'FinishLine - action needed.txt') -Encoding utf8 `
            -Value "$stamp  $title. $detail"
    } catch {}
    try {
        $message = ("$title at $(Get-Date -Format 'yyyy-MM-dd HH:mm').`n`n$detail`n`n" +
            "The same line is in 'FinishLine - action needed.txt' on the Desktop.") -replace "'", "''"
        $script = "Add-Type -AssemblyName PresentationFramework; " +
            "[System.Windows.MessageBox]::Show('$message', 'FinishLine', 'OK', 'Error') | Out-Null"
        # Encoded, because Start-Process joins its arguments with spaces and no quoting, which
        # cut a plain -Command apart at the first space and showed nothing.
        $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
        Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden `
            -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encoded) | Out-Null
    } catch {}
}

# Any notice, for the one task that also reports good news (scripts/check-final-tag.ps1).
function Send-Notice([string]$title, [string]$detail) {
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
            [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $text = $template.GetElementsByTagName('text')
        $text.Item(0).AppendChild($template.CreateTextNode($title)) | Out-Null
        $text.Item(1).AppendChild($template.CreateTextNode($detail)) | Out-Null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        # Keep it in the notification centre for a week, not the default few days.
        $toast.ExpirationTime = [DateTimeOffset]::Now.AddDays(7)
        # Windows PowerShell's own app id, so the toast needs no app registered for it.
        $app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($toast)
    } catch {}
}
