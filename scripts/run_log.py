#!/usr/bin/env python3
"""
run_log.py — LOCAL, air-gapped execution monitor for this agent's skills / agents / scripts.

This is the in-repo, zero-egress alternative to an external tracing service (Langfuse Cloud &c.):
it gives per-skill / per-agent / per-script visibility (status, duration, key counts) WITHOUT any
runtime call leaving this machine. It is a deliberate design choice for this repo's red lines:

  - RL1 (Runtime Self-Contained): pure stdlib, NO network, NO external service. Nothing is sent
    anywhere. This script never calls an LLM/API (§5) — it only records what already happened.
  - RL2 (Machine-Portable): no logic-baked absolute paths — the log path resolves off this repo's
    root (like every other backbone script).
  - RL4 (Directed Visibility Seam): the trace is written to worktemp/ (PRIVATE, gitignored). Like
    worktemp/session-index.json it may contain absolute paths in a wrapped command's stdout tail —
    that is fine INSIDE the private layer and NEVER reaches the upward coordinate. It records COUNTS
    and outcomes, not extracted evidence text.

It is NON-INVASIVE: it modifies no existing script. You monitor a step either by WRAPPING a
mechanical command, or by INGESTING the artifacts a skill / workflow already produced, or by
appending a manual EVENT for an interactive skill/agent step.

Subcommands
  new-run                         print a fresh run id (export RUN_LOG_RUN_ID=... to group a pipeline)
  wrap  --step NAME [--kind K] -- <cmd...>
                                  run <cmd> as a local subprocess; record status/exit/duration + a
                                  short stdout/stderr tail. (mechanical scripts: scan/aggregate/...)
  event --step NAME --status ok|fail|running [--kind K] [--unit U] [--kv k=v ...] [--note TEXT]
                                  append one manual event (interactive skill/agent step)
  ingest-skill  [--dir worktemp] [--glob 'agent-out-*.json'] [--step extract-capability]
                                  one event per extract-capability sub-agent output (session count)
  ingest-scan   [--index worktemp/session-index.json] [--step scan]
                                  record scan VOLUME (sessions_in_index / total_jsonl_seen) as metrics
  ingest-workflow --result FILE [--step emit-coordinate]
                                  one event per emit-coordinate per-axis agent (axis + level/placed)
  report [--runs N] [--json]      render the local run summary (the "dashboard")
  trend [--last N] [--json]       coordinate-placement trend across runs (placed/total over time)
  coverage [--last N] [--json]    coverage/volume trend (sessions/jsonl/sub-agents/signals over time)
  clear                           truncate the run log (worktemp scratch hygiene)

All state lives in worktemp/run-log.jsonl (one JSON event per line, append-only).
"""

import argparse
import json
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_LOG = os.path.join(ROOT, "worktemp", "run-log.jsonl")
TAIL_CHARS = 600  # cap the stdout/stderr tail we retain (keep the log small; abstract-leaning)


