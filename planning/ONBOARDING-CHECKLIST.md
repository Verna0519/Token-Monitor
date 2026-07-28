# 個人能力 Agent — 新機上線清單(Cold-Start Onboarding Checklist)

> 目標:在一台新機器把 `aocc-personal-ai-coach` 從零帶到「驗證通過」(兩道 .sh gate 皆 exit 0)。
> 每一項都可勾選,並標注對應的前置條件(PC-xx)或已知遷移問題(WSL-xx / P-W-xx / macos-xx)。
> 全程互動式 Claude Code;禁止 `--print`/批次/背景/dispatch(PC-01)。
> 捷徑:任何一步不確定,先跑 `python3 scripts/preflight.py`,它會輸出當前所有缺口與逐項修法(machine-readable + 人類摘要)。

---

## 階段 0 — 前置需求(prerequisites)

- [ ] **互動式 Claude Code CLI 可用**,不用 `--print`/batch/background/dispatch(PC-01)。
- [ ] **python3 真的能執行**(不是只有 `command -v` 通過):`python3 --version` 直接印出版本(PC-02)。
  - **macOS**(macos-python3-not-runnable,blocker):`/usr/bin/python3` 可能只是 Xcode CLT stub,實際呼叫會跳 GUI 或報錯。請 `brew install python@3.12` 或 `xcode-select --install`,並確認 `python3` 在 PATH 最前面(Apple Silicon `/opt/homebrew/bin`,Intel `/usr/local/bin`)。preflight 的 PF-PY-RUN 靠「能跑起來」證明,PF-PY3-TOKEN 另外驗證 `python3` 這個名字有解析。
  - **WSL / 少數 Linux**(WSL-04 / P-W-02):若只有 `python` 沒有 `python3`,腳本與 gate 全寫死 `python3` 會 command-not-found;`PYTHON_BIN` 這個 key 沒有任何腳本會讀(死鍵),別靠它。請 `sudo apt install python3` 或建 `python3` symlink。
  - **Windows-native**:`.sh` gate 無法在原生 Windows 跑;請在 **WSL** 或 **Git-Bash** 內完成最終 gate(見階段 5)。python preflight/onboard 本身在原生 Windows 也能跑並會誠實說明。
- [ ] **bash / git / grep / find / wc / tr 都在 PATH**(PC-04)。gate 用到 bash-ism(`compgen`、process substitution),非 POSIX sh。原生 Windows 這些在 WSL/Git-Bash 內。
- [ ] 知道自己解譯器是否為 **PEP-668 externally-managed**:
  `python3 -c "import sysconfig,os;print('MANAGED' if os.path.exists(os.path.join(sysconfig.get_path('stdlib'),'EXTERNALLY-MANAGED')) else 'FREE')"`
  - WSL Ubuntu 24.04 / Debian 12 與 Homebrew python 幾乎都是 `MANAGED`(WSL-05 / macos-pip-externally-managed-libs-missing)→ 直接 `pip install` 會被擋,依賴安裝改走階段 3 的 venv / 發行版套件。

## 階段 1 — 取得程式碼(clone / checkout,含 .gitattributes / CRLF)

- [ ] 把 repo clone 到 **原生檔案系統**;WSL 請放在 `~/code`(ext4),**不要**放在 `/mnt/c`。
  - **WSL-02**:`/mnt/c` 上掃描慢一個數量級、檔案權限非 POSIX。
  - **WSL-06**(重要,major):repo 在 `/mnt/c` 時 git 常 `fatal: detected dubious ownership`。**本次交付已把 `check-visibility-seam.sh` gate (a) 硬化**——git 出錯時大聲 FAIL 而非 `|| true` 假通過。若仍要放 `/mnt/c`,執行 `git config --global --add safe.directory <repo 絕對路徑>`。
- [ ] **確認換行是 LF,不是 CRLF**(WSL-03 / P-W-03,blocker):Windows 端 git(預設 `core.autocrlf=true`)clone 後再進 WSL/Git-Bash 跑,會把 `.sh` shebang 與 bash 行變 CRLF,`bash` 報 `set: pipefail\r`、`env: 'python3\r'`。(注意:CRLF **不會**弄壞 CLAUDE_PROJECTS_ROOT——scan_sessions 會 `.strip()` 掉那個值;真正的危害只在 `.sh`/`.py` 的 shebang 與 bash 行。)
  - 偵測:`python3 scripts/preflight.py`(PF-CRLF 項)。
  - 修復:`python3 scripts/onboard.py --normalize-eol`,再 `git config core.autocrlf false`,並提交隨附的 `.gitattributes`(把 `*.sh *.py *.yaml` 釘死 `eol=lf`)。
- [ ] 確認 repo 是可用的 git worktree(PC-12):`git ls-files` 有輸出、無 fatal(preflight PF-GIT-WORKTREE / PF-GIT-OWNERSHIP)。

## 階段 2 — 依賴安裝(python launcher 三 OS 差異 + pip / PEP-668)

- [ ] 安裝硬需求 python libs:**jsonschema + pyyaml**(PC-03)。`jsonschema` 是 fail-closed 硬依賴,`aggregate_signals.py` / `validate_extraction.py` ImportError 就 die;`pyyaml` render_growth 有 soft fallback 但 manifest 要求。
  - `FREE`(非 PEP-668):`pip install jsonschema pyyaml`。
  - `MANAGED`(PEP-668,多數 WSL/macOS)三選一:
    - (a) 專案 venv:`python3 -m venv .venv && .venv/bin/pip install jsonschema pyyaml`,之後**跑管線與 gate 前先 `source .venv/bin/activate`**(腳本寫死 `python3`)。
    - (b) 發行版套件:`sudo apt install python3-jsonschema python3-yaml`(macOS 用 brew)。
    - (c) 退路:`pip install --user jsonschema pyyaml`(或最後手段 `--break-system-packages`)。
