"""Detect an Aqua Scope ESP32-CAM connected over USB serial.

The firmware prints its WiFi IP on Serial 115200. This helper scans available
COM ports, reads boot/status logs, extracts an IP, then verifies that
http://<ip>/device looks like the Aqua Scope firmware.

Stdout is intentionally machine-readable: on success it prints only the IP.
Human diagnostics go to stderr so run_aqua_scope.bat can capture stdout safely.
"""

from __future__ import annotations

import argparse
import re
import sys
import time

import requests


IP_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)


def parse_ip_from_text(text: str) -> str | None:
    """Return the first useful IPv4 address from firmware serial text."""
    for match in IP_RE.finditer(text):
        ip = match.group(0)
        if ip.startswith(("0.", "127.", "169.254.")):
            continue
        return ip
    return None


def verify_board(ip: str, timeout_s: float = 2.0) -> bool:
    try:
        response = requests.get(f"http://{ip}/device", timeout=timeout_s)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return False
    return isinstance(payload, dict) and (
        str(payload.get("device_id", "")).startswith("aqua-cam-")
        or "camera" in payload
    )


def iter_candidate_ports():
    try:
        from serial.tools import list_ports
    except ImportError as exc:
        raise RuntimeError("pyserial is not installed") from exc

    ports = list(list_ports.comports())
    preferred = []
    fallback = []
    markers = (
        "usb", "uart", "serial", "ch340", "ch341", "cp210", "silicon labs",
        "ftdi", "wch", "esp32",
    )
    for port in ports:
        text = " ".join(
            str(value).lower()
            for value in (port.device, port.description, port.manufacturer, port.hwid)
            if value
        )
        if any(marker in text for marker in markers):
            preferred.append(port.device)
        else:
            fallback.append(port.device)
    return preferred + fallback


def read_port_for_ip(port_name: str, timeout_s: float) -> str | None:
    import serial

    deadline = time.monotonic() + timeout_s
    buffer = ""
    with serial.Serial(port_name, 115200, timeout=0.3) as ser:
        # Opening the port often resets ESP32 boards through the USB-serial chip.
        # If it does, the boot log will include the WiFi IP; if it does not, the
        # firmware still prints WiFi status roughly every 10 seconds.
        while time.monotonic() < deadline:
            chunk = ser.read(512)
            if not chunk:
                continue
            buffer += chunk.decode("utf-8", errors="ignore")
            ip = parse_ip_from_text(buffer)
            if ip:
                return ip
    return None


def detect(timeout_s: float) -> str | None:
    ports = iter_candidate_ports()
    if not ports:
        print("[detect] no serial ports found", file=sys.stderr)
        return None

    per_port_timeout = max(3.0, timeout_s / max(1, len(ports)))
    for port in ports:
        print(f"[detect] scanning {port}", file=sys.stderr)
        try:
            ip = read_port_for_ip(port, per_port_timeout)
        except Exception as exc:
            print(f"[detect] {port}: {exc}", file=sys.stderr)
            continue
        if not ip:
            continue
        print(f"[detect] {port}: saw IP {ip}", file=sys.stderr)
        if verify_board(ip):
            return ip
        print(f"[detect] {ip}: /device did not verify", file=sys.stderr)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        ip = detect(args.timeout)
    except RuntimeError as exc:
        print(f"[detect] {exc}", file=sys.stderr)
        return 2
    if not ip:
        return 1
    print(ip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
