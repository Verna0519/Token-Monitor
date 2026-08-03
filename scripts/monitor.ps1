# monitor.ps1 - PowerShell front-end for the LOCAL run monitor (scripts/run_log.py).
#
# Same air-gapped design as run_log.py: pure-local, NO egress, writes only to worktemp/run-log.jsonl.
# This file adds ZERO new behaviour - it just wraps run_log.py in convenient PowerShell functions and
# handles the run-id grouping with PowerShell ($env:) syntax instead of bash (export).
#
# USAGE - dot-source it once per PowerShell session (note the leading dot + space):
#     . .\scripts\monitor.ps1
# then:
#     Start-Monitor                                             # open a run (groups the pipeline)
#     Invoke-Monitored scan  python scripts\scan_sessions.py --max 30
#     Import-ScanLog                                            # scan volume -> metrics
#     # ...run the extract-capability skill in Claude Code, then:
#     Import-SkillLog                                           # per sub-agent from worktemp\agent-out-*.json
#     Invoke-Monitored aggregate  python scripts\aggregate_signals.py worktemp\agent-out-1.json
#     # ...run the emit-coordinate workflow in Claude Code, then:
#     Import-WorkflowLog worktemp\emit-result.json             # per axis-agent
#     Show-MonitorReport ; Show-MonitorTrend ; Show-MonitorCoverage
#
# Compatible with Windows PowerShell 5.1 (no PS7-only syntax).

$script:MonRepoRoot = Split-Path -Parent $PSScriptRoot
$script:MonRunLog   = Join-Path $PSScriptRoot 'run_log.py'

# Resolve a python interpreter once (python -> py -> python3).
$script:MonPy = $null
foreach ($c in 'python', 'py', 'python3') {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) { $script:MonPy = $cmd.Source; break }
}
if (-not $script:MonPy) {
    Write-Warning "No python interpreter found on PATH (tried python / py / python3). Monitor functions will fail."
}

function Invoke-RunLog {
    # Low-level pass-through to run_log.py from the repo root. Most users call the friendly wrappers below.
    [CmdletBinding()]
    param([Parameter(ValueFromRemainingArguments = $true)] [string[]] $Args)
    Push-Location $script:MonRepoRoot
    try { & $script:MonPy $script:MonRunLog @Args }
    finally { Pop-Location }
}

function Start-Monitor {
    # Open a fresh run and remember its id in $env:RUN_LOG_RUN_ID so every step this session groups together.
    [CmdletBinding()] param()
    $id = (& $script:MonPy $script:MonRunLog new-run).Trim()
    $env:RUN_LOG_RUN_ID = $id
    Write-Host "monitor run opened: $id" -ForegroundColor Green
    Write-Host "(every run_log step this session groups under it until you call Stop-Monitor)"
}

function Stop-Monitor {
    # Close the current run grouping (the next Start-Monitor opens a new one).
    [CmdletBinding()] param()
    Remove-Item Env:RUN_LOG_RUN_ID -ErrorAction SilentlyContinue
    Write-Host "monitor run closed."
}

function Invoke-Monitored {
    # Run a mechanical command under the monitor: records status / duration / exit + a stdout tail.
    #   Invoke-Monitored scan python scripts\scan_sessions.py --max 30
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true, Position = 0)] [string] $Step,
        [Parameter(ValueFromRemainingArguments = $true)] [string[]] $Command
    )
    if (-not $Command) { throw "Invoke-Monitored: give a command, e.g. Invoke-Monitored scan python scripts\scan_sessions.py" }
    Invoke-RunLog wrap --step $Step -- @Command
}

function Import-ScanLog {
    # Record scan volume (sessions_in_index / total_jsonl_seen) from worktemp\session-index.json.
    [CmdletBinding()] param([string] $Index)
    if ($Index) { Invoke-RunLog ingest-scan --index $Index } else { Invoke-RunLog ingest-scan }
}

function Import-SkillLog {
    # One event per extract-capability sub-agent output (worktemp\agent-out-*.json).
    [CmdletBinding()] param()
    Invoke-RunLog ingest-skill
}

function Import-WorkflowLog {
    # One event per emit-coordinate per-axis agent, from the workflow result file.
    [CmdletBinding()] param([Parameter(Mandatory = $true, Position = 0)] [string] $Result)
    Invoke-RunLog ingest-workflow --result $Result
}

