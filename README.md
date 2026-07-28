# Token Monitor

> 本機、離線（air-gapped）的 Claude Code **token / 花費監控**工具。純 stdlib Python + PowerShell，
> **零連外**，所有輸出只寫進 `worktemp/`（私有、gitignored）。給需要看「哪個 skill / 專案 / 對話
> 花了多少 token」的人使用，可打包分享，每個人填自己的資料。

> 中文在前，English summary at the bottom。

---

## 這是什麼

打開一個自包含的 HTML 儀表板，回答一個問題：**「誰花了什麼」** —— 從你本機的 Claude Code
對話記錄（`~/.claude/projects/**/*.jsonl`）統計 token 用量，依 **對話 / 專案 / skill** 分組，畫出
每日趨勢，並對照你 Claude Usage 頁上的 **$ 花費額度 / credit**。

- **本機分析**（token）：每次開啟／重新產生時，重讀你當下的對話記錄 —— 一定是最新的。
- **$ 與 credit**：預設由你手動填在 `config/usage-limits.json`（對照 Claude Settings > Usage 頁）。
  可選：設定 Analytics API key 後自動連外抓真實 $（見下方「連外抓 $」）。

---

## ⚠️ 當前狀態（一定要先讀）

| 區塊 | 資料來源 | 會自動更新嗎 |
|------|----------|--------------|
| Token usage（對話 / 專案 / skill / 每日曲線 / 近期列表） | 本機對話記錄，離線讀取 | ✅ 每次 `tokens` 或雙擊 `open-monitor.cmd` 都重抓當下資料 |
| Your usage limits（$ 花費額度） | `config/usage-limits.json`，**手動填** | ❌ 你改 config 才會變（除非開連外抓 $） |
| Claude Code and Cowork credit | `config/usage-limits.json`，**手動填** | ❌ 同上 |
| Daily spend by product（真實每日 $） | Claude Enterprise Analytics API，**連外** | 只有設了 `ANALYTICS_API_KEY` 才有 |

**關於 token 百分比（重要）：** 訂閱方案的真實上限是 **$ 花費額度**（例如 Usage 頁的
「Spend limit $150／100% used」），**Anthropic 沒有官方的 token 配額可抓**。所以儀表板裡
token 的 `%` 是對照一個**你自訂的參考值** `token_limit`，只是為了讓進度條有意義：

- 目前的 `token_limit` 是把 **$150 月額度換算成 token**：用「你實際花 ~$150／月、實際用掉多少
  token」的**實際費率**（快取重＋企業/credit 折扣後，約 $0.08／百萬 token）回推，得 **≈1,830,000,000
  （18.3 億）／月**。儀表板上的 `(1,830,000,000)` 數字會標出來，不會誤導。
  - 為什麼不用 Anthropic 清單價換算？因為你光 7 天的 token 量在清單價就要約 $278 > 月上限 $150，
    代表你走的是折扣／credit 價；用清單價換算（$150≈2.3 億）會**低估**你的真實額度、讓錶爆滿。
  - 這是個月額度；視窗預設 7 天，所以錶約顯示「這週用掉月額度的 ~1/4」。想看整月 → `tokens -Month`。
- **想改成別的數字**：編輯 `config/usage-limits.json` 的 `"token_limit"`，下次開啟就套用
  （設 `0` = 改回「佔本視窗總量的百分比」）。
- `$` 那兩塊（Spend limit / credit）請照你 Claude Usage 頁的數字手填；**連外抓真實 $ 需要
  Analytics API key，只有企業版 Primary Owner 能產**（見最後一節）。

### 量表顏色（gauge）

所有量表（Spend limit、credit、token）依使用百分比分四段上色：

| 顏色 | 區間 | 意思 |
|------|------|------|
| 🟩 綠 | `< 50%` | 充裕 |
| 🟨 黃 | `50–75%` | 過半、留意 |
| 🟧 橙 | `75–90%` | 接近上限 |
| 🟥 紅 | `≥ 90%` | 幾乎/已滿 |

門檻與色值集中在 `scripts/render_dashboard.py`：門檻在 `statusColor()`，色值在 CSS 變數
`--good / --warn / --high / --critical`，要微調改這兩處即可。

### Token 區塊用「錢」表示

「Token usage · who spent what」每一列除了 token 數，也會顯示 **≈$ 估算花費**：以你的
**$ 花費額度 ÷ `token_limit`** 當每-token 單價（即你的實際費率，約 $0.08／百萬 token）× 該列 token 數。
這是**估算**（`≈`），只有在 config 同時有 `usage_limit.limit` 與 `token_limit` 時才顯示；否則退回純 token 數。

### 四種分組怎麼看（who spent what）

