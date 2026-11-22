"""The Mollie payment-link client: the payment vendor the link and writeback stages talk to directly.

The stages reach the bookkeeping system through the port and Telegram through the approve stage;
Mollie is the one vendor with a direct client. Links are created in test mode only: the constructor
refuses any key that does not start with `test_`, and config refuses the same key earlier, so a
live key cannot reach this client by either route. Amounts cross the wire as the two-decimal
string common/money.py produces and come back as integer cents; a value with another number of
decimals is unrecognised and raises MollieError (fail closed). Field names on the wire are those
recorded in API-NOTES.md.

Errors: an error reply or an unrecognised reply raises MollieError; a connection or timeout failure
raises the transport's own exception (httpx), which the one retry policy in common/retry.py knows.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from .entry import StageNotBuilt

__all__ = ["MOLLIE_API", "LINK_LIFETIME", "MollieError", "PaymentLink", "MollieClient"]

MOLLIE_API = "https://api.mollie.com/v2"
# How long a new payment link stays payable when the caller gives no expiry: a stale link for an
# invoice that was settled another way ends on its own.
LINK_LIFETIME = timedelta(days=14)


class MollieError(RuntimeError):
    """Raised for an error reply from Mollie or a reply the client does not recognise (fail closed)."""


@dataclass(frozen=True)
class PaymentLink:
    """A payment link as the stages see it: integer cents, UTC-aware datetimes, never the vendor's JSON.

    `paid_at` and `paid_amount_cents` are both None until the link is paid and both set once it is;
    the constructor refuses one without the other (MollieError), so a half-read reply cannot look
    half paid. `amount_cents` is the amount the link asks for; `paid_amount_cents` is what was paid,
    read from the link's payments, which is why the two are separate fields. EUR only: a link or
    payment in another currency is unrecognised.
    """

    id: str
    url: str
    amount_cents: int
    paid_at: datetime | None
    paid_amount_cents: int | None
    expires_at: datetime | None

    def __post_init__(self) -> None:
        if (self.paid_at is None) != (self.paid_amount_cents is None):
            raise MollieError("a payment link is paid with both a time and an amount, or neither")


class MollieClient:
    """Creates, reads and archives payment links for one test API key.

    One httpx client for the client's lifetime (built from `transport` when given, so tests answer
    requests without a network); close() releases it, and the class is a context manager. The key
    is sent only as the Authorization header, never in a URL, a body, an error message or repr.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = MOLLIE_API,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not api_key.startswith("test_"):
            raise ValueError("MollieClient takes a test API key (test_...)")
        self._api_key = api_key
        self.base_url = base_url
        self._transport = transport
        self.timeout = timeout

    def close(self) -> None:
        """Release the underlying HTTP client."""
        raise StageNotBuilt("mollie.close is not implemented")

    def __enter__(self) -> "MollieClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"MollieClient(base_url={self.base_url!r})"

    def create_payment_link(
        self,
        amount_cents: int,
        description: str,
        *,
        expires_at: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> PaymentLink:
        """POST a new payment link and return it.

        `amount_cents` is sent as {"currency": "EUR", "value": "<two decimals>"}; `description` is
        what the customer sees (at most 255 characters). `expires_at` defaults to now + LINK_LIFETIME
        and is sent as an ISO 8601 UTC string; a caller that retries must pass the same value (the link
        stage derives it from the row's creation time), since Mollie answers 400 when a reused
        idempotency key arrives with a different body. The
        `idempotency_key`, when given, travels as the Idempotency-Key header: within Mollie's one-hour
        window a retried POST with the same key and body returns the same link instead of a second one.
        """
        raise StageNotBuilt("mollie.create_payment_link is not implemented")

    def get_payment_link(self, link_id: str) -> PaymentLink:
        """GET one payment link by id and return it with its paid state.

        `paid_at` maps from the link's `paidAt`. The paid amount is not on the link object: when
        `paidAt` is set, a second GET to /payment-links/{id}/payments reads it, counting only
        payments whose status is paid; when `paidAt` is null no second request is made and both paid
        fields are None.
        """
        raise StageNotBuilt("mollie.get_payment_link is not implemented")

    def deactivate_payment_link(self, link_id: str) -> None:
        """Archive a payment link so it can no longer be paid.

        Sends PATCH /payment-links/{id} with {"archived": true}; never DELETE, which Mollie refuses
        once the link has been opened or paid.
        """
        raise StageNotBuilt("mollie.deactivate_payment_link is not implemented")
