# Photo Grid

A native GNOME app to create print-ready photo grids and contact sheets, powered by ImageMagick.

Built with GTK 4 and libadwaita for a clean, modern Linux-native experience.

## Features

- **Paper sizes** — 4×6, 5×7, A5, A4, A3, Letter, Legal, and square formats
- **Grid layouts** — Full page, 2-up, 2×2, 3×3, 4×4, 5×5, and contact sheet
- **Orientation** — Portrait or landscape
- **DPI control** — 150 (draft), 300 (print), 600 (high quality)
- **Image sizing** — Fit (preserve aspect ratio) or fill (crop to fit)
- **Styling** — Configurable border width/colour, spacing, page margin, and background colour
- **Multi-page** — Automatically splits images across pages when they exceed the grid
- **PDF export** — Combine all pages into a single PDF document
- **Preview** — Preview all pages at screen resolution before saving, with page navigation
- **Thumbnails** — See image thumbnails in the file list

## Dependencies

### Runtime

| Package | Ubuntu / Debian | Fedora | Arch |
|---|---|---|---|
| PyGObject | `python3-gi` | `python3-gobject` | `python-gobject` |
| GTK 4 | `gir1.2-gtk-4.0` | `gtk4` | `gtk4` |
| libadwaita | `gir1.2-adw-1` | `libadwaita` | `libadwaita` |
| ImageMagick | `imagemagick` | `imagemagick` | `imagemagick` |

### Build

| Package | Ubuntu / Debian | Fedora | Arch |
|---|---|---|---|
| Meson | `meson` | `meson` | `meson` |
| Ninja | `ninja-build` | `ninja-build` | `ninja` |

## Install

```bash
# Install dependencies (Arch example)
sudo pacman -S python-gobject gtk4 libadwaita imagemagick meson ninja

# Build and install to ~/.local
meson setup builddir --prefix=~/.local
ninja -C builddir install

# The app appears in your GNOME app launcher, or run from terminal:
photo-grid
```

## Uninstall

```bash
ninja -C builddir uninstall
```

## Development

To run directly from source without installing:

```bash
python3 src/photo_grid.py
```

After making changes, rebuild and reinstall:

```bash
ninja -C builddir install
```

## Project Structure

```
photo_grid/
├── meson.build                          # Top-level build definition
├── README.md
├── data/
│   ├── meson.build                      # Installs desktop entry + metainfo
│   ├── io.github.photogrid.desktop.in   # Desktop launcher entry
│   └── io.github.photogrid.metainfo.xml # AppStream metadata
└── src/
    ├── meson.build                      # Installs launcher + app module
    ├── photo-grid.in                    # Launcher script template
    └── photo_grid.py                    # Application source
```

## How It Works

Photo Grid uses a two-step ImageMagick pipeline:

1. `magick montage` — arranges images into a grid with borders and spacing
2. `magick` — centres the grid onto a paper-sized canvas at the target DPI

For multi-page output, images are chunked according to the grid layout (e.g. 5 images in a 2×2 grid produces 2 pages). PDF export renders each page as a temporary PNG and combines them with ImageMagick.

## License

GPL-3.0-or-later
