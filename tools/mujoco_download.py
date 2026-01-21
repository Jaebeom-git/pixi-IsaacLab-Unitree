#!/usr/bin/env python3
import argparse
import os
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_target_dir() -> Path:
    env_dir = os.environ.get("MUJOCO_DIR")
    if env_dir:
        return Path(env_dir)
    return repo_root() / "unitree_mujoco" / "simulate" / "mujoco"


def strip_top_component(path: str) -> str | None:
    parts = PurePosixPath(path).parts
    if len(parts) <= 1:
        return None
    stripped = PurePosixPath(*parts[1:])
    if stripped.is_absolute() or ".." in stripped.parts:
        raise ValueError(f"unsafe path in tar: {path}")
    return str(stripped)


def download_file(url: str, dest: Path) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": "pixi-mujoco-downloader"}
    )
    with urllib.request.urlopen(request) as response:
        status = getattr(response, "status", None)
        if status is not None and status >= 400:
            raise RuntimeError(f"download failed with HTTP {status}")
        with dest.open("wb") as handle:
            shutil.copyfileobj(response, handle)


def extract_strip_top(tar_path: Path, target_dir: Path) -> None:
    with tarfile.open(tar_path, "r:gz") as tar:
        members = []
        for member in tar.getmembers():
            new_name = strip_top_component(member.name)
            if not new_name:
                continue
            member.name = new_name
            if member.issym() or member.islnk():
                if member.linkname:
                    new_link = strip_top_component(member.linkname)
                    if new_link:
                        member.linkname = new_link
            members.append(member)
        tar.extractall(path=target_dir, members=members)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and extract MuJoCo release into unitree_mujoco/simulate/mujoco."
    )
    parser.add_argument(
        "--version",
        default=os.environ.get("MUJOCO_VERSION", "3.4.0"),
        help="MuJoCo release version (default: 3.4.0 or MUJOCO_VERSION).",
    )
    parser.add_argument(
        "--platform",
        default=os.environ.get("MUJOCO_PLATFORM", "linux-x86_64"),
        help="MuJoCo platform string (default: linux-x86_64 or MUJOCO_PLATFORM).",
    )
    parser.add_argument(
        "--target-dir",
        default=str(default_target_dir()),
        help="Extraction directory (default: unitree_mujoco/simulate/mujoco or MUJOCO_DIR).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Extract even if the target directory is not empty.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target_dir = Path(args.target_dir)
    if target_dir.exists() and not target_dir.is_dir():
        print(f"[ERROR] {target_dir} exists and is not a directory", file=sys.stderr)
        return 1
    if target_dir.is_dir() and any(target_dir.iterdir()) and not args.force:
        print(f"[OK] {target_dir} already exists and is not empty")
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)
    tarball = f"mujoco-{args.version}-{args.platform}.tar.gz"
    url = f"https://github.com/google-deepmind/mujoco/releases/download/{args.version}/{tarball}"
    tar_path = Path("/tmp") / tarball

    print(f"[INFO] Downloading {url}")
    if not tar_path.exists():
        try:
            download_file(url, tar_path)
        except Exception as exc:
            print(f"[ERROR] download failed: {exc}", file=sys.stderr)
            return 1

    try:
        extract_strip_top(tar_path, target_dir)
    except Exception as exc:
        print(f"[ERROR] extraction failed: {exc}", file=sys.stderr)
        return 1

    print(f"[OK] Extracted into {target_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
