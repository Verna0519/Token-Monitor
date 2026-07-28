#!/usr/bin/env bash
#
# check-visibility-seam.sh — RL4 DIRECTED-VISIBILITY GATE (4 asserts). Exit code IS the gate.
#
# This is the personal-agent's highest-risk surface. It INVERTS aocc's check-seam.sh: aocc scanned
# the share surface for real names; here the risk is DIRECTED VISIBILITY — identity + score must
# never cross the layer boundary. Concept-forked from aocc-ai-advisory/scripts/check-seam.sh.
#
# (a) Tracked-path safety: no identity-bearing PRIVATE bucket (raw-sessions/ handoff/ output/
#     worktemp/) and no private config instance is git-TRACKED (deny-by-default .gitignore should
#     keep them untracked; a tracked one = a leak of raw transcripts / a real self-view onto git).
# (b) Upward-file integrity (RL4-i): every handoff/**/*.json is scanned for identity /
#     structural-leak patterns (emails, absolute username paths, repository_url, git hashes, cwd,
#     JWT). The ONLY allowed upward file type is a capability COORDINATE (coordinate-*.json),
#     shape-checked by _check_coordinate_shape.py (exactly the 5 contract keys, opaque sub- id,
#     int 0-3 levels, nothing else). Anything else in handoff/ FAILS — the digest pipeline was
#     RETIRED 2026-07-15 (operator ruling; recover via git history).
# (c) No-score-to-the-person (RL4-ii): every personal-facing output/**/*.md is scanned for score /
#     rung / tier vocabulary — the person must never see a rung/tier/score (operator rulings #8/#9/#11).
# (d) Hard-exclude credential stores (RL4-i): assert no auth.json / credential dump was copied into
#     any working bucket (it must never be opened/ingested).
#
# Runs on an empty tree (P0) and after later phases populate handoff/ + output/ (re-run as a gate).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

fail=0
note() { printf '%s\n' "$*"; }
bad()  { printf 'FAIL: %s\n' "$*" >&2; fail=1; }

note "== check-visibility-seam (root: $ROOT) =="

# --- (a) tracked-path safety -------------------------------------------------
# HARDENED (migration problem WSL-06): a repo on a Windows drive mount (/mnt/c) commonly trips
# git's "detected dubious ownership" safety refusal. The old form was:
#     TRACKED="$(git ls-files 2>/dev/null || true)"
# which swallowed that fatal, left TRACKED empty, and let this clause PASS vacuously WITHOUT ever
# consulting git — a silent false-PASS on the authoritative RL4 gate ("exit code IS the gate").
# We now capture git's real exit code + stderr and FAIL loudly if git cannot enumerate the tree.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  bad "(a) not inside a usable git work tree — tracked-path safety is INCONCLUSIVE (not a pass)"
  TRACKED=""
else
  TRACKED="$(git ls-files 2>/tmp/.seam-git-err.$$)"; GIT_RC=$?
  GIT_ERR="$(cat /tmp/.seam-git-err.$$ 2>/dev/null || true)"; rm -f /tmp/.seam-git-err.$$
  if [ "$GIT_RC" -ne 0 ]; then
    bad "(a) git ls-files failed (rc=$GIT_RC) — refusing to treat an empty result as a clean tree"
    printf 'hint: on a /mnt Windows-drive clone this is usually dubious ownership; fix with:\n' >&2
    printf '      git config --global --add safe.directory %s\n' "$ROOT" >&2
    [ -n "$GIT_ERR" ] && printf '%s\n' "$GIT_ERR" >&2
    TRACKED=""
  elif printf '%s' "$GIT_ERR" | grep -qi 'dubious ownership'; then
    bad "(a) git reported dubious ownership — tracked-path safety INCONCLUSIVE"
    printf '      fix with: git config --global --add safe.directory %s\n' "$ROOT" >&2
    TRACKED=""
  fi
fi
PRIVATE_BUCKETS_RE='^(raw-sessions|handoff|output|worktemp)/'
PRIVATE_FILES_RE='(^config/STATE\.md$|\.filled\.yaml$|^self-growth/insight-log-private\.md$|^\.env$)'
leak_tracked="$(printf '%s\n' "$TRACKED" | grep -E "$PRIVATE_BUCKETS_RE" || true)"
leak_files="$(printf '%s\n' "$TRACKED" | grep -E "$PRIVATE_FILES_RE" || true)"
if [ -n "$leak_tracked" ] || [ -n "$leak_files" ]; then
  bad "(a) identity-bearing PRIVATE path(s) are git-TRACKED (must be gitignored):"
  [ -n "$leak_tracked" ] && printf '%s\n' "$leak_tracked" >&2
  [ -n "$leak_files" ] && printf '%s\n' "$leak_files" >&2
else
  note "ok (a): no identity-bearing private path is tracked"
fi

