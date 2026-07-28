# Local Monitoring Suite

A pure-local, **air-gapped** monitor for this agent's token spend and pipeline execution. Nothing
leaves the machine: pure-stdlib Python + PowerShell wrappers, **zero network**, output written only
to `worktemp/` (private, gitignored).

> **Why local, not a cloud tracer?** External tracing (e.g. Langfuse Cloud) was rejected: a trace
> payload would carry identity-bearing session evidence off-machine, violating RL1 (runtime
> self-contained) and RL4 (directed-visibility seam). See [`../CLAUDE.md`](../CLAUDE.md) §1. Token
> spend also isn't in this repo's scripts (§5 — they make no LLM call); it is read out of the
> Claude Code transcripts, the same read-only corpus the pipeline ingests.

---

## Components

| File | Role |
|------|------|
| `token_report.py` | Reads the Claude Code transcripts, rolls token usage up by **conversation / project / skill**. Taiwan time; time-window filter. stdout + `worktemp/token-usage.json`. |
| `render_dashboard.py` | Renders a self-contained HTML dashboard (usage-limit gauges + token bars + daily curve). No network/CDN. -> `worktemp/dashboard.html`. |
| `run_log.py` | Records **execution** of the deterministic pipeline (scan/aggregate/emit) + skill/agent steps -> `worktemp/run-log.jsonl`. |
| `monitor.ps1` | PowerShell front-end: friendly commands for everything below. |
| `config/usage-limits.template.json` | Copy to `config/usage-limits.json` (private) and set your plan limits + reporting window. |

---

## Quick start (PowerShell)

```powershell
# from the repo root, once per shell (note the leading dot + space):
. .\scripts\monitor.ps1

# bring up the token dashboard (default window from config; opens in your browser):
tokens
```

If dot-sourcing is blocked by execution policy, allow local scripts for THIS shell only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

---

## Token usage (main use)

### 1. Set your limits (once)

```powershell
Copy-Item .\config\usage-limits.template.json .\config\usage-limits.json
```

Edit `config/usage-limits.json` (private, gitignored):

```json
{
  "window":    { "mode": "days", "days": 7 },
  "chat_code": { "label": "Chat & Claude Code", "unit": "tokens", "metric": "total", "limit": <your token ceiling> },
  "cowork":    { "label": "Cowork credit", "unit": "credits", "limit": <your credits>, "used": <credits used> }
}
```

- `chat_code.used` is computed locally (token total in the window); set `limit` to your plan ceiling.
- `cowork` is entered manually — Cowork runs on a separate credit pool that is **not** in local transcripts.
- `window` sets the default reporting period for the `used` figure and the daily curve.

> **Honesty note:** the gauge % is `local-used / your-configured-limit`. Real-time server quota is
> **not** fetched (that would break the air-gap). The dashboard says so on its face.

### 2. Bring up the token table, filtered by time range

```powershell
tokens                 # default = config window
tokens -Today          # today (Taiwan time)
tokens -Week           # last 7 days
tokens -Month          # last 30 days
tokens -Days 14        # last N days
tokens -Since 2026-07-01 -Until 2026-07-15
tokens -All            # all time
tokens -NoOpen         # regenerate only, do not launch a browser
```

`tokens` is an alias of `Show-TokenDashboard` (and of the older name `Show-MonitorDashboard`). Each
run: compute usage for the range -> limit % -> rebuild HTML -> open.

### 3. Other views of the same data

```powershell
Show-TokenMonitor -By skill -Week      # colored bars IN the terminal (Taiwan time; same filters)
Watch-TokenMonitor -Every 60           # live terminal view, redraw every 60s (Ctrl+C to stop)
Get-TokenReport -Days 7                # plain-text tables
```

### Field glossary

| Field | Meaning |
|-------|---------|
| `total` | all tokens in range (dominated by cache_read; a big number is normal) |
| `output` (shown as `out`) | tokens the model actually generated |
| `%` | share of the window total |
| `cache read` | context re-read each turn (billed at a fraction) |
| `turns` | assistant turns |
| `usage limit %` | local usage / your configured limit; green <70% · amber 70-90% · red >=90% |

All times are **Taiwan (UTC+8)** by default. Change with `--utc-offset` on the Python scripts.

---

## The dashboard is a static file

The HTML embeds its data at generation time, so **refreshing the browser alone does not fetch new
data** — you must regenerate. `tokens` regenerates and opens. To keep an open tab live:

```powershell
Watch-MonitorDashboard -Every 300   # regenerate every 5 min; the page auto-reloads to match
```

`Watch-MonitorDashboard` is an operator-run **foreground** loop (not a background agent mode, not a
stop-hook) — it runs in your terminal and stops on Ctrl+C.

---

## Execution monitoring (the deterministic pipeline)

Separate from token usage: this tracks the scan/extract/aggregate/emit pipeline runs.

