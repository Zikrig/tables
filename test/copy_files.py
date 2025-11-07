import argparse
import os
import shutil
from pathlib import Path


def copy_files(src: Path, dst: Path, recursive: bool = False, overwrite: bool = False) -> int:
    dst.mkdir(parents=True, exist_ok=True)
    copied = 0

    if recursive:
        for root, _, files in os.walk(src):
            rel = Path(root).relative_to(src)
            target_dir = dst / rel
            target_dir.mkdir(parents=True, exist_ok=True)
            for name in files:
                s = Path(root) / name
                d = target_dir / name
                if d.exists() and not overwrite:
                    continue
                shutil.copy2(s, d)
                copied += 1
    else:
        for name in os.listdir(src):
            s = src / name
            if s.is_file():
                d = dst / name
                if d.exists() and not overwrite:
                    continue
                shutil.copy2(s, d)
                copied += 1

    return copied


def main():
    parser = argparse.ArgumentParser(description="Copy files from one subfolder to another")
    parser.add_argument("source", help="Source subfolder path")
    parser.add_argument("dest", help="Destination subfolder path")
    parser.add_argument("--recursive", action="store_true", help="Copy recursively")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    src = Path(args.source)
    dst = Path(args.dest)

    if not src.exists() or not src.is_dir():
        raise SystemExit(f"Source folder not found: {src}")

    total = copy_files(src, dst, recursive=args.recursive, overwrite=args.overwrite)
    print(f"Copied {total} file(s) from '{src}' to '{dst}'")


if __name__ == "__main__":
    main()









