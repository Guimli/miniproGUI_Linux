#!/usr/bin/env python3
"""A stand-in for the minipro CLI, emulating a connected T76.

Lets the UI and the response processors be exercised end to end without
hardware. Output formats mirror what minipro 0.7.4 prints, including the
convention that everything human-readable goes to stderr while payload data
(chip lists, --read contents) goes to stdout.

Usage:
    PATH=/path/to/tests/fake-bin:$PATH python3 -m visualminipro
"""

from __future__ import annotations

import sys

FIRMWARE = "04.2.113 (0x271)"

EEPROM_CHIPS = [
    "AT28C256",
    "AT28C64B",
    "W27C512@DIP28",
    "SST39SF010A@PLCC32",
    "M27C801@DIP32",
    "MX25L12835F@SOP16",
]

LOGIC_CHIPS = ["SN74LS00", "SN74LS04", "CD4011", "CD4017"]

LOGIC_DETAILS = {
    "Package": "DIP14",
    "Vector count": "15",
}


def emit_version() -> None:
    sys.stderr.write(
        "Supported programmers: TL866A/CS, TL866II+, T48, T56, T76\n"
        f"Found T76 {FIRMWARE}\n"
        "Device code: 46A16257\n"
        "Serial code: HSSCVO9LARFMOYKYOMVE5123\n"
        "Manufactured: 2025-03-1409:30\n"
        "Supply voltage: 5.11 V\n"
        "USB speed: 5000Mbps (USB 3.0)\n"
        "minipro version 0.7.4     A free and open TL866 series programmer\n"
        "Commit date:\t2026-07-13 16:12:34 +0200\n"
        "Git commit:\tcae74c0607077d6260b24995f5e4c0d0b66a6a2e\n"
        "Git branch:\tmaster\n"
    )


def emit_list() -> None:
    for chip in EEPROM_CHIPS + LOGIC_CHIPS:
        sys.stdout.write(chip + "\n")


def emit_get_info(device: str) -> None:
    if device in LOGIC_CHIPS:
        sys.stderr.write(
            f"Name: {device}\n"
            "Available on: TL866A/CS, TL866II+, T48, T56, T76\n"
            "Memory: 0\n"
            f"Package: {LOGIC_DETAILS['Package']}\n"
            "Default VCC voltage: 5.0V\n"
            f"Vector count: {LOGIC_DETAILS['Vector count']}\n"
        )
        return

    sys.stderr.write(
        f"Name: {device}\n"
        "Available on: TL866A/CS, TL866II+, T48, T56, T76\n"
        "Memory: 32768 Bytes\n"
        "Package: DIP28\n"
        "Default VCC voltage: 5.0V\n"
        "Protocol: 0x0b\n"
        "Read buffer size: 128 Bytes\n"
        "Write buffer size: 128 Bytes\n"
        "Default VPP programming voltage: 12.5V\n"
        "Default VDD write voltage: 6.5V\n"
        "Default VCC verify voltage: 5.0V\n"
        "Default write pulse: 1000us\n"
    )


def emit_read() -> None:
    sys.stderr.write("Chip ID: 0x1E63  OK\n")
    for percent in (0, 25, 50, 75, 100):
        sys.stderr.write(f"Reading Code...  {percent}%\n")
        sys.stderr.flush()
    # A recognisable 32 KiB pattern.
    payload = bytes((offset * 7 + (offset >> 8)) & 0xFF for offset in range(32768))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def emit_write() -> None:
    sys.stdin.buffer.read()
    for percent in (0, 50, 100):
        sys.stderr.write(f"Writing Code...  {percent}%\n")
    for percent in (0, 50, 100):
        sys.stderr.write(f"Reading Code...  {percent}%\n")
    sys.stderr.write("Verification OK\n")


def emit_logic_test() -> None:
    sys.stdout.write("     1 2 3 4 5 6 7 8 9 10 11 12 13 14\n")
    for row in range(1, 8):
        pins = " ".join("1" if (row + index) % 2 else "0" for index in range(14))
        sys.stdout.write(f"{row:>4} {pins} |\n")


def main(argv: list[str]) -> int:
    args = argv[1:]

    if "--logic_test" in args:
        emit_logic_test()
        return 0
    if "--list" in args:
        emit_list()
        return 0
    if "--get_info" in args:
        emit_get_info(args[args.index("--get_info") + 1])
        return 0
    if "--read" in args:
        emit_read()
        return 0
    if "--write" in args:
        emit_write()
        return 0
    if "--update" in args:
        sys.stderr.write("Reflashing...  100%\nReflash... OK\n")
        return 0

    emit_version()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
