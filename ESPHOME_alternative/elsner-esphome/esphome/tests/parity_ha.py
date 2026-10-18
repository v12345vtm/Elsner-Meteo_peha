#!/usr/bin/env python3
# Versie: 0.1.1
"""Paritytest: de ESPHome-C++-parser moet dezelfde uitkomst geven als de HA-integratie.

Wat er gebeurt:
  1. De ECHTE HA-code (custom_components/elsner/hub.py + protocols.py) wordt geladen.
     Alleen Home Assistant zelf wordt vervangen door stubs (die zitten niet in deze test).
  2. Dezelfde reeks frames wordt door de HA-hub gehaald en door test_parity (C++).
  3. Per frame worden de tellers, variant, checksum en alle veldwaarden vergeleken.

Gebruik (vanuit de map esphome/tests):
  g++ -std=c++17 -O1 -I../../components/elsner test_parity.cpp -o test_parity
  python3 parity_ha.py --binary ./test_parity

De map custom_components wordt automatisch gezocht door omhoog te lopen vanaf dit
bestand. Staat het script los van de repo, geef dan --ha-root op.

Het script test de frame-verwerking. Het test niet de ESPHome-glue (uart, timers,
publicatie naar Home Assistant); die moet je met `esphome compile` controleren.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

ETX = b"\x03"


# ---------------------------------------------------------------------------
# Stubs voor Home Assistant en de seriële bibliotheken
# ---------------------------------------------------------------------------
def install_ha_stubs() -> None:
    names = [
        "homeassistant",
        "homeassistant.config_entries",
        "homeassistant.const",
        "homeassistant.core",
        "homeassistant.helpers",
        "homeassistant.helpers.device_registry",
        "homeassistant.util",
        "serial",
        "serial_asyncio_fast",
    ]
    for name in names:
        sys.modules[name] = MagicMock()
    # @callback moet gewoon de functie teruggeven, anders worden de methodes MagicMocks.
    sys.modules["homeassistant.core"].callback = lambda func: func


class FakeTime:
    """Vervangt de 'time'-module in hub.py zodat we de klok zelf bepalen."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now


# ---------------------------------------------------------------------------
# Frame-bouwer (zelfde velden en breedtes als protocols.py)
# ---------------------------------------------------------------------------
CET_LAYOUT = (
    ("temperature", 5), ("sun_south", 2), ("sun_west", 2), ("sun_east", 2),
    ("twilight", 1), ("daylight", 3), ("wind", 4), ("rain", 1), ("weekday", 1),
    ("day", 2), ("month", 2), ("year", 2), ("hour", 2), ("minute", 2), ("second", 2),
    ("summer_time", 1),
)
GPS_LAYOUT = (
    ("temperature", 5), ("sun_south", 2), ("sun_west", 2), ("sun_east", 2),
    ("twilight", 1), ("daylight", 3), ("wind", 4), ("rain", 1), ("weekday", 1),
    ("day", 2), ("month", 2), ("year", 2), ("hour", 2), ("minute", 2), ("second", 2),
    ("gps_status", 1), ("azimuth", 5), ("elevation", 5), ("longitude_direction", 1),
    ("longitude", 5), ("latitude_direction", 1), ("latitude", 4),
)


def build(start: str, layout, values: dict, good_checksum: bool = True) -> bytes:
    payload = start
    for name, width in layout:
        value = values[name]
        assert len(value) == width, (name, value)
        payload += value
    checksum = sum(ord(c) for c in payload) % 10000
    if not good_checksum:
        checksum = (checksum + 1) % 10000
    return (payload + f"{checksum:04d}").encode("ascii") + ETX


CET_A = dict(temperature="+12.3", sun_south="45", sun_west="12", sun_east="03",
             twilight="N", daylight="120", wind="03.5", rain="J", weekday="3",
             day="18", month="10", year="26", hour="12", minute="34", second="56",
             summer_time="S")
