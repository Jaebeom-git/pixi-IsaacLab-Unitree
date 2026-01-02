#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = "https://github.com/isaac-sim/IsaacLab.git"


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"[cmd] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def need_bin(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"{name} not found in PATH")


def prompt_required(prompt_text: str) -> str:
    """
    Require explicit user input. No defaults.
    - If stdin isn't interactive, error.
    - If user enters empty string, error.
    """
    if not sys.stdin.isatty():
        raise RuntimeError(
            "Missing required path argument and cannot prompt (non-interactive stdin). "
            "Please pass the path explicitly, e.g.:\n"
            "  pixi run isaaclab-install -- /home/...\n"
            "or\n"
            "  pixi run isaaclab-install -- /home/.../IsaacLab"
        )
    s = input(f"{prompt_text}: ").strip()
    if not s:
        raise RuntimeError(
            "No input provided. Please enter a path explicitly (no default is used).\n"
            "Example:\n"
            "  /home/...\n"
            "  /home/.../IsaacLab"
        )
    return s


def is_isaaclab_repo(path: Path) -> bool:
    return (path / "isaaclab.sh").exists() or (path / ".git").exists()


def resolve_clone_dest(user_input: str, repo_dirname: str = "IsaacLab") -> Path:
    """
    Accept either:
      - parent directory (e.g. /home/me/Projects) -> clone into /home/me/Projects/IsaacLab
      - explicit repo dir (e.g. /home/me/Projects/IsaacLab) -> clone into that dir
      - existing repo dir -> reuse it
      - non-existing path -> create that dir and clone into it
    """
    p = Path(user_input).expanduser().resolve()

    # If user pointed to an existing IsaacLab repo root, just use it.
    if p.exists() and p.is_dir() and is_isaaclab_repo(p):
        return p

    # If user gave an existing directory that is NOT a repo:
    # treat it as "parent", and clone into <parent>/IsaacLab
    if p.exists() and p.is_dir():
        return (p / repo_dirname).resolve()

    # If path doesn't exist: user is giving explicit destination directory
    return p


def clone_repo(dest: Path, repo: str, ref: str | None, depth: int) -> None:
    if dest.exists() and is_isaaclab_repo(dest):
        print(f"[OK] IsaacLab already exists: {dest}")
        return

    # If dest exists and is non-empty but not a repo -> refuse with guidance
    if dest.exists() and dest.is_dir():
        try:
            next(dest.iterdir())
            raise RuntimeError(
                f"Destination exists and is not empty: {dest}\n"
                f"Tip: pass the parent directory instead (I'll clone into <parent>/IsaacLab), "
                f"or choose an empty directory."
            )
        except StopIteration:
            pass  # empty dir OK

    dest.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "clone", "--depth", str(depth)]
    if ref:
        cmd += ["--branch", ref]
    cmd += [repo, str(dest)]

    print(f"[info] Cloning IsaacLab -> {dest}")
    run(cmd)


def isaaclab_install(dest: Path, install: str) -> None:
    sh = dest / "isaaclab.sh"
    if not sh.exists():
        raise RuntimeError(f"isaaclab.sh not found: {sh}")

    try:
        sh.chmod(sh.stat().st_mode | 0o111)
    except Exception:
        pass

    if install == "none":
        print("[info] install=none -> skip isaaclab.sh --install")
        return

    cmd = ["bash", "-lc", f'./isaaclab.sh --install "{install}"']
    print(f"[info] Running install: {install}")
    run(cmd, cwd=dest)


def main() -> None:
    ap = argparse.ArgumentParser(description="Clone IsaacLab and optionally run isaaclab.sh --install")
    ap.add_argument(
        "path",
        nargs="?",
        help="Either a parent directory (clones into <path>/IsaacLab) or an explicit destination directory.",
    )
    ap.add_argument("--repo", default=DEFAULT_REPO, help="Git repo URL")
    ap.add_argument("--ref", default=None, help="Git ref (branch/tag). Optional.")
    ap.add_argument("--depth", type=int, default=1, help="git clone depth (default: 1)")
    ap.add_argument(
        "--install",
        default="all",
        help='Install target for isaaclab.sh (default: all). Use "none" to skip.',
    )
    ap.add_argument("--clone-only", action="store_true", help="Only clone (same as --install none).")

    args = ap.parse_args()

    need_bin("git")
    need_bin("bash")

    if not args.path:
        args.path = prompt_required("Enter parent directory (or destination dir)")

    dest = resolve_clone_dest(args.path, repo_dirname="IsaacLab")

    clone_repo(dest, args.repo, args.ref, args.depth)

    install_target = "none" if args.clone_only else args.install
    isaaclab_install(dest, install_target)

    print("[OK] Done.")
    print(f"[hint] IsaacLab dir: {dest}")


if __name__ == "__main__":
    main()
