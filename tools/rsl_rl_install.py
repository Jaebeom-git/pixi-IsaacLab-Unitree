#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_RSL_RL_REPO = "https://github.com/leggedrobotics/rsl_rl.git"


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
            "Missing required path argument and cannot prompt (non-interactive stdin).\n"
            "Please pass the path explicitly, e.g.:\n"
            "  pixi run rsl-rl-install -- /home/.../IsaacLab\n"
            "or\n"
            "  pixi run rsl-rl-install -- /home/...   (parent containing IsaacLab)\n"
        )
    s = input(f"{prompt_text}: ").strip()
    if not s:
        raise RuntimeError(
            "No input provided. Please enter a path explicitly (no default is used).\n"
            "Example:\n"
            "  /home/.../IsaacLab\n"
            "  /home/... (parent containing IsaacLab)\n"
        )
    return s


def is_isaaclab_repo(path: Path) -> bool:
    return (path / "isaaclab.sh").exists() or (path / ".git").exists()


def resolve_isaaclab_root(user_input: str, repo_dirname: str = "IsaacLab") -> Path:
    """
    Accept either:
      - IsaacLab repo root (existing)
      - parent directory that contains IsaacLab (existing)
    """
    p = Path(user_input).expanduser().resolve()

    # If user pointed to an existing IsaacLab repo root, just use it.
    if p.exists() and p.is_dir() and is_isaaclab_repo(p) and (p / "isaaclab.sh").exists():
        return p

    # If user gave a directory that is NOT a repo: treat it as parent and look for <parent>/IsaacLab
    if p.exists() and p.is_dir():
        cand = (p / repo_dirname).resolve()
        if cand.exists() and cand.is_dir() and (cand / "isaaclab.sh").exists():
            return cand

    raise RuntimeError(
        f"Could not find IsaacLab repo from: {p}\n"
        f"Expected either:\n"
        f"  - an IsaacLab repo root containing isaaclab.sh, or\n"
        f"  - a parent directory containing {repo_dirname}/isaaclab.sh\n\n"
        f"Tip: run your IsaacLab clone/setup first, then re-run this installer."
    )


def clone_repo(dest: Path, repo: str, ref: str | None, depth: int) -> None:
    if dest.exists() and dest.is_dir():
        # If already looks like a git repo, keep it
        if (dest / ".git").exists():
            print(f"[OK] Repo already exists: {dest}")
            return
        # If exists and non-empty but not a git repo -> refuse
        try:
            next(dest.iterdir())
            raise RuntimeError(
                f"Destination exists and is not empty: {dest}\n"
                f"Choose an empty directory or delete it."
            )
        except StopIteration:
            pass  # empty dir OK

    dest.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "clone", "--depth", str(depth)]
    if ref:
        cmd += ["--branch", ref]
    cmd += [repo, str(dest)]

    print(f"[info] Cloning -> {dest}")
    run(cmd)


def isaaclab_pip(isaaclab_dir: Path, pip_args: str) -> None:
    """
    Run pip inside IsaacLab's configured python environment.
    This uses:
      ./isaaclab.sh -p -m pip <pip_args>
    """
    sh = isaaclab_dir / "isaaclab.sh"
    if not sh.exists():
        raise RuntimeError(f"isaaclab.sh not found: {sh}")

    try:
        sh.chmod(sh.stat().st_mode | 0o111)
    except Exception:
        pass

    cmd = ["bash", "-lc", f'./isaaclab.sh -p -m pip {pip_args}']
    run(cmd, cwd=isaaclab_dir)


def verify_rsl_rl(isaaclab_dir: Path) -> None:
    # Show pip metadata
    try:
        isaaclab_pip(isaaclab_dir, "show rsl-rl-lib")
    except subprocess.CalledProcessError:
        print("[warn] pip show rsl-rl-lib failed (maybe not installed?)")

    # Print import location
    cmd = [
        "bash",
        "-lc",
        r"""./isaaclab.sh -p - <<'PY'
import rsl_rl, pathlib
print("rsl_rl:", pathlib.Path(rsl_rl.__file__).resolve())
PY""",
    ]
    run(cmd, cwd=isaaclab_dir)


