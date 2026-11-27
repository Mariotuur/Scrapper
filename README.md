# 📰 News Monitor - Local Internet Keyword, Topic & Website News Tracker

A fast, local tool that continuously checks news across the internet matching any keywords or topics you provide, automatically refreshing on a customizable background timer, with website filtering, deletion controls, recency limits, and publication-ready trend analytics reports.

---

## ✨ Features & Capabilities

### 🌐 Smart News Scraping & Source Filtering
- **Global Internet Coverage**: Powered by Google News RSS (covering BBC, Reuters, Bloomberg, El País, TechCrunch, local outlets, and specialized portals globally with zero paid API keys) + optional Reddit & Hacker News sources.
- **Website & Domain Filtering**:
  - Restrict searches to specific websites, domains, or news outlets (e.g. `elpais.com`, `bbc.co.uk`, `theverge.com`, `Reuters`).
  - Active toggle: pause or enable specific website filters with one click, or leave unfiltered to search the entire web.
- **Continuous Background Timer**: Refreshes automatically on a customizable timer (every 1, 5, 10, 15, 30, or 60 minutes).
- **Multiple Keywords & Boolean Search**: Track as many words or phrases simultaneously as you need. Supports exact phrases (`"..."`), logical operators (`OR`, `AND`), and negative exclusions (`-term`).
- **Keyword Highlighting**: Matches are cleanly highlighted in headlines and snippet summaries.

---

### 🚀 What's New

#### 1. 📊 Topic Trend Analytics & Printable Graphics
Prove that your chosen topic is currently trending and receiving massive media coverage:
- **Interactive Coverage Timeline**: Visual trend curve and gradient area chart showing daily publication volume over time.
- **Top Media Outlets Breakdown**: Bar chart ranking newspapers and publications (e.g., *Industrial Cyber*, *INCIBE*, *CISA*, *EL PAÍS*) covering the topic.
- **Key Metric Badges**:
  - **Total News Detected** (e.g. 128 articles).
  - **Publication Velocity** (e.g. 4.3 articles/day).
  - **Distinct Media Outlets** (independent publishers reporting).
  - **Peak News Day** (highest single-day coverage volume).
- **🖨️ Print / Save to PDF**: Custom `@media print` stylesheet that strips web chrome and formats a clean executive white-paper report for physical printing or PDF export.
- **📥 Download High-Res Graphic (PNG)**: One-click export of a 150 DPI publication-quality graphic (generated with Matplotlib) ready to copy/paste into slides, PowerPoint, Word, or thesis defense.
- **Terminal Generation**: Generate `news_trend_report.png` directly from the command line using `python cli.py --chart`.

#### 2. 🗑️ Article Deletion & Feed Management
Easily discard stories you're not interested in:
- **Individual Delete (`🗑 Delete`)**: Direct delete button on every article card with smooth fade-out animation.
- **Multi-Select & Batch Delete**: Checkboxes on every card + **Select All** toolbar control + red **`🗑 Delete Selected (N)`** button to batch delete chosen items.
- **Delete All Stored News**: Toolbar modal button to wipe all stored articles in one click, with an optional toggle to protect your bookmarked (⭐ *Saved*) articles.

#### 3. ⏳ 30-Day Recency Limit (Eliminate Outdated News)
Avoid receiving articles from years ago:
- **Search-Level Recency**: Queries automatically append `when:30d`, instructing Google to filter out old results at the source.
- **Parser & Database Guard**: Validates publication dates (`published_at`) across Google News, Reddit, and Hacker News, rejecting any article older than 30 days.
- **Auto-Purge**: Automatically cleans out old articles on scan cycles while preserving your saved bookmarks.
- **Customizable**: Choose between 7, 14, 30 days (*Recommended*), 60, 90 days, or All time in the Settings modal.

#### 4. 🛡️ Self-Healing Embedded Assets
- Embedded fallback assets guarantee the dashboard never crashes with `TemplateNotFound`, automatically restoring missing templates and stylesheets on fresh clones or different computers.

---

### 🔔 Live Alerts, Database & Storage
- **Real-Time Live Updates (SSE)**: New news appears instantly on screen without manual page refreshing.
- **Dual Notification System**: Native Windows toast/tray alerts + browser sound chime.
- **Instant Links File (`news_links.txt`)**: Newly detected news links are instantly written to `news_links.txt` in real time.
- **Local SQLite Database**: Deduplicates articles, tracks read/unread states, and stores bookmarks locally.
- **Data Exporting**: 1-click export of your database feed to **CSV** or **JSON**.

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

