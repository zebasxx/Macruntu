# Macruntu

Minimal clipboard helper for Ubuntu 24.04 GNOME (Wayland). It keeps a 5-item clipboard history, exposes macro buttons, and lives in the top-right tray.

## Requirements

Install the GTK and Ayatana AppIndicator bindings:

```bash
sudo apt install -y python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
```

For reliable clipboard updates from shortcuts on Wayland, install wl-clipboard:

```bash
sudo apt install -y wl-clipboard
```

Optional: to auto-paste a macro into the focused app, install wtype (Wayland), ydotool (Wayland), or xdotool (X11):

```bash
sudo apt install -y wtype
```

```bash
sudo apt install -y xdotool
```

```bash
sudo apt install -y ydotool
```

On GNOME Wayland, wtype may be blocked by the compositor. ydotool works but requires the ydotoold daemon and permission to access uinput (usually via a systemd service).

### ydotool setup (GNOME Wayland)

Ubuntu 24.04 ships the ydotool client but not the ydotoold daemon, so build/install it once:

```bash
sudo apt install -y git build-essential cmake pkg-config libevdev-dev libudev-dev scdoc
git clone https://github.com/ReimuNotMoe/ydotool.git
cd ydotool
mkdir build && cd build
cmake ..
make -j"$(nproc)"
sudo make install
```

Set up permissions and a systemd service:

```bash
sudo groupadd -f uinput
sudo usermod -aG uinput $USER
echo 'KERNEL=="uinput", GROUP="uinput", MODE="0660"' | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

```bash
sudo tee /etc/systemd/system/ydotoold.service >/dev/null <<'EOF'
[Unit]
Description=ydotool daemon
After=network.target

[Service]
ExecStart=/usr/local/bin/ydotoold --socket-path=/run/ydotoold/socket --socket-perm=0660
Restart=always
RestartSec=1
User=root
Group=uinput
RuntimeDirectory=ydotoold
RuntimeDirectoryMode=0755

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now ydotoold
```

Log out/in to apply the group change. Opening a new terminal is not enough; `id -nG`
must include `uinput` before ydotool can access the socket. If you want to test
without logging out, run `newgrp uinput` first.

Then verify:

```bash
id -nG
ls -l /run/ydotoold/socket
YDOTOOL_SOCKET=/run/ydotoold/socket ydotool key 29:1 47:1 47:0 29:0
```

Make the socket available to launches from GNOME shortcuts/desktop entries:

```bash
systemctl --user set-environment YDOTOOL_SOCKET=/run/ydotoold/socket
```

## Run

```bash
python3 macruntu.py
```

The first run creates a config file at `~/.config/macruntu/config.json`. Edit it to customize macro buttons.
Add `"secret": true` to a macro to keep it out of history and avoid showing it in the main textbox.
Add `"paste": true` to auto-paste a macro by typing the text directly via wtype (Wayland), ydotool (Wayland), or xdotool (X11). This avoids touching the clipboard. If no typing backend is available, it falls back to `ctrl+v` using the clipboard.
Use `"paste_keys"` to override the combo when falling back to clipboard paste (e.g. `ctrl+shift+v` for terminals), or `"paste_command"` to run a custom command.
Use `"paste_delay_ms"` to wait a bit before pasting (helps keep focus in the target app).
Use `"paste_backend"` to force a backend (`"ydotool"`, `"wtype"`, or `"xdotool"`). This is useful on GNOME Wayland where wtype may be blocked.
By default, Macruntu restores the clipboard after a clipboard-based macro paste so your previous clipboard content is preserved. You can disable this globally with `"restore_clipboard_after_macro": false` or per macro with `"restore_clipboard": false`.
Use `"restore_clipboard_delay_ms"` (global) or `"restore_delay_ms"` (per macro) to control how long it waits before restoring.

Example:

```json
{
  "label": "Terminal paste",
  "text": "ls -la",
  "paste": true,
  "paste_keys": "ctrl+shift+v",
  "paste_delay_ms": 200,
  "paste_backend": "ydotool",
  "restore_clipboard": true,
  "restore_delay_ms": 300
}
```
Past Enter Key:

```json
{
  "label": "Enter",
  "text": "",
  "paste": true,
  "paste_keys": "enter",
  "paste_backend": "ydotool",
  "paste_delay_ms": 200
}
```
Use the "Start at login" checkbox in the UI to create or remove the GNOME autostart entry. Autostart launches Macruntu hidden in the tray.

## Shortcut

Create a custom shortcut in GNOME Settings and point it to (from the repo root):

```bash
python3 "$(pwd)/macruntu.py"
```

## Desktop entry (fix Dock icon)

Copy the desktop file so GNOME can pick up the app icon:

```bash
mkdir -p ~/.local/share/applications
cp "$(pwd)/com.seb.Macruntu.desktop" ~/.local/share/applications/
update-desktop-database ~/.local/share/applications
xdg-mime default com.seb.Macruntu.desktop x-scheme-handler/macruntu
```

Launch via the app menu or:

```bash
gtk-launch com.seb.Macruntu
```

## Macro shortcuts

For GNOME custom shortcuts, use the direct command with an absolute path:

```bash
env YDOTOOL_SOCKET=/run/ydotoold/socket python3 /home/seb/Code/GitHubSeba/Macruntu/macruntu.py --macro 1
```

That triggers the first macro without opening the UI. By default, triggering a
macro copies its text to the clipboard, so there may be no visible change until
you paste manually with `Ctrl+V`. You can confirm it worked with:

```bash
wl-paste
```

To make a shortcut type/paste into the currently focused app automatically, add
`"paste": true` to that macro in `~/.config/macruntu/config.json`:

```json
{
  "label": "Username",
  "text": "sebastian.garcia",
  "paste": true,
  "paste_backend": "ydotool"
}
```

You can change `--macro 1` to any macro number.

You can also trigger macros through the desktop entry with a macro URI after
registering the desktop file:

```bash
gtk-launch com.seb.Macruntu macruntu://macro/1
```

If the URI launch does nothing, verify GNOME knows the handler:

```bash
gio mime x-scheme-handler/macruntu
```
