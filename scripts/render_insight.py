#!/usr/bin/env python3
"""
render_insight.py — Phase 4: person-facing INSIGHT HTML report (NO SCORE).

A self-contained, BMW-styled HTML companion to render_growth.py's markdown note. It turns the
per-session capability signals (raw-sessions/capability-signals.json) into:

  - an 8-domain 觀察熱度 (evidence-COVERAGE) PURE-CSS HEATMAP — how often each domain showed up in
    the scanned conversations, shown ONLY as a heat-band color (no number/axis/tick/percentage),
    NEVER a capability level / rung / signal_tier;
  - per-domain forward growth directions (growth_hint ONLY, forward_only-normalized);
  - a gentle habits section (bias_flags) and a coverage-honesty (lower-bound) section.

Hard RL4-ii constraints (mirrors render_growth.py exactly):
  - NEVER surfaces signal_tier / rung / any score word — not as value, legend, tick, or prose.
  - The heat color encodes frequency-of-OBSERVATION (present-count ÷ sessions-scanned) = coverage
    density on a FIXED 0-100 scale (INTERNAL ONLY — quantized to heat bands, never rendered as a
    number), so it can never read as an ability ceiling and a band-1 (未觀察) tile means "not yet
    observed in this window" (coverage gap), not "low ability".
  - Only growth_hint is surfaced per domain; evidence_refs inform ONLY the aggregate density count
    and are never quoted.
  - Shows source_scope + lower-bound honesty (RL4-iv / operator ruling #10).

Self-containment (RL#5): NO vendored library at all (Emil ruling 2026-07-15 retired the Chart.js
radar). The heatmap is pure CSS; theming is handled solely by @media (prefers-color-scheme). The
only inline <script> is a small clipboard copy-helper. python3 STDLIB only, deterministic, fail-loud.

I18N (Emil order 2026-07-15): report chrome renders zh-TW by default; --lang en is also supported.
Only the CHROME (labels/headings/templates) is localized via LOCALES — observation CONTENT
(growth_hint / bias text) is rendered AS EXTRACTED, never translated. Every en string is worded to
avoid check-visibility-seam.sh gate (c)'s SCORE_RE deny regex (no score/rung/tier/R0-7 words, incl.
in negations).

Output = output/insight-<date>-<project|all>.html (default lang), or
output/insight-<date>-<project|all>-<lang>.html for a non-default lang (PRIVATE, gitignored).
Must pass check-visibility-seam.sh gate (c) (now extended to scan output/**/*.html with
script/style stripped).

Usage:
  render_insight.py [--in raw-sessions/capability-signals.json] [--index worktemp/session-index.json]
                    [--out PATH] [--project SUBSTR|all] [--source-scope claude-code-cli]
                    [--blind-spots codex-cli,chatgpt,claude-desktop] [--heat-bands {5,8}]
                    [--date YYYY-MM-DD] [--lang zh-TW|en]
"""

import argparse
import html
import json
import math
import os
import re
import sys
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
# REUSE the exact same aggregation + forward-normalization logic as render_growth.py so neither
# surface can drift. Importing render_growth is side-effect-free (its main() is under __main__).
from _growth_hint import forward_only  # noqa: E402
from render_growth import DOMAINS, load_labels, collect  # noqa: E402

