# ADR-0001 — Standalone-l3 Basis + Directed-Visibility Seam (RL4), Coordinate Model

- Status: **proposed** — FULL in-place rewrite ordered by the operator 2026-07-15 (identity docs
  rewritten for the coordinate model). The original digest-era text (accepted 2026-07-09) is
  preserved in git history; this version supersedes it as the current architecture record.
- Date: 2026-07-15 (original: 2026-07-09)
- Deciders: the operator (three-layer build; coordinate pivot 2026-07-14/15)

## Context

`aocc-personal-ai-coach` is the **personal layer** of a three-layer capability-coaching design
(personal / dept / center). It is a single-user, standalone, **interactive-only** Claude Code agent
that a PERSON runs on their own machine to grow their AI-collaboration capability: it scans their
own local session transcripts, extracts abstract capability signals, and turns them into
(a) a personal growth note and (b) a capability COORDINATE for the department layer's
**zone-positioning learning map** (dept pivot 2026-07-14). Two structural needs collide:

1. It must run with **no runtime dependency on any other layer or agent** — the three layers are
   physically separate repos; cross-layer data moves only by manual file carry.
2. It must let the person grow **without their identity or evidence ever leaving their machine**,
   while still feeding the dept map — a directed-visibility discipline (Red Line 4).

## Decision

### 1. Self-containment basis = standalone-l3 (Red Lines 1–3, unchanged)

- **RL1 — runtime self-contained**: no runtime call to any other agent/layer; no team-service
  dependency. Everything needed to run and grow lives in this directory.
- **RL2 — machine-portable**: no logic-baked absolute paths; every machine-specific path resolves
  through the single indirection layer `config/path-mappings.yaml` (committed as a generic-token
  template; scripts read the gitignored `config/path-mappings.filled.yaml` instance); a
  missing/unset resource flags loudly with a non-zero exit, never silent
  (`scan_sessions.py` resolution contract).
- **RL3 — fork-time scrub**: donor-forked scripts pass the scrub gate
  (`scripts/validate-selfcontainment.sh`: operative team-coupling tokens, hard imports, absolute
  paths, backbone-file existence, template placeholders, and self-growth/manifest dual-layer
  coverage).
- Clarification: reading the local transcript root (`CLAUDE_PROJECTS_ROOT`) is **read-only
  input-corpus ingestion** via path-mappings — data, not a runtime coupling.

### 2. Pipeline shape (what the seam protects)

`scan_sessions.py` (session index, **metadata only** — no message content) → `extract-capability`
skill (parallel per-session extraction: 8 domains × `present`/`signal_tier`/`evidence_refs`/
`growth_hint`; refs are ABSTRACT behaviors/counts, never raw transcript snippets — keeping refs
abstract is what lets the coordinate stay portable while the evidence stays local) →
`aggregate_signals.py` (deterministic, fence-tolerant,
schema-validated fail-closed; `validate_extraction.py` as the standalone check) → two outputs:

- **Personal growth note** (`render_growth.py`, `output/`): forward-looking only (`_growth_hint.py`
  forward_only backstop), zh-TW, coverage-honest (source_scope + lower-bound), **no score
  vocabulary** — RL4 (c).
- **Capability coordinate** (`emit-coordinate` workflow → `emit_coordinate.py`, `handoff/`): one
  agent per axis, grounded in that axis's `rung_rubric` (`config/personal-domains.yaml`); level =
  null when the evidence cannot place the axis — **absence of evidence is NEVER mapped to level 0**
  (level 0 is an observed low-maturity pattern). `signal_tier` (intended < structural < actual) is
  internal evidence STRENGTH for this assessment and is never echoed to the person; the
  `rung_rubric` is a definition/calibration layer (Phase 1b), not an output field.

### 3. Red Line 4 — directed visibility = EXACTLY `scripts/check-visibility-seam.sh`

The gate's four asserts ARE the red line (exit code is the verdict):

- **(a) Tracked-path safety**: the identity-bearing PRIVATE buckets (`raw-sessions/`, `handoff/`,
  `output/`, `worktemp/`) and private config instances (`config/STATE.md`, `*.filled.yaml`,
  private insight log, `.env`) are never git-tracked (deny-by-default `.gitignore`).
- **(b) Upward-file integrity**: every `handoff/**/*.json` is scanned for identity/structural-leak
  patterns; the ONLY allowed upward file type is `coordinate-*.json`, shape-checked by
  `_check_coordinate_shape.py` — exactly the 5 contract keys `{format, version, submission_id,
  period, position}`, opaque `sub-` id, int 0–3 levels, nothing else. Anything else in `handoff/`
  FAILS — **the digest pipeline was RETIRED 2026-07-15** (operator ruling; recover via git history).
- **(c) No-score-to-the-person**: personal-facing `output/**` carries no score/rung/tier
  vocabulary — EXCEPT `coordinate-basis-*` files, exempt by the 2026-07-15 「放行」 ruling: the
  person derives and CARRIES their own coordinate, so the basis (per-axis evidence + rationale)
  exists so they know what they upload. Growth notes keep the rule.
- **(d) Credential stores hard-excluded**: no `auth.json`/`.pem`/credential dump may be copied
  into any working bucket (never opened/ingested).

### 4. The coordinate is the SOLE upward artifact (strict contract)

The upload carries **only** `{format: "capability-coordinate", version: "0.1", submission_id,
period, position}` (8 axes × int 0–3). Evidence and the local `coordinate-basis-*` rationale stay
on this machine; a **fresh opaque `sub-` id is minted per emission** (no stable per-person id); a
human **hand-carries** the file to the dept repo's inbox — no runtime cross-repo call.
**Strict-contract rule** (operator ruling 2026-07-15, 「契約選補證據」): no nullable levels; on any
unplaced axis `emit_coordinate.py` REFUSES and directs to collect more evidence — extract sessions
that exercise that axis (`coverage_report.py` names the targets), re-assess, re-emit.

### 5. Scope of meaning (operator ruling 2026-07-15)

The 8 axes measure **how the person OPERATES AI**, not domain/professional expertise. Hence a
coordinate is **portable across departments**, and a zone fit claims ONLY that AI-operation
capability meets the project's per-axis band — **never professional qualification** (judged
elsewhere, by humans).

### 6. Operating rules

Self-growth is **propose-only**: the agent writes `status: proposed`; ratified requires the
operator's hand-authored marker. Communication with the operator is Traditional Chinese; shareable
file content is English. Resumption: read `CLAUDE.md` → `INDEX.md` → `config/STATE.md` → continue
from Next Action — no external context needed.

## Consequences

- The mechanical gates are the architecture's teeth: `validate-selfcontainment.sh` (RL1–3) and
  `check-visibility-seam.sh` (RL4 a–d) must stay green; the seam remains the highest-risk surface
  and is re-validated by context-blind third parties + mechanical grep, never same-brain agreement.
- The digest pipeline (build_digest / handoff schema / 8→6 fold) is retired; gate (b) now rejects
  any non-coordinate upward file, so a regression cannot ship silently.
- The cross-repo contract's **source of truth lives in the dept repo**
  (`dept-capability-agent/planning/coordinate-contract.md` + ADR `decisions/0002` addendum); both
  sides pin `version: "0.1"` and the same 8 axes — a contract bump must be deliberate on both sides.
