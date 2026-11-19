"""
scheduler.py - Background timer and orchestrator for news scanning.
Periodically fetches news for active keywords and active website filters, detects new articles,
notifies the user, and broadcasts real-time updates to connected clients.
"""

import threading
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import queue

import database
from news_scanner import NewsScanner
import notifier


class NewsScheduler:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._scan_trigger_event = threading.Event()
        self._lock = threading.Lock()

        self.is_scanning = False
        self.last_scan_time: Optional[str] = None
        self.next_scan_time: Optional[str] = None
        self.status_message = "Ready"

        # Event queues for Server-Sent Events (SSE) to update web UI in real time
        self._subscribers: List[queue.Queue] = []
        self._subscribers_lock = threading.Lock()

    def start(self):
        """Starts the background timer thread if not already running."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="NewsSchedulerThread")
            self._thread.start()
            print("[Scheduler] Background news monitor started.")

    def stop(self):
        """Stops the background scheduler."""
        with self._lock:
            self._stop_event.set()
            self._scan_trigger_event.set()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=3)
            print("[Scheduler] News monitor stopped.")

    def trigger_immediate_scan(self) -> bool:
        """Triggers an immediate scan without waiting for the timer."""
        if self.is_scanning:
            return False
        self._scan_trigger_event.set()
        return True

    def get_status(self) -> Dict[str, Any]:
        """Returns the current scheduler execution status."""
        settings = database.get_settings()
        interval_min = int(settings.get("refresh_interval_minutes", "10"))

        remaining_seconds = 0
        if self.next_scan_time:
            try:
                next_dt = datetime.fromisoformat(self.next_scan_time)
                diff = (next_dt - datetime.now()).total_seconds()
                remaining_seconds = max(0, int(diff))
            except Exception:
                remaining_seconds = interval_min * 60

        active_websites = database.get_websites(active_only=True)
        web_list = [w["name"] for w in active_websites]

        return {
            "is_scanning": self.is_scanning,
            "status_message": self.status_message,
            "last_scan_time": self.last_scan_time,
            "next_scan_time": self.next_scan_time,
            "remaining_seconds": remaining_seconds,
            "refresh_interval_minutes": interval_min,
            "active_websites": web_list,
            "active_websites_count": len(web_list)
        }

    def subscribe_events(self) -> queue.Queue:
        """Subscribes an event queue for live Server-Sent Events (SSE)."""
        q = queue.Queue(maxsize=50)
        with self._subscribers_lock:
            self._subscribers.append(q)
        return q

    def unsubscribe_events(self, q: queue.Queue):
        """Removes an SSE subscriber queue."""
        with self._subscribers_lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _broadcast_event(self, event_type: str, data: Any):
        """Broadcasts an event message to all connected web clients."""
        payload = {"event": event_type, "data": data}
        with self._subscribers_lock:
            dead_queues = []
            for q in self._subscribers:
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    dead_queues.append(q)
            for dq in dead_queues:
                if dq in self._subscribers:
                    self._subscribers.remove(dq)

    def execute_scan(self) -> Dict[str, Any]:
        """Performs a full scan across all active keywords with active website filters."""
        if self.is_scanning:
            return {"status": "busy", "message": "Scan already in progress"}

        self.is_scanning = True
        self.status_message = "Scanning news sources..."

        settings = database.get_settings()
        include_reddit = settings.get("enable_reddit", "false").lower() == "true"
        include_hn = settings.get("enable_hackernews", "false").lower() == "true"
        region_lang = settings.get("region_language", "en-US")
        enable_notif = settings.get("enable_windows_notifications", "true").lower() == "true"

        active_keywords = database.get_keywords(active_only=True)
        kw_list = [k["keyword"] for k in active_keywords]

        active_websites = database.get_websites(active_only=True)
        web_list = [w["name"] for w in active_websites]

        scan_info = {
            "message": "Scanning for updates...",
            "keywords": kw_list,
            "websites": web_list
        }
        self._broadcast_event("scan_started", scan_info)

        if not kw_list:
            self.is_scanning = False
            self.last_scan_time = datetime.now().isoformat()
            self.status_message = "Idle (no active keywords)"
            self._broadcast_event("scan_finished", {
                "new_count": 0,
                "total_found": 0,
                "message": "No active keywords to track."
            })
            return {"status": "empty", "message": "No active keywords tracked", "new_count": 0}

        scanner = NewsScanner(region_language=region_lang, websites=web_list)
        all_new_articles = []
        total_discovered = 0

        try:
            for kw in kw_list:
                status_kw_msg = f"Scanning for '{kw}'"
                if web_list:
                    status_kw_msg += f" on {', '.join(web_list)}"
                self.status_message = f"{status_kw_msg}..."
                self._broadcast_event("scanning_keyword", {"keyword": kw, "websites": web_list})

                articles = scanner.scan_for_keywords(
                    [kw],
                    websites=web_list,
                    include_reddit=include_reddit,
                    include_hackernews=include_hn
                )
                total_discovered += len(articles)

                # Save batch and collect genuinely new items
                new_saved = database.save_articles(articles)
                if new_saved:
                    all_new_articles.extend(new_saved)
                    if enable_notif:
                        notifier.notify_new_articles(new_saved, keyword=kw)

            now_iso = datetime.now().isoformat()
            self.last_scan_time = now_iso
            new_count = len(all_new_articles)

            database.log_scan_event(
                keywords=kw_list,
                found=total_discovered,
                new_count=new_count,
                websites=web_list,
                status="success",
                message=f"Found {total_discovered} items, {new_count} new"
            )

            status_done = f"Completed. Found {new_count} new article(s)."
            if web_list:
                status_done += f" (Filtered to: {', '.join(web_list)})"
            self.status_message = status_done

            self._broadcast_event("scan_finished", {
                "new_count": new_count,
                "total_found": total_discovered,
                "new_articles": all_new_articles[:10],
                "last_scan_time": now_iso,
                "websites": web_list
            })

            return {
                "status": "success",
                "keywords_scanned": kw_list,
                "websites_scanned": web_list,
                "total_found": total_discovered,
                "new_count": new_count
            }

        except Exception as e:
            err_msg = str(e)
            print(f"[Scheduler] Error during scan: {err_msg}")
            database.log_scan_event(
                keywords=kw_list,
                found=total_discovered,
                new_count=len(all_new_articles),
                websites=web_list,
                status="error",
                message=err_msg
            )
            self.status_message = f"Error during scan: {err_msg}"
            self._broadcast_event("scan_error", {"error": err_msg})
            return {"status": "error", "message": err_msg}

        finally:
            self.is_scanning = False

    def _run_loop(self):
        """Continuous background timer loop."""
        # Initial scan on startup after 3 seconds
        time.sleep(3)
        if not self._stop_event.is_set():
            self.execute_scan()

        while not self._stop_event.is_set():
            settings = database.get_settings()
            try:
                interval_minutes = max(1, int(settings.get("refresh_interval_minutes", "10")))
            except Exception:
                interval_minutes = 10

            next_dt = datetime.now() + timedelta(minutes=interval_minutes)
            self.next_scan_time = next_dt.isoformat()

            # Wait in small increments or until manual trigger/stop event
            interval_seconds = interval_minutes * 60
            start_wait = time.time()

            while not self._stop_event.is_set():
                elapsed = time.time() - start_wait
                if elapsed >= interval_seconds:
                    break
                # Check for manual trigger with 1-second resolution
                if self._scan_trigger_event.wait(timeout=1.0):
                    self._scan_trigger_event.clear()
                    break

            if self._stop_event.is_set():
                break

            # Execute scheduled scan
            self.execute_scan()


# Global scheduler singleton
scheduler = NewsScheduler()
