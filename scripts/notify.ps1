# A Windows notification when a scheduled task fails, dot-sourced by the three task scripts.
#
# The log alone was not enough: on 2026-10-03 the morning task failed to tag the Turkey Tea's
# final file, wrote "failed" to data/cache/freeze/predictions.log, and nobody read it for five
# days (PLAN.md 13 item 45). The tasks run in Peter's own session (LogonType Interactive), so a
# toast reaches the screen, and one shown while nobody is there waits in the notification
# centre. Showing it must never be what makes a task fail, so any error here is swallowed.

function Send-FailureNotice([string]$task, [string]$detail) {
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
            [Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $text = $template.GetElementsByTagName('text')
        $text.Item(0).AppendChild($template.CreateTextNode("FinishLine: $task failed")) | Out-Null
        $text.Item(1).AppendChild($template.CreateTextNode($detail)) | Out-Null
        $toast = [Windows.UI.Notifications.ToastNotification]::new($template)
        # Keep it in the notification centre for a week, not the default few days.
        $toast.ExpirationTime = [DateTimeOffset]::Now.AddDays(7)
        # Windows PowerShell's own app id, so the toast needs no app registered for it.
        $app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($toast)
    } catch {}
}
