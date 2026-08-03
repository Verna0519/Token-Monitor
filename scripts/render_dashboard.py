#!/usr/bin/env python3
"""
render_dashboard.py — render a SELF-CONTAINED, token-focused HTML dashboard.

Reads worktemp/token-usage.json (from token_report.py) and config/usage-limits.json (your own plan
limits, private) and emits ONE standalone HTML file: all CSS/JS/SVG inline, ZERO external resources,
ZERO network. Open it in a browser or VS Code. Air-gapped by design (RL1); output is private (RL4).

Layout (token-focused, per operator request):
  1. Your usage limits — Chat & Claude Code and Cowork credit, each as a % gauge against a limit YOU
     set in config/usage-limits.json. The real-time server quota is NOT fetched (air-gapped) — the %
     is local-used / your-configured-limit, and the card says so.
  2. Token usage - who spent what — bars by conversation / project / skill, each with its % share.
  3. Usage over time — a daily token-usage curve.

Times are Taiwan (UTC+8) as carried in token-usage.json's scope.

Usage:
  render_dashboard.py [--token-json worktemp/token-usage.json] [--out worktemp/dashboard.html]
                      [--limits config/usage-limits.json] [--refresh SECONDS]
"""

import argparse
import json
import os
import sys
import time

# Force UTF-8 stdout so a CJK project path in a status print can't crash on a legacy console codepage.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_OUT = os.path.join(ROOT, "worktemp", "dashboard.html")
DEFAULT_TOKENS = os.path.join(ROOT, "worktemp", "token-usage.json")
DEFAULT_LIMITS = os.path.join(ROOT, "config", "usage-limits.json")
TEMPLATE_LIMITS = os.path.join(ROOT, "config", "usage-limits.template.json")


def load_json(path):
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def render(model, generated_at, refresh=0):
    if refresh and refresh > 0:
        meta = '<meta http-equiv="refresh" content="%d">' % refresh
        note = " &middot; auto-refreshing every %ds (regenerate the file to see new data)" % refresh
    else:
        meta, note = "", ""
    html = HTML_TEMPLATE
    html = html.replace("__REFRESH_META__", meta)
    html = html.replace("__REFRESH_NOTE__", note)
    html = html.replace("__DATA__", json.dumps(model, ensure_ascii=False))
    html = html.replace("__GENERATED__", generated_at)
    return html


