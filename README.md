# Token Monitor

> 本機、離線的 **Claude Code + Cowork** token／花費監控儀表板。純 stdlib Python + PowerShell，
> **預設零連外**，所有輸出只寫進 `worktemp/`（私有、gitignored）。
>
> **核心原則：只顯示量得到的數字。** 量不到的就不顯示 —— 不擺過期的手填值，也不用假設換算出金額。

---

## 這是什麼

打開一個自包含的 HTML 儀表板，回答「**誰花了什麼**」：

- **Claude Code** —— 讀本機對話記錄（`~/.claude/projects/**/*.jsonl`），依 **對話／專案／skill／agent**
  與 **每日** 統計 token。
- **Cowork** —— 讀桌面 App 的本機 audit（`local-agent-mode-sessions/**/audit.jsonl`），依 **聊天室**
  與 **每日** 統計，並帶**真實 $**。

兩者是**不同產品、分開兩個區塊**，不混在一起。

---

## 儀表板上有什麼（依畫面順序）

| # | 區塊 | 內容 | 資料性質 |
|---|------|------|----------|
| 1 | **近期使用列表** | 最近 10 個對話（時間、標題、token） | 實測 |
| 2 | **Usage over time** | 每日 token 曲線；x 軸**以天為單位**、可切 **3／7／30 天**（預設 7 天）；點一天看**與前一日增減**；顯示**抓入區間與時區** | 實測 |
| 3 | **Token usage · who spent what** | **By conversation／By project／By skill／By agent** 四種分組，每列有 token、佔比；點 **▸** 展開看細項名稱 | 實測 |
| 4 | **Code · 本機用量** | token 組成表（cache 佔比）＋各 model；$ 為**官方牌價計算值**（CLI 無金額欄位） | 實測 token ＋ 計算 $ |
| 5 | **Cowork · 本機用量** | 每個**聊天室**（名稱＋真實 $＋點 ▸ 看每日）、**每日真實花費**、token 組成、各 model 單價 | **實測真實 $** |
| 6 | **欄位說明 / 使用說明** | 每個欄位的定義 ＋ 每個數字抓自哪個 jsonl 欄位 | — |

> **Your usage limits（帳號整體 $）** 只有在你用 `-Cloud` 連外抓到真實數字時才會出現；抓不到就**整塊不顯示**。

### 四種分組的定義

| 分組 | 依什麼歸戶（jsonl 欄位） | 點 ▸ 展開會看到 | 含子代理？ |
|------|--------------------------|-----------------|:---:|
| **By conversation** | `sessionId`（名稱 ← `customTitle`／`aiTitle`） | 每日用量、**用到的 skill**、開啟本機紀錄檔 | ✗ |
| **By project** | `cwd`（該 turn 當下的工作目錄） | 這個專案底下**哪些對話** | ✗ |
| **By skill** | `attributionSkill`（該 skill **作用期間**；無則 `(no skill)`） | 用到這個 skill 的**哪些對話** | ✗ |
| **By agent** | `attributionAgent`（主線 `(main thread)` ／子代理類型） | 這個 agent 出現在**哪些對話** | **✓ 唯一含** |

By agent 是唯一納入 nested（子代理／workflow）transcript 的分組，所以它的總量會比其他三個大 ——
差額就是子代理實際多耗的量，區塊標題會標出來。

### 時區（Usage over time）

transcript 存的是 **UTC**（ISO `…Z`）。報表預設換算成 **UTC+8（台灣）**，畫面上會寫明
「抓入區間 … (UTC+8)」。它還會**比對你這台機器的時區**：一致就標示一致，不一致會警告
「每日分界以 UTC+8 為準、非你的當地日」，並給出改用當地時間的指令
（`python scripts\token_report.py --utc-offset <你的offset>`）。

### $ 的三種身分（很重要）

| 來源 | 性質 | 說明 |
|------|------|------|
| **Cowork 區塊的 $** | ✅ **真實帳** | audit 的 `total_cost_usd`。已用官方牌價驗證：算 $236.80 vs 實帳 $236.83，**差 0.01%** |
| **Code 區塊的 $** | 🟡 **計算值** | CLI 沒有金額欄位，用**官方牌價 × 實測 token 組成**算。算法已用 Cowork 實帳驗證（誤差 0.7%），但**不是你的帳單** |
| 帳號整體 spend | ❌ 本機量不到 | 只有 claude.ai Usage 頁／Analytics API 有。沒抓到就不顯示 |