1. **Add Keywords**: Type any word or phrase into the "Keywords to Monitor" section on the left (e.g. `Ciberseguridad` or `"artificial intelligence"`) and hit **Enter** or click **Add**.
2. **Filter by Websites (Optional)**: In "Filter by Websites", type domain names or outlet names (e.g. `elpais.com`, `bbc.com`, `Reuters`) to restrict searches to specific sites.
3. **Manage & Delete News**:
   - Discard single articles with the **`🗑 Delete`** button on each card.
   - Select multiple articles with the checkboxes (or **Select All**) and click **`🗑 Delete Selected`**.
   - Use **`🗑 Delete All News`** in the toolbar to clear historical news while preserving starred bookmarks.
4. **View Trends & Print Graphic**:
   - Click **`📊 Trends & Graphic`** in the top navigation bar.
   - Filter by topic or timeframe (Last 7, 14, 30, or 60 days).
   - Click **🖨️ Print / Save PDF** to print a clean paper report.
   - Click **📥 Download Graphic (PNG)** to download a high-res image for slides and documents.
5. **Adjust Settings**: Click ⚙️ to change the auto-refresh interval, maximum article age (default: 30 days), language/region, or toggle notifications.

---

### 3. Command Line (CLI) Mode

Run the monitor directly inside your terminal or PowerShell window:

```bash
# Monitor keywords across the entire internet:
python cli.py --keywords "Ciberseguridad, AI" --interval 5

# Monitor keywords filtered to specific websites:
python cli.py --keywords "Ciberseguridad" --websites "elpais.com, bbc.com, reuters.com" --interval 5

# Generate and save a high-res trend graphic directly from terminal:
python cli.py --chart --chart-days 30

# Generate a trend graphic for a specific topic:
python cli.py --keywords "Ciberseguridad" --chart --chart-days 30
```

CLI Arguments:
- `-k, --keywords`: Comma-separated list of keywords to monitor.
- `-w, --websites`: Comma-separated list of website domains or source names to filter.
- `-i, --interval`: Refresh interval in minutes (default: 5).
- `-r, --region`: Region and language code (e.g. `en-US`, `es-ES`).
- `--chart`: Generates `news_trend_report.png` in the project directory and exits.
- `--chart-days`: Number of days to include in the trend graphic (default: 30).
- `--no-notifications`: Disable Windows desktop notifications.

Or double-click **`cli_run.bat`** to enter your settings interactively.

---

### 4. Python Module Usage

You can also import and use `NewsScanner` and `chart_generator` directly in your own scripts:

```python
from news_scanner import NewsScanner
import chart_generator

# 1. Fetch news with website filter and 30-day limit
scanner = NewsScanner(region_language="es-ES", max_age_days=30)
articles = scanner.fetch_google_news(
    keyword="Ciberseguridad",
    websites=["elpais.com", "reuters.com"],
    max_results=20
)

for art in articles:
    print(f"[{art['source']}] {art['title']}")
    print(f"Link: {art['link']}\n")

# 2. Generate a high-resolution trend graphic programmatically
chart_generator.generate_topic_trend_chart(
    keyword="Ciberseguridad",
    days=30,
    theme="dark",
    output_path="ciberseguridad_report.png"
)
```

---

## 🛠️ Project Structure

```
Scrapper/
├── app.py                 # Flask server, REST & SSE API, analytics & chart endpoints
├── chart_generator.py     # Matplotlib engine for rendering high-res trend graphics
├── news_scanner.py        # Multi-source fetcher with recency filter & domain filtering
├── scheduler.py           # Background timer loop & auto-purge orchestrator
├── database.py            # SQLite engine (articles, batch delete, analytics aggregation)
├── notifier.py            # Windows desktop notification dispatcher
├── cli.py                 # Terminal CLI runner with --websites and --chart support
├── frontend_assets.py     # Self-healing embedded assets (templates & styles)
├── news_links.txt         # Real-time plain text log of newly detected article links
├── run.bat                # Windows 1-click launcher for Web UI
├── cli_run.bat            # Windows 1-click launcher for CLI mode
├── requirements.txt       # Dependencies (Flask, feedparser, requests, colorama, matplotlib)
├── static/
│   ├── app.js             # Frontend reactivity, canvas timeline chart, batch delete, modals
│   └── style.css          # Dark-mode styles + @media print executive report styles
└── templates/
    └── index.html         # Single Page Dashboard with analytics & deletion modals
```

---

## 📋 Requirements

- **Python 3.9+** (compatible with Python 3.9 to 3.13)
- Required packages (installed via `pip install -r requirements.txt`):
  - `Flask`
  - `feedparser`
  - `requests`
  - `colorama`
  - `matplotlib`
