"""BLE client for the STM32WB55 + SCD30 environmental nodes. One hub runs every node's client on
a single asyncio loop in a daemon thread; the application only sees the latest decoded sample per
node label (or None)."""

import asyncio
import logging
import struct
import threading
import time
from dataclasses import dataclass
from datetime import datetime

log = logging.getLogger(__name__)

_U16, _I16 = struct.Struct("<H"), struct.Struct("<h")
# SCD30 specified ranges (CO2 400..10000 typical; allow 1..40000 so a bad read is the only reject).
_CO2_RANGE = (1, 40000)
_TEMP_CENTI_RANGE = (-4000, 7000)  # SCD30 operating range -40..70 C
_HUMIDITY_CENTI_MAX = 10000
_FIELDS = ("co2_ppm", "temperature_c", "humidity_percent")


class PayloadError(ValueError):
    pass


@dataclass(frozen=True)
class EnvironmentalSample:
    timestamp: datetime  # assigned by the Pi; the node has no wall clock
    co2_ppm: int
    temperature_c: float
    humidity_percent: float


def _unpack(struct_, data):
    if len(data) != struct_.size:
        raise PayloadError(f"expected {struct_.size} bytes, got {len(data)}")
    return struct_.unpack(bytes(data))[0]


def decode_co2(data) -> int:
    ppm = _unpack(_U16, data)
    if not _CO2_RANGE[0] <= ppm <= _CO2_RANGE[1]:
        raise PayloadError(f"CO2 out of range: {ppm}")
    return ppm


def decode_temperature(data) -> float:
    centi = _unpack(_I16, data)
    if not _TEMP_CENTI_RANGE[0] <= centi <= _TEMP_CENTI_RANGE[1]:
        raise PayloadError(f"temperature out of range: {centi / 100}")
    return centi / 100


def decode_humidity(data) -> float:
    centi = _unpack(_U16, data)
    if centi > _HUMIDITY_CENTI_MAX:
        raise PayloadError(f"humidity out of range: {centi / 100}")
    return centi / 100


_DECODERS = (decode_co2, decode_temperature, decode_humidity)


class LatestReadings:
    """Thread-safe latest value per field. get() yields a sample only while all three fields
    are fresh, so a half-updated or partly stale reading is never reported."""

    def __init__(self, stale_seconds: float):
        self._stale = stale_seconds
        self._lock = threading.Lock()
        self._values: dict[str, tuple[float, float]] = {}  # field -> (value, monotonic time)

    def set(self, field: str, value, at: float | None = None) -> None:
        with self._lock:
            self._values = {**self._values, field: (value, time.monotonic() if at is None else at)}

    def clear(self) -> None:
        with self._lock:
            self._values = {}

    def get(self, at: float | None = None) -> EnvironmentalSample | None:
        with self._lock:
            now = time.monotonic() if at is None else at
            values = self._values
        if any(f not in values or now - values[f][1] > self._stale for f in _FIELDS):
            return None
        return EnvironmentalSample(datetime.now().astimezone(), *(values[f][0] for f in _FIELDS))


async def _bleak_find_device(device_name: str, timeout: float):
    # Nodes are told apart by advertised name: they all expose the same service UUID, and the
    # 128-bit UUID does not fit next to the name in the advertisement anyway.
    from bleak import BleakScanner
    return await BleakScanner.find_device_by_name(device_name, timeout=timeout)


def _bleak_client(device, disconnected_callback):
    from bleak import BleakClient
    return BleakClient(device, disconnected_callback=disconnected_callback)