**Chat 的用量本機完全看不到**（不寫進任何本機檔），所以儀表板不含 Chat —— 這也是它和 claude.ai
Usage 頁「Daily spend by product」**本來就不會一致**的原因（那是全部產品的 $）。沒掃到 ≠ 沒用。

> **參考換算**：以實測組成 × 官方牌價，**$1,000 ≈ 7～12 億 tokens**
> （Code 的組成 ≈$0.86／百萬、Cowork ≈$1.41／百萬；cache_read 佔比越高越便宜）。
> 這是**牌價等值**，不代表你的 credit 消耗 —— 企業方案實際計費可能不同。

---

## 安裝

### 需求
- **Windows** + Windows PowerShell 5.1（內建）或 PowerShell 7
- **Python 3.9+**（指令會依序試 `python` → `py` → `python3`）
- 用過 Claude Code（`~/.claude/projects` 有記錄）
- **不需要** API key、Docker、或連網

### 步驟

```powershell
git clone https://github.com/Verna0519/Token-Monitor.git
cd Token-Monitor

# 唯一必要的設定：告訴它你的 Claude Code 記錄在哪
python scripts\onboard.py --projects-root "$HOME\.claude\projects"

. .\scripts\monitor.ps1 ; tokens
```

**Cowork 完全零設定** —— 會自動偵測桌面 App 的資料夾（Windows／macOS／Linux 各自的預設路徑都會探測）；
沒裝 Cowork 就自動略過該區塊。

選用：`Copy-Item config\usage-limits.template.json config\usage-limits.json` 後可填 `operator`（畫面上的名字）
與 `window`（預設時間範圍）。**不填也能正常用**，而且不會憑空生出任何 $。

> 執行原則擋住 dot-source 時，只放行這個 shell：
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`

---

## 看最新資料（三種方式）

儀表板是**靜態快照** —— **在瀏覽器按 F5 不會更新**，必須重新產生。

**① 一次性設定後，任何 PowerShell 直接打 `tokens`**（推薦）
```powershell
Add-Content $PROFILE ". 'C:\path\to\Token-Monitor\scripts\monitor.ps1' 6>`$null"
```
（`6>$null` 會靜音載入橫幅。之後開任何新視窗打 `tokens` 就是最新。）

**② 一行貼上就開**（可貼進 Win+R）
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command ". 'C:\path\to\Token-Monitor\scripts\monitor.ps1'; Show-TokenDashboard"
```

**③ 雙擊** `scripts\open-monitor.cmd`（建個桌面捷徑；等同 ②）

每一種都會：重讀當下記錄 → 重算 Code＋Cowork → 重建 HTML → 開啟。

### 常用指令

```powershell
tokens                      # 預設區間（config 的 window）
tokens -Today               # 今天
tokens -Week                # 近 7 天
tokens -Month               # 近 30 天
tokens -Days 14             # 近 N 天
tokens -Since 2026-07-01 -Until 2026-07-15
tokens -All                 # 全部時間
tokens -NoOpen              # 只重建，不開瀏覽器
tokens -Cloud               # 額外連外抓真實 $（需 ANALYTICS_API_KEY）

Show-TokenMonitor -By skill -Week   # 終端機彩色長條
Watch-TokenMonitor -Every 60        # 終端機即時視圖（Ctrl+C 停）
Watch-MonitorDashboard -Every 300   # 開著的分頁每 5 分鐘自動更新
Get-TokenReport -Days 7             # 純文字表格
```

---

## 額外工具

**送出前估 token**（`count_tokens.py`）—— 估一段 prompt 的 **input** token：
```powershell
python scripts\count_tokens.py --text "你要送的內容"
python scripts\count_tokens.py --file prompt.md
```
預設**離線粗估**（不連網、不用 key）；設了 `ANTHROPIC_API_KEY` 才改用官方
`POST /v1/messages/count_tokens` 精算（**opt-in 連外**）。只算 input，不含 output／帳單。

**連外抓真實 $**（`-Cloud`）—— 需要 **Claude Enterprise Analytics API key**，
而該 key **只有企業版 Primary Owner 能簽發**（`claude.ai > Organization settings > API`，scope
`read:analytics`）。填進 `.env` 的 `ANALYTICS_API_KEY` 後跑 `tokens -Cloud`。
沒有 key 時連外腳本自動 no-op，維持離線。

