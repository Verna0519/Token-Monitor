#!/usr/bin/env python3
"""
emit_coordinate.py — turn the emit-coordinate workflow result into a capability-coordinate upload.
Mechanical only: the JUDGMENT (evidence -> per-axis level) is done by the workflow (one agent per
axis, grounded in that axis's rung rubric); this script validates, mints a fresh opaque
submission_id, and writes the two artifacts:

  1. handoff/coordinate-<sid>.json — the UPLOAD. Carries ONLY
     {format, version, submission_id, period, position}. This is the only file that may leave
     this machine (a human carries it to the dept map's inbox/).
  2. output/coordinate-basis-<sid>.md — LOCAL ONLY. The per-axis basis + rationale (the WHY).
     Never carried anywhere; a level is a position on the map, not a grade.

Unplaced axes (level=null — evidence cannot place the axis; level 0 is an OBSERVED low-maturity
pattern, never a default for "no data") — RULED 2026-07-15 ("契約選補證據"): the contract stays
STRICT at version "0.1" (all 8 axes int 0-3). An unplaced axis means COLLECT MORE EVIDENCE —
extract more sessions that exercise it, re-assess, re-emit. This script refuses to emit until
every axis places; there is no nullable escape hatch.

Usage:
  emit_coordinate.py --from-workflow result.json [--period 2026-07]
"""

import argparse
import json
import os
import secrets
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)

AXES = ["DESIGN", "FRAMEWORK-SELECTION", "CODING", "TUNING",
        "CONTEXT-ENGINEERING", "EVAL", "ADVISORY", "CONTINUITY"]


def die(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_workflow(raw):
    """Validate the emit-coordinate result fail-closed. Returns {axis: entry} covering AXES exactly."""
    try:
        wf = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        die(f"--from-workflow input not valid JSON: {e}")
    results = wf.get("results") if isinstance(wf, dict) else None
    if not isinstance(results, list) or not results:
        die("--from-workflow input must be the workflow return object {format, results: [...]}")
    entries = {}
    for entry in results:
        if not isinstance(entry, dict):
            die(f"results entry must be an object, got {entry!r}")
        axis = entry.get("axis")
        if axis in entries:
            die(f"duplicate axis '{axis}' in workflow results")
        if axis not in AXES:
            die(f"unknown axis '{axis}' in workflow results")
        level = entry.get("level")
        if level is not None and (not isinstance(level, int) or isinstance(level, bool)
                                  or not (0 <= level <= 3)):
            die(f"axis '{axis}': level must be an int in [0,3] or null, got {level!r}")
        entries[axis] = entry
    missing = [a for a in AXES if a not in entries]
    if missing:
        die(f"workflow results missing axes {missing} — a per-axis agent was dropped; re-run the workflow")
    return entries


def main():
    ap = argparse.ArgumentParser(description="Emit a capability-coordinate upload from the workflow result.")
    ap.add_argument("--from-workflow", required=True, help="emit-coordinate result JSON ('-' for stdin)")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "handoff"))
    ap.add_argument("--basis-dir", default=os.path.join(ROOT, "output"))
    ap.add_argument("--period", default=None, help="optional period tag (e.g. 2026-07); default null")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.from_workflow == "-" else None
    if raw is None:
        try:
            with open(args.from_workflow, encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as e:
            die(f"cannot read {args.from_workflow}: {e}")
    entries = parse_workflow(raw)

    unplaced = [a for a in AXES if entries[a]["level"] is None]
    if unplaced:
        die(f"axes {unplaced} are UNPLACED — the contract stays strict (ruled 2026-07-15: "
            f"契約選補證據). COLLECT MORE EVIDENCE: extract more sessions that exercise "
            f"{unplaced}, re-run the assessment workflow, then re-emit. (Level 0 is observed "
            f"low-maturity behavior, never a default for missing evidence.)")
    version = "0.1"

    sid = "sub-" + secrets.token_hex(8)
    coordinate = {
        "format": "capability-coordinate",
        "version": version,
        "submission_id": sid,
        "period": args.period,
        "position": {a: entries[a]["level"] for a in AXES},
    }

    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, f"coordinate-{sid}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(coordinate, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    os.makedirs(args.basis_dir, exist_ok=True)
    basis_path = os.path.join(args.basis_dir, f"coordinate-basis-{sid}.md")
    with open(basis_path, "w", encoding="utf-8") as fh:
        fh.write(f"# Coordinate basis — {sid} (LOCAL ONLY, never carried)\n\n")
        fh.write("> A level is a POSITION on the learning map, not a grade — and it measures how you\n"
                 "> OPERATE AI, not your domain/professional expertise (a zone fit never claims\n"
                 "> professional qualification; ruled 2026-07-15). This file holds the per-axis\n"
                 "> evidence basis + rationale; only the coordinate JSON leaves this machine.\n\n")
        for a in AXES:
            e = entries[a]
            lvl = e["level"] if e["level"] is not None else "unplaced (null)"
            fh.write(f"## {a}: {lvl}\n\n- **basis**: {e.get('basis', '')}\n"
                     f"- **rationale**: {e.get('rationale', '')}\n\n")

    print(f"ok: coordinate {sid} written -> {out_path}  (version {version}; 8/8 axes placed)")
    print(f"ok: local basis (stays here)  -> {basis_path}")


if __name__ == "__main__":
    main()
