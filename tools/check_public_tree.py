#!/usr/bin/env python3
"""Check the tree that is about to be uploaded: no secrets, no words that belong elsewhere.

What is scanned: the files git tracks or has staged (`git ls-files` plus the index), so the scan
matches what a commit or an upload carries; a local .env, build output and other ignored files are
never scanned and never block a commit. Without git, every file under the root is scanned except
the virtual environment, caches and binary types. A file that cannot be decoded is reported as a
hit, not skipped: an unscanned file is not a clean file.

Three rules, from tools/public_vocabulary.py so the projector and this check agree:

1. Secrets (SECRET_SHAPES) in every scanned file. A hit prints the rule name and the line number,
   never the matched value.
2. Vocabulary (BANNED_VOCABULARY) in every scanned file except the two tools, whose job is to name
   these words, and the lock file. The list includes the optional extra rules read from a file
   beside the repository; the last line of output says how many of those were loaded.
3. ISO dates everywhere except API-NOTES.md (a record of when a documentation page was read) and
   invoice data under core/tests/ and the package's sample data (invoice dates).

The logs and reports under archives/ are published whole, as they were filed: rules 2 and 3 do not
apply to them, because the words and dates those rules ban are what a log consists of. Rule 1
applies to them like to every other file.

Exit codes: 0 clean, 1 hits found, 2 usage (the root is not a directory or nothing was scanned).

Usage:
    check_public_tree.py [ROOT]            scan ROOT (default: the parent of tools/)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from public_vocabulary import (  # noqa: E402
    BANNED_VOCABULARY,
    ENV_RULE_EXEMPT_PREFIXES,
    ISO_DATE,
    LOCAL_VOCABULARY,
    SECRET_SHAPES,
)

SKIP_DIRS = {".venv", "venv", "__pycache__", ".pytest_cache", ".git", ".mypy_cache", ".ruff_cache"}
BINARY_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".whl", ".fods"}
MAX_BYTES = 5_000_000

# Files whose job is to name the banned words.
VOCABULARY_EXEMPT = {"tools/check_public_tree.py", "tools/public_vocabulary.py", "tools/project_public_plan.py"}
# Files that carry dates by design.
DATE_EXEMPT_FILES = {"API-NOTES.md", ".secrets.baseline"}
DATE_EXEMPT_PREFIXES = ("core/tests/", "core/late_invoice_demo/adapters/sample_data/")
# Folders published whole: the filed logs and reports. Only the secret rule scans them.
PUBLISHED_WHOLE_PREFIXES = ("archives/",)
# Files that carry long hashes or pins the long-run rule would flag.
LONG_RUN_EXEMPT = {"requirements.lock", ".secrets.baseline", ".pre-commit-config.yaml"}


def git_files(root: Path) -> list[Path] | None:
    """Return the tracked and staged files under root, or None when git is not usable here."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root, capture_output=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    names = [n for n in out.decode("utf-8", errors="replace").split("\0") if n]
    return [root / n for n in names]


def walk_files(root: Path) -> list[Path]:
    """Return every file under root, skipping environments, caches and git internals (relative parts only)."""
    out = []
    for path in root.rglob("*"):
        rel_parts = path.relative_to(root).parts
        if any(p in SKIP_DIRS or p.endswith(".egg-info") for p in rel_parts):
            continue
        if path.is_file():
            out.append(path)
    return out


def scan(root: Path) -> tuple[list[str], int]:
    files = git_files(root)
    if files is None:
        files = walk_files(root)
    hits: list[str] = []
    scanned = 0
    for path in files:
        if not path.is_file() or path.suffix.lower() in BINARY_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        try:
            if path.stat().st_size > MAX_BYTES:
                hits.append(f"{rel}: unscanned: larger than {MAX_BYTES} bytes")
                continue
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            hits.append(f"{rel}: unscanned: not UTF-8 text (re-save as UTF-8 or add the type to BINARY_SUFFIXES)")
            continue
        except OSError as exc:
            hits.append(f"{rel}: unscanned: {exc.__class__.__name__}")
            continue
        scanned += 1
        lines = text.splitlines()
        for name, rx in SECRET_SHAPES:
            if name == "long token-like run" and rel in LONG_RUN_EXEMPT:
                continue
            if name == "env assignment with a value" and rel.startswith(ENV_RULE_EXEMPT_PREFIXES):
                continue
            for i, line in enumerate(lines, 1):
                if rx.search(line):
                    hits.append(f"{rel}:{i}: secret: {name}")
        if rel.startswith(PUBLISHED_WHOLE_PREFIXES):
            continue
        if rel not in VOCABULARY_EXEMPT and rel != "requirements.lock":
            for name, rx in BANNED_VOCABULARY:
                for i, line in enumerate(lines, 1):
                    if rx.search(line):
                        hits.append(f"{rel}:{i}: vocabulary: {name}")
        if rel not in DATE_EXEMPT_FILES and not rel.startswith(DATE_EXEMPT_PREFIXES):
            for i, line in enumerate(lines, 1):
                if ISO_DATE.search(line):
                    hits.append(f"{rel}:{i}: vocabulary: iso date")
    return hits, scanned


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parent.parent
    if not root.is_dir():
        print(f"usage: not a directory: {root}", file=sys.stderr)
        return 2
    hits, scanned = scan(root)
    if scanned == 0:
        print(f"usage: nothing scanned under {root}", file=sys.stderr)
        return 2
    for h in hits:
        print(h)
    print(
        f"{'clean' if not hits else str(len(hits)) + ' hit(s)'}: {scanned} file(s) scanned under {root}; "
        f"extra word-list rules loaded: {len(LOCAL_VOCABULARY)}"
    )
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
