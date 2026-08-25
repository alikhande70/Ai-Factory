from __future__ import annotations

from dataclasses import dataclass

from .backend import BookingRequest, BookingService
from .db import BookingRecord


@dataclass(frozen=True)
class BookingForm:
    customer_name: str
    slot: str


def submit_booking(form: BookingForm, service: BookingService) -> BookingRecord:
    """UI-facing adapter: transforms form state into the backend request contract."""

    return service.create_booking(
        BookingRequest(customer_name=form.customer_name, slot=form.slot)
    )
