# MAME ROM database

This directory holds `mame_roms.db`, the SQLite database used to identify a
chip's contents by SHA1. It is distributed separately from the source, in the
`.deb` rather than in Git.

The application works fine without it — the MAME Database tab simply explains
that no database is configured, and everything else behaves normally.

## Getting it

**From a release (easiest).** The `.deb` published on the
[Releases page](https://github.com/Guimli/miniproGUI_Linux/releases) already
contains the database and installs it to
`/usr/share/visual-minipro/data/mame_roms.db`.

**From the database project.** The database comes from
[MAME-Embedded-Database](https://github.com/Guimli/MAME-Embedded-Database),
which converts the official MAME DAT files into this format. Take its
`mame_roms.db` and drop it here, or rebuild it from scratch:

```bash
pip install py7zr
python3 build_mame_database.py      # downloads the latest MAME DAT set
cp mame_roms.db /path/to/this/data/
```

**Pointing at an existing copy.** If you already have one, leave this directory
empty and set its location in the application under
**Settings → MAME ROM Database**.

## What the application expects

A SQLite database with MAME-Embedded-Database's schema — `roms`, `machines`,
`machine_roms`, `rom_names` and `manufacturers`, with `roms.sha1` stored as a
20-byte BLOB and `machines.description` zlib-compressed. Any database built by
its `build_mame_database.py` qualifies.

Once present here, it is picked up automatically: the bundled copy is the first
candidate in the lookup order, ahead of `~/minipro+/mame_roms.db`.
