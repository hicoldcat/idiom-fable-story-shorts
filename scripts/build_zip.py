#!/usr/bin/env python3
"""把整个技能项目打包成可上传的 zip，输出到 dist/。

- 版本号取自 SKILL.md frontmatter 的 version
- zip 内层是技能同名文件夹（<name>/SKILL.md ...）
- 排除 .git/、dist/、__pycache__/ 等无关内容

用法：
    python scripts/build_zip.py          # 或双击项目根目录的 package.bat
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SKILL_MD = ROOT / "SKILL.md"

# 目录名命中即整棵跳过
EXCLUDE_DIRS = {".git", "dist", "__pycache__", ".idea", ".vscode", ".workbuddy"}
# 文件名命中即跳过（.gitignore / package.bat 属仓库自身，不进分发包）
EXCLUDE_FILES = {".DS_Store", "Thumbs.db", ".gitignore", "package.bat"}
# 后缀命中即跳过
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def read_frontmatter(path: Path) -> dict[str, str]:
    """只取一级 key: value，够用且不依赖 pyyaml。"""
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        return {}
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if not line or line[0] in " \t#":
            continue
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta


def iter_files(base: Path):
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(base)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.name in EXCLUDE_FILES or path.suffix in EXCLUDE_SUFFIXES:
            continue
        yield path, rel


def main() -> int:
    if not SKILL_MD.is_file():
        print(f"[ERROR] 找不到 {SKILL_MD}")
        return 1

    meta = read_frontmatter(SKILL_MD)
    name = meta.get("name") or ROOT.name
    version = meta.get("version") or "0.0.0"

    files = list(iter_files(ROOT))
    if not files:
        print("[ERROR] 没有可打包的文件")
        return 1

    DIST.mkdir(parents=True, exist_ok=True)
    out = DIST / f"{name}-v{version}.zip"

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, rel in files:
            # 统一用正斜杠，zip 内路径不依赖平台
            zf.write(path, f"{name}/{rel.as_posix()}")

    size_kb = out.stat().st_size / 1024
    print(f"[OK] {name} v{version} -> {out}")
    print(f"     {len(files)} 个文件，{size_kb:.1f} KB")
    for _, rel in files:
        print(f"     + {rel.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
