"""The bookkeeping port: the one interface the stages use to reach a bookkeeping system."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol, runtime_checkable

__all__ = [
    "Invoice",
    "PaymentReceipt",
    "Contact",
    "BookkeepingPort",
    "PaymentOutcomeUnknown",
    "PaymentReplyUnusable",
]


class PaymentOutcomeUnknown(RuntimeError):
    """The booking request failed or was answered with an unexpected status.

    The payment may or may not exist on the bookkeeping side. The caller must check before it
    books again: booking a second time could pay the invoice twice.
    """


class PaymentReplyUnusable(RuntimeError):
    """The bookkeeping system confirmed the payment (a 201 reply) but the reply cannot be used.

    The reply is not valid JSON or carries no payment id. The payment IS registered; only its id
    is unknown. Booking again would pay the invoice twice.
    """


@dataclass(frozen=True)
class Invoice:
    """A sales invoice as the stages see it. Amounts are integer cents.

    `id` is the vendor's primary key: what get_invoice takes and what the actions table stores as
    invoice_id. `invoice_number` is the printed number. `amount_cents` is the invoice total;
    `open_amount_cents` is what is still unpaid on it (the total minus payments already
    registered): below the total on a partly paid invoice, 0 on a fully paid one. The payment link
    charges the open amount and the writeback compares the paid amount with the open amount. `state` is the vendor's own invoice state
    as a string (for example "late", "paid") and is not the actions table's status. Datetime
    fields are UTC, timezone-aware; due_date is a naive calendar date as the bookkeeping system
    reports it.
    """

    id: str
    invoice_number: str
    contact_id: str
    contact_name: str = field(repr=False)
    amount_cents: int
    open_amount_cents: int
    currency: str
    due_date: date
    state: str


@dataclass(frozen=True)
class PaymentReceipt:
    """Confirmation that a payment was registered against an invoice. `paid_at` is UTC, timezone-aware."""

    id: str
    invoice_id: str
    amount_cents: int
    paid_at: datetime


@dataclass(frozen=True)
class Contact:
    """A customer record."""

    id: str
    name: str = field(repr=False)
    email: str | None = field(repr=False)


@runtime_checkable
class BookkeepingPort(Protocol):
    """One port, four verbs.

    fetch and link read through it, writeback writes through it, approve never touches it.
    "Late" means invoices the bookkeeping system itself reports as late (its own late state), not
    a due-date computed here.
    """

    def list_late_invoices(self) -> list[Invoice]:
        """Return the invoices the bookkeeping system itself reports as late (its own late state)."""
        ...

    def get_invoice(self, invoice_id: str) -> Invoice:
        """Return one invoice by id."""
        ...

    def register_payment(
        self, invoice_id: str, amount_cents: int, paid_at: datetime
    ) -> PaymentReceipt:
        """Book a payment against an invoice."""
        ...

    def get_contact(self, contact_id: str) -> Contact:
        """Return one contact by id.

        Optional by convention: an adapter that does not support it raises UnsupportedVerb; the
        Protocol lists it so the signature is fixed.
        """
        ...
