from __future__ import annotations

import queue
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import darkdetect
import sv_ttk
from tkinterdnd2 import DND_FILES, TkinterDnD

import finder
import settings as settings_store

VERSION = "1.2.0"
CLICK_GUARD_SECONDS = 0.4
POLL_MS = 80
PROGRESS_EVERY = 100
DELETE_ALL_LABEL = "Delete all"

PALETTES = {
    "dark": {
        "text": "#ffffff", "muted": "#a0a0a0", "border": "#6a6a6a", "accent": "#60cdff",
        "drop_bg": "#242424", "drop_hover": "#17384d", "warn": "#ff8a80",
    },
    "light": {
        "text": "#1a1a1a", "muted": "#5f5f5f", "border": "#9a9a9a", "accent": "#0067c0",
        "drop_bg": "#f0f4f8", "drop_hover": "#d9ecfa", "warn": "#b00020",
    },
}

BADGE_COLORS = {
    "ok": ("#2e9d4a", "#ffffff"),
    "mid": ("#f2c200", "#1a1a1a"),
    "low": ("#e8590c", "#ffffff"),
}


def score_level(score: float) -> str:
    if score >= 100:
        return "ok"
    if score >= 90:
        return "mid"
    return "low"


def system_theme() -> str:
    return "dark" if darkdetect.theme() == "Dark" else "light"


