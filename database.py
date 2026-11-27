"""
database.py - SQLite storage engine for News Monitor
Manages keywords, target website filters, discovered articles, user preferences, scan history,
and instantly outputs detected links to news_links.txt.
"""

import sqlite3
import os
import json
import hashlib
import re
import email.utils
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news_monitor.db")
LINKS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news_links.txt")


def is_within_max_age(date_str: str, max_age_days: int = 30) -> bool:
    """
    Checks if an article's published date is within the allowed maximum age (e.g. 30 days).
    Returns True if the article is within the age limit (or if max_age_days is 0/disabled).
    Returns False if the article is older than max_age_days.
    """
    if not date_str or max_age_days <= 0:
        return True
    try:
        clean_str = date_str.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(clean_str)
        except Exception:
            dt = email.utils.parsedate_to_datetime(date_str)

        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        diff = now - dt
        if diff.total_seconds() > max_age_days * 86400:
            return False
        return True
    except Exception:
        return True


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_links_file():
    """Initializes news_links.txt if it does not exist."""
    if not os.path.exists(LINKS_FILE_PATH):
        try:
            with open(LINKS_FILE_PATH, "w", encoding="utf-8") as f:
                f.write("# ========================================================\n")
                f.write("#  News Monitor - Detected Article Links\n")
                f.write("#  Newly detected news links are instantly appended below\n")
                f.write("# ========================================================\n\n")
        except Exception as e:
            print(f"[Database] Error initializing news_links.txt: {e}")


def append_links_to_file(new_articles: List[Dict[str, Any]]):
    """
    Instantly appends the links of newly discovered articles to news_links.txt.
    Supports both detailed (timestamp, keyword, title, link) and plain (URL only) formats.
    """
    if not new_articles:
        return

    try:
        init_links_file()
        format_mode = get_setting("links_file_format", "detailed")  # "detailed" or "plain"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = []
        for art in new_articles:
            link = art.get("link", "").strip()
            if not link:
                continue

            if format_mode == "plain":
                lines.append(f"{link}\n")
            else:
                kw = art.get("keyword_matched") or art.get("keyword") or "News"
                title = art.get("title", "Untitled").strip()
                source = art.get("source", "Web").strip()
                lines.append(f"[{now_str}] [{kw}] {title} ({source})\n{link}\n\n")

        if lines:
            with open(LINKS_FILE_PATH, "a", encoding="utf-8") as f:
                f.writelines(lines)
                f.flush()
    except Exception as e:
        print(f"[Database] Error writing to news_links.txt: {e}")


def get_links_file_path() -> str:
    """Returns the absolute path to news_links.txt."""
    return LINKS_FILE_PATH


