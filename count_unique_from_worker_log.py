#!/usr/bin/env python3
"""
Count unique page URLs from Logs/Worker.log (or path argument).

Assignment rule: uniqueness by URL with the fragment (#...) removed only.

Usage:
  python3 count_unique_from_worker_log.py
  python3 count_unique_from_worker_log.py path/to/Worker.log
  python3 count_unique_from_worker_log.py --http-ok   # only status 2xx lines
"""
import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urldefrag

DEFAULT_LOG = Path(__file__).resolve().parent / "Worker.log"
LINE_RE = re.compile(
    r"Downloaded (https?://[^,\s]+)\s*,\s*status\s*<(\d+)>",
    re.IGNORECASE,
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "log_file",
        nargs="?",
        type=Path,
        default=DEFAULT_LOG,
        help=f"Worker log file (default: {DEFAULT_LOG})",
    )
    ap.add_argument(
        "--http-ok",
        action="store_true",
        help="Only count lines whose HTTP status is 200-299",
    )
    args = ap.parse_args()
    path = args.log_file
    if not path.is_file():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    all_urls = set()
    ok_urls = set()
    lines_matched = 0

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LINE_RE.search(line)
            if not m:
                continue
            lines_matched += 1
            raw_url = m.group(1).strip()
            code = int(m.group(2))
            clean, _frag = urldefrag(raw_url)
            all_urls.add(clean)
            if 200 <= code <= 299:
                ok_urls.add(clean)

    print(f"Log file: {path}")
    print(f"Lines with 'Downloaded …, status <…>': {lines_matched}")
    print(f"Unique URLs (fragment stripped, all statuses): {len(all_urls)}")
    if args.http_ok:
        print(f"Unique URLs (fragment stripped, HTTP 2xx only): {len(ok_urls)}")
    else:
        print("(Use --http-ok to also print count for successful responses only.)")


if __name__ == "__main__":
    main()
