#!/usr/bin/env python3
"""
validate_extraction.py — fail-closed validation of Phase-2 extraction output.

Validates a capability-signals JSON (array of per-session objects, or a single object) against
config/extraction.schema.json. Also runs a belt-and-suspenders RL4-i CONTENT check: no evidence_ref
/ growth_hint may contain an obvious identity/path/email token (the schema can't express "no
verbatim", so this is a mechanical backstop).

Usage:
  validate_extraction.py <path-to-signals.json>

Exit 0 = all objects valid + clean; non-zero = at least one failed (loud).
"""

import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
SCHEMA_PATH = os.path.join(ROOT, "config", "extraction.schema.json")

# RL4-i backstop: identity/path/email/repo patterns that must NOT appear in abstract signal fields.
IDENT_RE = re.compile(
    r"(/home/[A-Za-z0-9_]+|/Users/[A-Za-z0-9_]+|/mnt/[a-z]/"
    r"|https?://|github\.com|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
)
# RL4-ii backstop: growth_hint must not carry score/rung/tier vocabulary.
SCORE_RE = re.compile(r"(\brung\b|\btier\b|\bR[0-7]\b|\bscore\b|評分|分數|評比)", re.IGNORECASE)


def die(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def content_check(obj, idx):
    """RL4 content backstop over one per-session object. Returns list of problems."""
    problems = []
    for dom, sig in (obj.get("domain_signals") or {}).items():
        for ref in (sig.get("evidence_refs") or []):
            if IDENT_RE.search(ref):
                problems.append(f"[{idx}] {dom}.evidence_refs identity/path leak: {ref!r}")
        hint = sig.get("growth_hint")
        if hint:
            if IDENT_RE.search(hint):
                problems.append(f"[{idx}] {dom}.growth_hint identity/path leak: {hint!r}")
            if SCORE_RE.search(hint):
                problems.append(f"[{idx}] {dom}.growth_hint score/rung/tier word: {hint!r}")
    for bf in (obj.get("bias_flags") or []):
        if IDENT_RE.search(bf.get("observed", "")):
            problems.append(f"[{idx}] bias_flags.observed identity/path leak: {bf.get('observed')!r}")
    return problems


def main():
    if len(sys.argv) != 2:
        die("usage: validate_extraction.py <path-to-signals.json>")
    target = sys.argv[1]
    if not os.path.isfile(target):
        die(f"signals file not found: {target}")
    if not os.path.isfile(SCHEMA_PATH):
        die(f"schema not found: {SCHEMA_PATH}")

    try:
        import jsonschema
    except ImportError:
        die("jsonschema not installed (see manifest.yaml python_libs)")

    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        schema = json.load(fh)
    with open(target, encoding="utf-8") as fh:
        data = json.load(fh)

    objs = data if isinstance(data, list) else [data]
    validator = jsonschema.Draft7Validator(schema)

    n_ok = 0
    n_fail = 0
    problems = []
    for i, obj in enumerate(objs):
        errs = sorted(validator.iter_errors(obj), key=lambda e: e.path)
        if errs:
            n_fail += 1
            for e in errs:
                loc = "/".join(str(p) for p in e.path) or "(root)"
                problems.append(f"[{i}] schema: {loc}: {e.message}")
            continue
        cprobs = content_check(obj, i)
        if cprobs:
            n_fail += 1
            problems.extend(cprobs)
        else:
            n_ok += 1

    if problems:
        print(f"FAIL: {n_fail} object(s) invalid, {n_ok} ok:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)
    print(f"PASS: {n_ok} object(s) valid + RL4-clean (schema + identity/score backstop)")


if __name__ == "__main__":
    main()
