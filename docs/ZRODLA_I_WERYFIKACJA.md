# Podstawa dokumentacji i zakres weryfikacji

Dokumentację sporządzono 27.10.2026 na podstawie odczytanego kodu repozytorium, aktualnych dostarczonych plików GUI i wyników poleceń przekazanych przez użytkownika w toku pracy. To zapis stanu, a nie nowa analiza danych.

## Odczyt repozytorium

Sprawdzono branch env-test, commit `3eae8a932024dd7dbc2be38fe3b24df2894cc083`:

- [README](https://github.com/BartekGitHub7/PSIP_BS_L1/blob/3eae8a932024dd7dbc2be38fe3b24df2894cc083/README.md);
- [generator H3](https://github.com/BartekGitHub7/PSIP_BS_L1/blob/3eae8a932024dd7dbc2be38fe3b24df2894cc083/app/python/h3_generator.py);
- [import granicy i siatek](https://github.com/BartekGitHub7/PSIP_BS_L1/blob/3eae8a932024dd7dbc2be38fe3b24df2894cc083/app/load.py);
- [import BDOT](https://github.com/BartekGitHub7/PSIP_BS_L1/blob/3eae8a932024dd7dbc2be38fe3b24df2894cc083/app/python/load_bdot.py);
- [agregacja](https://github.com/BartekGitHub7/PSIP_BS_L1/blob/3eae8a932024dd7dbc2be38fe3b24df2894cc083/app/aggregate_bdot.sql);
- [widoki CRS](https://github.com/BartekGitHub7/PSIP_BS_L1/blob/3eae8a932024dd7dbc2be38fe3b24df2894cc083/app/create_grid_crs_views.sql);
- docker-compose-local.yml, docker-compose-remote.yml i start_services.yml.

Przed zapisem sprawdzono listę zdalnych branchy: env-test, env-qa, main; nie było feature/gui-tkinter. Następnie w tej sesji utworzono feature/gui-tkinter i zapisano aktualny kod GUI (punkt kontrolny kodu: bf18c0920dc5a2e9798e34db35d04017ca08c553). Dokumentacja została dodana po kodzie, w kolejnych commitach.

## Wersja GUI opisana w dokumentacji

Źródło: gui/main.py z aktualnej paczki **PSIP_Tkinter_MVT.zip** po dodaniu obsługi przejezdności i sterowania warstwami, przed zmianą prezentacji na dwie klasy.

SHA-256 pliku main.py:

```text
5e310cd5528b4ae9c92ab8f3fa976dd11ce284467355cd4a8878c7d96ee3908c
```

To identyfikator zawartości dostarczonego pliku. Zapisano go również zdalnie na feature/gui-tkinter. Lokalny plik użytkownika może różnić się, jeśli wprowadzono własne zmiany. Użytkownik potwierdził działanie aktualnej wersji, ale nie przekazał pełnego odczytu wszystkich danych bazy po migracji.

## Wykonane sprawdzenia kodu GUI

- Kompilacja składni Python.
- Kodowanie i dekodowanie testowych kafelków MVT.
- Zachowanie tekstowego ID oraz pola przejezdności.
- Rysowanie poligonów, otworów, geometrii wieloczęściowych, linii i punktów.
- Puste kafelki i przezroczystość.
- Kolory wartości 0, 0,5, 1; NULL oraz nieprawidłowe wartości.
- Budowa SQL z trzema polami siatki i indekso-przyjaznym filtrem.
- Mapowanie znanych aliasów H3 do tabel źródłowych.
- Wyznaczanie kafelków XYZ.
- Usuwanie cache warstwy i zmiana kolejności.
- Odrzucenie wyniku trwającego zadania dla już usuniętej warstwy.

Testy używały danych syntetycznych oraz zastępczych obiektów dla części logiki. Nie stanowią pełnego testu Windows/Tkinter/PostGIS. Nie przeprowadzono automatycznie testu wszystkich przycisków w rzeczywistym oknie ani zapytań na bazie użytkownika.

## Wyniki danych

Liczby warstw, kolumn i sumy kontrolne w STATUS.md pochodzą z wcześniejszych wyników SQL przekazanych przez użytkownika. Nie pobierano ponownie całej bazy. Nie potwierdzono obecnej równości danych między TEST, QA i main; uruchomienie trzech kontenerów nie jest taką weryfikacją.

## Skrypty w tej paczce

check_test.sql jest zbiorem zapytań tylko do odczytu. backup_test.ps1 wykonuje kopię za pomocą istniejących narzędzi kontenera. Przy przygotowaniu sprawdzono zawartość i spójność instrukcji; nie uruchomiono ich na komputerze użytkownika. Migracji i backupu na komputerze użytkownika nie wykonano. Kod i dokumentację zapisano natomiast zdalnie w repozytorium; lokalna kopia robocza wymaga niezależnej synchronizacji zgodnie z UTRZYMANIE.md.

## Aktualizowanie dokumentacji

Po istotnej zmianie kodu uaktualnij datę, STATUS.md i opis właściwego modułu. Po zdefiniowaniu modelu dodaj osobny dokument metody z kryteriami, wzorami, wagami, źródłami i walidacją. Nie zmieniaj wcześniejszych propozycji na „zatwierdzone” bez rzeczywistej decyzji.