# --- i18n: chrome-only. Observation CONTENT (growth_hint / bias text) is NEVER translated — it
#     renders in whatever language it was extracted in. zh-TW values below are the EXACT strings
#     this file used before i18n landed (byte-identical zh-TW output is the acceptance bar).
LOCALES = {
    "zh-TW": {
        "html_lang": "zh-Hant",
        "title": "你的 AI 使用觀察筆記",
        "hero_h1": "你的 AI 使用觀察筆記",
        "hero_disclaimer": (
            '這份筆記只給你自己看，重點是<strong>接下來可以往哪裡走</strong>。'
            '下面看到的每一條，都是「可以再試試」的方向，是往前看的成長建議，不是回頭看的檢討。'
            '這裡不談誰高誰低，只談這次的對話裡觀察到了哪些使用習慣、以及下一步可以怎麼走。'
        ),
        "extraction_note": None,  # zh-TW is the extraction language convention; no extra note.
        "filler": "這次掃到的範圍裡還沒有這方面的具體方向，之後累積更多對話後可以再看。",
        "stat_extracted": "依據 session 數（已抽取）",
        "stat_scanned": "上次掃描索引 session 數",
        "stat_span": "時間範圍",
        "stat_scope": "掃到的範圍",
        "stat_domains_observed": "這次觀察到的領域數",
        "val_none": "（無）",
        "val_dash": "—",
        "summary_label": "重點摘要",
        "summary_title": "先看這幾件事",
        "callout_top_density_kicker": "最常出現的方向：",
        "callout_top_density_text": "這次的對話裡，{names} 出現得最多，可以先從這幾個方向看下一步。",
        "callout_top_density_empty": "這次掃到的範圍還沒累積到明顯的方向，之後多幾次對話後再回來看。",
        "callout_top_bullets_kicker": "可以再往前一步：",
        "callout_top_bullets_text": "{names} 這幾個方向，這次累積了最多可以嘗試的下一步，值得優先試試。",
        "callout_top_bullets_empty": "這次還沒有具體的下一步方向，等累積更多對話後會慢慢浮現。",
        "callout_coverage_kicker": "涵蓋率提醒：",
        "callout_coverage_text": (
            "這份筆記只掃到部分工具，還有 {blind_count} 種工具這次沒有看到；"
            "詳見下方 {link}，沒掃到不代表那裡能力低。"
        ),
        "coverage_link_text": "涵蓋率說明",
        "heatmap_label": "涵蓋視覺",
        "heatmap_title": "觀察熱度",
        "heatmap_caption": (
            "顏色深淺 = 這個領域在本次已抽取的對話中出現的頻率，"
            "<strong>不是能力高低</strong>。某個領域顏色很淡，只代表這次的對話裡還沒怎麼掃到它，"
            "不代表你在那裡表現不好。"
        ),
        "tab_heat_label": "觀察熱度",
        "tab_radar_label": "工作向性",
        "radar_caption": (
            "顯示本次 Extract 專案或時間區的工作內容向性主要是那些面向，"
            "顯示的向性為單純依照 Prompt 類型分類後統計，不代表技能熟練度，"
            "技能熟練度建議請參考觀察熱度。"
        ),
        "legend_low": "這次較少出現",
        "legend_high": "這次較常出現",
        "growth_label": "成長方向",
        "growth_title": "可以再往前一步的方向",
        "copy_all_btn": "全部複製",
        "copy_btn": "複製",
        "density_chip": "本次觀察：{present} 次 ／ 共 {total} session（已抽取）",
        "habits_label": "使用習慣",
        "habits_title": "要注意的 AI 壞習慣",
        "habits_intro": "這些是從你跟 AI 的對話裡觀察到、可以調整的方向，如果反覆發生，可以考慮設定為規則避免 AI 再犯。",
        "bucket_self_correct": "通常你自己會修正回來",
        "bucket_watch": "值得刻意留意",
        "coverage_label": "涵蓋率",
        "coverage_title": "這份筆記看到了多少（涵蓋率）",
        "coverage_sentence1": (
            "上次掃描索引到 <strong>{scanned}</strong> 個本機對話 session；"
            "其中 <strong>{extracted}</strong> 個實際被抽取進本次分析"
            "（上面的觀察熱度圖與方向卡片都是依這個已抽取數量統計的）。"
        ),
        "coverage_sentence2": "<strong>掃到的工具</strong>：{scope}。",
        "coverage_sentence3_blind": "<strong>沒掃到的工具</strong>：{blind} — 這些目前讀不到（server 端或尚未接入）。",
        "coverage_disclaimer": (
            "⚠️ <strong>這是一個最低限度估算：可能會因為工作型態跟工具的不同會有對話沒有掃到</strong>，"
            "沒掃到的地方只代表這份筆記還沒看到那部分，"
            "之後會開發手動匯入對話的機制讓你可以使用這個 Agent 幫你分析其他的 AI 對話。"
        ),
        "footer_date": "產生日期：{date}",
        "footer_local": "本檔僅存於本機，不會離開這台機器。",
        "footer_colorline": "顏色深淺為涵蓋率頻率，非能力評量；內容為往前看的成長方向。",
        "card_dir_sublabel": "可以再往前一步",
        "card_strength_sublabel": "值得持續保持的做法",
        "more_label": "更多（＋{n}）",
    },
    "en": {
        "html_lang": "en",
        "title": "Your AI Usage Observation Notes",
        "hero_h1": "Your AI Usage Observation Notes",
        "hero_disclaimer": (
            "This note is for your eyes only, and the focus is on "
            "<strong>where you can go next</strong>. Everything below is a "
            "‘worth trying next’ direction — forward-looking growth suggestions, "
            "not a retrospective review. This isn’t about who ranks higher or lower — "
            "it’s about which usage habits showed up in this round of conversations, and "
            "what the next step could be."
        ),
        "extraction_note": "Observation content appears in the language it was extracted in.",
        "filler": (
            "No specific direction yet within this scanned window — check back after more "
            "conversations accumulate."
        ),
        "stat_extracted": "Sessions used (extracted)",
        "stat_scanned": "Sessions indexed in last scan",
        "stat_span": "Time span",
        "stat_scope": "Scope scanned",
        "stat_domains_observed": "Domains observed this time",
        "val_none": "(none)",
        "val_dash": "—",
        "summary_label": "Summary",
        "summary_title": "A few things to look at first",
        "callout_top_density_kicker": "Most frequent directions:",
        "callout_top_density_text": (
            "In this round of conversations, {names} showed up the most — a good place to "
            "start for next steps."
        ),
        "callout_top_density_empty": (
            "This scan hasn’t accumulated a clear direction yet — check back after a "
            "few more conversations."
        ),
        "callout_top_bullets_kicker": "Worth pushing further:",
        "callout_top_bullets_text": (
            "{names} accumulated the most next-step suggestions this time — worth trying "
            "first."
        ),
        "callout_top_bullets_empty": (
            "No concrete next step yet this time — these will surface as more "
            "conversations accumulate."
        ),
        "callout_coverage_kicker": "Coverage note:",
        "callout_coverage_text": (
            "This note only scanned part of your tools — {blind_count} tool(s) weren’t "
            "seen this time; see {link} below. Not being scanned doesn’t mean lower ability "
            "there."
        ),
        "coverage_link_text": "Coverage Notes",
        "heatmap_label": "Coverage View",
        "heatmap_title": "Observation Heat",
        "heatmap_caption": (
            "Color intensity reflects how often this domain appeared in the scanned sessions "
            "— <strong>it does not measure ability</strong>. A faint tile just means this "
            "domain hasn’t been scanned much yet this time, not that you performed poorly "
            "there."
        ),
        "tab_heat_label": "Observation Heat",
        "tab_radar_label": "Work Orientation",
        "radar_caption": (
            "This shows which aspects the work content of this Extract's project or time "
            "range leans toward. The orientation is tallied purely by Prompt-type "
            "classification and does not reflect skill familiarity; for skill familiarity "
            "please refer to Observation Heat."
        ),
        "legend_low": "Appeared less this time",
        "legend_high": "Appeared more this time",
        "growth_label": "Growth Directions",
        "growth_title": "Directions worth pushing further",
        "copy_all_btn": "Copy All",
        "copy_btn": "Copy",
        "density_chip": "Observed {present} time(s) / {total} session(s) (extracted)",
        "habits_label": "Usage Habits",
        "habits_title": "AI habits to watch out for",
        "habits_intro": (
            "These are directions to adjust, observed in your conversations with the AI. "
            "If one keeps recurring, consider setting it as a rule so the AI stops repeating it."
        ),
        "bucket_self_correct": "Usually self-corrected",
        "bucket_watch": "Worth watching deliberately",
        "coverage_label": "Coverage",
        "coverage_title": "How much did this note see (coverage)",
        "coverage_sentence1": (
            "The last scan indexed <strong>{scanned}</strong> local conversation session(s); "
            "<strong>{extracted}</strong> were actually extracted into this analysis (the heat "
            "view and direction cards above are based on this extracted count)."
        ),
        "coverage_sentence2": "<strong>Tools scanned</strong>: {scope}.",
        "coverage_sentence3_blind": (
            "<strong>Tools not scanned</strong>: {blind} — these aren’t currently "
            "reachable (server-side or not yet connected)."
        ),
        "coverage_disclaimer": (
            "⚠️ <strong>This is a minimum estimate: depending on your work style and tools, "
            "some conversations may not have been scanned</strong> — anywhere not scanned just "
            "means this note hasn’t seen that part yet. A manual conversation-import mechanism is "
            "planned so you can use this agent to analyze your other AI conversations too."
        ),
        "footer_date": "Generated on: {date}",
        "footer_local": "This file lives only on this machine and will not leave it.",
        "footer_colorline": (
            "Color intensity reflects coverage frequency, not ability; content is "
            "forward-looking growth direction."
        ),
        "card_dir_sublabel": "Directions to push further",
        "card_strength_sublabel": "Worth keeping up",
        "more_label": "Show more (+{n})",
    },
}

