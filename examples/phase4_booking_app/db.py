from __future__ import annotations

from dataclasses import dataclass
import sqlite3


@dataclass(frozen=True)
class BookingRecord:
    booking_id: int
    customer_name: str
    slot: str


class BookingRepository:
    """Tiny transactional repository used by controlled Factory qualification fixtures."""

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
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        migration_id TEXT PRIMARY KEY,
                        applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
        finally:
            connection.close()

    def apply_add_notes_migration(self) -> bool:
        """Apply a controlled idempotent migration; returns True only on first application."""
        migration_id = "2026-08-add-booking-notes"
        connection = self._connect()
        try:
            with connection:
                seen = connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE migration_id=?", (migration_id,)
                ).fetchone()
                if seen is not None:
                    return False
                columns = {
                    str(row["name"])
                    for row in connection.execute("PRAGMA table_info(bookings)").fetchall()
                }
                if "notes" not in columns:
                    connection.execute("ALTER TABLE bookings ADD COLUMN notes TEXT")
                connection.execute(
                    "INSERT INTO schema_migrations(migration_id) VALUES(?)", (migration_id,)
                )
            return True
        finally:
            connection.close()

    def has_column(self, column_name: str) -> bool:
        connection = self._connect()
        try:
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(bookings)").fetchall()
            }
            return column_name in columns
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
