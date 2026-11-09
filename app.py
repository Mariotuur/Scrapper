"""
app.py - Main Web Application and REST API for News Monitor
Runs locally and serves a modern reactive dashboard.
"""

import os
import sys
import json
import csv
import io
import time
from flask import Flask, render_template, request, jsonify, Response, send_file
from datetime import datetime

import database
from scheduler import scheduler

app = Flask(__name__, static_folder="static", template_folder="templates")


@app.route("/")
def index():
    """Main dashboard page."""
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def get_status():
    """Returns scheduler and system status."""
    stats = database.get_dashboard_stats()
    sched_status = scheduler.get_status()
    return jsonify({
        "status": "ok",
        "scheduler": sched_status,
        "stats": stats
    })


@app.route("/api/scan", methods=["POST"])
def trigger_scan():
    """Manually triggers an immediate news scan."""
    triggered = scheduler.trigger_immediate_scan()
    if triggered:
        return jsonify({"status": "ok", "message": "Scan triggered successfully"})
    else:
        return jsonify({"status": "busy", "message": "A scan is already in progress"}), 409


# ==================== KEYWORD ENDPOINTS ====================

@app.route("/api/keywords", methods=["GET"])
def get_keywords():
    """Retrieves all tracked keywords."""
    keywords = database.get_keywords()
    return jsonify({"keywords": keywords})


@app.route("/api/keywords", methods=["POST"])
def add_keyword():
    """Adds a new keyword or multiple comma-separated keywords."""
    data = request.get_json() or {}
    raw_kw = data.get("keyword", "").strip()

    if not raw_kw:
        return jsonify({"error": "Keyword cannot be empty"}), 400

    # Support multiple keywords separated by commas if entered together
    kws = [k.strip() for k in raw_kw.split(",") if k.strip()]
    added = []
    for kw in kws:
        kw_id = database.add_keyword(kw)
        added.append({"keyword": kw, "id": kw_id})

    # Trigger scan immediately for the new keywords
    scheduler.trigger_immediate_scan()

    return jsonify({"status": "ok", "added": added})


@app.route("/api/keywords/<int:keyword_id>", methods=["DELETE"])
def delete_keyword(keyword_id):
    """Deletes a tracked keyword."""
    database.delete_keyword(keyword_id)
    return jsonify({"status": "ok", "message": "Keyword deleted"})


@app.route("/api/keywords/<int:keyword_id>/toggle", methods=["PUT"])
def toggle_keyword(keyword_id):
    """Pauses or resumes a keyword."""
    new_state = database.toggle_keyword(keyword_id)
    return jsonify({"status": "ok", "is_active": new_state})


# ==================== ARTICLE ENDPOINTS ====================

@app.route("/api/articles", methods=["GET"])
def get_articles():
    """Retrieves articles with filtering and search."""
    keyword = request.args.get("keyword", "all")
    filter_type = request.args.get("filter", "all")  # all, unread, bookmarked
    search = request.args.get("search", "")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    result = database.get_articles(
        keyword=keyword,
        filter_type=filter_type,
        search_query=search,
        limit=limit,
        offset=offset
    )
    return jsonify(result)


@app.route("/api/articles/<int:article_id>/read", methods=["POST"])
def mark_read(article_id):
    """Marks article as read or unread."""
    data = request.get_json() or {}
    is_read = data.get("is_read", True)
    database.mark_article_read(article_id, is_read=is_read)
    return jsonify({"status": "ok", "id": article_id, "is_read": is_read})


@app.route("/api/articles/mark-all-read", methods=["POST"])
def mark_all_read():
    """Marks all articles (optionally for a keyword) as read."""
    data = request.get_json() or {}
    keyword = data.get("keyword")
    database.mark_all_articles_read(keyword=keyword)
    return jsonify({"status": "ok", "message": "Articles marked as read"})


@app.route("/api/articles/<int:article_id>/bookmark", methods=["POST"])
def toggle_bookmark(article_id):
    """Toggles bookmark status on an article."""
    is_bookmarked = database.toggle_article_bookmark(article_id)
    return jsonify({"status": "ok", "id": article_id, "is_bookmarked": is_bookmarked})


