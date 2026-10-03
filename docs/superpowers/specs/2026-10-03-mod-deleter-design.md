# Mod Deleter — specyfikacja

## Cel
Program okienkowy na Windows. Użytkownik wrzuca foldery (z podfolderami) lub pliki, a program bierze z nich nazwy plików i szuka w wybranym folderze plików o takiej samej lub bardzo podobnej nazwie. Dla każdego trafienia pokazuje pełną ścieżkę i pyta, czy usunąć. Po usunięciu pliku usuwa też folder, który zrobił się pusty. Dystrybucja jako pojedynczy plik `.exe`.

## Zakres
- Wejście: foldery (rekurencyjnie) i/lub pojedyncze pliki, przez przeciągnięcie lub przycisk wyboru.
- Folder do przeszukania: wybierany przyciskiem, przeszukiwany rekurencyjnie.
- Dopasowanie po nazwie pliku: dokładne lub przybliżone.
- Usuwanie za każdym razem po potwierdzeniu użytkownika.
- Poza zakresem: dopasowanie po zawartości pliku, usuwanie niepustych folderów, usuwanie automatyczne bez pytania.

## Zachowanie

### 1. Źródło nazw
- Wrzucony folder jest skanowany rekurencyjnie, a nazwy wszystkich plików trafiają na listę „Czego szukam”.
- Wrzucone pliki dodają swoje nazwy do tej samej listy.
- Każdą pozycję można odznaczyć. Odznaczone nie są szukane.
- Wrzucone ścieżki służą tylko do pobrania nazw. Program niczego w nich nie usuwa z tego powodu.

### 2. Wyszukiwanie
- Przeszukanie wybranego folderu jest rekurencyjne (`os.walk`). Celami są wyłącznie pliki.
- Rozszerzenie musi być takie samo (bez rozróżniania wielkości liter). `sodium.jar` nie pasuje do `sodium.txt`. Plik bez rozszerzenia pasuje tylko do pliku bez rozszerzenia.
- Porównanie nazwy (bez rozszerzenia): małe litery, separatory (`-`, `_`, spacja, `.`) ujednolicone; podobieństwo z `difflib.SequenceMatcher`.
- Próg podobieństwa: suwak w oknie, domyślnie 85%. Dokładne dopasowanie ma 100%.
- Plik pasujący do kilku nazw z listy jest pokazany raz, z najlepszym wynikiem.
- Trafienia są posortowane malejąco po podobieństwie.
- Jeśli trafieniem jest plik, z którego pochodzi nazwa wzorcowa (folder wrzucony leży w przeszukiwanym folderze), jest oznaczony „plik wzorcowy” i domyślnie ostrzega przed usunięciem.

### 3. Potwierdzanie
- Dla każdego trafienia okno pokazuje: pełną ścieżkę, procent podobieństwa, nazwę, której dotyczy, licznik „trafienie N z M”.
- Przyciski: **Usuń**, **Pomiń**, **Zakończ**.
- Jeśli po usunięciu pliku folder zostanie pusty, okno informuje o tym przed decyzją („folder X też zostanie usunięty”).
- Nic nie jest usuwane bez kliknięcia „Usuń”.

### 4. Usuwanie
- Usuwany jest wybrany plik.
- Potem program sprawdza folder nadrzędny. Jeśli jest całkowicie pusty (bez plików, w tym ukrytych, i bez podfolderów), usuwa go. Powtarza to w górę drzewa, dopóki napotykane foldery są puste.
- Nigdy nie usuwa folderu głównego wybranego do przeszukania, ani żadnego folderu powyżej niego.
- Foldery niepuste nigdy nie są usuwane.
- Domyślnie pliki i puste foldery trafiają do Kosza (`send2trash`). Opcja „usuń trwale” w oknie używa `os.remove` i `os.rmdir`.
- Błędy (plik zablokowany, brak uprawnień) są pokazane w oknie, a program przechodzi do kolejnego trafienia.

## Struktura projektu
- `finder.py` — logika bez GUI: zbieranie nazw, dopasowanie, usuwanie pliku i pustych folderów.
- `app.py` — okno tkinter z `tkinterdnd2`.
- `tests/test_finder.py` — testy `finder` na tymczasowych drzewach folderów.
- `requirements.txt` — `tkinterdnd2`, `send2trash`, `pyinstaller`.
- `build.bat` — buduje `dist\ModDeleter.exe` przez PyInstaller (`--onefile --windowed`).

## Testy
- Dokładne dopasowanie ignoruje wielkość liter i separatory, ale wymaga tego samego rozszerzenia.
- Dopasowanie przybliżone respektuje próg.
- Foldery nigdy nie są trafieniami.
- Po usunięciu ostatniego pliku folder jest usuwany, a puste foldery nadrzędne też, aż do folderu głównego włącznie z jego wyłączeniem.
- Folder niepusty (inny plik, ukryty plik, podfolder) zostaje.
- Folder główny przeszukiwania nigdy nie jest usuwany.
- Plik wzorcowy jest oznaczany.
- Błąd usuwania nie przerywa pracy.
