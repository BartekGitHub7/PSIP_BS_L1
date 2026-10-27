# GUI Tkinter — instrukcja użytkownika

## Przeznaczenie

Natywna aplikacja do przeglądania warstw PostGIS, siatek H3 i przyszłych wyników przejezdności. Interfejs korzysta z Tkinter i lokalnego renderowania kafelków MVT. Nie wymaga QGIS do samego wyświetlania, choć QGIS pozostaje narzędziem niezależnej kontroli danych.

## Wymagania

Windows, Python z Tkinter, Docker Desktop z uruchomioną bazą env-test i pliki katalogu gui z aktualnej paczki PSIP_Tkinter_MVT.zip. Pakiety instalowane są w lokalnym .venv-gui; to inne środowisko niż Python w kontenerze do importu danych.

W katalogu projektu:

```powershell
.\.venv-gui\Scripts\python.exe -m pip install -r .\gui\requirements.txt
.\.venv-gui\Scripts\python.exe .\gui\main.py
```

Jeśli środowisko jeszcze nie istnieje, najpierw:

```powershell
py -3 -m venv .venv-gui
```

Aktualna paczka wymaga co najmniej Pythona 3.10; sprawdzaj też wymagania instalowanych wersji bibliotek. Zależności mają zakresy wersji, nie są pełnym lockfile.

## Dodanie danych

1. Kliknij Dodaj dane z PostGIS.
2. Wpisz host localhost, port 5444, bazę psip, użytkownika psip oraz własne hasło środowiska TEST.
3. Kliknij Połącz. Katalog obejmuje schematy grid, bdot, public.
4. Zaznacz np. grid.h3_r8_3857; Ctrl umożliwia wybór kilku warstw.
5. Kliknij Dodaj zaznaczone. Program dopasuje mapę do widocznych danych.

Można wybrać również wariant _2180 lub bazową tabelę H3. Mapa jest zawsze w EPSG:3857. Znane aliasy H3 odczytują dane tabeli bazowej, a nie dodatkowej kopii.

## Pola pobierane do mapy

| Rodzaj warstwy | Pola |
|---|---|
| Siatka H3 | id, geom, przejezdnosc |
| BDOT / warstwa pomocnicza | id, geom |

W MVT id jest właściwością tekstową, co pozwala zachować identyfikator H3. NULL przejezdności może być pominięty w właściwościach konkretnego obiektu MVT; dekoder traktuje brak pola jako brak wyniku.

Przy dodaniu warstwy odczytywane są metadane i zasięg. Geometrie do mapy są pobierane wyłącznie w potrzebnych kafelkach. Nie pobieramy 68 kolumn agregacji.

## Lista warstw

| Czynność | Obsługa |
|---|---|
| Zaznaczenie | Kliknij nazwę warstwy. |
| Widoczność | Kliknij ☑/☐ lub przycisk Pokaż/ukryj. |
| Usunięcie z mapy | Usuń lub Delete na liście. Dane w bazie pozostają. |
| Zmiana kolejności | ↑ i ↓; pozycja wyżej na liście jest na wierzchu. |
| Dopasowanie do jednej warstwy | Przybliż; włącza też widoczność tej warstwy. |
| Dopasowanie do widocznych | Pokaż wszystkie warstwy. |
| Menu kontekstowe | Prawy przycisk na nazwie warstwy. |
| Tabela | Zaznacz warstwę i kliknij Tabela danych. |

Ta sama nazwana warstwa z tego samego połączenia nie jest dodawana dwukrotnie. Alias _2180 i alias _3857 mają różne nazwy i mogą zostać dodane osobno, choć przedstawiają tę samą siatkę.

## Mapa

Lewy przycisk przesuwa mapę, kółko i +/− zmieniają zoom. Przy przesuwaniu gotowe kafelki są przemieszczane, a po zakończeniu ruchu doczytywane są brakujące. Status pokazuje zoom, liczbę kafelków i transfer od uruchomienia aplikacji.

Odśwież kafelki usuwa pamięciowy cache, aby mapa pobrała zmienione dane. Należy poczekać na zakończenie bieżących żądań. Zamknięcie aplikacji również usuwa cache.

## Przejezdność i legenda

Bieżąca wersja: 0 czerwony, 0,5 żółty, 1 zielony; pomiędzy kolorami interpolacja. NULL i nieprawidłowe dane są szare. Jest to kolorowanie wartości komórek (mapa tematyczna), nie estymacja gęstości punktów.

**Szara mapa jest oczekiwana przed obliczeniem modelu.** Nie świadczy sama w sobie o błędzie bazy. Brak kolumny jest dodatkowo sygnalizowany w opisie warstwy. Dostarczona migracja dodaje kolumnę, ale nie oblicza wartości.

Prowadzący wymaga dwóch klas wyniku. Obecna ciągła legenda musi zostać później dopasowana. Do czasu uzgodnienia kryteriów nie oznaczamy przypadkowych komórek jako przejezdnych.

## Tabela danych

Siatka pokazuje dokładnie id, geom, przejezdnosc. BDOT pokazuje id i geom. Pobierane jest do 101 rekordów, z czego 100 wyświetlamy, a dodatkowy pozwala stwierdzić istnienie następnej strony. Poprzednie/Następne przełącza strony; Odśwież tabelę ponawia odczyt.

Geom jest prezentowany jako WKT w SRID tabeli źródłowej i skracany na ekranie do 200 znaków. Jest to ograniczenie prezentacji; geometria w bazie nie jest skracana. Dla aliasu 3857 tabela GUI może więc pokazywać WKT źródła 2180; etykieta EPSG w oknie wskazuje ten układ.

Tabela jest tylko do odczytu. Nie wdrożono edycji, zapisu projektu, identyfikacji klikniętego obiektu, wyszukiwania tras ani eksportu mapy.

## Ograniczenia wydajności

MVT ogranicza transfer, upraszcza i przycina geometrię do skali kafelka. Bardzo małe obiekty mogą zniknąć w oddaleniu. Źródłowa geometria pozostaje w bazie. Włączenie wszystkich 68 warstw nadal może być kosztowne, szczególnie na widoku całego powiatu. Cache nie jest utrwalany na dysku; po ponownym otwarciu pierwsze kafelki są pobierane od nowa.