def get_links_file_content() -> str:
    """Reads and returns the contents of news_links.txt."""
    init_links_file()
    try:
        with open(LINKS_FILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading news_links.txt: {e}"


def clear_links_file():
    """Clears the contents of news_links.txt and re-initializes the header."""
    try:
        with open(LINKS_FILE_PATH, "w", encoding="utf-8") as f:
            f.write("# ========================================================\n")
            f.write("#  News Monitor - Detected Article Links\n")
            f.write("#  Newly detected news links are instantly appended below\n")
            f.write("# ========================================================\n\n")
    except Exception as e:
        print(f"[Database] Error resetting news_links.txt: {e}")


def init_db():
    """Initializes tables with proper schema, indexes, and default settings."""
    init_links_file()
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Keywords table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL UNIQUE,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

        # Target Websites / Sources table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS websites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_websites_name ON websites(name)")

        # Articles table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guid_hash TEXT NOT NULL UNIQUE,
                keyword_matched TEXT NOT NULL,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                source TEXT NOT NULL,
                source_url TEXT,
                snippet TEXT,
                published_at TEXT,
                discovered_at TEXT NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                is_bookmarked INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Indexes for fast filtering and deduplication
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_guid ON articles(guid_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_keyword ON articles(keyword_matched)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_discovered ON articles(discovered_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_read ON articles(is_read)")

        # Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Scan activity logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                keywords_scanned TEXT NOT NULL,
                websites_scanned TEXT NOT NULL DEFAULT '',
                articles_found INTEGER NOT NULL,
                new_articles_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                message TEXT
            )
        """)

        # Migration: ensure websites_scanned column exists in existing scan_logs
        try:
            cursor.execute("ALTER TABLE scan_logs ADD COLUMN websites_scanned TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass

        # Default settings if not already set
        default_settings = {
            "refresh_interval_minutes": "10",
            "max_article_age_days": "30",
            "enable_windows_notifications": "true",
            "enable_sound": "true",
            "enable_reddit": "false",
            "enable_hackernews": "false",
            "region_language": "en-US",
            "auto_mark_read_on_open": "true",
            "links_file_format": "detailed"
        }

        for k, v in default_settings.items():
            cursor.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (k, v)
            )

        conn.commit()

    # Clean up any outdated articles older than max_age_days (preserving user bookmarks)
    purge_old_articles(30, preserve_bookmarks=True)


# ==================== KEYWORD OPERATIONS ====================

def add_keyword(keyword: str) -> Optional[int]:
    """Adds a new search keyword or phrase."""
    cleaned = keyword.strip()
    if not cleaned:
        return None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO keywords (keyword, is_active, created_at) VALUES (?, 1, ?)",
                (cleaned, now)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Keyword already exists, ensure it is active
            cursor.execute(
                "UPDATE keywords SET is_active = 1 WHERE LOWER(keyword) = LOWER(?)",
                (cleaned,)
            )
            conn.commit()
            return None


def get_keywords(active_only: bool = False) -> List[Dict[str, Any]]:
    """Retrieves all tracked keywords with article counts."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT k.id, k.keyword, k.is_active, k.created_at,
                   COUNT(a.id) AS article_count,
                   SUM(CASE WHEN a.is_read = 0 THEN 1 ELSE 0 END) AS unread_count
            FROM keywords k
            LEFT JOIN articles a ON LOWER(a.keyword_matched) = LOWER(k.keyword)
        """
        if active_only:
            query += " WHERE k.is_active = 1"
        query += " GROUP BY k.id ORDER BY k.created_at ASC"

        rows = cursor.execute(query).fetchall()
        return [
            {
                "id": r["id"],
                "keyword": r["keyword"],
                "is_active": bool(r["is_active"]),
                "created_at": r["created_at"],
                "article_count": r["article_count"] or 0,
                "unread_count": r["unread_count"] or 0
            }
            for r in rows
        ]


def delete_keyword(keyword_id: int):
    """Deletes a keyword."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
        conn.commit()


def toggle_keyword(keyword_id: int) -> bool:
    """Toggles active/paused state of a keyword."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT is_active FROM keywords WHERE id = ?", (keyword_id,)).fetchone()
        if not row:
            return False
        new_state = 0 if row["is_active"] else 1
        cursor.execute("UPDATE keywords SET is_active = ? WHERE id = ?", (new_state, keyword_id))
        conn.commit()
        return bool(new_state)


# ==================== WEBSITE FILTER OPERATIONS ====================

def clean_website_input(web: str) -> str:
    """Normalizes website input for database storage."""
    if not web:
        return ""
    w = web.strip()
    w = re.sub(r"^https?://", "", w, flags=re.IGNORECASE)
    w = re.sub(r"^www\.", "", w, flags=re.IGNORECASE)
    w = w.rstrip("/")
    return w


def add_website(website_name: str) -> Optional[int]:
    """Adds a new target website/domain to filter news searches."""
    cleaned = clean_website_input(website_name)
    if not cleaned:
        return None
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO websites (name, is_active, created_at) VALUES (?, 1, ?)",
                (cleaned, now)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Website filter already exists, ensure it is active
            cursor.execute(
                "UPDATE websites SET is_active = 1 WHERE LOWER(name) = LOWER(?)",
                (cleaned,)
            )
            conn.commit()
            return None


def get_websites(active_only: bool = False) -> List[Dict[str, Any]]:
    """Retrieves all tracked websites with matching article counts."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT id, name, is_active, created_at FROM websites"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY created_at ASC"

        rows = cursor.execute(query).fetchall()
        result = []
        for r in rows:
            w_name = r["name"].lower()
            # Match domain or source title
            count_row = cursor.execute("""
                SELECT COUNT(*) FROM articles
                WHERE LOWER(source) LIKE ? OR LOWER(source_url) LIKE ? OR LOWER(link) LIKE ?
            """, (f"%{w_name}%", f"%{w_name}%", f"%{w_name}%")).fetchone()
            result.append({
                "id": r["id"],
                "name": r["name"],
                "is_active": bool(r["is_active"]),
                "created_at": r["created_at"],
                "article_count": count_row[0] if count_row else 0
            })
        return result


def delete_website(website_id: int):
    """Deletes a website filter."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM websites WHERE id = ?", (website_id,))
        conn.commit()


def toggle_website(website_id: int) -> bool:
    """Toggles active/paused state of a website filter."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT is_active FROM websites WHERE id = ?", (website_id,)).fetchone()
        if not row:
            return False
        new_state = 0 if row["is_active"] else 1
        cursor.execute("UPDATE websites SET is_active = ? WHERE id = ?", (new_state, website_id))
        conn.commit()
        return bool(new_state)


# ==================== ARTICLE OPERATIONS ====================

def generate_article_hash(link: str, title: str) -> str:
    """Generates a stable unique hash for deduplication."""
    clean_target = (link or "").strip().lower() + "|" + (title or "").strip().lower()
    return hashlib.sha256(clean_target.encode("utf-8")).hexdigest()


def save_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Saves a batch of articles into the database.
    Skips duplicates and articles older than max_article_age_days (e.g. 30 days).
    Returns the list of genuinely NEW articles saved.
    Instantly appends new article links to news_links.txt.
    """
    if not articles:
        return []

    try:
        max_age_days = int(get_setting("max_article_age_days", "30"))
    except Exception:
        max_age_days = 30

    new_articles = []
    now = datetime.now().isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        for art in articles:
            # Skip articles older than the allowed max age (avoids news from years ago)
            pub_date = art.get("published_at", "")
            if pub_date and not is_within_max_age(pub_date, max_age_days):
                continue

            guid_hash = art.get("guid_hash") or generate_article_hash(art.get("link", ""), art.get("title", ""))
            try:
                cursor.execute("""
                    INSERT INTO articles (
                        guid_hash, keyword_matched, title, link, source,
                        source_url, snippet, published_at, discovered_at, is_read, is_bookmarked
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
                """, (
                    guid_hash,
                    art.get("keyword", "News"),
                    art.get("title", "Untitled"),
                    art.get("link", ""),
                    art.get("source", "Web"),
                    art.get("source_url", ""),
                    art.get("snippet", ""),
                    art.get("published_at", ""),
                    now
                ))
                new_art = dict(art)
                new_art["id"] = cursor.lastrowid
                new_art["discovered_at"] = now
                new_art["is_read"] = 0
                new_art["is_bookmarked"] = 0
                new_articles.append(new_art)
            except sqlite3.IntegrityError:
                # Already exists, skip
                pass

        conn.commit()

    # Instantly copy links of newly detected articles to news_links.txt
    if new_articles:
        append_links_to_file(new_articles)

    return new_articles


def get_articles(
    keyword: Optional[str] = None,
    website: Optional[str] = None,
    filter_type: str = "all",  # "all", "unread", "bookmarked"
    search_query: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """Retrieves articles with comprehensive filtering and pagination."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        where_clauses = []
        params = []

        if keyword and keyword.lower() != "all":
            where_clauses.append("LOWER(keyword_matched) = LOWER(?)")
            params.append(keyword)

        if website and website.lower() != "all":
            w = f"%{website.strip().lower()}%"
            where_clauses.append("(LOWER(source) LIKE ? OR LOWER(source_url) LIKE ? OR LOWER(link) LIKE ?)")
            params.extend([w, w, w])

        if filter_type == "unread":
            where_clauses.append("is_read = 0")
        elif filter_type == "bookmarked":
            where_clauses.append("is_bookmarked = 1")

        if search_query and search_query.strip():
            sq = f"%{search_query.strip().lower()}%"
            where_clauses.append("(LOWER(title) LIKE ? OR LOWER(snippet) LIKE ? OR LOWER(source) LIKE ?)")
            params.extend([sq, sq, sq])

        where_str = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Total count
        count_query = f"SELECT COUNT(*) FROM articles {where_str}"
        total_count = cursor.execute(count_query, params).fetchone()[0]

        # Fetch articles
        data_query = f"""
            SELECT id, guid_hash, keyword_matched, title, link, source,
                   source_url, snippet, published_at, discovered_at, is_read, is_bookmarked
            FROM articles
            {where_str}
            ORDER BY discovered_at DESC, id DESC
            LIMIT ? OFFSET ?
        """
        rows = cursor.execute(data_query, params + [limit, offset]).fetchall()

        articles = [dict(r) for r in rows]

        return {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "articles": articles
        }


def mark_article_read(article_id: int, is_read: bool = True):
    """Sets the read status of an article."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE articles SET is_read = ? WHERE id = ?", (1 if is_read else 0, article_id))
        conn.commit()


def mark_all_articles_read(keyword: Optional[str] = None):
    """Marks all matching articles as read."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if keyword and keyword.lower() != "all":
            cursor.execute("UPDATE articles SET is_read = 1 WHERE LOWER(keyword_matched) = LOWER(?)", (keyword,))
        else:
            cursor.execute("UPDATE articles SET is_read = 1")
        conn.commit()


def toggle_article_bookmark(article_id: int) -> bool:
    """Toggles bookmark state of an article."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT is_bookmarked FROM articles WHERE id = ?", (article_id,)).fetchone()
        if not row:
            return False
        new_val = 0 if row["is_bookmarked"] else 1
        cursor.execute("UPDATE articles SET is_bookmarked = ? WHERE id = ?", (new_val, article_id))
        conn.commit()
        return bool(new_val)


def delete_article(article_id: int):
    """Deletes a single article."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM articles WHERE id = ?", (article_id,))
        conn.commit()


def delete_articles_batch(article_ids: List[int]) -> int:
    """Deletes a list of articles by their IDs. Returns number of rows deleted."""
    if not article_ids:
        return 0
    with get_db_connection() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in article_ids)
        cursor.execute(f"DELETE FROM articles WHERE id IN ({placeholders})", article_ids)
        conn.commit()
        return cursor.rowcount


