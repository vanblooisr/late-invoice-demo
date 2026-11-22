"""The SQLite actions table: one row per late invoice, moving forward through its statuses.

The chain is:

    pending       -> approved | rejected
    approved      -> link_created | paid_elsewhere
    link_created  -> booking | paid_elsewhere | amount_mismatch | link_expired
    booking       -> paid | booking_unconfirmed

Terminal statuses (no outgoing edge): rejected, paid, paid_elsewhere, amount_mismatch, link_expired,
booking_unconfirmed.

`booking` is the claim on a row: the one compare-and-set link_created -> booking that a run makes
before it books anything. Only the run that made the claim books, and `paid` is reachable from
`booking` only. A row found in `booking` at the start of a run means an earlier booking attempt
ended without a recorded result; it moves to `booking_unconfirmed`, is reported and is never
booked. `paid_elsewhere` records that the invoice was found paid by another route (from `approved`
in the link stage, from `link_created` in the writeback); the row is never booked and the case is
reported. `amount_mismatch` records a payment whose amount differs from the invoice's open amount;
`link_expired` records a link that ran out unpaid. Neither is booked; both are reported.

Every function that writes (insert_pending, insert_pending_many, set_status, mark_messaged,
set_link) runs in one explicit transaction (BEGIN IMMEDIATE) on a connection that has none open,
and commits before it returns, so the change is on disk and visible to any other connection to
the same file the moment the call returns; nothing is left in an open transaction. A write that
raises, for any reason, rolls back and re-raises, so the connection holds no transaction and no lock.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime

from .money import cents_to_str
from .ports import Invoice

__all__ = [
    "ACTIONS_TABLE",
    "PENDING",
    "APPROVED",
    "REJECTED",
    "LINK_CREATED",
    "PAID",
    "PAID_ELSEWHERE",
    "BOOKING",
    "AMOUNT_MISMATCH",
    "LINK_EXPIRED",
    "BOOKING_UNCONFIRMED",
    "STATUSES",
    "TERMINAL_STATUSES",
    "TRANSITIONS",
    "ActionRow",
    "connect",
    "init_schema",
    "insert_pending",
    "insert_pending_many",
    "get_row",
    "set_status",
    "mark_messaged",
    "set_link",
    "list_rows",
]

ACTIONS_TABLE = "actions"

# The status values, named once; stage code uses these names, never the bare strings.
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
LINK_CREATED = "link_created"
PAID = "paid"
PAID_ELSEWHERE = "paid_elsewhere"
BOOKING = "booking"
AMOUNT_MISMATCH = "amount_mismatch"
LINK_EXPIRED = "link_expired"
BOOKING_UNCONFIRMED = "booking_unconfirmed"
STATUSES = (
    PENDING,
    APPROVED,
    REJECTED,
    LINK_CREATED,
    PAID,
    PAID_ELSEWHERE,
    BOOKING,
    AMOUNT_MISMATCH,
    LINK_EXPIRED,
    BOOKING_UNCONFIRMED,
)
TERMINAL_STATUSES = frozenset(
    {REJECTED, PAID, PAID_ELSEWHERE, AMOUNT_MISMATCH, LINK_EXPIRED, BOOKING_UNCONFIRMED}
)
# Allowed status edges. Terminal statuses are listed with no outgoing edge, so every status is a key
# and an edge from a terminal status is refused the same way as any other illegal edge (ValueError).
TRANSITIONS: dict[str, frozenset[str]] = {
    PENDING: frozenset({APPROVED, REJECTED}),
    APPROVED: frozenset({LINK_CREATED, PAID_ELSEWHERE}),
    LINK_CREATED: frozenset({BOOKING, PAID_ELSEWHERE, AMOUNT_MISMATCH, LINK_EXPIRED}),
    BOOKING: frozenset({PAID, BOOKING_UNCONFIRMED}),
    REJECTED: frozenset(),
    PAID: frozenset(),
    PAID_ELSEWHERE: frozenset(),
    AMOUNT_MISMATCH: frozenset(),
    LINK_EXPIRED: frozenset(),
    BOOKING_UNCONFIRMED: frozenset(),
}


@dataclass(frozen=True)
class ActionRow:
    """One row of the actions table.

    Amounts are EUR integer cents; the demo is EUR-only, so there is no currency column (the fetch
    stage refuses any invoice whose currency is not EUR). `amount_cents` is the invoice total and
    `open_amount_cents` is what was still unpaid on it when the row was recorded (Invoice.amount_cents
    and Invoice.open_amount_cents at insert); the two differ on a partly paid invoice, and the
    approval message shows both. The stored open amount is a snapshot for that message: the link and
    writeback stages read the live open amount from the port. `id` is the row key every stage uses to
    name a row: it travels in Telegram callback_data and seeds the Mollie idempotency key.
    `invoice_id` is unique, so a second fetch of the same invoice finds the existing row. `due_date`
    is the invoice's due date as a naive calendar date, copied from Invoice.due_date at insert; the
    proposal text counts the days late from it. The three datetime fields are UTC, timezone-aware,
    or None.
    """

    id: int
    invoice_id: str
    invoice_number: str
    amount_cents: int
    open_amount_cents: int
    due_date: date
    status: str
    messaged_at: datetime | None
    payment_link_id: str | None
    payment_link_url: str | None
    created_at: datetime
    updated_at: datetime


# Column order of a SELECT that feeds _row_from; ActionRow's field order follows it.
_COLUMNS = (
    "id, invoice_id, invoice_number, amount_cents, open_amount_cents, due_date, status, "
    "messaged_at, payment_link_id, payment_link_url, created_at, updated_at"
)


def _now() -> str:
    """The current moment as a UTC ISO 8601 string, the stored form of every timestamp."""
    return datetime.now(UTC).isoformat()


def _utc_text(moment: datetime) -> str:
    """A timezone-aware datetime as a UTC ISO 8601 string; a naive one is refused."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("a timestamp must be timezone-aware")
    return moment.astimezone(UTC).isoformat()


