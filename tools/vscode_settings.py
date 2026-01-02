#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in {path}: {e}")


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


def as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def is_isaaclab_repo(path: Path) -> bool:
    return (path / "isaaclab.sh").exists() or (path / ".git").exists()


def resolve_isaaclab_root(user_input: str, repo_dirname: str = "IsaacLab") -> Path:
    p = Path(user_input).expanduser().resolve()

    if p.exists() and p.is_dir() and is_isaaclab_repo(p):
        return p

    if p.exists() and p.is_dir():
        return (p / repo_dirname).resolve()

    return p


def prompt_required(prompt_text: str) -> str:
    if not sys.stdin.isatty():
        raise RuntimeError(
            "Missing required path argument and cannot prompt (non-interactive stdin). "
            "Please pass the path explicitly, e.g.:\n"
            "  pixi run vscode-config -- /home/.../\n"
            "or\n"
            "  pixi run vscode-config -- /home/.../IsaacLab"
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


def unique_norm_paths(paths: list[str]) -> list[str]:
    """Deduplicate while preserving order, normalizing via Path()."""
    seen = set()
    out: list[str] = []
    for p in paths:
        sp = str(Path(p))
        if sp not in seen:
            seen.add(sp)
            out.append(p)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Patch .vscode/settings.json for pixi + IsaacLab (+unitree_rl_lab)")
    ap.add_argument(
        "path",
        nargs="?",
        help="Either IsaacLab root or a parent directory that contains IsaacLab/",
    )
    ap.add_argument(
        "--workspace",
        default=".",
        help="VSCode workspace root (default: .)",
    )
    ap.add_argument(
        "--unitree-root",
        default=None,
        help=(
            "Optional: root directory that contains unitree_rl_lab/. "
            "Default: sibling of IsaacLab root (i.e., <IsaacLab parent>/unitree_rl_lab)."
        ),
    )
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    settings_path = workspace / ".vscode" / "settings.json"

    if not args.path:
        args.path = prompt_required("Enter IsaacLab root (or parent directory)")

    isaaclab_root = resolve_isaaclab_root(args.path, repo_dirname="IsaacLab")
    source_dir = (isaaclab_root / "source").resolve()

    # ✅ unitree_rl_lab 기본 위치: <IsaacLab parent>/unitree_rl_lab
    unitree_root = (
        Path(args.unitree_root).expanduser().resolve()
        if args.unitree_root
        else (isaaclab_root.parent / "unitree_rl_lab").resolve()
    )

    # IsaacLab 쪽: source 아래에서 찾을 것들
    wanted = [
        "isaaclab",
        "isaaclab_assets",
        "isaaclab_mimic",
        "isaaclab_rl",
        "isaaclab_tasks",
        "third_party/rsl_rl",
    ]

    # ✅ unitree_rl_lab
    unitree_wanted_abs = [
        (unitree_root / "unitree_rl_lab" / "source" / "unitree_rl_lab").resolve()
    ]

    isaac_candidates = [(source_dir / name).resolve() for name in wanted]
    all_candidates = isaac_candidates + unitree_wanted_abs

    missing = [p for p in all_candidates if not p.exists()]
    present = [p for p in all_candidates if p.exists()]

    if not any(p in present for p in isaac_candidates):
        raise RuntimeError(
            f"No expected IsaacLab source packages found under: {source_dir}\n"
            f"Expected at least one of: {', '.join(wanted)}"
        )

    settings = load_json(settings_path)

    settings["python.defaultInterpreterPath"] = "${workspaceFolder}/.pixi/envs/default/bin/python"

    # Merge extraPaths (keep existing + add present ones)
    extra_paths = as_list(settings.get("python.analysis.extraPaths"))
    norm_existing = {str(Path(p)) for p in extra_paths}

    for p in present:
        sp = str(p)
        if sp not in norm_existing:
            extra_paths.append(sp)
            norm_existing.add(sp)

    settings["python.analysis.extraPaths"] = unique_norm_paths(extra_paths)
    settings["python.analysis.autoSearchPaths"] = True
    settings["python.analysis.indexing"] = True

    save_json(settings_path, settings)

    print("[OK] VSCode settings updated:")
    print(f" - {settings_path}")
    print(f" - python.defaultInterpreterPath = {settings['python.defaultInterpreterPath']}")
    print(" - added extraPaths:")
    for p in present:
        print(f"   - {p}")

    # 경고는 보기 좋게 분리
    if missing:
        print("[warn] Not found (skipped):")
        for p in missing:
            print(f"   - {p}")
        print("[hint] If unitree_rl_lab is elsewhere, pass --unitree-root /path/to/unitree_rl_lab")


if __name__ == "__main__":
    main()
