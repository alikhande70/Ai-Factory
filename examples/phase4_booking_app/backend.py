from __future__ import annotations

from dataclasses import dataclass

from .db import BookingRecord, BookingRepository


@dataclass(frozen=True)
class BookingRequest:
    customer_name: str
    slot: str

    def validate(self) -> None:
        if not self.customer_name.strip():
            raise ValueError("customer_name is required")
        if not self.slot.strip():
            raise ValueError("slot is required")


class BookingService:
    """Minimal backend boundary for the Phase 4 controlled application."""

    def __init__(self, repository: BookingRepository) -> None:
        self.repository = repository

    def create_booking(self, request: BookingRequest) -> BookingRecord:
        request.validate()
        return self.repository.create(
            customer_name=request.customer_name.strip(),
            slot=request.slot.strip(),
        )

    def get_booking(self, booking_id: int) -> BookingRecord | None:
        if booking_id <= 0:
            raise ValueError("booking_id must be positive")
        return self.repository.get(booking_id)
