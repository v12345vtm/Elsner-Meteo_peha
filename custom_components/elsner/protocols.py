"""Elsner P03/3 weather station frame protocols.

Supported variants:
  - "W": CET (Central European Time)
  - "G": GPS (Universal Time Coordinated + Position/Sun)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


def _flag(raw: str) -> bool:
    """'J' (ja/yes) -> True, 'N' (nee/no) -> False."""
    return raw.strip().upper() == "J"


@dataclass(frozen=True)
class Field:
    key: str  # stable id, used for the entity's object_id / unique_id
    name: str  # friendly name, e.g. "Wind"
    start: int  # slice start, 0-based, ETX already stripped from the frame
    end: int  # slice end (exclusive)
    unit: str | None = None
    device_class: str | None = None
    cast: Callable[[str], object] = str
    icon: str | None = None  # MDI icon shown next to the entity, e.g. "mdi:thermometer"


@dataclass(frozen=True)
class Protocol:
    start_char: str  # byte 1 of the frame ("W" or "G")
    frame_length: int  # length of frame WITHOUT trailing 0x03
    fields: tuple[Field, ...]
    checksum_field: str | None = None


# --- P03/3-RS485-CET (Start with "W", 39 bytes payload) ---
CET_FIELDS: tuple[Field, ...] = (
    Field("temperature", "Temperature", 1, 6, "°C", "temperature", float, icon="mdi:thermometer"),
    Field("sun_south", "Sun south", 6, 8, "klx", None, int, icon="mdi:sun-compass"),
    Field("sun_west", "Sun west", 8, 10, "klx", None, int, icon="mdi:sun-compass"),
    Field("sun_east", "Sun east", 10, 12, "klx", None, int, icon="mdi:sun-compass"),
    Field("twilight", "Twilight", 12, 13, None, None, _flag, icon="mdi:weather-sunset"),
    Field("daylight", "Daylight", 13, 16, "lx", "illuminance", int, icon="mdi:brightness-5"),
    Field("wind", "Wind", 16, 20, "m/s", None, float, icon="mdi:weather-windy"),
    Field("rain", "Rain", 20, 21, None, None, _flag, icon="mdi:weather-pouring"),
    Field("weekday", "Weekday", 21, 22, None, None, str, icon="mdi:calendar-week"),
    Field("day", "Day", 22, 24, None, None, int, icon="mdi:calendar"),
    Field("month", "Month", 24, 26, None, None, int, icon="mdi:calendar-month"),
    Field("year", "Year", 26, 28, None, None, int, icon="mdi:calendar"),
    Field("hour", "Hour", 28, 30, None, None, int, icon="mdi:clock-outline"),
    Field("minute", "Minute", 30, 32, None, None, int, icon="mdi:clock-outline"),
    Field("second", "Second", 32, 34, None, None, int, icon="mdi:clock-outline"),
    Field("summer_time", "Summer time", 34, 35, None, None, str, icon="mdi:sun-clock"),
    Field("checksum", "Checksum", 35, 39, None, None, int, icon="mdi:pound"),
)

# --- P03/3-RS485-GPS (Start with "G", 60 bytes payload) ---
GPS_FIELDS: tuple[Field, ...] = (
    Field("temperature", "Temperature", 1, 6, "°C", "temperature", float, icon="mdi:thermometer"),
    Field("sun_south", "Sun south", 6, 8, "klx", None, int, icon="mdi:sun-compass"),
    Field("sun_west", "Sun west", 8, 10, "klx", None, int, icon="mdi:sun-compass"),
    Field("sun_east", "Sun east", 10, 12, "klx", None, int, icon="mdi:sun-compass"),
    Field("twilight", "Twilight", 12, 13, None, None, _flag, icon="mdi:weather-sunset"),
    Field("daylight", "Daylight", 13, 16, "lx", "illuminance", int, icon="mdi:brightness-5"),
    Field("wind", "Wind", 16, 20, "m/s", None, float, icon="mdi:weather-windy"),
    Field("rain", "Rain", 20, 21, None, None, _flag, icon="mdi:weather-pouring"),
    Field("weekday", "UTC weekday", 21, 22, None, None, str, icon="mdi:calendar-week"),
    Field("day", "UTC day", 22, 24, None, None, int, icon="mdi:calendar"),
    Field("month", "UTC month", 24, 26, None, None, int, icon="mdi:calendar-month"),
    Field("year", "UTC year", 26, 28, None, None, int, icon="mdi:calendar"),
    Field("hour", "UTC hour", 28, 30, None, None, int, icon="mdi:clock-outline"),
    Field("minute", "UTC minute", 30, 32, None, None, int, icon="mdi:clock-outline"),
    Field("second", "UTC second", 32, 34, None, None, int, icon="mdi:clock-outline"),
    Field("gps_status", "GPS Status", 34, 35, None, None, int, icon="mdi:crosshairs-gps"),
    Field("azimuth", "Azimuth", 35, 40, "°", None, float, icon="mdi:compass-outline"),
    Field("elevation", "Elevation", 40, 45, "°", None, float, icon="mdi:angle-acute"),
    Field("longitude_direction", "Longitude Direction", 45, 46, None, None, str, icon="mdi:map-marker"),
    Field("longitude", "Longitude", 46, 51, "°", None, float, icon="mdi:map-marker"),
    Field("latitude_direction", "Latitude Direction", 51, 52, None, None, str, icon="mdi:map-marker"),
    Field("latitude", "Latitude", 52, 56, "°", None, float, icon="mdi:map-marker"),
    Field("checksum", "Checksum", 56, 60, None, None, int, icon="mdi:pound"),
)


PROTOCOLS_BY_START: dict[str, Protocol] = {
    "W": Protocol(
        start_char="W",
        frame_length=39,
        fields=CET_FIELDS,
        checksum_field="checksum",
    ),
    "G": Protocol(
        start_char="G",
        frame_length=60,
        fields=GPS_FIELDS,
        checksum_field="checksum",
    ),
}


def parse_frame(protocol: Protocol, frame: str) -> dict[str, object]:
    """Parse raw frame (ETX stripped) into key/value dictionary."""
    values: dict[str, object] = {}
    for field in protocol.fields:
        raw = frame[field.start:field.end]
        try:
            values[field.key] = field.cast(raw)
        except (ValueError, TypeError):
            values[field.key] = None
    return values


def verify_checksum(protocol: Protocol, frame: str) -> bool | None:
    """Validate ASCII sum checksum."""
    if protocol.checksum_field is None:
        return None
    checksum_field = next(
        f for f in protocol.fields if f.key == protocol.checksum_field
    )
    payload = frame[: checksum_field.start]
    computed = sum(ord(c) for c in payload)
    try:
        reported = int(frame[checksum_field.start:checksum_field.end])
    except ValueError:
        return False
    width = checksum_field.end - checksum_field.start
    return computed % (10 ** width) == reported
