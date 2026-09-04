"""Clinical-research 2.0 filesystem layout and filename rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


EXCLUDED_NAMES = frozenset({"indication", "attachments", "temp", "raw", "summary", "drug", "trials"})
WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)
FORBIDDEN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
IDENTIFIER = re.compile(r"^[^\W_](?:[\w. -]{0,78}[\w.-])?$", re.UNICODE)


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


def is_valid_identifier(name: str) -> bool:
    """Return whether a company/drug ID is safe for Windows and Markdown links."""
    return is_valid_filename(name) and bool(IDENTIFIER.fullmatch(name))


@dataclass(frozen=True)
class DrugLayout:
    research_dir: Path
    company_id: str
    drug_id: str

    @property
    def company_dir(self) -> Path:
        return self.research_dir / self.company_id

    @property
    def profile(self) -> Path:
        return self.company_dir / f"{self.drug_id}.md"

    @property
    def raw(self) -> Path:
        return self.company_dir / "raw"

    @property
    def summary(self) -> Path:
        return self.company_dir / "summary"


def discover_drugs(research_dir: str | Path, rejected: list[Path] | None = None) -> list[DrugLayout]:
    """Discover valid ``company/{drug_id}.md`` drug pages under a research root."""
    root = Path(research_dir).resolve()
    found: list[DrugLayout] = []
    if not root.is_dir():
        return found
    for company in sorted(root.iterdir(), key=lambda path: path.name.casefold()):
        if company.is_dir() and not is_contained(company, root):
            if rejected is not None:
                rejected.append(company)
            continue
        if (
            not _contained_directory(company, root)
            or company.name.startswith(".")
            or company.name.casefold() in EXCLUDED_NAMES
            or not is_valid_identifier(company.name)
        ):
            if (
                rejected is not None
                and company.is_dir()
                and not company.name.startswith(".")
                and company.name.casefold() not in EXCLUDED_NAMES
                and not is_valid_identifier(company.name)
            ):
                rejected.append(company)
            continue
        for profile in sorted(company.glob("*.md")):
            if not profile.is_file() or not is_contained(profile, root):
                continue
            drug_name = profile.name[:-3]
            if not drug_name or not is_valid_identifier(drug_name):
                continue
            found.append(DrugLayout(root, company.name, drug_name))
    return found


def is_contained(path: str | Path, root: str | Path) -> bool:
    """Return whether a path resolves within root (including the root itself)."""
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (OSError, ValueError):
        return False


def _contained_directory(path: Path, root: Path) -> bool:
    return path.is_dir() and is_contained(path, root)


def persistent_path(path: str | Path, research_dir: str | Path) -> str:
    """Return a stable research-root-relative path using POSIX separators."""
    return Path(path).resolve().relative_to(Path(research_dir).resolve()).as_posix()
