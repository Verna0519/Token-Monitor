#!/usr/bin/env python3
"""
onboard.py — COLD-START FIX HELPER (writes the on-target config files the preflight flags).

The interactive AGENT (Claude) reads worktemp/preflight-report.json, asks the operator the Q&A the
report carries (zh-TW), and then calls THIS helper with the confirmed answers to write the private,
gitignored setup files. Splitting "decide" (agent, with the human) from "write" (this helper) keeps
the mechanical step deterministic + auditable and keeps interactive stdin OUT of any hook.

What it writes (all PRIVATE / gitignored — never a tracked path, RL4 gate (a)):
  --init-env                  cp .env.template -> .env               (idempotent; refuses overwrite)
  --init-state                cp config/STATE-template.md -> config/STATE.md
  --projects-root PATH        create config/path-mappings.filled.yaml from the template and set
                              CLAUDE_PROJECTS_ROOT = expanduser/expandvars(PATH) as an ABSOLUTE,
                              already-expanded path (fixes the ~/$ tilde trap the template invites).
  --normalize-eol             rewrite CRLF -> LF in PRIVATE (untracked) scripts/config files only
                              (WSL-03 / P-W-03). CRLF in a git-TRACKED file is REPORTED, never
                              rewritten — fix those via git (the delivered .gitattributes pins
                              eol=lf): `git add --renormalize .`.

Red-line posture:
- RL1/RL5: writes ONLY inside this repo; no network, no other-agent call, no ~/.claude write.
- RL2: no logic-baked absolute path (ROOT from __file__). A path that does not resolve to an
  existing dir is REFUSED loudly (non-zero) — this helper will not seed a broken root silently.
  It expands the value so the downstream scan_sessions.py check passes.
- RL4: every file it writes is a PRIVATE/gitignored instance; it NEVER edits a tracked template
  and NEVER writes a real path into the tracked config/path-mappings.yaml template.
- flag-don't-reinterpret: it does not GUESS a projects root; the agent must pass one the operator
  confirmed. With no actionable flag it prints usage and exits non-zero.

Usage (examples):
  python3 scripts/onboard.py --init-env --init-state
  python3 scripts/onboard.py --projects-root "$HOME/.claude/projects"
  python3 scripts/onboard.py --normalize-eol
"""

import argparse
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)


