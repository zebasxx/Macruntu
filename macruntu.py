#!/usr/bin/env python3
import json
import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3, Gdk, Gio, GLib, Gtk


APP_ID = "com.seb.Macruntu"
APP_NAME = "Macruntu"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "macruntu")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
HISTORY_LIMIT = 5


DEFAULT_CONFIG = {
    "macros": [
        {"label": "Email", "text": "name@example.com"},
        {"label": "Phone", "text": "+1 555 0100"},
        {"label": "Address", "text": "221B Baker Street, London"},
        {"label": "Signature", "text": "Best regards,\nSeb"},
        {"label": "API Key", "text": "REPLACE_ME", "secret": True},
    ]
}


def load_config():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(DEFAULT_CONFIG, handle, indent=2)
        return DEFAULT_CONFIG
    with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


class MacruntuApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.parent_window = None
        self.entry = None
        self.history_list = []
        self.history_box = None
        self.clipboard = None
        self.config = load_config()
        self.indicator = None
        self.secret_texts = {
            macro.get("text", "")
            for macro in self.config.get("macros", [])
            if macro.get("secret", False)
        }

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self._setup_tray()

    def do_activate(self):
        if not self.window:
            self._build_ui()
        self.window.show_all()
        self.window.present()

    def do_command_line(self, command_line):
        self.activate()
        return 0

    def _setup_tray(self):
        self.indicator = AyatanaAppIndicator3.Indicator.new(
            APP_NAME,
            "edit-paste",
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)

        menu = Gtk.Menu()
        show_item = Gtk.MenuItem(label="Show/Hide")
        show_item.connect("activate", self._toggle_window)
        menu.append(show_item)

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._quit)
        menu.append(quit_item)

        menu.show_all()
        self.indicator.set_menu(menu)

    def _toggle_window(self, *_args):
        if not self.window:
            self.activate()
            return
        if self.window.get_visible():
            self.window.hide()
        else:
            self.window.show_all()
            self.window.present()

    def _quit(self, *_args):
        self.quit()

    def _build_ui(self):
        self.parent_window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.parent_window.set_application(self)
        self.parent_window.set_decorated(False)
        self.parent_window.set_skip_taskbar_hint(True)
        self.parent_window.set_skip_pager_hint(True)
        self.parent_window.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.parent_window.set_default_size(1, 1)

        self.window = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.window.set_application(self)
        self.window.set_transient_for(self.parent_window)
        self.window.set_title(APP_NAME)
        self.window.set_default_size(520, 420)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.set_decorated(False)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_type_hint(Gdk.WindowTypeHint.POPUP_MENU)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_border_width(12)
        self.window.add(root)

        header = Gtk.EventBox()
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label=APP_NAME)
        title.set_xalign(0.0)
        close_button = Gtk.Button.new_from_icon_name("window-close", Gtk.IconSize.BUTTON)
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        close_button.connect("clicked", lambda *_args: self.window.hide())
        header_box.pack_start(title, True, True, 0)
        header_box.pack_end(close_button, False, False, 0)
        header.add(header_box)
        header.connect("button-press-event", self._on_header_press)
        root.pack_start(header, False, False, 0)

        self.entry = Gtk.Entry()
        self.entry.set_editable(False)
        self.entry.set_placeholder_text("Latest clipboard text…")
        root.pack_start(self.entry, False, False, 0)

        history_label = Gtk.Label(label="Recent clipboard history")
        history_label.set_xalign(0.0)
        root.pack_start(history_label, False, False, 0)

        self.history_box = Gtk.ListBox()
        self.history_box.set_selection_mode(Gtk.SelectionMode.NONE)
        history_scroller = Gtk.ScrolledWindow()
        history_scroller.set_vexpand(True)
        history_scroller.add(self.history_box)
        root.pack_start(history_scroller, True, True, 0)

        macros_label = Gtk.Label(label="Macros")
        macros_label.set_xalign(0.0)
        root.pack_start(macros_label, False, False, 0)

        macros_grid = Gtk.Grid()
        macros_grid.set_column_spacing(8)
        macros_grid.set_row_spacing(8)
        root.pack_start(macros_grid, False, False, 0)

        for index, macro in enumerate(self.config.get("macros", [])):
            button = Gtk.Button(label=macro.get("label", f"Macro {index + 1}"))
            button.connect(
                "clicked",
                self._apply_macro,
                macro.get("text", ""),
                bool(macro.get("secret", False)),
            )
            row = index // 2
            col = index % 2
            macros_grid.attach(button, col, row, 1, 1)

        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.clipboard.connect("owner-change", self._on_clipboard_owner_change)
        self._pull_clipboard()

    def _apply_macro(self, _button, text, secret):
        if not text:
            return
        self.clipboard.set_text(text, -1)
        if secret:
            self.entry.set_text("Secret copied")
            return
        self._update_history(text)

    def _on_clipboard_owner_change(self, *_args):
        self._pull_clipboard()

    def _pull_clipboard(self):
        self.clipboard.request_text(self._on_clipboard_text)

    def _on_clipboard_text(self, _clipboard, text):
        if text is None:
            return
        if text in self.secret_texts or text.strip() in self.secret_texts:
            return
        self._update_history(text)

    def _update_history(self, text):
        trimmed = text.strip()
        if not trimmed:
            return
        if self.history_list and self.history_list[0] == trimmed:
            return
        self.history_list.insert(0, trimmed)
        self.history_list = self.history_list[:HISTORY_LIMIT]
        self.entry.set_text(trimmed)
        self._render_history()

    def _render_history(self):
        for child in self.history_box.get_children():
            self.history_box.remove(child)
        for item in self.history_list:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=item)
            label.set_xalign(0.0)
            label.set_line_wrap(True)
            row.add(label)
            self.history_box.add(row)
        self.history_box.show_all()

    def _on_header_press(self, _widget, event):
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
            self.window.begin_move_drag(event.button, int(event.x_root), int(event.y_root), event.time)
        return True


def main():
    app = MacruntuApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