CET_B = dict(temperature="-05.3", sun_south="00", sun_west="00", sun_east="00",
             twilight="j", daylight="000", wind="00.0", rain="n", weekday="4",
             day="19", month="10", year="26", hour="06", minute="07", second="08",
             summer_time="W")
CET_BAD_NUMBERS = dict(CET_A, temperature="ABCDE", wind=" 1.0")
CET_SPACES = dict(CET_A, temperature=" 8.1 ")
GPS_A = dict(temperature="+01.5", sun_south="10", sun_west="20", sun_east="30",
             twilight="N", daylight="500", wind="02.0", rain="N", weekday="5",
             day="20", month="10", year="26", hour="09", minute="00", second="01",
             gps_status="3", azimuth="123.4", elevation=" 45.6",
             longitude_direction="E", longitude="04.12", latitude_direction="N",
             latitude="51.2")


def cet(values=CET_A, good=True) -> bytes:
    return build("W", CET_LAYOUT, values, good)


def gps(values=GPS_A, good=True) -> bytes:
    return build("G", GPS_LAYOUT, values, good)


# ---------------------------------------------------------------------------
# Scenario's: (naam, analyse-interval in ms, [(tijd_ms, frame_bytes), ...])
# ---------------------------------------------------------------------------
def scenarios():
    yield "CET: interval 0 + randgevallen", 0, [
        (0, cet()),                                   # eerste frame: lock op CET
        (1000, cet(CET_B)),                           # negatieve temperatuur, lage waarden
        (2000, cet(CET_BAD_NUMBERS)),                 # ongeldige temperatuur -> None/NaN
        (3000, cet(good=False)),                      # verkeerde checksum -> wel analyseren
        (4000, b"\r\n" + cet() ),                     # CR/LF ervoor -> strippen
        (5000, cet()[:-1] + b" " + ETX),              # spatie ervoor ETX -> strippen
        (6000, cet()[:-2] + ETX),                     # te kort -> ongeldig
        (7000, b"X" + cet()[1:]),                     # onbekend startteken
        (8000, ETX),                                  # leeg frame
        (9000, gps()),                                # GPS terwijl CET is vergrendeld
        (10000, cet(CET_SPACES)),                     # spaties in een getal
    ]

    yield "GPS: eerste frame bepaalt de variant", 0, [
        (0, gps()),
        (1000, cet()),                                # CET terwijl GPS is vergrendeld
        (2000, gps(good=False)),
        (3000, gps()[:-2] + ETX),                     # te kort
    ]

    yield "Throttle: interval 5 s", 5000, [
        (0, cet()),                                   # geanalyseerd
        (1000, cet(CET_B)),                           # overgeslagen
        (2000, cet(CET_B)),
        (3000, cet(CET_B)),
        (4000, cet(CET_B)),
        (5000, cet(CET_B)),                           # precies 5 s later: geanalyseerd
        (6000, cet()),                                # overgeslagen
    ]


# ---------------------------------------------------------------------------
# HA-kant
# ---------------------------------------------------------------------------
def load_ha(ha_root: Path):
    sys.path.insert(0, str(ha_root))
    install_ha_stubs()
    import elsner.hub as ha_hub  # type: ignore[import-not-found]
    from elsner.protocols import verify_checksum  # type: ignore[import-not-found]

    ha_hub.time = FakeTime()
    return ha_hub, verify_checksum


def new_hub(ha_hub, interval_ms: int):
    hub = ha_hub.ElsnerHub.__new__(ha_hub.ElsnerHub)
    hub.hass = None
    hub.name = "parity"
    hub.port = "/dev/null"
    hub.analyse_interval = interval_ms / 1000.0
    hub.available = False
    hub.values = None
    hub.raw = None
    hub.variant = None
    hub.analysed_at = None
    hub.frames_received = 0
    hub.frames_analysed = 0
    hub.frames_skipped = 0
    hub.frames_invalid = 0
    hub._protocol = None
    hub._on_protocol = None
    hub._listeners = []
    hub._task = None
    hub._lock = None
    hub._last_analysis = float("-inf")
    hub._last_valid = float("-inf")
    hub._open_error_logged = False
    return hub


