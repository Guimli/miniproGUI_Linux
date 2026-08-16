# MAME ROM database

This directory holds `mame_roms.db`, the SQLite database used to identify a
chip's contents by SHA1. It is **not** tracked in Git: at 54 MB it would sit in
the repository history forever and be downloaded by every clone.

The application works fine without it — the MAME Database tab simply explains
that no database is configured, and everything else behaves normally.

## Getting it

**From a release (easiest).** The `.deb` published on the
[Releases page](https://github.com/Guimli/miniproGUI_Linux/releases) already
contains the database and installs it to
`/usr/share/visual-minipro/data/mame_roms.db`.

**Building it yourself.** The database is produced by the
[minipro+](https://gitlab.com/DavidGriffith/minipro) project:

```bash
pip install py7zr
python3 build_mame_database.py      # downloads the latest MAME DAT set
cp mame_roms.db /path/to/this/data/
```

**Pointing at an existing copy.** If you already have one, leave this directory
empty and set its location in the application under
**Settings → MAME ROM Database**.

## What the application expects

A SQLite database with minipro+'s schema — `roms`, `machines`, `machine_roms`,
`rom_names` and `manufacturers`, with `roms.sha1` stored as a 20-byte BLOB and
`machines.description` zlib-compressed. Any database built by
`build_mame_database.py` qualifies.

Once present here, it is picked up automatically: the bundled copy is the first
candidate in the lookup order, ahead of `~/minipro+/mame_roms.db`.
