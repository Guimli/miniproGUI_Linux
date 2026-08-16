"""Binary buffer viewer.

Port of MiniproUI/BinaryDataView.swift (Visual Minipro 1.5.8).

Rows are produced on demand by a lazy Gio.ListModel so that multi-megabyte
NAND dumps stay responsive - GTK only ever materialises the visible lines.
"""

from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GObject, Gtk  # noqa: E402

BYTES_PER_ROW = 16


def format_hex_row(data: bytes, offset: int) -> str:
    chunk = data[offset:offset + BYTES_PER_ROW]
    hex_part = " ".join(f"{byte:02X}" for byte in chunk)
    hex_part = hex_part.ljust(BYTES_PER_ROW * 3 - 1)
    ascii_part = "".join(chr(byte) if 0x20 <= byte <= 0x7E else "." for byte in chunk)
    return f"{offset:08X}  {hex_part}  {ascii_part}"


class HexLineModel(GObject.Object, Gio.ListModel):
    """Presents a byte buffer as one formatted string per 16 bytes."""

    def __init__(self, data: bytes = b""):
        super().__init__()
        self._data = data

    def do_get_item_type(self) -> GObject.GType:
        return Gtk.StringObject.__gtype__

    def do_get_n_items(self) -> int:
        if not self._data:
            return 0
        return (len(self._data) + BYTES_PER_ROW - 1) // BYTES_PER_ROW

    def do_get_item(self, position: int) -> Optional[Gtk.StringObject]:
        offset = position * BYTES_PER_ROW
        if offset >= len(self._data):
            return None
        return Gtk.StringObject.new(format_hex_row(self._data, offset))


class BinaryDataView(Gtk.Box):
    """Scrollable hex dump with a byte-count caption."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._data: Optional[bytes] = None

        self._model = HexLineModel()
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_setup)
        factory.connect("bind", self._on_bind)

        self._list_view = Gtk.ListView(
            model=Gtk.NoSelection(model=self._model),
            factory=factory,
        )
        self._list_view.add_css_class("monospace")

        self._placeholder = Gtk.Label(label="No data loaded")
        self._placeholder.add_css_class("dim-label")

        self._stack = Gtk.Stack()
        scroller = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            child=self._list_view,
            vexpand=True,
        )
        self._stack.add_named(self._placeholder, "empty")
        self._stack.add_named(scroller, "data")
        self._stack.set_vexpand(True)
        self.append(self._stack)

        self.set_data(None)

    def _on_setup(self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        label = Gtk.Label(xalign=0.0, selectable=True)
        label.add_css_class("monospace")
        list_item.set_child(label)

    def _on_bind(self, _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        item = list_item.get_item()
        label = list_item.get_child()
        if item is not None and label is not None:
            label.set_label(item.get_string())

    @property
    def data(self) -> Optional[bytes]:
        return self._data

    def set_data(self, data: Optional[bytes]) -> None:
        self._data = data
        self._model = HexLineModel(data or b"")
        self._list_view.set_model(Gtk.NoSelection(model=self._model))
        self._stack.set_visible_child_name("data" if data else "empty")
