"""Stage 5: runs stages 1 to 4 in order.

Run: lid demo  or  python -m late_invoice_demo.demo
Needs: what stages 1 to 4 need: nothing for fetch with the fake adapter, TELEGRAM_* and
MOLLIE_TEST_KEY in .env, and MONEYBIRD_* in .env with the moneybird adapter.
"""

import argparse
from collections.abc import Callable

from .adapters import ADAPTER_NAMES
from .common.config import DEFAULT_DB_PATH
from .common.entry import StageNotBuilt, parse_or_exit, run_guarded
from .common.mollie import MollieClient


def run(
    args: argparse.Namespace,
    *,
    send: Callable[..., None] | None = None,
    mollie: MollieClient | None = None,
    wait: Callable[[str], str] | None = None,
) -> int:
    """Run stages 1 to 4 in order and return a process exit code.

    The three keyword-only seams let a test drive the whole composition with no network. None means
    "build the real one from settings"; a value replaces it.

    `send(text, callback_prefix=None)`: delivers one Telegram message. With no prefix it is a plain
    message, the shape of the `send=` hooks of link.create_links and writeback.check_payments
    (`Callable[[str], None]`). With a prefix ("<row id>:") the message carries the two buttons, the
    shape approve.send_proposals calls (`Callable[[str, str], None]`). One callable therefore
    serves all three stages.

    `mollie`: a common.mollie.MollieClient, or an object with its three methods
    (create_payment_link, get_payment_link, deactivate_payment_link); the link and writeback stages
    use it directly.

    `wait(link_id)`: blocks until the payment link with that id is paid, the wait timed out, or it
    was cancelled, and returns writeback.WAIT_PAID, writeback.WAIT_TIMED_OUT or
    writeback.WAIT_CANCELLED. The default is writeback.wait_for_payment on the `mollie` in use. On
    anything but WAIT_PAID the row stays link_created and nothing is booked for it.

    How the real run receives the approval taps is not decided here; a `send` double can apply a tap
    through approve.handle_callback.
    """
    raise StageNotBuilt("demo.run is not implemented")


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add this stage's own flags to `parser`."""
    parser.add_argument(
        "--adapter",
        choices=ADAPTER_NAMES,
        default="fake",
        help="bookkeeping adapter: fake reads local fixtures and needs no keys; "
        "moneybird talks to one sandbox administration",
    )
    parser.add_argument(
        "--db",
        default=None,
        help=f"SQLite file for the actions table (default: {DEFAULT_DB_PATH}, resolved via config)",
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point for `python -m late_invoice_demo.demo`."""
    parser = argparse.ArgumentParser(prog="python -m late_invoice_demo.demo")
    add_arguments(parser)
    r = parse_or_exit(parser, argv)
    if isinstance(r, int):
        return r
    return run_guarded(run, r, parser.prog)


if __name__ == "__main__":
    raise SystemExit(main())
