# Stan prac i decyzje

Data: 27.10.2026. Ten dokument oddziela stan wykonany od planów. Nie jest deklaracją ukończenia wszystkich laboratoriów.

## Wykonane etapy

| Etap | Stan | Podstawa |
|---|---|---|
| Repozytorium, branche, PR i merge | Wykonane w dotychczasowej pracy | Historia pracy i obecne branche repozytorium. |
| Trzy środowiska PostGIS | Uruchomione i wcześniej sprawdzone | Wyniki docker ps i pg_isready użytkownika. |
| GitHub Actions + runner self-hosted | Przygotowane | Workflow w repo; runner wcześniej zgłaszał Listening for Jobs. |
| Granica właściwego powiatu | Poprawiona | Odczyt PRG: powiat radomszczański, 1012. |
| Generowanie H3 r6/r7/r8 | Wykonane | Generator i załadowane siatki. |
| Import 68 warstw BDOT | Wykonane w env-test | Użytkownik pokazał listę 68 tabel. |
| Agregacja BDOT do trzech siatek | Wykonana | Po 68 kolumn i niezerowe wyniki; sumy kontrolne poniżej. |
| Widoki 2180/3857 | Utworzone i sprawdzone w env-test | geometry_columns: 9 pozycji z odpowiednimi SRID. |
| GUI Tkinter | Uruchomione przez użytkownika | Potwierdzenie działania. |
| Przejście na MVT | Zaimplementowane | Kod aktualnej paczki i testy lokalne. |
| Trzy pola siatki i sterowanie warstwami | Zaimplementowane; użytkownik potwierdził działanie bieżącej wersji | Aktualny gui/main.py i informacja „działa jak na razie”. |
| Pole przejezdnosc i migracja | Dostarczony skrypt | Nie zebrano osobnego wyniku SQL potwierdzającego stan kolumn na komputerze. |
| Klasyfikacja przejezdności | **Niewykonana** | Brak zatwierdzonej metody i danych wynikowych. |

Stan uruchomionych kontenerów może zmieniać się po zamknięciu Docker Desktop. Dawne potwierdzenie działania nie oznacza bieżącego monitorowania.

## Wyniki kontrolne po poprawieniu powiatu

Użytkownik odczytał następujące sumy z env-test:

| Siatka | Powierzchnia budynków ot_bubd_a [m²] | Długość ot_skdr_l [m] | Liczba ot_adms_p |
|---|---:|---:|---:|
| r6 | 10 427 009,75 | 6 635 715,38 | 523 |
| r7 | 10 427 009,75 | 6 635 715,38 | 523 |
| r8 | 10 427 009,75 | 6 635 720,60 | 523 |

Długość linii dla r8 różni się o około 5,22 m. Przyczyna nie została jednoznacznie ustalona. Należy zachować tę informację; nie opisywać wszystkich sum jako identycznych. Suma długości to długość obiektów warstwy, a nie pomiar trasy przejazdu.

Dawna siatka r8 licząca 1885 komórek odnosiła się do błędnej granicy powiatu mińskiego. Po zmianie źródła granicy zgłaszano 2264 komórki r8; bieżącą liczbę należy odczytać z bazy.

## Zapis w repozytorium

Podczas odczytu GitHub 27.10.2026:

- env-test: `3eae8a932024dd7dbc2be38fe3b24df2894cc083`;
- env-qa: `41c15989737d6933b577ea559944287cd958947e`;
- main: `36c6acc90c656cc53192189f8b0d2a7d657cee7e`;
- zdalna lista nie zawierała `feature/gui-tkinter`.

Powyższa lista opisuje stan PRZED zapisem tej sesji. Następnie utworzono zdalny branch **feature/gui-tkinter** z env-test i zapisano cztery pliki GUI oraz .gitignore. Zapis kodu zakończył commit `bf18c0920dc5a2e9798e34db35d04017ca08c553` (następne commity dodają dokumentację). Kod jest już zdalnie dostępny. Nie wykonano merge do env-test, env-qa ani main. Nie odczytano lokalnych, dodatkowych zmian na dysku użytkownika.

## Ustalenia dotyczące przejezdności

**Potwierdzone przez prowadzącego:** analiza wielokryterialna; dwie klasy: nieprzejezdne i przejezdne.

**Nieustalone:** typ pojazdu, warunki terenowe, ruch po drogach/poza drogami, konkretne cechy BDOT, użycie NMT, reguły barier, wagi, punktacja, próg i sposób walidacji.

Wcześniejsze propozycje samochodu terenowego do 3,5 t, warunków suchych, wag 50/30/20 i progu 0,6 były wyłącznie pomysłem do rozmowy. **Nie stanowią wymagań ani przyjętej metody.** Nie należy ich implementować bez ustaleń.

## Różnica między wymaganiem a obecną implementacją

Obecna kolumna jest typu double precision i dopuszcza cały zakres 0–1. Legenda GUI jest ciągła: czerwony, żółty, zielony. To istniejąca infrastruktura prezentacji, nie gotowy model klasyfikacji.

Docelowo wynik ma zawierać tylko 0 albo 1, z szarym kolorem dla NULL. Do wykonania po ustaleniach: dostosować legendę do dwóch klas, rozstrzygnąć schemat pola wyniku i ewentualnego osobnego wskaźnika ciągłego. Teraz nie wprowadzamy tych zmian ani wartości demonstracyjnych do bazy.

## Kolejność dalszych prac

1. Zapisać lokalny kod, dokumentację i osobno kopię bazy.
2. Zinwentaryzować rzeczywiste atrybuty BDOT, nie tylko nazwy 68 warstw.
3. Ustalić znaczenie przejezdności komórki oraz kryteria z prowadzącym.
4. Zapisać metodę w dokumentacji: jednostki, normalizacja, wagi, bariery, klasyfikacja, obsługa NULL.
5. Zaimplementować obliczenia i dwuklasową prezentację.
6. Sprawdzić wynik na wybranych fragmentach terenu i wpływ rozdzielczości H3.

Przejezdność powierzchni komórki nie dowodzi istnienia ciągłej trasy przez komórkę. Model tras i połączeń nie został wdrożony.
