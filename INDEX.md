# INDEX — repo map + dual-layer classification

> Fresh-agent map of this repo (personal capability agent — coordinate model, 2026-07-15).
> Every path is **[S] shareable (git-tracked)** or **[P] private (gitignored, deny-by-default)**.
> The seam is **directed visibility** (RL4): identity never crosses UP, and no score/rung/tier
> vocabulary ever reaches the person DOWNWARD; the ONLY upward artifact is a shape-checked
> capability **coordinate** whose 0–3 levels are positions on the map, not grades. See
> `decisions/0001-standalone-l3-and-visibility-seam.md` and `scripts/check-visibility-seam.sh`.

## Shareable core [S]

| Path | Purpose |
|------|---------|
| `CLAUDE.md` | Identity + red lines RL1–RL4 (RL4 = directed visibility, highest-risk) |
| `README.md` | What it does + setup |
| `INDEX.md` | This map |
| `manifest.yaml` | standalone-l3 schema: fork lineage, deps, `dual_layer` classification |
| `.env.template` | Secrets template (empty — the pipeline needs no API key) |
| `.gitignore` | Deny-by-default seam enforcer (ignore all, un-ignore classified [S] paths) |
| `decisions/0001-*.md` | ADR: standalone-l3 + directed-visibility seam (architecture lock) |
| `planning/BUILD-PLAN.md` | Build phases + roadmap |
| `planning/COLD-START.md` | Cold-start mechanism reference (preflight + operator-driven onboard; native-Windows story; optional-hook ruling) |
| `config/path-mappings.yaml` | The single machine-path indirection layer (template; RL2) |
| `config/personal-domains.yaml` | 8 capability domains/axes + authored 0–3 `rung_rubric` (definition/calibration layer, Phase 1b; not an output field) |
| `config/extraction.schema.json` | Per-session signal contract (8 domains × present/signal_tier/evidence_refs/growth_hint + bias_flags); the shape gate + coverage report single-source the axis list from here (the emitter + workflow carry their own mirrored copy) |
| `config/STATE-template.md` | Identity-agnostic state template |
| `scripts/` | Gates + the deterministic pipeline backbone (see below) |
| `.claude/settings.json` | Harness settings |
| `.claude/skills/extract-capability/` | Ingestion skill: scan → parallel per-session extraction → aggregate (abstract signals only, never verbatim) |
| `.claude/workflows/emit-coordinate.js` | Coordinate assessment: one agent per axis, grounded in that axis's `rung_rubric`; level null when evidence cannot place (never absence→0) |
| `self-growth/README.md` | Propose-only promotion rule (ratified = operator hand marker) |
| `self-growth/insight-log-core.md` | Identity-agnostic proposed methodology log |

### scripts/ (key files)

