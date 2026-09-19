from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_EXCLUDED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "build",
    "data",
    "dist",
    "logs",
    "models",
    "outputs",
    "reports",
    "work",
}
_LOCAL_SECRET_FILES = {".env"}
_SECRET_PATTERNS = (
    ("openai-token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github-token", re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    (
        "credential-assignment",
        re.compile(
            r"(?im)^[ \t]*(?:OPENAI_API_KEY|MARKET_DATA_API_KEY|ALERT_WEBHOOK_URL)"
            r"[ \t]*=[ \t]*[^\r\n#\s]+"
        ),
    ),
)
_REQUIRED_FILES = (
    ".env.example",
    ".gitignore",
    "README.md",
    "SECURITY.md",
    "docs/final-release.md",
)


@dataclass(frozen=True)
class SecurityFinding:
    path: str
    rule: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "rule": self.rule, "detail": self.detail}


@dataclass(frozen=True)
class SecurityReport:
    status: str
    checked_files: int
    findings: tuple[SecurityFinding, ...]
    required_files: tuple[str, ...]
    real_orders_enabled: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "checked_files": self.checked_files,
            "findings": [finding.to_dict() for finding in self.findings],
            "required_files": list(self.required_files),
            "real_orders_enabled": self.real_orders_enabled,
        }


def run_security_checks(root: str | Path) -> SecurityReport:
    """Run repository checks without reading local secret files."""
    root_path = Path(root).resolve()
    findings: list[SecurityFinding] = []
    checked_files = 0

    for path in root_path.rglob("*"):
        if not path.is_file() or _is_excluded(path, root_path):
            continue
        if path.suffix.lower() in {".pyc", ".sqlite", ".sqlite3", ".db", ".png", ".whl"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        checked_files += 1
        relative = path.relative_to(root_path).as_posix()
        for rule, pattern in _SECRET_PATTERNS:
            if pattern.search(content):
                findings.append(
                    SecurityFinding(
                        path=relative,
                        rule=rule,
                        detail=(
                            "Potential credential or private key detected; inspect before release."
                        ),
                    )
                )

    for relative in _REQUIRED_FILES:
        if not (root_path / relative).is_file():
            findings.append(
                SecurityFinding(
                    path=relative,
                    rule="required-file",
                    detail="Required release or security document is missing.",
                )
            )

    gitignore = root_path / ".gitignore"
    if gitignore.is_file():
        ignored = gitignore.read_text(encoding="utf-8")
        if ".env" not in ignored:
            findings.append(
                SecurityFinding(
                    path=".gitignore",
                    rule="secret-ignore",
                    detail=".env must be excluded from version control.",
                )
            )

    return SecurityReport(
        status="ok" if not findings else "failed",
        checked_files=checked_files,
        findings=tuple(findings),
        required_files=_REQUIRED_FILES,
    )


def _is_excluded(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    if any(part in _EXCLUDED_DIRECTORIES for part in relative_parts):
        return True
    filename = path.name
    return filename in _LOCAL_SECRET_FILES or (
        filename.startswith(".env.") and filename != ".env.example"
    )