@contextmanager
def _write_transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Run the block in one explicit transaction: BEGIN IMMEDIATE, then COMMIT, or ROLLBACK on any exception.

    Independent of the connection's mode: the BEGIN is issued here, so it holds on a connection in
    autocommit mode as on one with implicit transactions. A connection that already has a transaction
    open is refused with RuntimeError before anything runs, so the caller's transaction is never
    committed or rolled back from under it. On any BaseException the rollback leaves no transaction
    and no lock open, and the exception propagates.
    """
    if conn.in_transaction:
        raise RuntimeError("a write needs a connection with no transaction open")
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def _parse_utc(text: str) -> datetime:
    """Read a stored timestamp back as a UTC, timezone-aware datetime."""
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError("a stored timestamp lacks its timezone")
    return moment.astimezone(UTC)


def _row_from(values: tuple) -> ActionRow:
    """Build an ActionRow from one row of a SELECT over _COLUMNS."""
    (
        row_id,
        invoice_id,
        invoice_number,
        amount_cents,
        open_amount_cents,
        due_date,
        status,
        messaged_at,
        payment_link_id,
        payment_link_url,
        created_at,
        updated_at,
    ) = values
    return ActionRow(
        id=row_id,
        invoice_id=invoice_id,
        invoice_number=invoice_number,
        amount_cents=amount_cents,
        open_amount_cents=open_amount_cents,
        due_date=date.fromisoformat(due_date),
        status=status,
        messaged_at=None if messaged_at is None else _parse_utc(messaged_at),
        payment_link_id=payment_link_id,
        payment_link_url=payment_link_url,
        created_at=_parse_utc(created_at),
        updated_at=_parse_utc(updated_at),
    )


def connect(path: str) -> sqlite3.Connection:
    """Open the database file at `path` in autocommit mode (isolation_level None).

    The write functions open and close their own transactions explicitly, so no implicit BEGIN is
    wanted from the sqlite3 module.
    """
    return sqlite3.connect(path, isolation_level=None)


def init_schema(conn: sqlite3.Connection) -> None:
    """Create the actions table if it does not exist."""
    # The status list comes from the module's own constants, never from input.
    allowed = ", ".join(f"'{status}'" for status in STATUSES)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ACTIONS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT NOT NULL UNIQUE,
            invoice_number TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0),
            open_amount_cents INTEGER NOT NULL CHECK (open_amount_cents >= 0),
            due_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ({allowed})),
            messaged_at TEXT,
            payment_link_id TEXT,
            payment_link_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _insert_pending_row(conn: sqlite3.Connection, invoice: Invoice, now: str) -> int | None:
    """Validate the invoice and INSERT a pending row; the id of the new row, or None when one exists.

    Does not commit: the caller owns the transaction.
    """
    cents_to_str(invoice.amount_cents)  # the one money rule: int cents, not bool, not negative
    cents_to_str(invoice.open_amount_cents)
    if type(invoice.due_date) is not date:
        raise ValueError("due_date must be a calendar date")
    cursor = conn.execute(
        f"INSERT INTO {ACTIONS_TABLE} (invoice_id, invoice_number, amount_cents, open_amount_cents, "
        "due_date, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT (invoice_id) DO NOTHING",
        (
            invoice.id,
            invoice.invoice_number,
            invoice.amount_cents,
            invoice.open_amount_cents,
            invoice.due_date.isoformat(),
            PENDING,
            now,
            now,
        ),
    )
    return cursor.lastrowid if cursor.rowcount == 1 else None


def _read_inserted(conn: sqlite3.Connection, row_id: int) -> ActionRow:
    """Read back a row this transaction just inserted; a missing one rolls the write back."""
    row = get_row(conn, row_id)
    if row is None:
        raise RuntimeError(f"the row inserted as id {row_id} could not be read back")
    return row


def insert_pending(conn: sqlite3.Connection, invoice: Invoice) -> ActionRow | None:
    """Record a pending row for an invoice. Returns None when a row for that invoice already exists.

    The row takes invoice_number, the total amount_cents, the open_amount_cents and due_date from
    the invoice. Commits before returning. An amount that is not integer cents (a float, a bool, a
    negative) or a due_date that is not a plain date raises ValueError and writes nothing; any other
    failure rolls back and re-raises.
    """
    with _write_transaction(conn):
        inserted_id = _insert_pending_row(conn, invoice, _now())
        return None if inserted_id is None else _read_inserted(conn, inserted_id)


def insert_pending_many(conn: sqlite3.Connection, invoices: list[Invoice]) -> list[ActionRow]:
    """Record a pending row for every invoice that has none, in one transaction.

    All rows land or none: any error (an invalid invoice, a database failure) rolls the whole batch
    back and is re-raised, and the connection is left outside a transaction. Returns only the rows
    newly inserted, in input order; an invoice that already has a row (or that repeats an earlier one
    in the list) is skipped. An empty list is a no-op. Commits once before returning. Each invoice
    is checked as insert_pending checks it.
    """
    if not invoices:
        return []
    now = _now()
    with _write_transaction(conn):
        inserted_ids = [
            row_id for invoice in invoices if (row_id := _insert_pending_row(conn, invoice, now)) is not None
        ]
        return [_read_inserted(conn, row_id) for row_id in inserted_ids]


def get_row(conn: sqlite3.Connection, action_id: int) -> ActionRow | None:
    """Return the row with this id, or None when there is no such row."""
    found = conn.execute(
        f"SELECT {_COLUMNS} FROM {ACTIONS_TABLE} WHERE id = ?", (action_id,)
    ).fetchone()
    return None if found is None else _row_from(found)


def set_status(conn: sqlite3.Connection, invoice_id: str, expected: str, new: str) -> bool:
    """Compare-and-set a row's status; only edges in TRANSITIONS are allowed.

    One UPDATE ... WHERE invoice_id = ? AND status = ?, so the check and the write are one
    statement. An unknown status or an edge not in TRANSITIONS raises ValueError before any write.
    False means only that the row did not hold `expected` (a lost race); True means it moved.
    Commits before returning, also when it returns False.

    The claim on a row before booking is this call with expected=LINK_CREATED, new=BOOKING: of two
    runs that race for the same row, exactly one gets True.
    """
    if expected not in TRANSITIONS or new not in STATUSES:
        raise ValueError(f"unknown status in {expected!r} -> {new!r}")
    if new not in TRANSITIONS[expected]:
        raise ValueError(f"the edge {expected!r} -> {new!r} is not allowed")
    with _write_transaction(conn):
        cursor = conn.execute(
            f"UPDATE {ACTIONS_TABLE} SET status = ?, updated_at = ? WHERE invoice_id = ? AND status = ?",
            (new, _now(), invoice_id, expected),
        )
        moved = cursor.rowcount == 1
    return moved


def mark_messaged(conn: sqlite3.Connection, action_id: int, at: datetime) -> bool:
    """Record that the proposal for this row was sent at `at` (UTC, timezone-aware).

    One UPDATE ... WHERE id = ? AND messaged_at IS NULL. False means the row was already marked
    or does not exist; True means it was marked now. Commits before returning.
    """
    stamp = _utc_text(at)
    with _write_transaction(conn):
        cursor = conn.execute(
            f"UPDATE {ACTIONS_TABLE} SET messaged_at = ?, updated_at = ? WHERE id = ? AND messaged_at IS NULL",
            (stamp, _now(), action_id),
        )
        marked = cursor.rowcount == 1
    return marked


def set_link(conn: sqlite3.Connection, action_id: int, link_id: str, link_url: str) -> bool:
    """Store the payment link and move approved -> link_created in one compare-and-set.

    One UPDATE ... SET payment_link_id = ?, payment_link_url = ?, status = 'link_created'
    WHERE id = ? AND status = 'approved', so a row is never link_created without its link, and a
    stored link never sits on a row that is still approved. False means the row did not hold
    approved (a lost race or a repeat); True means it moved. Commits before returning. A link id or
    url that is not a non-blank str raises ValueError before the UPDATE, so no row is ever
    link_created without a usable link.
    """
    for name, value in (("link_id", link_id), ("link_url", link_url)):
        if type(value) is not str or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
    with _write_transaction(conn):
        cursor = conn.execute(
            f"UPDATE {ACTIONS_TABLE} SET payment_link_id = ?, payment_link_url = ?, status = ?, "
            "updated_at = ? WHERE id = ? AND status = ?",
            (link_id, link_url, LINK_CREATED, _now(), action_id, APPROVED),
        )
        moved = cursor.rowcount == 1
    return moved


def list_rows(conn: sqlite3.Connection, status: str | None = None) -> list[ActionRow]:
    """Return all rows, or only those with the given status, ordered by id ascending.

    Returns the whole table on purpose (demo scale).
    """
    if status is None:
        found = conn.execute(f"SELECT {_COLUMNS} FROM {ACTIONS_TABLE} ORDER BY id ASC").fetchall()
    else:
        if status not in STATUSES:
            raise ValueError(f"unknown status {status!r}")
        found = conn.execute(
            f"SELECT {_COLUMNS} FROM {ACTIONS_TABLE} WHERE status = ? ORDER BY id ASC", (status,)
        ).fetchall()
    return [_row_from(values) for values in found]