# --- (b) upward-digest de-identification (RL4-i) -----------------------------
# Scan working-tree handoff/**/*.json (they are gitignored but exist on disk where the gate runs).
# Identity / structural-leak patterns that must NEVER appear in an upward digest:
IDENT_RE='(/home/[A-Za-z0-9_]+|/Users/[A-Za-z0-9_]+|/mnt/[a-z]/Users/[A-Za-z0-9_]+|[A-Za-z]:\\+[^\\[:space:]"]+\\+[A-Za-z0-9._-]+|repository_url|"?repo_url"?|"?cwd"?[[:space:]]*:|"?git[_.]?(commit|branch|hash)"?|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})'
digest_count=0
if compgen -G "handoff/**/*.json" >/dev/null 2>&1 || compgen -G "handoff/*.json" >/dev/null 2>&1; then
  while IFS= read -r -d '' f; do
    digest_count=$((digest_count+1))
    hits="$(grep -EnI "$IDENT_RE" "$f" 2>/dev/null || true)"
    if [ -n "$hits" ]; then
      bad "(b) upward file '$f' contains an identity/structural-leak pattern:"
      printf '%s\n' "$hits" >&2
    fi
    case "$(basename "$f")" in
      coordinate-*.json)
        # Capability COORDINATE (the dept learning-map input contract; operator ruling 2026-07-15
        # "回頭對其契約改個人層"). The shape check — exactly the 5 contract keys, opaque sub- id,
        # int 0-3 levels, nothing else (no evidence text, no identity fields) — IS this layer's
        # upward de-identification guarantee.
        shapeerr="$(python3 "$SCRIPT_DIR/_check_coordinate_shape.py" "$f" 2>&1)" || bad "(b) '$f' coordinate shape: $shapeerr"
        ;;
      *)
        # Digest pipeline RETIRED 2026-07-15 (operator ruling). No other upward file type exists.
        bad "(b) '$f' is not a coordinate-*.json — the digest pipeline is retired; the capability coordinate is the only upward file type"
        ;;
    esac
  done < <(find handoff -type f -name '*.json' -print0 2>/dev/null)
fi
if [ "$digest_count" -gt 0 ]; then
  note "ok (b): scanned $digest_count upward digest(s) for identity/structural leaks + de-id flags"
else
  note "note (b): no upward digest present yet (Phase 4) — de-id scan no-op"
fi

# --- (c) no-score-to-the-person (RL4-ii) -------------------------------------
# Personal-facing output MUST NOT contain score/rung/tier vocabulary. Case-insensitive.
# NOTE: this intentionally forbids the words themselves in personal-facing prose — the personal
# layer uses a forked no-score growth vocabulary (operator ruling #11). A file describing the RULE (not
# addressed to the person) does not live under output/, so output/ is the correct narrow scope.
# Also scans output/**/*.html (e.g. render_insight.py's self-contained BMW-styled report): for
# .html files, <script>...</script> and <style>...</style> blocks are stripped BEFORE the grep so
# vendored Chart.js internals (e.g. minified 'R0'/'R1' tokens that would false-positive on
# \bR[0-7]\b) and our radar config never trip the gate — only the person-visible rendered text is
# scanned.
SCORE_RE='(\brung\b|\btier\b|\bR[0-7]\b|\bscore\b|評分|分數|評比|成熟度等級|signal_tier|(intended|structural|actual)[[:space:]-]*tier)'
outdoc_count=0
if [ -d output ]; then
  while IFS= read -r -d '' f; do
    case "$(basename "$f")" in
      coordinate-basis-*)
        # Operator ruling 2026-07-15 (放行): the person derives + CARRIES their own coordinate, so
        # the basis file exists precisely so they know what they are uploading and why (a level is
        # a position on the map, not a grade). Level/tier vocabulary is allowed HERE ONLY; growth
        # notes keep the no-score rule.
        continue
        ;;
    esac
    outdoc_count=$((outdoc_count+1))
    case "$f" in
      *.html)
        content="$(python3 -c 'import re,sys;t=open(sys.argv[1],encoding="utf-8").read();t=re.sub(r"<script\b[^>]*>.*?</script>", " ", t, flags=re.S|re.I);t=re.sub(r"<style\b[^>]*>.*?</style>", " ", t, flags=re.S|re.I);sys.stdout.write(t)' "$f")"
        hits="$(printf '%s' "$content" | grep -EniI "$SCORE_RE" || true)"
        ;;
      *)
        hits="$(grep -EniI "$SCORE_RE" "$f" 2>/dev/null || true)"
        ;;
    esac
    if [ -n "$hits" ]; then
      bad "(c) personal-facing output '$f' leaks score/rung/tier vocabulary to the person:"
      printf '%s\n' "$hits" >&2
    fi
  done < <(find output -type f \( -name '*.md' -o -name '*.txt' -o -name '*.html' \) -print0 2>/dev/null)
fi
if [ "$outdoc_count" -gt 0 ]; then
  note "ok (c): scanned $outdoc_count personal-facing doc(s) for score/rung/tier leakage"
else
  note "note (c): no personal-facing output present yet (Phase 3) — no-score scan no-op"
fi

# --- (d) hard-exclude credential stores (RL4-i) ------------------------------
# auth.json / credential dumps must never be copied into a working bucket (never opened/ingested).
cred_hits="$(find raw-sessions handoff output worktemp -type f \( -name 'auth.json' -o -name '*.pem' -o -name 'credentials' -o -name '.env' \) 2>/dev/null || true)"
if [ -n "$cred_hits" ]; then
  bad "(d) a credential store was found inside a working bucket (must be HARD-EXCLUDED, never copied):"
  printf '%s\n' "$cred_hits" >&2
else
  note "ok (d): no credential store copied into any working bucket"
fi

# --- verdict -----------------------------------------------------------------
if [ "$fail" -eq 0 ]; then
  note "PASS: directed-visibility seam intact (gate exit 0)"
  exit 0
else
  note "FAIL: directed-visibility seam (exit 1)" >&2
  exit 1
fi
