# Mod Deleter

Program okienkowy na Windows, który usuwa pliki o takiej samej lub bardzo podobnej nazwie jak pliki wzorcowe. Powstał z myślą o porządkowaniu folderów z modami: wrzucasz folder (albo pliki) ze starymi wersjami, wskazujesz folder do przeszukania, a program znajduje pasujące pliki i przy każdym pyta, czy go usunąć.

Usuwa **tylko pliki**. Foldery znikają wyłącznie wtedy, gdy po usunięciu pliku zostały całkiem puste.

## Pobieranie

Gotowy program (`ModDeleter.exe`, Python nie jest potrzebny) jest w zakładce **[Releases](../../releases/latest)**. Pobierz plik i uruchom go dwuklikiem.

> **Ostrzeżenie Windows:** plik nie jest podpisany certyfikatem, więc SmartScreen może go zablokować. Kliknij „Więcej informacji” → „Uruchom mimo to”.

Repozytorium jest prywatne, więc pobieranie wymaga zalogowania na konto z dostępem.

## Jak używać

1. **Czego szukam.** Przeciągnij na okno foldery lub pliki (albo użyj „Dodaj pliki…” / „Dodaj folder…”). Program pobierze z nich same nazwy plików. Pozycje na liście możesz odznaczyć.
2. **Gdzie szukam.** Kliknij „Wybierz folder…” i wskaż folder do przeszukania. Program przeszuka go razem ze wszystkimi podfolderami.
3. **Próg podobieństwa.** Suwak (50–100%, domyślnie 85%) ustala, jak bardzo nazwa może się różnić, np. `sodium-0.5.jar` i `sodium-0.6.jar`.
4. Kliknij **Szukaj**. Szukanie działa w tle, widać postęp i można je przerwać przyciskiem **Anuluj**.
5. Dla każdego trafienia zobaczysz pełną ścieżkę, procent podobieństwa i nazwę, której dotyczy. Kliknij:
   - **Usuń** — usuwa ten plik,
   - **Pomiń** — przechodzi do następnego,
   - **Pokaż w Eksploratorze** — otwiera folder z zaznaczonym plikiem,
   - **Usuń wszystkie (N)** — usuwa wszystkie pozostałe trafienia naraz, po dodatkowym potwierdzeniu (patrz niżej),
   - **Zakończ** — kończy przegląd.

### Zasady dopasowania

- Rozszerzenie musi być **takie samo** (wielkość liter nie ma znaczenia): `sodium.jar` nie pasuje do `sodium.txt`.
- Nazwa (bez rozszerzenia) może być dokładna albo bardzo podobna. Wielkość liter oraz znaki `-`, `_`, `.` i spacja są traktowane jednakowo.
- Dokładne dopasowanie ma 100%. Kolor etykiety: zielony 100%, żółty od 90%, pomarańczowy niżej.

### Usuń wszystkie

Przycisk usuwa wszystkie trafienia od bieżącego do końca listy. Przed usunięciem pojawia się okno z potwierdzeniem (domyślnie zaznaczona jest odpowiedź „Nie”), w którym widać:

- ile plików zostanie usuniętych i czy trafią do Kosza, czy zostaną usunięte trwale,
- ile z nich ma podobieństwo poniżej 100% i jakie jest najniższe,
- ostrzeżenie, jeśli któreś pliki leżą na dysku bez Kosza (sieciowym lub wymiennym).

Pliki wzorcowe (te, z których pobrano nazwy) są pomijane. Błąd przy jednym pliku nie przerywa usuwania pozostałych, a po zakończeniu pojawia się podsumowanie.

## Bezpieczeństwo

- Pliki domyślnie trafiają do **Kosza**. Opcja „Usuń trwale (bez Kosza)” wymaga dodatkowego potwierdzenia i **nie jest zapamiętywana**: przy każdym uruchomieniu jest wyłączona.
- Foldery są usuwane tylko wtedy, gdy są całkowicie puste (ukryte pliki liczą się jako zawartość). Folder wybrany do przeszukania ani żaden folder nad nim nie zostanie usunięty.
- Usunięcie pliku wzorcowego wymaga osobnego potwierdzenia.
- Na dysku sieciowym lub pendrive (bez Kosza) program ostrzega, że plik zniknie na stałe.
- Przycisk „Usuń” ignoruje kliknięcia w pierwszych 0,4 s po pokazaniu trafienia, żeby przypadkowe podwójne kliknięcie nie usunęło pliku, którego nie zdążyłeś zobaczyć.
- Plik, który zniknął w trakcie przeglądu, jest automatycznie pomijany.

**Przed pierwszym użyciem na prawdziwych modach przetestuj program na kopii folderu.**

## Ustawienia

Program zapamiętuje ostatni folder do przeszukania, próg podobieństwa i motyw (jasny/ciemny; domyślnie taki jak w systemie) w pliku `%APPDATA%\ModDeleter\settings.json`. Uszkodzony lub brakujący plik jest ignorowany.

## Uruchamianie ze źródeł

Wymagany jest Python 3.11 lub nowszy.

```bat
python -m pip install -r requirements.txt
python app.py
```

### Budowanie pliku .exe

```bat
build.bat
```

Skrypt instaluje zależności i buduje `dist\ModDeleter.exe` przez PyInstaller (`--onefile --windowed`).

### Testy

```bat
python -m pip install -r requirements-dev.txt
python -m pytest
```

Test z dowiązaniem symbolicznym jest pomijany, jeśli system nie daje uprawnień do ich tworzenia.

## Struktura projektu

| Plik | Rola |
|---|---|
| `finder.py` | Logika bez interfejsu: zbieranie nazw, dopasowanie, usuwanie plików i pustych folderów |
| `app.py` | Okno (tkinter, `sv-ttk`, `tkinterdnd2`) |
| `settings.py` | Zapis i odczyt ustawień |
| `tests/` | Testy (`pytest`) |
| `build.bat` | Budowanie `ModDeleter.exe` |
| `docs/superpowers/` | Specyfikacja i plan implementacji |

## Znane ograniczenia

- Przy niskim progu podobieństwa (suwak sięga do 50%) pojawia się dużo luźno podobnych trafień. Każde wymaga kliknięcia, ale warto zacząć od wyższego progu.
- Foldery, których nie da się odczytać, są pomijane bez komunikatu.
- Aplikacja nie jest podpisana certyfikatem (patrz ostrzeżenie Windows wyżej).

## Historia zmian

Zobacz [CHANGELOG.md](CHANGELOG.md).
