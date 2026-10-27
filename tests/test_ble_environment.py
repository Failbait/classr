import asyncio
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from sensors.ble_environment import (BleEnvironmentClient, BleEnvironmentHub, LatestReadings,
                                     PayloadError, decode_co2, decode_humidity,
                                     decode_temperature)

CO2, TEMP, HUM = config.ENV_CO2_UUID, config.ENV_TEMPERATURE_UUID, config.ENV_HUMIDITY_UUID


def u16(v):
    return struct.pack("<H", v)


def i16(v):
    return struct.pack("<h", v)


# --- decoding ---------------------------------------------------------------------------

def test_decodes_the_documented_example():
    assert decode_co2(u16(812)) == 812
    assert decode_temperature(i16(2247)) == 22.47
    assert decode_humidity(u16(3981)) == 39.81


def test_decodes_negative_temperature():
    assert decode_temperature(i16(-550)) == -5.5


@pytest.mark.parametrize("decode", [decode_co2, decode_temperature, decode_humidity])
@pytest.mark.parametrize("data", [b"", b"\x00", b"\x00" * 3])
def test_wrong_length_is_rejected(decode, data):
    with pytest.raises(PayloadError):
        decode(data)


@pytest.mark.parametrize("decode,bad", [
    (decode_co2, u16(0)), (decode_co2, u16(60000)), (decode_humidity, u16(10001)),
    (decode_temperature, i16(9000)), (decode_temperature, i16(-5000))])
def test_out_of_range_measurement_is_rejected(decode, bad):
    with pytest.raises(PayloadError):
        decode(bad)


# --- latest-value holder ----------------------------------------------------------------

def fill(latest, at, co2=812):
    latest.set("co2_ppm", co2, at=at)
    latest.set("temperature_c", 22.47, at=at)
    latest.set("humidity_percent", 39.81, at=at)


def test_no_sample_until_all_three_fields_arrive():
    latest = LatestReadings(stale_seconds=15)
    assert latest.get() is None
    latest.set("co2_ppm", 812, at=100.0)
    latest.set("temperature_c", 22.47, at=100.0)
    assert latest.get(at=100.0) is None
    latest.set("humidity_percent", 39.81, at=100.0)
    s = latest.get(at=100.0)
    assert (s.co2_ppm, s.temperature_c, s.humidity_percent) == (812, 22.47, 39.81)
    assert s.timestamp.tzinfo is not None


def test_sample_goes_stale_if_any_field_stops_updating():
    latest = LatestReadings(stale_seconds=15)
    fill(latest, at=100.0)
    assert latest.get(at=110.0) is not None
    latest.set("co2_ppm", 900, at=114.0)  # others are now 14 s old
    assert latest.get(at=114.0).co2_ppm == 900
    assert latest.get(at=116.0) is None  # temperature/humidity are 16 s old


def test_clear_drops_everything():
    latest = LatestReadings(stale_seconds=15)
    fill(latest, at=200.0)
    latest.clear()
    assert latest.get(at=200.0) is None


# --- connection loop (fakes, no radio) --------------------------------------------------

INITIAL = {CO2: u16(700), TEMP: i16(2100), HUM: u16(4000)}


class FakeClient:
    instances = []

    def __init__(self, device, disconnected_callback):
        self.on_disconnect = disconnected_callback
        self.handlers = {}
        self.stopped = 0
        FakeClient.instances.append(self)

    async def connect(self):
        pass

    async def read_gatt_char(self, uuid):
        return bytearray(INITIAL[uuid])

    async def start_notify(self, uuid, handler):
        assert uuid not in self.handlers, "duplicate subscription"
        self.handlers[uuid] = handler

    async def stop_notify(self, uuid):
        self.stopped += 1

    async def disconnect(self):
        pass


def make_client(retry=0.01, find=None, factory=FakeClient):
    FakeClient.instances = []

    async def found(name, timeout):
        return "device"

    return BleEnvironmentClient(
        device_name="classr-s1", characteristic_uuids=(CO2, TEMP, HUM),
        retry_seconds=retry, stale_seconds=15, scan_seconds=0.1,
        find_device=find or found, client_factory=factory)


def run_for(client, seconds, during=None):
    async def go():
        task = asyncio.create_task(client.run())
        await asyncio.sleep(seconds)
        if during:
            await during()
        client.request_stop()
        await asyncio.wait_for(task, 2)
    asyncio.run(go())


