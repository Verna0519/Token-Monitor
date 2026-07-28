#!/usr/bin/env bash
#
# validate-selfcontainment.sh — P0 EXIT GATE (file-resolution oracle, not prose).
# Forked from aocc-ai-advisory/scripts/validate-selfcontainment.sh; backbone list adapted.
#
# Proves the agent is self-contained (standalone-l3) WITHOUT any transcript data:
#   1. Scrub-grep: the standalone-l3 team-coupling token set over the agent's OWN runtime surfaces
#      (scripts/, CLAUDE.md, .claude/) returns empty (negation/declaration lines exempt).
#   2. Team/machine absolute-path check over the same surfaces returns empty.
#   3. Backbone file-existence asserts (non-placeholder).
#   4. path-mappings template carries generic tokens (no real machine paths committed).
#   5. self-growth log + promotion rule + manifest dual_layer coverage present.
#
# Exit code IS the gate (0 = self-contained, non-zero = fail).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

fail=0
note() { printf '%s\n' "$*"; }
bad()  { printf 'FAIL: %s\n' "$*" >&2; fail=1; }

note "== validate-selfcontainment (root: $ROOT) =="

# --- 1. Scrub-grep over runtime surfaces (NOT reference/) --------------------
# NEGATION/DECLARATION lines are exempt: the standalone-l3 pattern REQUIRES CLAUDE.md/ADR to
# DECLARE "no mem0/qmd/team-coupling" — naming a token to assert its ABSENCE is the contract, not
# a coupling. Only an OPERATIVE coupling (an actual import/call/path) trips the gate.
#
# NOTE (this agent): `~/.claude/projects` is this agent's INPUT CORPUS, read via path-mappings
# indirection (ADR-0001 §1) — it is data ingestion, not a runtime coupling. The scrub token for
# the ~/.claude COUPLING is scoped to a skills-import path (`~/.claude/skills/...`), so a
# path-mappings-resolved data read of ~/.claude/projects does not trip it.
SCRUB_TARGETS=()
[ -d scripts ] && SCRUB_TARGETS+=(scripts)
[ -f CLAUDE.md ] && SCRUB_TARGETS+=(CLAUDE.md)
[ -d .claude ] && SCRUB_TARGETS+=(.claude)

SCRUB_RE='qmd[[:space:]]|qmd$|mem0|m0-cli|m0-add|m0-search|agent-em|agent-C7|agent-GM|/Users/[A-Za-z0-9._-]+|~/\.claude/skills|\.claude/skills/(memory-protocol|wiki-search|team-communication|wiki-schema)'
NEGATION_RE='([Nn][Oo]|NO|never|not |without|anti|❌|forbidden|absence|do(es)? not|independence|scrub|coupling|ingestion|input|read-only|MUST explicitly state)'

scrub_scan() {
  grep -rEn "$SCRUB_RE" "$@" 2>/dev/null \
    | grep -v "scripts/validate-selfcontainment.sh:" \
    | grep -v "\.claude/settings\.local\.json:" \
    | grep -vE ":[0-9]+:.*$NEGATION_RE" || true
}

if [ "${#SCRUB_TARGETS[@]}" -gt 0 ]; then
  hits="$(scrub_scan "${SCRUB_TARGETS[@]}")"
  if [ -n "$hits" ]; then
    bad "scrub-grep found OPERATIVE team-coupling tokens on runtime surfaces:"
    printf '%s\n' "$hits" >&2
  else
    note "ok: scrub-grep clean on runtime surfaces (operative coupling = none)"
  fi
else
  bad "no runtime surfaces found to scrub"
fi

# --- 1b. A REAL python import of a team module is NEVER negation-exempt ------
hard_import="$(grep -rEn '^[[:space:]]*(import|from)[[:space:]]+(mem0|qmd)([[:space:].]|$)|^[[:space:]]*import[[:space:]]+m0_cli\b' scripts/ CLAUDE.md .claude/ 2>/dev/null | grep -v 'scripts/validate-selfcontainment.sh:' || true)"
if [ -n "$hard_import" ]; then
  bad "hard team-module import (a negation comment cannot exempt a real import):"
  printf '%s\n' "$hard_import" >&2
