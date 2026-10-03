# Historia zmian

Format wzorowany na [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/).

## [1.1.0] - 2026-10-03

Nowy wygląd i wygodniejsza praca. Zasady dopasowania i usuwania pozostały bez zmian.

### Dodano
- **Usuń wszystkie (N)** — usuwa wszystkie pozostałe trafienia naraz, po potwierdzeniu z podsumowaniem (liczba plików, Kosz czy trwale, ile ma podobieństwo poniżej 100%). Pliki wzorcowe są pomijane, a błąd przy jednym pliku nie przerywa reszty.
- Nowoczesny motyw w stylu Windows 11, jasny i ciemny (domyślnie taki jak w systemie), z przyciskiem przełączania.
- Duża strefa przeciągania z podświetleniem po najechaniu plikiem oraz licznik „Zaznaczone: N z M”.
- Szukanie w tle z paskiem postępu, licznikiem przeszukanych plików i przyciskiem **Anuluj**. Okno nie zawiesza się przy dużych folderach.
- Kolorowa etykieta podobieństwa przy trafieniu (zielona 100%, żółta od 90%, pomarańczowa niżej).
- Przycisk **Pokaż w Eksploratorze**.
- Zapamiętywanie ostatniego folderu do przeszukania, progu podobieństwa i motywu (`%APPDATA%\ModDeleter\settings.json`). Opcja „Usuń trwale” celowo nie jest zapamiętywana.
- README oraz ten plik.

### Zmieniono
- Okno można rozciągać; układ w kartach.
- `finder.find_matches` przyjmuje opcjonalne `on_progress`, `should_cancel` i `progress_every` (dotychczasowe wywołania działają bez zmian) i może rzucić `SearchCancelled`.
- `build.bat` dołącza pliki motywu (`--collect-all sv_ttk`). Nowe zależności: `sv-ttk`, `darkdetect`.

### Znane ograniczenia
- Prawdziwe przeciąganie plików myszką i anulowanie w trakcie długiego szukania nie zostały sprawdzone ręcznie (testy używają symulowanych zdarzeń).

## [1.0.0] - 2026-10-03

Pierwsze wydanie.

### Dodano
- Okno z przeciąganiem folderów i plików: z nich pobierane są nazwy plików do wyszukania, każdą można odznaczyć.
- Wyszukiwanie w wybranym folderze (razem z podfolderami) plików o takim samym rozszerzeniu i dokładnej lub bardzo podobnej nazwie; suwak progu podobieństwa (domyślnie 85%).
- Przegląd trafień jedno po drugim: pełna ścieżka, procent podobieństwa, przyciski Usuń / Pomiń / Zakończ.
- Usuwanie tylko plików; puste foldery po usuniętym pliku też są usuwane (nigdy folder główny wyszukiwania ani nic nad nim, nigdy foldery niepuste).
- Domyślnie usuwanie do Kosza; „Usuń trwale” z dodatkowym potwierdzeniem.
- Zabezpieczenia: potwierdzenie przy usuwaniu pliku wzorcowego, ostrzeżenie dla dysków bez Kosza (sieciowych i wymiennych), ochrona przed przypadkowym podwójnym kliknięciem, automatyczne pomijanie plików, które zniknęły w trakcie przeglądu.
- `build.bat` budujący pojedynczy plik `ModDeleter.exe`.
