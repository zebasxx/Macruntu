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

Log out/in to apply the group change, then verify:

```bash
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
Add `"paste": true` to auto-paste a macro after copying it. By default it uses `ctrl+v` via wtype (Wayland) or xdotool (X11).
Use `"paste_keys"` to override the combo (e.g. `ctrl+shift+v` for terminals), or `"paste_command"` to run a custom command.
Use `"paste_delay_ms"` to wait a bit before pasting (helps keep focus in the target app).
Use `"paste_backend"` to force a backend (`"ydotool"`, `"wtype"`, or `"xdotool"`). This is useful on GNOME Wayland where wtype may be blocked.

Example:

```json
{
  "label": "Terminal paste",
  "text": "ls -la",
  "paste": true,
  "paste_keys": "ctrl+shift+v",
  "paste_delay_ms": 200,
  "paste_backend": "ydotool"
}
```

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
```

Launch via the app menu or:

```bash
gtk-launch com.seb.Macruntu
```

## Macro shortcuts

You can trigger macros without opening the UI by launching with a macro URI:

```bash
gtk-launch com.seb.Macruntu macruntu://macro/1
```

Create a GNOME custom shortcut with that command to bind `Ctrl+1` to the first macro.
