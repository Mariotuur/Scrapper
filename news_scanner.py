"""
news_scanner.py - Core news fetching and keyword matching engine.
Supports Google News RSS (unlimited, global, real-time), Reddit, Hacker News,
with website and source domain filtering.
"""

import urllib.request
import urllib.parse
import json
import re
import html
import unicodedata
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


def clean_website_name(web: str) -> str:
    """Cleans a website/source name or URL, stripping protocol, www, and trailing slashes."""
    if not web:
        return ""
    w = web.strip().lower()
    w = re.sub(r"^https?://", "", w)
    w = re.sub(r"^www\.", "", w)
    w = w.rstrip("/")
    return w


def normalize_text(text: str) -> str:
    """Lowercases and removes accents/diacritics and non-alphanumeric characters for fuzzy matching."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    ascii_text = ''.join([c for c in nfkd if not unicodedata.combining(c)])
    return re.sub(r'[^a-zA-Z0-9]', '', ascii_text.lower())


def matches_website_filter(article: Dict[str, Any], websites: Optional[List[str]]) -> bool:
    """
    Checks if an article matches any of the specified target websites/sources.
    Supports domain names (e.g. 'elpais.com', 'bbc.co.uk'), source titles (e.g. 'El País', 'BBC News'),
    or short names (e.g. 'elpais', 'reuters').
    """
    if not websites:
        return True

    clean_filters = [clean_website_name(w) for w in websites if w and w.strip()]
    if not clean_filters:
        return True

    source_title = (article.get("source") or "").lower()
    source_url = (article.get("source_url") or "").lower()
    link = (article.get("link") or "").lower()

    source_norm = normalize_text(article.get("source", ""))
    url_norm = normalize_text(article.get("source_url", ""))

    for f in clean_filters:
        f_norm = normalize_text(f)
        f_domain = f.split("/")[0]
        f_name = f_domain.split(".")[0] if "." in f_domain else f_domain

        # 1. Domain match in source URL or link
        if f_domain and (f_domain in source_url or f_domain in link):
            return True

        # 2. Match in source title (e.g. "El País", "BBC News")
        if f in source_title or f_name in source_title:
            return True

        # 3. Normalized fuzzy comparison (handles accents e.g. "elpais" vs "el país")
        if f_norm and (f_norm in source_norm or source_norm in f_norm):
            return True

        # 4. Domain stem match (e.g. 'elpais' in cincodias.elpais.com)
        if f_name and len(f_name) >= 3 and (f_name in url_norm or f_name in source_norm):
            return True

    return False


def build_google_news_query(keyword: str, websites: Optional[List[str]] = None) -> str:
    """
    Constructs a Google News search query with website/source domain restrictions.
    """
    cleaned_kw = keyword.strip()
    if not websites:
        return cleaned_kw

    clean_webs = [clean_website_name(w) for w in websites if w and w.strip()]
    if not clean_webs:
        return cleaned_kw

    site_terms = []
    for w in clean_webs:
        if "." in w:
            site_terms.append(f"site:{w}")
        else:
            w_nospace = re.sub(r"\s+", "", w)
            site_terms.append(f'(site:{w_nospace}.com OR site:{w_nospace}.es OR "{w}")')

    if len(site_terms) == 1:
        return f"{cleaned_kw} {site_terms[0]}"
    else:
        combined = " OR ".join(site_terms)
        return f"{cleaned_kw} ({combined})"


class NewsScanner:
    def __init__(self, region_language: str = "en-US", websites: Optional[List[str]] = None):
        self.region_language = region_language
        self.websites = [w.strip() for w in websites if w and w.strip()] if websites else []

    def _parse_google_entries(self, entries, keyword: str, target_webs: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Parses and filters Google News feed entries."""
        articles = []
        for entry in entries:
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
            if snippet == raw_title or snippet == clean_title:
                snippet = f"Latest report from {source_title} regarding '{keyword}'."

            art = {
                "keyword": keyword,
                "title": clean_title,
                "link": link,
                "source": source_title,
                "source_url": source_url,
                "snippet": snippet,
                "published_at": published_at
            }

            if matches_website_filter(art, target_webs):
                articles.append(art)

        return articles

    def fetch_google_news(
        self,
        keyword: str,
        websites: Optional[List[str]] = None,
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetches news from Google News RSS using keyword query and optional website filters.
        Returns parsed list of article dicts.
        """
        target_webs = websites if websites is not None else self.websites
        target_webs = [w.strip() for w in target_webs if w and w.strip()] if target_webs else []

        # Region and language parameters
        parts = self.region_language.split("-")
        lang = parts[0] if len(parts) > 0 else "en"
        country = parts[1] if len(parts) > 1 else "US"

        # 1. Primary targeted query (with site filter if specified)
        search_query = build_google_news_query(keyword, target_webs)
        encoded_query = urllib.parse.quote(search_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl={lang}-{country}&gl={country}&ceid={country}:{lang}"

        articles = []
        try:
            req = urllib.request.Request(rss_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as response:
                content = response.read()

            feed = feedparser.parse(content)
            articles = self._parse_google_entries(feed.entries[:max_results], keyword, target_webs)

            # 2. Fallback: if website filter was active but targeted query yielded 0 results,
            # query Google News with just the keyword and post-filter by source/url to catch any edge cases
            if not articles and target_webs:
                plain_encoded = urllib.parse.quote(keyword)
                fallback_url = f"https://news.google.com/rss/search?q={plain_encoded}&hl={lang}-{country}&gl={country}&ceid={country}:{lang}"
                req_fb = urllib.request.Request(fallback_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req_fb, timeout=12) as response_fb:
                    feed_fb = feedparser.parse(response_fb.read())
                articles = self._parse_google_entries(feed_fb.entries[:max_results], keyword, target_webs)

        except Exception as e:
            print(f"[NewsScanner] Error fetching Google News for '{keyword}': {e}")

        return articles

    def fetch_reddit_news(
        self,
        keyword: str,
        websites: Optional[List[str]] = None,
        max_results: int = 15
    ) -> List[Dict[str, Any]]:
        """Fetches recent discussions/news from Reddit RSS if Reddit matches website filters."""
        target_webs = websites if websites is not None else self.websites
        target_webs = [w.strip() for w in target_webs if w and w.strip()] if target_webs else []

        # If websites are filtered and Reddit is not among them, skip Reddit
        if target_webs:
            reddit_match = any("reddit" in clean_website_name(w) for w in target_webs)
            if not reddit_match:
                return []

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

                art = {
                    "keyword": keyword,
                    "title": title,
                    "link": link,
                    "source": "Reddit",
                    "source_url": "https://www.reddit.com",
                    "snippet": snippet or f"Discussion thread on Reddit matching '{keyword}'.",
                    "published_at": published_at
                }
                if matches_website_filter(art, target_webs):
                    articles.append(art)
        except Exception as e:
            print(f"[NewsScanner] Error fetching Reddit for '{keyword}': {e}")

        return articles

    def fetch_hackernews(
        self,
        keyword: str,
        websites: Optional[List[str]] = None,
        max_results: int = 15
    ) -> List[Dict[str, Any]]:
        """Fetches tech news from Hacker News Algolia search API if HN matches website filters."""
        target_webs = websites if websites is not None else self.websites
        target_webs = [w.strip() for w in target_webs if w and w.strip()] if target_webs else []

        # If websites are filtered and Hacker News / YCombinator is not among them, skip HN
        if target_webs:
            hn_match = any(
                "hackernews" in clean_website_name(w) or
                "hacker" in clean_website_name(w) or
                "ycombinator" in clean_website_name(w)
                for w in target_webs
            )
            if not hn_match:
                return []

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

                art = {
                    "keyword": keyword,
                    "title": title,
                    "link": link,
                    "source": "Hacker News",
                    "source_url": "https://news.ycombinator.com",
                    "snippet": f"Score: {points} points | Author: {author} | Hacker News discussion",
                    "published_at": parse_rfc822_date(created_at)
                }
                if matches_website_filter(art, target_webs):
                    articles.append(art)
        except Exception as e:
            print(f"[NewsScanner] Error fetching Hacker News for '{keyword}': {e}")

        return articles

    def scan_for_keywords(
        self,
        keywords: List[str],
        websites: Optional[List[str]] = None,
        include_reddit: bool = False,
        include_hackernews: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Scans all specified keywords across enabled news providers with optional website filters.
        Returns aggregated list of discovered articles.
        """
        target_webs = websites if websites is not None else self.websites
        all_results = []

        for kw in keywords:
            cleaned_kw = kw.strip()
            if not cleaned_kw:
                continue

            # 1. Primary: Google News
            google_articles = self.fetch_google_news(cleaned_kw, websites=target_webs)
            all_results.extend(google_articles)

            # 2. Optional: Reddit
            if include_reddit:
                reddit_articles = self.fetch_reddit_news(cleaned_kw, websites=target_webs)
                all_results.extend(reddit_articles)

            # 3. Optional: Hacker News
            if include_hackernews:
                hn_articles = self.fetch_hackernews(cleaned_kw, websites=target_webs)
                all_results.extend(hn_articles)

        return all_results
