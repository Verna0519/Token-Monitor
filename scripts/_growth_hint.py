#!/usr/bin/env python3
"""
_growth_hint.py — shared growth_hint normalization (de-id audit F3, operator ruling #9).

A growth_hint often reads "<retrospective praise>；<forward advice>". operator ruling #9 / RL4-ii require the
personal layer to be PURE forward-looking — no retrospective assessment tone, even as praise. The
root fix is to generate pure-forward hints at extraction time (skill prompt updated); this is the
mechanical BACKSTOP that both output paths share so neither can ship a retrospective clause:

  - render_growth.py (Phase 3, personal-facing note) — the person must never read praise-of-past.
  - (build_digest.py consumed it too until the digest pipeline was retired 2026-07-15)

Previously forward_only() lived only in render_growth.py, so the upward DIGEST still carried
retrospective hints (the committed digest showed "已經很扎實 / 抓對了 / 很紮實"). Sharing it here
closes that gap (DRY) — one normalizer, both surfaces.
"""

import re

# Forward-pivot markers: a hint that starts with one of these is already forward-looking.
_FORWARD_START = re.compile(r"^\s*(?:可以|試著|試試|之後|下次|未來|建議|不妨|或許可以)")
# Cut everything up to and including the first clause separator that is followed by a forward pivot.
_PIVOT_RE = re.compile(
    r".*?(?:；|;|,|，)\s*(?=(?:可以|試著|試試|之後|下次|未來|建議|不妨|或許可以))"
)


def forward_only(hint):
    """Strip a leading retrospective-praise clause; keep the forward-looking advice (operator ruling #9).

    - If the hint already starts with a forward pivot (可以/試著/…), return it as-is.
    - Else if a forward clause follows a separator, drop everything before it.
    - Else return the hint unchanged (never drop real advice — a false strip is worse than a mild
      retrospective tone; the extraction-time root fix is the primary defense).
    """
    if not hint:
        return hint
    if _FORWARD_START.match(hint):
        return hint.strip()
    m = _PIVOT_RE.match(hint)
    if m:
        rest = hint[m.end():].strip()
        if rest:
            return rest
    return hint.strip()