def default_rsl_rl_path(isaaclab_dir: Path) -> Path:
    # ✅ 기본 경로: IsaacLab/source/third_party/rsl_rl
    return (isaaclab_dir / "source" / "third_party" / "rsl_rl").resolve()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Install rsl_rl from source (editable) into IsaacLab python env via isaaclab.sh -p -m pip"
    )
    ap.add_argument(
        "path",
        nargs="?",
        help="Either IsaacLab repo root (containing isaaclab.sh) or its parent directory (containing IsaacLab/isaaclab.sh).",
    )

    # Install source options
    group = ap.add_mutually_exclusive_group(required=False)
    group.add_argument(
        "--rsl-rl-path",
        default=None,
        help="Local path to rsl_rl repo (editable install). If omitted, defaults to <IsaacLab>/source/third_party/rsl_rl (if exists).",
    )
    group.add_argument(
        "--clone",
        action="store_true",
        help="Clone rsl_rl from GitHub into <IsaacLab>/source/third_party/rsl_rl (default) and install editable.",
    )

    ap.add_argument(
        "--repo",
        default=DEFAULT_RSL_RL_REPO,
        help="rsl_rl Git repo URL (used with --clone).",
    )
    ap.add_argument(
        "--ref",
        default=None,
        help="rsl_rl git ref (branch/tag). Optional (used with --clone).",
    )
    ap.add_argument(
        "--depth",
        type=int,
        default=1,
        help="rsl_rl git clone depth (default: 1). Used with --clone.",
    )
    ap.add_argument(
        "--clone-dir",
        default=None,
        help="Where to clone rsl_rl parent directory. Default: <IsaacLab>/source/third_party. Used with --clone.",
    )

    ap.add_argument(
        "--clean",
        action="store_true",
        help="Uninstall rsl-rl-lib before installing editable (helps avoid confusion).",
    )
    ap.add_argument(
        "--verify",
        action="store_true",
        help="After install, print pip info and rsl_rl import path.",
    )

    args = ap.parse_args()

    need_bin("bash")
    if args.clone:
        need_bin("git")

    if not args.path:
        args.path = prompt_required("Enter IsaacLab repo root (or its parent directory)")

    isaaclab_dir = resolve_isaaclab_root(args.path, repo_dirname="IsaacLab")
    print(f"[info] IsaacLab dir: {isaaclab_dir}")

    default_path = default_rsl_rl_path(isaaclab_dir)

    # Determine rsl_rl source path
    if args.clone:
        # ✅ 기본 clone parent: <IsaacLab>/source/third_party
        base = (
            Path(args.clone_dir).expanduser().resolve()
            if args.clone_dir
            else (isaaclab_dir / "source" / "third_party").resolve()
        )
        rsl_src = (base / "rsl_rl").resolve()
        clone_repo(rsl_src, args.repo, args.ref, args.depth)
    else:
        if args.rsl_rl_path is None:
            if default_path.exists():
                rsl_src = default_path
                print(f"[info] Using default rsl_rl path: {rsl_src}")
            else:
                raise RuntimeError(
                    f"Default rsl_rl path not found: {default_path}\n"
                    f"Provide --rsl-rl-path explicitly, or run with --clone to clone into this default location.\n"
                    f"Examples:\n"
                    f"  pixi run rsl-rl-install -- {isaaclab_dir} --clone\n"
                    f"  pixi run rsl-rl-install -- {isaaclab_dir} --rsl-rl-path /path/to/rsl_rl\n"
                )
        else:
            rsl_src = Path(args.rsl_rl_path).expanduser().resolve()
            if not rsl_src.exists():
                raise RuntimeError(f"rsl_rl path does not exist: {rsl_src}")

    if args.clean:
        print("[info] Cleaning existing rsl-rl-lib (pip uninstall -y rsl-rl-lib)")
        # If not installed, uninstall returns non-zero; tolerate that.
        try:
            isaaclab_pip(isaaclab_dir, "uninstall -y rsl-rl-lib")
        except subprocess.CalledProcessError:
            print("[warn] uninstall failed (maybe not installed). continuing...")

    print(f"[info] Installing rsl_rl editable from: {rsl_src}")
    isaaclab_pip(isaaclab_dir, f'install -U -e "{rsl_src}"')

    print("[OK] rsl_rl editable install complete.")
    if args.verify:
        verify_rsl_rl(isaaclab_dir)


if __name__ == "__main__":
    main()