---

## 檔案與隱私

寫出的東西全在 `worktemp/`（或 `config/usage-limits.json`），**都是 gitignored、不會被追蹤**：

- `worktemp/token-usage.json` — Code token 統計（含專案路徑／標題，帶身分）
- `worktemp/cowork-usage.json` — Cowork 統計（含 session id、真實 $）
- `worktemp/dashboard.html` — 產生的儀表板
- `worktemp/cloud-usage.json` — 連外抓來的 $（若有）
- `config/usage-limits.json`、`.env` — 你的設定與 key

腳本以**唯讀**方式讀對話記錄與 Cowork audit，從不寫到 repo 外，也**從不主動連網**
（只有你自己跑 `-Cloud` 或設了 `ANTHROPIC_API_KEY` 的 `count_tokens.py` 才連）。

**分享給別人是安全的** —— 個資都在 gitignored 檔案裡，隨附的只有 `*.template.json` /
`.env.template` 佔位檔（已實測：全新 clone 只需上面那行 `onboard` 就能抓到自己的數值，
且不會出現任何假數字）。

---

## 疑難排解

- **`. .\scripts\monitor.ps1` 被擋** — 執行原則，用上面的 `-Scope Process` 那行。
- **`FAIL: config/path-mappings.filled.yaml missing`** — 還沒跑 `onboard.py --projects-root`（設計如此：
  找不到記錄會**大聲失敗**，不會靜默給你空數字）。
- **Cowork 區塊沒出現** — 這台機器沒有 Cowork 資料；要覆寫路徑可在
  `config/path-mappings.filled.yaml` 設 `COWORK_SESSIONS_ROOT`。
- **終端機 CJK 亂碼** — 儀表板一定正常；主控台是舊 codepage 的顯示問題（腳本已強制 UTF-8 輸出，
  不會因此中斷）。
- **`monitor.ps1` 必須維持純 ASCII** — PS 5.1 會把 UTF-8-no-BOM 的 `.ps1` 當 ANSI 讀，原始碼含非
  ASCII 會解析失敗（CJK 一律來自執行期讀 JSON）。
- **找不到 python** — 安裝 Python 3.9+。

---

## 這個 repo 其實也是一個 agent

Token Monitor 內建在 **`aocc-personal-ai-coach`**（三層 AI 能力教練設計的個人層）裡。整個 agent 的
憲章、紅線（RL1–RL4）、能力座標管線見 [`CLAUDE.md`](CLAUDE.md) 與 [`INDEX.md`](INDEX.md)。
**Token Monitor 的 Cowork 讀取只服務監控**，不進能力座標／萃取管線（那條維持 Claude Code CLI only）。
只想看 token／$ 的話，上面的內容就夠了。

---

## English summary

**Token Monitor** is a local, air-gapped dashboard for **Claude Code + Cowork** token/spend usage:
pure-stdlib Python + PowerShell, no network by default, output only in `worktemp/` (gitignored).

**Guiding rule — only measured numbers are shown.** Blocks whose data cannot be measured are simply
not rendered; no stale hand-typed values, no $ invented from assumptions.

**What it shows:** recent activity → daily usage curve (per-day x-axis, 3/7/30-day filter, default 7d,
day-over-day delta, timezone stated and cross-checked against your machine) → who spent what
(**by conversation / project / skill / agent**, each row expandable to name its members) →
**Code** block (token composition + per-model; $ computed from official list prices, since the CLI
records no $) → **Cowork** block (per chat room + per day with **REAL $** from `audit.jsonl`,
verified to 0.01% against official pricing).

**Install:** Windows PowerShell + Python 3.9+, no API key, no Docker, no network.
`git clone` → `python scripts\onboard.py --projects-root "$HOME\.claude\projects"` →
`. .\scripts\monitor.ps1 ; tokens`. Cowork needs zero configuration (OS-default paths are probed).

**Not covered:** Chat usage and your real account spend are not in any local file — only
claude.ai's Usage page / the Analytics API have them (`tokens -Cloud`, key mintable only by an
Enterprise Primary Owner). This repo is also the `aocc-personal-ai-coach` agent — see
[`CLAUDE.md`](CLAUDE.md).
