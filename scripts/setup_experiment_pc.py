#!/usr/bin/env python3
"""Experiment PC one-click setup — bootstrap ExpToolKit for production use.

Purpose: turn a fresh ``git clone`` of ExpToolKit into a ready-to-use
experiment PC environment in a single command.

What it does (idempotent — safe to re-run):
  1. Creates docs/requirements/{inbox,done} directories
  2. Installs exp_toolkit in editable mode (``pip install -e .``)
  3. Configures Claude Code for diagnostic/read-only role
  4. Appends experiment PC conventions to CLAUDE.md
  5. Runs smoke test to verify everything works

Usage:
    python scripts/setup_experiment_pc.py          # interactive (asks before changes)
    python scripts/setup_experiment_pc.py --yes    # non-interactive (auto-confirm all)

Exit code: 0 = ready, non-zero = setup failed (check messages).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (relative to this script)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

CLAUDE_MD = PROJECT_ROOT / "CLAUDE.md"
CLAUDE_MD_BACKUP = PROJECT_ROOT / "CLAUDE.md.dev-backup"
CLAUDE_SETTINGS = PROJECT_ROOT / ".claude" / "settings.local.json"
CLAUDE_SETTINGS_BACKUP = PROJECT_ROOT / ".claude" / "settings.local.json.dev-backup"

EXPERIMENT_PC_CLAUDE_FRAGMENT = SCRIPT_DIR.parent / "docs" / "experiment-pc-claude.md"
EXPERIMENT_PC_SETTINGS_TEMPLATE = PROJECT_ROOT / ".claude" / "settings.experiment-pc.json"

REQUIREMENTS_INBOX = PROJECT_ROOT / "docs" / "requirements" / "inbox"
REQUIREMENTS_DONE = PROJECT_ROOT / "docs" / "requirements" / "done"

SMOKE_TEST = SCRIPT_DIR / "smoke_test.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _confirm(prompt: str, *, yes: bool) -> bool:
    """Ask user for confirmation, or auto-accept if --yes."""
    if yes:
        print(f"  [--yes] {prompt}")
        return True
    answer = input(f"  {prompt} [y/N] ").strip().lower()
    return answer in ("y", "yes")


def _run(cmd: list[str], desc: str) -> bool:
    """Run a command and report success/failure."""
    print(f"  Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(f"  [OK] {desc}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  [FAIL] {desc}")
        if e.stdout:
            print(f"    {e.stdout.decode('utf-8', errors='replace')[:500]}")
        return False
    except FileNotFoundError:
        print(f"  [FAIL] {desc} — command not found: {cmd[0]}")
        return False


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step_create_directories(*, yes: bool) -> bool:
    """Create requirement-card directories if they don't exist."""
    print("\n--- Step 1/5: Create requirement directories ---")
    for d in (REQUIREMENTS_INBOX, REQUIREMENTS_DONE):
        if d.exists():
            print(f"  [SKIP] {d.relative_to(PROJECT_ROOT)} already exists")
        else:
            if _confirm(f"Create {d.relative_to(PROJECT_ROOT)}?", yes=yes):
                d.mkdir(parents=True, exist_ok=True)
                (d / ".gitkeep").touch()
                print(f"  [OK] Created {d.relative_to(PROJECT_ROOT)}")
            else:
                print(f"  [SKIP] {d.relative_to(PROJECT_ROOT)}")
    return True


def step_install_package(*, yes: bool) -> bool:
    """Install exp_toolkit (non-editable — copies to site-packages).

    Uses regular ``pip install .`` (NOT ``-e``) to decouple the installed
    package from the source tree.  This enforces the environment separation
    principle: code changes on the experiment PC require a deliberate
    ``git checkout <version> && pip install .`` cycle, not just editing a
    file in the repo.
    """
    print("\n--- Step 2/5: Install exp_toolkit ---")
    if not _confirm("pip install . (copy to site-packages)?", yes=yes):
        print("  [SKIP] Package installation skipped — smoke test may fail.")
        return True
    return _run([sys.executable, "-m", "pip", "install", "."],
                "pip install .")


