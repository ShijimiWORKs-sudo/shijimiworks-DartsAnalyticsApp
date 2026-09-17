"""DARTSLIVE HOME BLE observation script (docs §3 手順の機械化).

Run this on the Windows PC that will actually run DartsAnalyticsApp, with
DARTSLIVE HOME powered on and pairing-visible, over Bluetooth LE (not
classic Bluetooth pairing in Windows Settings — this talks GATT directly).

WHY THIS SCRIPT EXISTS: this development session runs in a cloud sandbox
with no Bluetooth hardware, and has no way to execute commands on the
user's own PC. §3 requires observing REAL BLE traffic from REAL hardware
at 7 specific moments (see docs §3), across multiple repeated trials, to
check for reproducibility — none of that can be done by guessing. This
script automates the MECHANICAL part (scanning, connecting, discovering
GATT services/characteristics, subscribing to notifications, and logging
everything with timestamps) so the user only has to run it and physically
throw darts at the prompted moments. It does NOT interpret the data in
any way — no assumption about payload format, byte layout, or meaning is
made anywhere in this script. That interpretation is exactly the next
step (a future Claude session, once this script's raw log is available).

USAGE (PowerShell, on the Windows PC — see
docs/reports/ble/HOWTO_ja.md for the same instructions in Japanese with
more detail):

    cd C:\\制作データ\\20_DartsAnalyticsApp
    python -m venv .venv
    .venv\\Scripts\\activate
    pip install bleak
    python scripts\\ble_investigate.py

The script will:
  1. Scan for nearby BLE devices for 10 seconds and list them (by name
     and address) so you can identify DARTSLIVE HOME (or confirm it does
     NOT appear — itself an important, reportable finding per docs §3's
     "デバイス非表示" outcome).
  2. Ask you to pick the device (or type its address directly if scanning
     doesn't show a name).
  3. Connect, and if connection succeeds, discover every GATT
     service/characteristic and print/save their UUIDs plus each
     characteristic's properties (read/write/notify) and, where readable,
     its current raw value.
  4. Subscribe to notifications on every characteristic that advertises
     the "notify" property.
  5. Prompt you, one at a time, through the 7 observation moments docs §3
     names: 接続直後 / 投げる前 / 1投後 / 3投後 / CHANGE後 /
     ラウンド変更時 / ゲーム終了時 — press Enter at each moment (after
     doing the physical action) to snapshot "what notifications arrived
     since the last snapshot" into the log.
  6. Ask if you want to repeat the whole 7-step sequence again (docs §3:
     "同じ試験を複数回行い、再現性を確認する") — do this at least 2-3
     times if you can.
  7. Write everything to ble_investigation_<timestamp>.json (raw,
     structured) AND a human-readable .txt summary, both in the current
     directory. Send BOTH files back so they can be analyzed.

If ANY step fails (device not found, pairing fails, connection fails,
GATT discovery fails, no notifications ever arrive), the script does NOT
stop and pretend success — it records exactly which step failed and lets
you continue reporting what you observed at whatever point you stopped
at. A failure IS a valid, useful result (see docs §3's own classification
of failure stages) — do not skip sending the log just because the device
"didn't work".

No credentials, pairing PINs, or anything besides BLE advertisement/GATT
data is ever logged by this script.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print(
        "This script needs the 'bleak' package. Install it first:\n"
        "    pip install bleak\n"
        "(bleak is a cross-platform BLE library; on Windows it uses the "
        "built-in Bluetooth stack, no extra hardware driver needed beyond "
        "what Windows already has for Bluetooth LE.)",
        file=sys.stderr,
    )
    raise

OBSERVATION_MOMENTS = [
    "接続直後 (right after connecting, before throwing anything)",
    "投げる前 (right before throwing the first dart)",
    "1投後 (right after the 1st dart)",
    "3投後 (right after the 3rd dart / end of round 1)",
    "CHANGE後 (right after pressing CHANGE, if applicable)",
    "ラウンド変更時 (right when the round changes)",
    "ゲーム終了時 (right when the game/session ends)",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log_entry(event_type: str, **fields) -> dict:
    return {"timestamp": _now_iso(), "event_type": event_type, **fields}


async def scan_for_devices(timeout: float = 10.0) -> list:
    print(f"\nScanning for BLE devices for {timeout:.0f} seconds...")
    devices = await BleakScanner.discover(timeout=timeout)
    if not devices:
        print("No BLE devices found at all. This could mean:")
        print("  - DARTSLIVE HOME's Bluetooth is off / not in pairing mode")
        print("  - Bluetooth is off on this PC, or the adapter doesn't support BLE")
        print("  - DARTSLIVE HOME's advertisement is not BLE (classic Bluetooth only)")
    else:
        print(f"\nFound {len(devices)} device(s):")
        for i, d in enumerate(devices):
            print(f"  [{i}] name={d.name!r} address={d.address} rssi={getattr(d, 'rssi', '?')}")
    return devices


async def discover_gatt(client: BleakClient, log: list) -> None:
    print("\nDiscovering GATT services/characteristics...")
    for service in client.services:
        print(f"  Service: {service.uuid}")
        log.append(_log_entry("gatt_service", uuid=str(service.uuid), description=service.description))
        for char in service.characteristics:
            props = list(char.properties)
            print(f"    Characteristic: {char.uuid} properties={props}")
            value_hex = None
            if "read" in props:
                try:
                    raw = await client.read_gatt_char(char.uuid)
                    value_hex = raw.hex()
                    print(f"      current value (hex): {value_hex}")
                except Exception as e:  # noqa: BLE001 - report, don't hide
                    print(f"      read failed: {e}")
            log.append(
                _log_entry(
                    "gatt_characteristic",
                    service_uuid=str(service.uuid),
                    char_uuid=str(char.uuid),
                    properties=props,
                    initial_value_hex=value_hex,
                )
            )


def make_notification_handler(log: list, notify_counts: dict):
    def handler(sender, data: bytearray):
        entry = _log_entry(
            "notification", char_uuid=str(sender), value_hex=bytes(data).hex(), value_len=len(data)
        )
        log.append(entry)
        notify_counts[str(sender)] = notify_counts.get(str(sender), 0) + 1
        print(f"      [notify] {sender}: {bytes(data).hex()} ({len(data)} bytes)")

    return handler


async def subscribe_all_notify(client: BleakClient, log: list, notify_counts: dict) -> list:
    subscribed = []
    handler = make_notification_handler(log, notify_counts)
    for service in client.services:
        for char in service.characteristics:
            if "notify" in char.properties or "indicate" in char.properties:
                try:
                    await client.start_notify(char.uuid, handler)
                    subscribed.append(char.uuid)
                    print(f"  Subscribed to notifications: {char.uuid}")
                except Exception as e:  # noqa: BLE001
                    print(f"  Failed to subscribe to {char.uuid}: {e}")
                    log.append(_log_entry("subscribe_failed", char_uuid=str(char.uuid), error=str(e)))
    return subscribed


async def run_observation_sequence(log: list, notify_counts: dict, trial_number: int) -> None:
    print(f"\n=== Trial {trial_number}: observation sequence ===")
    for moment in OBSERVATION_MOMENTS:
        input(f"\n>>> {moment}\n    Do the action now, then press Enter here to snapshot...")
        snapshot = dict(notify_counts)
        log.append(
            _log_entry(
                "observation_moment",
                trial=trial_number,
                moment=moment,
                notify_counts_so_far=snapshot,
            )
        )
        print(f"    snapshot recorded: {snapshot}")


async def main() -> None:
    log: list = []
    log.append(_log_entry("script_started"))

    devices = await scan_for_devices()
    log.append(_log_entry("scan_result", devices=[{"name": d.name, "address": d.address} for d in devices]))

    if devices:
        choice = input(
            "\nEnter the [index] of DARTSLIVE HOME above, or paste its address directly "
            "(or press Enter to re-scan, or type 'skip' to record 'device not found'): "
        ).strip()
    else:
        choice = input(
            "\nNo devices found. Type an address to try directly, or 'skip' to record "
            "'device not found' and exit: "
        ).strip()

    if choice.lower() == "skip" or not choice:
        log.append(_log_entry("outcome", stage="device_not_found"))
        _write_log(log)
        print("\nRecorded outcome: device not found. Log written. Please send it back.")
        return

    if choice.isdigit() and int(choice) < len(devices):
        address = devices[int(choice)].address
    else:
        address = choice

    print(f"\nConnecting to {address}...")
    try:
        async with BleakClient(address) as client:
            connected = client.is_connected
            log.append(_log_entry("connect_result", address=address, connected=connected))
            if not connected:
                print("Connection failed.")
                log.append(_log_entry("outcome", stage="connection_failed"))
                _write_log(log)
                return

            print("Connected. Discovering services...")
            try:
                await discover_gatt(client, log)
            except Exception as e:  # noqa: BLE001
                print(f"GATT discovery failed: {e}")
                log.append(_log_entry("outcome", stage="gatt_discovery_failed", error=str(e)))
                _write_log(log)
                return

            notify_counts: dict = {}
            subscribed = await subscribe_all_notify(client, log, notify_counts)
            if not subscribed:
                print("\nNo notify/indicate characteristics found or subscribable.")
                log.append(_log_entry("outcome", stage="no_notify_characteristics"))

            trial = 1
            while True:
                await run_observation_sequence(log, notify_counts, trial)
                again = input(
                    "\nRepeat the full 7-step sequence again for reproducibility? [y/N]: "
                ).strip().lower()
                if again != "y":
                    break
                trial += 1

            log.append(_log_entry("outcome", stage="completed", total_trials=trial))
    except Exception as e:  # noqa: BLE001
        print(f"\nUnexpected error: {e}")
        log.append(_log_entry("outcome", stage="unexpected_error", error=str(e)))

    _write_log(log)
    print("\nDone. Please send BOTH the .json and .txt files back for analysis.")


def _write_log(log: list) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = Path(f"ble_investigation_{timestamp}.json")
    txt_path = Path(f"ble_investigation_{timestamp}.txt")

    json_path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = []
    for entry in log:
        lines.append(f"[{entry['timestamp']}] {entry['event_type']}: "
                      f"{ {k: v for k, v in entry.items() if k not in ('timestamp', 'event_type')} }")
    txt_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nWrote {json_path} and {txt_path}")


if __name__ == "__main__":
    asyncio.run(main())
