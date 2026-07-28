# BUILD-PLAN — aocc-personal-ai-coach (as-built history + forward plan)

> A single-user, standalone-l3 Claude Code agent a person runs on their own machine to grow their
> AI-collaboration capability. Interactive only. Its upward artifact is a **capability COORDINATE**
> for the dept learning map (dept repo `planning/coordinate-contract.md`, ADR `decisions/0002`).
> Rewritten 2026-07-15 for the coordinate model; the digest pipeline sections below are HISTORY.
> Everything the agent produces is PROPOSED; ratified = the operator's hand marker only.

## As-built history

### P0 — Scaffold + gates ✅ (2026-07-09)

Independent repo with the standalone-l3 skeleton (RL1 runtime self-contained; RL2 machine-portable
via `config/path-mappings.yaml` single indirection, loud-fail on unresolved; RL3 fork-time scrub)
plus the net-new **RL4 directed-visibility seam**: deny-by-default `.gitignore`, `manifest.yaml`
dual-layer map, and two exit gates that ARE the red lines:

- `scripts/validate-selfcontainment.sh` — scrub-grep over runtime surfaces (operative team
  coupling / hard imports / logic-baked absolute paths = fail), backbone file asserts,
  path-mappings template must stay generic, self-growth propose-only rule present.
- `scripts/check-visibility-seam.sh` — RL4 (a) private buckets (`raw-sessions/ handoff/ output/
  worktemp/` + private configs) never git-tracked; (b) upward-file integrity; (c) no
  score/rung/tier vocabulary in personal-facing `output/`; (d) credential stores hard-excluded
  from working buckets.

### P1 — Extraction pipeline ✅ (P1a 2026-07-09; hardened 2026-07-13)

`extract-capability` skill (fork-in-spirit of a session-ingest skeleton, schema swapped):

1. **Scan** — `scripts/scan_sessions.py`: resolves `CLAUDE_PROJECTS_ROOT` via the filled
   path-mappings (RL2), indexes local Claude Code CLI jsonl **metadata only** (paths, counts, time
   span; no content), excludes nested subagent/workflow transcripts.
2. **Extract** — parallel sub-agents (Sonnet, effort low), one JSON object per session per
   `config/extraction.schema.json`: 8 domains x {present, signal_tier, evidence_refs, growth_hint}
   + bias_flags + coverage. Evidence refs are ABSTRACT (counts/behaviors) — never verbatim
   snippets, paths, or identity.
3. **Aggregate** — `scripts/aggregate_signals.py`: deterministic, fence-tolerant merge;
   schema-validates fail-closed; drops+logs invalid objects loudly; refuses an empty write.
4. **Validate** — `scripts/validate_extraction.py`: schema + identity/score content backstop.

`signal_tier` (intended < structural < actual) = internal evidence STRENGTH for the coordinate
assessment; never echoed to the person. Taxonomy went 6→8 domains 2026-07-13 (added
CONTEXT-ENGINEERING + CONTINUITY); the dept map mirrors the same 8 axes.

### Phase 1b — Rung rubric ✅ (2026-07-13)

All 8 domains in `config/personal-domains.yaml` carry an authored `rung_rubric` (0→3 capability
maturity; per-level definition/observable_markers/grounding/boundary_note; 32 rung definitions),
built via an author→adversarial-verify workflow (orthogonality/grounding/monotonicity checks).
The rubric is a **definition/calibration layer**, not an output field: it sharpens extraction
(SKILL.md calibrates off `observable_markers`) and grounds the coordinate assessment. PROPOSED.

### P3 — Personal growth note ✅ (2026-07-09; hardened 2026-07-13)

`scripts/render_growth.py` → `output/growth-note.md` (zh-TW, private): forward-looking growth
directions per domain (growth_hint only, `_growth_hint.py forward_only()` backstop strips
retrospective tone), all 8 sections rendered regardless of presence, coverage honesty
(source_scope + lower-bound: unscanned ≠ low capability). No score vocabulary — gate (c) enforced.

### P4 — Upward digest: built, then RETIRED 2026-07-15 (operator ruling)

The pilot terminus was an upward DIGEST (`build_digest.py`, `handoff.schema.json`, 8→6 domain
fold, NO_PLACEMENT flags), proven end-to-end and reviewed by a two-track check. The dept
layer then pivoted (2026-07-14) to a **zone-positioning learning map** whose sole input is a
capability coordinate — so the digest pipeline was retired 2026-07-15 (files git-rm'd, recover
via history; relic archived under `worktemp/`). The 8→6 fold is gone: dept consumes the same 8 axes.

### Capability-coordinate emitter ✅ (supersedes the retired P4; built + gate-aligned 2026-07-15)

- `.claude/workflows/emit-coordinate.js` — one agent per axis, grounded in that axis's
  `rung_rubric`; judges the level the evidence DEMONSTRATES, weighing signal_tier as evidence
  strength; **level = null when evidence cannot place — NEVER absence→0** (level 0 is an observed
  low-maturity pattern). Fails loudly on missing/duplicate/unknown axes.
- `scripts/emit_coordinate.py` — mechanical: validates fail-closed, mints a fresh opaque `sub-` id
  per emission, writes (1) `handoff/coordinate-<sid>.json` — the UPLOAD, carrying ONLY
  {format, version "0.1", submission_id, period, position: 8 axes int 0–3} — and (2)
  `output/coordinate-basis-<sid>.md` — LOCAL ONLY per-axis basis + rationale. Per the 2026-07-15
  ruling (契約選補證據) it REFUSES on any unplaced axis and directs to collect more evidence.
- Gate alignment (rulings 2/3, 2026-07-15): seam (b) accepts ONLY `coordinate-*.json`,
  shape-checked by `scripts/_check_coordinate_shape.py` (exactly the 5 contract keys, opaque
  `sub-` id, int 0–3 levels, nothing else); seam (c) exempts `coordinate-basis-*` (the person
  carries their own coordinate); growth notes keep the no-score rule.
- `scripts/coverage_report.py` — per-axis evidence coverage → names the extraction targets.
- SCOPE (operator ruling 2026-07-15): the 8 axes measure how the person OPERATES AI, not
  domain/professional expertise; coordinates are cross-department portable; a zone fit claims only
  "AI-operation capability meets the project band", never professional qualification.
- A human hand-carries the coordinate file to the dept repo inbox — no runtime cross-repo call (RL1).

## Forward plan

> Fresh-agent resumption: read `CLAUDE.md` → `INDEX.md` → `config/STATE.md`, then continue from
> that file's Next Action (CLAUDE.md §9).

1. **補證據 (next)** — extract sessions exercising **TUNING** (currently the sole unplaced axis;
   `coverage_report.py` is the targeting tool) → re-run emit-coordinate → emit a full 0.1
   coordinate → hand-carry to the dept inbox.
2. **Periodic re-assessment cadence** — open: how often to re-scan/re-emit (the contract's
   `period` field is reserved dept-side; cross-period semantics undesigned).
3. **bias_flags zh-TW unification** — extraction sub-agents emit English `observed`/`bias` text;
   unify to zh-TW (cosmetic leftover).

## Deferred

Codex CLI (`~/.codex/sessions`) + server-only sources (ChatGPT / Claude Desktop) stay out of
scope — recorded as coverage blind spots in the honesty statement, never silently claimed.
