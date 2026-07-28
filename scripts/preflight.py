#!/usr/bin/env python3
"""
preflight.py — COLD-START PREFLIGHT (read-only setup-completeness check, portable).

Runs everywhere python3 runs (Windows-native / WSL / macOS / Linux) because python3 is already a
hard dependency of this agent — so it needs no bash and can flag the "bash gates won't run here"
case on Windows-native itself. It is a CHECK, never a fixer: it emits a machine-readable GAP REPORT
(worktemp/preflight-report.json, PRIVATE/gitignored) + a human summary, and the interactive AGENT
reads that report to drive the operator Q&A (hooks/scripts cannot do interactive stdin).

Red-line posture:
- RL1: reads ONLY local repo files + shells `git`/gate scripts locally; no mem0/qmd/team/inbox, no
  network, no ~/.claude coupling (it does not even read the corpus content — only checks the ROOT
  resolves).
- RL2: no logic-baked absolute path (ROOT derived from __file__); a missing/unset required resource
  is reported as a GAP and the script exits NON-ZERO (loud), never silent-pass. Windows drive
  mounts are DISCOVERED from /proc/mounts, never hardcoded as `/mnt/c`.
- RL4: the report lands in worktemp/ (PRIVATE); it may name local absolute paths — allowed INSIDE
  the private layer (identity only must never cross UPWARD or reach the person as a score).

Native-Windows completion story: on platform.system()=="Windows" the bash/coreutils gate tooling
is intentionally reported as WARN (remediation: run the two .sh gates under WSL or Git-Bash), NOT
as a hard GAP — so a correctly configured native-Windows machine CAN reach setup_complete: true.
The two .sh gates remain the authoritative "驗證通過" and are run under WSL/Git-Bash.

Exit codes: 0 = setup complete (no GAP on any check); 1 = gaps present (loud, RL2).

Usage:
  python3 scripts/preflight.py [--report-path PATH] [--quiet] [--no-gates]
"""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)

# Private denylist mirrored from check-visibility-seam.sh gate (a) — never git-tracked.
PRIVATE_TRACKED_RE = re.compile(
    r"^(raw-sessions|handoff|output|worktemp)/|"
    r"(^config/STATE\.md$|\.filled\.yaml$|^self-growth/insight-log-private\.md$|^\.env$)"
)


def is_wsl():
    rel = platform.release().lower()
    if "microsoft" in rel or "wsl" in rel:
        return True
    try:
        with open("/proc/version", encoding="utf-8") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False


def which(name):
    return shutil.which(name)


def read_filled_projects_root():
    """Parse CLAUDE_PROJECTS_ROOT EXACTLY as scan_sessions.py does (literal line, .strip(),
    strip quotes, NO expanduser) so we reproduce that script's real behaviour, tilde-trap
    included. .strip() also removes any trailing CR, so a CRLF filled file does NOT corrupt the
    resolved root value — only .sh/.py shebang CRLF is a real hazard (covered by PF-CRLF)."""
    filled = os.path.join(ROOT, "config", "path-mappings.filled.yaml")
    if not os.path.isfile(filled):
        return None, "missing"
    with open(filled, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("CLAUDE_PROJECTS_ROOT:"):
                val = s.split(":", 1)[1].strip().strip('"').strip("'")
                return val, "found"
    return None, "unset"


def count_jsonl(root, cap=5):
    """Count *.jsonl under root, cheaply capped (we only need 0 vs >=1 for the corpus verdict)."""
    n = 0
    for _dp, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".jsonl"):
                n += 1
                if n >= cap:
                    return n
    return n


