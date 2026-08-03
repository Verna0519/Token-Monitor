#!/usr/bin/env python3
"""
token_report.py — LOCAL token-usage report, aggregated by conversation / project / skill.

Token spend does NOT happen in this repo's scripts (§5: they make no LLM call). It happens in the
Claude Code interactive runtime, which records every turn to ~/.claude/projects/**/*.jsonl — the
SAME read-only corpus scan_sessions.py ingests. Each assistant turn carries message.usage with the
token counts. This tool reads that corpus (read-only, RL2-resolved) and rolls the usage up three
ways a normal user cares about:

  - by CONVERSATION (session, with its title + time span)
  - by PROJECT (the working directory the turns ran in)
  - by SKILL (Claude Code's attributionSkill on each turn)

Times are in TAIWAN time (UTC+8) by default — display and the --since/--until/--days window both.
Filtering is by each turn's own timestamp (accurate per-interval spend), not file mtime.

Air-gapped like the rest of the monitor: pure stdlib, NO egress. Output is stdout + an optional
worktemp/token-usage.json (PRIVATE, gitignored) that render_dashboard.py picks up. Project paths and
conversation titles are identity-bearing, so this stays LOCAL — it is never an upward artifact.

Coverage honesty: by default only the person's MAIN sessions are counted; nested sub-agent /
workflow transcripts are excluded (add --include-nested). Turns with no timestamp are skipped when a
window is set (can't be placed) and the count is reported — silence about them would be dishonest.

Usage:
  token_report.py [--project SUBSTR|all] [--days N | --since YYYY-MM-DD [--until YYYY-MM-DD]]
                  [--utc-offset 8] [--include-nested] [--top N] [--json-out worktemp/token-usage.json]
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

# Conversation titles are arbitrary Unicode (CJK, emoji). The Windows console defaults to a
# legacy codepage (e.g. Big5/cp950) that can't encode them, which would crash the stdout table
# print BEFORE the JSON is written. Force UTF-8 with replacement so a title never breaks the run.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_JSON = os.path.join(ROOT, "worktemp", "token-usage.json")

TOKKEYS = ["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"]
_DATE_FMTS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
              "%Y-%m-%dT%H:%M", "%Y-%m-%d"]


def die(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def resolve_projects_root():
    """RL2 single indirection — same contract as scan_sessions.py (loud non-zero on unset/missing)."""
    filled = os.path.join(ROOT, "config", "path-mappings.filled.yaml")
    if not os.path.isfile(filled):
        die("config/path-mappings.filled.yaml missing — copy path-mappings.yaml and set "
            "CLAUDE_PROJECTS_ROOT (RL2 resolution contract).")
    root = None
    with open(filled, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("CLAUDE_PROJECTS_ROOT:"):
                root = line.split(":", 1)[1].strip().strip('"').strip("'")
                break
    if not root or root.startswith("<set me"):
        die("CLAUDE_PROJECTS_ROOT is unset in path-mappings.filled.yaml (RL2 contract).")
    if not os.path.isdir(root):
        die(f"CLAUDE_PROJECTS_ROOT does not resolve to a directory: {root}")
    return root


def parse_ts(ts):
    """Transcript timestamp (UTC ISO, e.g. 2026-07-28T01:26:08.289Z) -> aware UTC datetime, or None."""
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def parse_local_dt(s, tz, end=False):
    """Parse a user-supplied date/datetime as LOCAL (tz) time -> aware datetime. Date-only + end -> 23:59:59."""
    s = s.strip()
    for f in _DATE_FMTS:
        try:
            dt = datetime.strptime(s, f)
            break
        except ValueError:
            dt = None
    if dt is None:
        die(f"cannot parse date {s!r} (use YYYY-MM-DD or 'YYYY-MM-DD HH:MM')")
    if f == "%Y-%m-%d" and end:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt.replace(tzinfo=tz)


def tw_str(ts, tz):
    dt = parse_ts(ts)
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M") if dt else (ts or "")


def zero():
    return defaultdict(int)


def total_of(d):
    return sum(d.get(k, 0) for k in TOKKEYS)


def collect(projects_root, project_filter, include_nested, since, until, tz):
    by_conv, by_proj, by_skill, by_day = {}, defaultdict(zero), defaultdict(zero), defaultdict(zero)
    by_agent = defaultdict(zero)                       # who did the work: (main thread) + each subagent type
    conv_day = defaultdict(lambda: defaultdict(zero))  # per-conversation daily breakdown (session -> day -> tokens)
    # cross-tabs so each row can NAME its members (which chats / which skills)
    members = {"project": defaultdict(lambda: defaultdict(int)),   # project -> session -> tokens
               "skill":   defaultdict(lambda: defaultdict(int)),   # skill   -> session -> tokens
               "agent":   defaultdict(lambda: defaultdict(int)),   # agent   -> session -> tokens
               "conv_skills": defaultdict(lambda: defaultdict(int))}  # session -> skill -> tokens
    conv_meta = {}
    grand = zero()
    life = zero()   # ALL-TIME totals, ignoring the window (used for lifetime pools e.g. the credit)
    stats = {"files": 0, "nested_files": 0, "skipped_no_ts": 0, "skipped_out_window": 0}

    for dirpath, _dirs, files in os.walk(projects_root):
        for name in files:
            if not name.endswith(".jsonl"):
                continue
            full = os.path.join(dirpath, name)
            posix = full.replace(os.sep, "/")
            nested = ("/subagents/" in posix or "/workflows/" in posix)
            proj_dir = os.path.relpath(dirpath, projects_root)
            if project_filter != "all" and project_filter not in proj_dir:
                continue
            # nested files are ALWAYS read (for the By-agent lens), but only feed the standard
            # conversation/project/skill/day lenses when --include-nested is set.
            if nested and not include_nested:
                stats["nested_files"] += 1
            else:
                stats["files"] += 1
            _read_file(full, nested, include_nested, by_conv, conv_meta, by_proj, by_skill,
                       by_day, by_agent, conv_day, grand, since, until, tz, stats, life, members)

    return by_conv, conv_meta, by_proj, by_skill, by_day, by_agent, conv_day, grand, stats, life, members


def _read_file(path, nested, include_nested, by_conv, conv_meta, by_proj, by_skill,
               by_day, by_agent, conv_day, grand, since, until, tz, stats, life=None, members=None):
    count_main = (not nested) or include_nested   # feed the standard lenses?
    windowed = since is not None or until is not None
    try:
        fh = open(path, encoding="utf-8")
    except OSError:
        return
    with fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                o = json.loads(raw)
            except json.JSONDecodeError:
                continue
            sess = o.get("sessionId", "?")
            if count_main:
                meta = conv_meta.setdefault(sess, {"title": None, "project": None,
                                                    "first_ts": None, "last_ts": None, "file": None})
                if meta.get("file") is None:
                    meta["file"] = path            # transcript file this chat was read from (local ref/link)
                if o.get("customTitle"):
                    meta["title"] = o.get("customTitle")
                elif o.get("aiTitle") and not meta["title"]:
                    meta["title"] = o.get("aiTitle")
                if o.get("cwd"):
                    meta["project"] = o.get("cwd")

            if o.get("type") != "assistant":
                continue
            usage = (o.get("message") or {}).get("usage") or {}
            if not usage:
                continue

            # ALL-TIME tally (pre-window), same scope as `grand` (standard lenses only)
            if life is not None and count_main:
                for k in TOKKEYS:
                    life[k] += usage.get(k, 0) or 0
                life["msgs"] += 1

            dt = parse_ts(o.get("timestamp"))
            if windowed:
                if dt is None:
                    stats["skipped_no_ts"] += 1
                    continue
                if (since and dt < since) or (until and dt > until):
                    stats["skipped_out_window"] += 1
                    continue

            day = dt.astimezone(tz).strftime("%Y-%m-%d") if dt is not None else None
            # By-agent lens: ALWAYS (main-thread turns -> '(main thread)', subagent turns -> their type)
            agent = o.get("attributionAgent") or "(main thread)"
            for k in TOKKEYS:
                by_agent[agent][k] += usage.get(k, 0) or 0
            by_agent[agent]["msgs"] += 1

            if not count_main:
                continue  # nested file & not --include-nested: standard lenses skip it

            # track the in-window time span for the session
            if dt is not None:
                if meta["first_ts"] is None or dt < parse_ts(meta["first_ts"]):
                    meta["first_ts"] = o.get("timestamp")
                if meta["last_ts"] is None or dt > parse_ts(meta["last_ts"]):
                    meta["last_ts"] = o.get("timestamp")

            cwd = o.get("cwd") or "(unknown project)"
            skill = o.get("attributionSkill") or "(no skill)"
            cbucket = by_conv.setdefault(sess, zero())
            for k in TOKKEYS:
                v = usage.get(k, 0) or 0
                cbucket[k] += v
                by_proj[cwd][k] += v
                by_skill[skill][k] += v
                grand[k] += v
                if day is not None:
                    by_day[day][k] += v
                    conv_day[sess][day][k] += v
            cbucket["msgs"] += 1
            by_proj[cwd]["msgs"] += 1
            by_skill[skill]["msgs"] += 1
            grand["msgs"] += 1
            if day is not None:
                by_day[day]["msgs"] += 1
                conv_day[sess][day]["msgs"] += 1
            # cross-tabs: which chats make up this project / skill / agent (for named drilldowns)
            if members is not None:
                _t = sum(usage.get(k, 0) or 0 for k in TOKKEYS)
                members["project"][cwd][sess] += _t
                members["skill"][skill][sess] += _t
                members["agent"][agent][sess] += _t
                members["conv_skills"][sess][skill] += _t


def _rows(bucket_map, key_name, tz, meta=None):
    rows = []
    for key, d in bucket_map.items():
        if not d.get("msgs"):
            continue  # session existed but had no in-window assistant turns
        row = {key_name: key, "msgs": d.get("msgs", 0), "total": total_of(d)}
        for k in TOKKEYS:
            row[k] = d.get(k, 0)
        if meta and key in meta:
            m = meta[key]
            row.update({"title": m.get("title"), "project": m.get("project"),
                        "file": m.get("file"),
                        "first_tw": tw_str(m.get("first_ts"), tz),
                        "last_tw": tw_str(m.get("last_ts"), tz)})
        rows.append(row)
    rows.sort(key=lambda r: -r["total"])
    return rows


def fmt(n):
    return f"{n:,}"


def print_table(title, rows, label_key, top, label_fn=None):
    print(f"\n=== {title} (top {top} by total tokens) ===")
    print(f"  {'':<38}  {'total':>13}  {'output':>10}  {'input':>7}  {'cache_read':>12}  {'msgs':>5}")
    for r in rows[:top]:
        label = (label_fn(r) if label_fn else str(r.get(label_key, "")))[:38]
        print(f"  {label:<38}  {fmt(r['total']):>13}  {fmt(r['output_tokens']):>10}  "
              f"{fmt(r['input_tokens']):>7}  {fmt(r['cache_read_input_tokens']):>12}  {r['msgs']:>5}")


def main():
    ap = argparse.ArgumentParser(description="Local token-usage report by conversation/project/skill (Taiwan time).")
    ap.add_argument("--project", default="all", help="substring match on the project dir, or 'all'")
    ap.add_argument("--days", type=int, default=None, help="rolling window: only turns within the last N days")
    ap.add_argument("--since", default=None, help="window start (YYYY-MM-DD or 'YYYY-MM-DD HH:MM'), Taiwan time")
    ap.add_argument("--until", default=None, help="window end (inclusive), Taiwan time")
    ap.add_argument("--utc-offset", type=int, default=8, help="display/window timezone offset (default 8 = Taiwan)")
    ap.add_argument("--include-nested", action="store_true",
                    help="also count nested sub-agent/workflow transcripts (default: excluded)")
    ap.add_argument("--top", type=int, default=10, help="rows to show per section (default 10)")
    ap.add_argument("--json-out", default=DEFAULT_JSON, help="write machine-readable JSON here ('-' to skip)")
    args = ap.parse_args()

    tz = timezone(timedelta(hours=args.utc_offset))
    tzlabel = f"UTC+{args.utc_offset}" if args.utc_offset >= 0 else f"UTC{args.utc_offset}"

    since = until = None
    if args.days is not None:
        if args.since or args.until:
            die("use --days OR --since/--until, not both")
        now_local = datetime.now(timezone.utc).astimezone(tz)
        since = now_local - timedelta(days=args.days)
    else:
        if args.since:
            since = parse_local_dt(args.since, tz)
        if args.until:
            until = parse_local_dt(args.until, tz, end=True)

    root = resolve_projects_root()
    by_conv, conv_meta, by_proj, by_skill, by_day, by_agent, conv_day, grand, stats, life, members = collect(
        root, args.project, args.include_nested, since, until, tz)

    conv_rows = _rows(by_conv, "session", tz, conv_meta)
    # attach each conversation's per-day breakdown (Feature: single-conversation daily detail)
    for r in conv_rows:
        cd = conv_day.get(r["session"], {})
        r["by_day"] = [{"date": day, "total": total_of(cd[day]), "msgs": cd[day].get("msgs", 0)}
                       for day in sorted(cd.keys())]
    # name each conversation (title if known, else short session id) for the drilldowns
    conv_name = {}
    for sess, m in conv_meta.items():
        conv_name[sess] = (m.get("title") or sess[:8])
    def named(bucket, key):
        """Turn {session: tokens} into a named, sorted member list for a row's drilldown."""
        d = bucket.get(key) or {}
        out = [{"session": s, "name": conv_name.get(s, s[:8]), "total": v} for s, v in d.items() if v]
        out.sort(key=lambda x: -x["total"])
        return out

    proj_rows = _rows(by_proj, "project", tz)
    for r in proj_rows:
        r["members"] = named(members["project"], r["project"])
    skill_rows = _rows(by_skill, "skill", tz)
    for r in skill_rows:
        r["members"] = named(members["skill"], r["skill"])
    agent_rows = _rows(by_agent, "agent", tz)
    for r in agent_rows:
        r["members"] = named(members["agent"], r["agent"])
    agent_total = sum(r["total"] for r in agent_rows)
    # which skills each conversation used (shown inside a chat's drilldown)
    for r in conv_rows:
        sk = members["conv_skills"].get(r["session"]) or {}
        r["skills"] = sorted([{"skill": k, "total": v} for k, v in sk.items() if v],
                             key=lambda x: -x["total"])
    day_rows = []
    for day in sorted(by_day.keys()):
        d = by_day[day]
        day_rows.append({"date": day, "total": total_of(d), "msgs": d.get("msgs", 0),
                         **{k: d.get(k, 0) for k in TOKKEYS}})

    gtot = total_of(grand)
    win = "all time" if not (since or until) else (
        f"{since.strftime('%Y-%m-%d %H:%M') if since else '...'} -> "
        f"{until.strftime('%Y-%m-%d %H:%M') if until else 'now'}")
    print(f"projects_root: {root}")
    print(f"timezone: {tzlabel} (Taiwan default)   window: {win}")
    print(f"counted: {stats['files']} transcript file(s); nested sub-agent/workflow = "
          f"{'INCLUDED' if args.include_nested else 'excluded'}."
          + (f"  skipped {stats['skipped_out_window']} out-of-window"
             f" + {stats['skipped_no_ts']} no-timestamp turn(s)."
             if (since or until) else ""))
    print(f"\nGRAND TOTAL: {fmt(gtot)} tokens  "
          f"(output {fmt(grand['output_tokens'])}, input {fmt(grand['input_tokens'])}, "
          f"cache_write {fmt(grand['cache_creation_input_tokens'])}, "
          f"cache_read {fmt(grand['cache_read_input_tokens'])})")
    print("note: 'total' is dominated by cache_read -- context re-read each turn, billed at a "
          "fraction of fresh input. 'output' is what the model generated.")

    print_table("By conversation", conv_rows, "session", args.top,
                label_fn=lambda r: (r.get("title") or r["session"][:12]))
    print_table("By project", proj_rows, "project", args.top,
                label_fn=lambda r: os.path.basename(str(r["project"]).rstrip("/\\")) or str(r["project"]))
    print_table("By skill", skill_rows, "skill", args.top)
    print_table("By agent (incl. nested subagents/workflows)", agent_rows, "agent", args.top)
    print(f"  (By agent total {fmt(agent_total)} = main thread {fmt(gtot)} + "
          f"{fmt(agent_total - gtot)} nested; {stats.get('nested_files', 0)} nested file(s))")

    if args.json_out and args.json_out != "-":
        payload = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "scope": {"projects_root": root, "files_counted": stats["files"],
                      "include_nested": args.include_nested, "project_filter": args.project,
                      "timezone": tzlabel, "utc_offset": args.utc_offset,
                      "window_since": since.strftime("%Y-%m-%d %H:%M") if since else None,
                      "window_until": until.strftime("%Y-%m-%d %H:%M") if until else None,
                      "skipped_no_ts": stats["skipped_no_ts"],
                      "skipped_out_window": stats["skipped_out_window"]},
            "totals": {**{k: grand[k] for k in TOKKEYS}, "total": gtot, "msgs": grand.get("msgs", 0)},
            "lifetime": {**{k: life[k] for k in TOKKEYS}, "total": total_of(life),
                         "msgs": life.get("msgs", 0)},
            "by_conversation": conv_rows,
            "by_project": proj_rows,
            "by_skill": skill_rows,
            "by_agent": agent_rows,
            "by_agent_total": agent_total,
            "by_day": day_rows,
        }
        os.makedirs(os.path.dirname(args.json_out), exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"\nok: machine-readable JSON -> {os.path.relpath(args.json_out, ROOT)} "
              f"(private; render_dashboard.py picks it up)")


if __name__ == "__main__":
    main()
