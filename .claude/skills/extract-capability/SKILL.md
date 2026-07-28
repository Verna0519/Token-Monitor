---
name: extract-capability
description: "Scan the person's local Claude Code CLI transcripts and extract eight-domain capability signals + AI-usage BIAS (abstract signals only, NEVER verbatim). Phase-1 scan + Phase-2 parallel extraction. Personal layer of the three-layer coaching design. Args: [--project SUBSTR|all] [--days N] [--max N]"
user-invocable: true
---

Extract **eight-domain capability signals + AI-usage BIAS** from the operator's own local Claude Code
CLI transcripts. This is the personal-layer agent's ingestion pipeline (Phase 1 of the Pilot).
Forked-in-spirit from `ai-article/session-ingest` — Phase-1 jsonl scan + Phase-2 parallel sub-agent
extraction — but the schema is SWAPPED: capability signals, not writing material.

```
/extract-capability [--project SUBSTR|all] [--days N] [--max N]
```

Defaults: `--project all --max 30` (session-ingest convention). Example:
`/extract-capability --project aocc --days 7`.

## 🔒 Red Line 4 (directed visibility) — READ FIRST

This skill runs entirely inside the PRIVATE layer. Two non-negotiable constraints:

- **NO VERBATIM.** Unlike the donor (which extracts verbatim quotes for writing material), this
  skill extracts **abstract signals only** — counts, behaviors, evidence-tier observations. A raw
  transcript snippet is a **style-fingerprint re-identification vector** (RL4-i). Sub-agents are
  instructed to never return a quote, a file path, a repo name, or any identity token.
- **signal_tier is a SCORE.** It is captured as internal evidence STRENGTH for the
  capability-coordinate assessment (`emit-coordinate` workflow → `scripts/emit_coordinate.py`;
  the digest pipeline was RETIRED 2026-07-15) and is **NEVER echoed to the person** (RL4-ii).
  The personal-facing output (Phase 3) surfaces `growth_hint` only.

Output lands in `worktemp/` and `raw-sessions/` (PRIVATE, gitignored). Nothing here leaves the
private layer without passing the two-stage scrub + `check-visibility-seam.sh` (Phase 2/4).

## Workflow

```
/extract-capability --project X --days N
       ↓
  Phase 1: scan_sessions.py → worktemp/session-index.json (metadata only, subagent transcripts excluded)
       ↓
  Phase 2: parallel extraction sub-agents (Sonnet, effort:'low'), max 10 sessions/agent
       ↓
  Phase 3: aggregate_signals.py → raw-sessions/capability-signals.json (fence-tolerant, schema-validated)
       ↓
  Phase 4: report coverage (source_scope + lower-bound honesty) — no score shown
                → render_growth.py + render_insight.py (both no-score)
```

### Phase 1 — Scan (deterministic)

Run the scanner (resolves `CLAUDE_PROJECTS_ROOT` via path-mappings; RL2 loud-fail on unset):

```bash
python3 scripts/scan_sessions.py --project <SUBSTR|all> --days <N> --max <N>
```

It writes `worktemp/session-index.json` (paths + line/message counts + time span; NO content) and
excludes nested `/subagents/` + `/workflows/` transcripts (those are spawned agents, not the person).

### Phase 2 — Parallel extraction (sub-agents)

Split the indexed sessions into batches of **≤10** and spawn parallel `general-purpose` sub-agents
(model tiering: **Sonnet, `effort:'low'`** — bounded mechanical extraction; do NOT inherit session
xhigh, per the effort-tiering rule). Each sub-agent:

1. Reads its assigned session jsonl paths (from the index — the sub-agent Reads the file itself;
   do NOT inline transcript content into the prompt).
2. For each session, extracts the eight-domain signals (`present`, `signal_tier`, `evidence_refs`,
   `growth_hint` + optional `strength`) + BIAS per `config/extraction.schema.json`.
3. Returns a JSON **array** of per-session objects matching that schema. **Abstract only** — the
   prompt (below) forbids verbatim / paths / identity.

**Eight domains** (`config/personal-domains.yaml`; lifecycle order decide→…→persist):
DESIGN (whether/what to build), FRAMEWORK-SELECTION (which substrate/shape), CODING (produce+
integrate runnable artifacts), TUNING (method-based convergence loop), CONTEXT-ENGINEERING (what
the model SEES at one instant — JIT/token-budget/progressive-disclosure), EVAL (independent
error-analysis-first measurement), ADVISORY (human-in-loop boundary), CONTINUITY (recoverable state
across session/agent boundaries). CONTEXT-ENGINEERING + CONTINUITY are net-new (taxonomy 2026-07-13;
the dept learning map's `axes.yaml` mirrors the SAME 8 — no fold; the old 8→6 digest fold was
retired 2026-07-15 with the digest pipeline). **Evidence-
tier** (`signal_tier`): `intended` (talked about it) < `structural` (set up the structure) <
`actual` (demonstrably did it with an observable result).

