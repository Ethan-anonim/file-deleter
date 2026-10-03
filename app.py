from __future__ import annotations

import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD

import finder

CLICK_GUARD_SECONDS = 0.4


class App:
    def __init__(self, root: tk.Misc):
        self.root = root
        root.title("Mod Deleter")
        root.geometry("860x700")

        self.sources: dict[str, finder.SourceFile] = {}
        self.checked: dict[str, bool] = {}
        self.search_root: Path | None = None
        self.active_root: Path | None = None
        self.matches: list[finder.Match] = []
        self.index = 0
        self.deleted = 0
        self.last_error = ""
        self.shown_at = 0.0

        self.permanent = tk.BooleanVar(value=False)
        self.threshold = tk.IntVar(value=85)
        self.status = tk.StringVar(value="")
        self.root_label = tk.StringVar(value="(nie wybrano folderu)")
        self.counter = tk.StringVar(value="")
        self.match_path = tk.StringVar(value="")
        self.match_info = tk.StringVar(value="")
        self.warning = tk.StringVar(value="")

        self._build()
        self._set_review_enabled(False)

    # ---------- budowa okna ----------
    def _build(self) -> None:
        pad = {"padx": 10, "pady": 6}

        src = ttk.LabelFrame(self.root, text="1. Czego szukam (przeciągnij tu foldery lub pliki)")
        src.pack(fill="both", expand=True, **pad)
        self.tree = ttk.Treeview(src, columns=("use", "name", "from"), show="headings", height=8)
        self.tree.heading("use", text="Szukaj")
        self.tree.heading("name", text="Nazwa pliku")
        self.tree.heading("from", text="Pochodzi z")
        self.tree.column("use", width=60, anchor="center", stretch=False)
        self.tree.column("name", width=300)
        self.tree.column("from", width=420)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree.bind("<Button-1>", self._on_tree_click)
        row = ttk.Frame(src)
        row.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Button(row, text="Dodaj pliki…", command=self._pick_files).pack(side="left")
        ttk.Button(row, text="Dodaj folder…", command=self._pick_source_folder).pack(side="left", padx=6)
        ttk.Button(row, text="Wyczyść listę", command=self.clear_sources).pack(side="left")
        for widget in (self.tree, src):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self._on_drop)

        where = ttk.LabelFrame(self.root, text="2. Gdzie szukam")
        where.pack(fill="x", **pad)
        row = ttk.Frame(where)
        row.pack(fill="x", padx=6, pady=6)
        ttk.Button(row, text="Wybierz folder…", command=self._pick_search_root).pack(side="left")
        ttk.Label(row, textvariable=self.root_label).pack(side="left", padx=10)
        row = ttk.Frame(where)
        row.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Label(row, text="Podobieństwo nazwy (min. %):").pack(side="left")
        tk.Scale(row, from_=50, to=100, orient="horizontal", variable=self.threshold,
                 length=260).pack(side="left", padx=8)
        ttk.Button(row, text="Szukaj", command=self.start_search).pack(side="right")

        rev = ttk.LabelFrame(self.root, text="3. Trafienia")
        rev.pack(fill="x", **pad)
        ttk.Label(rev, textvariable=self.counter).pack(anchor="w", padx=6, pady=(6, 0))
        ttk.Label(rev, textvariable=self.match_path, wraplength=800,
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=6)
        ttk.Label(rev, textvariable=self.match_info).pack(anchor="w", padx=6)
        tk.Label(rev, textvariable=self.warning, fg="#b00020", wraplength=800,
                 justify="left").pack(anchor="w", padx=6)
        row = ttk.Frame(rev)
        row.pack(fill="x", padx=6, pady=6)
        self.btn_delete = ttk.Button(row, text="Usuń", command=self._on_delete_click)
        self.btn_skip = ttk.Button(row, text="Pomiń", command=self._on_skip_click)
        self.btn_stop = ttk.Button(row, text="Zakończ", command=self.finish)
        for b in (self.btn_delete, self.btn_skip, self.btn_stop):
            b.pack(side="left", padx=(0, 6))
        ttk.Checkbutton(row, text="Usuń trwale (bez Kosza)", variable=self.permanent).pack(side="right")
        ttk.Label(self.root, textvariable=self.status).pack(anchor="w", padx=12, pady=(0, 8))

    # ---------- lista źródeł ----------
    def _on_drop(self, event) -> None:
        self.add_paths(self.root.tk.splitlist(event.data))

    def _pick_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Wybierz pliki")
        if paths:
            self.add_paths(paths)

    def _pick_source_folder(self) -> None:
        path = filedialog.askdirectory(title="Wybierz folder ze wzorcami")
        if path:
            self.add_paths([path])

    def add_paths(self, paths) -> None:
        for source in finder.collect_sources(paths):
            key = finder._key(source.path)
            if key not in self.sources:
                self.sources[key] = source
                self.checked[key] = True
        self._refresh_tree()
        self.status.set(f"Na liście: {len(self.sources)} nazw plików.")

    def clear_sources(self) -> None:
        self.sources.clear()
        self.checked.clear()
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        ordered = sorted(self.sources.items(), key=lambda kv: kv[1].name.casefold())
        for key, source in ordered:
            mark = "☑" if self.checked[key] else "☐"
            self.tree.insert("", "end", iid=key, values=(mark, source.name, str(source.path.parent)))

    def _on_tree_click(self, event) -> None:
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        if self.tree.identify_column(event.x) != "#1":
            return
        key = self.tree.identify_row(event.y)
        if key:
            self.checked[key] = not self.checked[key]
            self.tree.set(key, "use", "☑" if self.checked[key] else "☐")

    # ---------- wybór folderu i szukanie ----------
    def _pick_search_root(self) -> None:
        path = filedialog.askdirectory(title="Wybierz folder do przeszukania")
        if path:
            self.set_search_root(path)

    def set_search_root(self, path) -> None:
        self.search_root = Path(path)
        self.root_label.set(str(self.search_root))

    def start_search(self) -> None:
        chosen = [s for k, s in self.sources.items() if self.checked.get(k)]
        if not chosen:
            messagebox.showinfo("Mod Deleter", "Lista „Czego szukam” jest pusta lub nic nie jest zaznaczone.")
            return
        if self.search_root is None or not self.search_root.is_dir():
            messagebox.showinfo("Mod Deleter", "Najpierw wybierz folder do przeszukania.")
            return
        self.active_root = self.search_root
        self.matches = finder.find_matches(chosen, self.active_root, float(self.threshold.get()))
        self.index = 0
        self.deleted = 0
        self.last_error = ""
        if not self.matches:
            self.status.set("Nie znaleziono pasujących plików.")
            self._clear_review()
            return
        self.status.set(f"Znaleziono trafień: {len(self.matches)}.")
        self._show_current()

    # ---------- przegląd trafień ----------
    def _set_review_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for b in (self.btn_delete, self.btn_skip, self.btn_stop):
            b.configure(state=state)

    def _clear_review(self) -> None:
        self.counter.set("")
        self.match_path.set("")
        self.match_info.set("")
        self.warning.set("")
        self._set_review_enabled(False)

    def _show_current(self) -> None:
        while self.index < len(self.matches):
            match = self.matches[self.index]
            if not match.path.is_file():
                self.status.set(f"Pominięto (plik już nie istnieje): {match.path.name}")
                self.index += 1
                continue
            self.counter.set(f"Trafienie {self.index + 1} z {len(self.matches)}")
            self.match_path.set(str(match.path))
            self.match_info.set(f"Podobieństwo: {match.score:.0f}%   |   szukana nazwa: {match.source_name}")
            notes = []
            if match.is_source:
                notes.append("UWAGA: to jest plik wzorcowy, z którego pobrano nazwę.")
            try:
                emptied = finder.folders_emptied_by(match.path, self.active_root)
            except OSError:
                emptied = []
                notes.append("(nie można sprawdzić folderu)")
            if emptied:
                names = ", ".join(str(p) for p in emptied)
                notes.append(f"Po usunięciu zostaną też usunięte puste foldery: {names}")
            self.warning.set("\n".join(notes))
            self.shown_at = time.monotonic()
            self._set_review_enabled(True)
            return
        skipped = self.status.get()
        self.finish()
        if skipped.startswith("Pominięto"):
            self.status.set(f"{self.status.get()}  ({skipped})")

    def _click_too_soon(self) -> bool:
        return time.monotonic() - self.shown_at < CLICK_GUARD_SECONDS

    def _on_delete_click(self) -> None:
        if not self._click_too_soon():
            self.delete_current()

    def _on_skip_click(self) -> None:
        if not self._click_too_soon():
            self.skip_current()

    def delete_current(self) -> None:
        if not self.matches or self.index >= len(self.matches):
            return
        match = self.matches[self.index]
        permanent = self.permanent.get()
        if permanent and not messagebox.askyesno(
                "Usuń trwale", f"Usunąć trwale, bez Kosza?\n\n{match.path}"):
            return
        if match.is_source and not messagebox.askyesno(
                "Plik wzorcowy",
                "To jest plik wzorcowy, z którego pobrano nazwę. Na pewno usunąć?"):
            return
        if not permanent and not finder.drive_has_recycle_bin(match.path):
            if not messagebox.askyesno(
                    "Brak Kosza",
                    f"Ten dysk nie ma Kosza — plik zostanie usunięty trwale.\nKontynuować?\n\n{match.path}"):
                return
        self._set_review_enabled(False)
        self.root.update_idletasks()
        try:
            result = finder.delete_match(match.path, self.active_root, permanent=permanent)
        except OSError as exc:
            self.last_error = f"Nie udało się usunąć {match.path.name}: {exc}"
            self.status.set(self.last_error)
            self.index += 1
            self._show_current()
            return
        self.deleted += 1
        extra = f" (+ {len(result.removed_folders)} pustych folderów)" if result.removed_folders else ""
        self.status.set(f"Usunięto: {match.path.name}{extra}")
        self.index += 1
        self._show_current()

    def skip_current(self) -> None:
        if not self.matches or self.index >= len(self.matches):
            return
        self.index += 1
        self._show_current()

    def finish(self) -> None:
        summary = f"Koniec. Usunięto plików: {self.deleted}."
        if self.last_error:
            summary += f"  Ostatni błąd: {self.last_error}"
        self.status.set(summary)
        self.matches = []
        self._clear_review()


def main() -> None:
    root = TkinterDnD.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
