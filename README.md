# Visual Minipro — Linux port

A GTK4/libadwaita port of [Visual Minipro 1.5.8](https://github.com/moozzyk/MiniproUI)
for Debian 13 (trixie), with T76 support.

The original is a macOS SwiftUI app. It cannot be built or run on Linux, so its
logic was reimplemented in Python/GTK4 while keeping the same architecture:

```
GTK4 views  ->  MiniproAPI  ->  MiniproInvoker  ->  minipro CLI binary
```

All programmer intelligence lives in the `minipro` CLI. This app is the
front-end, exactly as upstream intended ("a command-line interface that allows
for a GUI front-end if desired").

## Features

| Feature | Status |
|---|---|
| Read / write EEPROM & flash | Yes — with the full option set (`no_id_error`, `no_size_error`, `skip_verify`, `unprotect`/`protect`) |
| Hex viewer | Yes — lazily rendered, handles multi-megabyte dumps |
| SHA1 + MAME ROM identification | **Added** — not in the macOS original, see below |
| Chip search + favourites | Yes |
| 74xx/40xx logic IC testing | Yes — with per-pin failure markers |
| Programmer info & warnings | Yes |
| T76/T56 algorithm bundle install | Yes — extracts the Xgpro `.rar` and builds `algorithm.xml` |
| Firmware update | Yes — with an added confirmation step |

## Requirements

Debian 13. Everything except `libarchive-tools` ships in a default GNOME install.

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 libarchive-tools
```

### minipro

The `minipro` CLI is **not** packaged in Debian 13 and must be built from
source. Its `master` branch supports the T76 even though its README does not
yet say so (`src/t76.c`, USB `a466:1a86`).

```bash
sudo apt install build-essential pkg-config libusb-1.0-0-dev zlib1g-dev
git clone https://gitlab.com/DavidGriffith/minipro.git
cd minipro && make && sudo make install
sudo cp udev/*.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo usermod -aG plugdev "$USER"   # log out and back in
```

Verify with `minipro --version`; it should list `T76` among supported programmers.

## Install

### As a Debian package (recommended)

```bash
./build-deb.sh              # builds dist/visual-minipro_<version>-1_all.deb
./build-deb.sh --install    # builds it and installs it with apt
```

The version is read from the application source, so it can never drift from the
package version. Useful overrides:

```bash
DEB_REVISION=2 MAINTAINER="Jane <jane@example.org>" ./build-deb.sh
./build-deb.sh --clean      # remove build/ and dist/
```

The package installs to `/usr/share/visual-minipro`, with a launcher in
`/usr/bin`, a desktop entry, an icon and a man page. Remove it with
`sudo apt remove visual-minipro`.

It also ships `data/mame_roms.db`, which takes the `.deb` from 44 KB to about
14 MB (the database compresses from 54 MB to ~14 MB). Delete `data/` before
building if you would rather ship without it — the build warns and carries on,
and the app falls back to a minipro+ checkout.

`minipro` cannot be expressed as a dependency because Debian does not package
it, so the package installs without it and `postinst` prints build instructions
when it is missing.

### As a user install (development)

```bash
./install.sh
```

This symlinks a launcher into `~/.local/bin` and adds a desktop entry, both
pointing back at this directory, so `git pull` is enough to update.

**Do not use both at once.** `~/.local/bin` comes before `/usr/bin` on PATH, so
a leftover user install shadows the packaged one and you get two entries in the
application menu. Undo the user install with:

```bash
rm -f ~/.local/bin/visual-minipro ~/.local/share/applications/visual-minipro.desktop
```

Both installs share `~/.config/visual-minipro/` and
`~/.local/share/visual-minipro/`, so settings, favourites and installed
algorithm bundles survive switching between them.

Run it with `visual-minipro`, or `python3 -m visualminipro` from here.

## SHA1 and MAME ROM identification

Not part of the macOS original. Borrowed from the
[minipro+](https://gitlab.com/DavidGriffith/minipro) fork in `~/minipro+`,
which adds a `-M <database>` option doing the same lookup from the CLI.

After **every chip read and every file open**, the buffer is hashed with SHA1
and the hash is looked up in minipro+'s MAME ROM database. The Chip Programming
page shows:

- the **SHA1 next to the buffer size**, in full and selectable
- two tabs over the buffer: **Hex View** and **MAME Database**

The MAME tab lists every arcade machine using a ROM with that hash, in the same
order `minipro -M` prints them. Each match shows its description and year in the
heading, then ROM filename, machine short name and manufacturer.

The ROM size is deliberately not repeated per match: `sha1` is effectively
unique in the `roms` table (164 834 ROMs, 164 834 distinct SHA1s, none carrying
two different sizes), so a lookup resolves to exactly one size — always the one
already shown above the tabs.

The lookup is a reimplementation of minipro+'s `src/mamedb.c` in Python
(`visualminipro/utils/mamedb.py`), against the same `mame_roms.db`:

- `roms.sha1` is a 20-byte BLOB and is indexed, so lookups take ~7 ms even
  across 164 834 ROMs and 50 283 machines
- `machines.description` is zlib-compressed and is inflated on read
- `roms.size_pow2` is an exponent — the real size is `1 << size_pow2`
- the database is opened read-only (`file:…?mode=ro`), so it is never written

### Where the database comes from

The database (~165 000 ROMs across ~50 000 machines) lives at
`data/mame_roms.db` and is used **by default** when present — nothing to
configure. It sits beside the Python package, so the same relative lookup
resolves in the source tree and at `/usr/share/visual-minipro/data/` once
packaged.

At 54 MB it is **not tracked in Git**. The `.deb` on the
[Releases page](https://github.com/Guimli/miniproGUI_Linux/releases) contains
it, so installing the package gets you the database too. Cloning the source
does not — see [`data/README.md`](data/README.md) for how to build or supply
it. The application runs fine without one; only the MAME tab is affected.

Resolution order:

1. the path set in **Settings → MAME ROM Database**, if any — an explicit
   setting always wins
2. `data/mame_roms.db` bundled here
3. `~/minipro+/mame_roms.db`, `~/minipro-plus/`, then minipro's share directory

To use a newer database, rebuild it with minipro+'s `build_mame_database.py`
and either replace `data/mame_roms.db` or point at it in Settings. If no
database is present at all, everything else keeps working and the tab explains
what is missing.

Hashing and the query both run on a worker thread, so a large NAND dump does
not freeze the window.

## T76 setup

The T76 and T56 keep their per-chip programming algorithms **outside** the
firmware — they live in XGecu's Windows software. Until they are installed, the
app shows a "Programming algorithms are not installed" banner and read/write
stay disabled.

1. Download the Xgpro bundle matching your firmware version. The Programmer
   Info page names the exact file it expects (for example
   `xgpro_T76_V1321.rar` for firmware `0x112`).
2. Programmer Info → **Software Bundle Installation** → **Select Bundle…**
3. Press **Install…**

The app then extracts the archive, reads the `.alg` files from `algoT76/`,
gzip+base64-encodes each bitstream into an `algorithm.xml`, and writes it to:

```
~/.local/share/visual-minipro/T76/0x<firmware>/algorithm.xml
```

That file is passed to minipro as `--algorithms` on every operation. Because
the path is keyed by firmware version, **flashing new firmware requires
reinstalling the bundle**.

Bundles whose SHA-256 is known are verified and the result shown next to the
file name. An unknown bundle is not blocked, only flagged.

## What changed from the macOS original

The parsing logic and the algorithm/firmware byte layouts are ported verbatim.
These are the deliberate platform differences:

| macOS | Linux |
|---|---|
| `minipro` bundled inside the `.app` | Resolved from `PATH` (`/usr/local/bin/minipro`) |
| `infoic.xml` / `logicic.xml` in the app bundle | `/usr/local/share/minipro/` (installed by minipro) |
| `~/Library/Application Support` | `$XDG_DATA_HOME` (`~/.local/share/visual-minipro`) |
| `UserDefaults` | `~/.config/visual-minipro/settings.json` |
| `/usr/bin/gzip` subprocess | Python's `gzip` module (`mtime=0`, so output is reproducible) |
| `/usr/bin/bsdtar` (built in) | `bsdtar` from `libarchive-tools` |
| Swift async/await + `Task {}` | Worker threads marshalled onto the GTK loop via `GLib.idle_add` |
| `XMLDocument` | `ElementTree`, **after stripping XML comments** — see below |

Two Linux-specific issues had to be solved:

- **minipro's `infoic.xml` is not valid XML.** It contains 258 comments with
  `--` inside them, which XML forbids. macOS's `XMLDocument` tolerates this;
  Python's expat rejects the whole 19 MB file. Comments are stripped before
  parsing, and the parsed name set is cached by mtime (~0.6 s otherwise).
- **`minipro --list` prompts interactively** when no programmer is attached,
  asking which database to show. Like the original, the app queries the
  programmer first and only lists chips once one is detected.

An explicit confirmation dialog was added before any firmware flash. The
original flashes as soon as the button is pressed; a mistake there can leave the
programmer unusable.

## Testing

```bash
python3 -m unittest discover -s tests -v
```

55 tests. 38 are ported from `MiniproUITests/` and use the same real minipro output
captures — including the T76 quirk where an `FPGA Reset  OK` line follows
verification, and the negative lookahead that keeps
`Logic test failed: N errors encountered` from being treated as a fatal error.

The other 17 cover the MAME lookup, using a fixture database with the real
schema. Three of them run against the actual `~/minipro+/mame_roms.db` when it
is present (and skip when it is not), checking that minipro+'s own worked
example — the 8 KiB Pole Position ROM
`52342572940489175607BBF5B6CFD05EE9B0F004` — still resolves to `polepos` and
friends.

There is also a fake programmer for exercising the UI without hardware:

```bash
PATH="$PWD/tests/fake-bin:$PATH" python3 -m visualminipro
```

It reports a connected T76 on firmware `0x271` and serves a synthetic chip list,
32 KiB reads, and logic-test vectors.

## Hardware validation

Verified against a real XGecu T76 (USB `a466:1a86`, firmware `00.1.18 (0x112)`,
USB 3.0 at 5 Gbps), accessed without root via minipro's udev rules:

- Programmer detected and fully identified — device code, serial, manufacture
  date, USB speed and supply voltage all parsed correctly
- 29 789 chips loaded from the T76 database
- Both firmware warnings rendered, including the multi-line
  "Firmware is newer than expected" one folded into a single readable line
- The exact matching software bundle for firmware `0x112` correctly identified
  as `xgpro_T76_V1321.rar`

Read and write against a physical chip were not exercised — no EEPROM was in
the socket. The read path was verified end to end against the fake programmer
(32 KiB transferred into the hex viewer).

## Known limitations

- The chip list caps at 2000 visible rows and says so; narrow the search to
  reach the rest. The T76 database has ~34 600 devices.
- The "legacy InfoIC database" setting is disabled unless an
  `infoic_0.7.4.xml` is present in minipro's share directory. Current minipro
  ships only `infoic.xml`.

## Licence

**GPL version 3 only** — not "version 3 or later".

The two upstreams are not licensed identically:

| Project | Licence |
|---|---|
| [Visual Minipro](https://github.com/moozzyk/MiniproUI) (the original) | GPL-3.0 **only** |
| [minipro](https://gitlab.com/DavidGriffith/minipro) (the tool being driven) | GPL-3.0-**or-later** |
| This port | GPL-3.0 **only** |

Visual Minipro ships the plain GPL version 3 text and grants no "or any later
version" option — the clause appears nowhere in its `LICENSE`, its `README` or
its source headers, and it carries no SPDX identifier. This port is a
derivative of it: it reuses its parsing rules, the T76 algorithm byte offsets,
the software-bundle checksum table and its test fixtures. It therefore inherits
the more restrictive of the two licences.

`minipro` is a separate program invoked as a subprocess, not linked into this
one, so its more permissive GPL-3+ terms do not widen what applies here.
