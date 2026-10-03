# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.2.0] - 2026-10-03

### Changed
- **All user-facing text is now in English**: every label, button, dialog, status message and error message in the app, plus the README, this changelog, the release notes and the build script output. (The app was Polish-only in 1.0.0 and 1.1.0.)
- The version number shown in the window is now 1.2.0.

### Fixed
- Tests no longer skip silently when Tk fails to initialise transiently on Windows; window creation is retried first.

## [1.1.0] - 2026-10-03

A new look and a more comfortable workflow. The matching and deletion rules are unchanged.

### Added
- **Delete all (N)** — deletes all remaining matches at once after a confirmation that summarises the action (number of files, Recycle Bin or permanent, how many have a similarity below 100%). Reference files are skipped, and an error on one file does not stop the rest.
- A modern Windows 11 style theme, light and dark (follows the system by default), with a toggle button.
- A large drag-and-drop zone that highlights when you hover over it with files, and a “Selected: N of M” counter.
- Background search with a progress bar, a scanned-files counter and a **Cancel** button. The window no longer freezes on large folders.
- A colour-coded similarity badge on each match (green 100%, yellow from 90%, orange below).
- A **Show in Explorer** button.
- Remembering the last search folder, the similarity threshold and the theme (`%APPDATA%\ModDeleter\settings.json`). “Delete permanently” is deliberately not remembered.
- README and this changelog.

### Changed
- The window is resizable; the layout uses cards.
- `finder.find_matches` accepts optional `on_progress`, `should_cancel` and `progress_every` (existing calls keep working) and can raise `SearchCancelled`.
- `build.bat` bundles the theme files (`--collect-all sv_ttk`). New dependencies: `sv-ttk`, `darkdetect`.

### Known limitations
- Real mouse drag-and-drop and cancelling during a long search were not checked by hand (the tests use simulated events).

## [1.0.0] - 2026-10-03

First release.

### Added
- A window with drag-and-drop of folders and files: the file names are collected from them as search patterns, and each can be unticked.
- Searching the chosen folder (including subfolders) for files with the same extension and an exact or very similar name; a similarity threshold slider (default 85%).
- Reviewing matches one by one: full path, similarity percentage, Delete / Skip / Finish buttons.
- Deleting files only; folders left empty after a deletion are removed too (never the search root or anything above it, never non-empty folders).
- The Recycle Bin by default; “Delete permanently” with an extra confirmation.
- Safeguards: confirmation before deleting a reference file, a warning for drives without a Recycle Bin (network and removable), protection against accidental double-clicks, and automatic skipping of files that vanish during the review.
- `build.bat`, which builds a single `ModDeleter.exe`.
