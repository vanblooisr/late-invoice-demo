"""Bookkeeping adapters that satisfy BookkeepingPort: one real vendor (Moneybird) and a local fake for tests and demos."""

from .fake import FakeBookkeeping
from .moneybird import MoneybirdAdapter

__all__ = ["ADAPTER_NAMES", "FakeBookkeeping", "MoneybirdAdapter"]

ADAPTER_NAMES: tuple[str, ...] = ("fake", "moneybird")
