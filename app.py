"""
app.py - Main Web Application and REST API for News Monitor
Runs locally and serves a modern reactive dashboard with keyword & website filtering.
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
import frontend_assets

app = Flask(__name__, static_folder="static", template_folder="templates")


@app.route("/")
def index():
    """Main dashboard page."""
    frontend_assets.ensure_frontend_files()
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


# ==================== WEBSITE FILTER ENDPOINTS ====================

@app.route("/api/websites", methods=["GET"])
def get_websites():
    """Retrieves all target websites/sources configured for filtering."""
    websites = database.get_websites()
    return jsonify({"websites": websites})


@app.route("/api/websites", methods=["POST"])
def add_website():
    """Adds a new website or multiple comma-separated website domains/names."""
    data = request.get_json() or {}
    raw_web = data.get("website", "").strip()

    if not raw_web:
        return jsonify({"error": "Website cannot be empty"}), 400

    # Support multiple websites separated by commas if entered together
    webs = [w.strip() for w in raw_web.split(",") if w.strip()]
    added = []
    for w in webs:
        web_id = database.add_website(w)
        added.append({"website": w, "id": web_id})

    # Trigger scan immediately to reflect the new website filter
    scheduler.trigger_immediate_scan()

    return jsonify({"status": "ok", "added": added})


@app.route("/api/websites/<int:website_id>", methods=["DELETE"])
def delete_website(website_id):
    """Deletes a website filter."""
    database.delete_website(website_id)
    scheduler.trigger_immediate_scan()
    return jsonify({"status": "ok", "message": "Website filter deleted"})


@app.route("/api/websites/<int:website_id>/toggle", methods=["PUT"])
def toggle_website(website_id):
    """Pauses or resumes a website filter."""
    new_state = database.toggle_website(website_id)
    scheduler.trigger_immediate_scan()
    return jsonify({"status": "ok", "is_active": new_state})


# ==================== ARTICLE ENDPOINTS ====================

@app.route("/api/articles", methods=["GET"])
def get_articles():
    """Retrieves articles with keyword, website, status filtering and search."""
    keyword = request.args.get("keyword", "all")
    website = request.args.get("website", "all")
    filter_type = request.args.get("filter", "all")  # all, unread, bookmarked
    search = request.args.get("search", "")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    result = database.get_articles(
        keyword=keyword,
        website=website,
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


@app.route("/api/articles/delete-batch", methods=["POST"])
def delete_articles_batch():
    """Deletes multiple selected articles by ID."""
    data = request.get_json() or {}
    ids = data.get("ids", [])
    if not isinstance(ids, list):
        return jsonify({"error": "ids must be a list"}), 400

    clean_ids = [int(i) for i in ids if str(i).isdigit()]
    deleted_count = database.delete_articles_batch(clean_ids)
    return jsonify({"status": "ok", "deleted_count": deleted_count})


@app.route("/api/articles/clear", methods=["DELETE"])
def clear_articles():
    """Clears stored articles (optionally preserving bookmarks)."""
    preserve = request.args.get("preserve_bookmarks", "false").lower() == "true"
    keyword = request.args.get("keyword")
    deleted_count = database.clear_articles(only_unbookmarked=preserve, keyword=keyword)
    return jsonify({"status": "ok", "deleted_count": deleted_count, "message": "Articles cleared"})


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
    if "max_article_age_days" in data:
        try:
            days = int(data["max_article_age_days"])
            if days > 0:
                database.purge_old_articles(max_age_days=days, preserve_bookmarks=True)
        except Exception:
            pass
    return jsonify({"status": "ok", "settings": database.get_settings()})


@app.route("/api/export", methods=["GET"])
def export_articles():
    """Exports articles to CSV or JSON format."""
    format_type = request.args.get("format", "csv").lower()
    keyword = request.args.get("keyword", "all")
    website = request.args.get("website", "all")
    filter_type = request.args.get("filter", "all")

    data = database.get_articles(keyword=keyword, website=website, filter_type=filter_type, limit=5000)
    articles = data.get("articles", [])

    if format_type == "json":
        output = io.BytesIO(json.dumps(articles, indent=2).encode("utf-8"))
        filename = f"news_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        return send_file(output, mimetype="application/json", as_attachment=True, download_name=filename)

    # Default CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Keyword", "Title", "Source", "Source URL", "Link", "Published At",
        "Discovered At", "Is Read", "Is Bookmarked"
    ])
    for a in articles:
        writer.writerow([
            a.get("id"),
            a.get("keyword_matched"),
            a.get("title"),
            a.get("source"),
            a.get("source_url"),
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


# ==================== TOPIC TREND ANALYTICS & GRAPHICS ====================

@app.route("/api/analytics/data", methods=["GET"])
def get_analytics_data_route():
    """Returns aggregated topic volume trends, daily velocity, and media sources."""
    keyword = request.args.get("keyword")
    try:
        days = int(request.args.get("days", "30"))
    except Exception:
        days = 30
    data = database.get_analytics_data(keyword=keyword, days=days)
    return jsonify(data)


@app.route("/api/analytics/chart.png", methods=["GET"])
def get_analytics_chart_route():
    """Generates and serves a publication-ready PNG graphic showing news momentum."""
    import chart_generator

    keyword = request.args.get("keyword")
    try:
        days = int(request.args.get("days", "30"))
    except Exception:
        days = 30
    theme = request.args.get("theme", "dark")
    download = request.args.get("download", "false").lower() == "true"

    img_bytes = chart_generator.generate_topic_trend_chart(
        keyword=keyword,
        days=days,
        theme=theme
    )

    clean_kw = (keyword.strip() if keyword and keyword.lower() != "all" else "all_topics").replace(" ", "_")
    filename = f"news_trend_{clean_kw}_{days}d.png"

    return send_file(
        io.BytesIO(img_bytes),
        mimetype="image/png",
        as_attachment=download,
        download_name=filename
    )


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
