"""
chart_generator.py - Generates publication-ready trend graphics and media coverage reports.
Creates high-resolution charts showing news volume over time, publication velocity,
and top media outlets to demonstrate the relevance and importance of a topic.
"""

import io
import os
from datetime import datetime
from typing import Optional, Dict, Any

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend safe for servers
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyBboxPatch

import database


def generate_topic_trend_chart(
    keyword: Optional[str] = None,
    days: int = 30,
    theme: str = "dark",
    output_path: Optional[str] = None
) -> bytes:
    """
    Renders a high-resolution (150 DPI) executive graphic showing news momentum,
    daily coverage volume, and publisher diversity for a topic.
    Returns PNG bytes.
    """
    data = database.get_analytics_data(keyword=keyword, days=days)

    is_dark = theme.lower() != "light"

    # Theme color palettes
    if is_dark:
        bg_main = "#0d1117"
        bg_card = "#161b22"
        border_col = "#30363d"
        text_title = "#f0f6fc"
        text_sub = "#8b949e"
        text_accent = "#58a6ff"
        line_color = "#2f81f7"
        fill_color = "#1f6feb"
        bar_colors = ["#2f81f7", "#3fb950", "#a371f7", "#d29922", "#f85149", "#56d364"]
        grid_col = "#21262d"
    else:
        bg_main = "#ffffff"
        bg_card = "#f6f8fa"
        border_col = "#d0d7de"
        text_title = "#1f2328"
        text_sub = "#656d76"
        text_accent = "#0969da"
        line_color = "#0969da"
        fill_color = "#ddf4ff"
        bar_colors = ["#0969da", "#1a7f37", "#8250df", "#9a6700", "#cf222e", "#2da44e"]
        grid_col = "#eaeef2"

    topic_label = keyword if (keyword and keyword.lower() != "all") else "All Tracked Topics"
    total_articles = data["total_articles"]
    distinct_sources = data["distinct_sources"]
    avg_per_day = data["avg_per_day"]
    peak_info = data["peak_day"]

    # Setup Figure with high DPI
    fig = plt.figure(figsize=(14, 8.5), dpi=150, facecolor=bg_main)
    
    # Grid: Header/KPIs on top, 2 subplots side-by-side below
    # (Top: 0.15 height, Bottom: 0.85 height with 65% timeline / 35% sources)
    gs = fig.add_gridspec(
        nrows=2, ncols=2,
        height_ratios=[1.2, 5.0],
        width_ratios=[1.8, 1.0],
        left=0.06, right=0.95, top=0.92, bottom=0.08,
        wspace=0.22, hspace=0.28
    )

    # ------------------ TOP ZONE: HEADER & METRIC CARDS ------------------
    ax_top = fig.add_subplot(gs[0, :])
    ax_top.set_facecolor(bg_main)
    ax_top.axis("off")

    # Main Title
    ax_top.text(
        0.0, 0.82,
        f"Media Coverage & Relevance Trend: {topic_label.upper()}",
        fontsize=18, fontweight="bold", color=text_title,
        transform=ax_top.transAxes, va="top"
    )

    # Subtitle with date range
    start_fmt = data["start_date"]
    end_fmt = data["end_date"]
    ax_top.text(
        0.0, 0.40,
        f"Demonstrating high media interest & news frequency • Timeframe: {start_fmt} to {end_fmt} ({days} days)",
        fontsize=10.5, color=text_sub,
        transform=ax_top.transAxes, va="top"
    )

    # 4 KPI Mini-Badges across the right of top bar
    kpis = [
        ("TOTAL NEWS", f"{total_articles}", text_accent),
        ("DAILY VELOCITY", f"{avg_per_day}/day", "#3fb950" if is_dark else "#1a7f37"),
        ("MEDIA SOURCES", f"{distinct_sources}", "#a371f7" if is_dark else "#8250df"),
        ("PEAK SINGLE DAY", f"{peak_info['count']} articles", "#d29922" if is_dark else "#9a6700")
    ]

    card_width = 0.14
    start_x = 0.40
    gap = 0.015

    for idx, (label, val, col) in enumerate(kpis):
        cx = start_x + idx * (card_width + gap)
        # Background box for KPI
        rect = FancyBboxPatch(
            (cx, 0.12), card_width, 0.76,
            boxstyle="round,pad=0.02,rounding_size=0.04",
            facecolor=bg_card, edgecolor=border_col,
            transform=ax_top.transAxes, clip_on=False, lw=1
        )
        ax_top.add_patch(rect)

        ax_top.text(
            cx + card_width / 2, 0.65, label,
            fontsize=7.5, fontweight="bold", color=text_sub,
            ha="center", va="center", transform=ax_top.transAxes
        )
        ax_top.text(
            cx + card_width / 2, 0.32, val,
            fontsize=12, fontweight="bold", color=col,
            ha="center", va="center", transform=ax_top.transAxes
        )

    # ------------------ LEFT SUBPLOT: TIMELINE TREND ------------------
    ax_timeline = fig.add_subplot(gs[1, 0])
    ax_timeline.set_facecolor(bg_card)
    for spine in ax_timeline.spines.values():
        spine.set_color(border_col)

    daily_data = data["daily_trends"]
    dates = [datetime.strptime(d["date"], "%Y-%m-%d") for d in daily_data]
    counts = [d["count"] for d in daily_data]

    if counts:
        # Plot area and line
        ax_timeline.fill_between(dates, counts, color=fill_color, alpha=0.25 if is_dark else 0.4)
        ax_timeline.plot(dates, counts, color=line_color, lw=2.5, marker="o", markersize=4.5, label="Articles / Day")

        # Peak annotation
        max_idx = counts.index(max(counts)) if counts else 0
        if counts and counts[max_idx] > 0:
            peak_date = dates[max_idx]
            peak_val = counts[max_idx]
            ax_timeline.annotate(
                f"Peak: {peak_val} news",
                xy=(peak_date, peak_val),
                xytext=(0, 14),
                textcoords="offset points",
                ha="center",
                fontsize=8.5,
                fontweight="bold",
                color=text_title,
                bbox=dict(boxstyle="round,pad=0.2", facecolor=bg_main, edgecolor=text_accent, lw=1)
            )

    ax_timeline.set_title("Daily News Coverage Timeline (Publication Momentum)", fontsize=11, fontweight="bold", color=text_title, pad=12)
    ax_timeline.set_ylabel("Articles Published", fontsize=9.5, color=text_sub)
    ax_timeline.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax_timeline.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 7)))
    plt.setp(ax_timeline.get_xticklabels(), rotation=30, ha="right", fontsize=8.5, color=text_sub)
    plt.setp(ax_timeline.get_yticklabels(), fontsize=8.5, color=text_sub)
    ax_timeline.grid(True, linestyle="--", alpha=0.6, color=grid_col)
    ax_timeline.set_ylim(bottom=0, top=max(counts + [5]) * 1.25 if counts else 10)

    # ------------------ RIGHT SUBPLOT: TOP MEDIA SOURCES ------------------
    ax_sources = fig.add_subplot(gs[1, 1])
    ax_sources.set_facecolor(bg_card)
    for spine in ax_sources.spines.values():
        spine.set_color(border_col)

    top_sources = data["top_sources"][:8]  # Top 8 sources
    if top_sources:
        src_names = [s["source"][:20] for s in reversed(top_sources)]
        src_counts = [s["count"] for s in reversed(top_sources)]
        y_pos = range(len(src_names))

        colors = [bar_colors[i % len(bar_colors)] for i in range(len(src_names))]
        bars = ax_sources.barh(y_pos, src_counts, color=colors, height=0.65, alpha=0.9)

        ax_sources.set_yticks(y_pos)
        ax_sources.set_yticklabels(src_names, fontsize=8.5, color=text_title)
        plt.setp(ax_sources.get_xticklabels(), fontsize=8.5, color=text_sub)

        # Bar value labels on the right of each bar
        for bar in bars:
            width = bar.get_width()
            ax_sources.text(
                width + 0.3, bar.get_y() + bar.get_height() / 2,
                f"{int(width)}",
                va="center", ha="left",
                fontsize=8.5, fontweight="bold", color=text_title
            )

        max_src_val = max(src_counts) if src_counts else 10
        ax_sources.set_xlim(0, max_src_val * 1.25)
    else:
        ax_sources.text(0.5, 0.5, "No source data yet", ha="center", va="center", color=text_sub, transform=ax_sources.transAxes)

    ax_sources.set_title("Top Reporting Media Outlets", fontsize=11, fontweight="bold", color=text_title, pad=12)
    ax_sources.set_xlabel("Articles Count", fontsize=9.5, color=text_sub)
    ax_sources.grid(True, axis="x", linestyle="--", alpha=0.6, color=grid_col)

    # Footer note
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    fig.text(
        0.5, 0.02,
        f"Generated by News Monitor • High-Impact Media Intelligence Report • Analyzed at {now_str}",
        fontsize=8, color=text_sub, ha="center"
    )

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    image_bytes = buf.getvalue()

    if output_path:
        try:
            with open(output_path, "wb") as f:
                f.write(image_bytes)
        except Exception as e:
            print(f"[ChartGenerator] Error saving graphic to {output_path}: {e}")

    return image_bytes