「Token usage」把用量用四種方式切開，每列都顯示 tokens、佔比 %、≈$ 估算：

| 分組 | 依什麼歸戶 | 用途 | 是否含 nested |
|------|-----------|------|:---:|
| **By conversation** | 對話 (sessionId) | 哪一次 chat 花最多 | 否 |
| **By project** | 工作目錄 (cwd) | 哪個專案花最多 | 否 |
| **By skill** | 當下啟用的 skill（`attributionSkill`）；沒掛的算 `(no skill)` | 各 skill 耗多少 | 否 |
| **By agent** | `attributionAgent`：主線=`(main thread)`、子代理=其類型（如 `general-purpose`） | 各 agent 耗多少 | **是** |

- **單一對話的每日明細**：By conversation 每列前面有 **▸**，點開展開該對話的**逐日**用量（日期 · ≈$ · tokens · 佔該對話 % · turns）。跨天的對話會逐日列出。
- **By agent 的計數口徑（重要）**：這是**唯一把子代理/workflow（nested）算進來**的分組。子代理的 transcript 平常被排除（避免和主線重複計算），只有 By agent 會納入 —— 所以它的**總量會比其它分組大**，區塊標題也標明「含 nested、總量與上方不同」。差額就是所有子代理/workflow 實際多耗的量。
- 其餘三個分組（conversation / project / skill）維持 **nested excluded**，數字彼此一致。

> 想讓「主線 + 子代理」全部一起算進 conversation/project/skill，可跑
> `python scripts\token_report.py --include-nested`（會改變那三個分組的數字）。

---

## 安裝手冊

### 需求
- **Windows** + Windows PowerShell 5.1（內建）或 PowerShell 7。
- **Python 3.9+**（指令會依序試 `python` → `py` → `python3`）。
- 你自己的 Claude Code 對話記錄在 `~/.claude/projects/`（用過 Claude Code 就會有）。
- **不需要** API key、不需要 Docker、不需要連網。

### 步驟

```powershell
# 1) 取得專案
git clone https://github.com/Verna0519/Token-Monitor.git
cd Token-Monitor\aocc-personal-ai-coach

# 2) 複製設定範本，填自己的數字（檔案是 gitignored，不會被推上去）
Copy-Item config\usage-limits.template.json config\usage-limits.json

# 3) 載入指令（注意開頭的「點 + 空白」），開啟儀表板
. .\scripts\monitor.ps1
tokens
```

`tokens` 會：讀當下對話記錄 → 算用量 → 重建 HTML → 用瀏覽器開啟。

編輯 `config/usage-limits.json`，把 `$` 花費、credit %、resets／expires 日期、`operator`
（你的名字）、`token_limit` 填成你自己的（對照 Claude Settings > Usage 頁）。

> **執行原則擋住 dot-source？** 只放行「這個 shell」：
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
> ```

### 一鍵「開啟＝重新整理」
把 **`scripts\open-monitor.cmd`** 建個桌面捷徑，雙擊即可：重抓當下資料 → 重建 → 開啟。
（HTML 是靜態快照，**在瀏覽器按 F5 不會重抓**，一定要重新產生。）

---

## 重新抓取最新資料（最常用）

**從任何一個新的 PowerShell 視窗貼上這一行**，就會重讀你當下的對話記錄 → 重算 → 重建 HTML →
開啟（把路徑換成你自己 clone 的位置）：

```powershell
cd "C:\path\to\Token-Monitor\aocc-personal-ai-coach"; . .\scripts\monitor.ps1; tokens
```

之後在**同一個視窗**，只要打 `tokens` 就會再抓一次最新的（每跑一次都重讀 `~/.claude/projects`）。

> **重點：** 儀表板是靜態 HTML 快照 —— 在瀏覽器**按 F5 不會抓到新資料**，一定要用 `tokens`
> （或雙擊 `scripts\open-monitor.cmd`）重新產生才會是最新的。想讓開著的分頁自動更新，用
> `Watch-MonitorDashboard -Every 300`（每 5 分鐘自動重抓＋重整，Ctrl+C 停）。

---

## 日常使用（PowerShell）

```powershell
. .\scripts\monitor.ps1     # 每個新 shell 載入一次

