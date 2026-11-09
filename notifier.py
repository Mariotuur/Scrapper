"""
notifier.py - Windows desktop notification manager
Delivers non-blocking toast/balloon notifications when new matching news is detected.
"""

import subprocess
import threading
import sys
import os
from typing import List, Dict, Any


def send_windows_notification_async(title: str, message: str):
    """Fires a Windows tray notification via PowerShell in a background thread."""
    def _run():
        try:
            # Escape single quotes for PowerShell
            safe_title = title.replace("'", "''").replace("\n", " ")
            safe_message = message.replace("'", "''").replace("\n", " ")

            ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.BalloonTipTitle = '{safe_title}'
$notify.BalloonTipText = '{safe_message}'
$notify.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
$notify.Visible = $True
$notify.ShowBalloonTip(5000)
Start-Sleep -Milliseconds 2500
$notify.Dispose()
"""
            # Run PowerShell silently without popup window
            startupinfo = None
            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                creationflags=creationflags,
                capture_output=True,
                timeout=10
            )
        except Exception as e:
            # Notifications shouldn't break the scanner
            print(f"[Notifier] Notification error: {e}")

    t = threading.Thread(target=_run, daemon=True, name="NotifierThread")
    t.start()


def notify_new_articles(new_articles: List[Dict[str, Any]], keyword: str = ""):
    """Dispatches a notification summarizing new articles discovered."""
    if not new_articles:
        return

    count = len(new_articles)
    first_art = new_articles[0]
    art_title = first_art.get("title", "")
    art_source = first_art.get("source", "")
    kw = keyword or first_art.get("keyword_matched") or first_art.get("keyword") or "News"

    if count == 1:
        notif_title = f"📰 New '{kw}' Article"
        notif_msg = f"{art_title} ({art_source})"
    else:
        notif_title = f"📰 {count} New Articles for '{kw}'"
        notif_msg = f"Latest: {art_title} ({art_source}) + {count - 1} more"

    # Truncate if too long for Windows balloon limit
    if len(notif_msg) > 200:
        notif_msg = notif_msg[:197] + "..."

    send_windows_notification_async(notif_title, notif_msg)