- [ ] **確認要用的 `python3` 就是裝了上述 libs 的那個直譯器**(python-bin-override-key-is-dead / WSL-05)。用 `python3 -c "import jsonschema,yaml;print('ok')"` 從 repo 根確認,而非 `pip show`(可能裝到別的直譯器)。
  - **三 OS launcher 差異**:Linux/WSL 期望 `python3`;macOS 若只有 `python3.12` 或在 brew 路徑,建 `python3` symlink / 調 PATH;原生 Windows 是 `python` / `py -3`(在 WSL/Git-Bash 內跑則有 `python3`)。`PYTHON_BIN` key 目前是死的(無腳本讀),真正生效的是 PATH 上第一個 `python3`。

## 階段 3 — 設定填寫(path-mappings.filled / .env / STATE,全部落在私有層)

- [ ] **建立 `.env`**(PC-06):`python3 scripts/onboard.py --init-env`(或 `cp .env.template .env`;Pilot 無需 API key,空的即可)。
- [ ] **建立 `config/STATE.md`**(PC-07):`python3 scripts/onboard.py --init-state`(§9 復原協定要靠它讀 Next Action)。
- [ ] **建立 `config/path-mappings.filled.yaml` 並填 `CLAUDE_PROJECTS_ROOT`**(PC-05)。
  - **必須寫「已展開的絕對路徑」**;`scan_sessions.py` 無 `expanduser`/`expandvars`,`~/.claude/projects` 或 `$HOME/...` 會直接 die(claude-projects-root-tilde-not-expanded)。**模板佔位符本身仍寫 `~` 是個陷阱**——請用 helper,它會替你展開:
    `python3 scripts/onboard.py --projects-root "$HOME/.claude/projects"`(路徑不存在會 loud-fail,不塞壞值)。
  - Linux/WSL:`/home/<你>/.claude/projects`;macOS:`/Users/<你>/.claude/projects`(是 `/Users` 不是 `/home`);Windows 端 CLI 從 WSL 存取:`/mnt/<drive>/Users/<你的Windows帳號>/.claude/projects`。
- [ ] 確認以上三檔**都沒有被 git 追蹤**(RL4 gate (a)):`git check-ignore .env config/STATE.md config/path-mappings.filled.yaml` 應全部命中。

## 階段 4 — 語料接線(CLAUDE_PROJECTS_ROOT 三 OS 位置 + 空 corpus 說明)

- [ ] 確認 `CLAUDE_PROJECTS_ROOT` 底下**真的有 `*.jsonl`**(PC-08)。preflight PF-CORPUS 會實際數。
  - **空 corpus 是分兩種情況**:
    - (i) **全新機器、沒用過 Claude Code CLI**:0 個 jsonl 是**預期的**(preflight 報 WARN,不擋 setup_complete)。開始用 CLI 累積 session 後再跑 pipeline——沒掃到不等於能力低。
    - (ii) **WSL-01 / WSL-07 誤配**(major):你設的根目錄空,但 CLI 其實裝在 Windows 端。preflight 會用 `/proc/mounts` 探測 `/mnt/<drive>/Users/.../.claude/projects`,若 Windows 端有紀錄而設定根目錄空,報 **GAP**(避免把空讀誤當低能力)。修法:把 root 指到 Windows 端(接受 WSL-02 慢),或改在 WSL 內用 CLI。
  - **macos-projects 位置**:`/Users/<你>`,不是 `/home`。
- [ ] (可選)冒煙:`python3 scripts/scan_sessions.py --max 1` 應寫出 `worktemp/session-index.json` 且不 die。

## 階段 5 — 驗證通過(preflight + 兩道 .sh gate 的三 OS 跑法)⛳

- [ ] 跑 preflight 總檢:`python3 scripts/preflight.py` → 期望 `setup_complete: true`、`gap=0`(PF-PYTHON-BIN / PF-ENV-01 等 WARN 可接受)。
- [ ] **兩道 gate 皆 exit 0(PC-11,這才是「驗證通過」)**:
  - `bash scripts/validate-selfcontainment.sh` → `PASS`(exit 0):standalone-l3 自足檢查(scrub / 無 baked 路徑 / backbone / 模板佔位符)。
  - `bash scripts/check-visibility-seam.sh` → `PASS`(exit 0):RL4 directed-visibility(a 私有桶未被追蹤 / b 只收 shape-checked coordinate / c 個人面向輸出無 score-rung-tier / d 憑證硬排除)。
  - **三 OS 跑法**:Linux / macOS / WSL 直接如上;**原生 Windows 這兩道 `.sh` 跑不起來(P-W-01)**,必須在 **WSL 或 Git-Bash** 內完成本項——preflight 在原生 Windows 會把這件事列成 WARN(不是假裝通過,也不會讓 setup 永遠不完成)。
- [ ] 完成後依 §9:讀 `CLAUDE.md → INDEX.md → config/STATE.md`,從 STATE 的 Next Action 續作(目前:補證據 TUNING → 重跑 emit-coordinate → 手動遞交 0.1 座標)。

> **驗證通過標準**:`preflight` 無 GAP(setup_complete=true)+ 兩道 gate 皆 exit 0。任何紅字都不是「差不多可以」——依 preflight gap report 的 remediation 修到綠;不確定就問 Emil,不要猜(flag-don't-reinterpret)。