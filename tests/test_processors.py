"""Response processor tests.

Ported from MiniproUITests/ (Visual Minipro 1.5.8). The minipro output strings
are the real captures used by the Swift tests, so a parsing regression here
means the port diverged from the original.

Run with:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import base64
import gzip
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from visualminipro.minipro import ProgrammerModel, ReadOptions, WriteOptions  # noqa: E402
from visualminipro.minipro.errors import (  # noqa: E402
    ChipIdMismatch,
    DeviceNotFound,
    IncorrectFileSize,
    InvalidChip,
    IOErrorResult,
    LogicICTestError,
    ProgrammerNotFound,
    UnknownError,
    VerificationFailed,
)
from visualminipro.minipro.invoker import InvocationResult, MiniproInvoker  # noqa: E402
from visualminipro.minipro.processors import (  # noqa: E402
    DeviceDetailsProcessor,
    DeviceIdProcessor,
    LogicICTestProcessor,
    ProgrammerInfoProcessor,
    ProgressUpdateProcessor,
    ReadProcessor,
    WriteProcessor,
)
from visualminipro.minipro.processors.utils import ensure_no_error  # noqa: E402
from visualminipro.utils.xgpro_firmware import (  # noqa: E402
    AlgorithmsNotFound,
    XgproFirmwareUtils,
)

ESC = "\x1b"

T48_HEADER = (
    "Found T48 00.1.31 (0x11f)\n"
    "Warning: T48 support is experimental!\n"
    "Device code: 46A16257\n"
    "Serial code: HSSCVO9LARFMOYKYOMVE5123\n"
    "Manufactured: 2024-06-2816:55\n"
    "USB speed: 480Mbps (USB 2.0)\n"
    "Supply voltage: 5.13 V\n"
)


def result(std_err: str = "", std_out: bytes = b"", exit_code: int = 0) -> InvocationResult:
    return InvocationResult(exit_code=exit_code, std_out=std_out, std_err=std_err)


class EnsureNoErrorTests(unittest.TestCase):
    def test_programmer_not_found(self):
        with self.assertRaises(ProgrammerNotFound):
            ensure_no_error(result("No programmer found.\n"))

    def test_device_not_found(self):
        with self.assertRaises(DeviceNotFound) as ctx:
            ensure_no_error(result("Device AT28C256X not found!\n"))
        self.assertEqual(ctx.exception.device_id, "AT28C256X")

    def test_io_error(self):
        with self.assertRaises(IOErrorResult) as ctx:
            ensure_no_error(result("IO error: Pipe error\n"))
        self.assertEqual(ctx.exception.message, "Pipe error")

    def test_invalid_chip_id(self):
        with self.assertRaises(InvalidChip) as ctx:
            ensure_no_error(result("Invalid Chip ID: expected 0xDA01, got 0xFDFD\n"))
        self.assertEqual((ctx.exception.expected, ctx.exception.actual), ("0xDA01", "0xFDFD"))

    def test_invalid_chip_id_can_be_ignored(self):
        ensure_no_error(
            result("Invalid Chip ID: expected 0xDA01, got 0xFDFD\n"),
            ignore_invalid_chip_id=True,
        )

    def test_errors_encountered_is_not_treated_as_an_error(self):
        """The negative lookahead must let logic-test failures through."""
        ensure_no_error(result("Logic test failed: 10 errors encountered.\n"))

    def test_generic_error_is_reported(self):
        with self.assertRaises(UnknownError):
            ensure_no_error(result("Error: something went wrong\n"))


class ProgrammerInfoProcessorTests(unittest.TestCase):
    def test_parses_t76(self):
        info = ProgrammerInfoProcessor.run(
            result(
                "Found T76 00.1.13 (0x10d)\n"
                "Device code: 58A02670\n"
                "Serial code: 5M55O5G378PD0XBAXPXD3032\n"
                "Manufactured: 2025-08-1817:22\n"
                "USB speed: 480Mbps (USB 2.0)\n"
                "Supply voltage: 5.25 V (USB)\n"
            )
        )
        self.assertEqual(info.model, ProgrammerModel.T76)
        self.assertEqual(info.firmware_version, "00.1.13 (0x10d)")
        self.assertEqual(info.firmware_version_number(), 0x10D)
        self.assertEqual(info.device_code, "58A02670")
        self.assertEqual(info.date_manufactured, "2025-08-18 17:22")
        self.assertEqual(info.supply_voltage, "5.25 V (USB)")

    def test_firmware_out_of_date_warning_absorbs_following_lines(self):
        info = ProgrammerInfoProcessor.run(
            result(
                "Found T48 00.1.33 (0x121)\n"
                "Warning: Firmware is out of date.\n"
                "Expected  01.1.34 (0x122)\n"
                "Found     00.1.33 (0x121)\n"
                "Device code: 46A16257\n"
                "Serial code: HSSCVO9LARFMOYKYOMVE5123\n"
                "Manufactured: 2024-06-2816:55\n"
            )
        )
        self.assertEqual(len(info.warnings), 1)
        self.assertIn("Firmware is out of date.", info.warnings[0])
        self.assertIn("Expected 01.1.34 (0x122)", info.warnings[0])
        self.assertIn("Found 00.1.33 (0x121)", info.warnings[0])

    def test_experimental_warning_is_kept_standalone(self):
        info = ProgrammerInfoProcessor.run(result(T48_HEADER))
        self.assertEqual(info.warnings, ["T48 support is experimental!"])


class DeviceDetailsProcessorTests(unittest.TestCase):
    def test_memory_chip_is_not_a_logic_chip(self):
        details = DeviceDetailsProcessor.run(
            result(
                "Name: AT28C256\n"
                "Memory: 32768 Bytes\n"
                "Package: DIP28\n"
                "Protocol: 0x0b\n"
                "Read buffer size: 128 Bytes\n"
                "Write buffer size: 128 Bytes\n"
                "Default VPP programming voltage: 12.5V\n"
            )
        )
        self.assertEqual(details.name, "AT28C256")
        self.assertFalse(details.is_logic_chip)
        self.assertEqual(len(details.programming_info), 1)

    def test_vector_count_marks_a_logic_chip(self):
        details = DeviceDetailsProcessor.run(
            result("Name: SN74LS00\nMemory: 0\nPackage: DIP14\nVector count: 15\n")
        )
        self.assertTrue(details.is_logic_chip)


class DeviceIdProcessorTests(unittest.TestCase):
    def test_reads_chip_id(self):
        self.assertEqual(DeviceIdProcessor.run(result("Chip ID: 0x1E63  OK\n")), "0x1E63")

    def test_mismatch_raises(self):
        with self.assertRaises(ChipIdMismatch):
            DeviceIdProcessor.run(result("Chip ID mismatch: expected 0xDA01, got 0xFDFD\n"))


class ReadProcessorTests(unittest.TestCase):
    def test_returns_payload(self):
        self.assertEqual(ReadProcessor.run(result("", b"\x01\x02\x03")), b"\x01\x02\x03")

    def test_non_zero_exit_raises(self):
        from visualminipro.minipro.errors import ReadError

        with self.assertRaises(ReadError):
            ReadProcessor.run(result("", b"", 1))


class WriteProcessorTests(unittest.TestCase):
    """Fixtures copied from WriteProcessorTests.swift."""

    def test_successful_response_t48(self):
        std_err = (
            T48_HEADER
            + "Chip ID: 0xDA08  OK\n"
            "Warning: Incorrect file size: 1024 (needed 65536)\n"
            "Erasing... 0.30Sec OK\n"
            f"\r{ESC}[KWriting  Code...   0%\r{ESC}[KWriting  Code...  50%"
            f"\r{ESC}[KWriting Code...  0.35Sec  OK\n"
            f"\r{ESC}[KReading Code...   0%\r{ESC}[KReading Code...  0.01Sec  OK\n"
            "Verification OK\n"
        )
        WriteProcessor.run(result(std_err), WriteOptions())

    def test_successful_response_t76_ignores_fpga_reset(self):
        """The T76 prints an FPGA reset line after verification."""
        std_err = (
            "Found T76 00.1.13 (0x10d)\n"
            "Device code: 58A02670\n"
            f"\r{ESC}[KReading Code...  46.6 ms  OK\n"
            "Verification OK\n"
            "FPGA Reset  OK\n"
        )
        WriteProcessor.run(result(std_err), WriteOptions())

    def test_verification_failure_raises(self):
        std_err = (
            "Found T48 00.1.33 (0x121)\n"
            "Erasing... 9.01Sec OK\n"
            "Writing  Code...   0%\n"
            "Verification failed at address 0x0000: File=0xF3, Device=0xFD"
        )
        with self.assertRaises(VerificationFailed) as ctx:
            WriteProcessor.run(result(std_err), WriteOptions())
        self.assertIn("Verification failed at address 0x0000", str(ctx.exception))

    def test_incorrect_file_size_raises_with_expected_and_actual(self):
        std_err = (
            "Found T48 00.1.31 (0x11f)\n"
            "Incorrect file size: 1024 (needed 65536)\n"
            "Writing Code...  OK\n"
        )
        with self.assertRaises(IncorrectFileSize) as ctx:
            WriteProcessor.run(result(std_err), WriteOptions())
        self.assertEqual(ctx.exception.expected, 65536)
        self.assertEqual(ctx.exception.actual, 1024)

    def test_skip_verification_accepts_writing_ok(self):
        WriteProcessor.run(
            result("Found T48 00.1.31 (0x11f)\nWriting Code...  0.35Sec  OK\n"),
            WriteOptions(skip_verification=True),
        )


class ProgressUpdateProcessorTests(unittest.TestCase):
    def test_parses_reading(self):
        update = ProgressUpdateProcessor.run(f"\r{ESC}[KReading Code...  42%".encode())
        self.assertIsNotNone(update)
        self.assertEqual(update.operation, "Reading Code")
        self.assertEqual(update.percentage, 42)

    def test_parses_reflashing(self):
        update = ProgressUpdateProcessor.run(b"Reflashing...  7%")
        self.assertEqual(update.operation, "Reflashing")
        self.assertEqual(update.percentage, 7)

    def test_ignores_unrelated_output(self):
        self.assertIsNone(ProgressUpdateProcessor.run(b"Erasing... OK\n"))

    def test_ignores_empty(self):
        self.assertIsNone(ProgressUpdateProcessor.run(None))


class LogicICTestProcessorTests(unittest.TestCase):
    def test_success(self):
        std_out = b"     1 2 3 4\n   1 1 0 1 0 |\n   2 0 1 0 1 |\n"
        outcome = LogicICTestProcessor.run(result("", std_out), "SN74LS00")
        self.assertTrue(outcome.is_success)
        self.assertEqual(outcome.num_errors, 0)
        self.assertEqual(len(outcome.test_vectors), 2)

    def test_failure_count_is_parsed(self):
        std_out = b"     1 2 3 4\n   1 1 0 1 0 |\n"
        outcome = LogicICTestProcessor.run(
            result("Logic test failed: 10 errors encountered.\n", std_out), "SN74LS00"
        )
        self.assertFalse(outcome.is_success)
        self.assertEqual(outcome.num_errors, 10)

    def test_failing_pin_keeps_its_marker(self):
        std_out = b"     1 2\n   1 1 0- |\n"
        outcome = LogicICTestProcessor.run(result("", std_out), "SN74LS00")
        self.assertEqual(outcome.test_vectors[0], ["1", "0-"])

    def test_step_error_raises(self):
        with self.assertRaises(LogicICTestError):
            LogicICTestProcessor.run(
                result("Error running the init step of logic test.\n"), "SN74LS00"
            )


class LibusbFilteringTests(unittest.TestCase):
    def test_libusb_lines_are_removed(self):
        raw = result(
            "[timestamp] [threadID] facility level [function call] <message>\n"
            + "-" * 80
            + "\n[ 0.1] libusb: debug [init] something\nFound T76 00.1.13 (0x10d)\n"
        )
        filtered = MiniproInvoker.filter_libusb_lines(raw)
        self.assertNotIn("libusb", filtered.std_err)
        self.assertIn("Found T76", filtered.std_err)


class XgproFirmwareUtilsTests(unittest.TestCase):
    """Ported from XgproFirmwareUtilsTests.swift."""

    @staticmethod
    def _make_t76_alg(path: Path) -> None:
        data = bytearray(5000)
        data[4:8] = b"ABCD"
        path.write_bytes(bytes(data))

    @staticmethod
    def _make_t56_alg(path: Path, description: str) -> None:
        data = bytearray(0x220 + 100)
        encoded = description.encode("ascii")
        data[0:len(encoded)] = encoded
        path.write_bytes(bytes(data))

    def test_known_bundle_names(self):
        self.assertEqual(
            XgproFirmwareUtils.get_software_name(ProgrammerModel.T76, 0x112),
            "xgpro_T76_V1321.rar",
        )
        self.assertEqual(
            XgproFirmwareUtils.get_latest_software_name(ProgrammerModel.T76),
            "xgpro_T76_V1321.rar",
        )
        self.assertIsNone(XgproFirmwareUtils.get_software_name(ProgrammerModel.T76, 0xFFFF))

    def test_create_algorithm_xml_reports_progress_for_t76(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            algorithm_directory = base / "algoT76"
            algorithm_directory.mkdir()
            self._make_t76_alg(algorithm_directory / "T7_first.alg")
            self._make_t76_alg(algorithm_directory / "T7_second.alg")

            updates = []
            xml = XgproFirmwareUtils.create_algorithm_xml(
                base, ProgrammerModel.T76, updates.append
            )

            self.assertEqual([update.percentage for update in updates], [50, 100])
            self.assertTrue(all(u.operation == "Preparing Algorithms" for u in updates))
            self.assertIn("algorithms_T76", xml)
            # The T7_ prefix is stripped from the algorithm name.
            self.assertIn('name="first"', xml)
            self.assertIn('name="second"', xml)

    def test_create_algorithm_xml_raises_without_alg_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "algoT76").mkdir()
            with self.assertRaises(AlgorithmsNotFound):
                XgproFirmwareUtils.create_algorithm_xml(base, ProgrammerModel.T76)

    def test_t56_xml_contains_description_and_names(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            algorithm_directory = base / "algorithm"
            algorithm_directory.mkdir()
            self._make_t56_alg(algorithm_directory / "ROM40P82.alg", "27C400")
            self._make_t56_alg(algorithm_directory / "SPI25F11.alg", "25F11")

            xml = XgproFirmwareUtils.create_algorithm_xml(base, ProgrammerModel.T56)
            self.assertIn("algorithms_T56", xml)
            self.assertIn("ROM40P82", xml)
            self.assertIn("SPI25F11", xml)
            self.assertIn("27C400", xml)

    def test_t76_bitstream_is_header_plus_payload_gzipped(self):
        """Bytes 4..12 are prepended to everything from offset 4096 on."""
        data = bytearray(4096 + 16)
        data[4:12] = bytes(range(8))
        data[4096:4096 + 16] = bytes(range(0x10, 0x20))

        bitstream = XgproFirmwareUtils.create_algorithm_bitstream_t76(bytes(data))
        decoded = gzip.decompress(base64.b64decode(bitstream))

        self.assertEqual(decoded[:8], bytes(range(8)))
        self.assertEqual(decoded[8:], bytes(range(0x10, 0x20)))

    def test_firmware_version_is_read_from_the_first_two_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            # 0x0112 little-endian == the V1321 bundle firmware.
            (base / "UpdateT76.Dat").write_bytes(b"\x12\x01" + bytes(64))
            info = XgproFirmwareUtils.get_firmware_info(base)
            self.assertEqual(info.programmer_model, ProgrammerModel.T76)
            self.assertEqual(info.firmware_version, 0x112)
            self.assertEqual(info.file_name, "UpdateT76.Dat")

    def test_t76_wins_when_both_firmware_files_are_present(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "UpdateT76.Dat").write_bytes(b"\x12\x01" + bytes(16))
            (base / "updatet56.dat").write_bytes(b"\x49\x01" + bytes(16))
            self.assertEqual(
                XgproFirmwareUtils.get_firmware_info(base).programmer_model,
                ProgrammerModel.T76,
            )


class AlgorithmPathTests(unittest.TestCase):
    def test_path_is_keyed_by_model_and_firmware(self):
        from visualminipro.utils.algorithm_xml import resolve_algorithm_xml_path

        path = resolve_algorithm_xml_path(ProgrammerModel.T76, 0x271)
        self.assertEqual(path.name, "algorithm.xml")
        self.assertEqual(path.parent.name, "0x271")
        self.assertEqual(path.parent.parent.name, "T76")


if __name__ == "__main__":
    unittest.main()