def die(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def ok(msg):
    print(f"ok: {msg}")


def warn(msg):
    print(f"warn: {msg}", file=sys.stderr)


def _copy_template(src_rel, dst_rel, allow_empty_src=False):
    src = os.path.join(ROOT, src_rel)
    dst = os.path.join(ROOT, dst_rel)
    if not os.path.isfile(src):
        die(f"template missing: {src_rel}")
    if os.path.exists(dst):
        ok(f"{dst_rel} already exists — left untouched (idempotent).")
        return
    with open(src, "rb") as fh:
        data = fh.read()
    if not data and not allow_empty_src:
        die(f"template is empty: {src_rel}")
    os.makedirs(os.path.dirname(dst) or ROOT, exist_ok=True)
    with open(dst, "wb") as fh:
        fh.write(data)
    ok(f"wrote {dst_rel} from {src_rel}.")


def init_env():
    # .env.template may legitimately be near-empty (Pilot needs no key) -> allow_empty_src.
    _copy_template(".env.template", ".env", allow_empty_src=True)


def init_state():
    _copy_template("config/STATE-template.md", "config/STATE.md")


def set_projects_root(raw):
    """Create config/path-mappings.filled.yaml (from the template) with an expanded, existing,
    absolute CLAUDE_PROJECTS_ROOT. Refuses a non-existent dir (RL2 loud-fail) instead of seeding a
    broken value the operator would only discover at scan time."""
    template = os.path.join(ROOT, "config", "path-mappings.yaml")
    filled = os.path.join(ROOT, "config", "path-mappings.filled.yaml")
    if not os.path.isfile(template):
        die("config/path-mappings.yaml template missing.")

    expanded = os.path.abspath(os.path.expanduser(os.path.expandvars(raw.strip())))
    if not os.path.isdir(expanded):
        die(f"projects root does not resolve to an existing directory: {expanded} "
            f"(from '{raw}'). Pass a real transcripts dir — the agent must confirm it with the "
            f"operator (flag-don't-reinterpret), never guess.")

    # Start from the current filled instance if present (preserve other keys), else the template.
    base = filled if os.path.isfile(filled) else template
    with open(base, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    out, replaced = [], False
    for line in lines:
        line = line.rstrip("\r")  # tolerate a CR from a CRLF source
        if line.strip().startswith("CLAUDE_PROJECTS_ROOT:"):
            out.append(f'CLAUDE_PROJECTS_ROOT: "{expanded}"')
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f'CLAUDE_PROJECTS_ROOT: "{expanded}"')

    with open(filled, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    ok(f"config/path-mappings.filled.yaml CLAUDE_PROJECTS_ROOT = {expanded}")


def _is_git_tracked(relpath):
    """True if relpath is a git-tracked file. Fail-closed: on any git error, treat as tracked
    (so we never rewrite a file we cannot prove is private)."""
    try:
        r = subprocess.run(["git", "ls-files", "--error-unmatch", relpath],
                           cwd=ROOT, capture_output=True, text=True)
        return r.returncode == 0
    except OSError:
        return True


def normalize_eol():
    # RL4 invariant (verified 2026-07-15): this helper writes ONLY private/gitignored files and
    # NEVER edits a git-tracked file. CRLF in a TRACKED file is fixed via git (the delivered
    # .gitattributes pins eol=lf), NOT by rewriting it here — so tracked files are reported, not
    # touched. A blind-verify probe caught the earlier version silently rewriting tracked scripts.
    targets = []
    for sub, exts in (("scripts", (".sh", ".py")), ("config", (".yaml",))):
        d = os.path.join(ROOT, sub)
        if os.path.isdir(d):
            for name in os.listdir(d):
                if name.endswith(exts):
                    targets.append(os.path.join(d, name))
    fixed = []
    tracked_crlf = []
    for p in targets:
        try:
            with open(p, "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        if b"\r\n" not in data and b"\r" not in data:
            continue
        rel = os.path.relpath(p, ROOT)
        if _is_git_tracked(rel):
            tracked_crlf.append(rel)          # report only — never rewrite a tracked file
            continue
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        with open(p, "wb") as fh:
            fh.write(data)
        fixed.append(rel)
    if fixed:
        ok("normalized CRLF->LF in (private files only): " + ", ".join(fixed))
    if tracked_crlf:
        warn("CRLF found in git-TRACKED file(s) — NOT rewritten here (that is git's job): "
             + ", ".join(tracked_crlf))
        print("fix tracked files via git (keeps the eol=lf pin authoritative):")
        print("  git config core.autocrlf false && git add --renormalize . && git status")
    if not fixed and not tracked_crlf:
        ok("no CRLF found — all target files already LF.")


def main():
    ap = argparse.ArgumentParser(description="Cold-start fix helper (writes private setup files).")
    ap.add_argument("--init-env", action="store_true", help="create .env from .env.template")
    ap.add_argument("--init-state", action="store_true",
                    help="create config/STATE.md from config/STATE-template.md")
    ap.add_argument("--projects-root", metavar="PATH",
                    help="set CLAUDE_PROJECTS_ROOT (expanded+validated) in path-mappings.filled.yaml")
    ap.add_argument("--normalize-eol", action="store_true",
                    help="rewrite CRLF->LF in scripts/config")
    args = ap.parse_args()

    did = False
    if args.init_env:
        init_env(); did = True
    if args.init_state:
        init_state(); did = True
    if args.projects_root:
        set_projects_root(args.projects_root); did = True
    if args.normalize_eol:
        normalize_eol(); did = True

    if not did:
        ap.print_help(sys.stderr)
        die("no action requested — pass at least one of --init-env / --init-state / "
            "--projects-root / --normalize-eol.")
    print("\nnext: re-run `python3 scripts/preflight.py` to confirm the gap closed.")


if __name__ == "__main__":
    main()
