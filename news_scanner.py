"""
news_scanner.py - Core news fetching and keyword matching engine.
Supports Google News RSS (unlimited, global, real-time), Reddit, Hacker News, and Custom RSS feeds.
"""

import urllib.request
import urllib.parse
import json
import re
import html
import email.utils
from datetime import datetime
from typing import List, Dict, Any, Optional
import feedparser

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 NewsScanner/2.0"


def clean_html(raw_html: str) -> str:
    """Strips HTML tags and decodes entities."""
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    clean = html.unescape(clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def parse_rfc822_date(date_str: str) -> str:
    """Parses standard RSS RFC 822 or ISO dates into ISO format string."""
    if not date_str:
        return datetime.now().isoformat()
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        return dt.isoformat()
    except Exception:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).isoformat()
        except Exception:
            return datetime.now().isoformat()


def extract_keywords_from_query(query: str) -> List[str]:
    """Extracts individual words and quoted phrases from a search query for highlighting."""
    phrases = re.findall(r'"([^"]+)"', query)
    unquoted = re.sub(r'"[^"]+"', ' ', query)
    tokens = [w.strip() for w in re.split(r'[\s,]+', unquoted) if w.strip() and w.upper() not in ("AND", "OR", "NOT")]
    all_terms = list(dict.fromkeys(phrases + tokens))
    return [t for t in all_terms if len(t) > 1]


def contains_keyword(text: str, keyword: str) -> bool:
    """Checks if keyword or phrase is present in text (case-insensitive)."""
    if not text or not keyword:
        return False
    lower_text = text.lower()
    lower_kw = keyword.lower().strip('"')
    
    # If phrase
    if " " in lower_kw:
        return lower_kw in lower_text
        
    # Single word - check word boundary or substring
    pattern = r'\b' + re.escape(lower_kw) + r'\b'
    return bool(re.search(pattern, lower_text, re.IGNORECASE)) or lower_kw in lower_text


class NewsScanner:
    def __init__(self, region_language: str = "en-US"):
        self.region_language = region_language

    def fetch_google_news(self, keyword: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Fetches news from Google News RSS using keyword query.
        Returns parsed list of article dicts.
        """
        articles = []
        encoded_query = urllib.parse.quote(keyword)
        
        # Region and language parameters
        parts = self.region_language.split("-")
        lang = parts[0] if len(parts) > 0 else "en"
        country = parts[1] if len(parts) > 1 else "US"

        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl={lang}-{country}&gl={country}&ceid={country}:{lang}"

        try:
            req = urllib.request.Request(rss_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as response:
                content = response.read()

            feed = feedparser.parse(content)

            for entry in feed.entries[:max_results]:
                raw_title = clean_html(entry.get("title", ""))
                link = entry.get("link", "")
                pub_date_str = entry.get("published", "")
                published_at = parse_rfc822_date(pub_date_str)

                # Extract source and clean headline
                source_title = getattr(entry, "source", {}).get("title", "")
                source_url = getattr(entry, "source", {}).get("url", "")

                clean_title = raw_title
                if not source_title and " - " in raw_title:
                    parts = raw_title.rsplit(" - ", 1)
                    clean_title = parts[0].strip()
                    source_title = parts[1].strip()
                elif source_title and raw_title.endswith(f" - {source_title}"):
                    clean_title = raw_title[:-len(f" - {source_title}")].strip()

                if not source_title:
                    source_title = "Google News"

                snippet = clean_html(entry.get("summary", ""))
                # If summary is just link and source, create clean snippet from title
                if snippet == raw_title or snippet == clean_title:
                    snippet = f"Latest report from {source_title} regarding '{keyword}'."

                articles.append({
                    "keyword": keyword,
                    "title": clean_title,
                    "link": link,
                    "source": source_title,
                    "source_url": source_url,
                    "snippet": snippet,
                    "published_at": published_at
                })

        except Exception as e:
            print(f"[NewsScanner] Error fetching Google News for '{keyword}': {e}")

        return articles

    def fetch_reddit_news(self, keyword: str, max_results: int = 15) -> List[Dict[str, Any]]:
        """Fetches recent discussions/news from Reddit RSS."""
        articles = []
        encoded = urllib.parse.quote(keyword)
        rss_url = f"https://www.reddit.com/search.rss?q={encoded}&sort=new"

        try:
            req = urllib.request.Request(rss_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read()

            feed = feedparser.parse(content)
            for entry in feed.entries[:max_results]:
                title = clean_html(entry.get("title", ""))
                link = entry.get("link", "")
                published_at = parse_rfc822_date(entry.get("published", ""))
                snippet = clean_html(entry.get("summary", ""))[:300]

                articles.append({
                    "keyword": keyword,
                    "title": title,
                    "link": link,
                    "source": "Reddit",
                    "source_url": "https://www.reddit.com",
                    "snippet": snippet or f"Discussion thread on Reddit matching '{keyword}'.",
                    "published_at": published_at
                })
        except Exception as e:
            print(f"[NewsScanner] Error fetching Reddit for '{keyword}': {e}")

        return articles

    def fetch_hackernews(self, keyword: str, max_results: int = 15) -> List[Dict[str, Any]]:
        """Fetches tech news from Hacker News Algolia search API."""
        articles = []
        encoded = urllib.parse.quote(keyword)
        api_url = f"https://hn.algolia.com/api/v1/search_by_date?query={encoded}&tags=story&hitsPerPage={max_results}"

        try:
            req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))

            hits = data.get("hits", [])
            for hit in hits:
                title = hit.get("title", "")
                link = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                created_at = hit.get("created_at", "")
                points = hit.get("points") or 0
                author = hit.get("author", "anonymous")

                articles.append({
                    "keyword": keyword,
                    "title": title,
                    "link": link,
                    "source": "Hacker News",
                    "source_url": "https://news.ycombinator.com",
                    "snippet": f"Score: {points} points | Author: {author} | Hacker News discussion",
                    "published_at": parse_rfc822_date(created_at)
                })
        except Exception as e:
            print(f"[NewsScanner] Error fetching Hacker News for '{keyword}': {e}")

        return articles

    def scan_for_keywords(
        self,
        keywords: List[str],
        include_reddit: bool = False,
        include_hackernews: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Scans all specified keywords across enabled news providers.
        Returns aggregated list of discovered articles.
        """
        all_results = []
        for kw in keywords:
            cleaned_kw = kw.strip()
            if not cleaned_kw:
                continue

            # 1. Primary: Google News
            google_articles = self.fetch_google_news(cleaned_kw)
            all_results.extend(google_articles)

            # 2. Optional: Reddit
            if include_reddit:
                reddit_articles = self.fetch_reddit_news(cleaned_kw)
                all_results.extend(reddit_articles)

            # 3. Optional: Hacker News
            if include_hackernews:
                hn_articles = self.fetch_hackernews(cleaned_kw)
                all_results.extend(hn_articles)

        return all_results
