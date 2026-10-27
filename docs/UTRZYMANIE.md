# Uruchamianie, kontrola i zapis stanu

Komendy poniżej zakładają Windows PowerShell, katalog projektu oraz już przygotowane dane. Nie są poleceniem ponownego importowania istniejącej analizy.

## 1. Powrót do pracy

```powershell
Set-Location 'E:\7 semestr\psip\laby\PSIP_BS_L1'
git branch --show-current
git status --short
docker ps -a --filter "label=com.docker.compose.service=postgis"
```

Pracę GUI prowadzimy na lokalnym feature/gui-tkinter. Jeżeli branch istnieje, przełącz się:

```powershell
git switch feature/gui-tkinter
```

Jeżeli branch nie istnieje, najpierw sprawdź git status i zachowaj zmiany. Nowy branch można utworzyć z właściwej lokalnej wersji env-test. Nie przełączaj ani nie resetuj w ciemno drzewa z niezapisanymi zmianami.

Gdy kontener TEST istnieje, ale jest zatrzymany:

```powershell
docker start remote-db-env-test-postgis-1
docker exec remote-db-env-test-postgis-1 pg_isready
```

Jeśli kontenera nie ma, samo docker start go nie utworzy. Skorzystaj z istniejącego Start Remote Database dla env-test; brak wolumenu oznacza konieczność odtworzenia danych z backupu lub świadomego importu.

Uruchom GUI:

```powershell
.\.venv-gui\Scripts\python.exe .\gui\main.py
```

## 2. Kontrola bazy bez przeliczania

Gotowy skrypt tylko do odczytu jest w tools/check_test.sql:

```powershell
Get-Content -Raw .\tools\check_test.sql | docker exec -i remote-db-env-test-postgis-1 psql -U psip -d psip -v ON_ERROR_STOP=1
```

Sprawdza granicę, liczbę warstw BDOT, SRID, liczbę kolumn agregacji, indeksy i obecność pola przejezdnosc. Nie dodaje kolumn, nie importuje i nie liczy modelu. Brak któregoś obiektu może zatrzymać skrypt i wskazuje, który etap trzeba sprawdzić.

Po pierwszym dodaniu pola przejezdnosc można osobno sprawdzić liczbę gotowych wyników:

```powershell
docker exec remote-db-env-test-postgis-1 psql -U psip -d psip -c "SELECT count(*) AS komorki, count(przejezdnosc) AS z_wynikiem FROM grid.h3_r8;"
```

Z_wynikiem = 0 jest poprawne przed wdrożeniem modelu.

## 3. Pierwsze dodanie pola przejezdności

Tylko jeżeli migracji jeszcze nie wykonano:

```powershell
Get-Content -Raw .\gui\add_passability.sql | docker exec -i remote-db-env-test-postgis-1 psql -U psip -d psip -v ON_ERROR_STOP=1
```

Nie wypełnia pola sztucznymi wynikami. Ograniczenie 0–1 odpowiada bieżącej technicznej wersji GUI; nie jest jeszcze ograniczeniem wyłącznie do dwóch klas.

## 4. Zapis w Git

Aktualny kod GUI, skrypty SQL, .gitignore i tę dokumentację zapisano na GitHubie na **feature/gui-tkinter**. env-test, env-qa i main nie zostały zmienione. Główny README zachowuje treść laboratorium 1 oraz zawiera link do docs/README.md.

Git zapisuje kod i dokumentację. **Nie zapisuje zawartości wolumenu PostgreSQL.** Nie zna również zmian, które istnieją tylko na dysku użytkownika i nie zostały przekazane do tej sesji.

### Synchronizacja istniejącej lokalnej kopii

Najpierw wyłącznie odczyt:

```powershell
git fetch origin
git branch --show-current
git status --short
git log --oneline --left-right HEAD...origin/feature/gui-tkinter
```

Jeśli jesteś na lokalnym feature/gui-tkinter, drzewo jest czyste i lokalna historia jest przodkiem zdalnego brancha, można wykonać:

