from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import sqlite3


_EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class GeoPoint:
    latitude: float
    longitude: float

    def validate(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError("latitude must be between -90 and 90")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError("longitude must be between -180 and 180")


@dataclass(frozen=True)
class GeoHit:
    canonical_id: str
    distance_km: float


class SQLiteGeoIndex:
    """Small deterministic spatial index for Mission 001.

    This is intentionally independent from the canonical inventory schema. It can be
    replaced by a production spatial database later without granting that database
    authority over listing lifecycle, rights or trust state.
    """

    SCHEMA_VERSION = 1

    def __init__(self, path: str) -> None:
        self._connection = sqlite3.connect(path)
        self._connection.row_factory = sqlite3.Row
        self.apply_migrations()

    def close(self) -> None:
        self._connection.close()

    def apply_migrations(self) -> int:
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS geo_schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {
            int(row[0])
            for row in self._connection.execute("SELECT version FROM geo_schema_version").fetchall()
        }
        count = 0
        if 1 not in applied:
            with self._connection:
                self._connection.executescript(
                    """
                    CREATE TABLE geo_points (
                        canonical_id TEXT PRIMARY KEY,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE INDEX idx_geo_latitude ON geo_points(latitude);
                    CREATE INDEX idx_geo_longitude ON geo_points(longitude);
                    """
                )
                self._connection.execute(
                    "INSERT INTO geo_schema_version(version, applied_at) VALUES (?, ?)",
                    (1, self._now_iso()),
                )
            count += 1
        return count

    def upsert(self, canonical_id: str, point: GeoPoint) -> None:
        if not canonical_id.strip():
            raise ValueError("canonical_id is required")
        point.validate()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO geo_points(canonical_id, latitude, longitude, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(canonical_id) DO UPDATE SET
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    updated_at = excluded.updated_at
                """,
                (canonical_id, point.latitude, point.longitude, self._now_iso()),
            )

    def remove(self, canonical_id: str) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM geo_points WHERE canonical_id = ?", (canonical_id,))

    def point(self, canonical_id: str) -> GeoPoint | None:
        row = self._connection.execute(
            "SELECT latitude, longitude FROM geo_points WHERE canonical_id = ?",
            (canonical_id,),
        ).fetchone()
        if row is None:
            return None
        return GeoPoint(float(row["latitude"]), float(row["longitude"]))

    def within_radius(self, center: GeoPoint, *, radius_km: float, limit: int | None = None) -> tuple[GeoHit, ...]:
        center.validate()
        if radius_km <= 0.0:
            raise ValueError("radius_km must be positive")
        if limit is not None and limit <= 0:
            raise ValueError("limit must be positive")

        # Coarse deterministic bounding box first, then exact haversine distance.
        lat_delta = radius_km / 111.32
        cos_lat = max(0.01, math.cos(math.radians(center.latitude)))
        lon_delta = radius_km / (111.32 * cos_lat)
        min_lat = max(-90.0, center.latitude - lat_delta)
        max_lat = min(90.0, center.latitude + lat_delta)
        min_lon = center.longitude - lon_delta
        max_lon = center.longitude + lon_delta

        if min_lon < -180.0 or max_lon > 180.0:
            rows = self._connection.execute(
                "SELECT canonical_id, latitude, longitude FROM geo_points WHERE latitude BETWEEN ? AND ?",
                (min_lat, max_lat),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT canonical_id, latitude, longitude FROM geo_points
                WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?
                """,
                (min_lat, max_lat, min_lon, max_lon),
            ).fetchall()

        hits: list[GeoHit] = []
        for row in rows:
            point = GeoPoint(float(row["latitude"]), float(row["longitude"]))
            distance = self.distance_km(center, point)
            if distance <= radius_km:
                hits.append(GeoHit(str(row["canonical_id"]), round(distance, 6)))
        hits.sort(key=lambda hit: (hit.distance_km, hit.canonical_id))
        if limit is not None:
            hits = hits[:limit]
        return tuple(hits)

    @staticmethod
    def distance_km(a: GeoPoint, b: GeoPoint) -> float:
        a.validate()
        b.validate()
        lat1 = math.radians(a.latitude)
        lat2 = math.radians(b.latitude)
        dlat = lat2 - lat1
        dlon = math.radians(b.longitude - a.longitude)
        hav = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
        angle = 2.0 * math.atan2(math.sqrt(hav), math.sqrt(max(0.0, 1.0 - hav)))
        return _EARTH_RADIUS_KM * angle

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
