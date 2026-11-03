# Baza danych i znaczenie wyników

## Schematy i tabele

| Obiekt | Zawartość | Geometria / układ |
|---|---|---|
| public.powiat | Granica powiatu radomszczańskiego | geom, EPSG:2180 |
| bdot.ot_* | Warstwy BDOT10k; w zweryfikowanym imporcie 68 tabel | geom, EPSG:2180 |
| grid.h3_r6 / h3_r7 / h3_r8 | Bazowe siatki z ID i agregacjami | geom, MultiPolygon, EPSG:2180 |
| grid.h3_r6_2180 itd. | Widoki źródłowej geometrii | EPSG:2180 |
| grid.h3_r6_3857 itd. | Widoki transformujące geometrię | EPSG:3857 |

Identyfikator H3 ma nazwę h3_id i tekstową postać, np. 881e216743fffff. GUI używa ogólnej nazwy id. W BDOT identyfikatorem technicznym w obecnym imporcie jest ogc_fid. Nie należy zakładać, że ogc_fid pozostanie tym samym identyfikatorem po ponownym imporcie innej wersji plików.

## Dlaczego dwa układy

- Źródło PRG było opisane jako EPSG:4258. Generator transformuje dane do 4326 wymaganego do generowania H3.
- Import do bazy transformuje geometrię do 2180. W tym układzie obliczamy metry i metry kwadratowe.
- GUI i kafelki pracują w 3857. To układ prezentacji, nie podstawa przeliczenia metryk BDOT.
- Widok _3857 przelicza tylko geometrię. Wartości kolumn area_m2 i length_m nadal pochodzą z obliczeń w 2180.

Widoki nie posiadają własnych indeksów ani osobnej kopii geometrii. Ich odczyt jest wykonywaniem zapytania na tabeli źródłowej.

## Siatki i obszar obliczeń

Generator zapisuje pełne komórki przecinające powiat. Dlatego zasięg siatki może wystawać poza granicę PRG. Podczas agregacji komórki są tymczasowo przecinane z granicą powiatu; analizowane są części wewnątrz powiatu.

To ważne przy przyszłym modelu: komórka brzegowa nie może być automatycznie uznana za nieprzejezdną dlatego, że część poza powiatem nie była analizowana. Należy ustalić sposób traktowania jej powierzchni odniesienia.

Każda rozdzielczość jest generowana i agregowana oddzielnie. Nie zakładamy, że wynik r7 powstaje przez proste zsumowanie r8.

## Agregacje BDOT

Skrypt przegląda warstwy bdot o nazwach ot_*_a/l/p i tworzy kolumny double precision:

| Typ źródła | Przykładowa kolumna | Znaczenie |
|---|---|---|
| Poligony _a | ot_bubd_a_area_m2 | Suma powierzchni części obiektów w komórce i powiecie [m²]. |
| Linie _l | ot_skdr_l_length_m | Suma długości części obiektów w komórce i powiecie [m]. |
| Punkty _p | ot_adms_p_count | Liczba obiektów przypisanych do komórki. |

Dla punktu przecinającego kilka komórek wybierany jest najmniejszy h3_id, aby nie liczyć go wielokrotnie. Powierzchnia jest sumą powierzchni obiektów; jeśli źródłowe poligony się nakładają, nie oznacza automatycznie powierzchni ich unii.

Agregacje nie rozróżniają wszystkich kategorii wewnątrz warstwy. Np. samo pole długości warstwy drogowej nie koduje osobno każdej nawierzchni i kategorii drogi. Analiza wielokryterialna może wymagać dodatkowych agregacji według atrybutów BDOT.

Liczba 68 wynika z zaimportowanego zestawu, a nie ze stałej zaszytej w pętli SQL. Agregacja jest jednym poleceniem DO: błąd lub anulowanie przed zatwierdzeniem wycofuje operację, a nie pozostawia dowolnej części kolumn jako zakończonego etapu.

## Pole przejezdnosc

Aktualna migracja gui/add_passability.sql dodaje do trzech bazowych tabel:

| Właściwość | Obecna implementacja |
|---|---|
| Nazwa | przejezdnosc |
| Typ | double precision |
| Dopuszczalne wartości | NULL albo liczba od 0 do 1 |
| Początkowa wartość | NULL — brak obliczenia |
| Automatyczne obliczenie | Brak |
| GUI | Ciągła skala czerwony–żółty–zielony; NULL szary |

**Docelowe wymaganie:** dwie klasy 0/1. Obecny CHECK nie ogranicza pola wyłącznie do tych dwóch wartości. Nie twierdzimy, że wersja binarna jest już wdrożona. Ewentualny ciągły wskaźnik pośredni powinien zostać rozdzielony od klasy końcowej po ustaleniu metody.

GUI przesyła NULL również wtedy, gdy pole jeszcze nie istnieje, i pokazuje informację o potrzebie migracji. Żadna wartość nie jest losowana ani wyliczana z niezatwierdzonych wag.

Dodanie kolumny do tabeli nie rozszerza automatycznie wcześniej utworzonego widoku SELECT *. GUI omija ten problem przez odczyt tabel bazowych dla znanych aliasów H3. Aby pole było dostępne bezpośrednio w widokach w QGIS, należy po migracji świadomie odtworzyć widoki istniejącym skryptem, uwzględniając ich zależności. Nie jest to konieczne do działania obecnego GUI.

## Indeksy przestrzenne

Import tworzy GiST na geom. Skrypt gui/ensure_spatial_indexes.sql sprawdza istnienie gotowego, poprawnego, nieczęściowego indeksu GiST obejmującego geom i w razie potrzeby tworzy brakujący. Następnie odświeża statystyki ANALYZE.

Dla aliasów 2180 zwykłe filtrowanie geometrii może korzystać z indeksu źródła. Dla 3857 nie wystarczy automatycznie zapytać WHERE ST_Transform(geom,3857) && bbox: zwykły indeks na geom nie jest indeksem na wyrażeniu transformacji.

Obecne GUI stosuje:

```sql
WHERE t.geom && granice_kafelka_w_ukladzie_tabeli
```

Dopiero wybrane geometrie transformuje do 3857 do MVT. Obwiednia jest buforowana i segmentowana przed transformacją. Ostateczny wybór indeksu należy do planisty; kafelek obejmujący niemal całą warstwę może uzasadniać skan sekwencyjny.

## Zmiany wymagające uwagi

- app/load.py ma overwrite. Ponowny import może zastąpić tabele, usunąć dodatkowe kolumny albo zatrzymać się na zależnych widokach. To nie jest komenda rutynowego uruchamiania GUI.
- load_bdot.py także zastępuje tabele BDOT.
- Zmiana granicy, źródeł lub siatki wymaga ponownej oceny zależnych agregacji i wyników modelu.
- Zmiana brancha w Git nie zmienia automatycznie danych istniejącej bazy.
- Wolumen PostgreSQL zawiera rzeczywiste dane i nie jest zapisywany przez git push.