def ha_snapshot(hub, verify_checksum) -> dict:
    values = None
    if hub.values is not None:
        values = {k: (v.strip() if isinstance(v, str) else v) for k, v in hub.values.items()}
    checksum_ok = None
    if hub.raw is not None and hub._protocol is not None:
        checksum_ok = bool(verify_checksum(hub._protocol, hub.raw))
    return {
        "received": hub.frames_received,
        "analysed": hub.frames_analysed,
        "skipped": hub.frames_skipped,
        "invalid": hub.frames_invalid,
        "variant": hub.variant,
        "checksum_ok": checksum_ok,
        "values": values,
    }


def run_ha(ha_hub, verify_checksum, interval_ms, frames) -> list[dict]:
    hub = new_hub(ha_hub, interval_ms)
    out = []
    for t_ms, data in frames:
        ha_hub.time.now = t_ms / 1000.0
        hub._async_handle_raw(data)
        out.append(ha_snapshot(hub, verify_checksum))
    return out


# ---------------------------------------------------------------------------
# C++-kant
# ---------------------------------------------------------------------------
def run_cpp(binary: str, interval_ms, frames) -> list[dict]:
    lines = [f"I {interval_ms}"]
    lines += [f"T {t_ms} {data.hex()}" for t_ms, data in frames]
    proc = subprocess.run(
        [binary], input="\n".join(lines) + "\n", capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"{binary} faalde (exit {proc.returncode}); zie zelftest-melding hierboven")
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Vergelijken
# ---------------------------------------------------------------------------
def same_value(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=0.0)
    return a == b


def compare(name: str, ha_states: list[dict], cpp_states: list[dict]) -> int:
    problems = 0
    for i, (h, c) in enumerate(zip(ha_states, cpp_states)):
        for key in ("received", "analysed", "skipped", "invalid", "variant", "checksum_ok"):
            if h[key] != c[key]:
                problems += 1
                print(f"  frame {i}: {key}: HA={h[key]!r} C++={c[key]!r}")
        hv, cv = h["values"], c["values"]
        if (hv is None) != (cv is None):
            problems += 1
            print(f"  frame {i}: values: HA={hv is not None} C++={cv is not None}")
        elif hv is not None:
            for key in sorted(set(hv) | set(cv)):
                a = hv.get(key, "<ontbreekt>")
                b = cv.get(key, "<ontbreekt>")
                if not same_value(a, b):
                    problems += 1
                    print(f"  frame {i}: {key}: HA={a!r} C++={b!r}")
    if len(ha_states) != len(cpp_states):
        problems += 1
        print(f"  aantal frames verschilt: HA={len(ha_states)} C++={len(cpp_states)}")
    status = "OK" if problems == 0 else f"{problems} VERSCHIL(LEN)"
    print(f"[{status}] {name} ({len(ha_states)} frames)")
    return problems


def find_ha_root() -> Path:
    """Loop omhoog vanaf dit bestand tot er een custom_components/elsner-map is."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "custom_components"
        if (candidate / "elsner").is_dir():
            return candidate
    return Path("custom_components")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--binary", default="./test_parity", help="pad naar de gecompileerde test_parity")
    parser.add_argument(
        "--ha-root",
        default=str(find_ha_root()),
        help="map die de 'elsner'-integratie bevat (standaard: automatisch gezocht)",
    )
    args = parser.parse_args()

    ha_hub, verify_checksum = load_ha(Path(args.ha_root).resolve())
    total = 0
    for name, interval_ms, frames in scenarios():
        ha_states = run_ha(ha_hub, verify_checksum, interval_ms, frames)
        cpp_states = run_cpp(args.binary, interval_ms, frames)
        total += compare(name, ha_states, cpp_states)
    print("ALLES GELIJK" if total == 0 else f"{total} verschillen gevonden")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
