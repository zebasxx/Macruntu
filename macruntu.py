#!/usr/bin/env python3
import json
import os
import shutil
import shlex
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3, Gdk, Gio, GLib, Gtk


APP_ID = "com.seb.Macruntu"
APP_NAME = "Macruntu"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "macruntu")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
AUTOSTART_DIR = os.path.join(os.path.expanduser("~"), ".config", "autostart")
AUTOSTART_PATH = os.path.join(AUTOSTART_DIR, f"{APP_ID}.desktop")
HISTORY_LIMIT = 5


DEFAULT_CONFIG = {
    "macros": [
        {"label": "Email", "text": "name@example.com"},
        {"label": "Phone", "text": "+1 555 0100"},
        {"label": "Address", "text": "221B Baker Street, London"},
        {"label": "Signature", "text": "Best regards,\nSeb"},
        {"label": "API Key", "text": "REPLACE_ME", "secret": True},
    ],
    "autostart": False,
}


def load_config():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(DEFAULT_CONFIG, handle, indent=2)
        return DEFAULT_CONFIG
    with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
        config = json.load(handle)
    if "macros" not in config:
        config["macros"] = DEFAULT_CONFIG["macros"]
    if "autostart" not in config:
        config["autostart"] = DEFAULT_CONFIG["autostart"]
    return config


class MacruntuApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE | Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self.window = None
        self.parent_window = None
        self.entry = None
        self.history_list = []
        self.history_box = None
        self.clipboard = None
        self.primary_clipboard = None
        self.config = load_config()
        self.indicator = None
        self.wl_copy_path = shutil.which("wl-copy")
        self.wtype_path = shutil.which("wtype")
        self.xdotool_path = shutil.which("xdotool")
        self.ydotool_path = shutil.which("ydotool")
        self.start_hidden = False
        self.secret_texts = {
            macro.get("text", "")
            for macro in self.config.get("macros", [])
            if macro.get("secret", False)
        }

    def _save_config(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as handle:
            json.dump(self.config, handle, indent=2)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Gtk.Window.set_default_icon_name("edit-paste")
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.primary_clipboard = Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)
        self.clipboard.connect("owner-change", self._on_clipboard_owner_change)
        self._setup_tray()
        if self.config.get("autostart", False):
            self._set_autostart_enabled(True)

    def do_activate(self):
        if not self.window:
            self._build_ui()
        self.window.show_all()
        self.window.present()

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        self.start_hidden = self._has_hidden_flag(args)
        macro_index = self._parse_macro_from_args(args)
        if macro_index is not None:
            self._apply_macro_index(macro_index)
            return 0
        if self.start_hidden:
            self._ensure_hidden_window()
            return 0
        self.activate()
        return 0

    def do_open(self, files, _n_files, _hint):
        for entry in files:
            uri = entry.get_uri()
            macro_index = self._parse_macro_from_args([uri])
            if macro_index is not None:
                self._apply_macro_index(macro_index)
                return
        self.activate()

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
        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_application(self)
        self.window.set_title(APP_NAME)
        self.window.set_icon_name("edit-paste")
        self.window.set_wmclass(APP_NAME, APP_NAME)
        self.window.set_default_size(520, 420)
        self.window.set_position(Gtk.WindowPosition.CENTER)
        self.window.set_decorated(False)
        self.window.set_skip_taskbar_hint(True)
        self.window.set_skip_pager_hint(True)
        self.window.set_type_hint(Gdk.WindowTypeHint.UTILITY)

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
        self._render_history()

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
                macro,
            )
            row = index // 2
            col = index % 2
            macros_grid.attach(button, col, row, 1, 1)

        autostart_checkbox = Gtk.CheckButton.new_with_label("Start at login")
        autostart_checkbox.set_active(bool(self.config.get("autostart", False)))
        autostart_checkbox.connect("toggled", self._toggle_autostart)
        root.pack_start(autostart_checkbox, False, False, 0)

        self._pull_clipboard()

    def _ensure_hidden_window(self):
        if not self.window:
            self._build_ui()
        self.window.hide()

    def _parse_macro_from_args(self, args):
        for arg in args:
            if arg.startswith("--macro="):
                return self._safe_index(arg.split("=", 1)[1])
            if arg == "--macro":
                continue
            if arg.startswith("macruntu://macro/"):
                return self._safe_index(arg.rsplit("/", 1)[-1])
            if arg.startswith("macro:"):
                return self._safe_index(arg.split(":", 1)[1])
        if "--macro" in args:
            idx = args.index("--macro")
            if idx + 1 < len(args):
                return self._safe_index(args[idx + 1])
        return None

    def _has_hidden_flag(self, args):
        return "--hidden" in args or "--start-hidden" in args

    def _safe_index(self, value):
        try:
            index = int(value)
        except (TypeError, ValueError):
            return None
        if index < 1:
            return None
        return index

    def _apply_macro_index(self, index):
        macros = self.config.get("macros", [])
        if index > len(macros):
            return
        macro = macros[index - 1]
        self._apply_macro(None, macro)

    def _apply_macro(self, _button, macro):
        text = macro.get("text", "")
        if not text:
            return
        secret = bool(macro.get("secret", False))
        self._set_clipboard_text(text)
        self._auto_paste(macro)
        if secret:
            if self.entry:
                self.entry.set_text("Secret copied")
            return
        self._update_history(text)

    def _on_clipboard_owner_change(self, *_args):
        self._pull_clipboard()

    def _pull_clipboard(self):
        self.clipboard.request_text(self._on_clipboard_text)

    def _set_clipboard_text(self, text):
        # Update both CLIPBOARD and PRIMARY for terminal paste compatibility.
        if self.wl_copy_path:
            self._run_wl_copy(text, primary=False)
            self._run_wl_copy(text, primary=True)
        self.clipboard.set_text(text, -1)
        self.clipboard.store()
        if self.primary_clipboard:
            self.primary_clipboard.set_text(text, -1)
            self.primary_clipboard.store()

    def _run_wl_copy(self, text, primary):
        args = [self.wl_copy_path]
        if primary:
            args.append("--primary")
        subprocess.run(args, input=text, text=True, check=False)

    def _auto_paste(self, macro):
        if not macro.get("paste", False):
            return
        delay_ms = macro.get("paste_delay_ms", 150)
        if isinstance(delay_ms, (int, float)) and delay_ms > 0:
            GLib.timeout_add(int(delay_ms), self._auto_paste_now, macro)
            return
        self._auto_paste_now(macro)

    def _auto_paste_now(self, macro):
        paste_command = macro.get("paste_command")
        if paste_command:
            self._run_command(paste_command)
            return False
        key_combo = macro.get("paste_keys", "ctrl+v")
        backend = macro.get("paste_backend")
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if backend == "xdotool" and self.xdotool_path:
            self._run_command([self.xdotool_path, "key", "--clearmodifiers", key_combo])
            return False
        if backend == "wtype" and self.wtype_path:
            if self._run_wtype_combo(key_combo) == 0:
                return False
            return False
        if backend == "ydotool" and self.ydotool_path:
            self._run_ydotool_key_combo(key_combo)
            return False
        if session == "x11" and self.xdotool_path:
            self._run_command([self.xdotool_path, "key", "--clearmodifiers", key_combo])
            return False
        if self.wtype_path:
            key_data = self._parse_key_combo(key_combo)
            if not key_data:
                return False
            key, modifiers = key_data
            if self._run_wtype_combo(key_combo) == 0:
                return False
        if self.ydotool_path:
            self._run_ydotool_key_combo(key_combo)
        return False

    def _parse_key_combo(self, combo):
        if not combo:
            return None
        parts = [part.strip().lower() for part in combo.split("+") if part.strip()]
        if not parts:
            return None
        key = parts[-1]
        modifiers = parts[:-1]
        allowed_mods = {"ctrl", "shift", "alt", "super"}
        modifiers = [mod for mod in modifiers if mod in allowed_mods]
        return key, modifiers

    def _run_ydotool_key_combo(self, combo):
        key_data = self._parse_key_combo(combo)
        if not key_data:
            return
        key, modifiers = key_data
        key_code = self._ydotool_keycode_for_key(key)
        if key_code is None:
            return
        sequence = []
        for mod in modifiers:
            mod_code = self._ydotool_modifier_code(mod)
            if mod_code is not None:
                sequence.append(f"{mod_code}:1")
        sequence.append(f"{key_code}:1")
        sequence.append(f"{key_code}:0")
        for mod in reversed(modifiers):
            mod_code = self._ydotool_modifier_code(mod)
            if mod_code is not None:
                sequence.append(f"{mod_code}:0")
        self._run_command([self.ydotool_path, "key", *sequence])

    def _run_wtype_combo(self, combo):
        key_data = self._parse_key_combo(combo)
        if not key_data:
            return 1
        key, modifiers = key_data
        args = [self.wtype_path]
        for mod in modifiers:
            args.extend(["-M", mod])
        args.append(key)
        for mod in reversed(modifiers):
            args.extend(["-m", mod])
        return self._run_command(args)

    def _ydotool_modifier_code(self, modifier):
        return {
            "ctrl": 29,
            "shift": 42,
            "alt": 56,
            "super": 125,
        }.get(modifier)

    def _ydotool_keycode_for_key(self, key):
        if len(key) == 1 and "a" <= key <= "z":
            letter_codes = {
                "a": 30,
                "b": 48,
                "c": 46,
                "d": 32,
                "e": 18,
                "f": 33,
                "g": 34,
                "h": 35,
                "i": 23,
                "j": 36,
                "k": 37,
                "l": 38,
                "m": 50,
                "n": 49,
                "o": 24,
                "p": 25,
                "q": 16,
                "r": 19,
                "s": 31,
                "t": 20,
                "u": 22,
                "v": 47,
                "w": 17,
                "x": 45,
                "y": 21,
                "z": 44,
            }
            return letter_codes.get(key)
        if len(key) == 1 and "0" <= key <= "9":
            digit_codes = {
                "1": 2,
                "2": 3,
                "3": 4,
                "4": 5,
                "5": 6,
                "6": 7,
                "7": 8,
                "8": 9,
                "9": 10,
                "0": 11,
            }
            return digit_codes.get(key)
        named = {
            "enter": 28,
            "tab": 15,
            "space": 57,
            "esc": 1,
            "escape": 1,
            "backspace": 14,
            "delete": 111,
            "insert": 110,
            "home": 102,
            "end": 107,
            "pageup": 104,
            "pagedown": 109,
            "up": 103,
            "down": 108,
            "left": 105,
            "right": 106,
        }
        if key.startswith("f") and key[1:].isdigit():
            fn = int(key[1:])
            if 1 <= fn <= 12:
                return 58 + (fn - 1)
        return named.get(key)

    def _run_command(self, command):
        if isinstance(command, str):
            args = shlex.split(command)
        else:
            args = command
        if not args:
            return 1
        result = subprocess.run(args, check=False)
        return result.returncode

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
        if self.entry:
            self.entry.set_text(trimmed)
        if self.history_box:
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

    def _toggle_autostart(self, checkbox):
        enabled = checkbox.get_active()
        self.config["autostart"] = enabled
        self._save_config()
        self._set_autostart_enabled(enabled)

    def _set_autostart_enabled(self, enabled):
        if enabled:
            os.makedirs(AUTOSTART_DIR, exist_ok=True)
            with open(AUTOSTART_PATH, "w", encoding="utf-8") as handle:
                handle.write(self._autostart_desktop_entry())
        else:
            try:
                os.remove(AUTOSTART_PATH)
            except FileNotFoundError:
                pass

    def _autostart_desktop_entry(self):
        script_path = os.path.realpath(__file__)
        socket_path = os.environ.get("YDOTOOL_SOCKET")
        if not socket_path and os.path.exists("/run/ydotoold/socket"):
            socket_path = "/run/ydotoold/socket"
        if socket_path:
            exec_cmd = (
                f"env YDOTOOL_SOCKET={shlex.quote(socket_path)} "
                f"python3 {shlex.quote(script_path)} --hidden %u"
            )
        else:
            exec_cmd = f"python3 {shlex.quote(script_path)} --hidden %u"
        return "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                f"Name={APP_NAME}",
                "Comment=Clipboard macros and history",
                f"Exec={exec_cmd}",
                "Terminal=false",
                "X-GNOME-Autostart-enabled=true",
                "",
            ]
        )


def main():
    app = MacruntuApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
