"""Small, dependency-free helpers for reading clinical-research config files."""

from __future__ import annotations

import os
from pathlib import Path


def _value(line: str) -> str:
    value = line.split(":", 1)[1].split("#", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value


def read_config(config_path: str | Path) -> dict[str, str]:
    """Read the flat path-only config format used by this skill."""
    config = {}
    with Path(config_path).open("r", encoding="utf-8-sig") as stream:
        for raw_line in stream:
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, _ = line.split(":", 1)
            config[key.strip()] = _value(line)
    return config


def configured_path(config: dict[str, str], key: str) -> Path:
    value = config.get(key, "").strip()
    if not value:
        raise ValueError(f"config.yaml 缺少 {key}")
    return Path(os.path.expanduser(value)).expanduser()
