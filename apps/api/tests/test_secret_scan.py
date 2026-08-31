"""Fail if committed examples look like they contain live credentials."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

_AWS_ACCESS_KEY = re.compile(r"AKIA[0-9A-Z]{16}")
_AWS_SECRET = re.compile(
    r"(?i)(aws_secret_access_key|secret_key|secretaccesskey)\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}"
)
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----")

_SCAN_GLOBS = (
    ".env.example",
    "apps/api/.env.example",
    "infra/**/*.tf",
    "infra/**/*.tfvars.example",
    "infra/**/*.md",
    "README.md",
    "apps/api/README.md",
    "apps/web/README.md",
)


def _candidate_files() -> list[Path]:
    found: list[Path] = []
    for pattern in _SCAN_GLOBS:
        found.extend(path for path in REPO.glob(pattern) if path.is_file())
    return sorted(set(found))


def test_example_and_infra_files_do_not_contain_live_secrets() -> None:
    hits: list[str] = []
    for path in _candidate_files():
        text = path.read_text(encoding="utf-8")
        for pattern in (_AWS_ACCESS_KEY, _AWS_SECRET, _PRIVATE_KEY):
            match = pattern.search(text)
            if match:
                hits.append(f"{path.relative_to(REPO)}:{match.group(0)[:24]}")
    assert hits == []
