"""The `lid` command: one subcommand per stage."""

import argparse
from types import ModuleType

from . import __version__, approve, demo, fetch, link, writeback
from .common.entry import EXIT_USAGE, parse_or_exit, run_guarded

_STAGES = (
    ("fetch", fetch),
    ("approve", approve),
    ("link", link),
    ("check", writeback),
    ("demo", demo),
)


def _help_text(module: ModuleType, name: str) -> str:
    """Return the first docstring line of `module` without its leading `Stage N: `.

    Falls back to the command name when the module has no docstring (for example under python -OO).
    """
    lines = (module.__doc__ or "").strip().splitlines()
    if not lines:
        return name
    first = lines[0]
    prefix, sep, rest = first.partition(": ")
    if sep and prefix.startswith("Stage "):
        first = rest
    return first.rstrip(".")


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser with one subparser per stage."""
    parser = argparse.ArgumentParser(prog="lid")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    for name, module in _STAGES:
        # The command is the user's verb; the module is the internal noun.
        aliases = ["writeback"] if name == "check" else []
        stage_parser = sub.add_parser(name, aliases=aliases, help=_help_text(module, name))
        module.add_arguments(stage_parser)
        stage_parser.set_defaults(func=module.run)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the chosen stage; return its exit code."""
    parser = build_parser()
    args = parse_or_exit(parser, argv)
    if isinstance(args, int):
        return args
    if args.command is None:
        parser.print_help()
        return EXIT_USAGE
    return run_guarded(args.func, args, f"{parser.prog} {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