class App:
    def __init__(self, root: tk.Misc, settings_file: str | Path | None = None):
        self.root = root
        root.title("Mod Deleter")
        root.geometry("920x820")
        root.minsize(780, 700)

        self.settings_file = settings_file
        saved = settings_store.load(settings_file)

        self.sources: dict[str, finder.SourceFile] = {}
        self.checked: dict[str, bool] = {}
        self.search_root: Path | None = None
        self.active_root: Path | None = None
        self.matches: list[finder.Match] = []
        self.index = 0
        self.deleted = 0
        self.last_error = ""
        self.shown_at = 0.0

        self.searching = False
        self._cancel = threading.Event()
        self._results: queue.Queue = queue.Queue()
        self._scanned = 0
        self._poll_job: str | None = None
        self._hover = False

        self.permanent = tk.BooleanVar(value=False)
        self.threshold = tk.IntVar(value=saved["threshold"])
        self.threshold_text = tk.StringVar(value=f"{saved['threshold']}%")
        self.status = tk.StringVar(value="")
        self.root_label = tk.StringVar(value="(no folder selected)")
        self.sources_text = tk.StringVar(value="")
        self.progress_text = tk.StringVar(value="")
        self.counter = tk.StringVar(value="")
        self.match_path = tk.StringVar(value="")
        self.match_info = tk.StringVar(value="")
        self.warning = tk.StringVar(value="")
        self.delete_all_text = tk.StringVar(value=DELETE_ALL_LABEL)

        if saved["theme"] == "system":
            self.theme = system_theme()
        else:
            self.theme = saved["theme"]
        self.palette = PALETTES[self.theme]

        self._build()
        self.apply_theme(self.theme)
        self.scale.set(self.threshold.get())
        if saved["last_root"] and Path(saved["last_root"]).is_dir():
            self.set_search_root(saved["last_root"], save=False)
        self._set_review_enabled(False)
        self._set_search_ui(False)
        self._refresh_sources_text()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- window layout ----------
    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text="Mod Deleter", font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Label(header, text=f"v{VERSION}", foreground="gray").pack(side="left", padx=(8, 0), pady=(8, 0))
        self.btn_theme = ttk.Button(header, command=self.toggle_theme)
        self.btn_theme.pack(side="right")

        src = ttk.LabelFrame(outer, text="1. What to look for", padding=10)
        src.pack(fill="both", expand=True, pady=(0, 8))
        self.drop_canvas = tk.Canvas(src, height=96, highlightthickness=0, bd=0)
        self.drop_canvas.pack(fill="x")
        self.drop_canvas.bind("<Configure>", lambda _e: self._draw_drop_zone())
        self.tree = ttk.Treeview(src, columns=("use", "name", "from"), show="headings", height=5)
        self.tree.heading("use", text="Use")
        self.tree.heading("name", text="File name")
        self.tree.heading("from", text="From")
        self.tree.column("use", width=60, anchor="center", stretch=False)
        self.tree.column("name", width=300)
        self.tree.column("from", width=420)
        self.tree.pack(fill="both", expand=True, pady=(8, 8))
        self.tree.bind("<Button-1>", self._on_tree_click)
        row = ttk.Frame(src)
        row.pack(fill="x")
        ttk.Button(row, text="Add files…", command=self._pick_files).pack(side="left")
        ttk.Button(row, text="Add folder…", command=self._pick_source_folder).pack(side="left", padx=6)
        ttk.Button(row, text="Clear list", command=self.clear_sources).pack(side="left")
        ttk.Label(row, textvariable=self.sources_text, foreground="gray").pack(side="right")
        for widget in (self.drop_canvas, self.tree, src):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<DropEnter>>", self._on_drop_enter)
            widget.dnd_bind("<<DropLeave>>", self._on_drop_leave)
            widget.dnd_bind("<<Drop>>", self._on_drop)

        where = ttk.LabelFrame(outer, text="2. Where to search", padding=10)
        where.pack(fill="x", pady=(0, 8))
        row = ttk.Frame(where)
        row.pack(fill="x")
        self.btn_root = ttk.Button(row, text="Choose folder…", command=self._pick_search_root)
        self.btn_root.pack(side="left")
        ttk.Label(row, textvariable=self.root_label).pack(side="left", padx=10)
        row = ttk.Frame(where)
        row.pack(fill="x", pady=(10, 0))
        ttk.Label(row, text="Minimum name similarity:").pack(side="left")
        self.scale = ttk.Scale(row, from_=settings_store.THRESHOLD_MIN, to=settings_store.THRESHOLD_MAX,
                               orient="horizontal", length=240, command=self._on_scale)
        self.scale.pack(side="left", padx=10)
        ttk.Label(row, textvariable=self.threshold_text, width=5).pack(side="left")
        self.btn_cancel = ttk.Button(row, text="Cancel", command=self.cancel_search)
        self.btn_cancel.pack(side="right")
        self.btn_search = ttk.Button(row, text="Search", style="Accent.TButton", command=self.start_search)
        self.btn_search.pack(side="right", padx=(0, 6))
        row = ttk.Frame(where)
        row.pack(fill="x", pady=(10, 0))
        self.progress = ttk.Progressbar(row, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True)
        ttk.Label(row, textvariable=self.progress_text, width=30, anchor="e").pack(side="left", padx=(10, 0))

        rev = ttk.LabelFrame(outer, text="3. Matches", padding=10)
        rev.pack(fill="x", pady=(0, 8))
        ttk.Label(rev, textvariable=self.counter, foreground="gray").pack(anchor="w")
        ttk.Label(rev, textvariable=self.match_path, wraplength=840,
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(2, 4))
        info = ttk.Frame(rev)
        info.pack(fill="x")
        self.badge = tk.Label(info, font=("Segoe UI", 10, "bold"), padx=6, pady=1)
        self.info_label = ttk.Label(info, textvariable=self.match_info)
        self.info_label.pack(side="left")
        self.warning_label = ttk.Label(rev, textvariable=self.warning, wraplength=840, justify="left")
        self.warning_label.pack(anchor="w", pady=(4, 0))
        row = ttk.Frame(rev)
        row.pack(fill="x", pady=(10, 0))
        self.btn_delete = ttk.Button(row, text="Delete", style="Accent.TButton", command=self._on_delete_click)
        self.btn_skip = ttk.Button(row, text="Skip", command=self._on_skip_click)
        self.btn_reveal = ttk.Button(row, text="Show in Explorer", command=self.reveal_current)
        self.btn_stop = ttk.Button(row, text="Finish", command=self.finish)
        self.btn_delete_all = ttk.Button(row, textvariable=self.delete_all_text, command=self.delete_all)
        for b in (self.btn_delete, self.btn_skip, self.btn_reveal, self.btn_stop, self.btn_delete_all):
            b.pack(side="left", padx=(0, 6))
        ttk.Checkbutton(row, text="Delete permanently (skip Recycle Bin)", variable=self.permanent).pack(side="right")

        ttk.Label(outer, textvariable=self.status, foreground="gray").pack(anchor="w")

    # ---------- theme ----------
    def apply_theme(self, name: str) -> None:
        self.theme = name
        self.palette = PALETTES[name]
        sv_ttk.set_theme(name, self.root)
        self.btn_theme.configure(text="Theme: light" if name == "dark" else "Theme: dark")
        self.warning_label.configure(foreground=self.palette["warn"])
        self._draw_drop_zone()

    def toggle_theme(self) -> None:
        self.apply_theme("light" if self.theme == "dark" else "dark")
        self._save_settings()

    # ---------- drop zone ----------
    def _draw_drop_zone(self) -> None:
        c = self.drop_canvas
        w, h = max(c.winfo_width(), 2), max(c.winfo_height(), 2)
        p = self.palette
        c.delete("all")
        c.configure(bg=p["drop_hover"] if self._hover else p["drop_bg"])
        c.create_rectangle(4, 4, w - 4, h - 4, outline=p["accent"] if self._hover else p["border"],
                           dash=(6, 4), width=2)
        title = "Drop here" if self._hover else "Drag folders or files here"
        c.create_text(w / 2, h / 2 - 10, text=title, fill=p["text"], font=("Segoe UI", 13, "bold"))
        c.create_text(w / 2, h / 2 + 16, text="their file names will be used as search patterns",
                      fill=p["muted"], font=("Segoe UI", 10))

    def _on_drop_enter(self, event):
        self._hover = True
        self._draw_drop_zone()
        return event.action

    def _on_drop_leave(self, event):
        self._hover = False
        self._draw_drop_zone()
        return event.action

    def _on_drop(self, event):
        self._hover = False
        self._draw_drop_zone()
        self.add_paths(self.root.tk.splitlist(event.data))
        return event.action

    # ---------- source list ----------
    def _pick_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Choose files")
        if paths:
            self.add_paths(paths)

    def _pick_source_folder(self) -> None:
        path = filedialog.askdirectory(title="Choose a folder with reference files")
        if path:
            self.add_paths([path])

    def add_paths(self, paths) -> None:
        for source in finder.collect_sources(paths):
            key = finder._key(source.path)
            if key not in self.sources:
                self.sources[key] = source
                self.checked[key] = True
        self._refresh_tree()
        self.status.set(f"{len(self.sources)} file names on the list.")

    def clear_sources(self) -> None:
        self.sources.clear()
        self.checked.clear()
        self._refresh_tree()

    def _refresh_sources_text(self) -> None:
        total = len(self.sources)
        used = sum(1 for k in self.sources if self.checked.get(k))
        self.sources_text.set(f"Selected: {used} of {total}" if total else "List is empty")

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        ordered = sorted(self.sources.items(), key=lambda kv: kv[1].name.casefold())
        for key, source in ordered:
            mark = "☑" if self.checked[key] else "☐"
            self.tree.insert("", "end", iid=key, values=(mark, source.name, str(source.path.parent)))
        self._refresh_sources_text()

    def _on_tree_click(self, event) -> None:
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#1":
            return
        key = self.tree.identify_row(event.y)
        if key:
            self.checked[key] = not self.checked[key]
            self.tree.set(key, "use", "☑" if self.checked[key] else "☐")
            self._refresh_sources_text()

    # ---------- folder choice and search ----------
    def _on_scale(self, value) -> None:
        rounded = round(float(value))
        self.threshold.set(rounded)
        self.threshold_text.set(f"{rounded}%")

    def _pick_search_root(self) -> None:
        path = filedialog.askdirectory(title="Choose a folder to search")
        if path:
            self.set_search_root(path)

    def set_search_root(self, path, save: bool = True) -> None:
        self.search_root = Path(path)
        self.root_label.set(str(self.search_root))
        if save:
            self._save_settings()

    def _set_search_ui(self, searching: bool) -> None:
        self.btn_search.configure(state="disabled" if searching else "normal")
        self.btn_root.configure(state="disabled" if searching else "normal")
        self.btn_cancel.configure(state="normal" if searching else "disabled")
        if searching:
            self.progress.start(12)
        else:
            self.progress.stop()

    def start_search(self) -> None:
        if self.searching:
            return
        chosen = [s for k, s in self.sources.items() if self.checked.get(k)]
        if not chosen:
            messagebox.showinfo("Mod Deleter", "The “What to look for” list is empty or nothing is selected.")
            return
        if self.search_root is None or not self.search_root.is_dir():
            messagebox.showinfo("Mod Deleter", "Choose a folder to search first.")
            return
        self.active_root = self.search_root
        threshold = float(self.threshold.get())
        self.matches = []
        self.index = 0
        self.deleted = 0
        self.last_error = ""
        self._clear_review()
        self._save_settings()

        self._cancel.clear()
        self._results = queue.Queue()
        self._scanned = 0
        self.searching = True
        self._set_search_ui(True)
        self.progress_text.set("Scanned 0 files…")
        self.status.set("Searching…")

        results, cancel, root_dir = self._results, self._cancel, self.active_root

        def work() -> None:
            try:
                found = finder.find_matches(
                    chosen, root_dir, threshold,
                    on_progress=lambda n: results.put(("progress", n)),
                    should_cancel=cancel.is_set,
                    progress_every=PROGRESS_EVERY)
            except finder.SearchCancelled:
                results.put(("cancelled", None))
            except Exception as exc:
                results.put(("error", exc))
            else:
                results.put(("done", found))

        threading.Thread(target=work, daemon=True).start()
        self._poll_job = self.root.after(POLL_MS, self._poll_search)

    def cancel_search(self) -> None:
        if self.searching:
            self._cancel.set()
            self.status.set("Cancelling…")

    def _drain_results(self) -> bool:
        """Handle queued worker messages; True once the search has ended."""
        while True:
            try:
                kind, payload = self._results.get_nowait()
            except queue.Empty:
                return not self.searching
            if kind == "progress":
                self._scanned = payload
                self.progress_text.set(f"Scanned {payload} files…")
                continue
            self._end_search(kind, payload)
            return True

    def _poll_search(self) -> None:
        self._poll_job = None
        if not self._drain_results():
            self._poll_job = self.root.after(POLL_MS, self._poll_search)

    def wait_for_search(self, timeout: float = 15.0) -> None:
        deadline = time.monotonic() + timeout
        while self.searching:
            if time.monotonic() > deadline:
                raise TimeoutError("search is taking too long")
            self._drain_results()
            self.root.update()
            time.sleep(0.005)

    def _end_search(self, kind: str, payload) -> None:
        self.searching = False
        self._set_search_ui(False)
        if self._poll_job is not None:
            self.root.after_cancel(self._poll_job)
            self._poll_job = None
        if kind == "cancelled":
            self.progress_text.set("")
            self.status.set("Search cancelled.")
        elif kind == "error":
            self.progress_text.set("")
            self.status.set(f"Search error: {payload}")
        else:
            self.matches = payload
            self.progress_text.set(f"Scanned {self._scanned} files")
            if not self.matches:
                self.status.set("No matching files found.")
                self._clear_review()
            else:
                self.status.set(f"Matches found: {len(self.matches)}.")
                self._show_current()

    # ---------- match review ----------
    def _set_review_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for b in (self.btn_delete, self.btn_skip, self.btn_reveal, self.btn_stop, self.btn_delete_all):
            b.configure(state=state)

    def _clear_review(self) -> None:
        self.counter.set("")
        self.match_path.set("")
        self.match_info.set("")
        self.warning.set("")
        self.badge.pack_forget()
        self.delete_all_text.set(DELETE_ALL_LABEL)
        self._set_review_enabled(False)

    def _show_badge(self, score: float) -> None:
        bg, fg = BADGE_COLORS[score_level(score)]
        self.badge.configure(text=f"{score:.0f}%", bg=bg, fg=fg)
        self.badge.pack(side="left", padx=(0, 8), before=self.info_label)

    def _show_current(self) -> None:
        while self.index < len(self.matches):
            match = self.matches[self.index]
            if not match.path.is_file():
                self.status.set(f"Skipped (file no longer exists): {match.path.name}")
                self.index += 1
                continue
            self.counter.set(f"Match {self.index + 1} of {len(self.matches)}")
            self.match_path.set(str(match.path))
            self.match_info.set(f"looking for: {match.source_name}")
            self._show_badge(match.score)
            notes = []
            if match.is_source:
                notes.append("WARNING: this is the reference file the name was taken from.")
            try:
                emptied = finder.folders_emptied_by(match.path, self.active_root)
            except OSError:
                emptied = []
                notes.append("(cannot inspect the folder)")
            if emptied:
                names = ", ".join(str(p) for p in emptied)
                notes.append(f"Empty folders will also be deleted afterwards: {names}")
            self.warning.set("\n".join(notes))
            self.delete_all_text.set(f"{DELETE_ALL_LABEL} ({len(self.matches) - self.index})")
            self.shown_at = time.monotonic()
            self._set_review_enabled(True)
            return
        skipped = self.status.get()
        self.finish()
        if skipped.startswith("Skipped"):
            self.status.set(f"{self.status.get()}  ({skipped})")

    def _click_too_soon(self) -> bool:
        return time.monotonic() - self.shown_at < CLICK_GUARD_SECONDS

    def _on_delete_click(self) -> None:
        if not self._click_too_soon():
            self.delete_current()

    def _on_skip_click(self) -> None:
        if not self._click_too_soon():
            self.skip_current()

    def reveal_current(self) -> None:
        if not self.matches or self.index >= len(self.matches):
            return
        path = self.matches[self.index].path
        try:
            if path.is_file():
                subprocess.Popen(["explorer", "/select,", str(path)])
            else:
                subprocess.Popen(["explorer", str(path.parent)])
        except OSError as exc:
            self.status.set(f"Cannot open Explorer: {exc}")

    def delete_current(self) -> None:
        if not self.matches or self.index >= len(self.matches):
            return
        match = self.matches[self.index]
        permanent = self.permanent.get()
        if permanent and not messagebox.askyesno(
                "Delete permanently", f"Delete permanently, bypassing the Recycle Bin?\n\n{match.path}"):
            return
        if match.is_source and not messagebox.askyesno(
                "Reference file",
                "This is the reference file the name was taken from. Delete it anyway?"):
            return
        if not permanent and not finder.drive_has_recycle_bin(match.path):
            if not messagebox.askyesno(
                    "No Recycle Bin",
                    f"This drive has no Recycle Bin — the file will be deleted permanently.\nContinue?\n\n{match.path}"):
                return
        self._set_review_enabled(False)
        self.root.update_idletasks()
        try:
            result = finder.delete_match(match.path, self.active_root, permanent=permanent)
        except OSError as exc:
            self.last_error = f"Could not delete {match.path.name}: {exc}"
            self.status.set(self.last_error)
            self.index += 1
            self._show_current()
            return
        self.deleted += 1
        extra = f" (+ {len(result.removed_folders)} empty folders)" if result.removed_folders else ""
        self.status.set(f"Deleted: {match.path.name}{extra}")
        self.index += 1
        self._show_current()

    def delete_all(self) -> None:
        if not self.matches or self.index >= len(self.matches):
            return
        pending = [m for m in self.matches[self.index:] if m.path.is_file()]
        targets = [m for m in pending if not m.is_source]
        skipped_sources = len(pending) - len(targets)
        if not targets:
            self.status.set("Nothing to delete: only reference files remain."
                            if skipped_sources else "Nothing to delete: the files no longer exist.")
            return
        permanent = self.permanent.get()
        lines = [f"Files to delete: {len(targets)}"]
        if permanent:
            lines.append("Method: PERMANENTLY, cannot be undone.")
        else:
            lines.append("Method: files will go to the Recycle Bin.")
        below = [m for m in targets if m.score < 100]
        if below:
            lowest = min(m.score for m in below)
            lines.append(f"Of these, with similarity below 100%: {len(below)} (lowest: {lowest:.0f}%).")
        lines.append("Folders left empty after deletion will also be deleted.")
        if skipped_sources:
            lines.append(f"Reference files will be skipped: {skipped_sources}.")
        if not permanent:
            no_bin = [m for m in targets if not finder.drive_has_recycle_bin(m.path)]
            if no_bin:
                lines.append(f"WARNING: {len(no_bin)} files are on a drive without a Recycle Bin and will be deleted permanently.")
        question = "Delete all remaining matches?\n\n" + "\n".join(lines)
        if not messagebox.askyesno("Delete all", question, icon="warning", default="no"):
            return

        self._set_review_enabled(False)
        done = folders = errors = 0
        for number, match in enumerate(targets, 1):
            self.status.set(f"Deleting {number} of {len(targets)}…")
            self.root.update_idletasks()
            try:
                result = finder.delete_match(match.path, self.active_root, permanent=permanent)
            except OSError as exc:
                errors += 1
                self.last_error = f"Could not delete {match.path.name}: {exc}"
                continue
            done += 1
            folders += len(result.removed_folders)
        self.deleted += done
        summary = f"Files deleted: {done}"
        if folders:
            summary += f" (+ {folders} empty folders)"
        if errors:
            summary += f". Errors: {errors} (last: {self.last_error})"
        if skipped_sources:
            summary += f". Reference files skipped: {skipped_sources}"
        self.matches = []
        self._clear_review()
        self.status.set(summary + ".")

    def skip_current(self) -> None:
        if not self.matches or self.index >= len(self.matches):
            return
        self.index += 1
        self._show_current()

    def finish(self) -> None:
        summary = f"Done. Files deleted: {self.deleted}."
        if self.last_error:
            summary += f"  Last error: {self.last_error}"
        self.status.set(summary)
        self.matches = []
        self._clear_review()

    # ---------- settings and closing ----------
    def _save_settings(self) -> None:
        settings_store.save({
            "theme": self.theme,
            "last_root": str(self.search_root) if self.search_root else "",
            "threshold": int(self.threshold.get()),
        }, self.settings_file)

    def _on_close(self) -> None:
        self._cancel.set()
        self._save_settings()
        self.root.destroy()


def main() -> None:
    root = TkinterDnD.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