def step_configure_claude_settings(*, yes: bool) -> bool:
    """Configure Claude Code for diagnostic/read-only role."""
    print("\n--- Step 3/5: Configure Claude Code settings ---")

    template = EXPERIMENT_PC_SETTINGS_TEMPLATE
    target = CLAUDE_SETTINGS

    if not template.exists():
        print(f"  [WARN] Template not found: {template.relative_to(PROJECT_ROOT)}")
        print("  Using built-in defaults instead.")
        settings_json = _builtin_experiment_pc_settings()
        if not _confirm("Write .claude/settings.local.json with built-in defaults?", yes=yes):
            return True
    else:
        if target.exists():
            if not _confirm(f"Overwrite existing {target.relative_to(PROJECT_ROOT)}?\n"
                           f"         (backup will be saved to settings.local.json.dev-backup)", yes=yes):
                print("  [SKIP] Keeping existing settings.")
                return True
            # Backup
            shutil.copy2(target, CLAUDE_SETTINGS_BACKUP)
            print(f"  [OK] Backup: {CLAUDE_SETTINGS_BACKUP.relative_to(PROJECT_ROOT)}")

        settings_json = template.read_text(encoding="utf-8")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(settings_json, encoding="utf-8")
    print(f"  [OK] Written: {target.relative_to(PROJECT_ROOT)}")
    return True


def _builtin_experiment_pc_settings() -> str:
    """Fallback settings JSON when template file is missing."""
    return (
        '{\n'
        '  "permissions": {\n'
        '    "allow": [\n'
        '      "Read",\n'
        '      "Grep",\n'
        '      "Glob",\n'
        '      "WebSearch",\n'
        '      "WebFetch"\n'
        '    ],\n'
        '    "deny": [\n'
        '      "Edit",\n'
        '      "Write",\n'
        '      "Bash(git push*)",\n'
        '      "Bash(pip install*)",\n'
        '      "Bash(rm *)",\n'
        '      "Bash(del *)"\n'
        '    ],\n'
        '    "ask": [\n'
        '      "Bash(python*)",\n'
        '      "Bash(pytest*)",\n'
        '      "Bash(git status)",\n'
        '      "Bash(git diff*)",\n'
        '      "Bash(git log*)"\n'
        '    ]\n'
        '  }\n'
        '}\n'
    )


def step_configure_claude_md(*, yes: bool) -> bool:
    """Append experiment PC conventions to CLAUDE.md."""
    print("\n--- Step 4/5: Configure CLAUDE.md for experiment PC ---")

    fragment = EXPERIMENT_PC_CLAUDE_FRAGMENT
    target = CLAUDE_MD

    if not fragment.exists():
        print(f"  [WARN] Fragment not found: {fragment.relative_to(PROJECT_ROOT)}")
        print("  Using built-in fragment instead.")
        fragment_text = _builtin_experiment_pc_claude_fragment()
    else:
        fragment_text = fragment.read_text(encoding="utf-8")

    # Check if fragment is already appended
    current = target.read_text(encoding="utf-8")
    marker = "## 实验电脑特殊约定"
    if marker in current:
        print(f"  [SKIP] {marker} already present in CLAUDE.md")
        return True

    if not _confirm(f"Append experiment PC conventions to CLAUDE.md?\n"
                   f"         (backup: CLAUDE.md.dev-backup)", yes=yes):
        print("  [SKIP] Keeping original CLAUDE.md.")
        return True

    # Backup
    shutil.copy2(target, CLAUDE_MD_BACKUP)
    print(f"  [OK] Backup: {CLAUDE_MD_BACKUP.relative_to(PROJECT_ROOT)}")

    # Append
    new_content = current.rstrip("\n") + "\n\n" + fragment_text.strip() + "\n"
    target.write_text(new_content, encoding="utf-8")
    print(f"  [OK] Appended experiment PC conventions to CLAUDE.md")
    return True


