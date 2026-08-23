"""List raw Markdown files not referenced by a summary."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from config import configured_path, read_config  # noqa: E402
from scan_sources import processed_sources, raw_sources  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="找出未被摘要的 raw/ 文件")
    parser.add_argument("--config", type=Path, default=SCRIPT_DIR.parent / "config.yaml")
    args = parser.parse_args()

    try:
        config = read_config(args.config)
        raw_dir = configured_path(config, "raw_dir")
        summary_dir = configured_path(config, "summary_dir")
    except (OSError, ValueError) as exc:
        print(f"[ERROR] 无法读取配置: {exc}", file=sys.stderr)
        return 1

    print("扫描目录:")
    print(f"  raw_dir: {raw_dir}")
    print(f"  summary_dir: {summary_dir}")
    print()

    processed = processed_sources(summary_dir)
    print(f"已摘要文件数: {len(processed)}")
    print()
    print("未处理的 raw 文件:")
    pending = [source for _, source in raw_sources(raw_dir) if source not in processed]
    for source in pending:
        print(f"  {source}")
    print()
    print(f"总计: {len(pending)} 个文件待处理")
    if not pending:
        print("raw/ 目录下无新增文件需要处理")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
