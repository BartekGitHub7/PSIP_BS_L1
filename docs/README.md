# PSIP — dokumentacja projektu

Stan opisany: **27 października 2026 r.** Repozytorium: [BartekGitHub7/PSIP_BS_L1](https://github.com/BartekGitHub7/PSIP_BS_L1).
Obszar: **powiat radomszczański, TERYT 1012**.

Projekt obejmuje przygotowanie danych przestrzennych w PostGIS, siatki H3 z agregacjami BDOT10k oraz aplikację desktopową Tkinter wyświetlającą dane z bazy przez kafelki wektorowe MVT. Kolejnym etapem ma być klasyfikacja przejezdności terenu metodą analizy wielokryterialnej.

**Działa przygotowanie i prezentacja danych. Nie ma jeszcze modelu wyznaczającego przejezdność.** Puste pole nie oznacza terenu nieprzejezdnego.

## Od czego zacząć

| Dokument | Zawartość |
|---|---|
| [STATUS.md](STATUS.md) | Co wykonano, co potwierdzono, a co pozostaje do zrobienia. |
| [ARCHITEKTURA.md](ARCHITEKTURA.md) | Przepływ danych i odpowiedzialność poszczególnych plików. |
| [BAZA_DANYCH.md](BAZA_DANYCH.md) | Schematy, układy współrzędnych, H3, agregacje, indeksy i przejezdność. |
| [GUI.md](GUI.md) | Uruchomienie, obsługa, trzy pola siatki i sposób działania MVT. |
| [UTRZYMANIE.md](UTRZYMANIE.md) | Kontrola działania, zapis w Git, kopia bazy i rozwiązywanie problemów. |
| [ZRODLA_I_WERYFIKACJA.md](ZRODLA_I_WERYFIKACJA.md) | Podstawa opisu, wersje źródeł i zakres wykonanych sprawdzeń. |

## Najważniejsze fakty

- Źródło granicy: PRG; dane tematyczne: BDOT10k tego samego powiatu.
- Obliczenia powierzchni i długości: **EPSG:2180**.
- Wyświetlanie mapy GUI i kafelki: **EPSG:3857**.
- Siatki: H3 **r6, r7, r8**; r8 jest najdrobniejsza z tych trzech.
- Każda siatka ma **68 kolumn agregacji BDOT** w zweryfikowanym zbiorze.
- GUI pobiera dla siatki tylko **ID, geometrię i przejezdność**. Pozostałe atrybuty pozostają w bazie.
- Ostateczna przejezdność ma mieć **dwie klasy: 0 — nieprzejezdne, 1 — przejezdne**.
- **NULL — brak obliczeń lub danych**. Nie jest trzecią klasą analityczną.
- Kryteria, wagi, reguły wykluczające i metoda klasyfikacji **nie zostały zatwierdzone**.

## Środowiska

| Zastosowanie | Branch / środowisko | Port na Windowsie | Projekt Compose |
|---|---|---:|---|
| Praca na danych i GUI | env-test | 5444 | remote-db-env-test |
| Środowisko QA | env-qa | 5445 | remote-db-env-qa |
| Środowisko main | main | 5446 | remote-db-main |
| Osobna lokalna baza z local Compose | — | 5447 | domyślny projekt lokalny |

GUI rozwijamy lokalnie na **feature/gui-tkinter**. Branch funkcjonalny nie jest dodatkowym środowiskiem bazy. GUI łączy się z env-test na 5444.

Słowo „remote” w nazwach nie oznacza obecnie serwera w chmurze: runner i Docker działają na komputerze użytkownika. Każde środowisko ma odrębny wolumen i odrębne dane.
