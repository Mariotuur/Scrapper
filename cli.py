"""
cli.py - Standalone Command-Line News Monitor
Run directly in your terminal to monitor keywords with a live countdown and desktop alerts.
Usage:
    python cli.py --keywords "OpenAI, SpaceX, Quantum Computing" --interval 5
"""

import argparse
import time
import sys
from datetime import datetime
import colorama
from colorama import Fore, Style

import database
from news_scanner import NewsScanner
import notifier

colorama.init(autoreset=True)


def format_time(seconds: int) -> str:
    mins, secs = divmod(seconds, 60)
    return f"{mins:02d}:{secs:02d}"


def run_cli_scanner(keywords_arg: str, interval_minutes: int, region: str = "en-US", enable_notif: bool = True):
    database.init_db()
    
    # Process keywords
    if keywords_arg:
        kws = [k.strip() for k in keywords_arg.split(",") if k.strip()]
        for kw in kws:
            database.add_keyword(kw)
    
    active_keywords = database.get_keywords(active_only=True)
    if not active_keywords:
        print(Fore.RED + "\n[!] No active keywords specified. Provide keywords via --keywords 'word1, word2'")
        sys.exit(1)

    kw_names = [k["keyword"] for k in active_keywords]

    print(Style.BRIGHT + Fore.CYAN + "\n" + "=" * 65)
    print(Style.BRIGHT + Fore.CYAN + "   🌐 LOCAL INTERNET NEWS MONITOR (CLI MODE)")
    print(Style.BRIGHT + Fore.CYAN + "=" * 65)
    print(Fore.YELLOW + f"  Tracking Keywords : {', '.join(kw_names)}")
    print(Fore.YELLOW + f"  Refresh Timer     : Every {interval_minutes} minute(s)")
    print(Fore.YELLOW + f"  Region / Language : {region}")
    print(Fore.YELLOW + f"  Desktop Alerts    : {'Enabled' if enable_notif else 'Disabled'}")
    print(Style.BRIGHT + Fore.CYAN + "=" * 65 + "\n")

    scanner = NewsScanner(region_language=region)

    try:
        while True:
            # Refresh active keywords
            active_keywords = database.get_keywords(active_only=True)
            kw_names = [k["keyword"] for k in active_keywords]
            
            print(Fore.BLUE + f"[{datetime.now().strftime('%H:%M:%S')}] Checking news across the internet...")
            
            total_found = 0
            all_new = []

            for kw in kw_names:
                sys.stdout.write(f"  Searching for '{kw}'... ")
                sys.stdout.flush()
                articles = scanner.fetch_google_news(kw, max_results=30)
                new_saved = database.save_articles(articles)
                total_found += len(articles)
                all_new.extend(new_saved)
                
                if new_saved:
                    sys.stdout.write(Fore.GREEN + f"Found {len(new_saved)} NEW articles!\n")
                    for art in new_saved[:3]:
                        print(Fore.LIGHTGREEN_EX + f"    • [{art.get('source')}] {art.get('title')}")
                        print(Fore.LIGHTBLACK_EX + f"      Link: {art.get('link')}")
                    if len(new_saved) > 3:
                        print(Fore.LIGHTBLACK_EX + f"      ... and {len(new_saved) - 3} more new articles.")
                else:
                    sys.stdout.write(Fore.LIGHTBLACK_EX + "No new articles since last check.\n")

            if all_new and enable_notif:
                notifier.notify_new_articles(all_new, keyword=kw_names[0] if len(kw_names) == 1 else "Watchlist")

            database.log_scan_event(
                keywords=kw_names,
                found=total_found,
                new_count=len(all_new),
                status="success",
                message=f"CLI scan found {len(all_new)} new items."
            )

            # Countdown loop
            total_seconds = interval_minutes * 60
            for sec_left in range(total_seconds, 0, -1):
                sys.stdout.write(f"\r{Fore.YELLOW}Next check in {format_time(sec_left)} (Press Ctrl+C to stop)... {Style.RESET_ALL}")
                sys.stdout.flush()
                time.sleep(1)

            sys.stdout.write("\r" + " " * 70 + "\r")

    except KeyboardInterrupt:
        print(Fore.CYAN + "\n\nNews Monitor CLI stopped. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor the internet for news matching specific words.")
    parser.add_argument("-k", "--keywords", type=str, default="", help="Comma-separated keywords to monitor, e.g., 'OpenAI, SpaceX'")
    parser.add_argument("-i", "--interval", type=int, default=5, help="Refresh interval in minutes (default: 5)")
    parser.add_argument("-r", "--region", type=str, default="en-US", help="Region and language code, e.g. en-US, es-ES")
    parser.add_argument("--no-notifications", action="store_true", help="Disable Windows desktop notifications")

    args = parser.parse_args()
    run_cli_scanner(
        keywords_arg=args.keywords,
        interval_minutes=args.interval,
        region=args.region,
        enable_notif=not args.no_notifications
    )
