#!/usr/bin/env python3
"""
cowork_report.py — LOCAL Cowork usage report, per chat room (session) + per day, with REAL $.

Cowork (the desktop app's "local agent mode") stores each session's audit log at
  <COWORK_SESSIONS_ROOT>/<install>/<org>/local_<sid>/audit.jsonl
Each `result` (subtype=success) entry in that audit carries BOTH `usage` (token counts) and
`total_cost_usd` (the REAL billed $ for that run) — so unlike the Claude Code CLI transcripts,
Cowork gives real money, not an estimate. We account ONE unit per `result` entry (the `system`
usage snapshots are ignored to avoid double-counting), grouped by session_id and by day.

This is a SECOND local read-only corpus for the Token Monitor ONLY. It never feeds the capability
extract/coordinate pipeline (that stays Claude Code CLI jsonl only, per CLAUDE.md §1). Output is
worktemp/cowork-usage.json (PRIVATE, gitignored) — session ids / cwd / org path are identity-bearing
and stay LOCAL; never an upward artifact.

Air-gapped: pure stdlib, NO egress. If the Cowork root is absent (no Cowork on this machine), it
no-ops cleanly (writes nothing / an empty marker) so the dashboard simply omits the Cowork block.

Usage:
  cowork_report.py [--days N | --since YYYY-MM-DD [--until YYYY-MM-DD]] [--utc-offset 8]
                   [--top N] [--json-out worktemp/cowork-usage.json]
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_JSON = os.path.join(ROOT, "worktemp", "cowork-usage.json")
FILLED = os.path.join(ROOT, "config", "path-mappings.filled.yaml")
TOKKEYS = ["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"]
_DATE_FMTS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"]


def resolve_cowork_root():
    """COWORK_SESSIONS_ROOT from path-mappings.filled.yaml if set; else the OS default. May be None."""
    if os.path.isfile(FILLED):
        try:
            for line in open(FILLED, encoding="utf-8"):
                line = line.strip()
                if line.startswith("COWORK_SESSIONS_ROOT:"):
                    v = line.split(":", 1)[1].strip().strip('"').strip("'")
                    if v and not v.startswith("<"):
                        return os.path.expanduser(os.path.expandvars(v))
        except OSError:
            pass
    default = os.path.expanduser(os.path.join("~", "AppData", "Roaming", "Claude", "local-agent-mode-sessions"))
    return default


def parse_ts(ts):
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def parse_local_dt(s, tz, end=False):
    s = s.strip()
    dt = None
    for f in _DATE_FMTS:
        try:
            dt = datetime.strptime(s, f)
            break
        except ValueError:
            dt = None
    if dt is None:
        print(f"FAIL: cannot parse date {s!r}", file=sys.stderr)
        sys.exit(1)
    if len(s) == 10 and end:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt.replace(tzinfo=tz)


def load_room_titles(root):
    """Map audit session_id -> real chat-room title.

    Each Cowork session has a sidecar `local_<uuid>.json` next to its folder carrying the
    room's `title` plus `cliSessionId` — and it is cliSessionId (not sessionId) that matches
    the `session_id` in audit.jsonl. Best-effort: unreadable/oversized sidecars are skipped.
    """
    titles = {}
    try:
        entries = os.listdir(root)
    except OSError:
        return titles
    for install in entries:
        idir = os.path.join(root, install)
        if not os.path.isdir(idir):
            continue
        for org in os.listdir(idir) if os.path.isdir(idir) else []:
            odir = os.path.join(idir, org)
            if not os.path.isdir(odir):
                continue
            for name in os.listdir(odir):
                if not (name.startswith("local_") and name.endswith(".json")):
                    continue
                p = os.path.join(odir, name)
                try:
                    d = json.load(open(p, encoding="utf-8", errors="replace"))
                except (OSError, json.JSONDecodeError, ValueError):
                    continue
                if not isinstance(d, dict):
                    continue
                sid = d.get("cliSessionId")
                title = d.get("title")
                if sid and isinstance(title, str) and title.strip():
                    titles[sid] = " ".join(title.split())[:70]
    return titles


def first_user_label(path):
    """A human-ish label for the chat room: first plain-text user message (skip file-upload markers)."""
    try:
        for raw in open(path, encoding="utf-8", errors="replace"):
            if '"type": "user"' not in raw and '"type":"user"' not in raw:
                continue
            try:
                o = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if o.get("type") != "user":
                continue
            c = (o.get("message") or {}).get("content")
            text = None
            if isinstance(c, str):
                text = c
            elif isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "text":
                        text = b.get("text")
                        break
            if text:
                text = " ".join(text.split())
                if text.startswith("<uploaded_files") or text.startswith("<"):
                    continue
                return text[:60]
    except OSError:
        pass
    return None


def main():
    ap = argparse.ArgumentParser(description="Local Cowork usage per chat room + per day, with real $ (audit.jsonl).")
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--since", default=None)
    ap.add_argument("--until", default=None)
    ap.add_argument("--utc-offset", type=int, default=8)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--json-out", default=DEFAULT_JSON)
    args = ap.parse_args()

    tz = timezone(timedelta(hours=args.utc_offset))
    tzlabel = f"UTC+{args.utc_offset}" if args.utc_offset >= 0 else f"UTC{args.utc_offset}"
    since = until = None
    if args.days is not None:
        since = datetime.now(timezone.utc).astimezone(tz) - timedelta(days=args.days)
    else:
        if args.since:
            since = parse_local_dt(args.since, tz)
        if args.until:
            until = parse_local_dt(args.until, tz, end=True)

    root = resolve_cowork_root()
    if not root or not os.path.isdir(root):
        print(f"cowork: no local Cowork sessions dir ({root}) — skipping (dashboard omits the block).")
        payload = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                   "available": False, "scope": {"root": root, "timezone": tzlabel}}
        os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
        json.dump(payload, open(args.json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return

    # walk audit.jsonl files
    audits = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name == "audit.jsonl":
                audits.append(os.path.join(dirpath, name))

    by_room = {}       # session_id -> aggregate
    room_day = defaultdict(lambda: defaultdict(lambda: {"cost": 0.0, "total": 0}))
    by_day = defaultdict(lambda: {"cost": 0.0, "total": 0, "results": 0})
    grand = {"cost": 0.0, "total": 0, "results": 0}
    life = {"cost": 0.0, "total": 0, "results": 0}   # ALL-TIME (ignores window)
    # token composition + per-model split, taken from modelUsage (same basis as costUSD, and more
    # complete than the top-level `usage` — it includes sub-agent turns).
    comp = {"input_tokens": 0, "output_tokens": 0,
            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    per_model = {}
    _MU = {"inputTokens": "input_tokens", "outputTokens": "output_tokens",
           "cacheCreationInputTokens": "cache_creation_input_tokens",
           "cacheReadInputTokens": "cache_read_input_tokens"}
    labels = {}
    windowed = since is not None or until is not None

    for path in audits:
        try:
            fh = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for raw in fh:
                if '"total_cost_usd"' not in raw:
                    continue
                try:
                    o = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if o.get("type") != "result":
                    continue  # ONE unit per result entry (avoids double-count with system snapshots)
                cost = o.get("total_cost_usd")
                if not isinstance(cost, (int, float)):
                    continue
                # tokens for this run: prefer modelUsage (matches costUSD, includes sub-agents)
                mu = o.get("modelUsage")
                if isinstance(mu, dict) and mu:
                    _t0 = 0
                    for _m, _d in mu.items():
                        if not isinstance(_d, dict):
                            continue
                        pm = per_model.setdefault(_m, {"cost": 0.0, "total": 0})
                        pm["cost"] += _d.get("costUSD", 0) or 0
                        for _src, _dst in _MU.items():
                            v = _d.get(_src, 0) or 0
                            _t0 += v
                            comp[_dst] += v
                            pm["total"] += v
                else:
                    _u0 = o.get("usage") or {}
                    _t0 = sum(_u0.get(k, 0) or 0 for k in TOKKEYS)
                    for k in TOKKEYS:
                        comp[k] += _u0.get(k, 0) or 0
                life["cost"] += cost; life["total"] += _t0; life["results"] += 1   # all-time, pre-window
                dt = parse_ts(o.get("timestamp"))
                if windowed:
                    if dt is None:
                        continue
                    if (since and dt < since) or (until and dt > until):
                        continue
                sid = o.get("session_id") or "?"
                toks = _t0                      # same basis as cost (modelUsage) — see above
                turns = o.get("num_turns") or 0
                day = dt.astimezone(tz).strftime("%Y-%m-%d") if dt is not None else None

                r = by_room.setdefault(sid, {"session": sid, "cost": 0.0, "total": 0, "results": 0,
                                             "turns": 0, "first_ts": None, "last_ts": None})
                r["cost"] += cost
                r["total"] += toks
                r["results"] += 1
                r["turns"] += turns
                ts_raw = o.get("timestamp")
                if dt is not None:
                    if r["first_ts"] is None or dt < parse_ts(r["first_ts"]):
                        r["first_ts"] = ts_raw
                    if r["last_ts"] is None or dt > parse_ts(r["last_ts"]):
                        r["last_ts"] = ts_raw
                grand["cost"] += cost
                grand["total"] += toks
                grand["results"] += 1
                if day is not None:
                    by_day[day]["cost"] += cost
                    by_day[day]["total"] += toks
                    by_day[day]["results"] += 1
                    room_day[sid][day]["cost"] += cost
                    room_day[sid][day]["total"] += toks
    # Room names: prefer the real title from the session sidecar (cliSessionId -> title);
    # fall back to the first plain-text user message in that session's audit.
    titles = load_room_titles(root)
    for sid in by_room:
        if titles.get(sid):
            by_room[sid]["label"] = titles[sid]
    for path in audits:
        try:
            for raw in open(path, encoding="utf-8", errors="replace"):
                if '"session_id"' not in raw:
                    continue
                try:
                    o = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                sid = o.get("session_id")
                if sid and sid in by_room and not by_room[sid].get("label"):
                    lbl = first_user_label(path)
                    if lbl:
                        by_room[sid]["label"] = lbl
                break
        except OSError:
            continue

    def tw(ts):
        d = parse_ts(ts)
        return d.astimezone(tz).strftime("%Y-%m-%d %H:%M") if d else ""

    rooms = []
    for sid, r in by_room.items():
        rooms.append({"session": sid, "label": r.get("label"),
                      "cost_usd": round(r["cost"], 4), "total": r["total"],
                      "results": r["results"], "turns": r["turns"],
                      "first_tw": tw(r["first_ts"]), "last_tw": tw(r["last_ts"]),
                      "by_day": [{"date": d, "cost_usd": round(room_day[sid][d]["cost"], 4),
                                  "total": room_day[sid][d]["total"]}
                                 for d in sorted(room_day[sid].keys())]})
    rooms.sort(key=lambda x: -x["cost_usd"])
    days = [{"date": d, "cost_usd": round(by_day[d]["cost"], 4), "total": by_day[d]["total"],
             "results": by_day[d]["results"]} for d in sorted(by_day.keys())]

    win_since = since.strftime("%Y-%m-%d %H:%M") if since else None
    win_until = until.strftime("%Y-%m-%d %H:%M") if until else None
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "available": True,
        "scope": {"root": root, "audit_files": len(audits), "timezone": tzlabel,
                  "window_since": win_since, "window_until": win_until},
        "totals": {"cost_usd": round(grand["cost"], 2), "total": grand["total"],
                   "rooms": len(rooms), "results": grand["results"]},
        "lifetime": {"cost_usd": round(life["cost"], 2), "total": life["total"],
                     "results": life["results"]},
        "composition": {**comp, "total": sum(comp.values()),
                        "basis": "modelUsage (same basis as costUSD; includes sub-agent turns)"},
        "by_model": sorted(
            [{"model": m, "cost_usd": round(d["cost"], 4), "total": d["total"],
              "usd_per_mtok": round(d["cost"] / d["total"] * 1e6, 4) if d["total"] else None}
             for m, d in per_model.items()], key=lambda x: -x["cost_usd"]),
        "by_room": rooms,
        "by_day": days,
    }
    os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
    json.dump(payload, open(args.json_out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print(f"cowork: {len(audits)} audit file(s); {len(rooms)} chat room(s); "
          f"real ${grand['cost']:,.2f}; {grand['total']:,} tokens over {grand['results']} runs "
          f"({tzlabel}{', window '+win_since if win_since else ''}).")
    for r in rooms[:args.top]:
        lab = (r.get("label") or r["session"][:8])[:40]
        print(f"   {lab:<42} ${r['cost_usd']:>9,.2f}  {r['total']:>13,} tok  {r['turns']} turns")
    print(f"-> {os.path.relpath(args.json_out, ROOT)} (private)")


if __name__ == "__main__":
    main()
