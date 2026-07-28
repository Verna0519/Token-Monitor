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
import time

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
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--refresh", type=int, default=0,
                    help="seconds between browser auto-reloads (0=off); pair with a regenerate loop")
    args = ap.parse_args()

    tokens = None if args.token_json == "-" else load_json(args.token_json)
    limits = load_json(args.limits) or load_json(TEMPLATE_LIMITS) or {}
    cloud = None if args.cloud_json == "-" else load_json(args.cloud_json)
    model = {"tokens": tokens, "limits": limits, "cloud": cloud}
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
  var T = M.tokens, L = M.limits || {};
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

  function gaugeRow(label, pct, subHtml, color){
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
    // Section 1 — Your usage limits (a spend limit in currency; mirrors the Claude Usage page)
    var c1=h("div","card");
    c1.appendChild(h("h2","","Your usage limits" + (L.plan? "  <span class='chip'>"+L.plan+"</span>":"")));
    var u=L.usage_limit||{}, cur=u.currency||"$";
    var fromCloud=(M.cloud && M.cloud.total_spent_usd!=null);
    var spent=fromCloud ? M.cloud.total_spent_usd : u.spent;
    var pct=pctOf(spent,u.limit);
    var sub=(spent!=null&&u.limit!=null)
      ? (cur+Number(spent).toLocaleString(undefined,{maximumFractionDigits:2})+" of "+
         cur+Number(u.limit).toLocaleString(undefined,{maximumFractionDigits:2})+" spent"+
         (fromCloud?" <span style='color:var(--series)'>(fetched)</span>":"")+
         " &middot; "+whenInfo(u.resets,"resets"))
      : "在 config/usage-limits.json 填 usage_limit.spent / limit / resets";
    c1.appendChild(gaugeRow(u.label||"Spend limit", pct, sub, statusColor(pct==null?0:pct)));
    c1.appendChild(h("p","cap", (fromCloud
      ? "spent 由 Enterprise Analytics API 連外抓取；limit / resets 由 <code>config/usage-limits.json</code> 提供。"
      : "數值由你填入 <code>config/usage-limits.json</code>（air-gapped）。加 <code>-Cloud</code> 可連外抓真實 spent。")+
      " 下方是本機 token 分析。"));
    c1.appendChild(fetchedLine());
    app.appendChild(c1);

    // Section 2 — Claude Code and Cowork credit (a one-time included credit that expires)
    var c2=h("div","card");
    c2.appendChild(h("h2","","Claude Code and Cowork credit"));
    var cr=L.credit||{};
    if(cr.note) c2.appendChild(h("p","cap", cr.note));
    var cpct=(cr.used_pct!=null)? Number(cr.used_pct) : pctOf(cr.used,cr.total);
    var csub=(cr.expires? whenInfo(cr.expires,"expires") : "expiry not set");
    if(cpct==null) csub="在 config/usage-limits.json 填 credit.used_pct / expires";
    c2.appendChild(gaugeRow(cr.label||"Included credit", cpct, csub, statusColor(cpct==null?0:cpct)));
    c2.appendChild(fetchedLine());
    app.appendChild(c2);
  }

  function barBlock(rows, nameFn, tipFn, grand, rate){
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
      wrap.appendChild(row);
    });
    return wrap;
  }

  function renderTokenBars(){
    var card=h("div","card");
    card.appendChild(h("h2","","Token usage &middot; who spent what"));
    var sc=T.scope||{}, tot=T.totals||{};
    var tlim = (L.token_limit && Number(L.token_limit) > 0) ? Number(L.token_limit) : 0;
    var ulim = (L.usage_limit && Number(L.usage_limit.limit) > 0) ? Number(L.usage_limit.limit) : 0;
    // $ per token: tie the money conversion to the SAME basis as token_limit
    // (token_limit was derived so that it == the $ spend limit). 0 => money view off.
    var rate = (ulim > 0 && tlim > 0) ? (ulim / tlim) : 0;
    var cur = (L.usage_limit && L.usage_limit.currency) || "$";
    var pctBasis = tlim > 0
      ? ("% = 佔 token_limit (" + tlim.toLocaleString() + ") 的比例 — 此為<b>自訂參考值</b>，"
         + "方案的真實上限是上方的 $ 花費額度，Anthropic 並無官方 token 配額；在 config 可改")
      : "% = 佔本視窗總量的比例（在 config 設 token_limit 可改為佔額度%）";
    var moneyBasis = rate > 0
      ? (" &middot; <b>"+cur+" 為估算</b>：以 "+cur+ulim.toLocaleString()+" 花費額度 &divide; token_limit 換算"
         + "（約 "+cur+(rate*1e6).toFixed(3)+"／百萬 token，你的實際費率）")
      : "";
    card.appendChild(h("p","cap",
      "counted "+(sc.files_counted||0)+" transcript file(s); nested sub-agent/workflow "+
      (sc.include_nested?"included":"excluded")+". "+pctBasis+moneyBasis+". 'total' is mostly "+
      "cache_read (cheap re-reads); 'out' = generated tokens."));
    var tiles=h("div","tiles");
    tiles.appendChild(tileEl("total tokens", n(tot.total)));
    if(rate>0){ tiles.appendChild(tileEl("≈ "+cur+" this window (est)", usd(tot.total*rate))); }
    if(tlim>0){
      var usedPct=Math.min(100,(tot.total/tlim)*100);
      tiles.appendChild(tileEl("of token limit", usedPct.toFixed(1)+"%"));
    } else if(rate<=0){
      tiles.appendChild(tileEl("generated (output)", n(tot.output_tokens)));
    }
    if(rate<=0){ tiles.appendChild(tileEl("cache read", n(tot.cache_read_input_tokens))); }
    tiles.appendChild(tileEl("assistant turns", n(tot.msgs)));
    card.appendChild(tiles);
    if(rate>0 && ulim>0){
      var estSpend=tot.total*rate, spendPct=Math.min(100, estSpend/ulim*100);
      var sub="&asymp;"+usd(estSpend)+" / "+cur+ulim.toLocaleString()+" 月額度 &middot; 本視窗 token 換算的<b>估算</b>花費，"+
        "非真實帳單（真實 spent 見最上方 Spend limit，或用 <code>-Cloud</code> 連外抓）";
      card.appendChild(gaugeRow("本視窗估算花費 / 月額度 (est. spend vs monthly limit)", spendPct, sub, statusColor(spendPct)));
    }
    var grand=tot.total||0, top=8;
    var denom = tlim > 0 ? tlim : grand;
    if((T.by_conversation||[]).length){
      card.appendChild(h("div","sectlead","<b>By conversation</b> &mdash; per chat (top "+top+")"));
      card.appendChild(barBlock(T.by_conversation.slice(0,top),
        function(r){return r.title||(r.session||"").slice(0,12);},
        function(r){return (r.title||r.session)+" — "+n(r.total)+" total, "+r.msgs+" turns";}, denom, rate));
    }
    if((T.by_project||[]).length){
      card.appendChild(h("div","sectlead","<b>By project</b> &mdash; per working directory (top "+top+")"));
      card.appendChild(barBlock(T.by_project.slice(0,top),
        function(r){var p=String(r.project||"");return p.replace(/[\\/]+$/,"").split(/[\\/]/).pop()||p;},
        function(r){return r.project+" — "+n(r.total)+" total";}, denom, rate));
    }
    if((T.by_skill||[]).length){
      card.appendChild(h("div","sectlead","<b>By skill</b> &mdash; while each skill was active (top "+top+")"));
      card.appendChild(barBlock(T.by_skill.slice(0,top),
        function(r){return r.skill;},
        function(r){return r.skill+" — "+n(r.total)+" total, "+r.msgs+" turns";}, denom, rate));
    }
    app.appendChild(card);
  }
  function tileEl(k,v){ var t=h("div","tile"); t.appendChild(h("div","k",k)); t.appendChild(h("div","v",v)); return t; }

  function curve(pts, onPick){
    var W=920,H=240,padL=52,padR=54,padT=16,padB=32, iw=W-padL-padR, ih=H-padT-padB;
    var yMax=Math.max(1, Math.max.apply(null, pts.map(function(p){return p.val||0;}))*1.15);
    var m=pts.length;
    function X(i){ return padL+(m<=1? iw/2 : iw*i/(m-1)); }
    function Y(v){ return padT+ih-ih*(v/yMax); }
    var s=svg("svg",{viewBox:"0 0 "+W+" "+H, role:"img"});
    for(var t=0;t<=4;t++){ var v=yMax*t/4, y=Y(v);
      s.appendChild(svg("line",{x1:padL,y1:y,x2:W-padR,y2:y,stroke:"var(--grid)","stroke-width":1}));
      var lab=svg("text",{x:padL-8,y:y+4,"text-anchor":"end","class":"axis"});
      lab.textContent=Math.round(v).toLocaleString(); s.appendChild(lab); }
    s.appendChild(svg("line",{x1:padL,y1:Y(0),x2:W-padR,y2:Y(0),stroke:"var(--baseline)","stroke-width":1}));
    pts.forEach(function(p,i){ var lab=svg("text",{x:X(i),y:H-10,"text-anchor":"middle","class":"axis"});
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
      hit.addEventListener("mousemove",function(e){ showTip(e,"<b>"+p.label+"</b><br>"+n(p.val)+" total<br>out "+n(p.out)+" · "+p.msgs+" turns"); });
      hit.addEventListener("mouseleave",hideTip);
      hit.addEventListener("click",sel);
      markers.push(c); s.appendChild(c); s.appendChild(hit);
    });
    if(m){ markers[m-1].setAttribute("r",7);
      var lp=pts[m-1]; var tl=svg("text",{x:X(m-1)-4,y:Y(lp.val||0)-12,"text-anchor":"end","class":"lastlabel"});
      tl.textContent=Number(lp.val||0).toLocaleString(); s.appendChild(tl); }
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
    card.appendChild(h("p","cap","每日 token 用量（台灣時間，<b>以天為單位</b>，無活動的日子補 0）。點一個時間點看該日用量。"));
    var readout=h("div","readout");
    // fill every calendar day between the first and last active day so the x-axis is per-day
    var byDate={}; days.forEach(function(d){ byDate[d.date]=d; });
    function iso(dt){ return dt.getFullYear()+"-"+String(dt.getMonth()+1).padStart(2,"0")+"-"+String(dt.getDate()).padStart(2,"0"); }
    var pts=[];
    var cur=new Date(days[0].date+"T00:00:00"), end=new Date(days[days.length-1].date+"T00:00:00");
    var guard=0;
    while(cur<=end && guard++<1000){
      var key=iso(cur), d=byDate[key];
      pts.push(d ? {label:d.date,val:d.total,out:d.output_tokens,msgs:d.msgs}
                 : {label:key,val:0,out:0,msgs:0});
      cur.setDate(cur.getDate()+1);
    }
    function pick(p){ readout.innerHTML="選取 <b>"+p.label+"</b> &mdash; total <b>"+n(p.val)+
      "</b> &middot; output "+n(p.out)+" &middot; "+p.msgs+" turns"; }
    card.appendChild(curve(pts, pick));
    card.appendChild(readout);
    if(pts.length) pick(pts[pts.length-1]);
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

  function renderLegend(){
    var card=h("div","card");
    card.appendChild(h("h2","","欄位說明 (legend)"));
    var g=h("div","legend");
    g.innerHTML=
      "<div><b>total</b> — 該範圍全部 token（含快取，數字大屬正常）</div>"+
      "<div><b>output</b>（列上標 <b>out</b>）— 模型實際生成的 token</div>"+
      "<div><b>%</b> — token 各列佔『可用額度』(config token_limit) 或視窗總量的比例</div>"+
      "<div><b>&asymp;$</b>（各列）— 以 $ 花費額度 &divide; token_limit 換算的<b>估算</b>花費（你的實際費率）</div>"+
      "<div><b>cache read</b> — 每回合重讀的上下文（計費便宜）</div>"+
      "<div><b>turns</b> — assistant 回合數</div>"+
      "<div><b>usage limit / credit %</b> — 對照 Claude Usage 頁、由你填入 config（非即時抓取）</div>"+
      "<div>gauge 顏色：<span class='swatch' style='background:var(--good)'></span>&lt;50% "+
        "<span class='swatch' style='background:var(--warn)'></span>50–75% "+
        "<span class='swatch' style='background:var(--high)'></span>75–90% "+
        "<span class='swatch' style='background:var(--critical)'></span>&ge;90%</div>";
    card.appendChild(g); app.appendChild(card);
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
    renderLimits();
    renderCloud();
    if(!T || !T.totals){ app.appendChild(h("div","empty",
      "No token data yet. Run <code>token_report.py</code> (or <code>Show-MonitorDashboard</code>) and reload.")); return; }
    renderTokenBars();
    renderRecent();
    renderCurve();
    renderLegend();
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
