# Mod Deleter

A Windows desktop app that deletes files whose names are the same as, or very similar to, a set of reference files. It was built for tidying mod folders: you drop in a folder (or files) containing the old versions, point the app at the folder to clean, and it finds the matching files and asks, one by one, whether to delete each of them.

It deletes **files only**. Folders disappear only when they are left completely empty after a file was deleted.

## Download

The ready-to-run program (`ModDeleter.exe`, no Python needed) is on the **[Releases](../../releases/latest)** page. Download the file and double-click it.

> **Windows warning:** the file is not code-signed, so SmartScreen may block it. Click “More info” → “Run anyway”.

The repository is private, so downloading requires being signed in to an account with access.

## How to use

1. **What to look for.** Drag folders or files onto the window (or use “Add files…” / “Add folder…”). The app takes only the file names from them. You can untick any entry in the list.
2. **Where to search.** Click “Choose folder…” and pick the folder to clean. The app searches it together with all its subfolders.
3. **Similarity threshold.** The slider (50–100%, default 85%) sets how much a name may differ, e.g. `sodium-0.5.jar` vs `sodium-0.6.jar`.
4. Click **Search**. The search runs in the background; you can watch the progress and stop it with **Cancel**.
5. For each match you see the full path, the similarity percentage and the name it matched. Then click:
   - **Delete** — deletes this file,
   - **Skip** — moves on to the next match,
   - **Show in Explorer** — opens the folder with the file selected,
   - **Delete all (N)** — deletes all remaining matches at once, after an extra confirmation (see below),
   - **Finish** — ends the review.

### Matching rules

- The extension must be **identical** (case does not matter): `sodium.jar` does not match `sodium.txt`.
- The name (without the extension) may be exact or very similar. Letter case and the characters `-`, `_`, `.` and space are treated alike.
- An exact match scores 100%. Badge colour: green for 100%, yellow from 90%, orange below that.

### Delete all

The button deletes every match from the current one to the end of the list. Before anything is deleted, a confirmation dialog appears (the default answer is “No”) that shows:

- how many files will be deleted, and whether they go to the Recycle Bin or are deleted permanently,
- how many of them have a similarity below 100%, and the lowest similarity,
- a warning if some files are on a drive without a Recycle Bin (network or removable).

Reference files (the ones the names were taken from) are skipped. An error on one file does not stop the rest, and a summary is shown at the end.

## Safety

- Files go to the **Recycle Bin** by default. “Delete permanently (skip Recycle Bin)” asks for an extra confirmation and is **not remembered**: it is off every time you start the app.
- A folder is deleted only if it is completely empty (hidden files count as content). The folder you chose to search, and any folder above it, is never deleted.
- Deleting a reference file requires a separate confirmation.
- On a network drive or USB stick (no Recycle Bin) the app warns that the file will be gone for good.
- The “Delete” button ignores clicks during the first 0.4 s after a match is shown, so an accidental double-click cannot delete a file you have not had time to see.
- A file that disappeared during the review is skipped automatically.

**Try the app on a copy of your folder before using it on real mods.**

## Settings

The app remembers the last folder searched, the similarity threshold and the theme (light/dark; follows the system by default) in `%APPDATA%\ModDeleter\settings.json`. A missing or corrupted file is ignored.

## Running from source

Python 3.11 or newer is required.

```bat
python -m pip install -r requirements.txt
python app.py
```

### Building the .exe

```bat
build.bat
```

The script installs the dependencies and builds `dist\ModDeleter.exe` with PyInstaller (`--onefile --windowed`).

### Tests

```bat
python -m pip install -r requirements-dev.txt
python -m pytest
```

The symlink test is skipped when the system does not allow creating symlinks.

## Project layout

| File | Purpose |
|---|---|
| `finder.py` | UI-free logic: collecting names, matching, deleting files and empty folders |
| `app.py` | The window (tkinter, `sv-ttk`, `tkinterdnd2`) |
| `settings.py` | Saving and loading settings |
| `tests/` | Tests (`pytest`) |
| `build.bat` | Builds `ModDeleter.exe` |
| `docs/superpowers/` | Design spec and implementation plan (in Polish) |

## Known limitations

- With a low similarity threshold (the slider goes down to 50%) many loosely similar matches show up. Each one still needs a click, but it is best to start with a higher threshold.
- Folders that cannot be read are skipped without a message.
- The app is not code-signed (see the Windows warning above).

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