```powershell
Start-Monitor                                            # open a run (groups the steps)
Invoke-Monitored scan python scripts\scan_sessions.py --max 30
Import-ScanLog                                           # scan volume -> metrics
Import-SkillLog                                          # per extract-capability sub-agent
Invoke-Monitored aggregate python scripts\aggregate_signals.py worktemp\agent-out-1.json
Import-WorkflowLog worktemp\emit-result.json             # per emit-coordinate axis agent
Show-MonitorReport ; Show-MonitorTrend ; Show-MonitorCoverage
Stop-Monitor
```

- `Show-MonitorTrend` — coordinate placement (placed/8) over time.
- `Show-MonitorCoverage` — sessions / signals volume over time.
- `Add-MonitorEvent <step> ok -Kind script -Unit <name> -Kv k=v` — log an interactive step manually.
- `Clear-MonitorLog` — reset the run log.

---

## Files & privacy

Everything the monitor writes is inside `worktemp/` (or `config/usage-limits.json`) and is
**gitignored / never tracked** (RL4):

- `worktemp/token-usage.json` — token rollup (identity-bearing project paths + titles; local only)
- `worktemp/dashboard.html` — the rendered dashboard
- `worktemp/run-log.jsonl` — execution log
- `config/usage-limits.json` — your personal plan limits

The scripts read `~/.claude/projects` (the Claude Code transcripts) **read-only**, resolved via
`config/path-mappings.filled.yaml`. They never write outside this repo and never call the network.

---

## Troubleshooting

- **`. .\scripts\monitor.ps1` refuses to run** — execution policy. Use the `-Scope Process` line
  above (affects only the current shell).
- **CJK titles look garbled in the terminal** — `Show-TokenMonitor` sets the console to UTF-8; if a
  wrapper still garbles, your console font may lack CJK glyphs. The HTML dashboard always renders
  CJK correctly.
- **`monitor.ps1` must stay pure ASCII** — Windows PowerShell 5.1 reads a UTF-8-without-BOM `.ps1`
  as ANSI; a non-ASCII character in the source breaks parsing. CJK shown by the tools comes from
  JSON read with `-Encoding UTF8` at runtime, never from the script source.
- **"No python interpreter found"** — install Python 3.9+ (the scripts try `python`, then `py`,
  then `python3`).

---

## Enabling the cloud fetch (real per-product $ spend)

By default the dashboard is fully local (air-gapped) and shows no real $. To pull real
per-product spend (chat / claude_code / cowork) from the Claude Enterprise Analytics API:

1. **Get an Analytics API key.** The Enterprise **Primary Owner** creates it at
   `claude.ai > Organization settings > API` (enable public API access; scope `read:analytics`).
   Cost/usage figures are real only on **usage-based** Enterprise plans (seat-based plans show
   credit usage only).
2. **Put it in `.env`** (create from the template first if needed). Edit the line — no quotes, no
   spaces — and save:
   ```
   ANALYTICS_API_KEY=<your key>
   ```
   `.env` is gitignored, so the key stays on your machine and never reaches Git.
3. **Fetch + view:**
   ```powershell
   . .\scripts\monitor.ps1
   tokens -Cloud                        # fetch now + rebuild + open
   Watch-MonitorDashboard -Every 300 -Cloud   # or auto-refetch every 5 min
   ```

Without the key, `fetch_usage_cloud.py` no-ops and the dashboard stays air-gapped — the
"last fetched" line then reads "未連外抓取（手動 config）".

**How the timestamps behave** (why "last fetched" may look unchanged):
- The dashboard is a **static HTML snapshot** — pressing **F5 in the browser does NOT re-fetch**;
  it re-shows the same file. The `last fetched` time only advances when you **regenerate**
  (`tokens -Cloud` or the watch loop), because that's what re-runs the fetch.
- `last fetched` = when `fetch_usage_cloud.py` ran; `API 資料更新 <...>` = the API's own
  `data_refreshed_at`, which Anthropic updates only every ~4 hours — so a re-fetch within that
  window can legitimately show the same API timestamp.

## Sharing this repo (recipient setup)

This repo is safe to share — every piece of personal data lives in gitignored files, and the
shipped templates carry only placeholders. After cloning, each person fills their own:

1. **Copy the templates and fill your own values:**
   ```powershell
   Copy-Item config\usage-limits.template.json config\usage-limits.json   # your plan limits / reset / token_limit
   Copy-Item .env.template .env                                           # OPTIONAL: ANALYTICS_API_KEY (cloud fetch)
   ```
2. **(only if you'll run the capability pipeline)** fill `config/path-mappings.filled.yaml`
   (`CLAUDE_PROJECTS_ROOT`) — see `planning/COLD-START.md`.
3. **Run it:**
   ```powershell
   . .\scripts\monitor.ps1
   tokens                 # local token dashboard (air-gapped)
   tokens -Cloud          # ALSO fetch real per-product $ (needs ANALYTICS_API_KEY; EGRESS)
   ```

**What never ships with the repo** (all gitignored): `config/usage-limits.json` (your name + limits),
`.env` (your key), `worktemp/` (token stats, rendered dashboards, fetched cloud data),
`raw-sessions/`, `output/`, `handoff/`. Only the `*.template.json` / `.env.template` placeholders are
tracked, so each recipient's own numbers, name, and key stay on their machine.
