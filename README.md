# 📰 News Monitor - Local Internet Keyword & Website News Tracker

A local tool that continuously checks news across the internet matching any keywords or phrases you provide, automatically refreshing on a customizable background timer, with optional filtering by specific websites or news sources.

---

## ✨ Features

- **Global Internet News Coverage**: Powered by Google News RSS (covering BBC, CNN, Reuters, Bloomberg, TechCrunch, El País, local news, and blogs globally without requiring paid API keys) + optional Reddit & Hacker News sources.
- **🌐 Website & Source Filtering (New!)**:
  - Restrict your searches to specific websites, domains, or news sources (e.g. `elpais.com`, `bbc.co.uk`, `theverge.com`, `Reuters`).
  - Input domain names (`techcrunch.com`), source names (`El País`, `BBC News`), or domain stems (`elpais`).
  - Active toggle: pause or enable specific website filters with one click, or leave unfiltered to search the entire web.
- **Continuous Background Timer**: Refreshes automatically on a customizable timer (every 1, 5, 10, 15, 30, or 60 minutes).
- **Multiple Keywords & Phrases**: Track as many words/phrases as you want simultaneously (e.g. `"OpenAI"`, `"quantum computing"`, `"Ciberseguridad"`).
- **Phrase & Boolean Support**: Supports exact phrases (using quotes `"..."`), logical operators (`OR`, `AND`), and negative filters (`-term`).
- **Keyword Highlighting**: Matches are cleanly highlighted in headlines and snippet summaries.
- **Real-Time Live Updates (SSE)**: New news appears instantly on your screen without manual page reloading.
- **Dual Notification System**:
  - **Windows Desktop Toast/Balloon Alerts**: Pops up a native Windows notification when new articles are detected.
  - **Browser Notifications & Audio Chime**: Subtle synthesized sound alert and web notifications.
- **Instant Links Text File (`news_links.txt`)**: Newly detected news links are instantly appended into `news_links.txt` in real time as they are discovered.
- **Local SQLite Database**:
  - Automatically deduplicates articles (never alerts twice for the same story).
  - Keeps track of read/unread articles and bookmarks.
  - Saves your history, keywords, websites, and settings locally.
- **Exporting**: 1-click export of discovered articles to **CSV** or **JSON**.
- **CLI Mode Included**: Can also run in a terminal or PowerShell session with full keyword and website filtering.

---

## 🚀 Quick Start

### 1. Launch with One Click (Web UI)
Double-click **`run.bat`** in this folder, or run:

```bash
python app.py
```

This starts the local server and automatically opens `http://127.0.0.1:5000` in your web browser.

---

### 2. Using the Web Dashboard

1. **Add Keywords**: Type any word or phrase into the "Keywords to Monitor" section on the left (e.g., `SpaceX` or `"artificial intelligence"`) and hit **Enter** or click **Add**.
2. **Filter by Websites (Optional)**: In the "Filter by Websites" section, type the names or domains of the websites you want to search (e.g., `elpais.com`, `bbc.com`, `Reuters`) and hit **Enter** or click **Filter**.
   - If website filters are added, news will be searched and filtered strictly from those sites.
   - If no website filters are active, the monitor searches across the entire internet.
   - Use the pause/play button on any tag to temporarily toggle individual websites on or off.
3. **Watch the Timer**: The countdown pill in the header displays the time remaining until the next automatic scan (e.g., `04:32`).
4. **Immediate Scan**: Click **Scan Now** anytime to check the internet immediately.
5. **Read & Bookmark**: Click on any article headline to open the original source in a new tab. Use the star icon to bookmark articles or the checkmark to mark them as read.
6. **Adjust Timer & Sources**: Click the ⚙️ **Settings** icon to change the refresh interval (1m to 60m), language/region, or toggle Windows notifications and Reddit/Hacker News sources.

---

### 3. Command Line (CLI) Mode

If you prefer to run the monitor directly inside your terminal or PowerShell window:

```bash
# Monitor keywords across the entire internet:
python cli.py --keywords "OpenAI, Tesla, AI" --interval 5

# Monitor keywords filtered to specific websites:
python cli.py --keywords "Ciberseguridad, AI" --websites "elpais.com, elmundo.es, bbc.com" --interval 5
```

Options:
- `-k, --keywords`: Comma-separated list of keywords to monitor.
- `-w, --websites`: Comma-separated list of website domains or source names to filter (e.g. `elpais.com, bbc.com` or `BBC, Reuters`).
- `-i, --interval`: Refresh interval in minutes (default: 5).
- `-r, --region`: Region and language code (default: `en-US`, or `es-ES`, etc.).
- `--no-notifications`: Disable Windows desktop notifications.

Or simply double-click **`cli_run.bat`** to enter your keywords and website filters interactively.

---

### 4. Python Module Usage

You can also import and use `NewsScanner` directly in your own scripts:

```python
from news_scanner import NewsScanner

scanner = NewsScanner(region_language="en-US")

# Search OpenAI news restricted to specific tech sites
articles = scanner.fetch_google_news(
    keyword="OpenAI",
    websites=["theverge.com", "techcrunch.com", "arstechnica.com"],
    max_results=20
)

for art in articles:
    print(f"[{art['source']}] {art['title']}")
    print(f"Link: {art['link']}\n")
```

---

## 🛠️ Project Structure

```
Scrapper/
├── app.py             # Flask Web Server & REST / SSE API (keywords & websites endpoints)
├── news_scanner.py    # Multi-source internet news fetcher, query builder & website filter
├── scheduler.py       # Background timer loop & notification orchestrator
├── database.py        # SQLite persistence layer (keywords, websites, articles, deduplication)
├── notifier.py        # Windows desktop toast/tray notification dispatcher
├── cli.py             # Standalone terminal CLI runner with --websites argument
├── news_links.txt     # Text file where newly detected links are instantly copied
├── run.bat            # Windows 1-click launcher for Web UI
├── cli_run.bat        # Windows 1-click launcher for CLI mode with website prompt
├── requirements.txt   # Dependencies (Flask, feedparser, requests, colorama)
├── static/
│   ├── app.js         # Frontend reactivity, SSE events, countdown, sound chime, website UI
│   └── style.css      # Modern dark-mode UI styling
└── templates/
    └── index.html     # Single Page Web App dashboard with website filter manager
```

---

## 📋 Requirements

- **Python 3.9+** (tested and compatible with Python 3.9 to 3.13)
- Required packages (installed via `pip install -r requirements.txt`):
  - `Flask`
  - `feedparser`
  - `requests`
  - `colorama`
