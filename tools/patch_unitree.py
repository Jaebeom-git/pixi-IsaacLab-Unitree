#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_unitree.py

Purpose
- Patch Unitree robot config file (unitree.py) so you can switch spawn mode:
  * URDF mode  : use UnitreeUrdfFileCfg (uncomment) and comment UnitreeUsdFileCfg
  * USD mode   : use UnitreeUsdFileCfg (uncomment) and comment UnitreeUrdfFileCfg
- Optionally patch UNITREE_ROS_DIR / UNITREE_MODEL_DIR at top of the file.

Key guarantees
- Never "one-line collapse" the spawn blocks.
- Works even if the spawn blocks are currently commented (# spawn=...) or uncommented.
- Produces clean comment style:
    # spawn=...
    #     ...
    # ),
  instead of awkward "        # usd_path=..."
- Creates a .bak backup.

Usage examples
1) URDF mode (recommended if you only want URDF)
    python tools/patch_unitree.py --mode urdf --ros-rel unitree_ros

2) USD mode
    python tools/patch_unitree.py --mode usd --model-rel unitree_model

3) Explicit absolute paths
    python tools/patch_unitree.py --mode urdf --ros-dir /abs/path/unitree_ros
    python tools/patch_unitree.py --mode usd  --model-dir /abs/path/unitree_model

4) Custom unitree.py location
    python tools/patch_unitree.py --mode urdf --unitree-py unitree_rl_lab/source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple, List


# --------------------------
# Path helpers
# --------------------------

def find_repo_root(start: Path) -> Path:
    p = start.resolve()
    for parent in (p, *p.parents):
        if (parent / "pixi.toml").exists():
            return parent
    return p


def resolve_path(root: Path, p: str) -> Path:
    if os.path.isabs(p):
        return Path(p).expanduser().resolve()
    return (root / p).expanduser().resolve()


def normalize_unitree_ros_dir(p: Path) -> Path:
    """
    Some clones create unitree_ros/unitree_ros/... structure.
    If 'p' doesn't contain package.xml but nested 'unitree_ros' does, use nested.
    """
    nested = p / "unitree_ros"
    if p.exists() and nested.is_dir():
        if not (p / "package.xml").exists() and (nested / "package.xml").exists():
            return nested.resolve()
    return p.resolve()


# --------------------------
# Top-level DIR patch
# --------------------------

DIR_ASSIGN_RE = re.compile(
    r'^(?P<indent>[ \t]*)'
    r'(?P<name>UNITREE_(?:ROS|MODEL)_DIR)\s*=\s*'
    r'(?P<q>[\'"])(?P<val>.*?)(?P=q)'
    r'(?P<tail>[ \t]*(#.*)?)$'
)


def replace_dir_assignments(src: str, values: dict) -> str:
    out: List[str] = []
    for ln in src.splitlines(True):
        m = DIR_ASSIGN_RE.match(ln.rstrip("\n"))
        if m and m.group("name") in values:
            indent = m.group("indent")
            name = m.group("name")
            tail = m.group("tail") or ""
            out.append(f'{indent}{name} = "{values[name]}"{tail}\n')
        else:
            out.append(ln)
    return "".join(out)


# --------------------------
# Spawn block switcher
# --------------------------

# Header lines can be commented or not:
#   spawn=UnitreeUrdfFileCfg(
#   # spawn=UnitreeUrdfFileCfg(
SPAWN_HEADER_ANY_RE = re.compile(
    r'^(?P<indent>[ \t]*)'
    r'(?P<prefix>#\s*)?'
    r'spawn\s*=\s*'
    r'(?P<kind>Unitree(?:Urdf|Usd)FileCfg)\s*'
    r'\(\s*$'
)

# Footer line can be commented or not:
#   ),
#   # ),
SPAWN_FOOTER_ANY_RE = re.compile(
    r'^(?P<indent>[ \t]*)'
    r'(?P<prefix>#\s*)?'
    r'\)\s*,\s*$'
)

# Config assignment start:
CFG_START_RE = re.compile(
    r'^(?P<indent>[ \t]*)'
    r'(?P<var>[A-Z0-9_]+_CFG)\s*=\s*UnitreeArticulationCfg\s*\(\s*$'
)


def is_commented(line: str) -> bool:
    return bool(re.match(r'^\s*#', line))


