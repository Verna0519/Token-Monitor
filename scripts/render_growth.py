#!/usr/bin/env python3
"""
render_growth.py — Phase 3: personal-facing growth output (NO SCORE).

Turns the per-session capability signals (raw-sessions/capability-signals.json) into a
forward-looking, encouraging growth note for the PERSON. Hard RL4-ii constraints:

  - NEVER surfaces signal_tier / rung / any score word. Only growth_hint + an abstract self-view.
  - Framed as forward-looking growth/evolution advice, NOT a self-assessment or self-ranking
    (operator ruling #9 reframe): "往哪走", not "你現在幾分".
  - Shows source_scope + lower_bound honesty (operator ruling #10 / RL4-iv): "僅掃到本機 X, 別工具未計入 —
    沒掃到不等於能力低."

Output = a Traditional-Chinese markdown note in output/ (PRIVATE, gitignored). It must pass
check-visibility-seam.sh (c) (no score/rung/tier vocabulary).

Usage:
  render_growth.py [--in raw-sessions/capability-signals.json] [--out output/growth-note.md]
                   [--source-scope claude-code-cli] [--blind-spots codex-cli,chatgpt,claude-desktop]
"""

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
from _growth_hint import forward_only  # noqa: E402  (shared F3 backstop, both output paths)

# The personal layer coaches at EIGHT domains (the person sees all 8; the 8→6 fold is a dept-side
# concern for upward artifacts, never here). Order = the AI-usage lifecycle:
# decide→select→build→contextualize→iterate→verify→govern→persist.
DOMAINS = ["DESIGN", "FRAMEWORK-SELECTION", "CODING", "TUNING",
           "CONTEXT-ENGINEERING", "EVAL", "ADVISORY", "CONTINUITY"]
# Domain labels are loaded from personal-domains.yaml at runtime; fall back to these if absent.
DOMAIN_LABELS_FALLBACK = {
    "DESIGN": "系統/流程設計",
    "FRAMEWORK-SELECTION": "框架/基材選擇",
    "CODING": "實作/整合",
    "TUNING": "方法化調校/迭代",
    "CONTEXT-ENGINEERING": "脈絡工程",
    "EVAL": "評估/驗證",
    "ADVISORY": "顧問/人機界線",
    "CONTINUITY": "跨界狀態承接/交接",
}


