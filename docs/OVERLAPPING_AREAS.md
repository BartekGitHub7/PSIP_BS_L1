# PSIP — kontrola i naprawa powierzchni H3 (BDOT10k)

## Wynik audytu przeslanego fragmentu

W pliku z wynikami przekroczen znajdowalo sie **2216** wierszy, dotyczacych **2183** roznych komorek H3. Wystepowaly wyłącznie dwie kolumny:

| Siatka | ot_adja_a_area_m2 | ot_adms_a_area_m2 |
| --- | ---: | ---: |
| h3_r6 | 61 | 23 |
| h3_r7 | 335 | 10 |
| h3_r8 | 1787 | 0 |

**To kontrola przeslanego fragmentu, nie pelnej geometrii z bazy.**
Wyniki dla `ot_adja_a` byly czesto 4 razy wieksze od powierzchni komorki. Skrypt w poprzedniej wersji wykonywal `SUM(ST_Area(ST_Intersection(...)))` dla wszystkich poligonow kazdej warstwy. Jesli kilka poligonow zachodzi na siebie, suma liczy ten sam teren wielokrotnie.

## Co zostalo zmienione

- `app/aggregate_bdot.sql`: dla `ot_adja_a` i `ot_adms_a` obliczana jest powierzchnia **unii** czesci poligonow przecietych z komorka (`ST_Area(ST_UnaryUnion(ST_Collect(...)))`). Inne warstwy nadal zachowuja dotychczasowa semantyke, bez niespodziewanej zmiany metryk.
- `app/repair_overlap_areas.sql`: jednorazowa naprawa **istniejacych** wartosci tych dwoch kolumn w trzech siatkach. Przed zmianami zapisuje ich stare wartosci w `audit.bdot_overlap_area_backup`, bez nadpisywania wczesniejszego backupu. Uzywa jednej transakcji i wykonuje kontrole zakresu; blad oznacza rollback.
- `app/verify_overlap_areas.sql`: odczytowy raport z liczba naruszen i maksymalnym udzialem powierzchni dla trzech siatek.

**Nie nalezy ponownie importowac siatek przez `load.py`**: ten skrypt odtwarza tabele H3 i usuwa juz zgromadzone agregaty.

## Procedura uruchomienia (Windows PowerShell, katalog projektu)

Najpierw upewnij sie, ze kontener PostGIS dla `env-test` jest uruchomiony. Nie uruchamiaj naprawy w `env-qa` ani `main`.

```powershell
git fetch origin
git switch fix/overlapping-bdot-area
Get-Content -Raw .\app\repair_overlap_areas.sql | docker exec -i remote-db-env-test-postgis-1 psql -U psip -d psip -v ON_ERROR_STOP=1
Get-Content -Raw .\app\verify_overlap_areas.sql | docker exec -i remote-db-env-test-postgis-1 psql -U psip -d psip -v ON_ERROR_STOP=1
```

Oczekiwany wynik w raporcie to `bledne_adja = 0` i `bledne_adms = 0` we wszystkich trzech wierszach. Przy pelnych komorkach i prawidlowych danych `max_udzial_*` nie powinien przekraczac 1. Jesli raport lub naprawa zglosza blad, zachowaj komunikat do dalszej diagnozy.

Przy ponownym uruchomieniu `repair_overlap_areas.sql` tabela backup nie jest nadpisywana: zachowuje pierwsza zarejestrowana wartosc dla kazdego `(grid_name, h3_id)`.

## Przykladowy test semantyki, bez modyfikacji danych

```sql
WITH nakladajace AS (
    SELECT ST_MakeEnvelope(0, 0, 10, 10, 2180) AS geom
    FROM generate_series(1, 4)
)
SELECT
    sum(ST_Area(geom)) AS suma_powierzchni_obiektow_m2,
    ST_Area(ST_UnaryUnion(ST_Collect(geom))) AS powierzchnia_unii_m2
FROM nakladajace;
-- Oczekiwane: 400 m2 i 100 m2.
```

## Ograniczenia i znaczenie wynikow

- Zmiana oznacza, ze pola `ot_adja_a_area_m2` i `ot_adms_a_area_m2` opisuja **unikalnie zajeta powierzchnie na danym poziomie warstwy**, a nie sume powierzchni jej obiektow (np. poziomow administracyjnych). Do zliczania obiektow i sumowania powierzchni konkretnych rekordow potrzebne sa osobne miary.
- Nie nalezy sumowac wszystkich pol powierzchni BDOT i porownywac ich z powierzchnia H3: rozne klasy obiektow moga nakladac sie miedzy warstwami (np. budynek i teren zabudowany). Jednowarstwowa unia nie rozstrzyga takich nakladek.
- Brak przekroczen po naprawie **nie dowodzi** pelnej poprawnosci geometrii, duplikatow w danych ani kompletnego pokrycia wszystkich kategorii.
- Skrypty zostaly przejrzane statycznie; wymagaja uruchomienia i zatwierdzenia wynikow w lokalnej bazie `env-test`, do ktorej nie ma dostepu z GitHub.