def comment_line(line: str) -> str:
    """
    Make line commented with clean style:
        <indent># <rest>
    If already commented, keep as-is.
    """
    if line.strip() == "":
        return line
    m = re.match(r'^([ \t]*)(.*?)(\r?\n)?$', line)
    if not m:
        return line
    indent, rest, nl = m.group(1), m.group(2), m.group(3) or ""
    if rest.lstrip().startswith("#"):
        return line  # already commented somewhere; don't double-comment
    return f"{indent}# {rest}{nl}"


def uncomment_line(line: str) -> str:
    """
    Uncomment only if comment marker is right after indentation:
        <indent># <rest>  -> <indent><rest>
        <indent>#<rest>   -> <indent><rest>
    Otherwise keep line.
    """
    if line.strip() == "":
        return line
    m = re.match(r'^([ \t]*)#\s?(.*?)(\r?\n)?$', line)
    if not m:
        return line
    indent, rest, nl = m.group(1), m.group(2), m.group(3) or ""
    return f"{indent}{rest}{nl}"


def find_matching_footer(lines: List[str], start_idx: int) -> Optional[int]:
    """
    Find the first SPAWN_FOOTER_ANY_RE after start_idx.
    This assumes spawn blocks are short and well-formed like:
        spawn=UnitreeXxxFileCfg(
            ...
        ),
    """
    for j in range(start_idx + 1, len(lines)):
        if SPAWN_FOOTER_ANY_RE.match(lines[j].rstrip("\n")):
            return j
    return None


def locate_spawn_blocks_within(lines: List[str], block_start: int, block_end: int) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
    """
    Search spawn blocks between [block_start, block_end] inclusive.
    Return (urdf_block, usd_block) as (start_idx, end_idx).
    """
    urdf = None
    usd = None
    i = block_start
    while i <= block_end:
        m = SPAWN_HEADER_ANY_RE.match(lines[i].rstrip("\n"))
        if m:
            kind = m.group("kind")  # UnitreeUrdfFileCfg or UnitreeUsdFileCfg
            j = find_matching_footer(lines, i)
            if j is None or j > block_end:
                i += 1
                continue
            if kind.endswith("UrdfFileCfg") and urdf is None:
                urdf = (i, j)
            elif kind.endswith("UsdFileCfg") and usd is None:
                usd = (i, j)
            i = j + 1
            continue
        i += 1
    return urdf, usd


def switch_spawn_block(lines: List[str], span: Tuple[int, int], enable: bool) -> None:
    """
    enable=True  -> uncomment the entire spawn block cleanly
    enable=False -> comment the entire spawn block cleanly
    """
    s, e = span
    for k in range(s, e + 1):
        if enable:
            lines[k] = uncomment_line(lines[k])
        else:
            lines[k] = comment_line(lines[k])


def find_cfg_block_end(lines: List[str], start_idx: int) -> int:
    """
    Find the end line index for:
        XXX_CFG = UnitreeArticulationCfg(
            ...
        )
    by tracking parentheses nesting, while ignoring parentheses inside strings crudely.
    This is a best-effort line-based approach that works well for this file style.
    """
    depth = 0
    started = False
    for i in range(start_idx, len(lines)):
        ln = lines[i]
        # Very lightweight: count '(' and ')' excluding obvious string literals cases not handled perfectly.
        # Good enough for this config file.
        for ch in ln:
            if ch == "(":
                depth += 1
                started = True
            elif ch == ")":
                depth -= 1
        if started and depth <= 0:
            return i
    return len(lines) - 1


def patch_spawn_modes(src: str, mode: str) -> Tuple[str, int, int, int]:
    """
    mode in {"urdf", "usd"}
    Returns (new_src, cfg_blocks_seen, urdf_blocks_seen, usd_blocks_seen)
    """
    lines = src.splitlines(True)
    cfg_blocks = 0
    urdf_seen = 0
    usd_seen = 0

    i = 0
    while i < len(lines):
        m = CFG_START_RE.match(lines[i].rstrip("\n"))
        if not m:
            i += 1
            continue

        cfg_blocks += 1
        block_start = i
        block_end = find_cfg_block_end(lines, block_start)

        urdf_span, usd_span = locate_spawn_blocks_within(lines, block_start, block_end)

        if urdf_span:
            urdf_seen += 1
        if usd_span:
            usd_seen += 1

        # Switch logic:
        # - If mode == urdf: enable urdf span, disable usd span
        # - If mode == usd : enable usd span, disable urdf span
        if mode == "urdf":
            if urdf_span:
                switch_spawn_block(lines, urdf_span, enable=True)
            if usd_span:
                switch_spawn_block(lines, usd_span, enable=False)
        else:
            if usd_span:
                switch_spawn_block(lines, usd_span, enable=True)
            if urdf_span:
                switch_spawn_block(lines, urdf_span, enable=False)

        i = block_end + 1

    return "".join(lines), cfg_blocks, urdf_seen, usd_seen


