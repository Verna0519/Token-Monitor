#!/usr/bin/env python3
"""
count_tokens.py — estimate how many INPUT tokens a prompt will cost BEFORE you send it.

Two modes:
  - OFFLINE (default, air-gapped): a rough LOCAL heuristic (~chars/4, CJK-aware). No network,
    no key. Result is labelled "~approx".
  - EXACT (opt-in egress): if ANTHROPIC_API_KEY is set, calls Anthropic's
    POST /v1/messages/count_tokens and returns the real input_tokens for the chosen model.

  +-------------------------------------------------------------------------+
  | !! EXACT mode makes a NETWORK call (EGRESS) to api.anthropic.com. It is  |
  |    a DELIBERATE, OPT-IN exception to the repo air-gap (RL1), exactly     |
  |    like scripts/fetch_usage_cloud.py. It runs ONLY when YOU run this     |
  |    AND a key is set. No key -> offline heuristic, air-gap preserved.     |
  +-------------------------------------------------------------------------+

Scope: count_tokens counts INPUT ONLY (the prompt you would send) -- NOT output, NOT cache,
NOT actual billed usage. For real post-hoc "who spent what", use token_report.py (it reads the
actual message.usage the runtime already recorded). This tool is the "before you send" estimate.

Auth for EXACT mode: x-api-key: $ANTHROPIC_API_KEY  +  anthropic-version: 2023-06-01.
This is a regular Messages API key (NOT the read:analytics Analytics key used by fetch_usage_cloud).

Input (pick one; otherwise reads stdin):
  --text "..."      inline text
  --file PATH       read a file as the user message
  (piped stdin)     echo "hello" | count_tokens.py

Usage:
  count_tokens.py [--text T | --file F] [--system S] [--model M] [--print-request]
  count_tokens.py --file prompt.md
  echo "draft prompt" | count_tokens.py
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

# Titles / prompts are arbitrary Unicode; force UTF-8 stdout so a legacy console codepage
# (e.g. Big5/cp950) can't crash the print.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

API_BASE = os.environ.get("ANTHROPIC_API_BASE", "https://api.anthropic.com")
COUNT_PATH = "/v1/messages/count_tokens"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-4-8"


def die(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def read_input(args):
    if args.text is not None:
        return args.text
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                return fh.read()
        except OSError as e:
            die(f"cannot read --file {args.file}: {e}")
    if not sys.stdin.isatty():
        data = sys.stdin.read()
        if data.strip():
            return data
    die("no input: use --text, --file PATH, or pipe text via stdin")


def local_estimate(text, system):
    """Rough OFFLINE heuristic. Latin ~4 chars/token; CJK ~1.5 chars/token. Not exact."""
    s = (system or "") + "\n" + (text or "")
    cjk = sum(1 for c in s if "㐀" <= c <= "鿿" or "豈" <= c <= "﫿"
              or "぀" <= c <= "ヿ")
    other = len(s) - cjk
    return int(cjk / 1.5 + other / 4) + 8  # + small message/role overhead


def api_count(text, system, model, key):
    body = {"model": model, "messages": [{"role": "user", "content": text}]}
    if system:
        body["system"] = system
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(API_BASE + COUNT_PATH, data=data, method="POST", headers={
        "x-api-key": key,
        "anthropic-version": API_VERSION,
        "content-type": "application/json",
        "User-Agent": "aocc-token-monitor/0.1 (count_tokens)",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", "replace")[:400]
        die(f"HTTP {e.code} from count_tokens API: {body_txt}")
    except urllib.error.URLError as e:
        die(f"network error calling count_tokens API: {e.reason}")


def main():
    ap = argparse.ArgumentParser(
        description="Estimate INPUT tokens before sending: offline heuristic by default, "
                    "or exact via the Anthropic API when ANTHROPIC_API_KEY is set (opt-in egress).")
    ap.add_argument("--text", default=None, help="inline text to count")
    ap.add_argument("--file", default=None, help="read this file as the user message")
    ap.add_argument("--system", default=None, help="optional system prompt to include in the count")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"model id for the exact count (default {DEFAULT_MODEL})")
    ap.add_argument("--print-request", action="store_true",
                    help="print the request that WOULD be sent (no key/network) and exit")
    args = ap.parse_args()
    text = read_input(args)

    if args.print_request:
        print("POST " + API_BASE + COUNT_PATH)
        print("headers: x-api-key: <ANTHROPIC_API_KEY>, anthropic-version: " + API_VERSION)
        preview = {"model": args.model,
                   "system": args.system,
                   "messages": [{"role": "user", "content": f"<input, {len(text)} chars>"}]}
        print("body: " + json.dumps(preview, ensure_ascii=False))
        return

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        r = api_count(text, args.system, args.model, key)
        it = r.get("input_tokens")
        print(f"input_tokens (EXACT, {args.model}): {it:,}" if isinstance(it, int)
              else f"input_tokens (EXACT): {it}")
        print("note: EGRESS call was made to api.anthropic.com (opt-in). This counts INPUT only.")
    else:
        est = local_estimate(text, args.system)
        print(f"input_tokens (~approx, OFFLINE heuristic): ~{est:,}")
        print("for an EXACT count: set ANTHROPIC_API_KEY in .env then re-run "
              "(opt-in EGRESS to api.anthropic.com).")
        print("(heuristic ~= latin chars/4 + CJK/1.5; not exact. Counts INPUT only, not output/usage.)")


if __name__ == "__main__":
    main()
