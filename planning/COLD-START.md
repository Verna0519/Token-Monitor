# Cold-Start (new-machine bring-up)

This agent has **no automated startup hook by default** (CLAUDE.md §1 forbids stop-hook,
SessionStart auto-load, and inbox/outbox). Cold-start is a three-part, red-line-clean flow.

1. **PREFLIGHT (read-only) — `scripts/preflight.py`.** Pure-stdlib Python (python3 is already a
   hard dependency), so it runs on Windows-native / WSL / macOS / Linux. It only CHECKS setup
   completeness and writes a machine-readable gap report to `worktemp/preflight-report.json`
   (PRIVATE/gitignored) plus a human summary. It never modifies anything and exits non-zero when
   setup is incomplete (RL2 loud-fail). Each check maps to a real precondition (PC-xx) or migration
   problem and uses a cross-OS probe: PEP-668 externally-managed marker (WSL-05 / macos), the
   literal `python3` token resolving (WSL-04 / P-W-02), CRLF byte-scan (WSL-03 / P-W-03), git
   dubious-ownership (WSL-06), an unexpanded `~`/`$` in `CLAUDE_PROJECTS_ROOT`
   (claude-projects-root-tilde), an empty corpus with a Windows-side store discovered via
   `/proc/mounts` (WSL-01 / WSL-07), UTF-8 BOM (P-W-07), and the two bash gates' real exit codes
   (PC-11 / P-W-01).
2. **AGENT-DRIVEN Q&A (interactive Claude).** A hook cannot read stdin, so the interactive agent —
   as step 0 of the §9 resumption protocol — runs the preflight, reads the report, and asks the
   operator the `qa_prompt` carried per gap (zh-TW). Ambiguity is a question, never a guess
   (flag-don't-reinterpret).
3. **FIX (mechanical) — `scripts/onboard.py`.** Once the operator confirms, the agent calls this
   idempotent helper to write the PRIVATE, gitignored config files (`.env`, `config/STATE.md`,
   `config/path-mappings.filled.yaml`) and to normalize CRLF->LF. It expands `~`/`$HOME`, validates
   the transcript dir exists, and loud-fails rather than seeding a broken value. It never edits a
   tracked template and never writes a real path into the tracked `config/path-mappings.yaml`.

## Fresh-machine quick path

```bash
python3 scripts/preflight.py                 # see the gap report
# ... the agent asks you the per-gap questions, then runs, e.g.:
python3 scripts/onboard.py --init-env --init-state \
        --projects-root "$HOME/.claude/projects"   # macOS: /Users/<you>/.claude/projects
python3 scripts/onboard.py --normalize-eol   # only if preflight flagged CRLF
python3 scripts/preflight.py                 # re-check -> setup_complete: true
bash scripts/validate-selfcontainment.sh     # exit 0
bash scripts/check-visibility-seam.sh         # exit 0   <- "驗證通過"
```

The full per-OS, checkable onboarding checklist (zh-TW) is handed to the operator; this doc is the
shareable mechanism reference.

## Per-OS notes

- **WSL**: clone under the ext4 home (`~/code`), not `/mnt/c` (slow + non-POSIX perms + git
  dubious-ownership; WSL-06). If prior CLI usage was on Windows-native, transcripts live under
  `/mnt/<drive>/Users/<WinUser>/.claude/projects`, not the empty WSL home (WSL-01 / WSL-07).
- **macOS**: ensure a real, runnable `python3` (a bare Xcode CLT stub pops a GUI); the transcript
  root is under `/Users`, not `/home`. Homebrew python is PEP-668 externally-managed — use a venv.
- **Windows-native**: the `.sh` gates cannot run here (P-W-01) — do the final gate step under WSL
  or Git-Bash. `preflight.py` / `onboard.py` still run and honestly report bash-absence.
- **PEP-668 (WSL/macOS common)**: `pip install jsonschema pyyaml` is blocked; use a project venv,
  the distro package, or `pip install --user` (preflight prints the exact recipe it detected).

## Native-Windows completion story

`preflight.py` runs on native Windows. Because the two `.sh` gates need bash + coreutils that are
absent there, the bash/coreutils/`python3`-token checks are reported as **WARN (not GAP)** when
`platform.system()=="Windows"`, so a correctly configured native-Windows machine still reaches
`setup_complete: true`. The authoritative "驗證通過" remains the two `.sh` gates exiting 0 — run
them under WSL or Git-Bash (which ship bash + grep/find/wc/tr). preflight also raises a
`PF-WIN-PIPELINE` advisory that the pipeline itself carries POSIX-path assumptions (P-W-04 nested
transcript exclusion, P-W-05 identity regex) and should be driven under WSL/Git-Bash until those
are patched by an explicit Emil ruling.

## Optional SessionStart hook (requires an operator ruling)

By default there is **no hook**. If Emil rules that a read-only preflight is distinct from the
forbidden "SessionStart auto-load" (CLAUDE.md §1 line 44), a non-blocking SessionStart hook may run
`preflight.py --quiet --no-gates` to surface the gap summary as session context. See the delivered
`settings.json` patch. Until that ruling, the resumption-protocol-invoked path above is the design.
