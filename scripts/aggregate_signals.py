#!/usr/bin/env python3
"""
aggregate_signals.py — Phase 3 deterministic aggregate (fence-tolerant merge + fail-closed).

The extract-capability skill spawns parallel Phase-2 sub-agents; each returns a JSON ARRAY of
per-session capability-signal objects. Merging that used to be an LLM-improvised step inside the
skill, and a LIVE sub-agent wrapped its JSON in a ```json fence — which broke the hand-merge
(personal repo STATE Next Action #3). Per this project's own discipline ("a rule in prose is
silently skipped; it needs a structural gate" — agent-build-patterns / architectural-invariants),
the merge is moved OUT of the prose skill into this deterministic, fence-tolerant helper.

What it does:
  1. Read each sub-agent output (a file path, or '-' for stdin). Each may be a bare JSON array /
     object, OR wrapped in ```json ... ``` / ``` ... ``` fences, OR have incidental prose around a
     fenced block. Parsing cascades until one strategy yields JSON (never trusts the fence to be
     absent).
  2. Flatten every parsed value into a flat list of per-session objects.
  3. Validate each object fail-closed against config/extraction.schema.json.
  4. Drop + LOUDLY log any invalid object (never silent — RL4 honesty). Write the survivors to
     raw-sessions/capability-signals.json.

Exit posture (fail-closed by default):
  - exit non-zero if ANY object was dropped (default) — a malformed sub-agent output must surface,
    not vanish. Pass --drop-invalid to tolerate drops and still exit 0 (the drops are still logged).
  - exit non-zero if ZERO valid objects survive (an empty signals file would break Phase 3/4).

Usage:
  aggregate_signals.py <sub-agent-out.json> [<more>...]      # merge N sub-agent output files
  aggregate_signals.py -                                     # read one sub-agent output from stdin
  aggregate_signals.py <...> --out raw-sessions/capability-signals.json [--drop-invalid]
"""

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
SCHEMA_PATH = os.path.join(ROOT, "config", "extraction.schema.json")
DEFAULT_OUT = os.path.join(ROOT, "raw-sessions", "capability-signals.json")


def die(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def _first_json_value(text):
    """Return the first well-formed JSON array/object embedded anywhere in text, or None.

    Scans for a leading '[' or '{' and uses raw_decode so trailing prose after the value is
    tolerated. This is the last-resort strategy when fences are malformed or prose surrounds it.
    """
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch in "[{":
            try:
                val, _end = decoder.raw_decode(text[i:])
                return val
            except json.JSONDecodeError:
                continue
    return None


def parse_agent_output(raw, label):
    """Fence-tolerant parse of ONE sub-agent output string. die() loudly if nothing parses.

    Cascade (each step is tried only if the previous failed — we NEVER assume the fence is absent):
      1. bare JSON as-is;
      2. strip a single wrapping ```lang ... ``` fence, then parse;
      3. the interior of the first ``` ... ``` block found anywhere;
      4. the first balanced JSON value embedded anywhere (prose-tolerant).
    """
    text = raw.strip()
    if not text:
        die(f"{label}: empty sub-agent output")

    # 1. bare JSON.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. single wrapping fence: ```json\n...\n``` (or any / no language tag).
    if text.startswith("```"):
        body = text[3:]
        nl = body.find("\n")
        if nl != -1:
            body = body[nl + 1:]          # drop the ```lang line
        if body.rstrip().endswith("```"):
            body = body.rstrip()[:-3]     # drop the closing fence
        try:
            return json.loads(body.strip())
        except json.JSONDecodeError:
            pass

    # 3. first fenced block anywhere in the text.
    open_idx = text.find("```")
    if open_idx != -1:
        after = text.find("\n", open_idx)
        close_idx = text.find("```", after + 1) if after != -1 else -1
        if after != -1 and close_idx != -1:
            inner = text[after + 1:close_idx].strip()
            try:
                return json.loads(inner)
            except json.JSONDecodeError:
                pass

    # 4. first balanced JSON value embedded anywhere.
    val = _first_json_value(text)
    if val is not None:
        return val

    die(f"{label}: could not parse JSON from sub-agent output (tried bare / fenced / embedded)")


def flatten(value):
    """A parsed value is either a per-session object or a list of them. Return a flat list."""
    if isinstance(value, list):
        out = []
        for v in value:
            out.extend(flatten(v))
        return out
    return [value]


def main():
    ap = argparse.ArgumentParser(description="Phase 3 deterministic fence-tolerant aggregate.")
    ap.add_argument("inputs", nargs="+",
                    help="sub-agent output files (JSON, possibly ```-fenced); '-' = stdin")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help=f"merged output (default: {os.path.relpath(DEFAULT_OUT, ROOT)})")
    ap.add_argument("--drop-invalid", action="store_true",
                    help="tolerate dropped invalid objects and still exit 0 (drops still logged)")
    args = ap.parse_args()

    if not os.path.isfile(SCHEMA_PATH):
        die(f"schema not found: {SCHEMA_PATH}")
    try:
        import jsonschema
    except ImportError:
        die("jsonschema not installed (see manifest.yaml python_libs)")
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        schema = json.load(fh)
    validator = jsonschema.Draft7Validator(schema)

    # Collect + parse every sub-agent output (fence-tolerant).
    objs = []
    for src in args.inputs:
        if src == "-":
            raw, label = sys.stdin.read(), "<stdin>"
        else:
            if not os.path.isfile(src):
                die(f"input not found: {src}")
            with open(src, encoding="utf-8") as fh:
                raw = fh.read()
            label = os.path.relpath(src, ROOT)
        objs.extend(flatten(parse_agent_output(raw, label)))

    # Validate each object fail-closed; drop + LOUDLY log invalid ones (never silent).
    valid, dropped = [], 0
    for i, obj in enumerate(objs):
        errs = sorted(validator.iter_errors(obj), key=lambda e: list(e.path))
        if errs:
            dropped += 1
            print(f"DROP: object[{i}] failed schema (not written):", file=sys.stderr)
            for e in errs:
                loc = "/".join(str(p) for p in e.path) or "(root)"
                print(f"  - {loc}: {e.message}", file=sys.stderr)
        else:
            valid.append(obj)

    if not valid:
        die(f"no valid per-session objects after aggregate ({dropped} dropped) — refusing to "
            f"write an empty signals file (would break Phase 3/4).")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(valid, fh, ensure_ascii=False, indent=2)

    print(f"ok: aggregated {len(valid)} valid per-session object(s) from {len(args.inputs)} "
          f"sub-agent output(s) → {args.out}")
    if dropped:
        print(f"{'note' if args.drop_invalid else 'FAIL'}: {dropped} object(s) DROPPED "
              f"(logged above).", file=sys.stderr)
        if not args.drop_invalid:
            print("      re-run the failing sub-agent, or pass --drop-invalid to tolerate.",
                  file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
