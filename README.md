# PSIP\_BS\_L1

## Aktualna dokumentacja i aplikacja GUI

[Dokumentacja projektu — zacznij tutaj](docs/README.md) | [Stan prac](docs/STATUS.md) | [Obsługa GUI](docs/GUI.md)

Na branchu `feature/gui-tkinter` znajduje się przeglądarka Tkinter z kafelkami wektorowymi MVT, obsługą warstw oraz polem `przejezdnosc`. Kryteria analizy wielokryterialnej nie zostały jeszcze ustalone. Docelowo wynik ma dwie klasy (0/1); bieżące GUI zachowuje roboczą skalę 0–1 i szary kolor dla brakujących wyników. Szczegóły i ograniczenia opisano w dokumentacji.

laboratorium 1
- Stanisław - turecki
* Bartek - radomszczański
* Maciej - kutnowski
- Julia - hajnowski
- Daniel - sochaczewski
- Jan - miński
- Jan - warszawski
- Tymoteusz - toruński
- Marcin - miński
- Dominik - koniński
- Kacper - legnicki
- Jakub - chełmski
- Dawid - bocheński
- Michał - biłgorajski



## Laboratorium 2 — PostGIS, GitHub Actions i H3

Obszar opracowania: powiat radomszczański, kod TERYT 1012.

### Środowiska

| Branch / środowisko GitHub | Port | Projekt Docker Compose |
|---|---|---|
| env-test | 5444 | remote-db-env-test |
| env-qa | 5445 | remote-db-env-qa |
| main | 5446 | remote-db-main |

Każde środowisko ma osobny wolumen danych PostgreSQL.
Sekrety środowisk: POSTGRES_USER, POSTGRES_PASSWORD,
POSTGRES_DB i POSTGRES_PORT.

Runner GitHub Actions działa lokalnie w Dockerze.
Wymaga uruchomionego Docker Desktop oraz montowania
/var/run/docker.sock:/var/run/docker.sock.

### Uruchamianie bazy

Push na env-test, env-qa lub main uruchamia start_services.yml.

Zdalny Compose korzysta z lokalnego obrazu psip_bs_l1-postgis:latest.
Na nowym komputerze należy najpierw przygotować ten obraz:

```powershell
docker build -t psip_bs_l1-postgis:latest -f docker/postgis/Dockerfile .
```

Obraz lokalny zastosowano jako obejście problemu DNS podczas
pobierania obrazów przez runnera.

Ręczne workflow w GitHub Actions:
- Stop Remote Database — zatrzymuje bazę, zachowując dane.
- Destroy Remote Database — usuwa kontenery i wolumen wybranego
  środowiska; wymaga wpisania USUN.

Po usunięciu środowiska można je odtworzyć przez ponowienie
workflow Start Remote Database dla właściwego brancha.
Odtworzona baza wymaga ponownego importu danych.

### Dane i siatki H3

Granica PRG znajduje się w data/powiat.shp wraz z plikami
towarzyszącymi.

Dane BDOT10k należy pobrać osobno dla powiatu radomszczańskiego
i rozpakować do data/bdot. Paczka BDOT nie jest częścią repozytorium.

Przygotowanie kontenera Pythona i generowanie siatek:

```powershell
docker compose -f docker-compose-local.yml up -d --build python
docker compose -f docker-compose-local.yml exec python python /app/python/h3_generator.py
```

Generator zapisuje do output siatki o rozdzielczościach 6, 7 i 8.
Uwzględnia pełne komórki przecinające powiat.

Import granicy i siatek do wybranego środowiska, przykład env-test:

```powershell
$dbSecret = Read-Host "Haslo env-test" -AsSecureString
$env:PGPASSWORD = [System.Net.NetworkCredential]::new("", $dbSecret).Password
docker compose -f docker-compose-local.yml run --rm --no-deps -e PGPASSWORD python python /app/load.py --port 5444
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
Remove-Variable dbSecret -ErrorAction SilentlyContinue
```

Dla QA należy użyć portu 5445 i hasła QA, a dla main portu 5446
i hasła main.

Siatki są zapisywane w schemacie grid, a granica w public.powiat.
Geometrie w bazie mają układ EPSG:2180.

Uwaga: load.py zastępuje tabele siatek, usuwając również istniejące
kolumny agregacji. Import należy wykonać przed agregacją.

### BDOT i agregacja

BDOT importowany jest wyłącznie do env-test, do schematu bdot:

```powershell
$dbSecret = Read-Host "Haslo env-test" -AsSecureString
$env:PGPASSWORD = [System.Net.NetworkCredential]::new("", $dbSecret).Password
docker compose -f docker-compose-local.yml run --rm --no-deps -e PGPASSWORD python python /app/python/load_bdot.py
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
Remove-Variable dbSecret -ErrorAction SilentlyContinue
```

Uruchomienie agregacji w PowerShell:

```powershell
Get-Content -Raw .\app\aggregate_bdot.sql | docker exec -i remote-db-env-test-postgis-1 psql -U psip -d psip -v ON_ERROR_STOP=1
```

Dla każdej z 68 warstw powstaje osobna kolumna w każdej siatce:
- poligony: powierzchnia w m², końcówka _area_m2;
- linie: długość w metrach, końcówka _length_m;
- punkty: liczba obiektów, końcówka _count.

Obliczenia ograniczono do granicy powiatu.
Obiekt punktowy na granicy komórek przypisywany jest tylko raz.
Agregacja działa w jednej transakcji; anulowanie wycofuje jej postęp.

### Sprawdzenie wyników

Każda z trzech siatek ma 68 kolumn agregacji.
Suma powierzchni budynków w każdej rozdzielczości:
10 427 009,75 m².

Liczba obiektów warstwy ot_adms_p w każdej rozdzielczości: 523.

Wyniki sprawdzono zapytaniami SQL i wizualnie w QGIS,
nakładając budynki BDOT na siatkę H3.

Połączenie QGIS dla testu:
host localhost, port 5444, baza psip, użytkownik psip,
hasło zgodne z ustawieniem środowiska env-test.

Do wizualizacji wykorzystano grid.h3_r8 i pole
ot_bubd_a_area_m2.