def clear_articles(only_unbookmarked: bool = False, keyword: Optional[str] = None) -> int:
    """Clears all stored articles (or preserves bookmarked ones if requested)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        clauses = []
        params = []
        if only_unbookmarked:
            clauses.append("is_bookmarked = 0")
        if keyword and keyword.lower() != "all":
            clauses.append("LOWER(keyword_matched) = LOWER(?)")
            params.append(keyword)

        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        cursor.execute(f"DELETE FROM articles {where_sql}", params)
        conn.commit()
        return cursor.rowcount


def purge_old_articles(max_age_days: int = 30, preserve_bookmarks: bool = True) -> int:
    """
    Deletes articles whose published_at date is older than max_age_days (e.g. 30 days).
    Preserves bookmarked articles if preserve_bookmarks is True.
    Returns number of deleted articles.
    """
    if max_age_days <= 0:
        return 0

    cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        if preserve_bookmarks:
            cursor.execute("""
                DELETE FROM articles 
                WHERE published_at < ? AND (is_bookmarked = 0 OR is_bookmarked IS NULL)
            """, (cutoff_iso,))
        else:
            cursor.execute("DELETE FROM articles WHERE published_at < ?", (cutoff_iso,))
        count = cursor.rowcount
        conn.commit()
        return count


def get_dashboard_stats() -> Dict[str, Any]:
    """Returns high-level statistics for the dashboard."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        total_articles = cursor.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        unread_articles = cursor.execute("SELECT COUNT(*) FROM articles WHERE is_read = 0").fetchone()[0]
        bookmarked_articles = cursor.execute("SELECT COUNT(*) FROM articles WHERE is_bookmarked = 1").fetchone()[0]
        active_keywords = cursor.execute("SELECT COUNT(*) FROM keywords WHERE is_active = 1").fetchone()[0]
        total_keywords = cursor.execute("SELECT COUNT(*) FROM keywords").fetchone()[0]
        active_websites = cursor.execute("SELECT COUNT(*) FROM websites WHERE is_active = 1").fetchone()[0]
        total_websites = cursor.execute("SELECT COUNT(*) FROM websites").fetchone()[0]

        last_scan = cursor.execute(
            "SELECT timestamp, status, new_articles_count FROM scan_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()

        return {
            "total_articles": total_articles,
            "unread_articles": unread_articles,
            "bookmarked_articles": bookmarked_articles,
            "active_keywords": active_keywords,
            "total_keywords": total_keywords,
            "active_websites": active_websites,
            "total_websites": total_websites,
            "last_scan_time": last_scan["timestamp"] if last_scan else None,
            "last_scan_status": last_scan["status"] if last_scan else "Never",
            "last_scan_new_count": last_scan["new_articles_count"] if last_scan else 0
        }


# ==================== SETTINGS OPERATIONS ====================

def get_settings() -> Dict[str, str]:
    """Returns all settings as a dict."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


def get_setting(key: str, default: str = "") -> str:
    """Returns a specific setting value."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def update_settings(settings_dict: Dict[str, Any]):
    """Updates one or more settings."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for k, v in settings_dict.items():
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (k, str(v))
            )
        conn.commit()


# ==================== SCAN LOGS OPERATIONS ====================

def log_scan_event(
    keywords: List[str],
    found: int,
    new_count: int,
    websites: Optional[List[str]] = None,
    status: str = "success",
    message: str = ""
):
    """Logs a scan execution event."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        webs_str = ", ".join(websites) if websites else "All"
        cursor.execute("""
            INSERT INTO scan_logs (timestamp, keywords_scanned, websites_scanned, articles_found, new_articles_count, status, message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (now, ", ".join(keywords), webs_str, found, new_count, status, message))
        conn.commit()


def get_recent_logs(limit: int = 20) -> List[Dict[str, Any]]:
    """Returns the most recent scan logs."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT * FROM scan_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ==================== TOPIC TREND ANALYTICS ====================

def get_analytics_data(keyword: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
    """
    Computes news volume trends over time, top sources, and key metrics
    for proving the media importance and momentum of a topic.
    """
    if days <= 0:
        days = 30

    now = datetime.now(timezone.utc)
    cutoff_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Build WHERE clause
        where_clauses = ["COALESCE(NULLIF(SUBSTR(published_at, 1, 10), ''), SUBSTR(discovered_at, 1, 10)) >= ?"]
        params = [cutoff_date]

        if keyword and keyword.lower() != "all":
            where_clauses.append("LOWER(keyword_matched) = LOWER(?)")
            params.append(keyword.strip())

        where_sql = "WHERE " + " AND ".join(where_clauses)

        # 1. Total articles count in period
        cursor.execute(f"SELECT COUNT(*) FROM articles {where_sql}", params)
        total_articles = cursor.fetchone()[0]

        # 2. Daily counts
        cursor.execute(f"""
            SELECT 
                COALESCE(NULLIF(SUBSTR(published_at, 1, 10), ''), SUBSTR(discovered_at, 1, 10)) as pub_day,
                COUNT(*) as count
            FROM articles
            {where_sql}
            GROUP BY pub_day
            ORDER BY pub_day ASC
        """, params)
        raw_daily = {row["pub_day"]: row["count"] for row in cursor.fetchall()}

        # Fill all dates in range
        daily_trends = []
        peak_day = {"date": None, "count": 0}
        for i in reversed(range(days + 1)):
            day_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            cnt = raw_daily.get(day_str, 0)
            daily_trends.append({"date": day_str, "count": cnt})
            if cnt > peak_day["count"]:
                peak_day = {"date": day_str, "count": cnt}

        # 3. Top sources
        cursor.execute(f"""
            SELECT source, COUNT(*) as count
            FROM articles
            {where_sql}
            GROUP BY source
            ORDER BY count DESC
            LIMIT 10
        """, params)
        top_sources = [{"source": row["source"], "count": row["count"]} for row in cursor.fetchall()]

        # 4. Keyword breakdown
        cursor.execute(f"""
            SELECT keyword_matched, COUNT(*) as count
            FROM articles
            {where_sql}
            GROUP BY keyword_matched
            ORDER BY count DESC
        """, params)
        keywords_breakdown = [{"keyword": row["keyword_matched"], "count": row["count"]} for row in cursor.fetchall()]

        # Distinct sources count
        cursor.execute(f"SELECT COUNT(DISTINCT source) FROM articles {where_sql}", params)
        distinct_sources = cursor.fetchone()[0]

        avg_per_day = round(total_articles / max(days, 1), 1)

        return {
            "keyword": keyword or "all",
            "days": days,
            "total_articles": total_articles,
            "distinct_sources": distinct_sources,
            "avg_per_day": avg_per_day,
            "peak_day": peak_day,
            "start_date": cutoff_date,
            "end_date": now.strftime("%Y-%m-%d"),
            "daily_trends": daily_trends,
            "top_sources": top_sources,
            "keywords_breakdown": keywords_breakdown
        }


# Initialize on import
init_db()