# en domain labels are a literal, deterministic dict (no machine transform of the zh-TW yaml).
EN_LABELS = {
    "DESIGN": "Design",
    "FRAMEWORK-SELECTION": "Framework Selection",
    "CODING": "Coding",
    "TUNING": "Tuning",
    "CONTEXT-ENGINEERING": "Context Engineering",
    "EVAL": "Eval",
    "ADVISORY": "Advisory",
    "CONTINUITY": "Continuity",
}


def die(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def esc(x):
    """html.escape every model-derived string before it touches the HTML (injection discipline)."""
    return html.escape("" if x is None else str(x))


_CJK = r'㐀-鿿豈-﫿々'
_FW_MAP = {',': '，', '.': '。', ':': '：', ';': '；', '!': '！', '?': '？', '(': '（', ')': '）'}
_FW_PUNC = r',.:;!?()'


def fullwidth_cjk(s):
    """Normalize half-width , . : ; ! ? ( ) to full-width ONLY when adjacent to a CJK char.
    Pure-ASCII runs (product names, versions like 0.1, code) are left untouched (no CJK
    neighbor), so this never mangles ASCII or product names."""
    if not s:
        return s
    rep = lambda m: _FW_MAP[m.group(1)]
    s = re.sub(rf'(?<=[{_CJK}])([{_FW_PUNC}])', rep, s)   # punct preceded by CJK
    s = re.sub(rf'([{_FW_PUNC}])(?=[{_CJK}])', rep, s)     # punct followed by CJK
    return s


# The strength items already sit UNDER the "值得持續保持的做法" sub-label; a per-bullet
# lead-in that repeats that framing (an extraction-contract artifact) is redundant boilerplate,
# so strip it at render time. Two shapes occur: (1) a noun-phrase opener terminated by a
# separator ("值得持續保持的做法：…"), and (2) a verb-phrase opener with no separator
# ("可以繼續…", "接下來也保持…"). Backstop only — the contract no longer asks for either; this
# also cleans data already extracted under the old contract.
_STRENGTH_LEADIN_SEP = re.compile(   # shape 1: "值得持續保持的做法：" / "可以繼續的做法、"
    r'^\s*(?:值得|可以)?(?:持續|繼續)?(?:保持|維持)?(?:的)?(?:做法|習慣|方式|作法)?\s*(?:是)?\s*[:：、，,]\s*'
)
_STRENGTH_LEADIN_VERB = re.compile(  # shape 2: "可以繼續" / "接下來也(可以)?(持續|繼續)?保持" + no separator
    r'^\s*(?:可以繼續|接下來(?:也)?(?:可以)?(?:持續|繼續)?保持|繼續保持|持續保持)\s*'
)


# After stripping the boilerplate opener, a bullet whose remainder is only a content-free
# filler ("維持這個習慣。", "保持下去。") carries no actual practice — drop it (contract:
# "an empty or forced strength is worse than null").
_STRENGTH_FILLER = re.compile(r'^(?:維持|保持|持續|繼續)?(?:這個|此)?(?:習慣|做法|方式|作法|下去)?[。.，,]*$')


def is_substantive_strength(s):
    """True if the (already lead-in-stripped) strength bullet still states a real practice."""
    if not s:
        return False
    core = s.strip().rstrip('。.！!，,、')
    if len(core) < 6:            # too short to be a described practice
        return False
    return not _STRENGTH_FILLER.match(s.strip())


def strip_strength_leadin(s):
    """Remove a redundant '值得持續保持的做法：' / '可以繼續…' style opener from a strength
    bullet so it does not echo its own section label on every line. Shape 1 requires a
    trailing separator (never truncates real content); shape 2 matches the fixed verb openers.
    Never strips down to empty (falls back to the original if the opener IS the whole string)."""
    if not s:
        return s
    m = _STRENGTH_LEADIN_SEP.match(s)
    if m and re.search(r'持續|繼續|保持|維持|做法|作法', m.group(0)):
        rest = s[m.end():].lstrip()
        return rest if rest else s
    m = _STRENGTH_LEADIN_VERB.match(s)
    if m:
        rest = s[m.end():].lstrip()
        return rest if rest else s
    return s


def render_capped_list(h, items, li_class, more_label, cap=5):
    """Append a <ul> with the first `cap` items; put any remainder behind a native
    <details>. items are already esc-ready strings (already fullwidth_cjk-normalized)."""
    head, tail = items[:cap], items[cap:]
    h.append('<ul>')
    for it in head:
        cls = f' class="{li_class}"' if li_class else ''
        h.append(f'<li{cls}>{esc(it)}</li>')
    h.append('</ul>')
    if tail:
        h.append(f'<details class="more"><summary>{esc(more_label.format(n=len(tail)))}</summary>')
        h.append('<ul>')
        for it in tail:
            cls = f' class="{li_class}"' if li_class else ''
            h.append(f'<li{cls}>{esc(it)}</li>')
        h.append('</ul></details>')


# --- heat-band model (Emil ruling 2026-07-15). The 0-100 density is INTERNAL; it is quantized to a
#     heat BAND (1..B) that only ever surfaces as a background COLOR — never a number/axis/tick.
HEAT_RGB = "21,128,61"  # GREEN ramp (green-700); operator: blue not visible enough. Intensity via the per-band alpha ladder below. Base is dark enough that white text on the TOP band (full alpha) stays AA-legible.
# Exact operator-specified 5-stop alpha ladders (band1..band5) for the DEFAULT B=5.
LIGHT_ALPHAS_5 = [0.06, 0.22, 0.42, 0.68, 1.0]
DARK_ALPHAS_5 = [0.10, 0.28, 0.48, 0.72, 1.0]


def density_to_band(d, B):
    """Deterministic density(0-100) -> band(1..B). band = 1 if d==0 else 1 + ceil(d/(100/(B-1))),
    clamped to B. For B=5: 0->1, (0,25]->2, (25,50]->3, (50,75]->4, (75,100]->5."""
    if d <= 0:
        return 1
    band = 1 + math.ceil(d / (100.0 / (B - 1)))
    return min(band, B)


def heat_alphas(B, mode):
    """Per-band alpha ladder. B=5 returns the exact operator tuples; other B linearly interpolate
    the alpha from the band-1 start to 1.0 (endpoints preserved). mode in {'light','dark'}."""
    if B == 5:
        return list(LIGHT_ALPHAS_5 if mode == "light" else DARK_ALPHAS_5)
    first = 0.06 if mode == "light" else 0.10
    return [round(first + (1.0 - first) * i / (B - 1), 3) for i in range(B)]


def build_band_css(B):
    """Emit .band-N background (light default + dark @media override) + readable text color rules.
    NIT-1 (adversarial verifier): light text is a contrast risk on the mid-alpha bands in LIGHT
    mode (measured band-4 CR 2.67, below AA) — in LIGHT mode only the TOP band (n==B) gets light
    text (#f5f5f5); every band below that uses var(--black). In DARK mode the background alphas are
    higher across the board (measured band>=4 CR 6.90, fine), so bands >= 4 keep light text there.
    band-1 gets a --hairline border in both modes."""
    rows = []
    light = heat_alphas(B, "light")
    dark = heat_alphas(B, "dark")
    for i in range(B):
        n = i + 1
        light_txt = "#f5f5f5" if n == B else "var(--black)"
        border = " border:1px solid var(--hairline);" if n == 1 else ""
        rows.append(f".band-{n} {{ background:rgba({HEAT_RGB},{light[i]}); color:{light_txt};{border} }}")
    dark_rows = []
    for i in range(B):
        n = i + 1
        dark_txt = "#f5f5f5" if n >= 4 else "var(--black)"
        dark_rows.append(f"  .band-{n} {{ background:rgba({HEAT_RGB},{dark[i]}); color:{dark_txt}; }}")
    rows.append("@media (prefers-color-scheme: dark) {\n" + "\n".join(dark_rows) + "\n}")
    return "\n".join(rows)


def compute_density(signals):
    """density[d] = 0 if N==0 else min(100, round(100 * present_count / N)). Reads ONLY .present."""
    n = len(signals)
    density = {}
    present = {}
    for d in DOMAINS:
        cnt = sum(1 for s in signals
                  if bool(((s.get("domain_signals") or {}).get(d) or {}).get("present")))
        present[d] = cnt
        density[d] = 0 if n == 0 else min(100, round(100 * cnt / n))
    return density, present


# --- CSS: BMW design system, single self-contained <style>. Role-based tokens; dark via
#     prefers-color-scheme overriding the SAME variable VALUES. Zero border-radius everywhere;
#     blue (#1c69d4) only on interactive/data elements; depth via dark/light section alternation.
CSS = """
* { margin:0; padding:0; box-sizing:border-box; border-radius:0; }
:root {
  --white:#ffffff; --black:#262626; --bmw-blue:#1c69d4; --focus-blue:#0653b6;
  --meta:#757575; --silver:#bbbbbb; --dark:#1a1a1a; --hairline:#e0e0e0;
  --font:'Inter',Helvetica,Arial,'Hiragino Kaku Gothic ProN','Hiragino Sans',Meiryo,sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root { --white:#1a1a1a; --black:#e0e0e0; --meta:#999999; --silver:#666666; --hairline:#333333; }
}
html { scroll-behavior:smooth; }
body { background:var(--white); color:var(--black); font-family:var(--font);
       font-size:16px; font-weight:400; line-height:1.15; -webkit-font-smoothing:antialiased; }
a { color:var(--bmw-blue); text-decoration:none; }
a:hover { opacity:.8; }
:focus { outline:none; box-shadow:0 0 0 2px rgba(6,83,182,.2); }

/* dark full-bleed surfaces (constant #1a1a1a in both modes -> constant light text) */
.hero { padding:80px 32px; background:var(--dark); color:#f5f5f5; }
.hero h1 { font-size:60px; font-weight:300; line-height:1.30; text-transform:uppercase; margin-bottom:16px; }
.hero p { font-size:16px; line-height:1.30; color:#bbbbbb; max-width:680px; }
.hero .hero-note { font-size:13px; margin-top:12px; color:#999999; }
.footer { padding:48px 32px; background:var(--dark); color:#bbbbbb; }
.footer p { font-size:12px; line-height:1.30; color:#999999; max-width:900px; margin-bottom:8px; }
.footer .foot-strong { color:#f5f5f5; font-weight:700; }

.section { padding:64px 32px; max-width:1100px; margin:0 auto; }
.section-label { font-size:12px; font-weight:900; color:var(--meta);
                 text-transform:uppercase; letter-spacing:1px; }
.section-title { font-size:32px; font-weight:400; line-height:1.30; margin:8px 0 24px 0; }
.section-divider { border:none; border-top:1px solid var(--hairline); max-width:1100px; margin:0 auto; }
.section p { font-size:16px; line-height:1.30; color:var(--black); margin-bottom:12px; }
.muted { color:var(--meta); }

/* stat row */
.stat-row { max-width:1100px; margin:0 auto; padding:32px; display:flex; flex-wrap:wrap; gap:16px; }
.stat-chip { border:1px solid var(--hairline); padding:16px 20px; min-width:180px; flex:1 1 180px; }
.stat-chip .stat-label { font-size:12px; font-weight:900; color:var(--meta);
                         text-transform:uppercase; letter-spacing:1px; }
.stat-chip .stat-value { font-size:24px; font-weight:700; line-height:1.20; margin-top:8px; }

/* callout */
.callout { border:1px solid var(--hairline); padding:24px; margin-top:8px; }
.callout .callout-block { margin-bottom:16px; line-height:1.30; }
.callout .callout-block:last-child { margin-bottom:0; }
.callout .callout-kicker { font-weight:900; }

/* pure-CSS heatmap — heat comes ONLY from the per-band background color (see .band-N rules,
   generated per --heat-bands). No numbers/axes/ticks anywhere in this section. */
.heat-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:8px;
             max-width:1000px; margin:0 auto; }
.heat-tile { display:flex; align-items:center; justify-content:center; text-align:center;
             min-height:96px; padding:20px 16px; font-size:16px; font-weight:700; line-height:1.30; }
.heat-legend { max-width:1000px; margin:24px auto 0 auto; display:flex; align-items:center;
               flex-wrap:wrap; gap:8px; }
.heat-legend .heat-legend-label { font-size:12px; font-weight:900; color:var(--meta);
                                  text-transform:uppercase; letter-spacing:1px; }
.heat-swatch { width:28px; height:16px; display:inline-block; }
@media (max-width:768px) {
  .heat-grid { grid-template-columns:repeat(2,1fr); }
}

/* pure-CSS radio+:checked tab toggle (NO JS — survives <script>/<style> strip since the toggle
   logic is CSS-only and the CSS itself lives inside <style>, which the gate strips before scan). */
.tabs { max-width:1000px; margin:0 auto; }
.tab-radio { position:absolute; width:1px; height:1px; opacity:0; pointer-events:none; }
.tab-labels { display:flex; gap:0; border-bottom:1px solid var(--hairline); margin-bottom:24px; }
.tab-label { font-size:14px; font-weight:900; text-transform:uppercase; letter-spacing:1px;
             color:var(--meta); padding:12px 20px; cursor:pointer; border-bottom:2px solid transparent;
             margin-bottom:-1px; }
.tab-panel { display:none; }
#tab-heat:checked  ~ .tab-panel.panel-heat  { display:block; }
#tab-radar:checked ~ .tab-panel.panel-radar { display:block; }
#tab-heat:checked  ~ .tab-labels label[for="tab-heat"]  { color:var(--black); border-bottom-color:var(--bmw-blue); }
#tab-radar:checked ~ .tab-labels label[for="tab-radar"] { color:var(--black); border-bottom-color:var(--bmw-blue); }
/* keyboard focus visibility for the hidden radios */
.tab-radio:focus ~ .tab-labels label[for="tab-heat"],
.tab-radio:focus ~ .tab-labels label[for="tab-radar"] { }  /* optional; the :checked underline suffices */

/* radar (工作向性) — pure hand-drawn SVG, no Chart.js/canvas. Light orange, distinct from the
   heatmap's green ramp; var(--black) axis labels flip with prefers-color-scheme. */
.radar-grid  { fill:none; stroke:rgba(128,128,128,0.30); stroke-width:1; }
.radar-spoke { stroke:rgba(128,128,128,0.30); stroke-width:1; }
.radar-area  { fill:rgba(255,167,38,0.25); stroke:#f57c00; stroke-width:2; }
.radar-dot   { fill:#ef6c00; stroke:none; }
.radar-axis-label { fill:var(--black); font-size:12px; font-weight:700; font-family:var(--font); }
.radar-pct { fill:#e65100; font-size:11px; font-weight:900; font-family:var(--font); }
@media (prefers-color-scheme: dark) {
  .radar-area { fill:rgba(255,167,38,0.32); }
  .radar-pct  { fill:#ffb74d; }
}

/* card grid */
.card-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:16px; }
.card { background:var(--white); border:1px solid var(--hairline); padding:24px;
        display:flex; flex-direction:column; }
.card h3 { font-size:18px; font-weight:700; line-height:1.30; margin-bottom:8px; }
.density-chip { align-self:flex-start; font-size:12px; font-weight:900; color:var(--meta);
                text-transform:uppercase; letter-spacing:1px; border:1px solid var(--hairline);
                padding:4px 10px; margin-bottom:12px; }
.card ul { list-style:none; margin:0 0 16px 0; padding:0; flex:1 1 auto; }
.card li { font-size:16px; line-height:1.30; color:var(--black); margin-bottom:8px; padding-left:16px;
           position:relative; }
.card li::before { content:'•'; position:absolute; left:0; color:var(--bmw-blue); }
.card li.filler { color:var(--meta); }
.card-sublabel { font-size:12px; font-weight:900; color:var(--meta); text-transform:uppercase; letter-spacing:1px; margin:4px 0 6px 0; }
details.more > summary { cursor:pointer; font-size:14px; font-weight:700; color:var(--bmw-blue); margin-top:4px; }
details.more[open] > summary { margin-bottom:8px; }
details.more > ul { margin-top:8px; }

/* habits */
.habit-bucket { margin-bottom:24px; }
.habit-bucket h3 { font-size:18px; font-weight:700; line-height:1.30; margin-bottom:8px; }
.habit-bucket ul { list-style:none; margin:0; padding:0; }
.habit-bucket li { font-size:16px; line-height:1.30; margin-bottom:8px; padding-left:16px; position:relative; }
.habit-bucket li::before { content:'•'; position:absolute; left:0; color:var(--bmw-blue); }

/* buttons (blue = interactive) */
.btn-blue { display:inline-block; align-self:flex-start; background:var(--bmw-blue); color:#fff;
            padding:10px 20px; font-family:var(--font); font-size:14px; font-weight:700;
            border:none; cursor:pointer; }
.btn-blue:hover { opacity:.9; }

@media (max-width:768px) {
  .hero { padding:60px 20px; }
  .hero h1 { font-size:36px; }
  .section { padding:48px 20px; }
  .stat-row { padding:24px 20px; }
  .card-grid { grid-template-columns:1fr; }
}
""".strip()


# --- inline JS: the ONLY script now — a small clipboard copy-helper (with execCommand fallback).
#     copyText() copies an element's innerText (per-card 複製). copyAll() copies the hidden
#     textarea holding all 8 domains' forward directions (全部複製). No chart, no matchMedia.
def build_js():
    return """
function copyStr(s) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(s);
  } else {
    var ta = document.createElement('textarea');
    ta.value = s;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta);
  }
}
function copyText(id) {
  var el = document.getElementById(id);
  if (!el) return;
  copyStr(el.innerText);
}
function copyAll() {
  var el = document.getElementById('all-dirs');
  if (!el) return;
  copyStr(el.value);
}
function copyField(id) {
  var el = document.getElementById(id);
  if (el) copyStr(el.value);
}
""".strip()


def build_radar_svg(labels, present):
    """Pure hand-drawn <svg> radar (工作向性) — NO Chart.js/canvas/external lib (Emil ruling
    2026-07-15). Geometry uses present[d] (raw observation COUNT) max-normalized across the 8
    domains — NOT density[d] — per the operator's explicit spec. The % (count ÷ max-count) is used
    ONLY to scale the polygon geometry; each vertex's LABEL shows the raw COUNT itself. This axis
    is a FREQUENCY tally of prompt types, NOT an ability score (operator clarification 2026-07-15 —
    顯示次數, 單純頻次統計)."""
    order = DOMAINS
    counts = [present[d] for d in order]
    mx = max(counts) if counts else 0
    cx, cy, R, N = 220, 205, 120, 8
    s = ['<svg class="radar" viewBox="0 0 440 430" role="img" aria-label="radar" '
         'preserveAspectRatio="xMidYMid meet" '
         'style="width:100%;max-width:520px;height:auto;display:block;margin:0 auto 24px;overflow:visible;">']
    thetas = [-math.pi / 2 + i * (2 * math.pi / N) for i in range(N)]
    for r in (0.25, 0.5, 0.75, 1.0):
        pts = ' '.join(f'{cx + R * r * math.cos(t):.1f},{cy + R * r * math.sin(t):.1f}' for t in thetas)
        s.append(f'<polygon class="radar-grid" points="{pts}"/>')
    for t in thetas:
        s.append(f'<line class="radar-spoke" x1="{cx}" y1="{cy}" '
                 f'x2="{cx + R * math.cos(t):.1f}" y2="{cy + R * math.sin(t):.1f}"/>')
    verts = [(counts[i] / mx if mx > 0 else 0) for i in range(N)]
    vpts = ' '.join(f'{cx + R * verts[i] * math.cos(thetas[i]):.1f},{cy + R * verts[i] * math.sin(thetas[i]):.1f}'
                    for i in range(N))
    s.append(f'<polygon class="radar-area" points="{vpts}"/>')
    for i in range(N):
        vx = cx + R * verts[i] * math.cos(thetas[i])
        vy = cy + R * verts[i] * math.sin(thetas[i])
        s.append(f'<circle class="radar-dot" cx="{vx:.1f}" cy="{vy:.1f}" r="3"/>')
        # raw COUNT label just outside each vertex — the % is used only to scale the geometry;
        # the number shown is the frequency tally itself (operator: 顯示次數, not %)
        px = cx + (R * verts[i] + 15) * math.cos(thetas[i])
        py = cy + (R * verts[i] + 15) * math.sin(thetas[i])
        s.append(f'<text class="radar-pct" x="{px:.1f}" y="{py:.1f}" '
                 f'text-anchor="middle" dy="0.32em">{counts[i]}</text>')
    for i, d in enumerate(order):
        t = thetas[i]
        c = math.cos(t)
        si = math.sin(t)
        lx = cx + R * 1.18 * c
        ly = cy + R * 1.18 * si
        anchor = 'middle' if abs(c) < 0.30 else ('start' if c > 0 else 'end')
        dy = '0.75em' if si > 0.30 else ('-0.2em' if si < -0.30 else '0.32em')
        s.append(f'<text class="radar-axis-label" x="{lx:.1f}" y="{ly:.1f}" '
                 f'text-anchor="{anchor}" dy="{dy}">{esc(labels[d])}</text>')
    s.append('</svg>')
    return '\n'.join(s)


def build_html(L, lang, signals, index, labels, per_dom, biases, density, present,
               scope, blind, project, sessions_scanned, span, heat_bands, render_date):
    n = len(signals)
    total = n  # heatmap/density denominator == number of scanned signal records

    # forward-normalized, deduped growth bullets per domain (dedup already done by collect()).
    bullets = {}
    for d in DOMAINS:
        hs = [fullwidth_cjk(forward_only(h)) for h in per_dom[d]["hints"]]
        bullets[d] = [h for h in hs if h]

    # forward-normalized, deduped strength bullets per domain (no-score, forward-only backstop).
    strengths = {}
    for d in DOMAINS:
        ss = [fullwidth_cjk(strip_strength_leadin(forward_only(s))) for s in per_dom[d]["strengths"]]
        strengths[d] = [s for s in ss if is_substantive_strength(s)]

    domains_observed = sum(1 for d in DOMAINS if density[d] > 0)

    # --- deterministic callout selections (rank only, no numbers in prose for a/b) ---
    by_density = sorted(DOMAINS, key=lambda d: -density[d])
    top_density = [d for d in by_density if density[d] > 0][:2]
    by_bullets = sorted(DOMAINS, key=lambda d: -len(bullets[d]))
    top_bullets = [d for d in by_bullets if len(bullets[d]) > 0][:2]

    def dom_link(d):
        return f'<a href="#domain-{esc(d)}">{esc(labels[d])}</a>'

    h = []
    h.append('<div class="page">')

    # 1. HERO
    h.append('<header class="hero">')
    h.append(f'<h1>{esc(L["hero_h1"])}</h1>')
    h.append(f'<p>{L["hero_disclaimer"]}</p>')
    if L.get("extraction_note"):
        h.append(f'<p class="hero-note">{esc(L["extraction_note"])}</p>')
    h.append('</header>')

    # 2. STAT ROW
    h.append('<div class="stat-row">')
    stats = [
        (L["stat_extracted"], esc(n)),
        (L["stat_scanned"], esc(sessions_scanned)),
        (L["stat_span"], esc(span)),
        (L["stat_scope"], esc(", ".join(scope) if scope else L["val_none"])),
        (L["stat_domains_observed"], f"{domains_observed} / {len(DOMAINS)}"),
    ]
    for lab, val in stats:
        h.append('<div class="stat-chip">'
                 f'<div class="stat-label">{esc(lab)}</div>'
                 f'<div class="stat-value">{val}</div></div>')
    h.append('</div>')

    # 3. 重點摘要 CALLOUT
    h.append('<section class="section">')
    h.append(f'<div class="section-label">{esc(L["summary_label"])}</div>')
    h.append(f'<h2 class="section-title">{esc(L["summary_title"])}</h2>')
    h.append('<div class="callout">')
    # (a) top-density directions
    if top_density:
        names = "、".join(dom_link(d) for d in top_density) if lang == "zh-TW" \
            else ", ".join(dom_link(d) for d in top_density)
        h.append(f'<div class="callout-block"><span class="callout-kicker">{esc(L["callout_top_density_kicker"])}</span> '
                 f'{L["callout_top_density_text"].format(names=names)}</div>')
    else:
        h.append(f'<div class="callout-block"><span class="callout-kicker">{esc(L["callout_top_density_kicker"])}</span> '
                 f'{esc(L["callout_top_density_empty"])}</div>')
    # (b) top-bullets directions
    if top_bullets:
        names = "、".join(dom_link(d) for d in top_bullets) if lang == "zh-TW" \
            else ", ".join(dom_link(d) for d in top_bullets)
        h.append(f'<div class="callout-block"><span class="callout-kicker">{esc(L["callout_top_bullets_kicker"])}</span> '
                 f'{L["callout_top_bullets_text"].format(names=names)}</div>')
    else:
        h.append(f'<div class="callout-block"><span class="callout-kicker">{esc(L["callout_top_bullets_kicker"])}</span> '
                 f'{esc(L["callout_top_bullets_empty"])}</div>')
    # (c) coverage reminder
    cov_link = f'<a href="#coverage">{esc(L["coverage_link_text"])}</a>'
    h.append(f'<div class="callout-block"><span class="callout-kicker">{esc(L["callout_coverage_kicker"])}</span> '
             f'{L["callout_coverage_text"].format(blind_count=len(blind), link=cov_link)}</div>')
    h.append('</div>')
    h.append('</section>')

    h.append('<hr class="section-divider">')

    # 4. 涵蓋視覺 — two-tab pure-CSS control: 觀察熱度 (heatmap, default) / 工作向性 (radar).
    #    Pure-CSS radio+:checked pattern — NO JS (gate strips <script>, so a JS-driven toggle
    #    would vanish AND break; CSS in <style> is stripped before scan, so a CSS-only toggle
    #    is safe). Heatmap band logic (build_band_css/density_to_band/HEAT_RGB) is UNCHANGED.
    h.append('<section class="section" id="heatmap">')
    h.append(f'<div class="section-label">{esc(L["heatmap_label"])}</div>')
    h.append('<div class="tabs">')
    h.append('<input type="radio" name="covtab" id="tab-heat" class="tab-radio" checked>')
    h.append('<input type="radio" name="covtab" id="tab-radar" class="tab-radio">')
    h.append('<div class="tab-labels">')
    h.append(f'<label for="tab-heat" class="tab-label">{esc(L["tab_heat_label"])}</label>')
    h.append(f'<label for="tab-radar" class="tab-label">{esc(L["tab_radar_label"])}</label>')
    h.append('</div>')

    # panel-heat: existing heatmap body, unchanged, relocated inside the tab panel.
    h.append('<div class="tab-panel panel-heat">')
    h.append(f'<p class="muted">{L["heatmap_caption"]}</p>')
    # 8 tiles, fixed lifecycle order (DESIGN→CONTINUITY). Band index is INTERNAL (class only,
    # never rendered as text); the density number is never emitted here.
    h.append('<div class="heat-grid">')
    for d in DOMAINS:
        band = density_to_band(density[d], heat_bands)
        h.append(f'<div class="heat-tile band-{band}">{esc(labels[d])}</div>')
    h.append('</div>')
    # count-free frequency legend: end labels + B swatches (light -> dark), no numbers.
    h.append('<div class="heat-legend">')
    h.append(f'<span class="heat-legend-label">{esc(L["legend_low"])}</span>')
    for b in range(1, heat_bands + 1):
        h.append(f'<span class="heat-swatch band-{b}"></span>')
    h.append(f'<span class="heat-legend-label">{esc(L["legend_high"])}</span>')
    h.append('</div>')
    h.append('</div>')  # .panel-heat

    # panel-radar: pure hand-drawn SVG radar (工作向性), chart first then explanation.
    h.append('<div class="tab-panel panel-radar">')
    h.append(build_radar_svg(labels, present))
    h.append(f'<p class="muted">{esc(L["radar_caption"])}</p>')
    h.append('</div>')  # .panel-radar

    h.append('</div>')  # .tabs
    h.append('</section>')

    h.append('<hr class="section-divider">')

    # 5. 可以再往前一步的方向 (ALWAYS 8 cards)
    h.append('<section class="section">')
    h.append(f'<div class="section-label">{esc(L["growth_label"])}</div>')
    h.append(f'<h2 class="section-title">{esc(L["growth_title"])}</h2>')
    # 全部複製 — copies all 8 domains' forward directions as plain text (tool-agnostic).
    # Format: 【label】 then each bullet on its own line (filler included for empty domains),
    # a blank line between domains. Held in a hidden textarea (innerText of hidden nodes is
    # unreliable; textarea.value is not).
    all_blocks = []
    for d in DOMAINS:
        lines = [f"【{labels[d]}】"]
        lines.append(f"[{L['card_dir_sublabel']}]")
        lines.extend(bullets[d] if bullets[d] else [L["filler"]])
        if strengths[d]:
            lines.append(f"[{L['card_strength_sublabel']}]")
            lines.extend(strengths[d])
        all_blocks.append("\n".join(lines))
    all_text = "\n\n".join(all_blocks)
    h.append(f'<button type="button" class="btn-blue" onclick="copyAll()">{esc(L["copy_all_btn"])}</button>')
    h.append('<textarea id="all-dirs" readonly aria-hidden="true" '
             'style="position:absolute; left:-9999px; width:1px; height:1px;">'
             f'{esc(all_text)}</textarea>')
    h.append('<div class="card-grid">')
    for d in DOMAINS:
        h.append(f'<div class="card" id="domain-{esc(d)}">')
        h.append(f'<h3>{esc(labels[d])}</h3>')
        chip = L["density_chip"].format(present=present[d], total=total)
        h.append(f'<span class="density-chip">{esc(chip)}</span>')

        # (a) directions sub-block — always rendered (filler when empty).
        h.append(f'<div class="card-sublabel">{esc(L["card_dir_sublabel"])}</div>')
        if bullets[d]:
            render_capped_list(h, bullets[d], "", L["more_label"])
        else:
            h.append('<ul>')
            h.append(f'<li class="filler">{esc(L["filler"])}</li>')
            h.append('</ul>')

        # (b) strengths sub-block — ONLY when non-empty (no filler for an absent strength).
        if strengths[d]:
            h.append(f'<div class="card-sublabel">{esc(L["card_strength_sublabel"])}</div>')
            render_capped_list(h, strengths[d], "", L["more_label"])

        # hidden per-card textarea holding the FULL directions+strengths text, so the
        # per-card copy button doesn't lose items hidden behind a collapsed <details>.
        copy_lines = [f"[{L['card_dir_sublabel']}]"]
        copy_lines.extend(bullets[d] if bullets[d] else [L["filler"]])
        if strengths[d]:
            copy_lines.append(f"[{L['card_strength_sublabel']}]")
            copy_lines.extend(strengths[d])
        copy_text = "\n".join(copy_lines)
        copy_id = f"copy-{esc(d)}"
        h.append(f'<textarea id="{copy_id}" readonly aria-hidden="true" '
                 'style="position:absolute; left:-9999px; width:1px; height:1px;">'
                 f'{esc(copy_text)}</textarea>')
        h.append(f'<button type="button" class="btn-blue" onclick="copyField(\'{copy_id}\')">{esc(L["copy_btn"])}</button>')
        h.append('</div>')
    h.append('</div>')
    h.append('</section>')

    # 6. 幾個值得留意的使用習慣 (CONDITIONAL)
    if biases:
        h.append('<hr class="section-divider">')
        h.append('<section class="section">')
        h.append(f'<div class="section-label">{esc(L["habits_label"])}</div>')
        h.append(f'<h2 class="section-title">{esc(L["habits_title"])}</h2>')
        h.append(f'<p class="muted">{esc(L["habits_intro"])}</p>')
        self_correct = [bf for bf in biases if bf.get("self_correctable")]
        watch = [bf for bf in biases if not bf.get("self_correctable")]

        def habit_bucket(title, items):
            if not items:
                return
            h.append('<div class="habit-bucket">')
            h.append(f'<h3>{esc(title)}</h3>')
            lines = []
            for bf in items:
                bias = fullwidth_cjk(bf.get("bias", ""))
                observed = fullwidth_cjk(bf.get("observed", ""))
                lines.append(f'<strong>{esc(bias)}</strong> — {esc(observed)}')
            head, tail = lines[:5], lines[5:]
            h.append('<ul>')
            for li in head:
                h.append(f'<li>{li}</li>')
            h.append('</ul>')
            if tail:
                h.append(f'<details class="more"><summary>{esc(L["more_label"].format(n=len(tail)))}</summary>')
                h.append('<ul>')
                for li in tail:
                    h.append(f'<li>{li}</li>')
                h.append('</ul></details>')
            h.append('</div>')

        habit_bucket(L["bucket_self_correct"], self_correct)
        habit_bucket(L["bucket_watch"], watch)
        h.append('</section>')

    h.append('<hr class="section-divider">')

    # 7. 涵蓋率
    h.append('<section class="section" id="coverage">')
    h.append(f'<div class="section-label">{esc(L["coverage_label"])}</div>')
    h.append(f'<h2 class="section-title">{esc(L["coverage_title"])}</h2>')
    h.append(f'<p>{L["coverage_sentence1"].format(scanned=esc(sessions_scanned), extracted=esc(n))}</p>')
    h.append(f'<p>{L["coverage_sentence2"].format(scope=esc(", ".join(scope) if scope else L["val_none"]))}</p>')
    if blind:
        h.append(f'<p>{L["coverage_sentence3_blind"].format(blind=esc(", ".join(blind)))}</p>')
    h.append(f'<p>{L["coverage_disclaimer"]}</p>')
    h.append('</section>')

    # 8. FOOTER
    h.append('<footer class="footer">')
    h.append(f'<p class="foot-strong">{esc(L["footer_date"].format(date=render_date))}</p>')
    h.append(f'<p>{esc(L["footer_local"])}</p>')
    h.append(f'<p>{esc(L["footer_colorline"])}</p>')
    h.append('</footer>')

    h.append('</div>')  # .page

    js = build_js()

    parts = []
    parts.append(f'<html lang="{esc(L["html_lang"])}">')
    parts.append('<meta charset="utf-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append(f'<title>{esc(L["title"])}</title>')
    # base CSS + the per-band heat color rules generated for this --heat-bands value.
    parts.append(f'<style>\n{CSS}\n{build_band_css(heat_bands)}\n</style>')
    parts.append("\n".join(h))
    # the ONLY script: the inline clipboard copy-helper (no vendored library).
    parts.append(f'<script>\n{js}\n</script>')
    parts.append('</html>')
    return "\n".join(parts) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Phase 4 person-facing insight HTML (no score).")
    ap.add_argument("--in", dest="inp",
                    default=os.path.join(ROOT, "raw-sessions", "capability-signals.json"))
    ap.add_argument("--index",
                    default=os.path.join(ROOT, "worktemp", "session-index.json"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--project", default=None)
    ap.add_argument("--source-scope", default="claude-code-cli")
    ap.add_argument("--blind-spots", default="codex-cli,chatgpt,claude-desktop")
    ap.add_argument("--heat-bands", type=int, choices=(5, 8), default=5,
                    help="number of heat bands B (default 5); band index stays INTERNAL.")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--lang", default="zh-TW",
                    help="report chrome locale: zh-TW (default) or en. Observation content is "
                         "never translated — it renders in whatever language it was extracted in.")
    args = ap.parse_args()

    if args.lang not in LOCALES:
        die(f"unsupported --lang '{args.lang}'; supported locales: {', '.join(sorted(LOCALES))}")
    L = LOCALES[args.lang]

    # (2) signals: MISSING -> die; empty is OK.
    if not os.path.isfile(args.inp):
        die(f"input signals not found: {args.inp}")
    with open(args.inp, encoding="utf-8") as fh:
        signals = json.load(fh)
    if not isinstance(signals, list):
        signals = [signals]
    n = len(signals)

    # (3) index: absent -> {} (span '—', project 'all').
    index = {}
    if os.path.isfile(args.index):
        with open(args.index, encoding="utf-8") as fh:
            index = json.load(fh) or {}
    project = args.project or (index.get("filter", {}) or {}).get("project") or "all"
    if project in (None, "", "all"):
        project = "all"
    sessions_scanned = index.get("sessions_in_index") or n
    idx_sessions = index.get("sessions") or []
    firsts = [s.get("first_ts") for s in idx_sessions if s.get("first_ts")]
    lasts = [s.get("last_ts") for s in idx_sessions if s.get("last_ts")]
    if firsts and lasts:
        span = f"{min(firsts)[:10]} → {max(lasts)[:10]}"
    else:
        span = L["val_dash"]

    # (4) out path — non-default lang appends the locale so versions coexist.
    if args.out:
        out = args.out
    else:
        suffix = "" if args.lang == "zh-TW" else f"-{args.lang}"
        out = os.path.join(ROOT, "output", f"insight-{args.date}-{project}{suffix}.html")

    # (6) labels + aggregation (reused from render_growth for zh-TW; literal dict for en).
    labels = load_labels() if args.lang == "zh-TW" else dict(EN_LABELS)
    per_dom, biases = collect(signals)

    # (7) density.
    density, present = compute_density(signals)

    scope = [t.strip() for t in args.source_scope.split(",") if t.strip()]
    blind = [t.strip() for t in args.blind_spots.split(",") if t.strip()]

    doc = build_html(L, args.lang, signals, index, labels, per_dom, biases, density, present,
                     scope, blind, project, sessions_scanned, span, args.heat_bands, args.date)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(doc)

    domains_observed = sum(1 for d in DOMAINS if density[d] > 0)
    print(f"ok: insight report written to {out}")
    print(f"ok: {len(DOMAINS)} domain cards rendered, {domains_observed} observed, "
          f"{len(biases)} habit note(s), coverage={n} signal(s) "
          f"(sessions_scanned={sessions_scanned}, lower-bound, scope={scope}, lang={args.lang})")
    print("next: run scripts/check-visibility-seam.sh (c) — must find NO score/rung/tier word.")


if __name__ == "__main__":
    main()