@app.route("/api/articles/<int:article_id>", methods=["DELETE"])
def delete_article(article_id):
    """Deletes an article."""
    database.delete_article(article_id)
    return jsonify({"status": "ok", "message": "Article deleted"})


@app.route("/api/articles/clear", methods=["DELETE"])
def clear_articles():
    """Clears article history (retaining bookmarks by default)."""
    only_unbookmarked = request.args.get("preserve_bookmarks", "true").lower() == "true"
    database.clear_articles(only_unbookmarked=only_unbookmarked)
    return jsonify({"status": "ok", "message": "History cleared"})


# ==================== SETTINGS & EXPORT ====================

@app.route("/api/settings", methods=["GET"])
def get_settings():
    """Returns current settings."""
    return jsonify(database.get_settings())


@app.route("/api/settings", methods=["POST"])
def update_settings():
    """Updates settings."""
    data = request.get_json() or {}
    database.update_settings(data)
    return jsonify({"status": "ok", "settings": database.get_settings()})


@app.route("/api/export", methods=["GET"])
def export_articles():
    """Exports articles to CSV or JSON format."""
    format_type = request.args.get("format", "csv").lower()
    keyword = request.args.get("keyword", "all")
    filter_type = request.args.get("filter", "all")

    data = database.get_articles(keyword=keyword, filter_type=filter_type, limit=5000)
    articles = data.get("articles", [])

    if format_type == "json":
        output = io.BytesIO(json.dumps(articles, indent=2).encode("utf-8"))
        filename = f"news_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        return send_file(output, mimetype="application/json", as_attachment=True, download_name=filename)

    # Default CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Keyword", "Title", "Source", "Link", "Published At",
        "Discovered At", "Is Read", "Is Bookmarked"
    ])
    for a in articles:
        writer.writerow([
            a.get("id"),
            a.get("keyword_matched"),
            a.get("title"),
            a.get("source"),
            a.get("link"),
            a.get("published_at"),
            a.get("discovered_at"),
            a.get("is_read"),
            a.get("is_bookmarked")
        ])

    mem = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    filename = f"news_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name=filename)


@app.route("/api/links-file", methods=["GET"])
def get_links_file():
    """Serves the news_links.txt file for viewing or downloading."""
    download = request.args.get("download", "false").lower() == "true"
    filepath = database.get_links_file_path()
    if not os.path.exists(filepath):
        database.init_links_file()
    return send_file(
        filepath,
        mimetype="text/plain; charset=utf-8",
        as_attachment=download,
        download_name="news_links.txt"
    )


@app.route("/api/links-file/clear", methods=["POST"])
def clear_links_file_route():
    """Clears news_links.txt."""
    database.clear_links_file()
    return jsonify({"status": "ok", "message": "news_links.txt cleared"})


# ==================== SERVER-SENT EVENTS (SSE) ====================

@app.route("/api/events")
def sse_events():
    """Server-Sent Events stream for real-time live updates."""
    def event_stream():
        q = scheduler.subscribe_events()
        try:
            # Yield initial connect greeting
            yield f"data: {json.dumps({'event': 'connected', 'data': {'time': datetime.now().isoformat()}})}\n\n"
            while True:
                try:
                    msg = q.get(timeout=20)
                    yield f"data: {json.dumps(msg)}\n\n"
                except Exception:
                    # Heartbeat keep-alive every 20s
                    yield f": keepalive\n\n"
        finally:
            scheduler.unsubscribe_events(q)

    return Response(event_stream(), mimetype="text/event-stream")


def start_server(host="127.0.0.1", port=5000, debug=False, open_browser=True):
    """Starts the Flask server and background scheduler."""
    database.init_db()
    scheduler.start()

    if open_browser:
        import webbrowser
        def _open():
            time.sleep(1.2)
            webbrowser.open(f"http://{host}:{port}")
        import threading
        threading.Thread(target=_open, daemon=True).start()

    print(f"\n========================================================")
    print(f"  News Monitor running at: http://{host}:{port}")
    print(f"  Background scheduler active (checking news periodically)")
    print(f"========================================================\n")
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    start_server(open_browser=True)
