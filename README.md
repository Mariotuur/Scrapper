# 📰 News Monitor - Local Internet Keyword News Tracker

A local tool that continuously checks news across the internet matching any keywords or phrases you provide, automatically refreshing on a customizable background timer.

---

## ✨ Features

- **Global Internet News Coverage**: Powered by Google News RSS (covering BBC, CNN, Reuters, Bloomberg, TechCrunch, local news, and blogs globally without requiring paid API keys) + optional Reddit & Hacker News sources.
- **Continuous Background Timer**: Refreshes automatically every 1, 5, 10, 15, 30, or 60 minutes.
- **Multiple Keywords & Phrases**: Track as many words/phrases as you want simultaneously (e.g. `"OpenAI"`, `"quantum computing"`, `"Bitcoin"`).
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
  - Saves your history and settings locally.
- **Exporting**: 1-click export of discovered articles to **CSV** or **JSON**.
- **CLI Mode Included**: Can also run in a terminal or PowerShell session.

---

## 🚀 Quick Start

### 1. Launch with One Click
Double-click **`run.bat`** in this folder, or run:

```bash
python app.py
```

This starts the local server and automatically opens `http://127.0.0.1:5000` in your web browser.

---

### 2. Using the Web Dashboard

1. **Add Keywords**: Type any word or phrase into the top search bar (e.g., `SpaceX` or `"artificial intelligence"`) and hit **Enter** or click **Add Word**.
2. **Watch the Timer**: The countdown pill in the header displays the time remaining until the next automatic scan (e.g., `04:32`).
3. **Immediate Scan**: Click **Scan Now** anytime to check the internet immediately.
4. **Read & Bookmark**: Click on any article headline to open the original source in a new tab. Use the star icon to bookmark articles or the checkmark to mark them as read.
5. **Adjust Timer & Sources**: Click the ⚙️ **Settings** icon to change the refresh interval (1m to 60m), language/region, or toggle Windows notifications and Reddit/Hacker News sources.

---

### 3. Command Line (CLI) Mode

If you prefer to run the monitor directly inside your terminal or PowerShell window:

```bash
python cli.py --keywords "OpenAI, Tesla, AI" --interval 5
```

Options:
- `-k, --keywords`: Comma-separated list of keywords to monitor.
- `-i, --interval`: Refresh interval in minutes (default: 5).
- `-r, --region`: Region and language code (default: `en-US`).
- `--no-notifications`: Disable Windows desktop notifications.

Or simply double-click **`cli_run.bat`** to enter your keywords interactively.

---

## 🛠️ Project Structure

```
Scrapper/
├── app.py             # Flask Web Server & REST / SSE API
├── news_scanner.py    # Multi-source internet news fetcher & keyword parser
├── scheduler.py       # Background timer loop & notification orchestrator
├── database.py        # SQLite persistence layer, deduplication & tracking
├── notifier.py        # Windows desktop toast/tray notification dispatcher
├── cli.py             # Standalone terminal CLI runner
├── news_links.txt     # Text file where newly detected links are instantly copied
├── run.bat            # Windows 1-click launcher for Web UI
├── cli_run.bat        # Windows 1-click launcher for CLI mode
├── requirements.txt   # Dependencies
├── static/
│   ├── app.js         # Frontend reactivity, SSE events, countdown, sound chime
│   └── style.css      # Modern dark-mode UI styling
└── templates/
    └── index.html     # Single Page Web App dashboard
```

---

## 📋 Requirements

- **Python 3.10+** (tested and optimized for Python 3.13)
- Required packages (already installed): `Flask`, `feedparser`, `requests`, `colorama`
