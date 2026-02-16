#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later

"""Photo Grid - create print-ready photo grids using ImageMagick montage."""

import math, subprocess, shutil, tempfile
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk, Gio, GLib  # noqa: E402

APP_ID = "io.github.photogrid"

# Paper sizes in inches (width x height, portrait orientation)
PAPERS = {
    "4 x 6 in": (4, 6),
    "5 x 7 in": (5, 7),
    "A5": (5.83, 8.27),
    "A4": (8.27, 11.69),
    "A3": (11.69, 16.54),
    "Letter": (8.5, 11),
    "Legal": (8.5, 14),
    "Square 8 in": (8, 8),
    "Square 12 in": (12, 12),
}
PAPER_NAMES = list(PAPERS.keys())

# Layout presets: label -> (columns, rows) - (0,0) = auto
LAYOUTS = {
    "Full Page (1)": (1, 1),
    "2 per page": (1, 2),
    "2 x 2 (4)": (2, 2),
    "3 x 3 (9)": (3, 3),
    "4 x 4 (16)": (4, 4),
    "5 x 5 (25)": (5, 5),
    "Contact Sheet": (0, 0),
}
LAYOUT_NAMES = list(LAYOUTS.keys())


class PhotoGridWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(
            **kwargs, default_width=900, default_height=750, title="Photo Grid"
        )
        self.images: list[str] = []
        self._preview_win = None

        # -- header bar --
        header = Adw.HeaderBar()
        open_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Add images")
        open_btn.connect("clicked", self._on_add_images)
        clear_btn = Gtk.Button(
            icon_name="edit-clear-all-symbolic", tooltip_text="Clear images"
        )
        clear_btn.connect("clicked", self._on_clear)
        header.pack_start(open_btn)
        header.pack_start(clear_btn)

        # -- images area --
        self.status = Adw.StatusPage(
            title="No Images",
            description="Click + to add images",
        )

        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.listbox.add_css_class("boxed-list")

        img_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        img_scroll.set_min_content_height(120)
        img_scroll.set_max_content_height(220)
        img_scroll.set_propagate_natural_height(True)
        img_scroll.set_child(self.listbox)

        self.img_stack = Gtk.Stack()
        self.img_stack.add_named(self.status, "empty")
        self.img_stack.add_named(img_scroll, "list")
        self.img_stack.set_visible_child_name("empty")

        # -- page setup --
        page_group = Adw.PreferencesGroup(title="Page Setup")

        paper_model = Gtk.StringList.new(PAPER_NAMES)
        self.paper_row = Adw.ComboRow(title="Paper Size", model=paper_model)
        self.paper_row.set_selected(PAPER_NAMES.index("A4"))
        page_group.add(self.paper_row)

        orient_model = Gtk.StringList.new(["Portrait", "Landscape"])
        self.orient_row = Adw.ComboRow(title="Orientation", model=orient_model)
        self.orient_row.set_selected(0)
        page_group.add(self.orient_row)

        dpi_model = Gtk.StringList.new(["150 (draft)", "300 (print)", "600 (high)"])
        self.dpi_row = Adw.ComboRow(title="DPI", model=dpi_model)
        self.dpi_row.set_selected(1)
        page_group.add(self.dpi_row)

        self.pdf_row = Adw.SwitchRow(
            title="Save as PDF", subtitle="Combine all pages into one PDF"
        )
        page_group.add(self.pdf_row)

        # -- layout --
        layout_group = Adw.PreferencesGroup(title="Layout")

        layout_model = Gtk.StringList.new(LAYOUT_NAMES)
        self.layout_row = Adw.ComboRow(title="Grid Layout", model=layout_model)
        self.layout_row.set_selected(LAYOUT_NAMES.index("2 x 2 (4)"))
        layout_group.add(self.layout_row)

        fill_model = Gtk.StringList.new(["Fit (keep aspect)", "Fill (crop to fit)"])
        self.fill_row = Adw.ComboRow(title="Image Sizing", model=fill_model)
        self.fill_row.set_selected(0)
        layout_group.add(self.fill_row)

        # column 1: page setup + layout
        col1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, hexpand=True)
        col1.append(page_group)
        col1.append(layout_group)

        # -- style --
        style_group = Adw.PreferencesGroup(title="Style")

        self.border_row = Adw.SpinRow.new_with_range(0, 50, 1)
        self.border_row.set_title("Border Width (px)")
        self.border_row.set_value(2)
        style_group.add(self.border_row)

        self.spacing_row = Adw.SpinRow.new_with_range(0, 50, 1)
        self.spacing_row.set_title("Spacing (px)")
        self.spacing_row.set_value(4)
        style_group.add(self.spacing_row)

        self.margin_row = Adw.SpinRow.new_with_range(0, 100, 5)
        self.margin_row.set_title("Page Margin (px)")
        self.margin_row.set_value(20)
        style_group.add(self.margin_row)

        self.bg_row = Adw.EntryRow(title="Background Colour")
        self.bg_row.set_text("white")
        style_group.add(self.bg_row)

        self.border_color_row = Adw.EntryRow(title="Border Colour")
        self.border_color_row.set_text("black")
        style_group.add(self.border_color_row)

        # column 2: style
        col2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, hexpand=True)
        col2.append(style_group)

        # -- settings 2-col row --
        settings_cols = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        settings_cols.set_homogeneous(True)
        settings_cols.append(col1)
        settings_cols.append(col2)

        # -- action buttons (stacked) --
        btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        btn_box.set_halign(Gtk.Align.CENTER)
        btn_box.set_margin_top(4)
        btn_box.set_margin_bottom(8)

        preview_btn = Gtk.Button(label="Preview")
        preview_btn.add_css_class("pill")
        preview_btn.set_size_request(200, -1)
        preview_btn.connect("clicked", self._on_preview)
        btn_box.append(preview_btn)

        gen_btn = Gtk.Button(label="Create Grid")
        gen_btn.add_css_class("suggested-action")
        gen_btn.add_css_class("pill")
        gen_btn.set_size_request(200, -1)
        gen_btn.connect("clicked", self._on_generate)
        btn_box.append(gen_btn)

        # -- assemble --
        scroll = Gtk.ScrolledWindow(vexpand=True)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        inner.set_margin_start(12)
        inner.set_margin_end(12)
        inner.set_margin_top(6)
        inner.set_margin_bottom(6)
        inner.append(self.img_stack)
        inner.append(settings_cols)
        inner.append(btn_box)
        scroll.set_child(inner)

        # -- toast overlay --
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(scroll)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(self.toast_overlay)
        self.set_content(toolbar)

    # -- file handling -------------------------------------------------------

    def _on_add_images(self, _btn):
        dlg = Gtk.FileDialog(title="Select Images")
        f = Gtk.FileFilter()
        f.set_name("Images")
        for mime in (
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/tiff",
            "image/bmp",
        ):
            f.add_mime_type(mime)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(f)
        dlg.set_filters(filters)
        dlg.set_default_filter(f)
        dlg.open_multiple(self, None, self._on_files_ready)

    def _on_files_ready(self, dlg, result):
        try:
            files = dlg.open_multiple_finish(result)
        except GLib.Error:
            return
        for i in range(files.get_n_items()):
            path = files.get_item(i).get_path()
            if path and path not in self.images:
                self.images.append(path)
                self._add_image_row(path)
        self._update_visibility()

    def _add_image_row(self, path):
        row = Adw.ActionRow(title=Path(path).name, subtitle=path)
        # thumbnail
        thumb = Gtk.Image.new_from_file(path)
        thumb.set_pixel_size(48)
        row.add_prefix(thumb)
        # remove button
        remove_btn = Gtk.Button(
            icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER
        )
        remove_btn.add_css_class("flat")
        remove_btn.connect("clicked", self._on_remove_image, path, row)
        row.add_suffix(remove_btn)
        self.listbox.append(row)

    def _on_remove_image(self, _btn, path, row):
        self.images.remove(path)
        self.listbox.remove(row)
        self._update_visibility()

    def _on_clear(self, _btn):
        self.images.clear()
        while row := self.listbox.get_row_at_index(0):
            self.listbox.remove(row)
        self._update_visibility()

    def _update_visibility(self):
        if self.images:
            self.img_stack.set_visible_child_name("list")
        else:
            self.img_stack.set_visible_child_name("empty")

    # -- grid generation -----------------------------------------------------

    def _gather_settings(self, dpi_override=None):
        """Read all UI values and compute montage parameters."""
        paper_name = PAPER_NAMES[self.paper_row.get_selected()]
        pw, ph = PAPERS[paper_name]
        if self.orient_row.get_selected() == 1:  # landscape
            pw, ph = ph, pw

        dpi = dpi_override or [150, 300, 600][self.dpi_row.get_selected()]

        layout_name = LAYOUT_NAMES[self.layout_row.get_selected()]
        cols, rows = LAYOUTS[layout_name]

        border = int(self.border_row.get_value())
        spacing = int(self.spacing_row.get_value())
        margin = int(self.margin_row.get_value())
        bg = self.bg_row.get_text().strip() or "white"
        border_color = self.border_color_row.get_text().strip() or "gray"
        fill = self.fill_row.get_selected() == 1
        pdf = self.pdf_row.get_active()

        # canvas size in pixels
        canvas_w = int(pw * dpi)
        canvas_h = int(ph * dpi)

        # cell size derived from paper, margins, borders
        if cols > 0 and rows > 0:
            cell_w = (canvas_w - 2 * margin - cols * 2 * (border + spacing)) // cols
            cell_h = (canvas_h - 2 * margin - rows * 2 * (border + spacing)) // rows
            cell_w = max(cell_w, 64)
            cell_h = max(cell_h, 64)
            tile = f"{cols}x{rows}"
        else:
            # contact sheet - let montage decide tile, use reasonable cell
            cell_w = (canvas_w - 2 * margin) // 6
            cell_h = cell_w
            tile = ""

        return {
            "tile": tile,
            "cell_w": cell_w,
            "cell_h": cell_h,
            "border": border,
            "spacing": spacing,
            "margin": margin,
            "bg": bg,
            "border_color": border_color,
            "canvas_w": canvas_w,
            "canvas_h": canvas_h,
            "dpi": dpi,
            "fill": fill,
            "pdf": pdf,
        }

    def _check_ready(self):
        if not self.images:
            self.toast_overlay.add_toast(Adw.Toast(title="Add some images first"))
            return False
        if not shutil.which("magick"):
            self.toast_overlay.add_toast(
                Adw.Toast(title="ImageMagick not found - install it first")
            )
            return False
        return True

    def _chunk_images(self, s):
        """Split images into per-page chunks based on grid layout."""
        if s["tile"]:
            cols, rows = (int(x) for x in s["tile"].split("x"))
            per_page = cols * rows
            return [
                self.images[i : i + per_page]
                for i in range(0, len(self.images), per_page)
            ]
        return [self.images]  # contact sheet = one page

    def _run_montage(self, imgs, s, dest):
        """Run montage for one page \u2192 center on canvas \u2192 save."""
        cmd1 = ["magick", "montage"] + imgs
        if s["fill"]:
            cmd1 += [
                "-resize",
                f"{s['cell_w']}x{s['cell_h']}^",
                "-gravity",
                "center",
                "-extent",
                f"{s['cell_w']}x{s['cell_h']}",
            ]
            cmd1 += ["-geometry", f"+{s['spacing']}+{s['spacing']}"]
        else:
            cmd1 += [
                "-geometry",
                f"{s['cell_w']}x{s['cell_h']}+{s['spacing']}+{s['spacing']}",
            ]
        if s["tile"]:
            cmd1 += ["-tile", s["tile"]]
        cmd1 += ["-border", str(s["border"])]
        cmd1 += ["-bordercolor", s["border_color"]]
        cmd1 += ["-background", s["bg"]]
        cmd1 += ["png:-"]

        cmd2 = [
            "magick",
            "-",
            "-gravity",
            "center",
            "-background",
            s["bg"],
            "-extent",
            f"{s['canvas_w']}x{s['canvas_h']}",
            "-units",
            "PixelsPerInch",
            "-density",
            str(s["dpi"]),
            dest,
        ]

        r1 = subprocess.run(cmd1, capture_output=True, check=True)
        subprocess.run(cmd2, input=r1.stdout, capture_output=True, check=True)

    def _run_all_pages(self, s, dest_pattern):
        """Generate all pages. Returns list of output file paths."""
        chunks = self._chunk_images(s)
        paths = []
        for i, chunk in enumerate(chunks):
            dest = dest_pattern.format(page=i + 1)
            self._run_montage(chunk, s, dest)
            paths.append(dest)
        return paths

    def _on_preview(self, _btn):
        if not self._check_ready():
            return
        s = self._gather_settings(dpi_override=72)
        tmpdir = tempfile.mkdtemp(prefix="photogrid_")
        pattern = str(Path(tmpdir) / "page-{page}.png")
        try:
            pages = self._run_all_pages(s, pattern)
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode("utf-8", errors="replace").strip()[:120]
            self.toast_overlay.add_toast(Adw.Toast(title=f"Error: {err}"))
            return
        self._show_preview(pages)

    def _show_preview(self, pages):
        if self._preview_win:
            self._preview_win.close()

        self._preview_pages = pages
        self._preview_idx = 0

        self._preview_win = Adw.Window(
            title="Preview",
            transient_for=self,
            default_width=700,
            default_height=500,
            modal=True,
        )
        self._preview_win.connect("close-request", self._on_preview_close)

        header = Adw.HeaderBar()
        save_btn = Gtk.Button(label="Save As")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_generate)
        header.pack_end(save_btn)

        # page navigation (only if multi-page)
        if len(pages) > 1:
            nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            self._prev_btn = Gtk.Button(icon_name="go-previous-symbolic")
            self._prev_btn.connect("clicked", self._on_preview_nav, -1)
            self._next_btn = Gtk.Button(icon_name="go-next-symbolic")
            self._next_btn.connect("clicked", self._on_preview_nav, 1)
            self._page_label = Gtk.Label(label=f"1 / {len(pages)}")
            nav_box.append(self._prev_btn)
            nav_box.append(self._page_label)
            nav_box.append(self._next_btn)
            header.set_title_widget(nav_box)
        else:
            self._prev_btn = self._next_btn = self._page_label = None

        self._preview_picture = Gtk.Picture.new_for_filename(pages[0])
        self._preview_picture.set_can_shrink(True)
        self._preview_picture.set_content_fit(Gtk.ContentFit.CONTAIN)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        scroll.set_child(self._preview_picture)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(scroll)
        self._preview_win.set_content(toolbar)
        self._preview_win.present()
        self._update_preview_nav()

    def _on_preview_nav(self, _btn, direction):
        self._preview_idx = max(
            0, min(self._preview_idx + direction, len(self._preview_pages) - 1)
        )
        self._preview_picture.set_filename(self._preview_pages[self._preview_idx])
        self._update_preview_nav()

    def _update_preview_nav(self):
        if self._page_label is None:
            return
        n = len(self._preview_pages)
        i = self._preview_idx
        self._page_label.set_label(f"{i + 1} / {n}")
        self._prev_btn.set_sensitive(i > 0)
        self._next_btn.set_sensitive(i < n - 1)

    def _on_preview_close(self, _win):
        self._preview_win = None
        self._preview_pages = []
        return False

    def _on_generate(self, _btn):
        if not self._check_ready():
            return
        s = self._gather_settings()
        name = "grid.pdf" if s["pdf"] else "grid.jpg"
        save_dlg = Gtk.FileDialog(title="Save Grid", initial_name=name)
        parent = self._preview_win or self
        save_dlg.save(parent, None, self._on_save_ready, s)

    def _on_save_ready(self, dlg, result, s):
        try:
            dest = dlg.save_finish(result).get_path()
        except GLib.Error:
            return

        chunks = self._chunk_images(s)

        try:
            if s["pdf"]:
                # PDF: render all pages as temp PNGs, combine into one PDF
                tmpdir = tempfile.mkdtemp(prefix="photogrid_pdf_")
                pattern = str(Path(tmpdir) / "page-{page}.png")
                page_files = self._run_all_pages(s, pattern)
                # ensure .pdf extension
                if not dest.lower().endswith(".pdf"):
                    dest += ".pdf"
                cmd = (
                    ["magick"]
                    + page_files
                    + ["-units", "PixelsPerInch", "-density", str(s["dpi"]), dest]
                )
                subprocess.run(cmd, capture_output=True, check=True)
                self.toast_overlay.add_toast(
                    Adw.Toast(title=f"Saved {len(page_files)}-page PDF")
                )
            elif len(chunks) == 1:
                self._run_montage(chunks[0], s, dest)
                self.toast_overlay.add_toast(
                    Adw.Toast(title=f"Saved to {Path(dest).name}")
                )
            else:
                p = Path(dest)
                stem, ext = p.stem, p.suffix or ".jpg"
                for i, chunk in enumerate(chunks, 1):
                    out = str(p.with_name(f"{stem}-{i}{ext}"))
                    self._run_montage(chunk, s, out)
                self.toast_overlay.add_toast(
                    Adw.Toast(title=f"Saved {len(chunks)} files")
                )

            if self._preview_win:
                self._preview_win.close()
                self._preview_win = None
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode("utf-8", errors="replace").strip()[:120]
            self.toast_overlay.add_toast(Adw.Toast(title=f"Error: {err}"))


# -- application ---------------------------------------------------------


class PhotoGridApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )

    def do_activate(self):
        Gtk.Window.set_default_icon_name("view-grid-symbolic")
        win = self.get_active_window()
        if not win:
            win = PhotoGridWindow(application=self)
        win.present()


def main():
    app = PhotoGridApp()
    app.run()


if __name__ == "__main__":
    main()