```powershell
git merge --ff-only origin/feature/gui-tkinter
```

Jeśli są lokalne zmiany, nieśledzone pliki gui lub rozbieżne commity, nie wykonuj reset --hard ani clean. Zachowaj pliki i rozstrzygnij różnice przed scaleniem. Nie nadpisuj działającej wersji w ciemno. Sam git fetch nie zmienia plików roboczych i jest właściwym pierwszym krokiem.

### Zapisywanie kolejnych zmian po synchronizacji

```powershell
git status --short
git add docs tools gui/main.py gui/requirements.txt gui/add_passability.sql gui/ensure_spatial_indexes.sql .gitignore README.md
git diff --cached --stat
git diff --cached
git commit -m "Update PSIP viewer and project documentation"
git push -u origin feature/gui-tkinter
```

Polecenia commit/push służą przyszłym zmianom; nie trzeba ponownie wysyłać już zapisanego stanu. Sprawdź diff i nie dodawaj haseł ani kopii bazy. W .gitignore zapisano .venv-gui/, __pycache__/, *.pyc, backups/ i gui/main_before_*.py, zachowując wcześniejsze wpisy.

Push na feature/gui-tkinter nie uruchamia obecnego start_services.yml, który obserwuje tylko env-test, env-qa i main. Nie wykonano automatycznego merge do tych środowisk.

## 5. Osobna kopia bazy

Aby zachować agregacje i późniejsze wyniki przejezdności, wykonaj backup env-test. Dołączony skrypt używa pg_dump -Fc w kontenerze, potem docker cp. Nie używa przekierowania binarnego przez PowerShell.

```powershell
& .\tools\backup_test.ps1
```

Powstanie plik backups/env-test_YYYYMMDD_HHMMSS.dump oraz plik SHA-256. Backup może zawierać dane całego opracowania; nie dodajemy go do repo. Skrypt sprawdza czytelność archiwum poleceniem pg_restore --list. To kontrola struktury archiwum, nie pełny test odtworzenia.

Dla faktycznej ochrony przed utratą dysku skopiuj ten plik również do niezależnego miejsca. Pełne odtworzenie należy testować w osobnej, pustej bazie, nie przez nadpisywanie działającego TEST. Backup nie zastępuje zewnętrznych plików źródłowych BDOT ani kodu w Git.

## 6. Czego nie uruchamiać rutynowo

- app/load.py: zastępuje tabele siatek i może utracić kolumny wynikowe lub napotkać zależne widoki.
- app/python/load_bdot.py: zastępuje tabele BDOT.
- aggregate_bdot.sql: ponownie wykonuje kosztowne obliczenia; nie jest wymagany do otwarcia GUI.
- Destroy Remote Database lub docker compose down -v: usuwa dane wolumenu.

## 7. Najczęstsze sytuacje

| Objaw | Co sprawdzić |
|---|---|
| Connection refused | Docker Desktop, istnienie i stan TEST, port 5444. |
| Błąd hasła | Hasło Environment env-test; nie zakładaj, że jest takie samo jak w QA. |
| Brak h3 lub BDOT na liście | Właściwy port/baza oraz import danych do tego środowiska. |
| Szare komórki | NULL przejezdności jest teraz oczekiwany. Sprawdź obecność kolumny i liczbę wyników. |
| Dane w tabeli zmienione, mapa stara | Poczekaj na żądania i kliknij Odśwież kafelki. |
| Lagi przy całym powiecie | Ogranicz widoczne warstwy, przybliż, sprawdź indeksy i aktualne zadania bazy. |
| Dawne agregacje wszędzie zero | Sprawdź, czy granica PRG i BDOT dotyczą tego samego powiatu oraz ich zasięgi. |
| Brak gałęzi GUI na GitHubie | Lokalne pliki mogły nie zostać zacommitowane i wypchnięte. |

Nie rozwiązuj tych objawów przez kasowanie wolumenu. Najpierw ustal przyczynę.
