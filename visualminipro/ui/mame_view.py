"""MAME database results tab.

Linux-only addition, not present in the macOS original. Shows which arcade
machines use a ROM matching the current buffer's SHA1, using the database from
the minipro+ project (the same lookup its `-M` option performs).
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ..utils import MameMatch, database_summary, find_database, settings


class MameResultsView(Gtk.Box):
    """States: no buffer, searching, no match, matches, database error."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        self._status = Gtk.Label(xalign=0.0)
        self._status.set_wrap(True)
        self._status.add_css_class("heading")
        self._status.set_margin_top(8)
        self._status.set_margin_start(4)
        self.append(self._status)

        self._detail = Gtk.Label(xalign=0.0)
        self._detail.set_wrap(True)
        self._detail.set_selectable(True)
        self._detail.add_css_class("dim-label")
        self._detail.set_margin_start(4)
        self.append(self._detail)

        self._results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._results_box.set_margin_top(4)
        scroller = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            child=self._results_box,
            vexpand=True,
        )
        self.append(scroller)

        self.show_idle()

    # -- states ----------------------------------------------------------

    def _clear_results(self) -> None:
        child = self._results_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._results_box.remove(child)
            child = nxt

    def show_idle(self) -> None:
        self._clear_results()
        self._status.set_label("No data loaded")
        database_path = find_database(settings.mame_database_path)
        if database_path is None:
            self._set_detail(
                "No MAME ROM database configured. Set its location in Settings."
            )
            return
        try:
            summary = database_summary(database_path)
            self._set_detail(
                f"Read a chip or open a file to search the MAME database.\n"
                f"{database_path} — {summary}"
            )
        except Exception:  # noqa: BLE001
            self._set_detail(
                f"Read a chip or open a file to search the MAME database.\n{database_path}"
            )

    def _set_detail(self, text: str) -> None:
        """Set the sub-caption, collapsing it when there is nothing to say."""
        self._detail.set_label(text)
        self._detail.set_visible(bool(text))

    def show_searching(self) -> None:
        self._clear_results()
        self._status.set_label("Searching the MAME database…")
        self._set_detail("")

    def show_error(self, error: Exception) -> None:
        self._clear_results()
        self._status.set_label("MAME database unavailable")
        self._set_detail(str(error))

    def show_matches(self, matches: list[MameMatch]) -> None:
        # The SHA1 and its origin are already shown above the tabs, so they are
        # deliberately not repeated here.
        self._clear_results()
        self._set_detail("")

        if not matches:
            self._status.set_label("No match found in the MAME database")
            return

        machines = len({match.machine_name for match in matches})
        self._status.set_label(
            f"{len(matches)} match{'es' if len(matches) != 1 else ''} "
            f"across {machines} machine{'s' if machines != 1 else ''}"
        )

        for index, match in enumerate(matches, start=1):
            self._results_box.append(self._build_match_card(index, match))

    def _build_match_card(self, index: int, match: MameMatch) -> Gtk.Widget:
        """One heading plus a single block of fields.

        ROM Size is deliberately absent: a SHA1 identifies exactly one row in
        `roms`, so a match always has the size already shown above the tabs.
        The year rides along in the heading instead of costing its own row.
        """
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        year = f" ({match.year})" if match.year else ""
        title = Gtk.Label(
            xalign=0.0,
            label=f"Match #{index} — {match.machine_description}{year}",
            selectable=True,
        )
        title.add_css_class("heading")
        title.set_wrap(True)
        box.append(title)

        grid = Gtk.Grid(column_spacing=16, row_spacing=4)
        grid.set_margin_top(10)
        grid.set_margin_bottom(10)
        grid.set_margin_start(12)
        grid.set_margin_end(12)

        fields = (
            ("ROM File", match.rom_name, True),
            ("Machine", match.machine_name, True),
            ("Manufacturer", match.manufacturer, False),
        )
        for row_index, (label, value, monospace) in enumerate(fields):
            name_label = Gtk.Label(label=label, xalign=0.0)
            name_label.add_css_class("dim-label")
            name_label.set_valign(Gtk.Align.START)
            grid.attach(name_label, 0, row_index, 1, 1)

            value_label = Gtk.Label(label=value, xalign=0.0, selectable=True)
            if monospace:
                value_label.add_css_class("monospace")
            value_label.set_wrap(True)
            value_label.set_hexpand(True)
            grid.attach(value_label, 1, row_index, 1, 1)

        frame = Gtk.Frame(child=grid)
        frame.add_css_class("view")
        box.append(frame)
        return box
