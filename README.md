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

## Run

```bash
python3 macruntu.py
```

The first run creates a config file at `~/.config/macruntu/config.json`. Edit it to customize macro buttons.
Add `"secret": true` to a macro to keep it out of history and avoid showing it in the main textbox.

## Shortcut

Create a custom shortcut in GNOME Settings and point it to:

```bash
python3 /home/seb/Code/GitHub/Macruntu/macruntu.py
```

## Desktop entry (fix Dock icon)

Copy the desktop file so GNOME can pick up the app icon:

```bash
mkdir -p ~/.local/share/applications
cp /home/seb/Code/GitHub/Macruntu/com.seb.Macruntu.desktop ~/.local/share/applications/
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
