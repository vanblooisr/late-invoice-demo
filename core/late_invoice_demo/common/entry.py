"""Shared entry-point pieces: exit codes, the stub exception, and the two wrappers every main() uses."""

import argparse
import sys
from collections.abc import Callable, Sequence

__all__ = [
    "EXIT_USAGE",
    "EXIT_NOT_BUILT",
    "StageNotBuilt",
    "UnsupportedVerb",
    "run_guarded",
    "parse_or_exit",
]

EXIT_USAGE = 2
EXIT_NOT_BUILT = 3


class StageNotBuilt(NotImplementedError):
    """Raised by a stage or shared function whose body is not implemented."""


class UnsupportedVerb(NotImplementedError):
    """Raised by an adapter for an optional port verb it does not support.

    Distinct from StageNotBuilt, which means the body is not written.
    """


def run_guarded(func: Callable[[argparse.Namespace], int], args: argparse.Namespace, prog: str) -> int:
    """Call `func(args)`; on StageNotBuilt print one line to stderr and return EXIT_NOT_BUILT.

    The message body is the same on every entry path; the prefix is the invoker's prog.
    """
    try:
        return func(args)
    except StageNotBuilt as exc:
        print(f"{prog}: {exc}", file=sys.stderr)
        return EXIT_NOT_BUILT


def parse_or_exit(
    parser: argparse.ArgumentParser, argv: Sequence[str] | None
) -> argparse.Namespace | int:
    """Parse `argv`; --help, --version and bad arguments come back as an int exit code, not SystemExit."""
    try:
        return parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else EXIT_USAGE