def test_initial_read_seeds_sample_and_notifications_update_it():
    client = make_client()

    async def during():
        s = client.snapshot()
        assert (s.co2_ppm, s.temperature_c, s.humidity_percent) == (700, 21.0, 40.0)
        handlers = FakeClient.instances[0].handlers
        assert set(handlers) == {CO2, TEMP, HUM}
        handlers[CO2](None, bytearray(u16(900)))
        handlers[TEMP](None, bytearray(i16(2247)))
        s = client.snapshot()
        assert (s.co2_ppm, s.temperature_c) == (900, 22.47)

    run_for(client, 0.05, during)


def test_malformed_notification_is_ignored_and_keeps_last_good_value():
    client = make_client()

    async def during():
        FakeClient.instances[0].handlers[CO2](None, bytearray(b"\x01"))
        assert client.snapshot().co2_ppm == 700

    run_for(client, 0.05, during)


def test_disconnect_clears_value_and_reconnects_with_single_subscription():
    client = make_client(retry=0.05)

    async def during():
        first = FakeClient.instances[0]
        first.on_disconnect(first)
        await asyncio.sleep(0.02)
        assert client.snapshot() is None  # unavailable while down
        await asyncio.sleep(0.1)
        assert client.snapshot() is not None  # back after the retry delay

    run_for(client, 0.05, during)
    assert len(FakeClient.instances) >= 2
    assert all(len(c.handlers) == 3 for c in FakeClient.instances)


def test_device_not_found_keeps_retrying_without_crashing():
    calls = []

    async def not_found(name, timeout):
        calls.append(name)
        return None

    client = make_client(find=not_found)
    run_for(client, 0.08)
    assert len(calls) >= 2 and set(calls) == {"classr-s1"}  # looks for its own name
    assert client.snapshot() is None and not FakeClient.instances


def test_connect_failure_is_survived():
    class Failing(FakeClient):
        async def connect(self):
            raise TimeoutError("boom")

    client = make_client(factory=Failing)
    run_for(client, 0.08)
    assert len(FakeClient.instances) >= 2 and client.snapshot() is None


# --- several nodes, one hub ---------------------------------------------------------------

class NamedFakeClient(FakeClient):
    """Per-device readings: the 'device' handed over by the finder is the node's name."""
    values = {"classr-s1": {CO2: u16(700), TEMP: i16(2100), HUM: u16(4000)},
              "classr-s2": {CO2: u16(1200), TEMP: i16(2350), HUM: u16(5500)}}

    def __init__(self, device, disconnected_callback):
        super().__init__(device, disconnected_callback)
        self.device = device

    async def read_gatt_char(self, uuid):
        return bytearray(self.values[self.device][uuid])


def make_hub(find=None, nodes=None):
    FakeClient.instances = []

    async def found(name, timeout):
        return name

    return BleEnvironmentHub(
        nodes if nodes is not None else {"s1": "classr-s1", "s2": "classr-s2"}, characteristic_uuids=(CO2, TEMP, HUM),
        retry_seconds=0.02, stale_seconds=15, scan_seconds=0.1,
        find_device=find or found, client_factory=NamedFakeClient)


def run_hub(hub, seconds=0.15):
    hub.start()
    try:
        time.sleep(seconds)
        return hub.snapshot()
    finally:
        hub.stop()


def test_hub_keeps_each_nodes_readings_under_its_label():
    snap = run_hub(make_hub())
    assert set(snap) == {"s1", "s2"}
    assert (snap["s1"].co2_ppm, snap["s1"].temperature_c) == (700, 21.0)
    assert (snap["s2"].co2_ppm, snap["s2"].temperature_c, snap["s2"].humidity_percent) \
        == (1200, 23.5, 55.0)


def test_hub_reports_a_missing_node_as_none_without_hurting_the_other():
    async def only_s1(name, timeout):
        return name if name == "classr-s1" else None

    snap = run_hub(make_hub(find=only_s1))
    assert snap["s1"] is not None and snap["s2"] is None


def test_hub_never_scans_with_two_nodes_at_once():
    active, peak = [0], [0]

    async def slow_find(name, timeout):
        active[0] += 1
        peak[0] = max(peak[0], active[0])
        await asyncio.sleep(0.01)
        active[0] -= 1
        return name

    run_hub(make_hub(find=slow_find))
    assert peak[0] == 1  # BlueZ rejects concurrent discovery


def test_hub_with_no_nodes_is_rejected():
    with pytest.raises(ValueError):
        make_hub(nodes={})


def test_hub_rejects_two_labels_for_the_same_advertised_name():
    with pytest.raises(ValueError):
        make_hub(nodes={"s1": "classr-s1", "s2": "classr-s1"})


def test_hub_stop_returns_promptly():
    hub = make_hub()
    hub.start()
    started = time.monotonic()
    hub.stop()
    assert time.monotonic() - started < 3.0