def _builtin_experiment_pc_claude_fragment() -> str:
    """Fallback CLAUDE.md fragment when template file is missing."""
    return (
        "\n"
        "## 实验电脑特殊约定\n"
        "\n"
        "### 角色\n"
        "- 你是诊断助手，协助科学家分析实验数据、定位问题\n"
        "- **禁止修改 ExpToolKit 源码**（所有代码变更在开发电脑上完成）\n"
        "- **禁止 pip install / uninstall**（版本升级需人工确认）\n"
        "\n"
        "### 发现问题时的流程\n"
        "1. 用 Read/Grep 探索相关代码，理解预期行为\n"
        "2. 诊断问题根因（是数据问题还是代码 bug）\n"
        "3. 产出需求卡片：`docs/requirements/inbox/REQ-YYYY-MMDD-NNN.md`\n"
        "4. 如有不确定的物理知识，标记 `TODO(DOMAIN)`\n"
        "\n"
        "### 需求卡片格式\n"
        "见 `docs/deployment-guide.md` §4 阶段① 的模板。\n"
        "\n"
        "### 允许的操作\n"
        "- 运行 Python 分析脚本（Bash(python...)）\n"
        "- 运行测试（Bash(pytest...)）\n"
        "- 查看 git 状态/日志/diff\n"
        "- Web 搜索领域知识\n"
    )


def step_run_smoke_test(*, yes: bool) -> bool:
    """Run the smoke test to verify installation."""
    print("\n--- Step 5/5: Run smoke test ---")
    if not _confirm("Run smoke test now?", yes=yes):
        print("  [SKIP] You can run it later: python scripts/smoke_test.py")
        return True
    result = subprocess.run([sys.executable, str(SMOKE_TEST)],
                            cwd=str(PROJECT_ROOT))
    if result.returncode == 0:
        print("\n  [PASS] Smoke test passed — ExpToolKit is ready.")
        return True
    else:
        print(f"\n  [FAIL] Smoke test exited with code {result.returncode}")
        print("  Troubleshooting:")
        print("    1. Check Python version >= 3.10")
        print("    2. Check pip install -e . completed without errors")
        print("    3. Run: python scripts/smoke_test.py  (see full output)")
        return False


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_next_steps() -> None:
    """Print post-setup instructions."""
    print("\n" + "=" * 56)
    print("  Setup complete — next steps")
    print("=" * 56)
    print()
    print("  1. Verify Claude Code role:")
    print("     cat .claude/settings.local.json")
    print()
    print("  2. Start collecting experiment data:")
    print("     Place raw CSV+INI+JSON files in data/")
    print()
    print("  3. Initialize chip state:")
    print("     python -c \"")
    print("     from exp_toolkit.io import load_experiment")
    print("     from exp_toolkit.fitting import fit_t1")
    print("     from exp_toolkit.state import ChipState")
    print("     from exp_toolkit.visualization import ChipTopology")
    print("     from exp_toolkit.report import ReportGenerator")
    print("     # ... load data, fit, save state, generate report ...")
    print("     \"")
    print()
    print("  4. When you discover an issue or need a new feature:")
    print("     Ask Claude Code: 'create a requirement card for ...'")
    print(f"     Cards are saved to: {REQUIREMENTS_INBOX.relative_to(PROJECT_ROOT)}")
    print()
    print("  5. Sync requirements + data to development PC:")
    print("     See docs/how-to/git-lfs-workflow.md")
    print()
    print("  For the full workflow, read: docs/deployment-guide.md")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="ExpToolKit experiment PC one-click setup")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Non-interactive mode — auto-confirm all steps")
    args = parser.parse_args()

    print("=" * 56)
    print("  ExpToolKit — Experiment PC Setup")
    print(f"  Project root: {PROJECT_ROOT}")
    print(f"  Python: {sys.version}")
    print("=" * 56)

    all_ok = True

    all_ok &= step_create_directories(yes=args.yes)
    all_ok &= step_install_package(yes=args.yes)
    all_ok &= step_configure_claude_settings(yes=args.yes)
    all_ok &= step_configure_claude_md(yes=args.yes)
    all_ok &= step_run_smoke_test(yes=args.yes)

    if all_ok:
        print_next_steps()
        return 0
    else:
        print("\n[FAIL] Some setup steps failed. Review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
