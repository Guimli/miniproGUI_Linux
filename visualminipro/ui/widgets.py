"""Reusable widgets.

Ports of TabHeaderView.swift, PropertyRowView.swift, ErrorBannerView.swift,
SearchableListView.swift, OptionToggleRow.swift, ProgressBarView.swift,
MissingAlgorithmsView.swift and ProgrammerNotConnectedView.swift
(Visual Minipro 1.5.8).
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

SOFTWARE_BUNDLE_HELP_URL = (
    "https://github.com/moozzyk/MiniproUI/wiki/Software-Bundles-for-T56-and-T76"
)
FIRMWARE_HELP_URL = "https://github.com/moozzyk/MiniproUI/wiki/Downloading-Firmware"


class TabHeader(Gtk.Box):
    """Icon + caption strip at the top of each page."""

    def __init__(self, caption: str, icon_name: str, secondary_caption: str = ""):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        self._icon = Gtk.Image.new_from_icon_name(icon_name)
        self._icon.set_pixel_size(32)
        self.append(self._icon)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._caption = Gtk.Label(xalign=0.0, label=caption)
        self._caption.add_css_class("title-2")
        self._caption.set_wrap(True)
        self._caption.set_selectable(True)
        labels.append(self._caption)

        self._secondary = Gtk.Label(xalign=0.0, label=secondary_caption)
        self._secondary.add_css_class("dim-label")
        self._secondary.set_visible(bool(secondary_caption))
        labels.append(self._secondary)
        self.append(labels)

    def set_caption(self, caption: str) -> None:
        self._caption.set_label(caption)

    def set_secondary_caption(self, caption: Optional[str]) -> None:
        self._secondary.set_label(caption or "")
        self._secondary.set_visible(bool(caption))


def format_byte_count(size: int) -> str:
    """Group thousands with narrow no-break spaces so the count never wraps."""
    return f"{size:,}".replace(",", " ") + " bytes"


def property_row(label: str, value: str) -> Adw.ActionRow:
    """A read-only label/value pair, selectable so values can be copied."""
    row = Adw.ActionRow(title=label)
    value_label = Gtk.Label(label=value, selectable=True, xalign=1.0)
    value_label.add_css_class("dim-label")
    value_label.set_wrap(True)
    value_label.set_max_width_chars(48)
    row.add_suffix(value_label)
    return row


class ErrorBanner(Gtk.Box):
    """Inline warning block, the equivalent of ErrorBannerView."""

    def __init__(self, title: str = "", body: str = "", icon_name: str = "dialog-warning-symbolic"):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.add_css_class("card")
        self.set_margin_top(6)
        self.set_margin_bottom(6)
        for edge in ("set_margin_start", "set_margin_end"):
            getattr(self, edge)(0)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(24)
        icon.add_css_class("warning")
        icon.set_valign(Gtk.Align.START)
        icon.set_margin_top(12)
        icon.set_margin_start(12)
        self.append(icon)

        self._text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._text_box.set_margin_top(12)
        self._text_box.set_margin_bottom(12)
        self._text_box.set_margin_end(12)
        self._text_box.set_hexpand(True)

        self._title = Gtk.Label(xalign=0.0, label=title)
        self._title.add_css_class("heading")
        self._title.set_wrap(True)
        self._title.set_visible(bool(title))
        self._text_box.append(self._title)

        self._body = Gtk.Label(xalign=0.0, label=body)
        self._body.set_wrap(True)
        self._body.set_selectable(True)
        self._body.set_visible(bool(body))
        self._text_box.append(self._body)

        self.append(self._text_box)

    def set_title(self, title: str) -> None:
        self._title.set_label(title)
        self._title.set_visible(bool(title))

    def set_body(self, body: str) -> None:
        self._body.set_label(body)
        self._body.set_visible(bool(body))

    def append_widget(self, widget: Gtk.Widget) -> None:
        self._text_box.append(widget)


def programmer_not_connected_banner() -> ErrorBanner:
    return ErrorBanner(
        title="Programmer not connected",
        body=(
            "Connect an XGecu programmer over USB and it will be detected automatically.\n\n"
            "If it is plugged in but not detected, check that your user is in the "
            "'plugdev' group and that minipro's udev rules are installed."
        ),
        icon_name="dialog-information-symbolic",
    )


def missing_algorithms_banner(detail: str = "") -> ErrorBanner:
    banner = ErrorBanner(
        title="Programming algorithms are not installed",
        body=(
            detail
            or "This programmer stores its programming algorithms outside the firmware."
        ),
    )
    hint = Gtk.Label(
        xalign=0.0,
        label=(
            "Go to Programmer Info → Software Bundle Installation and select the "
            "Xgpro .rar bundle for your firmware version."
        ),
    )
    hint.set_wrap(True)
    hint.add_css_class("dim-label")
    banner.append_widget(hint)
    return banner


def option_toggle_row(title: str, active: bool, show_warning: bool) -> Adw.SwitchRow:
    """A switch row; warning options get a marker so risky choices stand out."""
    row = Adw.SwitchRow(title=title, active=active)
    if show_warning:
        icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        icon.add_css_class("warning")
        icon.set_tooltip_text("Overriding this safety check can damage a chip or produce a bad write.")
        row.add_prefix(icon)
    return row


class SearchableList(Gtk.Box):
    """Filterable single-selection chip list.

    Port of SearchableListView.swift, including the optional favourites filter
    which falls back to the full list when no favourite matches.
    """

    def __init__(
        self,
        on_selection_changed: Callable[[Optional[str]], None],
        show_filter_toggle: bool = False,
        filter_toggle_label: str = "Favorites only",
        additional_filter: Optional[Callable[[list[str]], list[str]]] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._items: list[str] = []
        self._on_selection_changed = on_selection_changed
        self._additional_filter = additional_filter
        self._selected: Optional[str] = None
        self._suppress_signal = False

        self._search = Gtk.SearchEntry(placeholder_text="Search chips")
        self._search.connect("search-changed", lambda _entry: self._refilter())
        self.append(self._search)

        self._filter_toggle: Optional[Gtk.CheckButton] = None
        if show_filter_toggle:
            self._filter_toggle = Gtk.CheckButton(label=filter_toggle_label, active=True)
            self._filter_toggle.connect("toggled", lambda _button: self._refilter())
            self.append(self._filter_toggle)

        self._list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.connect("row-selected", self._on_row_selected)

        scroller = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            child=self._list_box,
            vexpand=True,
        )
        self.append(scroller)

        self._count_label = Gtk.Label(xalign=0.0)
        self._count_label.add_css_class("dim-label")
        self._count_label.add_css_class("caption")
        self.append(self._count_label)

    @property
    def apply_additional_filter(self) -> bool:
        return bool(self._filter_toggle and self._filter_toggle.get_active())

    @property
    def selected_item(self) -> Optional[str]:
        return self._selected

    def set_items(self, items: Iterable[str]) -> None:
        self._items = list(items)
        self._refilter()

    def _visible_items(self) -> list[str]:
        items = self._items
        if self._additional_filter is not None and self.apply_additional_filter:
            items = self._additional_filter(items)
        needle = self._search.get_text().strip().lower()
        if needle:
            items = [item for item in items if needle in item.lower()]
        return items

    def _refilter(self) -> None:
        visible = self._visible_items()
        previously_selected = self._selected

        self._suppress_signal = True
        child = self._list_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._list_box.remove(child)
            child = nxt

        # A very long list makes the ListBox crawl; cap it and say so.
        capped = visible[:2000]
        for item in capped:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=item, xalign=0.0)
            label.set_margin_top(6)
            label.set_margin_bottom(6)
            label.set_margin_start(10)
            label.set_margin_end(10)
            label.set_ellipsize(3)  # Pango.EllipsizeMode.END
            label.set_tooltip_text(item)
            row.set_child(label)
            self._list_box.append(row)
            if item == previously_selected:
                self._list_box.select_row(row)
        self._suppress_signal = False

        if len(visible) > len(capped):
            self._count_label.set_label(
                f"Showing {len(capped)} of {len(visible)} matches — refine the search"
            )
        else:
            self._count_label.set_label(f"{len(visible)} chips")

    def _on_row_selected(self, _list_box: Gtk.ListBox, row: Optional[Gtk.ListBoxRow]) -> None:
        if self._suppress_signal:
            return
        value = row.get_child().get_label() if row is not None else None
        if value == self._selected:
            return
        self._selected = value
        self._on_selection_changed(value)


class ProgressDialog(Adw.Window):
    """Modal progress sheet.

    Port of ProgressBarView.swift + ModalDialogView.swift. minipro reports
    percentages for read/write/reflash; anything else runs as a pulse.
    """

    def __init__(self, parent: Gtk.Window, label: str):
        super().__init__(
            transient_for=parent,
            modal=True,
            resizable=False,
            default_width=420,
            title=label,
        )
        self.set_deletable(False)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(28)
        content.set_margin_bottom(28)
        content.set_margin_start(28)
        content.set_margin_end(28)

        self._label = Gtk.Label(label=label, xalign=0.0)
        self._label.add_css_class("heading")
        self._label.set_wrap(True)
        content.append(self._label)

        self._progress = Gtk.ProgressBar(show_text=True, text="Working…")
        content.append(self._progress)

        self._detail = Gtk.Label(xalign=0.0, label="")
        self._detail.add_css_class("dim-label")
        self._detail.add_css_class("caption")
        self._detail.set_wrap(True)
        content.append(self._detail)

        toolbar = Adw.ToolbarView(content=content)
        toolbar.add_top_bar(Adw.HeaderBar(show_end_title_buttons=False, show_start_title_buttons=False))
        self.set_content(toolbar)

        self._pulsing = False

    def set_label(self, label: str) -> None:
        self._label.set_label(label)

    def set_progress(self, operation: str, percentage: int) -> None:
        self._pulsing = False
        self._progress.set_fraction(max(0.0, min(1.0, percentage / 100.0)))
        self._progress.set_text(f"{percentage}%")
        self._detail.set_label(operation)

    def pulse(self) -> None:
        self._pulsing = True
        self._progress.pulse()


def error_dialog(parent: Gtk.Window, heading: str, message: str) -> None:
    """Port of the SwiftUI .alert(item:) error presentation."""
    dialog = Adw.AlertDialog(heading=heading, body=message)
    dialog.add_response("ok", "OK")
    dialog.set_default_response("ok")
    dialog.set_close_response("ok")
    dialog.present(parent)
