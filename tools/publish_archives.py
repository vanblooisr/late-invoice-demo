#!/usr/bin/env python3
"""Copy logs and reports into archives/ whole, with the value of any secret blanked.

A log is published as it was written. The one thing that changes on the way in is the value of a
secret: it is replaced by a marker, and everything around it stays, so the line still says what
happened. The secret shapes are the ones tools/check_public_tree.py looks for (SECRET_SHAPES in
tools/public_vocabulary.py), so a file this tool has written passes that check's secret rule.

A file with no secret in it is copied byte for byte. A file that is not UTF-8 text stops the run
before anything is written: a file that cannot be read cannot be shown to be clean.

The report prints one line per file with the number of values blanked. It never prints a value.

Usage:
    publish_archives.py --out DIR FILE [FILE ...]

Exit codes: 0 done, 1 a file could not be read as text, 2 usage.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from public_vocabulary import SECRET_SHAPES  # noqa: E402

__all__ = ["MARK", "main", "redact"]

MARK = "[REDACTED]"

# Where a shape carries a name and a value, the name stays and the value goes. Each pattern splits
# a match of the shape with the same name into what is kept and what is blanked.
_KEEP_NAME = {
    "bearer or token header with a value": re.compile(r"^(\S+\s+)(.+)$", re.S),
    "env assignment with a value": re.compile(r"^(.*?[:=]\s*[\"']?)([A-Za-z0-9._:\-]{8,})$", re.S),
}


def redact(text: str) -> tuple[str, int]:
    """Return `text` with every secret value replaced by MARK, and the number replaced."""
    count = 0

    for name, shape in SECRET_SHAPES:
        split = _KEEP_NAME.get(name)

        def blank(match: re.Match[str], split: re.Pattern[str] | None = split) -> str:
            nonlocal count
            count += 1
            parts = split.match(match.group(0)) if split is not None else None
            return f"{parts.group(1)}{MARK}" if parts is not None else MARK

        text = shape.sub(blank, text)
    return text, count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copy logs and reports into archives/, secrets blanked.")
    parser.add_argument("--out", required=True, help="the archives folder to write into")
    parser.add_argument("files", nargs="+", help="the logs and reports to publish")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    prepared: list[tuple[str, bytes, int]] = []
    for name in args.files:
        source = Path(name)
        try:
            raw = source.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"{source.name}: not published: {exc.__class__.__name__}; nothing was written")
            return 1
        redacted, count = redact(text)
        prepared.append((source.name, redacted.encode("utf-8") if count else raw, count))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    total = 0
    for name, data, count in prepared:
        (out / name).write_bytes(data)
        total += count
        print(f"{name}: {count} value(s) blanked")
    print(f"{len(prepared)} file(s) published to {out}; {total} value(s) blanked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