**Rung rubric (Phase 1b, LANDED 2026-07-13):** each domain in `config/personal-domains.yaml` now
carries an authored `rung_rubric` (0→3 capability maturity, with per-level `observable_markers`).
Use it to CALIBRATE extraction: read a domain's `observable_markers` to decide which behaviors count
as a signal there, and keep the levels' orthogonality boundaries (`boundary_note`) in mind so a
signal is attributed to the right domain. The rung (maturity) is ORTHOGONAL to `signal_tier`
(evidence strength) — still assign `signal_tier` on the intended/structural/actual axis by the
observable evidence, and flag `present:false` when a domain has no signal. The rung level itself is
NOT emitted in the per-session schema (it is a coaching/definition layer, never shown to the person,
RL4-ii) — it sharpens WHAT to look for, it is not a new output field. (The coordinate ASSESSMENT
(`emit-coordinate`) later judges a 0-3 level per axis FROM these signals, grounded in the same
rubric — that judgment happens downstream, not during extraction.)

#### Sub-agent prompt (verbatim contract)

> You are extracting AI-capability signals from a person's own Claude Code transcripts, for their
> OWN growth. Read each assigned session file. For EACH session return one object matching the
> schema (EIGHT domains + bias_flags + coverage).
>
> The 8 domains (all 8 required in domain_signals; use present:false when a domain has no signal):
> DESIGN = decide whether/what to build (framing, decomposition, deletion-test).
> FRAMEWORK-SELECTION = pick the right substrate/shape (Skill vs Subagent vs Agent-Team; model) by
>   bottleneck+cost, not trend (includes multi-agent orchestration-shape choice).
> CODING = produce+integrate runnable code/config that ships (path discipline, return contracts,
>   verification hooks, clean commits) — PRODUCTION only.
> TUNING = converge output by METHOD not vibes (additive-vs-subtractive, iteration caps) — the
>   multi-round refinement LOOP only.
> CONTEXT-ENGINEERING = architect WHAT the model sees at one instant (JIT load tiers, token budgets,
>   progressive disclosure, read-depth, pruning context anti-patterns) — distinct from CODING (what
>   it RUNS) and TUNING (the loop).
> EVAL = measure whether it works, error-analysis-first, via an audit OUTSIDE the actor's own
>   context (self-checking your own just-generated output does NOT count as EVAL).
> ADVISORY = draw the human-in-loop WHAT/HOW/RISK boundary; intervene with strategy not steps.
> CONTINUITY = leave recoverable, faithful state ACROSS session/agent boundaries (handoff-test,
>   tag temporary constraints with expiry, enumerate unwritten assumptions) — the TIME axis.
>
> HARD RULES (re-identification safety — non-negotiable):
> - NEVER return a verbatim or near-verbatim quote from the transcript.
> - NEVER return a file path, repo name, project name, URL, email, person name, or any identity.
> - `evidence_refs` are ABSTRACT only: e.g. "iterated on a design across ~3 turns before building",
>   "chose a framework after comparing 2 options", "ran a test and read the failure". Counts and
>   behaviors, never content.
> - `signal_tier`: intended < structural < actual. Use `actual` only when there is an observable
>   result (a tool ran, a file changed, a metric was read). null when present=false.
> - `growth_hint`: forward-looking, encouraging, NO score/rung/tier words ("試著加強 X", not "你的
>   DESIGN 是 R2"). This is the only field the person will ever see. **Pure forward-looking (de-id
>   audit F3, operator ruling #9): do NOT open with retrospective praise ("你已經很扎實…") — the personal layer
>   must not read as a retrospective assessment. Start directly with the forward advice ("可以再…",
>   "試著…"). NEVER name a tool/product (claude-code-cli/codex/chatgpt/…) — F1.**
> - `strength`: an OPTIONAL forward-framed note of a practice worth KEEPING UP. Write the PRACTICE
>   ITSELF directly (describe the effective behavior/habit) — do NOT prefix it with a stock lead-in
>   like "值得持續保持的做法：…" / "可以繼續…" / "接下來也保持…". That framing already lives in the
>   report's section label, so repeating it on every bullet is redundant boilerplate; the renderer
>   also strips such an opener as a backstop. Just state the practice (e.g. "把模糊需求先拆成具體的
>   分階段管線再動手" not "值得持續保持的做法：把模糊需求…"). This IS surfaced to the person
>   (render_insight 的成長卡片), so write it in Traditional Chinese (繁體中文) with FULL-WIDTH
>   punctuation （），、。「」：；！？. HARD constraints: (1) NEVER retrospective praise — do NOT open
>   with "你已經很扎實…／你已經做得很好…／抓對了…" (F3 / operator ruling #9: the personal layer must
>   not read as a retrospective assessment); describe the practice as an ongoing habit, framed
>   neutrally-forward, not as a grade of past work. (2) NO score/rung/tier/level vocabulary of any
>   kind (RL4-ii, gate (c)) — no 「等級」「成熟度」「R0-R3」「tier」「score」. (3) Set it to null when
>   nothing is notably worth keeping up this session — an empty or forced strength is worse than null.
> - `bias_flags`: write the `bias` (theme name) and `observed` (pattern description) fields in
>   Traditional Chinese (繁體中文), same register as `growth_hint`. These two fields ARE surfaced to
>   the person (render_insight 的「使用習慣」區塊), and the report NEVER translates observation
>   content (Phase 4 language rule) — so the zh-TW must already exist in the extracted source, or the
>   habit section renders English. Keep `self_correctable` a boolean. (Internal-only fields —
>   `evidence_refs`, `signal_tier` — are never shown to the person and may stay in any language.)
> - ALL zh-TW person-facing fields (`growth_hint`, `strength`, and the `bias`/`observed` bias-flag
>   fields) MUST use FULL-WIDTH punctuation （），、。「」：；！？ — never half-width , . : ; ! ? ( )
>   between Chinese characters. (Half-width punctuation is normalized at render time as a backstop,
>   but produce it full-width at the source.)
> Return ONLY the JSON array. No prose.

### Phase 3 — Aggregate + validate (deterministic, do NOT hand-merge)

Do **not** hand-merge the sub-agent outputs — a live sub-agent has wrapped its JSON in a ```` ```json ````
fence, which silently breaks a prose merge. Save each sub-agent's returned text to a file and run
the deterministic aggregator (fence-tolerant + fail-closed, per this repo's "a rule in prose is
silently skipped; it needs a structural gate" discipline):

```bash
python3 scripts/aggregate_signals.py <agent-out-1.json> <agent-out-2.json> ... \
  --out raw-sessions/capability-signals.json
```

It parses each output whether bare / ```` ``` ````-fenced / prose-wrapped, merges the per-session
arrays, validates each object against `config/extraction.schema.json` fail-closed, and **drops +
loudly logs** any invalid object (never silent). It **exits non-zero if any object is dropped**
(pass `--drop-invalid` to tolerate + still write the survivors) and **refuses to write an empty
signals file**. Re-run any failing sub-agent rather than shipping a partial extraction.

### Phase 4 — Coverage report (honesty)

Report to the operator: how many sessions scanned, which project dirs, and the **source_scope +
lower-bound** statement (RL4-iv): "僅掃到本機 Claude Code CLI;Codex / ChatGPT / Claude Desktop 未
計入 — 沒掃到不等於能力低." Do NOT show any score/tier. This feeds the personal growth output
(Phase 3) and the capability-coordinate assessment (`emit-coordinate` →
`scripts/emit_coordinate.py`; run `scripts/coverage_report.py` to see which axes still lack
evidence — those are the extraction targets to cover next, per the 2026-07-15 契約選補證據 ruling).

Phase 4 also renders the person-facing INSIGHT HTML, parallel to `scripts/render_growth.py`:

```bash
python3 scripts/render_insight.py [--project SUBSTR|all] [--source-scope …] [--blind-spots …]
                                  [--lang zh-TW|en]
```

→ `output/insight-<date>-<project|all>.html` — a self-contained BMW-styled report with a pure-CSS
8-tile 觀察熱度 (evidence-coverage) heatmap + per-domain forward growth directions (Emil ruling
2026-07-15: retires the Chart.js 8-axis radar; no Chart.js is used/inlined). Each tile's color
intensity falls into one of `--heat-bands` bands (default 5, supports {5,8}) mapped from
observation frequency, with NO visible numbers; a 全部複製 bulk-copy button sits alongside the
per-card copy buttons. It surfaces `growth_hint` ONLY (never `signal_tier`/rung/score — RL4-ii,
see top of file), reuses the same `forward_only` + `collect()` logic as `render_growth.py`, and
MUST pass `check-visibility-seam.sh` gate (c) (now extended to scan `output/**/*.html` with
`<script>`/`<style>` stripped). The heatmap color is observation FREQUENCY (coverage), never a
capability level 0-3 — 顏色=頻率非能力.

**Language (Emil order 2026-07-15):** the report renders in zh-TW by default (預設中文). After
rendering, ASK the operator one short question: 是否要再產生其他語系版本?(目前支援 en) — if yes,
re-run `render_insight.py --lang en` (output gets the `-en` filename suffix, e.g.
`insight-<date>-<project|all>-en.html`, so both versions coexist). Only the report CHROME
(labels/headings/templates) is localized — observation content (`growth_hint`/bias text) always
stays in whatever language it was extracted in, regardless of `--lang`.
