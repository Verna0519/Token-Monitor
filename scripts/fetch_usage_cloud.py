#!/usr/bin/env python3
"""
fetch_usage_cloud.py — OPT-IN cloud fetcher for the Claude Enterprise Analytics API.

  ┌─────────────────────────────────────────────────────────────────────────┐
  │ ⚠️  THIS SCRIPT MAKES A NETWORK CALL (EGRESS) to api.anthropic.com.        │
  │     It is a DELIBERATE, DOCUMENTED EXCEPTION to the repo's air-gap (RL1),  │
  │     added at operator request (2026-07-28) to pull real per-product        │
  │     spend for the dashboard. It is NOT part of, and never called by, the   │
  │     core extract/coordinate pipeline (§5 "no runtime API call" still holds │
  │     for every OTHER script). It runs only when YOU run it AND a key is set.│
  │     No key in .env  ->  it no-ops and prints how to enable  ->  air-gap    │
  │     preserved by default.                                                  │
  └─────────────────────────────────────────────────────────────────────────┘

What it does: calls GET /v1/organizations/analytics/cost_report (Enterprise plan;
Analytics API key, scope read:analytics), groups cost by product (chat / claude_code /
cowork / office_agent / ...) over a time window, and writes a PRIVATE summary to
worktemp/cloud-usage.json that render_dashboard.py renders as a "Daily spend by product"
view. Amounts are decimal strings in CENTS -> divided by 100 for USD.

Auth: x-api-key: $ANALYTICS_API_KEY  +  anthropic-version: 2023-06-01  (per
platform.claude.com/docs/en/manage-claude/analytics-api). The fetched data is per-org
cost — identity-bearing — so output stays in worktemp/ (gitignored), never upward.

Requirements you must satisfy (I cannot do these for you):
  1. Enterprise Primary Owner creates an Analytics API key at
     claude.ai > Organization settings > API, and puts it in .env as ANALYTICS_API_KEY.
  2. Cost/usage endpoints report real $ only on usage-based Enterprise plans; seat-based
     plans reflect usage credits only. Data ≥ 2026-01-01; may revise for up to 30 days.

Usage:
  fetch_usage_cloud.py [--days N | --since YYYY-MM-DD [--until YYYY-MM-DD]]
                       [--bucket 1d|1h|1m] [--out worktemp/cloud-usage.json]
                       [--print-request]   # show the URL it WOULD call (no key needed) and exit
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_OUT = os.path.join(ROOT, "worktemp", "cloud-usage.json")
LIMITS = os.path.join(ROOT, "config", "usage-limits.json")

API_BASE = os.environ.get("ANTHROPIC_ANALYTICS_BASE", "https://api.anthropic.com")
COST_PATH = "/v1/organizations/analytics/cost_report"
API_VERSION = "2023-06-01"
MIN_DATE = "2026-01-01T00:00:00Z"


def die(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def rfc3339(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_window_from_config():
    """Default the window to config/usage-limits.json .window (days) if present."""
    if not os.path.isfile(LIMITS):
        return None
    try:
        w = (json.load(open(LIMITS, encoding="utf-8")) or {}).get("window") or {}
    except (OSError, json.JSONDecodeError):
        return None
    if w.get("mode") == "days" and w.get("days"):
        return int(w["days"])
    return None


def build_query(since, until, bucket, page):
    # list params use bracket notation, repeated per value
    pairs = [("starting_at", since), ("bucket_width", bucket),
             ("group_by[]", "product"), ("group_by[]", "model")]
    if until:
        pairs.append(("ending_at", until))
    if page:
        pairs.append(("page", page))
    return urllib.parse.urlencode(pairs)


def request_page(url, key):
    req = urllib.request.Request(url, headers={
        "x-api-key": key,
        "anthropic-version": API_VERSION,
        "User-Agent": "aocc-personal-ai-coach/0.1 (local monitor)",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        die(f"HTTP {e.code} from analytics API: {body}")
    except urllib.error.URLError as e:
        die(f"network error calling analytics API: {e.reason}")


def aggregate(pages):
    """Fold raw cost_report pages into per-product totals + a daily-by-product series."""
    by_product, daily = {}, {}
    refreshed = None
    for pg in pages:
        refreshed = pg.get("data_refreshed_at") or refreshed
        for bucket in pg.get("data", []):
            day = (bucket.get("starting_at") or "")[:10]
            dslot = daily.setdefault(day, {"date": day, "total_cents": Decimal(0), "by_product": {}})
            for r in bucket.get("results", []):
                prod = r.get("product") or "(ungrouped)"
                cents = Decimal(str(r.get("amount") or "0"))
                by_product[prod] = by_product.get(prod, Decimal(0)) + cents
                dslot["total_cents"] += cents
                dslot["by_product"][prod] = dslot["by_product"].get(prod, Decimal(0)) + cents
    def usd(c):
        return float(c / Decimal(100))
    prods = [{"product": p, "spent_usd": usd(c)} for p, c in by_product.items()]
    prods.sort(key=lambda x: -x["spent_usd"])
    days = []
    for day in sorted(daily.keys()):
        d = daily[day]
        days.append({"date": day, "total_usd": usd(d["total_cents"]),
                     "by_product": {p: usd(c) for p, c in d["by_product"].items()}})
    total = usd(sum(by_product.values(), Decimal(0)))
    return prods, days, total, refreshed


def main():
    ap = argparse.ArgumentParser(description="Fetch Claude Enterprise Analytics cost by product (opt-in, egress).")
    ap.add_argument("--days", type=int, default=None, help="rolling window: last N days (default: config window or 7)")
    ap.add_argument("--since", default=None, help="window start YYYY-MM-DD (>= 2026-01-01)")
    ap.add_argument("--until", default=None, help="window end YYYY-MM-DD (max span 31 days)")
    ap.add_argument("--bucket", default="1d", choices=["1d", "1h", "1m"])
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--print-request", action="store_true",
                    help="print the request URL that WOULD be sent (no key/network) and exit")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    if args.since:
        since = f"{args.since}T00:00:00Z"
    else:
        days = args.days or load_window_from_config() or 7
        since = rfc3339(now - timedelta(days=days))
        if since < MIN_DATE:
            since = MIN_DATE
    until = f"{args.until}T00:00:00Z" if args.until else None

    query = build_query(since, until, args.bucket, page=None)
    url = f"{API_BASE}{COST_PATH}?{query}"

    if args.print_request:
        print("GET " + url)
        print("headers: x-api-key: <ANALYTICS_API_KEY>, anthropic-version: " + API_VERSION)
        return

    key = os.environ.get("ANALYTICS_API_KEY", "").strip()
    if not key:
        print("cloud fetch SKIPPED: ANALYTICS_API_KEY not set (air-gap preserved).")
        print("To enable: Enterprise Primary Owner creates an Analytics API key at")
        print("  claude.ai > Organization settings > API  (scope read:analytics),")
        print("  then set ANALYTICS_API_KEY in .env. This is the ONLY script that egresses.")
        return  # exit 0 — intentionally a no-op when not configured

    # paginate: repeat with next_page until has_more is false
    pages, page, guard = [], None, 0
    while True:
        guard += 1
        if guard > 50:
            die("pagination guard tripped (>50 pages) — aborting")
        u = f"{API_BASE}{COST_PATH}?{build_query(since, until, args.bucket, page)}"
        pg = request_page(u, key)
        pages.append(pg)
        if pg.get("has_more") and pg.get("next_page"):
            page = pg["next_page"]
        else:
            break

    by_product, daily, total, refreshed = aggregate(pages)
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "source": "claude-enterprise-analytics/cost_report",
        "data_refreshed_at": refreshed,
        "window": {"since": since, "until": until, "bucket": args.bucket},
        "currency": "USD",
        "total_spent_usd": total,
        "by_product": by_product,
        "daily": daily,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    print(f"ok: fetched {len(pages)} page(s); total ${total:,.2f} across "
          f"{len(by_product)} product(s) -> {os.path.relpath(args.out, ROOT)}")
    for r in by_product:
        print(f"   {r['product']:<16} ${r['spent_usd']:,.2f}")
    print("note: EGRESS call was made to api.anthropic.com (opt-in cloud fetcher).")


if __name__ == "__main__":
    main()
