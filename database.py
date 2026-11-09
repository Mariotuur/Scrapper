"""
database.py - SQLite storage engine for News Monitor
Manages keywords, discovered articles, user preferences, scan history,
and instantly outputs detected links to news_links.txt.
"""

import sqlite3
import os
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news_monitor.db")
LINKS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news_links.txt")


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

        # Index for fast filtering and deduplication
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_guid ON articles(guid_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_keyword ON articles(keyword_matched)")
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
                articles_found INTEGER NOT NULL,
                new_articles_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                message TEXT
            )
        """)

        # Default settings if not already set
        default_settings = {
            "refresh_interval_minutes": "10",
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
    """Deletes a keyword and optionally its untagged references."""
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


# ==================== ARTICLE OPERATIONS ====================

def generate_article_hash(link: str, title: str) -> str:
    """Generates a stable unique hash for deduplication."""
    clean_target = (link or "").strip().lower() + "|" + (title or "").strip().lower()
    return hashlib.sha256(clean_target.encode("utf-8")).hexdigest()


def save_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Saves a batch of articles into the database.
    Skips duplicates. Returns the list of genuinely NEW articles saved.
    Instantly appends new article links to news_links.txt.
    """
    if not articles:
        return []

    new_articles = []
    now = datetime.now().isoformat()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        for art in articles:
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


def clear_articles(only_unbookmarked: bool = True):
    """Clears article history. Preserves bookmarked articles by default."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if only_unbookmarked:
            cursor.execute("DELETE FROM articles WHERE is_bookmarked = 0")
        else:
            cursor.execute("DELETE FROM articles")
        conn.commit()


def get_dashboard_stats() -> Dict[str, Any]:
    """Returns high-level statistics for the dashboard."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        total_articles = cursor.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        unread_articles = cursor.execute("SELECT COUNT(*) FROM articles WHERE is_read = 0").fetchone()[0]
        bookmarked_articles = cursor.execute("SELECT COUNT(*) FROM articles WHERE is_bookmarked = 1").fetchone()[0]
        active_keywords = cursor.execute("SELECT COUNT(*) FROM keywords WHERE is_active = 1").fetchone()[0]
        total_keywords = cursor.execute("SELECT COUNT(*) FROM keywords").fetchone()[0]

        last_scan = cursor.execute(
            "SELECT timestamp, status, new_articles_count FROM scan_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()

        return {
            "total_articles": total_articles,
            "unread_articles": unread_articles,
            "bookmarked_articles": bookmarked_articles,
            "active_keywords": active_keywords,
            "total_keywords": total_keywords,
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

def log_scan_event(keywords: List[str], found: int, new_count: int, status: str = "success", message: str = ""):
    """Logs a scan execution event."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO scan_logs (timestamp, keywords_scanned, articles_found, new_articles_count, status, message)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (now, ", ".join(keywords), found, new_count, status, message))
        conn.commit()


def get_recent_logs(limit: int = 20) -> List[Dict[str, Any]]:
    """Returns the most recent scan logs."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT * FROM scan_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# Initialize on import
init_db()
