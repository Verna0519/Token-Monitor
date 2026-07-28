#!/usr/bin/env python3
"""
coverage_report.py — per-axis evidence coverage over the extracted signals (mechanical, local).

Answers "which axes can the coordinate assessment place, and which need more evidence?" — the
targeting tool for the 契約選補證據 ruling (2026-07-15): an unplaceable axis is fixed by extracting
more sessions that exercise it, never by loosening the contract or defaulting to level 0.

Reads raw-sessions/capability-signals.json (one object per extracted session) and reports, per
axis: sessions with a signal present, tier counts (intended/structural/actual), and a coverage
verdict. Prints only — changes nothing.

Usage:
  coverage_report.py [--signals raw-sessions/capability-signals.json]
"""

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)

TIERS = ["intended", "structural", "actual"]


def die(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="Per-axis evidence coverage report.")
    ap.add_argument("--signals", default=os.path.join(ROOT, "raw-sessions", "capability-signals.json"))
    args = ap.parse_args()

    with open(os.path.join(ROOT, "config", "extraction.schema.json"), encoding="utf-8") as fh:
        axes = json.load(fh)["properties"]["domain_signals"]["required"]
    try:
        with open(args.signals, encoding="utf-8") as fh:
            sessions = json.load(fh)
    except OSError as e:
        die(f"cannot read {args.signals}: {e}")
    except json.JSONDecodeError as e:
        die(f"{args.signals}: not valid JSON — {e}")
    if not isinstance(sessions, list) or not sessions:
        die(f"{args.signals}: expected a non-empty JSON array of per-session extractions")

    print(f"coverage over {len(sessions)} extracted session(s):\n")
    print(f"  {'AXIS':22} {'present':>7}  {'intended':>8} {'structural':>10} {'actual':>6}  verdict")
    targets = []
    for axis in axes:
        present = 0
        tiers = {t: 0 for t in TIERS}
        refs = 0
        for s in sessions:
            d = (s.get("domain_signals") or {}).get(axis) or {}
            if d.get("present"):
                present += 1
                t = d.get("signal_tier")
                if t in tiers:
                    tiers[t] += 1
                refs += len(d.get("evidence_refs") or [])
        if present == 0:
            verdict = "NO SIGNAL — collect evidence (unplaceable)"
            targets.append(axis)
        elif tiers["actual"] == 0 and tiers["structural"] == 0:
            verdict = "intended-only — thin (places conservatively at best)"
            targets.append(axis)
        elif present == 1:
            verdict = "single session — placeable but thin"
        else:
            verdict = "ok"
        print(f"  {axis:22} {present:>7}  {tiers['intended']:>8} {tiers['structural']:>10} "
              f"{tiers['actual']:>6}  {verdict}")
    print()
    if targets:
        print(f"extraction targets (補證據): {', '.join(targets)} — scan/extract sessions that "
              f"exercise these axes, then re-run the coordinate assessment.")
    else:
        print("all axes have non-intended evidence — the coordinate assessment can attempt a full placement.")


if __name__ == "__main__":
    main()