class BleEnvironmentClient:
    """scan -> connect -> subscribe -> decode, retrying forever after a fixed delay.

    A fresh client object per connection means a reconnect can never stack subscriptions."""

    def __init__(self, device_name, characteristic_uuids, retry_seconds, stale_seconds,
                 scan_seconds, find_device=_bleak_find_device, client_factory=_bleak_client,
                 scan_lock=None):
        self._chars = tuple(zip(characteristic_uuids, _FIELDS, _DECODERS, strict=True))
        self._retry = retry_seconds
        self._scan = scan_seconds
        self._name = device_name
        self._find_device = find_device
        self._client_factory = client_factory
        self._scan_lock = scan_lock
        self._latest = LatestReadings(stale_seconds)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._stop_requested = threading.Event()  # survives a stop that beats the loop's start

    def request_stop(self) -> None:
        self._stop_requested.set()
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)

    def snapshot(self) -> EnvironmentalSample | None:
        return self._latest.get()

    async def run(self) -> None:
        self._loop, self._stop = asyncio.get_running_loop(), asyncio.Event()
        if self._stop_requested.is_set():
            self._stop.set()
        while not self._stop.is_set():
            try:
                await self._connect_once()
            except Exception as exc:  # nothing here may take the application down
                log.warning("[BLE] %s connection failed: %s", self._name, exc)
            self._latest.clear()
            try:
                await asyncio.wait_for(self._stop.wait(), self._retry)
            except asyncio.TimeoutError:
                pass

    async def _connect_once(self) -> None:
        device = await self._scan_for_device()
        if device is None:
            log.debug("[BLE] %s not found", self._name)
            return
        log.info("[BLE] found %s", self._name)
        lost = asyncio.Event()
        loop = asyncio.get_running_loop()
        client = self._client_factory(device, lambda _c: loop.call_soon_threadsafe(lost.set))
        try:
            await client.connect()
            log.info("[BLE] %s connected", self._name)
            for uuid, field, decode in self._chars:
                self._accept(field, decode, await client.read_gatt_char(uuid))
            for uuid, field, decode in self._chars:
                await client.start_notify(
                    uuid, lambda _h, data, f=field, d=decode: self._accept(f, d, data))
            await asyncio.wait(
                [asyncio.ensure_future(lost.wait()), asyncio.ensure_future(self._stop.wait())],
                return_when=asyncio.FIRST_COMPLETED)
        finally:
            await self._close(client)
        log.warning("[BLE] %s disconnected", self._name)

    async def _scan_for_device(self):
        """Scans are serialised across nodes: BlueZ rejects a second discovery while one runs."""
        if self._scan_lock is None:
            return await self._find_device(self._name, self._scan)
        async with self._scan_lock:
            return await self._find_device(self._name, self._scan)

    async def _close(self, client) -> None:
        steps = [lambda u=uuid: client.stop_notify(u) for uuid, _f, _d in self._chars]
        for step in (*steps, client.disconnect):
            try:
                await step()
            except Exception as exc:  # already disconnected is the normal case
                log.debug("[BLE] cleanup: %s", exc)

    def _accept(self, field, decode, data) -> None:
        try:
            value = decode(data)
        except PayloadError as exc:
            log.warning("[BLE] %s dropped malformed %s payload: %s", self._name, field, exc)
            return
        self._latest.set(field, value)


class BleEnvironmentHub:
    """Runs one BleEnvironmentClient per node on a shared loop and serves snapshots by label.

    nodes maps a label (used for CSV columns) to the node's advertised BLE name."""

    def __init__(self, nodes, characteristic_uuids, retry_seconds, stale_seconds, scan_seconds,
                 **client_kwargs):
        if not nodes:
            raise ValueError("at least one environmental node is required")
        if len(set(nodes.values())) != len(nodes):
            raise ValueError(f"two labels share one advertised name: {dict(nodes)}")
        scan_lock = asyncio.Lock()
        self._clients = {
            label: BleEnvironmentClient(name, characteristic_uuids, retry_seconds, stale_seconds,
                                        scan_seconds, scan_lock=scan_lock, **client_kwargs)
            for label, name in nodes.items()}
        self._thread = threading.Thread(target=lambda: asyncio.run(self._run_all()),
                                        name="ble-env", daemon=True)

    async def _run_all(self) -> None:
        await asyncio.gather(*(c.run() for c in self._clients.values()))

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        for client in self._clients.values():
            client.request_stop()
        if self._thread.is_alive():
            self._thread.join(timeout=5.0)

    def snapshot(self) -> dict[str, EnvironmentalSample | None]:
        return {label: client.snapshot() for label, client in self._clients.items()}
