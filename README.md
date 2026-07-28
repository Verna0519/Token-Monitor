# aocc-personal-ai-coach

> 中文版在前,English version below（見 [English](#english)）。

三層 AI 能力教練設計（個人 / 部門 / 中心）中的**個人層**。這是一個單人、獨立的 Claude Code
agent,跑在**你自己的機器上**:掃描你自己的 AI 對話記錄,萃取抽象的能力訊號,產出兩份成果——

1. **個人成長筆記**——前瞻式的成長建議（繁體中文）,不帶任何評分字彙,並誠實聲明掃到了什麼、
   沒掃到什麼;
2. **能力座標（COORDINATE）**——你在部門層「區間定位學習地圖」上的位置:8 條能力軸,每軸一個
   0–3 級。

所有帶身分的資料都留在你的機器上。**唯一**會離開的檔案是通過形狀檢查的座標,而且由人手動攜帶
——三層是實體分離的儲存庫,執行期彼此永不通訊。

## 它量什麼、不量什麼

這 8 條軸量的是**你如何操作 AI**,不是你的領域或專業能力:

`DESIGN · FRAMEWORK-SELECTION · CODING · TUNING · CONTEXT-ENGINEERING · EVAL · ADVISORY · CONTINUITY`

一個級別（0–3）是**地圖上的位置,不是成績**:它本身沒有強弱意義,只有相對於部門地圖上某個專案的
能力區間時才有意義——所以座標無法被排名。一個區間吻合只主張你的「AI 操作能力」達到該專案的逐軸
帶寬;它**永遠不**主張你具備該專案的專業資格（那由別處、由人判斷）。因為這些軸與部門無關,座標
可跨部門攜帶。

## 運作方式

```
scan_sessions.py            對話索引（僅 metadata——無內容）
        ↓
extract-capability skill    逐 session 訊號:8 領域 ×{是否出現、證據強度、抽象引用}
        ↓                   （僅抽象行為/計次——絕不含原始逐字內容）
aggregate_signals.py        容錯 fence、schema 驗證、fail-closed 的合併
        ↓
        ├── render_growth.py          → output/growth-note.md        （個人面向,無評分）
        ├── render_insight.py         → output/insight-<date>-<project|all>.html（自包含,無評分）
        ├── coverage_report.py        → 哪些軸還缺證據（下一步的萃取目標）
        └── emit-coordinate workflow  → 每軸一個 agent,以該軸的 0–3 rubric 為依據;
            + emit_coordinate.py        當證據無法定位某軸時 level = null——
                                        缺證據絕不當成 level 0
```

emitter 執行**嚴格契約**（版本 `0.1`）:全部 8 軸、整數 0–3。若任何一軸無法從證據定位,它會拒絕
產出,並告訴你該去萃取哪些 session——證據不足的答案是*補更多證據*,絕不是給預設值或放寬契約。

### 洞察報告（HTML）

`render_insight.py` 在成長筆記之外,再產出第二份個人面向成果:一份自包含的單檔 HTML 報告
（BMW 風格、無外部資源、無 JS 函式庫）,位於 `output/insight-<date>-<project|all>.html`。它借用了
claude-code `/insights` 指令的分析手法——一個錨定的重點摘要區塊,以及每個領域**同時**呈現
前瞻方向卡片（「可以再往前一步」）**與**前瞻框架的優點（「值得持續保持的做法」）,所以報告永遠
不是只有批評的清單。過長的清單會收折在原生 `<details>`「更多」控制項後面（最多顯示 5 項,無 JS）,
每張卡片有複製 / 全部複製按鈕,習慣筆記分成兩個桶,最後以涵蓋率誠實區段收尾。所有優點都維持前瞻
框架、不帶評分字彙;中文報告內文全程使用全形標點。

涵蓋率視圖是一個**雙分頁**控制項:

- **觀察熱度**（預設）——一個純 CSS 的 8 格熱圖,顏色深淺反映每個領域被**觀察**到的頻率
  （證據涵蓋率）,分桶成熱度帶（`--heat-bands {5,8}`,預設 5）,刻意不顯示任何數字,採綠色階
  ——這是涵蓋率地圖,不是能力量測。
- **工作向性**——一個手繪的純 SVG 8 角雷達（無 Chart.js / 無外部函式庫）,頂點是每軸的觀察
  **計次**統計（半徑依最忙的軸縮放;每個頂點標上原始次數）,採淺橘色。它回答「這次的對話 prompt
  落在哪些工作面向」——是頻次統計,明確**不是**能力評分（其說明文字會指引讀者去看觀察熱度）。

它能以 `--lang zh-TW`（預設）或 `en` 渲染;只有報告框架被在地化（觀察內容維持它被萃取時的語言,
不翻譯）,非預設語系會加上 `-<lang>` 檔名後綴讓兩版並存——`extract-capability` skill 會問操作者
一次是否要同時產出另一語系。

## 隱私與可見性模型

- **本機優先**:原始記錄、萃取訊號、成長筆記、逐軸理由（`coordinate-basis-*`）永不離開這台機器。
- **上傳檔以構造保證最小**:恰好是 `{format, version, submission_id, period, position}`——無證據
  文字、無身分欄位。每次產出鑄一個全新的不透明 `sub-` id。
- **機械式 gate,而非口頭承諾**（退出碼即裁決）:
  - `scripts/check-visibility-seam.sh`——私有 bucket 永不被 git 追蹤;`handoff/` 只接受通過形狀
    檢查的 `coordinate-*.json`;個人面向輸出（含 `output/**/*.html`,掃描前先剝除 script/style）
    不得有 score/rung/tier 字彙;憑證存放硬性排除。
  - `scripts/validate-selfcontainment.sh`——儲存庫維持獨立（執行期不耦合任何其他 agent/層,無寫死
    的機器路徑）。

## 設定

```bash
python3 scripts/preflight.py                # 冷啟動檢查（唯讀）;告訴你缺什麼
cp config/path-mappings.yaml config/path-mappings.filled.yaml
$EDITOR config/path-mappings.filled.yaml    # 設定 CLAUDE_PROJECTS_ROOT（完整路徑,家目錄完整拼出）
cp .env.template .env                       # 不需要 API key
bash scripts/validate-selfcontainment.sh    # → exit 0
bash scripts/check-visibility-seam.sh       # → exit 0
```

在新的或未驗證的機器上,先跑 `python3 scripts/preflight.py`——一個唯讀、可攜、純 stdlib 的檢查,
會回報每個設定缺口（以及已知的跨機器遷移問題）,在設定完成前以非零退出;`python3
scripts/onboard.py` 是修復私有設定檔的機械式、冪等工具。兩者都不會動到被追蹤的模板。詳見
`planning/COLD-START.md`。

接著,在互動式 Claude Code session 中:對你的 session 跑 `extract-capability` skill,用
`python3 scripts/coverage_report.py` 檢查,跑 `emit-coordinate` workflow,最後以
`python3 scripts/emit_coordinate.py --from-workflow <result.json>` 收尾。

## 文件

- `CLAUDE.md`——憲章:身分、紅線（RL1–RL4）、管線、契約。
- `INDEX.md`——儲存庫地圖 + 每條路徑的 shareable/private 分類。
- `decisions/0001-standalone-l3-and-visibility-seam.md`——架構決策紀錄。
- `planning/BUILD-PLAN.md`——as-built 歷史 + 前瞻計畫。
- `planning/COLD-START.md`——冷啟動 / 跨機器設定:唯讀 preflight + 操作者驅動的 onboard 修復工具,
  以及原生 Windows 的情況。
- 座標契約的**真實來源**位於部門儲存庫（在那裡的 `planning/coordinate-contract.md`）;本儲存庫
  以機械方式鏡射其形狀。

## 狀態

試點階段。座標模型 v1（2026-07-15）:萃取管線、8 領域 0–3 rubric、成長筆記、洞察報告、座標
emitter 都已建置並通過 gate 測試;先前的 digest 管線已退役（可經 git 歷史復原）。第一個完整的
8/8 軸座標已從真實的多 session 執行中產出（攜帶到部門 inbox 是操作者的步驟）。已為新機器備好可攜的
冷啟動 preflight + onboard 流程。agent 產出的一切都是 PROPOSED——不自我批准;批准只由操作者親手
完成。即時狀態:`config/STATE.md`（私有,每台機器各自）。

---

<a name="english"></a>

# aocc-personal-ai-coach (English)

The **personal layer** of a three-layer AI-capability coaching design (personal / department /
center). A single-user, standalone Claude Code agent that runs on **your own machine**: it scans
your own AI-session transcripts, extracts abstract capability signals, and produces two artifacts —

1. a **personal growth note** — forward-looking growth suggestions (zh-TW), with no score
   vocabulary and an honest statement of what was and was not scanned;
2. a **capability COORDINATE** — your position on the department layer's zone-positioning
   *learning map*: one 0–3 level per axis across 8 capability axes.

Everything identity-bearing stays on your machine. The **only** file that ever leaves is the
shape-checked coordinate, and a human carries it by hand — the three layers are physically
separate repositories that never talk at runtime.

## What it measures — and what it does not

The 8 axes measure **how you operate AI**, not your domain or professional expertise:

`DESIGN · FRAMEWORK-SELECTION · CODING · TUNING · CONTEXT-ENGINEERING · EVAL · ADVISORY · CONTINUITY`

A level (0–3) is a **position on a map, not a grade**: it has no strong/weak meaning on its own
and gains meaning only relative to a project's capability zone on the department map — so
coordinates cannot be ranked. A zone fit claims only that your AI-operation capability meets that
project's per-axis band; it **never** claims you are professionally qualified for the project
(that is judged elsewhere, by humans). Because the axes are department-agnostic, a coordinate is
portable across departments.

## How it works

```
scan_sessions.py            session index (metadata only — no content)
        ↓
extract-capability skill    per-session signals: 8 domains × {present, evidence tier, abstract refs}
        ↓                   (abstract behaviors/counts only — never raw transcript text)
aggregate_signals.py        fence-tolerant, schema-validated, fail-closed merge
        ↓
        ├── render_growth.py          → output/growth-note.md        (personal-facing, no scores)
        ├── render_insight.py         → output/insight-<date>-<project|all>.html (self-contained, no scores)
        ├── coverage_report.py        → which axes still lack evidence (the extraction targets)
        └── emit-coordinate workflow  → one agent per axis, grounded in that axis's 0–3 rubric;
            + emit_coordinate.py        level = null when evidence cannot place an axis —
                                        absence of evidence is NEVER treated as level 0
```

The emitter enforces a **strict contract** (version `0.1`): all 8 axes, integer 0–3. If any axis
cannot be placed from evidence, it refuses to emit and tells you which sessions to go extract —
the answer to thin evidence is *more evidence*, never a default value or a looser contract.

### Insight report (HTML)

`render_insight.py` renders a second personal-facing artifact alongside the growth note: a
self-contained single-file HTML report (BMW-inspired styling, no external resources, no JS
library) at `output/insight-<date>-<project|all>.html`. It adapts analysis patterns from
claude-code's `/insights` command — an anchored key-takeaways callout and, per domain, BOTH
forward-direction cards ("directions to push further") AND forward-framed strengths ("worth keeping
up"), so the report is never a critique-only list. Long lists collapse behind a native
`<details>` "更多" control (at most 5 items shown, no JS), each card has copy / copy-all buttons,
habit notes sit in two buckets, and a coverage-honesty section closes it out. All strengths stay
forward-framed with no score vocabulary; zh-TW report text uses full-width punctuation throughout.

The coverage view is a **two-tab** control:

- **觀察熱度** (default) — a pure-CSS 8-tile heatmap whose color intensity reflects how often each
  domain was OBSERVED (evidence coverage), bucketed into heat bands (`--heat-bands {5,8}`, default
  5) with deliberately no visible numbers, in a green ramp — a coverage map, never an ability
  measure.
- **工作向性** — a hand-drawn pure-SVG 8-axis radar (no Chart.js / no external library) whose
  vertices are a per-axis observation-COUNT tally (radius scaled to the busiest axis; each vertex
  labelled with its raw count), in light orange. It answers "which kinds of work did this window's
  prompts fall into" — a frequency tally, explicitly NOT an ability score (its caption points the
  reader to 觀察熱度 for that).

It renders `--lang zh-TW` (default) or `en`; only the report chrome is localized (observation
content stays in whatever language it was extracted in), and a non-default locale gets a `-<lang>`
filename suffix so both can coexist — the `extract-capability` skill asks the operator once whether
to also render the other locale.

## Privacy & visibility model

- **Local-first**: raw transcripts, extracted signals, the growth note, and the per-axis
  rationale (`coordinate-basis-*`) never leave this machine.
- **The upload is minimal by construction**: exactly
  `{format, version, submission_id, period, position}` — no evidence text, no identity fields.
  A fresh opaque `sub-` id is minted per emission.
- **Mechanical gates, not promises** (exit code is the verdict):
  - `scripts/check-visibility-seam.sh` — private buckets are never git-tracked; `handoff/`
    accepts ONLY shape-checked `coordinate-*.json`; no score/rung/tier vocabulary in
    personal-facing output, including `output/**/*.html` (script/style stripped before the scan);
    credential stores are hard-excluded.
  - `scripts/validate-selfcontainment.sh` — the repo stays standalone (no runtime coupling to
    any other agent/layer, no machine-baked paths).

## Setup

```bash
python3 scripts/preflight.py                # cold-start check (read-only); tells you what is missing
cp config/path-mappings.yaml config/path-mappings.filled.yaml
$EDITOR config/path-mappings.filled.yaml    # set CLAUDE_PROJECTS_ROOT (full path, home spelled out)
cp .env.template .env                       # no API key needed
bash scripts/validate-selfcontainment.sh    # → exit 0
bash scripts/check-visibility-seam.sh       # → exit 0
```

On a fresh or unverified machine, start with `python3 scripts/preflight.py` — a read-only,
portable, pure-stdlib check that reports every setup gap (and known cross-machine migration
issues) and exits non-zero until setup is complete; `python3 scripts/onboard.py` is the mechanical,
idempotent fixer for the private setup files. Neither touches a tracked template. See
`planning/COLD-START.md`.

Then, in an interactive Claude Code session: run the `extract-capability` skill over your
sessions, check `python3 scripts/coverage_report.py`, run the `emit-coordinate` workflow, and
finish with `python3 scripts/emit_coordinate.py --from-workflow <result.json>`.

## Docs

- `CLAUDE.md` — the constitution: identity, red lines (RL1–RL4), pipeline, contract.
- `INDEX.md` — repo map + shareable/private classification of every path.
- `decisions/0001-standalone-l3-and-visibility-seam.md` — the architecture decision record.
- `planning/BUILD-PLAN.md` — as-built history + forward plan.
- `planning/COLD-START.md` — cold-start / cross-machine setup: the read-only preflight + the
  operator-driven onboard fixer, plus the native-Windows story.
- The coordinate contract's **source of truth** lives in the department repo
  (`planning/coordinate-contract.md` there); this repo mirrors its shape mechanically.

## Status

Pilot. Coordinate model v1 (2026-07-15): extraction pipeline, 8-domain 0–3 rubric, growth note,
insight report, and the coordinate emitter are built and gate-tested; the earlier digest pipeline
is retired (recoverable via git history). The first full 8/8-axis coordinate has been emitted from
a real multi-session run (hand-carry to the department inbox is the operator's step). A portable
cold-start preflight + onboard flow is in place for new machines. Everything the agent produces is
PROPOSED — nothing self-ratifies; ratification is the operator's hand only. Live state:
`config/STATE.md` (private, per machine).
