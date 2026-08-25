from __future__ import annotations

from dataclasses import dataclass
import sqlite3


@dataclass(frozen=True)
class BookingRecord:
    booking_id: int
    customer_name: str
    slot: str


class BookingRepository:
    """Tiny transactional repository used only for the controlled Phase 4 evaluation."""

    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bookings (
                        booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_name TEXT NOT NULL,
                        slot TEXT NOT NULL
                    )
                    """
                )
        finally:
            connection.close()

    def create(self, *, customer_name: str, slot: str) -> BookingRecord:
        connection = self._connect()
        try:
            with connection:
                cursor = connection.execute(
                    "INSERT INTO bookings(customer_name, slot) VALUES (?, ?)",
                    (customer_name, slot),
                )
                booking_id = int(cursor.lastrowid)
            return BookingRecord(booking_id=booking_id, customer_name=customer_name, slot=slot)
        finally:
            connection.close()

    def get(self, booking_id: int) -> BookingRecord | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT booking_id, customer_name, slot FROM bookings WHERE booking_id = ?",
                (booking_id,),
            ).fetchone()
            if row is None:
                return None
            return BookingRecord(
                booking_id=int(row["booking_id"]),
                customer_name=str(row["customer_name"]),
                slot=str(row["slot"]),
            )
        finally:
            connection.close()