function Add-MonitorEvent {
    # Append a manual event for an interactive step. -Kv takes key=value pairs.
    #   Add-MonitorEvent growth-note ok -Kind script -Unit render_growth.py -Kv domains=8
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true, Position = 0)] [string] $Step,
        [Parameter(Mandatory = $true, Position = 1)] [ValidateSet('ok', 'fail', 'running')] [string] $Status,
        [string] $Kind = 'skill',
        [string] $Unit,
        [string[]] $Kv,
        [string] $Note
    )
    $a = @('event', '--step', $Step, '--status', $Status, '--kind', $Kind)
    if ($Unit) { $a += @('--unit', $Unit) }
    if ($Note) { $a += @('--note', $Note) }
    if ($Kv)   { $a += @('--kv') + $Kv }
    Invoke-RunLog @a
}

function Show-MonitorReport   { [CmdletBinding()] param([int] $Runs = 5) Invoke-RunLog report --runs $Runs }
function Show-MonitorTrend    { [CmdletBinding()] param([int] $Last)  if ($Last) { Invoke-RunLog trend --last $Last }    else { Invoke-RunLog trend } }
function Show-MonitorCoverage { [CmdletBinding()] param([int] $Last)  if ($Last) { Invoke-RunLog coverage --last $Last } else { Invoke-RunLog coverage } }
function Clear-MonitorLog     { [CmdletBinding()] param() Invoke-RunLog clear }

function Get-TokenReport {
    # Token usage by conversation / project / skill, read from the Claude Code transcripts.
    #   Get-TokenReport                 # all projects
    #   Get-TokenReport -Project aocc   # filter, -Days 7, -IncludeNested, -Top 15
    [CmdletBinding()]
    param([string] $Project, [int] $Days, [switch] $IncludeNested, [int] $Top = 10)
    $a = @('token_report.py')
    if ($Project) { $a += @('--project', $Project) }
    if ($Days)    { $a += @('--days', $Days) }
    if ($IncludeNested) { $a += @('--include-nested') }
    $a += @('--top', $Top)
    $render = Join-Path $PSScriptRoot 'token_report.py'
    Push-Location $script:MonRepoRoot
    try { & $script:MonPy $render @($a[1..($a.Count-1)]) } finally { Pop-Location }
}

function Get-CloudUsage {
    # OPT-IN cloud fetch (EGRESS): pull real per-product $ spend from the Claude Enterprise
    # Analytics API into worktemp/cloud-usage.json. No-ops (air-gap preserved) unless
    # ANALYTICS_API_KEY is set in the environment. Time range: -Days N | -Since/-Until.
    [CmdletBinding()]
    param([int] $Days, [string] $Since, [string] $Until, [switch] $PrintRequest)
    $a = @()
    if ($PrintRequest) { $a += '--print-request' }
    if ($Days)  { $a += @('--days', $Days) }
    if ($Since) { $a += @('--since', $Since); if ($Until) { $a += @('--until', $Until) } }
    Push-Location $script:MonRepoRoot
    try { & $script:MonPy (Join-Path $PSScriptRoot 'fetch_usage_cloud.py') @a } finally { Pop-Location }
}

function Show-TokenDashboard {
    # Bring up the TOKEN dashboard (HTML): compute usage for a time range -> limit % -> rebuild -> open.
    # Time range (pick one; else config/usage-limits.json .window; else all time):
    #   tokens -Today | -Week | -Month | -Days N | -Since 2026-07-01 [-Until 2026-07-15] | -All
    #   tokens -NoOpen            # regenerate only, don't launch a browser
    #   tokens -Cloud             # ALSO fetch real per-product $ from the Enterprise Analytics API (EGRESS; needs ANALYTICS_API_KEY)
    [CmdletBinding()]
    param(
        [switch] $Today, [switch] $Week, [switch] $Month, [switch] $All,
        [int] $Days, [string] $Since, [string] $Until,
        [switch] $Cloud, [switch] $NoOpen, [switch] $SkipTokens
    )
    $repo = $script:MonRepoRoot
    $tok = @(); $lbl = ''
    if     ($All)        { $tok = @();                               $lbl = 'all time' }
    elseif ($Today)      { $tok = @('--since', (Get-Date).ToString('yyyy-MM-dd')); $lbl = 'today' }
    elseif ($Month)      { $tok = @('--days', 30);                   $lbl = 'last 30 days' }
    elseif ($Week)       { $tok = @('--days', 7);                    $lbl = 'last 7 days' }
    elseif ($Days)       { $tok = @('--days', $Days);                $lbl = "last $Days days" }
    elseif ($Since)      { $tok = @('--since', $Since); if ($Until) { $tok += @('--until', $Until) }; $lbl = "$Since..$(if($Until){$Until}else{'now'})" }
    else {
        $cfg = Join-Path $repo 'config\usage-limits.json'
        if (Test-Path $cfg) {
            try {
                $w = (Get-Content $cfg -Raw -Encoding UTF8 | ConvertFrom-Json).window
                if ($w) {
                    if ($w.mode -eq 'days' -and $w.days) { $tok = @('--days', $w.days); $lbl = "config: last $($w.days) days" }
                    elseif ($w.since) { $tok = @('--since', $w.since); if ($w.until) { $tok += @('--until', $w.until) }; $lbl = 'config range' }
                }
            } catch {}
        }
        if (-not $lbl) { $lbl = 'all time (no config window)' }
    }
    Push-Location $repo
    try {
        if (-not $SkipTokens) {
            Write-Host ("token window: {0}" -f $lbl) -ForegroundColor DarkGray
            & $script:MonPy (Join-Path $PSScriptRoot 'token_report.py') @tok | Out-Null
            & $script:MonPy (Join-Path $PSScriptRoot 'cowork_report.py') @tok | Out-Null
        }
        if ($Cloud) {
            Write-Host "cloud fetch (EGRESS) requested..." -ForegroundColor DarkGray
            & $script:MonPy (Join-Path $PSScriptRoot 'fetch_usage_cloud.py') @tok
        }
        & $script:MonPy (Join-Path $PSScriptRoot 'render_dashboard.py')
    } finally { Pop-Location }
    $out = Join-Path $repo 'worktemp\dashboard.html'
    if (-not $NoOpen -and (Test-Path $out)) { Invoke-Item $out }
}
Set-Alias -Name Show-MonitorDashboard -Value Show-TokenDashboard -Scope Global   # back-compat
Set-Alias -Name tokens -Value Show-TokenDashboard -Scope Global                  # short one-word command

