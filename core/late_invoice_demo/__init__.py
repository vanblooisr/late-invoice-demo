"""late_invoice_demo: a late invoice in Moneybird goes to Telegram for approval, gets a Mollie payment link, and is booked as paid in Moneybird.

Five stage modules: fetch, approve, link, writeback, demo. The `lid` command exposes them as
subcommands (fetch, approve, link, check, demo); check runs writeback.
common/ holds the shared pieces (settings, database, money, redaction, the bookkeeping port).
adapters/ holds the bookkeeping adapters (Moneybird and a local fake).

The command line and its flags are in place; each stage's run() is still a stub.
"""

__version__ = "0.0.1"
