"""List clinical-research 2.0 raw files not referenced by summaries."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from config import load_config  # noqa: E402
from scan_sources import research_sources  # noqa: E402


def find_unprocessed(research_dir: Path, company_id: str | None = None, drug_id: str | None = None) -> list[str]:
    """Return pending raw identities, optionally filtered by layout roles."""
    raw, processed = research_sources(research_dir)
    pending = []
    for _, source in raw:
        company, drug, *_ = source.split("/")
        if company_id is not None and company != company_id:
            continue
        if drug_id is not None and drug != drug_id:
            continue
        if source not in processed:
            pending.append(source)
    return sorted(pending)


def main() -> int:
    parser = argparse.ArgumentParser(description="找出未被摘要的 clinical-research 2.0 raw 文件")
    parser.add_argument("--config", type=Path, default=SCRIPT_DIR.parent / "config.yaml")
    parser.add_argument("--research-dir", type=Path)
    parser.add_argument("--company-id")
    parser.add_argument("--drug-id")
    parser.add_argument("--quiet", action="store_true", help="只输出持久相对路径")
    args = parser.parse_args()

    try:
        research_dir = args.research_dir.resolve() if args.research_dir else load_config(args.config).research_dir
        pending = find_unprocessed(research_dir, args.company_id, args.drug_id)
    except (OSError, ValueError) as exc:
        print(f"[ERROR] 无法读取配置: {exc}", file=sys.stderr)
        return 1

    if args.quiet:
        for source in pending:
            print(source)
        return 0
    print(f"扫描目录: {research_dir}")
    print("未处理的 raw 文件:")
    for source in pending:
        print(f"  {source}")
    print(f"总计: {len(pending)} 个文件待处理")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
