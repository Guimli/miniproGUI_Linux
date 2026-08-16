"""MAME ROM database lookup.

Hash the buffer with SHA1, then find every MAME machine that uses a ROM with
that hash.

The database is the `mame_roms.db` from MAME-Embedded-Database
(https://github.com/Guimli/MAME-Embedded-Database), built by its
`build_mame_database.py` (~165 000 ROMs across ~50 000 machines). Schema notes
that matter here:

  * `roms.sha1` is a 20-byte BLOB, not hex text — and it is indexed, so
    lookups are single-digit milliseconds.
  * `machines.description` is zlib-compressed.
  * `roms.size_pow2` is an exponent: the real size is `1 << size_pow2`.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger("visualminipro.mamedb")

# Ordered by machine then ROM name so repeated lookups of the same hash always
# present matches in the same order.
_LOOKUP_SQL = """
SELECT
  rn.name  AS rom_name,
  m.name   AS machine_name,
  m.description,
  man.name AS manufacturer,
  m.year,
  r.size_pow2
FROM roms r
JOIN machine_roms mr ON mr.rom_id = r.id
JOIN machines m ON mr.machine_id = m.id
JOIN rom_names rn ON mr.name_id = rn.id
LEFT JOIN manufacturers man ON m.manufacturer_id = man.id
WHERE r.sha1 = ?
ORDER BY m.name, rn.name
"""

def _bundled_database() -> Path:
    """The database shipped with this project.

    mamedb.py lives at <root>/visualminipro/utils/, so three parents up is the
    project root in the source tree and the install prefix once packaged
    (/usr/share/visual-minipro). The same expression resolves both.
    """
    return Path(__file__).resolve().parent.parent.parent / "data" / "mame_roms.db"


def _database_candidates() -> tuple[Path, ...]:
    """Auto-detection order: the bundled database first, then a checkout."""
    return (
        _bundled_database(),
        Path.home() / "MAME-Embedded-Database" / "mame_roms.db",
        Path("/usr/local/share/minipro/mame_roms.db"),
        Path("/usr/share/minipro/mame_roms.db"),
    )


@dataclass(frozen=True)
class MameMatch:
    rom_name: str
    machine_name: str
    machine_description: str
    manufacturer: str
    year: int
    size: int


class MameDatabaseError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


def compute_sha1(data: bytes) -> str:
    """Uppercase hex SHA1, the form MAME ROM databases quote hashes in."""
    return hashlib.sha1(data).hexdigest().upper()


def find_database(configured: Optional[str] = None) -> Optional[Path]:
    """Resolve the mame_roms.db path.

    An explicit setting always wins; otherwise the bundled database is used,
    falling back to a MAME-Embedded-Database checkout if this copy is missing.
    """
    if configured:
        candidate = Path(os.path.expanduser(configured))
        return candidate if candidate.is_file() else None
    for candidate in _database_candidates():
        if candidate.is_file():
            return candidate
    return None


def bundled_database_available() -> bool:
    return _bundled_database().is_file()


def _decompress_description(blob: Optional[bytes]) -> str:
    if not blob:
        return "N/A"
    try:
        return zlib.decompress(blob).decode("utf-8", errors="replace")
    except zlib.error as exc:
        logger.warning("Could not decompress machine description: %s", exc)
        return "N/A"


def find_by_sha1(database_path: Path, sha1_hex: str) -> list[MameMatch]:
    """Every machine using a ROM with this SHA1. Empty list means no match."""
    try:
        sha1_blob = bytes.fromhex(sha1_hex)
    except ValueError as exc:
        raise MameDatabaseError(f"Invalid SHA1: {sha1_hex}") from exc

    try:
        # Read-only URI so the database is never modified or journalled.
        connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise MameDatabaseError(f"Cannot open database {database_path}: {exc}") from exc

    try:
        rows = connection.execute(_LOOKUP_SQL, (sha1_blob,)).fetchall()
    except sqlite3.Error as exc:
        raise MameDatabaseError(f"Database query failed: {exc}") from exc
    finally:
        connection.close()

    return [
        MameMatch(
            rom_name=row[0] or "N/A",
            machine_name=row[1] or "N/A",
            machine_description=_decompress_description(row[2]),
            manufacturer=row[3] or "N/A",
            year=row[4] or 0,
            size=1 << row[5] if row[5] is not None else 0,
        )
        for row in rows
    ]


def database_summary(database_path: Path) -> str:
    """Short 'N ROMs, M machines' caption for the UI."""
    try:
        connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise MameDatabaseError(f"Cannot open database {database_path}: {exc}") from exc
    try:
        roms = connection.execute("SELECT COUNT(*) FROM roms").fetchone()[0]
        machines = connection.execute("SELECT COUNT(*) FROM machines").fetchone()[0]
    except sqlite3.Error as exc:
        raise MameDatabaseError(f"Database query failed: {exc}") from exc
    finally:
        connection.close()
    return f"{roms:,} ROMs · {machines:,} machines".replace(",", " ")