else
  note "ok: no hard import of a team module (mem0/qmd/m0_cli)"
fi

# --- 2. Team/machine absolute paths (logic-baked) over runtime surfaces ------
ABS_RE='/home/[A-Za-z0-9._-]+/|/mnt/[a-z]/|/Users/[A-Za-z0-9._-]+/|[A-Za-z]:\\+[^\\[:space:]"]+\\+[A-Za-z0-9._-]+'
abs_scan() {
  grep -rEn "$ABS_RE" "$@" 2>/dev/null \
    | grep -v "scripts/validate-selfcontainment.sh:" \
    | grep -v "\.claude/settings\.local\.json:" \
    | grep -vE ":[0-9]+:.*$NEGATION_RE" || true
}
if [ "${#SCRUB_TARGETS[@]}" -gt 0 ]; then
  abs_hits="$(abs_scan "${SCRUB_TARGETS[@]}")"
  if [ -n "$abs_hits" ]; then
    bad "logic-baked team/machine absolute paths on runtime surfaces:"
    printf '%s\n' "$abs_hits" >&2
  else
    note "ok: no logic-baked team/machine absolute paths on runtime surfaces"
  fi
fi

# --- 3. Backbone file-existence asserts (non-placeholder) --------------------
assert_file() {
  if [ ! -f "$1" ]; then bad "missing backbone file: $1"; return; fi
  sz="$(wc -c <"$1" | tr -d ' ')"
  if [ "$sz" -lt "$2" ]; then bad "backbone file too small (placeholder?): $1 ($sz < $2 bytes)"; fi
}

assert_file CLAUDE.md 3000
assert_file README.md 800
assert_file INDEX.md 800
assert_file manifest.yaml 800
assert_file .env.template 50
assert_file .gitignore 300
assert_file decisions/0001-standalone-l3-and-visibility-seam.md 1500
assert_file planning/BUILD-PLAN.md 1000
assert_file config/path-mappings.yaml 200
assert_file config/personal-domains.yaml 400
assert_file config/STATE-template.md 150
assert_file config/STATE.md 200
assert_file self-growth/insight-log-core.md 300
assert_file self-growth/README.md 500
assert_file scripts/check-visibility-seam.sh 800
assert_file .claude/settings.json 10
note "ok: backbone file-existence asserts run"

# --- 4. path-mappings template carries generic tokens (no real paths) --------
if grep -q '<set me' config/path-mappings.yaml 2>/dev/null; then
  note "ok: path-mappings.yaml template uses generic placeholder tokens"
else
  bad "path-mappings.yaml template missing '<set me' placeholder (real paths may be committed)"
fi
if grep -Eq '/mnt/[a-z]/|/home/[A-Za-z0-9._-]+/|/Users/[A-Za-z0-9._-]+/|[A-Za-z]:\\+[^\\[:space:]"]+\\+[A-Za-z0-9._-]+' config/path-mappings.yaml 2>/dev/null; then
  bad "path-mappings.yaml TEMPLATE contains real machine paths (must be generic only)"
fi

# --- 5. self-growth + manifest dual_layer coverage ---------------------------
if grep -q 'status: proposed' self-growth/insight-log-core.md 2>/dev/null; then
  note "ok: self-growth core log carries proposed entries"
else
  bad "self-growth core log missing 'status: proposed' entries"
fi
if grep -qi 'must NEVER' self-growth/README.md 2>/dev/null; then
  note "ok: self-growth promotion rule (agent never self-promotes) present"
else
  bad "self-growth README missing the never-self-promote rule"
fi
for key in 'mode: standalone-l3' 'dual_layer:' 'shareable:' 'private:'; do
  grep -q "$key" manifest.yaml 2>/dev/null || bad "manifest.yaml missing: $key"
done
note "ok: manifest dual_layer coverage checked"

# --- verdict -----------------------------------------------------------------
if [ "$fail" -eq 0 ]; then
  note "PASS: self-contained (gate exit 0)"
  exit 0
else
  note "FAIL: self-containment gate (exit 1)" >&2
  exit 1
fi