function Show-TokenMonitor {
    # In-terminal VISUAL token monitor: colored horizontal bars by conversation / project / skill.
    # Taiwan time (UTC+8) by default; filter with -Days N or -Since/-Until (Taiwan dates).
    #   Show-TokenMonitor                       # all time, all three views
    #   Show-TokenMonitor -Days 7 -By skill
    #   Show-TokenMonitor -Since 2026-07-01 -Until 2026-07-15 -Top 10
    [CmdletBinding()]
    param(
        [ValidateSet('conversation', 'project', 'skill', 'all')] [string] $By = 'all',
        [int] $Days,
        [string] $Since,
        [string] $Until,
        [int] $Top = 8,
        [switch] $IncludeNested,
        [int] $UtcOffset = 8,
        [int] $Width = 34
    )
    try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
    $tmp = Join-Path $env:TEMP ("token-monitor-{0}.json" -f $PID)
    $a = @('--utc-offset', $UtcOffset, '--top', [Math]::Max($Top, 50), '--json-out', $tmp)
    if ($Days)  { $a += @('--days', $Days) }
    if ($Since) { $a += @('--since', $Since) }
    if ($Until) { $a += @('--until', $Until) }
    if ($IncludeNested) { $a += @('--include-nested') }
    Push-Location $script:MonRepoRoot
    try { & $script:MonPy (Join-Path $PSScriptRoot 'token_report.py') @a | Out-Null } finally { Pop-Location }
    if (-not (Test-Path $tmp)) { Write-Warning "token_report produced no output"; return }
    $d = Get-Content $tmp -Raw -Encoding UTF8 | ConvertFrom-Json
    Remove-Item $tmp -ErrorAction SilentlyContinue

    $sc = $d.scope; $win = if ($sc.window_since) { "$($sc.window_since) -> $(if($sc.window_until){$sc.window_until}else{'now'})" } else { 'all time' }
    Write-Host ""
    Write-Host ("  TOKEN MONITOR  |  {0}  |  window: {1}" -f $sc.timezone, $win) -ForegroundColor White
    Write-Host ("  total {0:N0} tokens  |  output {1:N0}  |  {2} turns  |  {3} file(s){4}" -f `
        [int64]$d.totals.total, [int64]$d.totals.output_tokens, [int]$d.totals.msgs, [int]$sc.files_counted, `
        $(if ($sc.window_since) { "  |  skipped $($sc.skipped_out_window) out-of-window" } else { "" })) -ForegroundColor DarkGray

    function Render-Section($title, $rows, $labelFn) {
        if (-not $rows) { return }
        Write-Host ""
        Write-Host ("  $title") -ForegroundColor Yellow
        $max = ($rows | Measure-Object -Property total -Maximum).Maximum
        if (-not $max -or $max -le 0) { $max = 1 }
        foreach ($r in ($rows | Select-Object -First $Top)) {
            $label = (& $labelFn $r)
            if ($label.Length -gt 22) { $label = $label.Substring(0, 21) + '...' }
            $len = [int][Math]::Round(($r.total / $max) * $Width)
            if ($len -lt 1) { $len = 1 }
            $bar = [string]([char]0x2588) * $len
            Write-Host ("  {0,-22} " -f $label) -NoNewline
            Write-Host $bar -NoNewline -ForegroundColor Cyan
            Write-Host ("{0} {1,13:N0}  out {2,10:N0}" -f (' ' * ($Width - $len + 1)), [int64]$r.total, [int64]$r.output_tokens) -ForegroundColor DarkGray
        }
    }

    if ($By -in 'conversation', 'all') {
        Render-Section 'BY CONVERSATION' $d.by_conversation { param($r) if ($r.title) { $r.title } else { ($r.session -as [string]).Substring(0, [Math]::Min(12, ($r.session -as [string]).Length)) } }
    }
    if ($By -in 'project', 'all') {
        Render-Section 'BY PROJECT' $d.by_project { param($r) (($r.project -as [string]) -replace '[\\/]+$', '') -split '[\\/]' | Select-Object -Last 1 }
    }
    if ($By -in 'skill', 'all') {
        Render-Section 'BY SKILL' $d.by_skill { param($r) $r.skill }
    }
    Write-Host ""
}

