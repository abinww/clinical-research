"""Read the dependency-free, flat clinical-research configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


def restricted_scalar(value: str, context: str = "scalar") -> str:
    """Parse the one-line scalar subset used by config and frontmatter."""
    value = value.strip()
    if not value:
        return ""
    if value.startswith("#"):
        return ""
    if value[0] == "'":
        result = []
        index = 1
        while index < len(value):
            if value[index] == "'":
                if index + 1 < len(value) and value[index + 1] == "'":
                    result.append("'")
                    index += 2
                    continue
                tail = value[index + 1 :]
                if tail and not re_full_comment(tail):
                    raise ValueError(f"{context} contains text after a quoted scalar")
                return "".join(result)
            result.append(value[index])
            index += 1
        raise ValueError(f"{context} contains an unterminated quoted scalar")
    if value[0] == '"':
        escaped = False
        for index in range(1, len(value)):
            character = value[index]
            if character == '"' and not escaped:
                token = value[: index + 1]
                tail = value[index + 1 :]
                if tail and not re_full_comment(tail):
                    raise ValueError(f"{context} contains text after a quoted scalar")
                try:
                    parsed = json.loads(token)
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise ValueError(f"{context} contains an invalid quoted scalar") from exc
                if not isinstance(parsed, str):
                    raise ValueError(f"{context} must be a string scalar")
                return parsed
            escaped = character == "\\" and not escaped
            if character != "\\":
                escaped = False
        raise ValueError(f"{context} contains an unterminated quoted scalar")

    # In a plain scalar, # starts a comment only when separated by whitespace.
    for index, character in enumerate(value):
        if character == "#" and index > 0 and value[index - 1].isspace():
            return value[:index].rstrip()
    return value


def re_full_comment(tail: str) -> bool:
    stripped = tail.lstrip()
    return len(stripped) < len(tail) and stripped.startswith("#")


def read_config(config_path: str | Path) -> dict[str, str]:
    """Read the 2.0 config, which contains only an absolute research root."""
    config = {}
    with Path(config_path).open("r", encoding="utf-8-sig") as stream:
        for line_number, raw_line in enumerate(stream, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                raise ValueError(f"config.yaml 第 {line_number} 行格式无效")
            key, value = line.split(":", 1)
            key = key.strip()
            if not key or any(character.isspace() for character in key):
                raise ValueError(f"config.yaml 第 {line_number} 行格式无效")
            if key in config:
                raise ValueError(f"config.yaml 包含重复字段: {key}")
            config[key] = restricted_scalar(value, f"config.yaml line {line_number}")
    if not config.get("research_dir", "").strip():
        raise ValueError("config.yaml 缺少 research_dir")
    unexpected = set(config) - {"research_dir"}
    if unexpected:
        raise ValueError(f"config.yaml 包含不支持的字段: {', '.join(sorted(unexpected))}")
    return config


def configured_path(config: dict[str, str], key: str) -> Path:
    value = config.get(key, "").strip()
    if not value:
        raise ValueError(f"config.yaml 缺少 {key}")
    return Path(value).expanduser()


@dataclass(frozen=True)
class ResearchPaths:
    """Paths derived from the single configured research root."""

    research_dir: Path

    @property
    def index(self) -> Path:
        return self.research_dir / "index.md"

    @property
    def indication(self) -> Path:
        return self.research_dir / "indication"

    @property
    def attachments(self) -> Path:
        return self.research_dir / "attachments"

    @property
    def plans(self) -> Path:
        return self.research_dir / ".temp" / "plans"


def load_config(config_path: str | Path) -> ResearchPaths:
    """Load config and require the configured research root to be absolute."""
    path = Path(config_path)
    root = configured_path(read_config(path), "research_dir")
    if not root.is_absolute():
        raise ValueError("config.yaml 的 research_dir 必须是绝对路径")
    return ResearchPaths(root.resolve())