def main():
    ap = argparse.ArgumentParser(description="Render a token-focused self-contained HTML dashboard.")
    ap.add_argument("--token-json", default=DEFAULT_TOKENS, help="token_report.py output ('-' to skip)")
    ap.add_argument("--limits", default=DEFAULT_LIMITS, help="usage-limits config (falls back to template)")
    ap.add_argument("--cloud-json", default=os.path.join(ROOT, "worktemp", "cloud-usage.json"),
                    help="fetch_usage_cloud.py output to embed (optional; '-' to skip)")
    ap.add_argument("--cowork-json", default=os.path.join(ROOT, "worktemp", "cowork-usage.json"),
                    help="cowork_report.py output to embed (optional; '-' to skip)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--refresh", type=int, default=0,
                    help="seconds between browser auto-reloads (0=off); pair with a regenerate loop")
    args = ap.parse_args()

    tokens = None if args.token_json == "-" else load_json(args.token_json)
    limits = load_json(args.limits) or load_json(TEMPLATE_LIMITS) or {}
    cloud = None if args.cloud_json == "-" else load_json(args.cloud_json)
    cowork = None if args.cowork_json == "-" else load_json(args.cowork_json)
    model = {"tokens": tokens, "limits": limits, "cloud": cloud, "cowork": cowork}
    generated = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    html = render(model, generated, refresh=args.refresh)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(html)
    tot = (tokens or {}).get("totals", {}).get("total", 0)
    print(f"ok: dashboard written -> {args.out}")
    print(f"ok: {tot:,} total tokens embedded; limits from "
          f"{'config/usage-limits.json' if load_json(args.limits) else 'template (unset)'}")
    print(f"open it: start {os.path.relpath(args.out, ROOT)}  (or open in VS Code / a browser)")


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
__REFRESH_META__
<title>Token Monitor — aocc-personal-ai-coach</title>
<style>
  :root{
    color-scheme: light;
    --page:#f9f9f7; --surface:#fcfcfb; --text:#0b0b0b; --text2:#52514e; --muted:#898781;
    --grid:#e1e0d9; --baseline:#c3c2b7; --border:rgba(11,11,11,.10);
    --series:#2a78d6; --series-soft:rgba(42,120,214,.16);
    --good:#0ca30c; --warn:#fab219; --high:#ef7d1a; --critical:#d03b3b;
  }
  @media (prefers-color-scheme: dark){
    :root:where(:not([data-theme="light"])){
      color-scheme: dark;
      --page:#0d0d0d; --surface:#1a1a19; --text:#fff; --text2:#c3c2b7; --muted:#898781;
      --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
      --series:#3987e5; --series-soft:rgba(57,135,229,.20);
    }
  }
  :root[data-theme="dark"]{
    color-scheme: dark;
    --page:#0d0d0d; --surface:#1a1a19; --text:#fff; --text2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --baseline:#383835; --border:rgba(255,255,255,.10);
    --series:#3987e5; --series-soft:rgba(57,135,229,.20);
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--page);color:var(--text);
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.45;}
  .wrap{max-width:1000px;margin:0 auto;padding:28px 20px 64px;}
  header{display:flex;align-items:baseline;justify-content:space-between;gap:16px;flex-wrap:wrap;}
  h1{font-size:20px;margin:0;font-weight:650;}
  .sub{color:var(--text2);font-size:13px;}
  .toggle{margin-left:auto;border:1px solid var(--border);background:var(--surface);color:var(--text2);
    border-radius:8px;padding:6px 12px;font-size:12px;cursor:pointer;}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px 20px;margin:18px 0;}
  .card h2{font-size:14px;margin:0 0 2px;font-weight:620;}
  .card .cap{color:var(--text2);font-size:12px;margin:0 0 14px;}
  .scopenote{font-size:12px;line-height:1.55;color:var(--text);background:rgba(250,178,25,.12);
    border:1px solid rgba(250,178,25,.55);border-radius:8px;padding:9px 12px;margin:0 0 12px;}
  .scopenote code{background:var(--grid);padding:1px 5px;border-radius:4px;font-size:11px;}
  /* gauges */
  .gauge{margin:16px 0;}
  .gauge-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px;gap:10px;}
  .gauge-name{font-size:14px;font-weight:600;}
  .gauge-pct{font-size:22px;font-weight:680;font-variant-numeric:tabular-nums;}
  .gauge-track{background:var(--grid);border-radius:6px;height:14px;overflow:hidden;}
  .gauge-fill{height:100%;border-radius:6px;min-width:2px;transition:width .3s;}
  .gauge-sub{color:var(--text2);font-size:12px;margin-top:5px;font-variant-numeric:tabular-nums;}
  .gauge-unset{color:var(--muted);font-size:12px;margin-top:5px;}
  /* bars */
  .sectlead{color:var(--text2);font-size:12.5px;margin:14px 0 10px;}
  .sectlead b{color:var(--text);}
  .bar-row{display:grid;grid-template-columns:200px 1fr auto;align-items:center;gap:12px;padding:5px 0;}
  .bar-name{font-size:13px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .bar-track{background:var(--grid);border-radius:4px;height:16px;overflow:hidden;}
  .bar-fill{background:var(--series);height:100%;border-radius:4px;min-width:2px;}
  .bar-val{font-size:12px;color:var(--text2);font-variant-numeric:tabular-nums;white-space:nowrap;}
  .bar-val b{color:var(--text);font-weight:640;}
  .bar-val .pct{color:var(--series);font-weight:640;margin-left:2px;}
  /* expandable per-conversation daily detail */
  details.bar-details{margin:0;}
  details.bar-details>summary{cursor:pointer;list-style:none;display:grid;grid-template-columns:14px 1fr;align-items:center;gap:0;}
  details.bar-details>summary::-webkit-details-marker{display:none;}
  details.bar-details>summary::before{content:"\25B8";color:var(--muted);font-size:11px;}
  details.bar-details[open]>summary::before{content:"\25BE";}
  details.bar-details>summary>.bar-row{padding:5px 0;}
  .subdays{margin:0 0 8px 30px;border-left:2px solid var(--grid);padding-left:12px;}
  .subday{display:flex;justify-content:space-between;gap:12px;font-size:11.5px;color:var(--text2);padding:2px 0;font-variant-numeric:tabular-nums;}
  .subday .sd-date{color:var(--text);}
  /* range filter buttons */
  .rangebar{display:flex;gap:6px;margin:0 0 12px;flex-wrap:wrap;}
  .rangebtn{border:1px solid var(--border);background:var(--surface);color:var(--text2);
    border-radius:7px;padding:4px 13px;font-size:12.5px;cursor:pointer;font-family:inherit;}
  .rangebtn:hover{border-color:var(--series);}
  .rangebtn.active{background:var(--series);color:#fff;border-color:var(--series);}
  .rangeinfo{font-size:11.5px;color:var(--text2);margin:0 0 10px;font-variant-numeric:tabular-nums;}
  .rangeinfo b{color:var(--text);}
  /* curve */
  svg{width:100%;height:auto;display:block;overflow:visible;}
  .axis{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums;}
  .lastlabel{fill:var(--text);font-size:12px;font-weight:640;}
  .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:4px 0 6px;}
  .tile{background:var(--page);border:1px solid var(--border);border-radius:10px;padding:12px 14px;}
  .tile .k{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;}
  .tile .v{font-size:22px;font-weight:640;margin-top:4px;font-variant-numeric:tabular-nums;}
  .reset{font-size:12.5px;color:var(--text2);margin:0 0 12px;}
  .reset b{color:var(--text);} .reset .muted{color:var(--muted);}
  .fetched{font-size:11.5px;color:var(--text2);margin-top:8px;font-variant-numeric:tabular-nums;}
  .fetched b{color:var(--text);} .fetched .muted{color:var(--muted);}
  .readout{margin-top:10px;font-size:13px;color:var(--text2);font-variant-numeric:tabular-nums;
    background:var(--page);border:1px solid var(--border);border-radius:8px;padding:8px 12px;}
  .readout b{color:var(--text);}
  .recent-row{display:grid;grid-template-columns:128px 1fr auto;gap:12px;align-items:center;
    padding:6px 0;border-bottom:1px solid var(--grid);}
  .recent-row:last-child{border-bottom:none;}
  .recent-when{color:var(--text2);font-size:12px;font-variant-numeric:tabular-nums;}
  .recent-name{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .recent-val{font-size:12px;color:var(--text2);font-variant-numeric:tabular-nums;white-space:nowrap;}
  .recent-val b{color:var(--text);}
  .legend{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:9px 22px;}
  .legend div{font-size:12.5px;color:var(--text2);}
  .legend b{color:var(--text);font-weight:620;}
  .swatch{display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:middle;margin-right:4px;}
  table{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:12px;}
  th,td{text-align:right;padding:6px 8px;border-bottom:1px solid var(--grid);
    font-variant-numeric:tabular-nums;white-space:nowrap;}
  th:first-child,td:first-child{text-align:left;}
  th{color:var(--muted);font-weight:560;font-size:11px;text-transform:uppercase;letter-spacing:.03em;}
  td b{color:var(--text);} td.mono{font-family:ui-monospace,"Cascadia Code",Consolas,monospace;color:var(--text2);}
  .empty{color:var(--text2);font-size:14px;padding:26px 4px;}
  .tip{position:fixed;pointer-events:none;background:var(--surface);border:1px solid var(--border);
    border-radius:8px;padding:6px 10px;font-size:12px;color:var(--text);opacity:0;transition:opacity .08s;
    box-shadow:0 4px 14px rgba(0,0,0,.14);white-space:nowrap;z-index:9;}
  .foot{color:var(--muted);font-size:11px;margin-top:26px;text-align:center;}
  @media (max-width:640px){
    .wrap{padding:16px 12px 48px;}
    .card{padding:14px 14px;}
    h1{font-size:18px;}
    .bar-row{grid-template-columns:96px 1fr auto;gap:8px;}
    .bar-val{font-size:11px;}
    .recent-row{grid-template-columns:1fr auto;}
    .recent-when{grid-column:1 / -1;order:-1;}
    .tiles{grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;}
    .tile .v{font-size:20px;}
    .gauge-pct{font-size:20px;}
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>Token Monitor &middot; aocc-personal-ai-coach</h1>
      <div class="sub" id="subline">local &amp; air-gapped &mdash; generated __GENERATED__</div>
    </div>
    <button class="toggle" id="themeBtn" type="button">◐ theme</button>
  </header>

  <div id="app"></div>

  <div class="foot">self-contained &middot; no network &middot; data stays on this machine (RL1 / RL4)__REFRESH_NOTE__</div>
</div>

<div class="tip" id="tip"></div>
<script id="mon-data" type="application/json">__DATA__</script>
<script>
(function(){
  "use strict";
  var M = JSON.parse(document.getElementById("mon-data").textContent);
  var T = M.tokens, L = M.limits || {}, CW = M.cowork || null;
  var app = document.getElementById("app");
  var tip = document.getElementById("tip");
  var SVGNS = "http://www.w3.org/2000/svg";

  function svg(t,a){ var e=document.createElementNS(SVGNS,t); for(var k in a) e.setAttribute(k,a[k]); return e; }
  function h(t,c,html){ var e=document.createElement(t); if(c)e.className=c; if(html!=null)e.innerHTML=html; return e; }
  function n(v){ return (v==null)?"&mdash;":Number(v).toLocaleString(); }
  function shortDate(s){ return (s||"").slice(5); }
  function showTip(e,html){ tip.innerHTML=html; tip.style.opacity="1"; tip.style.left=(e.clientX+12)+"px"; tip.style.top=(e.clientY+12)+"px"; }
  function hideTip(){ tip.style.opacity="0"; }

  function statusColor(pct){ if(pct>=90) return "var(--critical)"; if(pct>=75) return "var(--high)"; if(pct>=50) return "var(--warn)"; return "var(--good)"; }

  function pctOf(a,b){ return (a!=null && b>0)? Math.min(100,(a/b)*100) : null; }
  function pctText(p){ return (p>=100)?"100":(Number.isInteger(p)?String(p):p.toFixed(1)); }

  function whenInfo(dateStr, verb){
    if(!dateStr) return verb+" not set";
    var d=new Date(String(dateStr).replace(" ","T"));
    if(isNaN(d)) return verb+" <b>"+dateStr+"</b>";
    var diff=d.getTime()-Date.now();
    var cd = diff>0 ? (Math.floor(diff/86400000)+"d "+Math.floor((diff%86400000)/3600000)+"h") : null;
    return verb+" <b>"+dateStr+"</b>"+(cd? (" &middot; 剩 "+cd) : " &middot; 已過");
  }

  var GAUGED=false;                  // set when a gauge actually renders, so the legend can skip its key
  function gaugeRow(label, pct, subHtml, color){
    GAUGED=true;
    var g=h("div","gauge");
    var head=h("div","gauge-head");
    head.appendChild(h("div","gauge-name", label));
    var pctEl=h("div","gauge-pct");
    if(pct!=null){ pctEl.style.color=color;
      pctEl.innerHTML=pctText(pct)+"<span style='font-size:13px;color:var(--text2)'>% used</span>"; }
    else { pctEl.innerHTML="&mdash;"; }
    head.appendChild(pctEl); g.appendChild(head);
    var track=h("div","gauge-track");
    var fill=h("div","gauge-fill"); fill.style.width=(pct!=null?Math.max(1,pct):0).toFixed(1)+"%";
    fill.style.background=color; track.appendChild(fill); g.appendChild(track);
    if(subHtml){ var s=h("div","gauge-sub"); s.innerHTML=subHtml; g.appendChild(s); }
    return g;
  }

  function usd(v){ return "$"+Number(v||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}); }

  function fetchedLine(){
    var e=h("div","fetched");
    if(M.cloud && M.cloud.generated_at){
      var api = M.cloud.data_refreshed_at ? (" · API 資料更新 "+String(M.cloud.data_refreshed_at).slice(0,16).replace("T"," ")) : "";
      e.innerHTML="最後抓取 (last fetched): <b>"+M.cloud.generated_at+"</b>"+api;
    } else {
      e.innerHTML="<span class='muted'>此區 $ 為<b>手動填入</b> — 要更新請改 "+
        "<code>config/usage-limits.json</code>（或設 ANALYTICS_API_KEY 後用 <code>-Cloud</code> 自動連外抓）。</span>";
    }
    return e;
  }

  function renderCloud(){
    var C = M.cloud;
    if(!C || !((C.by_product||[]).length)) return;
    var card=h("div","card");
    card.appendChild(h("h2","","Cloud spend &middot; by product"));
    var w=C.window||{};
    card.appendChild(h("p","cap",
      "來自 Claude Enterprise Analytics API (cost_report) — <b>連外抓取的實際 $ 花費</b>. window "+
      ((w.since||"?").slice(0,10))+" → "+(w.until? w.until.slice(0,10):"now")+
      " &middot; 資料更新 "+(C.data_refreshed_at? String(C.data_refreshed_at).slice(0,16).replace("T"," "):"?")));
    var tiles=h("div","tiles");
    tiles.appendChild(tileEl("total spend", usd(C.total_spent_usd)));
    (C.by_product||[]).slice(0,3).forEach(function(r){ tiles.appendChild(tileEl(r.product, usd(r.spent_usd))); });
    card.appendChild(tiles);
    var rows=C.by_product||[], max=Math.max.apply(null, rows.map(function(r){return r.spent_usd||0;}))||1;
    var bars=h("div","bars");
    rows.forEach(function(r){
      var row=h("div","bar-row");
      row.appendChild(h("div","bar-name", r.product));
      var track=h("div","bar-track"); var fill=h("div","bar-fill");
      fill.style.width=Math.max(1,(r.spent_usd/max)*100).toFixed(1)+"%"; track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(h("div","bar-val","<b>"+usd(r.spent_usd)+"</b>"));
      bars.appendChild(row);
    });
    card.appendChild(bars);
    app.appendChild(card);
  }

  function renderLimits(){
    // POLICY (operator ruling): only render a $ block that can actually be REFRESHED.
    //   - "Your usage limits" (account spend): local-unmeasurable -> rendered ONLY when a real
    //     spent was fetched via the Analytics API (-Cloud). Manual/stale values are NOT shown.
    //   - "Claude Code and Cowork credit": rendered ONLY when it can be auto-computed from
    //     measured local data (Cowork real $ + Code estimated $). The manual used_pct path is gone.
    var u=L.usage_limit||{}, cur=u.currency||"$";
    var fromCloud=(M.cloud && M.cloud.total_spent_usd!=null);
    if(fromCloud){
      var c1=h("div","card");
      c1.appendChild(h("h2","","Your usage limits" + (L.plan? "  <span class='chip'>"+L.plan+"</span>":"")));
      var spent=M.cloud.total_spent_usd;
      var pct=pctOf(spent,u.limit);
      var sub=cur+Number(spent).toLocaleString(undefined,{maximumFractionDigits:2})+
        (u.limit!=null? (" of "+cur+Number(u.limit).toLocaleString(undefined,{maximumFractionDigits:2})) : "")+
        " spent <span style='color:var(--series)'>(fetched)</span>"+
        (u.resets? (" &middot; "+whenInfo(u.resets,"resets")) : "");
      c1.appendChild(gaugeRow(u.label||"Spend limit", pct, sub, statusColor(pct==null?0:pct)));
      c1.appendChild(h("p","cap","spent 由 Enterprise Analytics API <b>連外抓取</b>（真實、全產品：Chat + Cowork + Code）；"+
        "limit / resets 由 <code>config/usage-limits.json</code> 提供。下方 token 分析只含 Claude Code CLI，範圍不同。"));
      c1.appendChild(fetchedLine());
      app.appendChild(c1);
    }

    // The "Claude Code and Cowork credit" block was REMOVED (operator ruling): it required a
    // per-token $ rate for the Code half, and that rate (usage_limit.limit / token_limit) was a
    // circular, never-validated assumption — the one measured rate (Cowork real $/token) differs
    // from it by ~21x. An inaccurate number is worse than no number, so it is not rendered.
    // Cowork's own block still shows REAL $ (from audit total_cost_usd), which is measured.
  }

  function barBlock(rows, nameFn, tipFn, grand, rate, detailFn){
    var wrap=h("div");
    var max=Math.max.apply(null, rows.map(function(r){return r.total||0;}))||1;
    rows.forEach(function(r){
      var row=h("div","bar-row");
      var nm=h("div","bar-name"); nm.textContent=nameFn(r); nm.title=nameFn(r);
      var track=h("div","bar-track");
      var fill=h("div","bar-fill"); fill.style.width=Math.max(1,(r.total/max)*100).toFixed(1)+"%"; fill.title=tipFn(r);
      track.appendChild(fill);
      var share=grand>0? (r.total/grand*100):0;
      var valHtml = (rate>0)
        ? ("<b>&asymp;"+usd(r.total*rate)+"</b> <span class='pct'>"+share.toFixed(1)+"%</span> &middot; "+n(r.total)+" tok &middot; out "+n(r.output_tokens))
        : ("<b>"+n(r.total)+"</b> <span class='pct'>"+share.toFixed(1)+"%</span> &middot; out "+n(r.output_tokens));
      var val=h("div","bar-val", valHtml);
      row.appendChild(nm); row.appendChild(track); row.appendChild(val);
      var det = detailFn ? detailFn(r) : null;
      if(det){
        var dd=h("details","bar-details");
        var sm=document.createElement("summary");
        sm.appendChild(row);
        dd.appendChild(sm); dd.appendChild(det);
        wrap.appendChild(dd);
      } else {
        wrap.appendChild(row);
      }
    });
    return wrap;
  }

  function renderTokenBars(){
    var card=h("div","card");
    card.appendChild(h("h2","","Token usage &middot; who spent what"));
    card.appendChild(h("div","scopenote",
      "⚠️ <b>涵蓋範圍：僅本機 Claude Code CLI 對話記錄</b>（<code>~/.claude/projects</code>）。"+
      "Chat／Cowork／其他產品的用量<b>不在內</b> —— 那些只出現在 claude.ai 的 Usage 頁，"+
      "或需 <code>-Cloud</code> 連外抓。因此本區的每日與總額和 Usage 頁的「Daily spend by product」"+
      "<b>本來就不會一致</b>（那是全部產品的 $）。沒掃到不代表沒用。"));
    var sc=T.scope||{}, tot=T.totals||{};
    // NOTE: all estimated-$ output was REMOVED here (operator ruling). Claude Code CLI transcripts
    // carry NO $ field, and the former per-token rate (usage_limit.limit / token_limit) was a
    // circular assumption that measured data contradicts by ~21x. This section now shows only
    // MEASURED tokens; % is a share of the window total (a fact, not an assumption).
    var rate = 0;   // keep the barBlock signature; 0 => token display only, never a fake $
    card.appendChild(h("p","cap",
      "counted "+(sc.files_counted||0)+" transcript file(s); nested sub-agent/workflow "+
      (sc.include_nested?"included":"excluded")+". % = 佔本視窗總量的比例。"+
      "<b>此區不顯示 $</b> —— CLI 記錄沒有金額欄位，任何換算都只是假設（真實 $ 只在 claude.ai Usage 頁；"+
      "Cowork 區塊的 $ 才是實測）。'total' is mostly cache_read (cheap re-reads); 'out' = generated tokens."));
    var tiles=h("div","tiles");
    tiles.appendChild(tileEl("total tokens", n(tot.total)));
    tiles.appendChild(tileEl("generated (output)", n(tot.output_tokens)));
    tiles.appendChild(tileEl("cache read", n(tot.cache_read_input_tokens)));
    tiles.appendChild(tileEl("assistant turns", n(tot.msgs)));
    card.appendChild(tiles);
    // (A "總佔比 vs the credit pool" row was tried and REMOVED at operator request: converting
    //  tokens to $ at list price implied a credit consumption that the Usage page contradicts —
    //  enterprise billing evidently does not charge Code at full list price. Misleading > useful.)
    var grand=tot.total||0, top=8;
    var denom = grand;
    // per-conversation daily breakdown (click a chat to expand its day-by-day usage)
    function convDaily(r){
      var days=(r.by_day||[]);
      if(!days.length) return null;
      var box=h("div","subdays");
      // which chat this row is + a link to its local transcript file
      var sid=(r.session||"").slice(0,8);
      var fileHtml = r.file
        ? "<a href='file:///"+String(r.file).replace(/\\/g,"/").replace(/ /g,"%20")+"' target='_blank'>開啟本機紀錄檔</a>"
        : "（無檔案路徑）";
      box.appendChild(h("div","subday","<span class='sd-date'>對話 "+sid+
        "</span><span class='sd-val'>"+fileHtml+"</span>"));
      days.slice().reverse().forEach(function(dd){
        var sh = r.total>0 ? (dd.total/r.total*100) : 0;
        box.appendChild(h("div","subday",
          "<span class='sd-date'>"+dd.date+"</span><span class='sd-val'>"+
          n(dd.total)+" tok &middot; "+sh.toFixed(1)+"% of this chat &middot; "+dd.msgs+" turns</span>"));
      });
      // which skills this chat used (names, not ids)
      var sks=(r.skills||[]);
      if(sks.length){
        box.appendChild(h("div","subday","<span class='sd-date'><b>用到的 skill</b></span><span class='sd-val'></span>"));
        sks.slice(0,6).forEach(function(s){
          var sh2 = r.total>0 ? (s.total/r.total*100) : 0;
          box.appendChild(h("div","subday","<span class='sd-date'>&nbsp;&nbsp;"+s.skill+
            "</span><span class='sd-val'>"+n(s.total)+" tok &middot; "+sh2.toFixed(1)+"%</span>"));
        });
      }
      return box;
    }
    // generic drilldown: name the conversations that make up a project / skill / agent row
    function memberList(r, whatLabel){
      var ms=(r.members||[]);
      if(!ms.length) return null;
      var box=h("div","subdays");
      box.appendChild(h("div","subday","<span class='sd-date'><b>"+whatLabel+"</b></span>"+
        "<span class='sd-val'>共 "+ms.length+" 個對話</span>"));
      ms.slice(0,8).forEach(function(m){
        var sh = r.total>0 ? (m.total/r.total*100) : 0;
        box.appendChild(h("div","subday","<span class='sd-date'>"+m.name+
          " <span class='muted'>("+(m.session||"").slice(0,8)+")</span></span><span class='sd-val'>"+
          n(m.total)+" tok &middot; "+sh.toFixed(1)+"%</span>"));
      });
      return box;
    }
    if((T.by_conversation||[]).length){
      card.appendChild(h("div","sectlead","<b>By conversation</b> &mdash; 依<b>對話 (sessionId)</b> 分組；"+
        "名稱來自 <code>customTitle</code>／<code>aiTitle</code>（top "+top+"）。點 &#9656; 看每日明細、用到的 skill、紀錄檔"));
      card.appendChild(barBlock(T.by_conversation.slice(0,top),
        function(r){return r.title||(r.session||"").slice(0,12);},
        function(r){return (r.title||r.session)+" — "+n(r.total)+" total, "+r.msgs+" turns";}, denom, rate, convDaily));
    }
    if((T.by_project||[]).length){
      card.appendChild(h("div","sectlead","<b>By project</b> &mdash; 依<b>工作目錄 <code>cwd</code></b> 分組"+
        "（每個 turn 當下所在的資料夾，top "+top+"）。點 &#9656; 看是哪些對話貢獻的"));
      card.appendChild(barBlock(T.by_project.slice(0,top),
        function(r){var p=String(r.project||"");return p.replace(/[\\/]+$/,"").split(/[\\/]/).pop()||p;},
        function(r){return r.project+" — "+n(r.total)+" total";}, denom, rate,
        function(r){return memberList(r,"這個專案底下的對話");}));
    }
    if((T.by_skill||[]).length){
      card.appendChild(h("div","sectlead","<b>By skill</b> &mdash; 依每個 turn 的 <code>attributionSkill</code> 分組"+
        "（該 skill <b>作用期間</b>產生的 token；沒掛 skill 的歸 <code>(no skill)</code>，top "+top+"）。點 &#9656; 看是哪些對話用到"));
      card.appendChild(barBlock(T.by_skill.slice(0,top),
        function(r){return r.skill;},
        function(r){return r.skill+" — "+n(r.total)+" total, "+r.msgs+" turns";}, denom, rate,
        function(r){return memberList(r,"用到這個 skill 的對話");}));
    }
    if((T.by_agent||[]).length){
      var agTot = T.by_agent_total || T.by_agent.reduce(function(a,r){return a+(r.total||0);},0);
      var nestedDelta = agTot - grand;
      card.appendChild(h("div","sectlead","<b>By agent</b> &mdash; 依每個 turn 的 <code>attributionAgent</code> 分組："+
        "主線 = <code>(main thread)</code>、子代理 = 其類型（如 <code>general-purpose</code>）。"+
        "<b>唯一含 nested</b>（子代理/workflow 的 transcript），故總量 "+n(agTot)+" 比上方多 "+
        n(nestedDelta>0?nestedDelta:0)+"；% 為佔 agent 總量。點 &#9656; 看是哪些對話"));
      card.appendChild(barBlock(T.by_agent.slice(0,top),
        function(r){return r.agent;},
        function(r){return r.agent+" — "+n(r.total)+" total, "+r.msgs+" turns";}, agTot, rate,
        function(r){return memberList(r,"這個 agent 出現的對話");}));
    }
    app.appendChild(card);
  }
  function tileEl(k,v){ var t=h("div","tile"); t.appendChild(h("div","k",k)); t.appendChild(h("div","v",v)); return t; }

  function curve(pts, onPick, opts){
    opts = opts || {};
    var yfmt = opts.yfmt || function(v){ return Math.round(v).toLocaleString(); };
    var valLabel = opts.valLabel || function(p){ return Number(p.val||0).toLocaleString(); };
    var tipFn = opts.tip || function(p){ return "<b>"+p.label+"</b><br>"+n(p.val)+"<br>out "+n(p.out)+" · "+p.msgs+" turns"; };
    var W=920,H=240,padL=52,padR=54,padT=16,padB=32, iw=W-padL-padR, ih=H-padT-padB;
    var m=pts.length;
    var maxVal=Math.max.apply(null, pts.map(function(p){return p.val||0;}));
    if(opts.refLine && opts.refLine.val>maxVal) maxVal=opts.refLine.val;
    var yMax=Math.max(1e-9, (maxVal||0)*1.15);
    function X(i){ return padL+(m<=1? iw/2 : iw*i/(m-1)); }
    function Y(v){ return padT+ih-ih*(v/yMax); }
    var s=svg("svg",{viewBox:"0 0 "+W+" "+H, role:"img"});
    for(var t=0;t<=4;t++){ var v=yMax*t/4, y=Y(v);
      s.appendChild(svg("line",{x1:padL,y1:y,x2:W-padR,y2:y,stroke:"var(--grid)","stroke-width":1}));
      var lab=svg("text",{x:padL-8,y:y+4,"text-anchor":"end","class":"axis"});
      lab.textContent=yfmt(v); s.appendChild(lab); }
    s.appendChild(svg("line",{x1:padL,y1:Y(0),x2:W-padR,y2:Y(0),stroke:"var(--baseline)","stroke-width":1}));
    if(opts.refLine && opts.refLine.val>0){        // e.g. daily-average budget line
      var ry=Y(opts.refLine.val);
      s.appendChild(svg("line",{x1:padL,y1:ry,x2:W-padR,y2:ry,stroke:"var(--critical)","stroke-width":1,"stroke-dasharray":"5 3",opacity:0.75}));
      var rlab=svg("text",{x:W-padR,y:ry-4,"text-anchor":"end","class":"axis",fill:"var(--critical)"});
      rlab.textContent=opts.refLine.label; s.appendChild(rlab);
    }
    var lstep=Math.max(1, Math.ceil(m/12));   // thin x-labels when many days (points stay per-day)
    pts.forEach(function(p,i){ if(i%lstep!==0 && i!==m-1) return;
      var lab=svg("text",{x:X(i),y:H-10,"text-anchor":"middle","class":"axis"});
      lab.textContent=shortDate(p.label); s.appendChild(lab); });
    if(m>1){
      var area="M"+X(0)+" "+Y(0)+" ";
      pts.forEach(function(p,i){ area+="L"+X(i)+" "+Y(p.val||0)+" "; });
      area+="L"+X(m-1)+" "+Y(0)+" Z";
      s.appendChild(svg("path",{d:area,fill:"var(--series-soft)",stroke:"none"}));
      var d=""; pts.forEach(function(p,i){ d+=(i?"L":"M")+X(i)+" "+Y(p.val||0)+" "; });
      s.appendChild(svg("path",{d:d,fill:"none",stroke:"var(--series)","stroke-width":2,"stroke-linejoin":"round","stroke-linecap":"round"}));
    }
    var markers=[];
    pts.forEach(function(p,i){
      var c=svg("circle",{cx:X(i),cy:Y(p.val||0),r:4,fill:"var(--series)",stroke:"var(--surface)","stroke-width":2});
      var hit=svg("circle",{cx:X(i),cy:Y(p.val||0),r:15,fill:"transparent"}); hit.style.cursor="pointer";
      function sel(){ markers.forEach(function(mm){mm.setAttribute("r",4);}); c.setAttribute("r",7); if(onPick)onPick(p,i); }
      hit.addEventListener("mousemove",function(e){ showTip(e, tipFn(p,i)); });
      hit.addEventListener("mouseleave",hideTip);
      hit.addEventListener("click",sel);
      markers.push(c); s.appendChild(c); s.appendChild(hit);
    });
    if(m){ markers[m-1].setAttribute("r",7);
      var lp=pts[m-1]; var tl=svg("text",{x:X(m-1)-4,y:Y(lp.val||0)-12,"text-anchor":"end","class":"lastlabel"});
      tl.textContent=valLabel(lp); s.appendChild(tl); }
    return s;
  }

  function renderDailySpend(){
    var days=(M.cloud.daily||[]);
    var card=h("div","card");
    card.appendChild(h("h2","","Usage over time &middot; daily spend ($)"));
    card.appendChild(h("p","cap","每日 $ 花費，以天為單位（來自 Enterprise Analytics API）。"+
      "<b>Spend limit</b> = 全部產品當日合計；<b>credit</b> 相關 = claude_code + cowork。"));
    // vertical bar chart of daily total $
    var W=920,H=240,padL=54,padR=16,padT=16,padB=34, iw=W-padL-padR, ih=H-padT-padB;
    var yMax=Math.max(1, Math.max.apply(null, days.map(function(d){return d.total_usd||0;}))*1.15);
    var n=days.length||1;
    function Y(v){ return padT+ih-ih*(v/yMax); }
    var s=svg("svg",{viewBox:"0 0 "+W+" "+H, role:"img"});
    for(var t=0;t<=4;t++){ var v=yMax*t/4, y=Y(v);
      s.appendChild(svg("line",{x1:padL,y1:y,x2:W-padR,y2:y,stroke:"var(--grid)","stroke-width":1}));
      var lab=svg("text",{x:padL-8,y:y+4,"text-anchor":"end","class":"axis"}); lab.textContent="$"+Math.round(v); s.appendChild(lab); }
    s.appendChild(svg("line",{x1:padL,y1:Y(0),x2:W-padR,y2:Y(0),stroke:"var(--baseline)","stroke-width":1}));
    var bw=Math.min(46,(iw/n)*0.62);
    days.forEach(function(d,i){
      var cx=padL+iw*(i+0.5)/n, val=d.total_usd||0;
      var rect=svg("rect",{x:(cx-bw/2).toFixed(1),y:Y(val).toFixed(1),width:bw.toFixed(1),
        height:Math.max(0,(ih*(val/yMax))).toFixed(1),fill:"var(--series)",rx:3});
      rect.style.cursor="pointer";
      var bp=d.by_product||{}; var tip="<b>"+d.date+"</b><br>total "+usd(val);
      Object.keys(bp).forEach(function(p){ tip+="<br>"+p+": "+usd(bp[p]); });
      rect.addEventListener("mousemove",function(e){ showTip(e,tip); });
      rect.addEventListener("mouseleave",hideTip);
      s.appendChild(rect);
      var xl=svg("text",{x:cx,y:H-12,"text-anchor":"middle","class":"axis"}); xl.textContent=d.date.slice(5); s.appendChild(xl);
    });
    card.appendChild(s);
    // per-day table
    var prods=[]; days.forEach(function(d){ Object.keys(d.by_product||{}).forEach(function(p){ if(prods.indexOf(p)<0) prods.push(p); }); });
    var tbl=h("table"); var thead="<thead><tr><th>date</th><th>spend (total)</th>";
    prods.forEach(function(p){ thead+="<th>"+p+"</th>"; }); thead+="</tr></thead>";
    tbl.innerHTML=thead;
    var tb=h("tbody");
    days.forEach(function(d){ var tr=h("tr"); var row="<td class='mono'>"+d.date+"</td><td><b>"+usd(d.total_usd)+"</b></td>";
      prods.forEach(function(p){ var v=(d.by_product||{})[p]; row+="<td>"+(v!=null?usd(v):"&mdash;")+"</td>"; });
      tr.innerHTML=row; tb.appendChild(tr); });
    tbl.appendChild(tb); card.appendChild(tbl);
    app.appendChild(card);
  }

  function renderCurve(){
    if(M.cloud && (M.cloud.daily||[]).length){ renderDailySpend(); return; }
    var days=(T.by_day||[]);
    if(!days.length) return;
    var card=h("div","card");
    card.appendChild(h("h2","","Usage over time"));
    // y-axis is MEASURED tokens. The former "$ per day vs monthly budget line" was removed with
    // the rest of the estimated-$ output (its rate was an unvalidated assumption).
    card.appendChild(h("p","cap",
      "每日 <b>token</b> 用量（台灣時間，以天為單位，無活動日補 0）。用按鈕切換範圍；點一天看<b>與前一日的增減</b>。"+
      "（不換算 $ —— CLI 記錄無金額欄位。）"));
    // build the FULL daily series (window_since .. today), zero-filled; buttons re-slice it client-side
    var byDate={}; days.forEach(function(d){ byDate[d.date]=d; });
    function iso(dt){ return dt.getFullYear()+"-"+String(dt.getMonth()+1).padStart(2,"0")+"-"+String(dt.getDate()).padStart(2,"0"); }
    var scc=T.scope||{};
    var startStr = scc.window_since ? String(scc.window_since).slice(0,10) : days[0].date;
    var endStr;
    if(scc.window_until){ endStr = String(scc.window_until).slice(0,10); }
    else { var td=iso(new Date()); endStr = (td>days[days.length-1].date)? td : days[days.length-1].date; }
    if(startStr > days[0].date) startStr = days[0].date;                 // never hide an active day
    if(endStr < days[days.length-1].date) endStr = days[days.length-1].date;
    var allPts=[];
    var cur=new Date(startStr+"T00:00:00"), end=new Date(endStr+"T00:00:00"), guard=0;
    while(cur<=end && guard++<800){
      var key=iso(cur), d=byDate[key];
      allPts.push(d ? {label:d.date,tok:d.total,out:d.output_tokens,msgs:d.msgs}
                    : {label:key,tok:0,out:0,msgs:0});
      cur.setDate(cur.getDate()+1);
    }
    var tzLabel=(scc.timezone)||"UTC+8";
    var winPulled=(scc.window_since? scc.window_since : (days[0]&&days[0].date)||"?")+" → "+(scc.window_until? scc.window_until : "now");
    var bar=h("div","rangebar");
    var rangeInfo=h("div","rangeinfo");
    var chart=h("div");                 // curve container, re-rendered on range change
    var readout=h("div","readout");
    function valOf(p){ return p.tok; }          // tokens only (no $ conversion — see note above)
    function fmtVal(p){ return n(p.tok); }
    function deltaHtml(p){
      if(p.delta==null) return "（範圍首日，無前一日可比）";
      if(!isFinite(p.delta)) return "前一日為 0 &rarr; <b>新增</b>";
      var up=p.delta>=0; return "較前一日 <b style='color:"+(up?"var(--critical)":"var(--good)")+"'>"+
        (up?"+":"−")+Math.abs(p.delta).toFixed(1)+"%</b>";
    }
    function pick(p){ readout.innerHTML="選取 <b>"+p.label+"</b> &mdash; "+fmtVal(p)+" tokens"+
      " &middot; out "+n(p.out)+" &middot; "+p.msgs+" turns &middot; "+deltaHtml(p); }
    function draw(nDays){
      var pts = (nDays>0 && allPts.length>nDays) ? allPts.slice(allPts.length-nDays) : allPts.slice();
      pts = pts.map(function(p){ return {label:p.label, tok:p.tok, out:p.out, msgs:p.msgs, val:valOf(p)}; });
      pts.forEach(function(p,i){        // day-over-day change vs the previous day in this range
        if(i===0){ p.delta=null; }
        else { var prev=pts[i-1].val; p.delta = prev>0 ? ((p.val-prev)/prev*100) : (p.val>0? Infinity : 0); }
      });
      var opts={
        yfmt: function(v){ return Math.round(v).toLocaleString(); },
        valLabel: function(pp){ return Number(pp.val||0).toLocaleString(); },
        tip: function(pp){ return "<b>"+pp.label+"</b><br><b>"+fmtVal(pp)+"</b> tokens"+
          "<br>"+deltaHtml(pp)+"<br>out "+n(pp.out)+" · "+pp.msgs+" turns"; }
      };
      chart.innerHTML="";
      chart.appendChild(curve(pts, function(p){ pick(p); }, opts));
      if(pts.length){
        pick(pts[pts.length-1]);
        rangeInfo.innerHTML="抓入區間（產生時實際掃到）：<b>"+winPulled+"</b>（"+tzLabel+"）"+
          " &middot; 目前顯示 <b>"+pts[0].label+" → "+pts[pts.length-1].label+"</b>（"+pts.length+" 天）";
      }
    }
    var ranges=[{n:3,label:"近 3 天"},{n:7,label:"近 7 天"},{n:30,label:"近一個月"}];
    var btns=[];
    ranges.forEach(function(rg){
      var b=document.createElement("button"); b.type="button"; b.className="rangebtn"; b.textContent=rg.label;
      b.addEventListener("click",function(){ btns.forEach(function(x){x.classList.remove("active");}); b.classList.add("active"); draw(rg.n); });
      bar.appendChild(b); btns.push(b);
    });
    card.appendChild(bar); card.appendChild(rangeInfo); card.appendChild(chart); card.appendChild(readout);
    var defIdx=1;                        // default: 近 7 天（operator ruling）
    btns[defIdx].classList.add("active"); draw(ranges[defIdx].n);
    app.appendChild(card);
  }

  function renderRecent(){
    var rows=(T.by_conversation||[]).slice();
    rows.sort(function(a,b){ return String(b.last_tw||"").localeCompare(String(a.last_tw||"")); });
    if(!rows.length) return;
    var card=h("div","card");
    card.appendChild(h("h2","","近期使用列表 (recent activity)"));
    card.appendChild(h("p","cap","對話依最後活動時間排序（新到舊，台灣時間）。"));
    rows.slice(0,10).forEach(function(r){
      var row=h("div","recent-row");
      row.appendChild(h("div","recent-when", r.last_tw||"&mdash;"));
      var nm=h("div","recent-name", r.title||(r.session||"").slice(0,12)); nm.title=r.title||r.session||"";
      row.appendChild(nm);
      row.appendChild(h("div","recent-val","<b>"+n(r.total)+"</b> &middot; out "+n(r.output_tokens)));
      card.appendChild(row);
    });
    app.appendChild(card);
  }

  // Official list prices per 1M tokens: [input, output, cache_read, cache_write@1h-TTL].
  // The 1h-TTL cache-write price (2x input) is what reconciles Cowork's audit total_cost_usd with
  // list pricing to ~0.01%, so the same basis is used to COST Claude Code (which records no $).
  var PRICE={
    "claude-opus-4-8":[5,25,0.50,10], "claude-opus-4-7":[5,25,0.50,10], "claude-opus-4-6":[5,25,0.50,10],
    "claude-opus-5":[5,25,0.50,10], "claude-fable-5":[10,50,1.00,20],
    "claude-sonnet-5":[3,15,0.30,6], "claude-sonnet-4-6":[3,15,0.30,6],
    "claude-haiku-4-5":[1,5,0.10,2], "claude-haiku-4-5-20251001":[1,5,0.10,2]
  };
  function priceRow(r){                 // r has the 4 token fields; returns $ or null if model unknown
    var p=PRICE[r.model]; if(!p) return null;
    return ((r.input_tokens||0)*p[0] + (r.output_tokens||0)*p[1] +
            (r.cache_read_input_tokens||0)*p[2] + (r.cache_creation_input_tokens||0)*p[3])/1e6;
  }
  function compTable(cmp){
    var t=h("table");
    var rows=[["cache_read（重讀上下文，最便宜）","cache_read_input_tokens"],
              ["cache_creation（寫入快取，較貴）","cache_creation_input_tokens"],
              ["output（模型生成，最貴）","output_tokens"],
              ["input（新輸入）","input_tokens"]];
    var html="<thead><tr><th>類型</th><th>tokens</th><th>佔比</th></tr></thead><tbody>";
    rows.forEach(function(r){ var v=cmp[r[1]]||0;
      html+="<tr><td>"+r[0]+"</td><td class='mono'>"+n(v)+"</td><td class='mono'>"+
        (cmp.total>0?(v/cmp.total*100).toFixed(2):"0")+"%</td></tr>"; });
    html+="<tr><td><b>total</b></td><td class='mono'><b>"+n(cmp.total)+"</b></td><td class='mono'>100%</td></tr></tbody>";
    t.innerHTML=html; return t;
  }

  function renderCodeLocal(){
    var cmp=T.composition, models=(T.by_model||[]);
    if(!cmp || !(cmp.total>0)) return;
    var card=h("div","card");
    card.appendChild(h("h2","","Code &middot; 本機用量（token 實測；$ 依官方牌價計算）"));
    // cost each model row with its own price, from its own measured composition
    var costed=0, unknown=0, anyCost=false;
    models.forEach(function(m){ var c=priceRow(m); if(c==null){ unknown+=(m.total||0); } else { costed+=c; anyCost=true; } });
    card.appendChild(h("div","scopenote",
      "來源：本機 Claude Code CLI 記錄（<code>~/.claude/projects</code>）的每個 turn <code>message.usage</code>。"+
      "CLI <b>沒有金額欄位</b>，所以這裡的 $ 是<b>用官方牌價 × 實測 token 組成算出來的</b>（非帳單）。"+
      "此算法已用 Cowork 的實際帳單驗證：官方價算 $238.41 vs 實帳 $236.83，<b>誤差 0.7%</b>。"+
      (unknown>0? " 有 "+n(unknown)+" tokens 的 model 未知、未計價。" : "")));
    var tiles=h("div","tiles");
    tiles.appendChild(tileEl("total tokens", n(cmp.total)));
    if(anyCost){
      tiles.appendChild(tileEl("$ at list price (calc)", usd(costed)));
      tiles.appendChild(tileEl("$ per 1M tok", "$"+(costed/cmp.total*1e6).toFixed(4)));
    }
    tiles.appendChild(tileEl("assistant turns", n((T.totals||{}).msgs)));
    card.appendChild(tiles);
    card.appendChild(h("div","sectlead","<b>Token 組成</b>（本視窗，來自 <code>message.usage</code>）"));
    card.appendChild(compTable(cmp));
    card.appendChild(h("p","cap","cache_read 佔比高屬正常：每回合重讀上下文，計價僅約新輸入的 1/10 —— 這也是本區單價"+
      "比 Cowork 低的原因（Cowork 的 cache_creation 佔比較高，而寫入快取較貴）。"));
    if(models.length){
      card.appendChild(h("div","sectlead","<b>各 model</b>（依 <code>message.model</code>；$ 為官方牌價計算）"));
      var mt=h("table");
      var html="<thead><tr><th>model</th><th>$ (calc)</th><th>tokens</th><th>佔比</th><th>turns</th></tr></thead><tbody>";
      models.slice(0,8).forEach(function(m){
        var c=priceRow(m);
        html+="<tr><td class='mono'>"+m.model+"</td><td class='mono'>"+(c!=null? usd(c):"&mdash;")+
          "</td><td class='mono'>"+n(m.total)+"</td><td class='mono'>"+
          (cmp.total>0?(m.total/cmp.total*100).toFixed(2):"0")+"%</td><td class='mono'>"+n(m.msgs)+"</td></tr>";
      });
      html+="</tbody>"; mt.innerHTML=html; card.appendChild(mt);
    }
    app.appendChild(card);
  }

  function renderCoworkLocal(){
    if(!CW || !CW.available || !(CW.by_room||[]).length) return;
    var tot=CW.totals||{}, sc=CW.scope||{};
    var card=h("div","card");
    card.appendChild(h("h2","","Cowork &middot; 本機用量（真實 $）"));
    card.appendChild(h("div","scopenote",
      "來源：Cowork 桌面 App 的本機 <code>audit.jsonl</code>（"+(sc.audit_files||0)+" 個 session）。"+
      "$ 是 <b>audit 的 total_cost_usd（真實花費，非估算）</b>；與上方 Claude Code 的 token 分析<b>是不同產品、分開算</b>。"));
    var tiles=h("div","tiles");
    tiles.appendChild(tileEl("real $ (this window)", usd(tot.cost_usd)));
    tiles.appendChild(tileEl("total tokens", n(tot.total)));
    tiles.appendChild(tileEl("chat rooms", n(tot.rooms)));
    tiles.appendChild(tileEl("runs", n(tot.results)));
    card.appendChild(tiles);
    // token composition (why $/token looks low: almost everything is cheap cache_read)
    var comp=CW.composition;
    if(comp && comp.total>0){
      card.appendChild(h("div","sectlead","<b>Token 組成</b>（全時間，basis: <code>modelUsage</code>，與 $ 同一來源）"));
      card.appendChild(compTable(comp));
      var lifeC=(CW.lifetime&&CW.lifetime.cost_usd)||0;
      if(lifeC>0){
        card.appendChild(h("p","cap","全時間 "+usd(lifeC)+" ÷ "+n(comp.total)+" tokens = <b>$"+
          (lifeC/comp.total*1e6).toFixed(4)+" / 百萬 token</b>（混合單價）。單價看起來低是因為 <b>"+
          (comp.cache_read_input_tokens/comp.total*100).toFixed(1)+
          "% 是 cache_read</b>（每回合重讀上下文，計價僅約新輸入的 1/10）。"));
      }
      var bm=CW.by_model||[];
      if(bm.length){
        card.appendChild(h("div","sectlead","<b>各 model</b>（實測 $ 與單價）"));
        var mt=h("table");
        var htmlM="<thead><tr><th>model</th><th>real $</th><th>tokens</th><th>$/1M tok</th></tr></thead><tbody>";
        bm.forEach(function(m){
          htmlM+="<tr><td class='mono'>"+m.model+"</td><td class='mono'>"+usd(m.cost_usd)+"</td><td class='mono'>"+
            n(m.total)+"</td><td class='mono'>"+(m.usd_per_mtok!=null? ("$"+m.usd_per_mtok) : "&mdash;")+"</td></tr>";
        });
        htmlM+="</tbody>"; mt.innerHTML=htmlM; card.appendChild(mt);
      }
    }
    // by chat room (real $), share of Cowork total
    var gtot=tot.cost_usd||0, top=8;
    card.appendChild(h("div","sectlead","<b>By chat room</b> &mdash; per Cowork session (top "+top+")；點 &#9656; 看每日"));
    var rooms=(CW.by_room||[]).slice(0,top);
    var max=Math.max.apply(null, rooms.map(function(r){return r.cost_usd||0;}))||1;
    var wrap=h("div");
    rooms.forEach(function(r){
      var row=h("div","bar-row");
      var nm=h("div","bar-name"); var label=r.label||(r.session||"").slice(0,10);
      nm.textContent=label; nm.title=(r.label? r.label+"  ":"")+"session "+(r.session||"");
      var track=h("div","bar-track");
      var fill=h("div","bar-fill"); fill.style.width=Math.max(1,(r.cost_usd/max)*100).toFixed(1)+"%";
      track.appendChild(fill);
      var share=gtot>0?(r.cost_usd/gtot*100):0;
      var val=h("div","bar-val","<b>"+usd(r.cost_usd)+"</b> <span class='pct'>"+share.toFixed(1)+"%</span> &middot; "+
        n(r.total)+" tok &middot; "+r.turns+" turns");
      row.appendChild(nm); row.appendChild(track); row.appendChild(val);
      var days=(r.by_day||[]);
      if(days.length){
        var dd=h("details","bar-details"); var sm=document.createElement("summary"); sm.appendChild(row);
        var box=h("div","subdays");
        box.appendChild(h("div","subday","<span class='sd-date'>session "+(r.session||"").slice(0,8)+
          "</span><span class='sd-val'>"+(r.last_tw||"")+"</span>"));
        days.slice().reverse().forEach(function(x){
          box.appendChild(h("div","subday","<span class='sd-date'>"+x.date+"</span><span class='sd-val'>"+
            usd(x.cost_usd)+" &middot; "+n(x.total)+" tok</span>"));
        });
        dd.appendChild(sm); dd.appendChild(box); wrap.appendChild(dd);
      } else { wrap.appendChild(row); }
    });
    card.appendChild(wrap);
    // by day (real $)
    var byday=(CW.by_day||[]);
    if(byday.length){
      card.appendChild(h("div","sectlead","<b>每日真實花費</b>（Cowork）"));
      var dmax=Math.max.apply(null, byday.map(function(d){return d.cost_usd||0;}))||1;
      var dwrap=h("div");
      byday.slice().reverse().forEach(function(d){
        var row=h("div","bar-row");
        var nm=h("div","bar-name"); nm.textContent=d.date;
        var track=h("div","bar-track");
        var fill=h("div","bar-fill"); fill.style.width=Math.max(1,(d.cost_usd/dmax)*100).toFixed(1)+"%";
        track.appendChild(fill);
        var val=h("div","bar-val","<b>"+usd(d.cost_usd)+"</b> &middot; "+n(d.total)+" tok");
        row.appendChild(nm); row.appendChild(track); row.appendChild(val);
        dwrap.appendChild(row);
      });
      card.appendChild(dwrap);
    }
    app.appendChild(card);
  }

  function renderLegend(){
    var card=h("div","card");
    card.appendChild(h("h2","","欄位說明 (legend)"));
    var g=h("div","legend");
    // Only describe what this page actually shows — entries for absent features are noise.
    var items=[
      "<div><b>total</b> — 該範圍全部 token（含快取，數字大屬正常）</div>",
      "<div><b>output</b>（列上標 <b>out</b>）— 模型實際生成的 token</div>",
      "<div><b>cache read</b> — 每回合重讀的上下文（計價約新輸入的 1/10）</div>",
      "<div><b>turns</b> — assistant 回合數</div>",
      "<div><b>%</b> — 該列佔<b>本視窗總量</b>的比例（實測值的佔比）</div>",
      "<div><b>$</b> — <b>Cowork</b> 的 $ 是 audit <b>實測真實花費</b>；<b>Code</b> 的 $ 是用"+
        "<b>官方牌價 × 實測 token 組成</b>算出的（CLI 無金額欄位，故為計算值、非帳單）</div>",
      "<div><b>By conversation</b> — 依<b>對話 <code>sessionId</code></b> 分組（名稱來自 "+
        "<code>customTitle</code>／<code>aiTitle</code>）</div>",
      "<div><b>By project</b> — 依<b>工作目錄 <code>cwd</code></b> 分組</div>",
      "<div><b>By skill</b> — 依 <code>attributionSkill</code> 分組（該 skill 作用期間；無則 "+
        "<code>(no skill)</code>）。<b>不含</b> nested</div>",
      "<div><b>By agent</b> — 依 <code>attributionAgent</code> 分組（主線 <code>(main thread)</code> / "+
        "子代理類型）。<b>唯一含</b> nested，故總量較大</div>",
      "<div><b>各 model</b> — 依 <code>message.model</code>（Code）／<code>modelUsage</code>（Cowork）</div>"
    ];
    if(GAUGED){
      items.push("<div>gauge 顏色：<span class='swatch' style='background:var(--good)'></span>&lt;50% "+
        "<span class='swatch' style='background:var(--warn)'></span>50–75% "+
        "<span class='swatch' style='background:var(--high)'></span>75–90% "+
        "<span class='swatch' style='background:var(--critical)'></span>&ge;90%</div>");
    }
    g.innerHTML=items.join("");
    card.appendChild(g); app.appendChild(card);
  }

  function renderHelp(){
    var card=h("div","card");
    card.appendChild(h("h2","","使用說明 &amp; 資料來源 (how to use / where the numbers come from)"));
    var g=h("div","legend");
    g.innerHTML=
      "<div><b>要看最新資料</b> — 跑 <code>tokens</code>（或雙擊 <code>scripts\\open-monitor.cmd</code>）重新產生。"+
        "這是靜態快照，<b>在瀏覽器按 F5 不會更新</b>。</div>"+
      "<div><b>時間範圍</b> — Usage over time 上方按鈕切 3 天 / 7 天 / 一個月（前端即時，預設 7 天）。</div>"+
      "<div><b>展開明細</b> — 每列點 <b>▸</b>：對話看每日＋用到的 skill＋<b>開啟本機紀錄檔</b>；"+
        "專案／skill／agent 看是<b>哪些對話</b>貢獻的。</div>"+
      "<div><b>涵蓋範圍</b> — <b>Claude Code</b>（本機 CLI 記錄）＋<b>Cowork</b>（本機 audit，含真實 $）"+
        "兩個獨立區塊；<b>Chat 不在內</b>（本機無紀錄，只有 claude.ai Usage 頁有）。</div>";
    card.appendChild(g);
    card.appendChild(h("div","sectlead","<b>每個數字抓自 transcript 的哪個欄位</b>（<code>~/.claude/projects/**/*.jsonl</code>）"));
    var t=h("table");
    t.innerHTML="<thead><tr><th>畫面上的欄位</th><th>來源（jsonl 欄位）</th></tr></thead><tbody>"+
      "<tr><td>total / tokens</td><td class='mono'>message.usage（input + output + cache_creation + cache_read 相加）</td></tr>"+
      "<tr><td>out（output）</td><td class='mono'>message.usage.output_tokens</td></tr>"+
      "<tr><td>cache read</td><td class='mono'>message.usage.cache_read_input_tokens</td></tr>"+
      "<tr><td>turns</td><td class='mono'>type == \"assistant\" 的訊息數</td></tr>"+
      "<tr><td>By conversation</td><td class='mono'>sessionId（名稱 ← customTitle / aiTitle）</td></tr>"+
      "<tr><td>By project</td><td class='mono'>cwd（工作目錄）</td></tr>"+
      "<tr><td>By skill</td><td class='mono'>attributionSkill（無則 (no skill)）</td></tr>"+
      "<tr><td>By agent</td><td class='mono'>attributionAgent（主線=(main thread)，子代理=其類型；含 nested）</td></tr>"+
      "<tr><td>日期 / 每日</td><td class='mono'>timestamp（UTC → 換算 UTC+8）</td></tr>"+
      "<tr><td>各 model（Code）</td><td class='mono'>message.model</td></tr>"+
      "<tr><td>Code $（計算值）</td><td class='mono'>官方牌價 × 各 model 的實測組成（<b>非帳單</b>；算法已用 Cowork 實帳驗證 0.7%）</td></tr>"+
      "<tr><td>Cowork $（真實）</td><td class='mono'>audit.jsonl 的 total_cost_usd（每個 result 一筆；<b>實測</b>）</td></tr>"+
      "<tr><td>Cowork 聊天室名稱</td><td class='mono'>session sidecar local_&lt;uuid&gt;.json 的 title（cliSessionId 對應 audit session_id）</td></tr>"+
      "<tr><td>紀錄檔連結</td><td class='mono'>該 sessionId 的 .jsonl 檔路徑</td></tr>"+
      "</tbody>";
    card.appendChild(t);
    app.appendChild(card);
  }

  function render(){
    app.innerHTML="";
    var op = (L.operator && String(L.operator).indexOf("<")<0) ? ("operator: <b>"+L.operator+"</b> &middot; ") : "";
    var base = "local &amp; air-gapped";
    if(T && T.scope){
      var sc=T.scope, win=sc.window_since? (sc.window_since+" -> "+(sc.window_until||"now")) : "all time";
      base += " &middot; "+(sc.timezone||"UTC+8")+" &middot; window: "+win;
    }
    document.getElementById("subline").innerHTML = op + base + " &middot; generated __GENERATED__";
    if(!T || !T.totals){
      renderLimits(); renderCloud();
      app.appendChild(h("div","empty",
        "No token data yet. Run <code>token_report.py</code> (or <code>Show-MonitorDashboard</code>) and reload.")); return; }
    // Order (operator ruling): recent activity -> usage over time -> who spent what
    //                          -> Code local -> Cowork local -> legend -> help
    renderRecent();
    renderLimits();
    renderCloud();
    renderCurve();
    renderTokenBars();
    renderCodeLocal();
    renderCoworkLocal();
    renderLegend();
    renderHelp();
  }

  document.getElementById("themeBtn").addEventListener("click",function(){
    var r=document.documentElement, cur=r.getAttribute("data-theme");
    var dark = cur? cur==="dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    r.setAttribute("data-theme", dark? "light":"dark");
  });

  render();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