# --------------------------
# Main
# --------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--unitree-py",
        default="unitree_rl_lab/source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py",
        help="Path to unitree.py to patch (relative to repo root unless absolute).",
    )
    ap.add_argument("--mode", choices=["urdf", "usd"], required=True, help="Target spawn mode.")
    ap.add_argument("--repo-root", default=None, help="Repo root (defaults to searching for pixi.toml).")

    # Path patching for DIR constants
    ap.add_argument("--ros-rel", default="unitree_ros", help="Relative path (from repo root) to unitree_ros.")
    ap.add_argument("--model-rel", default="unitree_model", help="Relative path (from repo root) to unitree_model.")
    ap.add_argument("--ros-dir", default=None, help="Absolute path to unitree_ros (overrides --ros-rel).")
    ap.add_argument("--model-dir", default=None, help="Absolute path to unitree_model (overrides --model-rel).")
    ap.add_argument("--write-dirs", action="store_true", help="Actually patch UNITREE_ROS_DIR / UNITREE_MODEL_DIR values.")
    ap.add_argument("--no-backup", action="store_true", help="Do not write .bak backup file.")
    args = ap.parse_args()

    root = Path(args.repo_root).expanduser().resolve() if args.repo_root else find_repo_root(Path.cwd())
    unitree_py = resolve_path(root, args.unitree_py)

    if not unitree_py.exists():
        print(f"[ERROR] unitree.py not found: {unitree_py}", file=sys.stderr)
        return 1

    original = unitree_py.read_text(encoding="utf-8")

    # 1) Spawn mode patch (URDF/USD switching)
    patched, cfg_blocks, urdf_seen, usd_seen = patch_spawn_modes(original, mode=args.mode)

    # 2) Optional DIR constants patch
    if args.write_dirs:
        values = {}

        ros_dir = normalize_unitree_ros_dir(
            Path(args.ros_dir).expanduser().resolve()
            if args.ros_dir else resolve_path(root, args.ros_rel)
        )
        if ros_dir.exists():
            values["UNITREE_ROS_DIR"] = str(ros_dir)
        else:
            print(f"[WARN] unitree_ros not found; skipping UNITREE_ROS_DIR: {ros_dir}", file=sys.stderr)

        # Only patch model dir if mode is usd OR user provided model-dir/--write-dirs explicitly.
        model_dir = (
            Path(args.model_dir).expanduser().resolve()
            if args.model_dir else resolve_path(root, args.model_rel)
        )
        if args.mode == "usd":
            if model_dir.exists():
                values["UNITREE_MODEL_DIR"] = str(model_dir)
            else:
                print(f"[WARN] unitree_model not found; USD mode may fail. Skipping UNITREE_MODEL_DIR: {model_dir}", file=sys.stderr)

        if values:
            patched = replace_dir_assignments(patched, values)

    # Write if changed
    if patched != original:
        if not args.no_backup:
            bak = unitree_py.with_suffix(unitree_py.suffix + ".bak")
            bak.write_text(original, encoding="utf-8")
            print(f"[OK] Backup written: {bak}")

        unitree_py.write_text(patched, encoding="utf-8")
        print(f"[OK] Patched file  : {unitree_py}")
    else:
        print(f"[OK] No changes needed: {unitree_py}")

    # Report
    print(f"[INFO] Mode             : {args.mode}")
    print(f"[INFO] CFG blocks found  : {cfg_blocks}")
    print(f"[INFO] URDF spawn blocks : {urdf_seen}")
    print(f"[INFO] USD  spawn blocks : {usd_seen}")
    if args.mode == "urdf" and urdf_seen == 0:
        print("[WARN] No URDF spawn blocks were detected. Your unitree.py may already be damaged or formatted unexpectedly.", file=sys.stderr)
    if args.mode == "usd" and usd_seen == 0:
        print("[WARN] No USD spawn blocks were detected. Your unitree.py may already be damaged or formatted unexpectedly.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
