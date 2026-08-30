from pathlib import Path


def find_repo_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "apps" / "api" / "pyproject.toml").exists():
            return candidate
    return Path.cwd()


def default_review_output() -> Path:
    return find_repo_root() / "data" / "reviews"