- `scan_sessions.py` — Phase-1 session index (metadata only; roots via path-mappings, loud-fail).
- `aggregate_signals.py` — fence-tolerant merge of sub-agent output; schema-validated, fail-closed.
- `validate_extraction.py` — fail-closed signal validation + RL4 identity/score content backstop.
- `_growth_hint.py` — shared forward-only normalizer (no retrospective-assessment tone).
- `render_growth.py` — personal growth note (zh-TW, forward-looking, NO score vocabulary).
- `coverage_report.py` — per-axis evidence coverage → names the extraction targets (補證據).
- `emit_coordinate.py` — validates the workflow result, mints a fresh opaque `sub-` id, writes the coordinate upload + the local basis file; REFUSES on any unplaced axis (strict contract 0.1).
- `_check_coordinate_shape.py` — coordinate shape check: exactly `{format, version, submission_id, period, position}`, opaque `sub-` id, int 0–3 levels, nothing else (called by seam gate (b)).
- `check-visibility-seam.sh` — **RL4 gate**: (a) private buckets/configs never tracked; (b) `handoff/` accepts ONLY shape-checked `coordinate-*.json` (digest pipeline retired 2026-07-15) + identity-leak scan; (c) no score/rung/tier vocabulary in `output/` (exempt: `coordinate-basis-*`); (d) no credential store in any working bucket.
- `validate-selfcontainment.sh` — standalone-l3 exit gate (scrub-grep, no baked paths, backbone).
- `preflight.py` — cold-start READ-ONLY preflight (portable, pure-stdlib): checks setup + known migration problems, writes `worktemp/preflight-report.json` (private) + human summary, non-zero exit when setup incomplete (RL2). Never modifies anything.
- `onboard.py` — cold-start FIX helper (mechanical, idempotent): writes the private gitignored setup files (.env / STATE.md / path-mappings.filled.yaml) + `--normalize-eol`, from operator-confirmed answers. Never edits a tracked template.
- `run_log.py` — LOCAL air-gapped execution monitor (pure-stdlib, NO egress): per-skill/agent/script status + duration + key counts, written ONLY to `worktemp/run-log.jsonl` (private). Non-invasive (modifies no existing script); the in-repo alternative to an external tracing service, chosen for RL1/RL4. Subcommands: `wrap` (mechanical scripts), `ingest-skill` / `ingest-scan` / `ingest-workflow` (per-sub-agent / scan-volume / per-axis-agent from their artifacts), `event` (interactive step), `report` (the dashboard), `trend` (coordinate placed/total over time), `coverage` (sessions/signals volume over time).
- `monitor.ps1` — PowerShell front-end for `run_log.py` / `token_report.py` / `render_dashboard.py` (dot-source `. .\scripts\monitor.ps1`): friendly functions (`Start-Monitor`, `Invoke-Monitored`, `Import-ScanLog`/`Import-SkillLog`/`Import-WorkflowLog`, `Add-MonitorEvent`, `Get-TokenReport`, `Show-TokenMonitor`/`Watch-TokenMonitor` (in-terminal VISUAL token bars, Taiwan time, `-Days`/`-Since`/`-Until`/`-By` filters; `Watch-` = live redraw loop), `Show-MonitorReport`/`Show-MonitorTrend`/`Show-MonitorCoverage`, `Show-TokenDashboard` (alias `tokens`, alias `Show-MonitorDashboard`) = one-command "bring up the token table": pick a time range (`-Today`/`-Week`/`-Month`/`-Days N`/`-Since`/`-Until`/`-All`, else `config/usage-limits.json .window`) -> compute usage -> limit % -> rebuild HTML -> open; `Watch-MonitorDashboard` = operator-run foreground regenerate-loop pairing with `render_dashboard.py --refresh`). Handles run-id grouping with `$env:` syntax. ASCII-only source (PS 5.1 reads UTF-8-no-BOM as ANSI); CJK data comes from JSON read with `-Encoding UTF8`. Pure wrapper, zero-egress.
- `fetch_usage_cloud.py` [S] — **OPT-IN cloud fetcher (EGRESS — a documented exception to RL1, operator-ruled 2026-07-28)**: calls the Claude Enterprise Analytics API `cost_report` (Analytics API key via `ANALYTICS_API_KEY`, `x-api-key`) for real per-product $ spend (chat/claude_code/cowork/…) → `worktemp/cloud-usage.json` (private). No-ops without the key (air-gap preserved). NEVER called by the core extract/coordinate pipeline; runs only on explicit `Get-CloudUsage` / `tokens -Cloud`.
- `token_report.py` — LOCAL token-usage report (read-only over the Claude Code transcripts, RL2-resolved — the same corpus `scan_sessions.py` ingests): rolls `message.usage` up by CONVERSATION / PROJECT / SKILL (via `attributionSkill`). **Taiwan time (UTC+8) by default**; time-window filter by turn timestamp (`--days N` | `--since`/`--until`, `--utc-offset` to change tz). stdout + `worktemp/token-usage.json` (private). Declares coverage scope (nested sub-agent/workflow excluded unless `--include-nested`; out-of-window + no-timestamp turns reported). Stays local — never an upward artifact.
- `cowork_report.py` — LOCAL **Cowork** usage report (read-only over the desktop app's Cowork "local agent mode" sessions: `<COWORK_SESSIONS_ROOT>/**/audit.jsonl`; OS-default probed, overridable via `COWORK_SESSIONS_ROOT` in path-mappings). Per CHAT ROOM (`session_id`, named from the session sidecar `local_<uuid>.json` → `title`, matched on `cliSessionId`) + per DAY, with **REAL $** from `total_cost_usd` (one unit per `result` entry; token counts + per-model split taken from `modelUsage`, the same basis as cost). Verified against official list pricing to **0.01%**. Zero-egress; no-ops cleanly when Cowork is absent. → `worktemp/cowork-usage.json` (private). Monitor-only — never feeds the extract/coordinate pipeline.
- `count_tokens.py` — pre-send INPUT-token estimate. OFFLINE heuristic by default (no key, no network); **exact via `POST /v1/messages/count_tokens` only when `ANTHROPIC_API_KEY` is set (opt-in EGRESS)**. Counts input only — not output, not billed usage (use `token_report.py` for actual usage).
- `render_dashboard.py` — renders a token-focused SELF-CONTAINED HTML dashboard (inline CSS/JS/SVG, NO network/CDN): **Token usage · who spent what** bars — by CONVERSATION / PROJECT / SKILL / AGENT, each row expandable to NAME its members (which chats, which skills) — + **Usage over time** daily curve (per-day x-axis, 3/7/30-day filter, default 7d, day-over-day delta) + the **Cowork** block (per chat room + per day with REAL $, token composition, per-model rates). **Shows only measured numbers**: all estimated-$ output was removed (its per-token rate was a circular assumption contradicted ~21x by measured Cowork $/token), and the account spend block renders ONLY when a real spend was fetched via `-Cloud` — a stale hand-typed $ is never displayed as current. Reads `worktemp/token-usage.json` + `worktemp/cowork-usage.json` + `config/usage-limits.json` (falls back to the template = unset). Output → `worktemp/dashboard.html` (private). The air-gapped alternative to a cloud dashboard (RL1/RL4).
- `README-monitor.md` [S] — operations manual for the whole local monitoring suite (token usage + execution + dashboard + the `tokens` command + config). Air-gapped rationale, quick start, field glossary, troubleshooting.
- `config/usage-limits.template.json` [S] → copy to `config/usage-limits.json` [P] and set your plan's Chat & Claude Code / Cowork limits; the dashboard's % gauges read it. Real-time server quota is never fetched (RL1).

## Private layer [P] — gitignored, never tracked

| Path | What lands here |
|------|-----------------|
| `raw-sessions/` | Extracted per-session signals (`capability-signals.json`) + identity-bearing analysis — highest sensitivity |
| `handoff/` | Coordinate uploads (`coordinate-<sid>.json`) — the ONLY file type that may leave this machine, hand-carried to the dept map inbox |
| `output/` | Personal growth note (`growth-note.md`) + `coordinate-basis-<sid>.md` (per-axis rationale — stays local, never carried) |
| `worktemp/` | Scratch: session index, `run-log.jsonl` (local execution monitor), `dashboard.html` (rendered monitor view), audit/pilot records, archives (e.g. `retired-digest-pipeline-2026-07-15/`) |
| `config/STATE.md` | Live operational state + Next Action (real machine paths/coverage) |
| `config/path-mappings.filled.yaml` | Filled real machine paths |
| `self-growth/insight-log-private.md` | Any identity-bearing insight |
| `.claude/settings.local.json` | Harness machine-local permission ledger |
| `.env` | Filled secrets |
| `.agents/`, `.codex/` | Local harness/tool dirs — caught by deny-by-default, never tracked |

## Pipeline (which bucket feeds which)

`scan_sessions.py` (worktemp/ index) → `extract-capability` skill → `aggregate_signals.py`
(raw-sessions/ signals, fence-tolerant + schema-validated) → (a) `render_growth.py` (output/
growth note) and (b) `emit-coordinate` workflow + `emit_coordinate.py` (handoff/ coordinate +
output/ basis). `coverage_report.py` names which axes still need evidence.

Scope (operator ruling 2026-07-15): the 8 axes measure how the person **operates AI**, not
domain/professional expertise. A coordinate is therefore portable across departments, and a zone
fit claims only that AI-operation capability meets the project's per-axis band — never
professional qualification to carry out the project (judged elsewhere, by humans).

## Resumption

`CLAUDE.md` → this `INDEX.md` → `config/STATE.md` → continue from Next Action.
