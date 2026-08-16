#!/bin/bash
# Build an installable .deb for Visual Minipro (Linux port).
#
#   ./build-deb.sh              build the package into dist/
#   ./build-deb.sh --install    build it, then install it with apt
#   ./build-deb.sh --clean      remove build/ and dist/
#
# The package version is read from the application source so the two can never
# drift. Override the Debian revision or maintainer with:
#   DEB_REVISION=2 MAINTAINER="Jane <jane@example.org>" ./build-deb.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$APP_DIR/build"
DIST_DIR="$APP_DIR/dist"

PACKAGE="visual-minipro"
DEB_REVISION="${DEB_REVISION:-1}"
MAINTAINER="${MAINTAINER:-$(id -un)@$(hostname --fqdn 2>/dev/null || hostname)}"
case "$MAINTAINER" in
    *"<"*) ;;                                   # already "Name <email>"
    *) MAINTAINER="Visual Minipro packaging <$MAINTAINER>" ;;
esac

# Where the application lives once installed.
INSTALL_PREFIX="/usr/share/$PACKAGE"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m warning:\033[0m %s\n' "$*" >&2; }
die()   { printf '\033[1;31m error:\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- clean

if [ "${1:-}" = "--clean" ]; then
    rm -rf "$BUILD_DIR" "$DIST_DIR"
    info "Removed build/ and dist/"
    exit 0
fi

command -v dpkg-deb >/dev/null 2>&1 || die "dpkg-deb not found (install dpkg-dev)"
command -v fakeroot >/dev/null 2>&1 || die "fakeroot not found (sudo apt install fakeroot)"

# --------------------------------------------------------------- version

VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"$/\1/p' \
    "$APP_DIR/visualminipro/minipro/processors/app_info.py")"
[ -n "$VERSION" ] || die "Could not read APP_VERSION from the application source"
FULL_VERSION="${VERSION}-${DEB_REVISION}"

info "Building $PACKAGE $FULL_VERSION"

# ----------------------------------------------------------------- stage

STAGE="$BUILD_DIR/$PACKAGE"
rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" \
         "$STAGE$INSTALL_PREFIX" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/scalable/apps" \
         "$STAGE/usr/share/doc/$PACKAGE" \
         "$STAGE/usr/share/man/man1"

info "Staging application files"
# Ship the app only - no tests, no caches, no development helpers.
cp -r "$APP_DIR/visualminipro" "$STAGE$INSTALL_PREFIX/"
find "$STAGE$INSTALL_PREFIX" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$STAGE$INSTALL_PREFIX" -name '*.py[co]' -delete

# The bundled MAME ROM database, if present. It sits beside the Python package
# so that the same relative lookup works in the source tree and once installed.
if [ -f "$APP_DIR/data/mame_roms.db" ]; then
    DB_SIZE="$(du -h "$APP_DIR/data/mame_roms.db" | cut -f1)"
    info "Including MAME database ($DB_SIZE)"
    mkdir -p "$STAGE$INSTALL_PREFIX/data"
    cp "$APP_DIR/data/mame_roms.db" "$STAGE$INSTALL_PREFIX/data/"
else
    warn "data/mame_roms.db not found - the package will ship without it"
fi

# ---------------------------------------------------------------- launcher

# The in-tree bin/visual-minipro resolves its directory relative to itself,
# which is wrong once installed to /usr/bin, so the packaged launcher points
# straight at the install prefix.
cat > "$STAGE/usr/bin/$PACKAGE" <<EOF
#!/bin/sh
# Visual Minipro (Linux port) - packaged launcher.
exec python3 -c "import sys; sys.path.insert(0, '$INSTALL_PREFIX'); from visualminipro.ui.app import main; sys.exit(main(sys.argv))" "\$@"
EOF
chmod 755 "$STAGE/usr/bin/$PACKAGE"

# ----------------------------------------------------------------- icon

cat > "$STAGE/usr/share/icons/hicolor/scalable/apps/$PACKAGE.svg" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <rect x="16" y="16" width="32" height="32" rx="3" fill="#3584e4"/>
  <rect x="23" y="23" width="18" height="18" rx="2" fill="#1c71d8"/>
  <g fill="#5e5c64">
    <rect x="8"  y="21" width="8" height="4" rx="1"/>
    <rect x="8"  y="30" width="8" height="4" rx="1"/>
    <rect x="8"  y="39" width="8" height="4" rx="1"/>
    <rect x="48" y="21" width="8" height="4" rx="1"/>
    <rect x="48" y="30" width="8" height="4" rx="1"/>
    <rect x="48" y="39" width="8" height="4" rx="1"/>
  </g>
</svg>
EOF

# --------------------------------------------------------------- desktop

sed -e "s|^Exec=.*|Exec=$PACKAGE|" \
    -e "s|^Icon=.*|Icon=$PACKAGE|" \
    "$APP_DIR/visual-minipro.desktop" \
    > "$STAGE/usr/share/applications/$PACKAGE.desktop"

# --------------------------------------------------------------- man page

cat > "$STAGE/usr/share/man/man1/$PACKAGE.1" <<EOF
.TH VISUAL-MINIPRO 1 "$(date -u '+%B %Y')" "$PACKAGE $VERSION" "User Commands"
.SH NAME
visual-minipro \- graphical front-end for XGecu chip programmers
.SH SYNOPSIS
.B visual-minipro
.SH DESCRIPTION
.B visual-minipro
is a GTK4 front-end for the
.BR minipro (1)
command-line tool, supporting the XGecu TL866A/CS, TL866II+, T48, T56 and T76
programmers. It reads and writes EEPROM and flash devices, tests 74xx/40xx
logic ICs, installs the Xgpro algorithm bundles required by the T56 and T76,
and updates programmer firmware.
.PP
After every chip read or file open the buffer is hashed with SHA1 and looked up
in a MAME ROM database, when one is configured, to identify known arcade ROMs.
.SH REQUIREMENTS
The
.BR minipro (1)
tool must be installed separately; it is not packaged in Debian. See
.I /usr/share/doc/$PACKAGE/README.md
for build instructions.
.SH FILES
.TP
.I ~/.config/$PACKAGE/settings.json
User settings.
.TP
.I ~/.local/share/$PACKAGE/
Generated algorithm databases, keyed by programmer model and firmware version.
.SH SEE ALSO
.BR minipro (1)
EOF
gzip -9n "$STAGE/usr/share/man/man1/$PACKAGE.1"

# ------------------------------------------------------------ doc/copyright

cp "$APP_DIR/README.md" "$STAGE/usr/share/doc/$PACKAGE/"

cat > "$STAGE/usr/share/doc/$PACKAGE/copyright" <<'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Visual Minipro (Linux port)
Source: https://github.com/moozzyk/MiniproUI
Comment:
 A GTK4 port of Visual Minipro by Pawel Kadluczka, driving the minipro tool by
 David Griffith (https://gitlab.com/DavidGriffith/minipro).
 .
 The two upstreams are not licensed identically. minipro is GPL-3+, but Visual
 Minipro ships the GPL version 3 text with no "or any later version" grant, in
 its LICENSE file, its README or its source headers. This port is a derivative
 of Visual Minipro - it reuses its parsing rules, the T76 algorithm byte
 offsets, the software-bundle checksum table and its test fixtures - so it
 inherits the more restrictive of the two: GPL-3 only.

Files: *
Copyright: 2025-2026 Pawel Kadluczka and the Visual Minipro Linux port contributors
License: GPL-3
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License version 3 as
 published by the Free Software Foundation.
 .
 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.
 .
 On Debian systems, the complete text of the GNU General Public License
 version 3 can be found in /usr/share/common-licenses/GPL-3.
EOF

cat > "$BUILD_DIR/changelog" <<EOF
$PACKAGE ($FULL_VERSION) unstable; urgency=medium

  * GTK4/libadwaita port of Visual Minipro $VERSION for Linux.
  * Supports TL866A/CS, TL866II+, T48, T56 and T76 programmers.
  * SHA1 and MAME ROM identification after each read or file open.

 -- $MAINTAINER  $(date -R)
EOF
gzip -9nc "$BUILD_DIR/changelog" > "$STAGE/usr/share/doc/$PACKAGE/changelog.Debian.gz"

# ---------------------------------------------------------------- control

INSTALLED_SIZE="$(du -ks "$STAGE" | cut -f1)"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: $PACKAGE
Version: $FULL_VERSION
Section: electronics
Priority: optional
Architecture: all
Depends: python3 (>= 3.9),
         python3-gi (>= 3.42),
         gir1.2-gtk-4.0 (>= 4.10),
         gir1.2-adw-1 (>= 1.5),
         libarchive-tools
Suggests: sqlite3
Maintainer: $MAINTAINER
Installed-Size: $INSTALLED_SIZE
Homepage: https://github.com/moozzyk/MiniproUI
Description: graphical front-end for XGecu chip programmers
 Visual Minipro is a GTK4/libadwaita application for XGecu programmers
 (TL866A/CS, TL866II+, T48, T56 and T76). It reads and writes EEPROM and flash
 devices, tests 74xx/40xx logic ICs, installs the Xgpro algorithm bundles the
 T56 and T76 require, and updates programmer firmware.
 .
 After every chip read or file open the buffer is hashed with SHA1 and looked
 up in the bundled MAME ROM database to identify known arcade ROMs. The
 database covers roughly 165000 ROMs across 50000 machines and is used
 automatically; a different one can be selected in the settings.
 .
 This is a Linux port of the macOS Visual Minipro application. It drives the
 minipro command-line tool, which is NOT packaged in Debian and must be built
 from https://gitlab.com/DavidGriffith/minipro separately. Without it the
 application starts but cannot talk to a programmer.
EOF

# --------------------------------------------------------------- maintainer

cat > "$STAGE/DEBIAN/postinst" <<EOF
#!/bin/sh
set -e

if [ "\$1" = "configure" ]; then
    if command -v py3compile >/dev/null 2>&1; then
        py3compile -p $PACKAGE $INSTALL_PREFIX >/dev/null 2>&1 || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -qtf /usr/share/icons/hicolor || true
    fi

    # minipro is not in Debian, so this cannot be expressed as a dependency.
    # Maintainer scripts run with a restricted PATH that excludes
    # /usr/local/bin, which is exactly where minipro's "make install" puts it,
    # so look there explicitly rather than trusting command -v alone.
    minipro_found=""
    for candidate in /usr/local/bin/minipro /usr/bin/minipro; do
        if [ -x "\$candidate" ]; then
            minipro_found="\$candidate"
            break
        fi
    done
    if [ -z "\$minipro_found" ] && command -v minipro >/dev/null 2>&1; then
        minipro_found="\$(command -v minipro)"
    fi

    if [ -z "\$minipro_found" ]; then
        echo ""
        echo "NOTE: the 'minipro' command-line tool was not found."
        echo "Visual Minipro is a front-end for it and needs it to reach a programmer."
        echo ""
        echo "  sudo apt install build-essential pkg-config libusb-1.0-0-dev zlib1g-dev"
        echo "  git clone https://gitlab.com/DavidGriffith/minipro.git"
        echo "  cd minipro && make && sudo make install"
        echo "  sudo cp udev/*.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules"
        echo "  sudo usermod -aG plugdev <user>   # then log out and back in"
        echo ""
    fi
fi

exit 0
EOF

cat > "$STAGE/DEBIAN/prerm" <<EOF
#!/bin/sh
set -e

if command -v py3clean >/dev/null 2>&1; then
    py3clean -p $PACKAGE >/dev/null 2>&1 || true
fi
find $INSTALL_PREFIX -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

exit 0
EOF

cat > "$STAGE/DEBIAN/postrm" <<EOF
#!/bin/sh
set -e

if [ "\$1" = "remove" ] || [ "\$1" = "purge" ]; then
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -qtf /usr/share/icons/hicolor || true
    fi
    rmdir $INSTALL_PREFIX 2>/dev/null || true
fi

exit 0
EOF

chmod 755 "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm" "$STAGE/DEBIAN/postrm"

# ------------------------------------------------------------ permissions

info "Normalising permissions"
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE$INSTALL_PREFIX" -type f -exec chmod 644 {} +
find "$STAGE/usr/share/applications" "$STAGE/usr/share/icons" \
     "$STAGE/usr/share/doc" "$STAGE/usr/share/man" -type f -exec chmod 644 {} +
chmod 755 "$STAGE/usr/bin/$PACKAGE" \
          "$STAGE/DEBIAN/postinst" "$STAGE/DEBIAN/prerm" "$STAGE/DEBIAN/postrm"

# ----------------------------------------------------------------- build

mkdir -p "$DIST_DIR"
DEB_FILE="$DIST_DIR/${PACKAGE}_${FULL_VERSION}_all.deb"

info "Building $DEB_FILE"
fakeroot dpkg-deb --build --root-owner-group "$STAGE" "$DEB_FILE" >/dev/null

if command -v lintian >/dev/null 2>&1; then
    info "Running lintian"
    lintian --no-tag-display-limit "$DEB_FILE" || warn "lintian reported issues (see above)"
else
    warn "lintian is not installed - skipping package checks"
fi

info "Done: $DEB_FILE ($(du -h "$DEB_FILE" | cut -f1))"
echo
echo "Install with:"
echo "  sudo apt install $DEB_FILE"
echo "Remove with:"
echo "  sudo apt remove $PACKAGE"

# --------------------------------------------------------------- install

if [ "${1:-}" = "--install" ]; then
    info "Installing"
    sudo apt install -y "$DEB_FILE"
fi