tokens                      # 預設區間（config 的 window）；每跑一次都重抓最新資料
tokens -Today               # 今天（台灣時間）
tokens -Week                # 近 7 天
tokens -Month               # 近 30 天
tokens -Days 14             # 近 N 天
tokens -Since 2026-07-01 -Until 2026-07-15
tokens -All                 # 全部時間
tokens -NoOpen              # 只重建，不開瀏覽器
tokens -Cloud               # 額外連外抓真實每日 $（需 ANALYTICS_API_KEY）
```

其他視圖（同一份資料）：

```powershell
Show-TokenMonitor -By skill -Week   # 在終端機用彩色長條顯示
Watch-TokenMonitor -Every 60        # 終端機即時視圖，每 60 秒重畫（Ctrl+C 停）
Watch-MonitorDashboard -Every 300   # 讓開著的 HTML 分頁每 5 分鐘自動重整
Get-TokenReport -Days 7             # 純文字表格
```

時間一律以 **台灣時間（UTC+8）** 為準；Python 腳本可用 `--utc-offset` 改。

---

## 檔案與隱私

監控寫出的東西全在 `worktemp/`（或 `config/usage-limits.json`），**都是 gitignored、不會被追蹤**：

- `worktemp/token-usage.json` — token 統計（含帶身分的專案路徑／標題，僅本機）
- `worktemp/dashboard.html` — 產生的儀表板
- `worktemp/cloud-usage.json` — 連外抓來的 $（若有）
- `config/usage-limits.json` — 你的方案數字與名字
- `.env` — 你的 API key（若有）

腳本以**唯讀**方式讀 `~/.claude/projects`，從不寫到 repo 外，也從不主動連網（除非你自己跑
`-Cloud`）。詳細操作手冊見 [`scripts/README-monitor.md`](scripts/README-monitor.md)。

---

## 分享給其他人

這個 repo 可以安全分享 —— 所有個資都在 gitignored 檔案裡，隨附的只有 `*.template.json` /
`.env.template` 佔位檔。收到的人 clone 之後填自己的：

```powershell
Copy-Item config\usage-limits.template.json config\usage-limits.json   # 你的方案數字 / token_limit
Copy-Item .env.template .env                                           # 選用：ANALYTICS_API_KEY
. .\scripts\monitor.ps1 ; tokens
```

---

## 連外抓 $（選用；真實 per-product 花費）

預設完全離線、$ 手填。要抓真實每日 $（chat / claude_code / cowork）需要
**Claude Enterprise Analytics API key**：

1. 企業版 **Primary Owner** 在 `claude.ai > Organization settings > API` 產一把（scope
   `read:analytics`）。**只有 Primary Owner 能產**；你不是的話要跟對方拿。
2. 填進 `.env`：`ANALYTICS_API_KEY=<你的 key>`（`.env` 是 gitignored）。
3. 跑 `tokens -Cloud`。只想抓自己的用量（非全組織）→ 在 `config/usage-limits.json` 設
   `"analytics_user_id"`。

沒有 key 時，連外腳本自動 no-op，儀表板維持離線 —— 這是**唯一**會連外的腳本，且只在你手動開啟時執行。

---

## 這個 repo 其實也是一個 agent

Token Monitor 是內建在 **`aocc-personal-ai-coach`**（三層 AI 能力教練設計的個人層）裡的一套本機監控
工具。整個 agent 的憲章、紅線（RL1–RL4）、能力座標管線等，見 [`CLAUDE.md`](CLAUDE.md) 與
[`INDEX.md`](INDEX.md)。若你只是要看 token／$，上面的步驟就夠了。

---

## English summary

**Token Monitor** is a local, **air-gapped** dashboard for your Claude Code **token / spend** usage:
pure-stdlib Python + PowerShell, **zero network**, output only in `worktemp/` (gitignored). It reads
your local transcripts (`~/.claude/projects/**/*.jsonl`) read-only and rolls token usage up by
**conversation / project / skill**, with a daily trend and your Usage-page **$ limits**.

**Install:** need Windows PowerShell + Python 3.9+ (no API key, no Docker, no network).
`git clone` → `cd aocc-personal-ai-coach` → `Copy-Item config\usage-limits.template.json
config\usage-limits.json` → `. .\scripts\monitor.ps1` → `tokens`. Or make a desktop shortcut to
`scripts\open-monitor.cmd` for one-click "open = refresh".

**Current state:** the **token** section is live from local transcripts on every run; the **$ /
credit** blocks are **manually filled** in `config/usage-limits.json` (mirror your Usage page).
There is **no official Anthropic token quota** — the real cap is the **$ spend limit** — so the
token `%` is measured against a **self-set** `token_limit` (currently `1,830,000,000`, i.e. the $150
monthly limit converted at your *effective* rate — your 7d volume would list at ~$278 > $150, so you
are on discounted/credit pricing and list-price conversion understates your real allowance; shown on
the face; change it in config, or set `0` for "% of window total"). Real per-product **$** requires an
Enterprise Analytics API key that only a Primary Owner can mint (`tokens -Cloud`). Full ops manual:
[`scripts/README-monitor.md`](scripts/README-monitor.md). This repo is also the
`aocc-personal-ai-coach` agent — see [`CLAUDE.md`](CLAUDE.md).
