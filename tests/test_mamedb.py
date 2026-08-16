"""MAME database lookup tests.

Tests that need a database build a small one with MAME-Embedded-Database's
schema, so they run without the real file; the ones that need the real database
skip when it is absent.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from visualminipro.utils.mamedb import (  # noqa: E402
    MameDatabaseError,
    bundled_database_available,
    compute_sha1,
    database_summary,
    find_by_sha1,
    find_database,
)

# A known 8 KiB Pole Position ROM, shared by several machines - a good probe
# because one hash legitimately resolves to many matches.
POLE_POSITION_SHA1 = "52342572940489175607BBF5B6CFD05EE9B0F004"

BUNDLED_DATABASE = Path(__file__).resolve().parent.parent / "data" / "mame_roms.db"

_SCHEMA = """
CREATE TABLE manufacturers (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
CREATE TABLE rom_names (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
CREATE TABLE roms (
    id INTEGER PRIMARY KEY, sha1 BLOB, crc BLOB,
    size_pow2 INTEGER, name_id INTEGER
);
CREATE TABLE machines (
    id INTEGER PRIMARY KEY, name TEXT UNIQUE, cloneof_id INTEGER,
    romof_id INTEGER, description BLOB, year INTEGER, manufacturer_id INTEGER
);
CREATE TABLE machine_roms (
    id INTEGER PRIMARY KEY, machine_id INTEGER, rom_id INTEGER, name_id INTEGER
);
"""


def build_fixture_database(path: Path, sha1_hex: str) -> None:
    """A two-machine database sharing one ROM, mirroring the real schema."""
    connection = sqlite3.connect(path)
    connection.executescript(_SCHEMA)
    connection.execute("INSERT INTO manufacturers (id, name) VALUES (1, 'Namco')")
    connection.execute("INSERT INTO rom_names (id, name) VALUES (1, 'pp2_11.2e')")
    connection.execute("INSERT INTO rom_names (id, name) VALUES (2, '136014-106.9c')")
    connection.execute(
        "INSERT INTO roms (id, sha1, crc, size_pow2, name_id) VALUES (1, ?, ?, 13, 1)",
        (bytes.fromhex(sha1_hex), b"\x01\x02\x03\x04"),
    )
    for machine_id, name, description, year in (
        (1, "polepos", "Pole Position (World)", 1982),
        (2, "polepos2a", "Pole Position II (Atari)", 1983),
    ):
        connection.execute(
            "INSERT INTO machines (id, name, description, year, manufacturer_id) "
            "VALUES (?, ?, ?, ?, 1)",
            (machine_id, name, zlib.compress(description.encode("utf-8")), year),
        )
    connection.execute(
        "INSERT INTO machine_roms (id, machine_id, rom_id, name_id) VALUES (1, 1, 1, 1)"
    )
    connection.execute(
        "INSERT INTO machine_roms (id, machine_id, rom_id, name_id) VALUES (2, 2, 1, 2)"
    )
    connection.commit()
    connection.close()


class ComputeSha1Tests(unittest.TestCase):
    def test_matches_the_uppercase_hex_form_used_by_minipro_plus(self):
        # SHA1 of the empty string.
        self.assertEqual(compute_sha1(b""), "DA39A3EE5E6B4B0D3255BFEF95601890AFD80709")

    def test_is_uppercase(self):
        digest = compute_sha1(b"minipro")
        self.assertEqual(digest, digest.upper())
        self.assertEqual(len(digest), 40)


class LookupTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.database = Path(self._temp.name) / "mame_roms.db"
        build_fixture_database(self.database, POLE_POSITION_SHA1)

    def tearDown(self):
        self._temp.cleanup()

    def test_finds_every_machine_using_the_rom(self):
        matches = find_by_sha1(self.database, POLE_POSITION_SHA1)
        self.assertEqual(len(matches), 2)
        self.assertEqual([m.machine_name for m in matches], ["polepos", "polepos2a"])

    def test_description_is_decompressed(self):
        matches = find_by_sha1(self.database, POLE_POSITION_SHA1)
        self.assertEqual(matches[0].machine_description, "Pole Position (World)")

    def test_size_is_expanded_from_the_power_of_two(self):
        matches = find_by_sha1(self.database, POLE_POSITION_SHA1)
        self.assertEqual(matches[0].size, 8192)  # 2**13

    def test_rom_name_is_per_machine(self):
        matches = find_by_sha1(self.database, POLE_POSITION_SHA1)
        self.assertEqual(matches[0].rom_name, "pp2_11.2e")
        self.assertEqual(matches[1].rom_name, "136014-106.9c")

    def test_manufacturer_and_year(self):
        matches = find_by_sha1(self.database, POLE_POSITION_SHA1)
        self.assertEqual(matches[0].manufacturer, "Namco")
        self.assertEqual(matches[0].year, 1982)

    def test_lookup_is_case_insensitive_on_the_hex_input(self):
        self.assertEqual(
            len(find_by_sha1(self.database, POLE_POSITION_SHA1.lower())),
            2,
        )

    def test_unknown_sha1_returns_no_matches(self):
        self.assertEqual(find_by_sha1(self.database, "00" * 20), [])

    def test_invalid_sha1_raises(self):
        with self.assertRaises(MameDatabaseError):
            find_by_sha1(self.database, "not-a-sha1")

    def test_missing_database_raises(self):
        with self.assertRaises(MameDatabaseError):
            find_by_sha1(Path("/nonexistent/mame_roms.db"), POLE_POSITION_SHA1)

    def test_summary(self):
        self.assertEqual(database_summary(self.database), "1 ROMs · 2 machines")


class FindDatabaseTests(unittest.TestCase):
    def test_configured_path_wins(self):
        with tempfile.TemporaryDirectory() as temp:
            database = Path(temp) / "custom.db"
            build_fixture_database(database, POLE_POSITION_SHA1)
            self.assertEqual(find_database(str(database)), database)

    def test_configured_but_missing_returns_none(self):
        self.assertIsNone(find_database("/nonexistent/mame_roms.db"))


@unittest.skipUnless(BUNDLED_DATABASE.is_file(), "data/mame_roms.db not present")
class BundledDatabaseTests(unittest.TestCase):
    """Checks against the database shipped in data/."""

    def test_it_is_detected(self):
        self.assertTrue(bundled_database_available())

    def test_it_is_what_auto_detection_picks(self):
        """No configured path must resolve to the bundled copy, not elsewhere."""
        self.assertEqual(find_database(""), BUNDLED_DATABASE)
        self.assertEqual(find_database(None), BUNDLED_DATABASE)

    def test_a_configured_path_still_overrides_it(self):
        with tempfile.TemporaryDirectory() as temp:
            override = Path(temp) / "other.db"
            build_fixture_database(override, POLE_POSITION_SHA1)
            self.assertEqual(find_database(str(override)), override)

    def test_pole_position_rom_is_found(self):
        matches = find_by_sha1(BUNDLED_DATABASE, POLE_POSITION_SHA1)
        self.assertGreater(len(matches), 0)
        machines = {match.machine_name for match in matches}
        self.assertIn("polepos", machines)
        self.assertTrue(all(match.size == 8192 for match in matches))

    def test_results_are_ordered_by_machine_then_rom_name(self):
        matches = find_by_sha1(BUNDLED_DATABASE, POLE_POSITION_SHA1)
        keys = [(m.machine_name, m.rom_name) for m in matches]
        self.assertEqual(keys, sorted(keys))

    def test_descriptions_decompress(self):
        matches = find_by_sha1(BUNDLED_DATABASE, POLE_POSITION_SHA1)
        descriptions = {m.machine_description for m in matches}
        self.assertIn("Pole Position (World)", descriptions)

    def test_sha1_is_unique_per_rom(self):
        """What lets the MAME tab omit a per-match ROM size."""
        connection = sqlite3.connect(f"file:{BUNDLED_DATABASE}?mode=ro", uri=True)
        try:
            duplicates = connection.execute(
                "SELECT COUNT(*) FROM (SELECT sha1 FROM roms GROUP BY sha1 "
                "HAVING COUNT(DISTINCT size_pow2) > 1)"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(duplicates, 0)


if __name__ == "__main__":
    unittest.main()