def windows_mount_points():
    """Discover WSL Windows-drive mount points from the LIVE mount table (/proc/mounts) rather
    than baking an absolute path (RL2: discover, never hardcode). Returns drvfs/9p/cifs mounts."""
    mps = []
    try:
        with open("/proc/mounts", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 3:
                    continue
                mount_point, fstype = parts[1], parts[2]
                if fstype in ("9p", "drvfs", "cifs") and mount_point not in mps:
                    mps.append(mount_point)
    except OSError:
        pass
    return mps


def probe_windows_side():
    """When the Linux/WSL root is empty, look for a Windows-native CLI store to distinguish
    'no history anywhere' from 'CLI ran on Windows' (WSL-01/WSL-07). Windows mount roots are
    DISCOVERED from /proc/mounts, not hardcoded, so this stays RL2-clean across wsl.conf setups."""
    hits = []
    for base in windows_mount_points():
        udir = os.path.join(base, "Users")
        if not os.path.isdir(udir):
            continue
        try:
            for user in os.listdir(udir):
                cand = os.path.join(udir, user, ".claude", "projects")
                if os.path.isdir(cand):
                    hits.append(cand)
        except OSError:
            pass
    return hits


def scan_crlf():
    """Find tracked text files carrying CRLF (WSL-03 / P-W-03). Pure-python, no grep -P."""
    bad = []
    for sub, exts in (("scripts", (".sh", ".py")), ("config", (".yaml",))):
        d = os.path.join(ROOT, sub)
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if not name.endswith(exts):
                continue
            p = os.path.join(d, name)
            try:
                with open(p, "rb") as fh:
                    if b"\r\n" in fh.read():
                        bad.append(os.path.relpath(p, ROOT))
            except OSError:
                pass
    return bad


def git_ls_files():
    """Return (tracked_list, dubious_ownership_bool, ok_bool). Detects WSL-06: the seam gate
    swallows a dubious-ownership fatal with `|| true`, so we surface it here too (belt AND
    braces; the gate itself is also hardened in this delivery)."""
    if not which("git"):
        return [], False, False
    try:
        proc = subprocess.run(["git", "-C", ROOT, "ls-files"],
                              capture_output=True, text=True)
    except OSError:
        return [], False, False
    dubious = "dubious ownership" in (proc.stderr or "").lower()
    if proc.returncode != 0:
        return [], dubious, False
    tracked = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    return tracked, dubious, True


def run_gate(script_name):
    """Run a bash gate if bash is available; return (ran, exit_code)."""
    if not which("bash"):
        return False, None
    path = os.path.join(SCRIPT_DIR, script_name)
    if not os.path.isfile(path):
        return False, None
    try:
        proc = subprocess.run(["bash", path], cwd=ROOT, capture_output=True, text=True)
        return True, proc.returncode
    except OSError:
        return False, None


class Report:
    def __init__(self):
        self.checks = []

    def add(self, cid, precondition, severity, status, detail,
            remediation="", qa_prompt="", auto_fixable=False, environment="all"):
        self.checks.append({
            "id": cid, "precondition": precondition, "severity": severity,
            "status": status, "environment": environment, "detail": detail,
            "remediation": remediation, "qa_prompt": qa_prompt,
            "auto_fixable": auto_fixable,
        })


def main():
    ap = argparse.ArgumentParser(description="Cold-start preflight (read-only setup check).")
    ap.add_argument("--report-path",
                    default=os.path.join(ROOT, "worktemp", "preflight-report.json"))
    ap.add_argument("--quiet", action="store_true", help="print only the summary line")
    ap.add_argument("--no-gates", action="store_true",
                    help="do not shell out to the bash gates")
    args = ap.parse_args()

    win_native = platform.system() == "Windows"
    wsl = is_wsl()
    repo_drvfs = os.path.realpath(ROOT).startswith("/mnt/")
    rep = Report()

    # --- python (PC-02 / macos-python3-not-runnable): if this runs at all, python3 works. -----
    rep.add("PF-PY-RUN", "PC-02", "blocker", "PASS",
            f"python3 runnable: {sys.executable} ({platform.python_version()}).")

    # --- required python libs (PC-03 / WSL-05 / macos-pip-externally-managed) -----------------
    missing_libs = []
    for mod in ("jsonschema", "yaml"):
        try:
            __import__(mod)
        except ImportError:
            missing_libs.append("pyyaml" if mod == "yaml" else mod)
    if missing_libs:
        import sysconfig
        managed = os.path.exists(os.path.join(sysconfig.get_path("stdlib"), "EXTERNALLY-MANAGED"))
        recipe = ("interpreter is PEP-668 externally-managed — use a venv "
                  "(`python3 -m venv .venv && .venv/bin/pip install jsonschema pyyaml`, then run "
                  "the pipeline via .venv/bin/python3), or the distro package "
                  "(`sudo apt install python3-jsonschema python3-yaml` / brew), or "
                  "`pip install --user jsonschema pyyaml`."
                  if managed else "install with `pip install jsonschema pyyaml`.")
        rep.add("PF-PY-LIBS", "PC-03", "blocker", "GAP",
                f"missing required python lib(s): {', '.join(missing_libs)} "
                f"(jsonschema is hard-required — aggregate_signals.py / validate_extraction.py "
                f"die on ImportError). {recipe}",
                remediation=recipe,
                qa_prompt="缺少 jsonschema/pyyaml。"
                          + ("此解譯器為 PEP-668 externally-managed,直接 pip install 會被擋。"
                             "你偏好 (a) 建立專案 venv 並用它跑管線,(b) sudo apt/brew 安裝發行版套件,"
                             "還是 (c) pip install --user?" if managed else
                             "要我用 `pip install jsonschema pyyaml` 裝到這個 python3 嗎?"),
                auto_fixable=False)
    else:
        rep.add("PF-PY-LIBS", "PC-03", "blocker", "PASS",
                "jsonschema + pyyaml importable under this interpreter.")

    # --- `python3` TOKEN resolves? (WSL-04 / P-W-02 / macos python3.x naming) -----------------
    # Scripts + gates hardcode the literal token `python3` (shebangs + `python3 ...` in the gates),
    # so it is not enough that THIS process runs — the token `python3` must resolve on PATH.
    if which("python3"):
        rep.add("PF-PY3-TOKEN", "PC-02", "blocker", "PASS",
                "the literal token `python3` resolves on PATH (matches the scripts' shebangs/gates).")
    else:
        alt = which("python") or which("py")
        rep.add("PF-PY3-TOKEN", "PC-02", "blocker" if not win_native else "minor",
                "WARN" if win_native else "GAP",
                "the token `python3` is NOT on PATH, but the scripts/gates hardcode `python3` "
                "(shebangs `#!/usr/bin/env python3`). "
                + (f"An alternative interpreter is `{os.path.basename(alt)}`. " if alt else "")
                + ("On native Windows, run the pipeline/gates under WSL or Git-Bash where a "
                   "`python3` is available, or drop a python3.bat shim forwarding to `py -3`."
                   if win_native else
                   "Symlink/alias a real `python3` first on PATH (there is no interpreter-override "
                   "key — the pipeline uses PATH `python3` only)."),
                remediation="ensure `python3` resolves (venv/brew symlink, apt python3, or a "
                            "python3.bat shim to `py -3`).",
                qa_prompt="你的機器上 `python3` 這個名字是否可用?腳本與 gate 都寫死呼叫 `python3`。"
                          "若只有 `python`/`py -3`,要我協助建立 python3 連結或 shim 嗎?",
                auto_fixable=False, environment="windows" if win_native else "all")

    # --- UTF-8 BOM in config/JSON the pipeline reads (P-W-07) ---------------------------------
    bom_hits = []
    bom_targets = [os.path.join(ROOT, "config", "path-mappings.filled.yaml"),
                   os.path.join(ROOT, "config", "extraction.schema.json")]
    cfg_dir = os.path.join(ROOT, "config")
    if os.path.isdir(cfg_dir):
        bom_targets += [os.path.join(cfg_dir, f) for f in os.listdir(cfg_dir)
                        if f.endswith(".json")]
    for p in dict.fromkeys(bom_targets):
        try:
            with open(p, "rb") as fh:
                if fh.read(3) == b"\xef\xbb\xbf":
                    bom_hits.append(os.path.relpath(p, ROOT))
        except OSError:
            pass
    if bom_hits:
        rep.add("PF-BOM", "n/a", "minor", "GAP",
                "leading UTF-8 BOM in: " + ", ".join(bom_hits) + " — json.load raises "
                "'Expecting value line 1 col 1' and the YAML hand-parser can miss a first-line key "
                "(P-W-07, common with Windows Notepad saves).",
                remediation="re-save as UTF-8 WITHOUT BOM (or strip the 3 leading bytes).",
                qa_prompt="偵測到設定/JSON 檔帶 UTF-8 BOM(常見於 Windows 記事本存檔),會讓解析爆掉。"
                          "要我協助去掉 BOM 嗎?",
                auto_fixable=False, environment="windows")
    else:
        rep.add("PF-BOM", "n/a", "minor", "PASS", "no UTF-8 BOM in the config/JSON the pipeline reads.")

    # --- native-Windows pipeline POSIX-path assumptions (P-W-04 / P-W-05) ---------------------
    if win_native:
        rep.add("PF-WIN-PIPELINE", "n/a", "major", "WARN",
                "native-Windows advisory: the pipeline scripts carry POSIX-path assumptions that "
                "silently misbehave under backslash paths — scan_sessions.py excludes nested agent "
                "transcripts with forward-slash literals `/subagents/`|`/workflows/` (P-W-04: on "
                "Windows os.sep='\\\\' so the exclusion is a NO-OP -> foreign sessions ingested), and "
                "the identity-leak regexes only match /home,/Users,/mnt — NOT `C:\\\\Users\\\\<name>` "
                "(P-W-05: a Windows user path could slip past the upward de-id guard). Until those "
                "are patched, RUN THE PIPELINE UNDER WSL/Git-Bash (POSIX paths) rather than native "
                "Windows python.",
                remediation="run scan/extract/emit under WSL or Git-Bash; or (code fix, Emil ruling) "
                            "normalize os.sep before the /subagents/ test and add a `C:\\\\Users\\\\` "
                            "branch to the three identity regexes.",
                qa_prompt="這是原生 Windows。pipeline 有 POSIX 路徑假設(P-W-04 子代理排除失效、"
                          "P-W-05 身分正則漏 C:\\Users)。建議在 WSL/Git-Bash 跑 pipeline;要我把這"
                          "兩個 code 缺陷列給 Emil 決定是否修原始碼嗎?",
                environment="windows", auto_fixable=False)

    # --- python3 interpreter advisory ---------------------------------------------------------
    # (The PYTHON_BIN override key was DELETED from path-mappings by Emil ruling 2026-07-15 — every
    #  script hardcodes `python3` / `#!/usr/bin/env python3`, so the interpreter is resolved from
    #  PATH only. This check confirms that PATH `python3` is the one carrying the config-parse libs.)
    rep.add("PF-PYTHON-BIN", "n/a", "minor", "WARN",
            "The pipeline uses whatever `python3` is first on PATH (there is no interpreter-override "
            "key). That `python3` must be the one carrying jsonschema/pyyaml.",
            remediation="ensure `python3` resolves to the interpreter that has jsonschema/pyyaml "
                        "(venv activate / brew symlink) on PATH.",
            qa_prompt="你的 `python3`(PATH 上第一個)是否已指向要用來跑管線的解譯器"
                      "(含 jsonschema/pyyaml)?",
            auto_fixable=False)

    # --- required CLI tools (PC-04) — bash/coreutils are WARN on native Windows ---------------
    for tool, sev in (("bash", "blocker"), ("git", "blocker"), ("grep", "required"),
                      ("find", "required"), ("wc", "required"), ("tr", "required")):
        if which(tool):
            rep.add(f"PF-CLI-{tool}", "PC-04", sev, "PASS", f"{tool} on PATH.")
        elif win_native:
            # On native Windows these live in WSL / Git-Bash; the .sh gates run there. WARN so a
            # correctly-configured Windows box can still reach setup_complete: true.
            rep.add(f"PF-CLI-{tool}", "PC-04", "minor", "WARN",
                    f"`{tool}` not on PATH — expected on native Windows. Run the two .sh gates "
                    f"(validate-selfcontainment.sh / check-visibility-seam.sh) under WSL or "
                    f"Git-Bash, which provide bash + coreutils.",
                    remediation="run the .sh gates under WSL/Git-Bash (Git for Windows ships "
                                "bash + grep/find/wc/tr).",
                    environment="windows", auto_fixable=False)
        else:
            rep.add(f"PF-CLI-{tool}", "PC-04", sev, "GAP",
                    f"`{tool}` not found on PATH (needed by the bash gates).",
                    remediation=f"install {tool} (coreutils/git/bash).",
                    auto_fixable=False)

    # --- git worktree + dubious-ownership (PC-12 / WSL-06) ------------------------------------
    tracked, dubious, ok = git_ls_files()
    if dubious:
        rep.add("PF-GIT-OWNERSHIP", "PC-12", "blocker", "GAP",
                "git reports 'dubious ownership' — `git ls-files` returns empty, which WOULD make "
                "check-visibility-seam.sh gate (a) a false-PASS (WSL-06). (This delivery also "
                "hardens the gate itself so it fails loudly instead of passing vacuously.)",
                remediation=f"git config --global --add safe.directory {ROOT} "
                            f"(better: keep the repo on a native filesystem, not a Windows mount).",
                qa_prompt=f"這個 repo 位置讓 git 因 dubious ownership 拒絕運作。要我請你執行 "
                          f"`git config --global --add safe.directory {ROOT}` 嗎?"
                          f"(更建議把 repo 移到 WSL 的 ~/code 下)",
                auto_fixable=True, environment="wsl")
    elif not ok:
        if win_native and not which("git"):
            rep.add("PF-GIT-WORKTREE", "PC-12", "minor", "WARN",
                    "git not on PATH on native Windows — install Git for Windows (also provides "
                    "the bash the .sh gates need). preflight/onboard themselves do not need git.",
                    remediation="install Git for Windows.",
                    environment="windows", auto_fixable=False)
        else:
            rep.add("PF-GIT-WORKTREE", "PC-12", "blocker", "GAP",
                    "`git ls-files` failed — this is not a usable git worktree (seam gate (a) "
                    "depends on it).",
                    remediation="run inside a git clone/worktree of this repo.",
                    auto_fixable=False)
    else:
        rep.add("PF-GIT-WORKTREE", "PC-12", "blocker", "PASS",
                f"git worktree ok ({len(tracked)} tracked files).")
        # gate (a) cross-check: no private path tracked (PC-09) --------------------------------
        leaked = [t for t in tracked if PRIVATE_TRACKED_RE.search(t)]
        if leaked:
            rep.add("PF-SEAM-A", "PC-09", "blocker", "GAP",
                    "identity-bearing PRIVATE path(s) are git-TRACKED (RL4 gate (a) leak): "
                    + ", ".join(leaked[:8]),
                    remediation="`git rm --cached` the path(s); confirm .gitignore un-ignore lines.",
                    auto_fixable=False)
        else:
            rep.add("PF-SEAM-A", "PC-09", "blocker", "PASS",
                    "no identity-bearing private path is git-tracked.")

    if repo_drvfs:
        rep.add("PF-REPO-DRVFS", "n/a", "minor", "WARN",
                "the repo itself sits on a /mnt drvfs mount — slow git + non-POSIX perms + it can "
                "trigger git dubious-ownership; prefer cloning under the WSL ext4 home (~/code).",
                environment="wsl", auto_fixable=False)

    # --- .env (PC-06) -------------------------------------------------------------------------
    if os.path.isfile(os.path.join(ROOT, ".env")):
        rep.add("PF-ENV", "PC-06", "required", "PASS",
                ".env present (may be empty — Pilot needs no key).")
    else:
        rep.add("PF-ENV", "PC-06", "required", "GAP",
                ".env missing.",
                remediation="`cp .env.template .env` (empty is fine) — or "
                            "`python3 scripts/onboard.py --init-env`.",
                qa_prompt="要我用 .env.template 建立空的 .env 嗎?(Pilot 不需 API key)",
                auto_fixable=True)

    # --- path-mappings.filled.yaml + CLAUDE_PROJECTS_ROOT (PC-05 / tilde / WSL-01/07) ---------
    root_val, root_state = read_filled_projects_root()
    if root_state == "missing":
        rep.add("PF-FILLED", "PC-05", "blocker", "GAP",
                "config/path-mappings.filled.yaml missing.",
                remediation="`cp config/path-mappings.yaml config/path-mappings.filled.yaml` then set "
                            "CLAUDE_PROJECTS_ROOT — or `python3 scripts/onboard.py "
                            "--projects-root <ABS path>`.",
                qa_prompt="尚未建立 path-mappings.filled.yaml。你的 Claude Code CLI transcripts "
                          "根目錄在哪?(Linux/WSL: /home/<你>/.claude/projects;macOS: "
                          "/Users/<你>/.claude/projects;若 CLI 裝在 Windows 端且從 WSL 存取:"
                          "/mnt/<drive>/Users/<你的Windows帳號>/.claude/projects)",
                auto_fixable=True)
    elif not root_val or root_val.startswith("<set me"):
        rep.add("PF-PROJECTS-ROOT", "PC-05", "blocker", "GAP",
                "CLAUDE_PROJECTS_ROOT is still the placeholder / unset.",
                remediation="set it to an absolute, already-expanded path via "
                            "`python3 scripts/onboard.py --projects-root <ABS path>`.",
                qa_prompt="CLAUDE_PROJECTS_ROOT 還是佔位符。請給我你的 transcripts 絕對路徑。",
                auto_fixable=True)
    elif root_val.startswith("~") or root_val.startswith("$"):
        rep.add("PF-PROJECTS-ROOT", "PC-05", "major", "GAP",
                f"CLAUDE_PROJECTS_ROOT='{root_val}' starts with ~ or $ — scan_sessions.py does NO "
                f"expanduser/expandvars, so it will die on this value (the tracked template "
                f"placeholder still shows a tilde — a trap; onboard.py expands it for you).",
                remediation="write an already-expanded absolute path: "
                            "`python3 scripts/onboard.py --projects-root \"$HOME/.claude/projects\"` "
                            "(macOS uses /Users not /home).",
                qa_prompt="CLAUDE_PROJECTS_ROOT 寫成了 ~ 或 $HOME 開頭,腳本不會展開。"
                          "要我幫你換成展開後的絕對路徑嗎?",
                auto_fixable=True)
    elif not os.path.isdir(root_val):
        hits = probe_windows_side()
        extra = (" A Windows-side CLI store WAS found at: " + ", ".join(hits) if hits else "")
        rep.add("PF-PROJECTS-ROOT", "PC-05", "blocker", "GAP",
                f"CLAUDE_PROJECTS_ROOT does not resolve to a directory: {root_val}." + extra,
                remediation="point it at an existing transcripts dir (or the Windows-side path "
                            "under /mnt/<drive>/Users/<u>/.claude/projects).",
                qa_prompt="設定的 transcripts 根目錄不存在。你的 Claude Code CLI 是裝在 WSL 端還是 "
                          "Windows 端?" + (f"(我在 {hits[0]} 找到 Windows 端紀錄)" if hits else ""),
                auto_fixable=False, environment="wsl" if hits else "all")
    else:
        rep.add("PF-PROJECTS-ROOT", "PC-05", "blocker", "PASS",
                f"CLAUDE_PROJECTS_ROOT resolves to a directory: {root_val}.")
        n = count_jsonl(root_val)
        root_drvfs = root_val.startswith("/mnt/")
        if n == 0:
            hits = probe_windows_side()
            extra = (" A Windows-side CLI store WAS found at: " + ", ".join(hits)
                     if hits else " No Windows-side store found either.")
            # Empty corpus on a FRESH machine is EXPECTED (info), not a hard failure. Only flag a
            # likely MISCONFIG (WSL-01/07) when a Windows-side store exists but the configured
            # root is empty. Otherwise it's WARN: no prior CLI usage here yet (PC-08).
            if hits:
                rep.add("PF-CORPUS", "PC-08", "major", "GAP",
                        "configured root resolves but has ZERO *.jsonl, WHILE a Windows-side CLI "
                        "store exists (WSL-01/07) — the pipeline would silently read empty and it "
                        "would be misread as 'low capability'." + extra,
                        remediation="point CLAUDE_PROJECTS_ROOT at "
                                    "/mnt/<drive>/Users/<WinUser>/.claude/projects (accept the "
                                    "v9fs perf hit) OR run Claude Code CLI in this environment.",
                        qa_prompt="設定根目錄底下沒有 .jsonl,但 Windows 端有紀錄。要把 "
                                  "CLAUDE_PROJECTS_ROOT 指到 Windows 端路徑嗎?" +
                                  (f"(找到:{hits[0]})" if hits else ""),
                        auto_fixable=False, environment="wsl")
            else:
                rep.add("PF-CORPUS", "PC-08", "minor", "WARN",
                        "configured root resolves but contains ZERO *.jsonl. On a FRESH machine "
                        "with no prior Claude Code CLI usage this is EXPECTED — not a failure. "
                        "Extraction will simply have nothing to scan until sessions accumulate "
                        "(沒掃到不等於能力低).",
                        remediation="use Claude Code CLI on this machine to accumulate transcripts; "
                                    "then re-run the pipeline.",
                        auto_fixable=False)
        else:
            rep.add("PF-CORPUS", "PC-08", "minor", "PASS",
                    f"transcript root has >=1 jsonl (found {n}{'+' if n >= 5 else ''}).")
        if root_drvfs:
            rep.add("PF-ROOT-DRVFS", "n/a", "minor", "WARN",
                    "transcript root is on a /mnt drvfs mount — scans are slow and file perms are "
                    "non-POSIX (WSL-02). Privacy rests on the .gitignore seam, not fs perms.",
                    environment="wsl", auto_fixable=False)

    # --- config/STATE.md (PC-07) --------------------------------------------------------------
    if os.path.isfile(os.path.join(ROOT, "config", "STATE.md")):
        rep.add("PF-STATE", "PC-07", "required", "PASS",
                "config/STATE.md present (fresh-agent resumption source).")
    else:
        rep.add("PF-STATE", "PC-07", "required", "GAP",
                "config/STATE.md missing — §9 resumption has no Next Action to read.",
                remediation="`cp config/STATE-template.md config/STATE.md` — or "
                            "`python3 scripts/onboard.py --init-state`.",
                qa_prompt="要我從 STATE-template.md 建立 config/STATE.md 嗎?",
                auto_fixable=True)

    # --- CRLF (WSL-03 / P-W-03) — the REAL line-ending hazard (shebang/bash lines) ------------
    crlf = scan_crlf()
    if crlf:
        rep.add("PF-CRLF", "n/a", "blocker", "GAP",
                "CRLF line endings in: " + ", ".join(crlf) + " — bash gates + python shebangs "
                "break under WSL/Git-Bash (`set: pipefail\\r`, `env: 'python3\\r'`). (This does "
                "NOT corrupt CLAUDE_PROJECTS_ROOT — scan_sessions .strip()s that value; the real "
                "hazard is the .sh/.py shebang + bash lines.)",
                remediation="`python3 scripts/onboard.py --normalize-eol` then "
                            "`git config core.autocrlf false`; commit the delivered .gitattributes.",
                qa_prompt="偵測到 CRLF 換行(通常是 Windows git clone 造成),會弄壞 bash/python "
                          "gate。要我轉回 LF 並建議 .gitattributes 嗎?",
                auto_fixable=True, environment="wsl")
    else:
        rep.add("PF-CRLF", "n/a", "blocker", "PASS",
                "tracked shell/py/yaml files are LF-only.")

    # --- the two bash gates (PC-11) — the real 驗證通過 gate ----------------------------------
    if args.no_gates:
        rep.add("PF-GATES", "PC-11", "minor", "WARN", "gate execution skipped (--no-gates).")
    elif not which("bash"):
        rep.add("PF-GATES", "PC-11", "minor", "WARN",
                "bash absent — cannot run validate-selfcontainment.sh / check-visibility-seam.sh "
                "here (native Windows). Run them under WSL or Git-Bash for the final gate.",
                remediation="run the two .sh gates under WSL/Git-Bash.",
                environment="windows", auto_fixable=False)
    else:
        for name in ("validate-selfcontainment.sh", "check-visibility-seam.sh"):
            ran, code = run_gate(name)
            if not ran:
                rep.add(f"PF-GATE-{name}", "PC-11", "blocker", "WARN",
                        f"could not execute {name}.")
            elif code == 0:
                rep.add(f"PF-GATE-{name}", "PC-11", "blocker", "PASS", f"{name} exits 0.")
            else:
                rep.add(f"PF-GATE-{name}", "PC-11", "blocker", "GAP",
                        f"{name} exits {code} — see its stderr; onboarding acceptance not met.",
                        remediation=f"run `bash scripts/{name}` and fix the reported FAIL lines.",
                        auto_fixable=False)

    # --- ENV-01: RESOLVED (Emil ruling 2026-07-15, option a) ----------------------------------
    # The MUST-cover list's ENV-01 (severity=blocker, title/content both the literal "test") was a
    # degenerate placeholder/canary with no real content. Emil confirmed it is a no-op canary, so it
    # is no longer surfaced as a WARN (no invented coverage to add). Kept as this note so a future
    # agent knows ENV-01 was adjudicated, not silently dropped.

    # --- verdict ------------------------------------------------------------------------------
    n_pass = sum(1 for c in rep.checks if c["status"] == "PASS")
    n_warn = sum(1 for c in rep.checks if c["status"] == "WARN")
    gaps = [c for c in rep.checks if c["status"] == "GAP"]
    blockers = [c for c in gaps if c["severity"] == "blocker"]
    setup_complete = not gaps
    out = {
        "tool": "preflight",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "os": {"system": platform.system(), "release": platform.release(),
               "is_wsl": wsl, "win_native": win_native, "repo_on_drvfs": repo_drvfs},
        "python": {"executable": sys.executable, "version": platform.python_version()},
        "summary": {"pass": n_pass, "warn": n_warn, "gap": len(gaps), "blocker": len(blockers)},
        "setup_complete": setup_complete,
        "checks": rep.checks,
    }

    os.makedirs(os.path.dirname(args.report_path), exist_ok=True)
    with open(args.report_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    if args.quiet:
        print(f"preflight: {'COMPLETE' if setup_complete else 'GAPS'} "
              f"(pass={n_pass} warn={n_warn} gap={len(gaps)} blocker={len(blockers)}) "
              f"-> {args.report_path}")
    else:
        print(f"== preflight (os={platform.system()} wsl={wsl} py={platform.python_version()}) ==")
        for c in rep.checks:
            mark = {"PASS": "ok ", "WARN": "!! ", "GAP": "XX "}[c["status"]]
            print(f"{mark}[{c['status']}] {c['id']}: {c['detail']}")
        print(f"-- summary: pass={n_pass} warn={n_warn} gap={len(gaps)} "
              f"blocker={len(blockers)} -> {args.report_path}")
        if gaps:
            print("-- next: the interactive agent reads the report and drives the setup Q&A.")

    sys.exit(0 if setup_complete else 1)


if __name__ == "__main__":
    main()
