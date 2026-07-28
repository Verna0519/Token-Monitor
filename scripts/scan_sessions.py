#!/usr/bin/env python3
"""
scan_sessions.py — Phase-1 session scanner (deterministic, stdlib-only).

Forked-in-spirit from ai-article session-ingest Phase-1. Resolves the local Claude Code CLI
transcript root via the path-mappings indirection (RL2: no logic-baked paths), lists jsonl
sessions within a window, and emits a SESSION INDEX (metadata only — paths, line counts, message
counts, time range). It does NOT read message content and does NOT extract signals — that is
Phase 2 (parallel sub-agents). Keeping scan/extract separate keeps the mechanical backbone testable.

RL4 note: the index is written to worktemp/ (PRIVATE, gitignored). It records absolute session
paths (identity-bearing: the paths encode the cwd/username) — that is fine INSIDE the private layer;
the de-id gate ensures nothing identity-bearing reaches the UPWARD digest (Phase 2/4), not that the
private layer is path-free.

Usage:
  scan_sessions.py [--project SUBSTR|all] [--days N] [--max N] [--out PATH]

  --project  substring match against the url-encoded project dir name, or 'all' (default: all)
  --days     only sessions whose newest mtime is within N days (default: no limit)
  --max      cap the number of sessions in the index (default: 30, session-ingest convention)
  --out      output path for the index JSON (default: worktemp/session-index.json)

Exit non-zero (loud) if the path-mappings root is unset/missing (RL2 resolution contract).
"""

import argparse
import json
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)


def die(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def resolve_projects_root():
    """Resolve CLAUDE_PROJECTS_ROOT via path-mappings.filled.yaml (RL2 single indirection).

    Loud non-zero exit if the filled mapping is absent or the token is unset — never silent-fail.
    Minimal YAML read (KEY: "value") to avoid a hard pyyaml dependency for this backbone script.
    """
    filled = os.path.join(ROOT, "config", "path-mappings.filled.yaml")
    if not os.path.isfile(filled):
        die("config/path-mappings.filled.yaml missing — copy path-mappings.yaml and set "
            "CLAUDE_PROJECTS_ROOT (RL2 resolution contract).")
    root = None
    with open(filled, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("CLAUDE_PROJECTS_ROOT:"):
                val = line.split(":", 1)[1].strip().strip('"').strip("'")
                root = val
                break
    if not root or root.startswith("<set me"):
        die("CLAUDE_PROJECTS_ROOT is unset in path-mappings.filled.yaml (RL2 contract).")
    if not os.path.isdir(root):
        die(f"CLAUDE_PROJECTS_ROOT does not resolve to a directory: {root}")
    return root


def session_meta(path):
    """Cheap metadata pass over one jsonl: line count, user/assistant counts, time span.

    Reads the file but keeps NO content — only counts + first/last timestamps.
    """
    lines = 0
    n_user = n_assistant = 0
    first_ts = last_ts = None
    try:
        with open(path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                lines += 1
                try:
                    o = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                t = o.get("type")
                if t == "user":
                    n_user += 1
                elif t == "assistant":
                    n_assistant += 1
                ts = o.get("timestamp")
                if ts:
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts
    except OSError as e:
        return {"error": str(e)}
    return {
        "lines": lines,
        "user_msgs": n_user,
        "assistant_msgs": n_assistant,
        "first_ts": first_ts,
        "last_ts": last_ts,
    }


def main():
    ap = argparse.ArgumentParser(description="Phase-1 session scanner (metadata only).")
    ap.add_argument("--project", default="all",
                    help="substring match on the encoded project dir, or 'all'")
    ap.add_argument("--days", type=int, default=None,
                    help="only sessions with mtime within N days")
    ap.add_argument("--max", type=int, default=30, help="cap sessions in the index")
    ap.add_argument("--out", default=os.path.join(ROOT, "worktemp", "session-index.json"))
    args = ap.parse_args()

    projects_root = resolve_projects_root()

    # Collect jsonl files, most-recent first by mtime.
    entries = []
    for dirpath, _dirs, files in os.walk(projects_root):
        for name in files:
            if not name.endswith(".jsonl"):
                continue
            full = os.path.join(dirpath, name)
            proj = os.path.relpath(dirpath, projects_root)
            # Skip NESTED subagent/workflow transcripts: those are a sub-agent's own conversation,
            # not the person's direct usage. The person's orchestration surfaces in the MAIN session
            # (via Task/tool calls). A personal-capability read wants the person driving, not the
            # spawned agents. (Refine in Phase 1b if orchestration signals warrant re-including them.)
            # P-W-04: normalize separators so the exclusion also fires on native-Windows backslash
            # paths (os.walk yields "\" there; a bare "/subagents/" test would silently no-op and
            # ingest foreign sub-agent transcripts).
            full_posix = full.replace(os.sep, "/")
            if "/subagents/" in full_posix or "/workflows/" in full_posix:
                continue
            if args.project != "all" and args.project not in proj:
                continue
            try:
                mtime = os.path.getmtime(full)
            except OSError:
                continue
            entries.append((mtime, full, proj))
    entries.sort(reverse=True)

    now = time.time()
    cutoff = now - args.days * 86400 if args.days else None

    sessions = []
    for mtime, full, proj in entries:
        if cutoff is not None and mtime < cutoff:
            continue
        if len(sessions) >= args.max:
            break
        meta = session_meta(full)
        sessions.append({
            "path": full,
            "project": proj,
            "mtime_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(mtime)),
            **meta,
        })

    index = {
        "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        "projects_root": projects_root,
        "filter": {"project": args.project, "days": args.days, "max": args.max},
        "total_jsonl_seen": len(entries),
        "sessions_in_index": len(sessions),
        "sessions": sessions,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)

    print(f"ok: scanned {len(entries)} jsonl under {projects_root}")
    print(f"ok: {len(sessions)} session(s) in index (project='{args.project}', "
          f"days={args.days}, max={args.max})")
    print(f"ok: index written to {args.out}")


if __name__ == "__main__":
    main()