def die(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def load_labels():
    path = os.path.join(ROOT, "config", "personal-domains.yaml")
    labels = dict(DOMAIN_LABELS_FALLBACK)
    try:
        import yaml
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        for dom, spec in (data.get("domains") or {}).items():
            if dom in labels and isinstance(spec, dict) and spec.get("label"):
                labels[dom] = spec["label"]
    except Exception:
        pass  # fall back to the built-in labels — non-fatal (this is personal-facing prose)
    return labels


def collect(sessions):
    """Aggregate presence + growth hints per domain, and bias hints. NO tier is ever read out."""
    per_dom = {d: {"present": False, "hints": [], "strengths": []} for d in DOMAINS}
    for s in sessions:
        for d in DOMAINS:
            sig = (s.get("domain_signals") or {}).get(d) or {}
            if sig.get("present"):
                per_dom[d]["present"] = True
                h = sig.get("growth_hint")
                if h and h not in per_dom[d]["hints"]:
                    per_dom[d]["hints"].append(h)
                st = sig.get("strength")
                if st and st not in per_dom[d]["strengths"]:
                    per_dom[d]["strengths"].append(st)
    biases = []
    seen = set()
    for s in sessions:
        for bf in (s.get("bias_flags") or []):
            k = bf.get("bias")
            if k and k not in seen:
                seen.add(k)
                biases.append(bf)
    return per_dom, biases


def main():
    ap = argparse.ArgumentParser(description="Phase 3 personal-facing growth note (no score).")
    ap.add_argument("--in", dest="inp",
                    default=os.path.join(ROOT, "raw-sessions", "capability-signals.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "output", "growth-note.md"))
    ap.add_argument("--source-scope", default="claude-code-cli")
    ap.add_argument("--blind-spots", default="codex-cli,chatgpt,claude-desktop")
    args = ap.parse_args()

    if not os.path.isfile(args.inp):
        die(f"input signals not found: {args.inp}")
    with open(args.inp, encoding="utf-8") as fh:
        sessions = json.load(fh)
    if not isinstance(sessions, list):
        sessions = [sessions]

    labels = load_labels()
    per_dom, biases = collect(sessions)

    scope = [t.strip() for t in args.source_scope.split(",") if t.strip()]
    blind = [t.strip() for t in args.blind_spots.split(",") if t.strip()]

    lines = []
    lines.append("# 你的 AI 使用成長筆記")
    lines.append("")
    # NOTE: intentionally avoids the words 分數/評分/排名/rung/tier even in a disclaimer — per
    # operator ruling #9, the personal layer should not invoke the assessment frame at all (not even to deny
    # it). check-visibility-seam.sh (c) is strict (no negation carve-out) and enforces exactly this.
    lines.append("> 這份筆記只給你自己看,重點是**接下來可以往哪裡走**。下面每一條都是"
                 "「可以再試試」的方向,是往前看的成長建議,不是回頭看的檢討。")
    lines.append("")

    # --- 成長方向(僅 growth_hint,絕不出現 tier/score) ---
    # F4 (de-id audit 2026-07-09): render ALL SIX domain sections regardless of presence, so the
    #   presence-set (which domains had signals) does not leak — a reader must not be able to infer
    #   "all six present" from which sections appear. A domain with no signal shows a neutral prompt.
    # F3 (de-id audit 2026-07-09): strip a LEADING retrospective-praise clause from each hint so the
    #   note reads as forward-looking growth advice, not a retrospective assessment (operator ruling #9). The
    #   deeper fix is to regenerate hints pure-forward at extraction time (Phase 1b, skill prompt
    #   already updated); this render-time strip is the mechanical backstop.
    lines.append("## 可以再往前一步的方向")
    lines.append("")
    for d in DOMAINS:
        lines.append(f"### {labels[d]}")
        hints = [forward_only(h) for h in per_dom[d]["hints"]]
        hints = [h for h in hints if h]
        if hints:
            for h in hints:
                lines.append(f"- {h}")
        else:
            lines.append("- _這次掃到的範圍裡還沒有這方面的具體方向,之後累積更多對話後可以再看。_")
        lines.append("")

    # --- 自我覺察(BIAS,溫和措辭) ---
    if biases:
        lines.append("## 幾個值得留意的使用習慣")
        lines.append("")
        lines.append("_這些是從你的對話裡觀察到、可以自己調整的小傾向,不是缺點清單。_")
        lines.append("")
        for bf in biases:
            note = "(通常你自己會修正回來)" if bf.get("self_correctable") else ""
            lines.append(f"- **{bf.get('bias','')}** — {bf.get('observed','')} {note}".rstrip())
        lines.append("")

    # --- 涵蓋率誠實(RL4-iv / operator ruling #10) ---
    lines.append("## 這份筆記看到了多少(涵蓋率)")
    lines.append("")
    lines.append(f"- 這次掃描了 **{len(sessions)}** 個本機對話 session。")
    lines.append(f"- **掃到的工具**:{', '.join(scope) if scope else '(無)'}。")
    if blind:
        lines.append(f"- **沒掃到的工具**:{', '.join(blind)} — 這些目前讀不到(server 端或尚未接入)。")
    lines.append("- ⚠️ **這是一個下界估計**:沒掃到的地方**不代表你在那裡能力低**,只代表這份筆記還沒看到那部分。")
    lines.append("")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    n_with_hints = sum(1 for d in DOMAINS if per_dom[d]["present"] and per_dom[d]["hints"])
    print(f"ok: personal-facing growth note written to {args.out}")
    print(f"ok: {len(DOMAINS)} domain sections rendered ({n_with_hints} with directions), "
          f"{len(biases)} habit note(s), coverage={len(sessions)} session(s) "
          f"(lower-bound, scope={scope})")
    print(f"next: run scripts/check-visibility-seam.sh (c) — must find NO score/rung/tier word.")


if __name__ == "__main__":
    main()
