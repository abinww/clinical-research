"""Clinical-research 2.0 filesystem layout and filename rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


EXCLUDED_NAMES = frozenset({"indication", "attachments", "temp", ".temp"})
WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)
FORBIDDEN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def is_valid_filename(name: str) -> bool:
    """Return whether *name* is safe as one Windows path component."""
    stem = name.split(".", 1)[0].upper()
    return bool(name) and not FORBIDDEN_CHARS.search(name) and not name.endswith((" ", ".")) and stem not in WINDOWS_RESERVED


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """Make one path component Windows-safe without changing valid Unicode."""
    value = FORBIDDEN_CHARS.sub(replacement, name).rstrip(" .")
    if not value:
        value = "untitled"
    if value.split(".", 1)[0].upper() in WINDOWS_RESERVED:
        value = f"_{value}"
    return value


@dataclass(frozen=True)
class DrugLayout:
    research_dir: Path
    company_id: str
    drug_id: str

    @property
    def directory(self) -> Path:
        return self.research_dir / self.company_id / self.drug_id

    @property
    def profile(self) -> Path:
        return self.directory / f"{self.drug_id}.md"

    @property
    def raw(self) -> Path:
        return self.directory / "raw"

    @property
    def summary(self) -> Path:
        return self.directory / "summary"


def discover_drugs(research_dir: str | Path) -> list[DrugLayout]:
    """Discover valid ``company/drug/drug.md`` trees under a research root."""
    root = Path(research_dir)
    found: list[DrugLayout] = []
    if not root.is_dir():
        return found
    for company in sorted(root.iterdir(), key=lambda path: path.name.casefold()):
        if not company.is_dir() or company.name.startswith(".") or company.name.casefold() in EXCLUDED_NAMES:
            continue
        for drug in sorted(company.iterdir(), key=lambda path: path.name.casefold()):
            if (
                drug.is_dir()
                and not drug.name.startswith(".")
                and drug.name.casefold() not in EXCLUDED_NAMES
                and (drug / f"{drug.name}.md").is_file()
            ):
                found.append(DrugLayout(root, company.name, drug.name))
    return found


def persistent_path(path: str | Path, research_dir: str | Path) -> str:
    """Return a stable research-root-relative path using POSIX separators."""
    return Path(path).resolve().relative_to(Path(research_dir).resolve()).as_posix()
