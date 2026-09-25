"""Elsner P03/3 weather station frame protocols.

Each variant the device can be configured to output (CET / GPS / plain) is
described here as an ordered tuple of `Field`s, taken straight from the
byte tables in the Elsner datasheet. To add a new variant:

  1. Add a new `Field` tuple (see CET_FIELDS below for the pattern).
  2. Register it in `PROTOCOLS` with its start character (byte 1 of the
     frame, e.g. "W" for CET/plain, "G" for GPS).

Nothing in sensor.py needs to change - it reads whichever protocol is
selected in the platform config and builds one entity per field.
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


@dataclass(frozen=True)
class Protocol:
    start_char: str  # byte 1 of the frame, used to validate/resync
    frame_length: int  # length of the frame WITHOUT the trailing 0x03
    fields: tuple[Field, ...]
    checksum_field: str | None = None  # key of the checksum field, if any


# --- P03/3-RS485-CET --------------------------------------------------
# Datasheet "P03/3-RS485-CET" byte table, bytes 1-40 (byte 40 = 0x03).
# This is the variant you are currently using (40 bytes incl. ETX).
CET_FIELDS: tuple[Field, ...] = (
    Field("temperature", "Temperature", 1, 6, "°C", "temperature", float),
    Field("sun_south", "Sun south", 6, 8, "klx", None, int),
    Field("sun_west", "Sun west", 8, 10, "klx", None, int),
    Field("sun_east", "Sun east", 10, 12, "klx", None, int),
    Field("twilight", "Twilight", 12, 13, None, None, _flag),
    Field("daylight", "Daylight", 13, 16, "lx", "illuminance", int),
    Field("wind", "Wind", 16, 20, "m/s", None, float),
    Field("rain", "Rain", 20, 21, None, None, _flag),
    Field("weekday", "Weekday", 21, 22, None, None, str),
    Field("day", "Day", 22, 24, None, None, int),
    Field("month", "Month", 24, 26, None, None, int),
    Field("year", "Year", 26, 28, None, None, int),
    Field("hour", "Hour", 28, 30, None, None, int),
    Field("minute", "Minute", 30, 32, None, None, int),
    Field("second", "Second", 32, 34, None, None, int),
    Field("summer_time", "Summer time", 34, 35, None, None, str),
    Field("checksum", "Checksum", 35, 39, None, None, int),
)

# --- P03/3-RS485-GPS ----------------------------------------------------
# TODO: fill in from the "P03/3-RS485-GPS" byte table (starts with "G",
# 61 bytes incl. ETX: adds UTC weekday/date/time, azimuth, elevation,
# longitude and latitude before the checksum). Left empty until needed -
# the CET variant below is unaffected by this.
GPS_FIELDS: tuple[Field, ...] = ()

# --- "Plain" P0x/3 (no date/time, no checksum) --------------------------
# TODO: fill in if/when you use a variant without CET/GPS. This is
# presumably the 26-byte layout the original integration assumed
# (temperature, sun x3, twilight, daylight, wind, rain - no date/time,
# no checksum). Confirm the exact byte offsets against that device's own
# datasheet before relying on it; do not reuse the CET offsets as-is.
PLAIN_FIELDS: tuple[Field, ...] = ()


PROTOCOLS: dict[str, Protocol] = {
    "cet": Protocol(
        start_char="W",
        frame_length=39,
        fields=CET_FIELDS,
        checksum_field="checksum",
    ),
    # "gps": Protocol(
    #     start_char="G",
    #     frame_length=60,
    #     fields=GPS_FIELDS,
    #     checksum_field="checksum",
    # ),
    # "plain": Protocol(
    #     start_char="W",
    #     frame_length=26,
    #     fields=PLAIN_FIELDS,
    # ),
}

DEFAULT_PROTOCOL = "cet"


def parse_frame(protocol: Protocol, frame: str) -> dict[str, object]:
    """Parse one raw frame (ETX already stripped) into named values.

    A field that fails to cast (garbled byte, wrong protocol selected,
    etc.) becomes None rather than raising, so one bad field doesn't take
    down the whole frame.
    """
    values: dict[str, object] = {}
    for field in protocol.fields:
        raw = frame[field.start:field.end]
        try:
            values[field.key] = field.cast(raw)
        except (ValueError, TypeError):
            values[field.key] = None
    return values


def verify_checksum(protocol: Protocol, frame: str) -> bool | None:
    """Sum of byte values up to (not incl.) the checksum field, ASCII-summed.

    Per the datasheet: "The checksum is calculated ... by adding all
    received bytes up until byte 35 [1-based] and then compared with the
    checksum transferred". Returns None if this protocol has no checksum
    field, so callers can skip validation for variants that don't define
    one yet.
    """
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
    # The device's checksum is transferred as a fixed-width decimal
    # counter; compare modulo 10**width since it presumably wraps.
    width = checksum_field.end - checksum_field.start
    return computed % (10 ** width) == reported
