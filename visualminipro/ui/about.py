"""About page.

Port of MiniproUI/VisualMiniproInfoView.swift (Visual Minipro 1.5.8).
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from ..minipro import APP_VERSION
from .model import MiniproModel
from .widgets import TabHeader, property_row


class AboutPage(Gtk.Box):
    def __init__(self, model: MiniproModel, window: Gtk.Window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._model = model
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)

        self.append(TabHeader("About Visual Minipro", "help-about-symbolic"))

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        scroller = Gtk.ScrolledWindow(child=self._content, vexpand=True)
        self.append(scroller)

        model.connect("programmer-changed", lambda _m: self.rebuild())
        self.rebuild()

    def rebuild(self) -> None:
        child = self._content.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._content.remove(child)
            child = nxt

        intro = Gtk.Label(
            xalign=0.0,
            label=(
                "A GTK4 port of Visual Minipro for Linux, driving the minipro command-line "
                "tool. Both this port and minipro are released under the GNU General Public "
                "License."
            ),
        )
        intro.set_wrap(True)
        self._content.append(intro)

        group = Adw.PreferencesGroup(title="Build")
        info = self._model.visual_minipro_info
        if info is not None and info.details:
            for pair in info.details:
                group.add(property_row(pair.key, pair.value))
        else:
            group.add(property_row("Version", APP_VERSION))
        self._content.append(group)

        links = Adw.PreferencesGroup(title="Upstream Projects")
        for title, uri in (
            ("Visual Minipro (macOS original)", "https://github.com/moozzyk/MiniproUI"),
            ("minipro command-line tool", "https://gitlab.com/DavidGriffith/minipro"),
        ):
            row = Adw.ActionRow(title=title, subtitle=uri)
            row.add_suffix(Gtk.LinkButton(uri=uri, label="Open", valign=Gtk.Align.CENTER))
            links.add(row)
        self._content.append(links)