def die(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def gen_run_id():
    """Short, sortable-ish local id. os.urandom (not the Math.random/Date ban — that is JS only)."""
    return "run-" + time.strftime("%Y%m%dT%H%M%S", time.localtime()) + "-" + os.urandom(3).hex()


def current_run_id(args):
    return getattr(args, "run_id", None) or os.environ.get("RUN_LOG_RUN_ID") or gen_run_id()


def append_event(log_path, ev):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")


def base_event(args, *, kind, step, status, **rest):
    ev = {
        "ts": now_iso(),
        "run_id": current_run_id(args),
        "kind": kind,
        "step": step,
        "status": status,
    }
    ev.update({k: v for k, v in rest.items() if v is not None})
    return ev


def parse_kv(pairs):
    """['sessions=30', 'placed=6'] -> {'sessions': 30, 'placed': 6} (ints where possible)."""
    out = {}
    for p in pairs or []:
        if "=" not in p:
            die(f"--kv expects key=value, got {p!r}")
        k, v = p.split("=", 1)
        try:
            out[k] = int(v)
        except ValueError:
            out[k] = v
    return out


def tail(text, n=TAIL_CHARS):
    text = (text or "").strip()
    return text[-n:] if len(text) > n else text


# ---- fence-tolerant JSON parse (mirrors aggregate_signals.py so ingest matches real outputs) ----

def first_json_value(text):
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch in "[{":
            try:
                val, _ = dec.raw_decode(text[i:])
                return val
            except json.JSONDecodeError:
                continue
    return None


def parse_agent_output(raw):
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    if text.startswith("```"):
        body = text[3:]
        nl = body.find("\n")
        if nl != -1:
            body = body[nl + 1:]
        if body.rstrip().endswith("```"):
            body = body.rstrip()[:-3]
        try:
            return json.loads(body.strip())
        except json.JSONDecodeError:
            pass
    return first_json_value(text)


# ---- subcommands ----

def cmd_new_run(args):
    print(current_run_id(args))


def cmd_wrap(args):
    if not args.cmd:
        die("wrap needs a command after '--', e.g. wrap --step scan -- python scripts/scan_sessions.py")
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        die("empty command after '--'")
    run_id = current_run_id(args)
    append_event(args.log, base_event(args, kind=args.kind, step=args.step, status="running",
                                       unit=cmd[0], run_id=run_id))
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as e:
        append_event(args.log, base_event(args, kind=args.kind, step=args.step, status="fail",
                                           unit=cmd[0], note=f"could not launch: {e}", run_id=run_id))
        die(f"could not launch {cmd[0]!r}: {e}")
    dur_ms = int((time.monotonic() - start) * 1000)
    status = "ok" if proc.returncode == 0 else "fail"
    ev = base_event(args, kind=args.kind, step=args.step, status=status, unit=cmd[0],
                    duration_ms=dur_ms, exit_code=proc.returncode, run_id=run_id,
                    note=tail(proc.stdout if status == "ok" else (proc.stderr or proc.stdout)))
    append_event(args.log, ev)
    # transparently pass through the child's own output + exit code
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    print(f"[run_log] {args.step}: {status} in {dur_ms}ms (exit {proc.returncode})", file=sys.stderr)
    sys.exit(proc.returncode)


def cmd_event(args):
    ev = base_event(args, kind=args.kind, step=args.step, status=args.status,
                    unit=args.unit, note=args.note)
    kv = parse_kv(args.kv)
    if kv:
        ev["metrics"] = kv
    append_event(args.log, ev)
    print(f"[run_log] event: {args.step} ({args.kind}) {args.status}", file=sys.stderr)


def cmd_ingest_skill(args):
    import glob as _glob
    base = args.dir if os.path.isabs(args.dir) else os.path.join(ROOT, args.dir)
    files = sorted(_glob.glob(os.path.join(base, args.glob)))
    if not files:
        die(f"no sub-agent outputs matched {args.glob!r} under {base}")
    run_id = current_run_id(args)
    total_sessions = 0
    for f in files:
        label = os.path.relpath(f, ROOT)
        try:
            with open(f, encoding="utf-8") as fh:
                val = parse_agent_output(fh.read())
        except OSError as e:
            append_event(args.log, base_event(args, kind="agent", step=args.step, status="fail",
                                               unit=label, note=str(e), run_id=run_id))
            continue
        if val is None:
            append_event(args.log, base_event(args, kind="agent", step=args.step, status="fail",
                                               unit=label, note="unparseable output", run_id=run_id))
            continue
        sessions = val if isinstance(val, list) else [val]
        n = len(sessions)
        total_sessions += n
        append_event(args.log, base_event(args, kind="agent", step=args.step, status="ok",
                                           unit=label, run_id=run_id,
                                           metrics={"session_objects": n}))
    append_event(args.log, base_event(args, kind="skill", step=args.step, status="ok",
                                       unit=args.step, run_id=run_id,
                                       metrics={"subagents": len(files),
                                                "session_objects": total_sessions}))
    print(f"[run_log] ingest-skill: {len(files)} sub-agent output(s), "
          f"{total_sessions} session object(s)", file=sys.stderr)


def cmd_ingest_scan(args):
    """Record scan VOLUME as structured metrics from worktemp/session-index.json.

    `wrap --step scan` captures scan's status/duration, but its session count lives only in the
    stdout note (unstructured). This reads the index the scan just wrote and logs the counts as
    real metrics, so the coverage trend has a clean per-run data point.
    """
    path = args.index if os.path.isabs(args.index) else os.path.join(ROOT, args.index)
    if not os.path.isfile(path):
        die(f"session index not found: {path} — run scan_sessions.py first")
    with open(path, encoding="utf-8") as fh:
        idx = json.load(fh)
    metrics = {
        "sessions_in_index": idx.get("sessions_in_index", len(idx.get("sessions", []))),
        "total_jsonl_seen": idx.get("total_jsonl_seen", 0),
    }
    append_event(args.log, base_event(args, kind="script", step=args.step, status="ok",
                                       unit="session-index", metrics=metrics))
    print(f"[run_log] ingest-scan: {metrics['sessions_in_index']} session(s) in index, "
          f"{metrics['total_jsonl_seen']} jsonl seen", file=sys.stderr)


def cmd_ingest_workflow(args):
    path = args.result if os.path.isabs(args.result) else os.path.join(ROOT, args.result)
    if not os.path.isfile(path):
        die(f"workflow result not found: {path}")
    with open(path, encoding="utf-8") as fh:
        val = parse_agent_output(fh.read())
    results = val.get("results") if isinstance(val, dict) else None
    if not isinstance(results, list) or not results:
        die("result must be the emit-coordinate return object {format, results:[...]}")
    run_id = current_run_id(args)
    placed = 0
    for entry in results:
        if not isinstance(entry, dict):
            continue
        axis = entry.get("axis", "?")
        level = entry.get("level")
        is_placed = level is not None
        placed += 1 if is_placed else 0
        append_event(args.log, base_event(args, kind="agent", step=args.step, status="ok",
                                           unit=axis, run_id=run_id,
                                           metrics={"level": level, "placed": int(is_placed)}))
    total = len(results)
    append_event(args.log, base_event(args, kind="workflow", step=args.step, status="ok",
                                       unit=args.step, run_id=run_id,
                                       metrics={"axes": total, "placed": placed,
                                                "unplaced": total - placed}))
    print(f"[run_log] ingest-workflow: {total} axis agent(s), {placed} placed, "
          f"{total - placed} unplaced", file=sys.stderr)


def _load_events(log_path):
    if not os.path.isfile(log_path):
        return []
    events = []
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def cmd_report(args):
    events = _load_events(args.log)
    if not events:
        print("run log empty — nothing recorded yet "
              f"({os.path.relpath(args.log, ROOT)})")
        return
    if args.json:
        print(json.dumps(events, ensure_ascii=False, indent=2))
        return

    # group by run_id, preserving first-seen order
    runs = {}
    for ev in events:
        runs.setdefault(ev.get("run_id", "(no-run-id)"), []).append(ev)
    run_ids = list(runs.keys())[-args.runs:]

    icon = {"ok": "ok  ", "fail": "FAIL", "running": "... "}
    for rid in run_ids:
        evs = [e for e in runs[rid] if e.get("status") != "running"]
        if not evs:
            evs = runs[rid]
        span = f"{evs[0].get('ts', '?')} -> {evs[-1].get('ts', '?')}"
        ok = sum(1 for e in evs if e.get("status") == "ok")
        fail = sum(1 for e in evs if e.get("status") == "fail")
        print(f"\n== {rid}   {span}   ({ok} ok / {fail} fail)")
        for e in evs:
            st = icon.get(e.get("status"), e.get("status", "?"))
            dur = f"{e['duration_ms']}ms" if "duration_ms" in e else "-"
            exit_c = f"exit{e['exit_code']}" if "exit_code" in e else ""
            metrics = e.get("metrics", {})
            mstr = " ".join(f"{k}={v}" for k, v in metrics.items())
            print(f"   [{st}] {e.get('kind',''):<8} {e.get('step',''):<18} "
                  f"{e.get('unit',''):<22} {dur:>7} {exit_c:<6} {mstr}")

    total = sum(1 for e in events if e.get("status") != "running")
    fails = sum(1 for e in events if e.get("status") == "fail")
    print(f"\n{total} recorded step(s) across {len(runs)} run(s); {fails} failure(s). "
          f"log: {os.path.relpath(args.log, ROOT)}")


def cmd_trend(args):
    """Coordinate-placement trend: placed/total axes per run over time, with delta + unplaced axes.

    Reads across ALL recorded runs and, for each run that ran an emit-coordinate assessment, plots
    how many axes placed. This is the growth signal — is the coordinate filling in over time? The
    per-run 'still unplaced' column names exactly what to collect evidence for next (補證據).
    """
    events = _load_events(args.log)
    runs = {}
    for ev in events:
        runs.setdefault(ev.get("run_id", "(no-run-id)"), []).append(ev)

    rows = []
    for rid, evs in runs.items():
        wf = next((e for e in reversed(evs)
                   if e.get("kind") == "workflow" and e.get("step") == args.step), None)
        axis_evs = [e for e in evs if e.get("kind") == "agent" and e.get("step") == args.step]
        if wf is None and not axis_evs:
            continue  # this run had no coordinate assessment — skip
        if wf is not None:
            m = wf.get("metrics", {})
            placed = m.get("placed", 0)
            total = m.get("axes", len(axis_evs) or 8)
        else:
            placed = sum(1 for e in axis_evs if e.get("metrics", {}).get("placed") == 1)
            total = len(axis_evs) or 8
        unplaced = sorted(e.get("unit", "?") for e in axis_evs
                          if e.get("metrics", {}).get("placed") == 0)
        ts = evs[0].get("ts", "?")
        rows.append({"run_id": rid, "ts": ts, "placed": placed, "total": total,
                     "unplaced": unplaced})

    rows.sort(key=lambda r: r["ts"])
    if args.last:
        rows = rows[-args.last:]

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("no coordinate-assessment runs recorded yet — run ingest-workflow after an "
              "emit-coordinate assessment to start the trend.")
        return

    print("\nCoordinate placement trend  (placed / total axes)\n")
    print(f"  {'when':<19}  {'placed':>7}  {'progress':<12}  {'chg':>3}  still unplaced")
    print(f"  {'-'*19}  {'-'*7}  {'-'*12}  {'-'*3}  {'-'*30}")
    prev = None
    for r in rows:
        filled = r["placed"]
        total = r["total"] or 8
        bar = "[" + "#" * filled + "." * max(0, total - filled) + "]"
        delta = "" if prev is None else (f"+{filled - prev}" if filled > prev
                                         else (str(filled - prev) if filled < prev else "="))
        unp = ", ".join(r["unplaced"]) if r["unplaced"] else "(none - 8/8 placed)"
        print(f"  {r['ts']:<19}  {filled:>3}/{total:<3}  {bar:<12}  {delta:>3}  {unp}")
        prev = filled
    last = rows[-1]
    print(f"\nlatest: {last['placed']}/{last['total']} axes placed across {len(rows)} "
          f"assessment run(s).")
    if last["unplaced"]:
        print(f"next: collect more evidence for {', '.join(last['unplaced'])}, "
              f"re-assess, re-emit.")


def cmd_coverage(args):
    """Coverage / volume trend: per run over time, how much was scanned & extracted.

    Answers "is my evidence base growing?" — sessions scanned, jsonl seen, extract sub-agents,
    and extracted signal objects. A thin evidence base is a coverage blind spot (never proof of low
    capability), so watching this rise is how you know a re-assessment rests on more ground.
    """
    events = _load_events(args.log)
    runs = {}
    for ev in events:
        runs.setdefault(ev.get("run_id", "(no-run-id)"), []).append(ev)

    rows = []
    for rid, evs in runs.items():
        scan = next((e for e in reversed(evs)
                     if e.get("step") == "scan" and "sessions_in_index" in e.get("metrics", {})),
                    None)
        skill = next((e for e in reversed(evs)
                      if e.get("kind") == "skill" and e.get("step") == "extract-capability"), None)
        if scan is None and skill is None:
            continue
        sm = scan.get("metrics", {}) if scan else {}
        km = skill.get("metrics", {}) if skill else {}
        rows.append({
            "ts": evs[0].get("ts", "?"),
            "sessions": sm.get("sessions_in_index"),
            "jsonl_seen": sm.get("total_jsonl_seen"),
            "subagents": km.get("subagents"),
            "signals": km.get("session_objects"),
        })

    rows.sort(key=lambda r: r["ts"])
    if args.last:
        rows = rows[-args.last:]

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("no scan/extract volume recorded yet — run `ingest-scan` after scan and "
              "`ingest-skill` after extract-capability to start the coverage trend.")
        return

    def cell(v):
        return "-" if v is None else str(v)

    print("\nCoverage / volume trend  (evidence base over time)\n")
    print(f"  {'when':<19}  {'sessions':>8}  {'jsonl_seen':>10}  {'subagents':>9}  {'signals':>7}")
    print(f"  {'-'*19}  {'-'*8}  {'-'*10}  {'-'*9}  {'-'*7}")
    for r in rows:
        print(f"  {r['ts']:<19}  {cell(r['sessions']):>8}  {cell(r['jsonl_seen']):>10}  "
              f"{cell(r['subagents']):>9}  {cell(r['signals']):>7}")
    last = rows[-1]
    print(f"\nlatest: {cell(last['sessions'])} session(s) scanned, "
          f"{cell(last['signals'])} extracted signal object(s) across "
          f"{len(rows)} run(s).")


def cmd_clear(args):
    if os.path.isfile(args.log):
        os.remove(args.log)
        print(f"cleared {os.path.relpath(args.log, ROOT)}")
    else:
        print("run log already empty")


def build_parser():
    ap = argparse.ArgumentParser(description="Local air-gapped execution monitor (no egress).")
    ap.add_argument("--log", default=DEFAULT_LOG, help=f"log path (default: {os.path.relpath(DEFAULT_LOG, ROOT)})")
    ap.add_argument("--run-id", default=None, help="override run id (else $RUN_LOG_RUN_ID or fresh)")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("new-run", help="print a fresh run id").set_defaults(func=cmd_new_run)

    w = sub.add_parser("wrap", help="run a command and record its outcome")
    w.add_argument("--step", required=True)
    w.add_argument("--kind", default="script")
    w.add_argument("cmd", nargs=argparse.REMAINDER, help="-- <command ...>")
    w.set_defaults(func=cmd_wrap)

    e = sub.add_parser("event", help="append a manual event")
    e.add_argument("--step", required=True)
    e.add_argument("--status", required=True, choices=["ok", "fail", "running"])
    e.add_argument("--kind", default="skill")
    e.add_argument("--unit", default=None)
    e.add_argument("--kv", nargs="*", default=[])
    e.add_argument("--note", default=None)
    e.set_defaults(func=cmd_event)

    s = sub.add_parser("ingest-skill", help="event per extract-capability sub-agent output")
    s.add_argument("--dir", default="worktemp")
    s.add_argument("--glob", default="agent-out-*.json")
    s.add_argument("--step", default="extract-capability")
    s.set_defaults(func=cmd_ingest_skill)

    isc = sub.add_parser("ingest-scan", help="record scan volume from the session index")
    isc.add_argument("--index", default=os.path.join("worktemp", "session-index.json"))
    isc.add_argument("--step", default="scan")
    isc.set_defaults(func=cmd_ingest_scan)

    iw = sub.add_parser("ingest-workflow", help="event per emit-coordinate per-axis agent")
    iw.add_argument("--result", required=True)
    iw.add_argument("--step", default="emit-coordinate")
    iw.set_defaults(func=cmd_ingest_workflow)

    r = sub.add_parser("report", help="render the local run summary")
    r.add_argument("--runs", type=int, default=5, help="show the last N runs (default 5)")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_report)

    t = sub.add_parser("trend", help="coordinate-placement trend across runs (placed/8 over time)")
    t.add_argument("--step", default="emit-coordinate", help="assessment step to trend")
    t.add_argument("--last", type=int, default=None, help="only the last N assessment runs")
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=cmd_trend)

    cov = sub.add_parser("coverage", help="coverage/volume trend (sessions/signals over time)")
    cov.add_argument("--last", type=int, default=None, help="only the last N runs")
    cov.add_argument("--json", action="store_true")
    cov.set_defaults(func=cmd_coverage)

    sub.add_parser("clear", help="truncate the run log").set_defaults(func=cmd_clear)
    return ap


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
