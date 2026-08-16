#!/bin/bash
# Install Visual Minipro (Linux port) for the current user.
#
# Puts a launcher in ~/.local/bin and a desktop entry in
# ~/.local/share/applications. Nothing is copied - the launcher points back at
# this directory, so `git pull` is enough to update.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

echo "==> Checking dependencies"

missing_packages=()
python3 - <<'PY' 2>/dev/null || missing_packages+=("python3-gi gir1.2-gtk-4.0 gir1.2-adw-1")
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
PY

command -v bsdtar >/dev/null 2>&1 || missing_packages+=("libarchive-tools")

if [ ${#missing_packages[@]} -gt 0 ]; then
    echo "Missing dependencies. Install them with:"
    echo "  sudo apt install ${missing_packages[*]}"
    exit 1
fi

if ! command -v minipro >/dev/null 2>&1; then
    cat <<'EOF'
The 'minipro' command-line tool was not found.

Visual Minipro is a front-end for it - install it first:

  sudo apt install build-essential pkg-config libusb-1.0-0-dev zlib1g-dev
  git clone https://gitlab.com/DavidGriffith/minipro.git
  cd minipro && make && sudo make install
  sudo cp udev/*.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules
  sudo usermod -aG plugdev "$USER"     # log out and back in afterwards
EOF
    exit 1
fi

echo "    minipro: $(command -v minipro)"

echo "==> Installing launcher"
mkdir -p "$BIN_DIR" "$DESKTOP_DIR"
ln -sf "$APP_DIR/bin/visual-minipro" "$BIN_DIR/visual-minipro"
chmod +x "$APP_DIR/bin/visual-minipro"

echo "==> Installing desktop entry"
sed "s|^Exec=.*|Exec=$BIN_DIR/visual-minipro|" "$APP_DIR/visual-minipro.desktop" \
    > "$DESKTOP_DIR/visual-minipro.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

echo
echo "Installed. Launch it from your application menu, or run:"
echo "  visual-minipro"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo
       echo "Note: $BIN_DIR is not on your PATH."
       echo "Add it with:  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.profile" ;;
esac

if ! id -nG "$USER" | grep -qw plugdev; then
    echo
    echo "Note: you are not in the 'plugdev' group, so the programmer may not be"
    echo "accessible without root. Fix it with:"
    echo "  sudo usermod -aG plugdev $USER   # then log out and back in"
fi