function Watch-TokenMonitor {
    # Live in-terminal token monitor: clears + redraws every -Every seconds. Ctrl+C to stop.
    [CmdletBinding()]
    param([int] $Every = 60,
          [ValidateSet('conversation', 'project', 'skill', 'all')] [string] $By = 'all',
          [int] $Days, [string] $Since, [string] $Until, [int] $Top = 8,
          [switch] $IncludeNested, [int] $UtcOffset = 8)
    Write-Host "live token monitor - refreshing every $Every s. Ctrl+C to stop." -ForegroundColor Cyan
    while ($true) {
        Clear-Host
        Show-TokenMonitor -By $By -Days $Days -Since $Since -Until $Until -Top $Top -IncludeNested:$IncludeNested -UtcOffset $UtcOffset
        Write-Host ("  refreshed {0:yyyy-MM-dd HH:mm:ss} (Taiwan)  -  Ctrl+C to stop" -f (Get-Date)) -ForegroundColor DarkGray
        Start-Sleep -Seconds $Every
    }
}

function Watch-MonitorDashboard {
    # Keep the dashboard live: regenerate every -Every seconds; the page auto-reloads to match.
    # -Cloud also re-fetches real per-product $ from the Enterprise Analytics API each cycle (EGRESS;
    # needs ANALYTICS_API_KEY, else no-ops). This is an OPERATOR-run FOREGROUND loop (not a background
    # agent mode, not a stop-hook) - it runs in YOUR terminal and stops on Ctrl+C. Open the tab once.
    [CmdletBinding()] param([int] $Every = 300, [switch] $Cloud)
    $render = Join-Path $PSScriptRoot 'render_dashboard.py'
    $token  = Join-Path $PSScriptRoot 'token_report.py'
    $cloud  = Join-Path $PSScriptRoot 'fetch_usage_cloud.py'
    $out    = Join-Path $script:MonRepoRoot 'worktemp\dashboard.html'
    Push-Location $script:MonRepoRoot
    try {
        $cycle = {
            & $script:MonPy $token | Out-Null
            if ($Cloud) { & $script:MonPy $cloud | Out-Null }
            & $script:MonPy $render --refresh $Every | Out-Null
        }
        & $cycle
        if (Test-Path $out) { Invoke-Item $out }
        Write-Host ("watching - regenerating every $Every s{0}. Ctrl+C to stop." -f ($(if($Cloud){' (with cloud fetch)'}else{''}))) -ForegroundColor Cyan
        while ($true) {
            Start-Sleep -Seconds $Every
            & $cycle
            Write-Host ("refreshed {0:HH:mm:ss}" -f (Get-Date)) -ForegroundColor DarkGray
        }
    } finally { Pop-Location }
}

Write-Host "run monitor loaded." -ForegroundColor Cyan
Write-Host "  token (Taiwan time): Get-TokenReport | Show-TokenMonitor [-Days N|-Since d -Until d] [-By skill] | Watch-TokenMonitor" -ForegroundColor Cyan
Write-Host "  execution: Start-Monitor | Invoke-Monitored <step> <cmd..> | Import-ScanLog/-SkillLog/-WorkflowLog | Add-MonitorEvent | Show-MonitorReport/-Trend/-Coverage | Stop-Monitor | Clear-MonitorLog" -ForegroundColor Cyan
Write-Host "  dashboard (HTML): tokens [-Today|-Week|-Month|-Days N|-Since d -Until d|-All] [-Cloud]  (= Show-TokenDashboard) | Watch-MonitorDashboard" -ForegroundColor Cyan
Write-Host "  cloud (EGRESS, opt-in): Get-CloudUsage [-Days N|-Since d -Until d]  (needs ANALYTICS_API_KEY; no-ops without it)" -ForegroundColor Cyan
