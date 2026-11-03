# Wdrożenie IOP v2 — 03.11.2026

## Środowiska i dane

PostGIS działa na komputerze użytkownika w Docker Desktop (`desktop-linux`).
To nie jest niezależny zdalny serwer. Użytkownik zaakceptował te kontenery jako cel.
Test: `remote-db-env-test-postgis-1`, localhost:5444, osobny wolumin `remote-db-env-test_pgdata`.
QA: `remote-db-env-qa-postgis-1`, localhost:5445, osobny wolumin `remote-db-env-qa_pgdata`.
GitHub przechowuje kod; push nie przenosi danych PostGIS.
Nie wykonywano operacji na bazie prod ani gałęzi main.

## Zakończone na test

- Pełna kopia bazy: `backups/env-test_20261103_103146.dump`, 79 782 633 bajtów.
  SHA256: `DF654FB12ECB8AE57C5C99EF7CBC82E27C73A45C9029D7C1FEAC0B8858C5E4AA`.
- Odtworzenie całej kopii w osobnej bazie `iop_rehearsal_20261103`.
- Rzeczywisty `--write`, odczyt wszystkich 2689 wartości, GUI/MVT bez podglądu CSV.
- Wykonanie wygenerowanego rollback SQL; odciski całych trzech tabel identyczne ze stanem przed zapisem.
- Zapis do właściwego `psip` na test. R6:63, R7:362, R8:2264; 0 błędów.
- Porównanie z audytowanymi CSV: maksymalna różnica 0. Odczyt GUI po kliknięciu,
  kafelki MVT i aliasy 2180/3857 poprawne dla wszystkich trzech rozdzielczości.
- 17 testów algorytmu, 10 GUI/CSV, integracja rzeczywistych kontrolek Tk oraz smoke-test poprawne.
- Backup poprzednich wartości w `grid.iop_backup_*`; SQL rollback i raport w
  `output/iop/deploy_test_20261103/`. Dane wejściowe i pliki wynikowe pozostają lokalne.

## QA i odtwarzanie

QA początkowo nie ma 68 kolumn agregatów ani przejezdnosc. Pełny backup przed
migracją: `backups/env-qa_before_iop_20261103.dump`, 357 980 bajtów,
SHA256 `B5413DD0BE809E09E0AF43DD9CFFEF292BFD8A2AAB87F4C1D9D1467443698AC4`.
Kopię odtworzono w osobnej bazie QA `iop_rehearsal_20261103`.
Próba migracji 68 agregatów zakończona poprawnie: geometrie i ID wszystkich
2689 komórek są identyczne między test i QA. Migracja zachowuje istniejące pola
oraz geometrie; blokuje nadpisanie różnych istniejących agregatów.

Po scaleniu kodu na env-qa wykonuje się kolejno (z katalogu repo, Python z zależnościami GUI):

```powershell
python tools/promote_iop_inputs.py                   # próba zakończona rollbackiem
python tools/promote_iop_inputs.py --write           # osobny backup wymagany przed zapisem
python app/iop.py --environment env-qa --write --output output/iop/deploy_qa_20261103
python tools/verify_iop_database.py --environment env-qa
```

Domyślny algorytm nadal nic nie zapisuje. Wymagana jest gałąź zgodna z wybranym
środowiskiem, dozwolone są wyłącznie test i QA. `--database iop_rehearsal_20261103`
umożliwia powtórzenie próby na klonie. Backupy, surowe dane i output są ignorowane
przez Git. Odtworzenie wyników wymaga danych PostGIS albo lokalnych danych audytu;
repo samo nie zawiera pełnego zbioru GIS. Historyczna `INSTRUKCJA.txt` dotyczy starego
GUI i skali 0–1, dlatego nie została dołączona do wdrożenia.

QA otrzymuje agregaty potrzebne do obliczeń, bez surowego schematu BDOT.
Opcjonalne tło dróg i cieków wymaga osobnego importu BDOT do QA.
Stary podgląd dry-run ma odcisk sprzed zapisu i zostanie poprawnie odrzucony przez GUI;
nowy podgląd tworzy `app/iop.py --dry-run --output NOWY_KATALOG`.

## Wynik wdrożenia QA

Właściwe QA `psip` otrzymało agregaty po kontroli identyczności ID/geometrii,
próbie transakcyjnej z rollbackiem i próbie pełnego zapisu na odtworzonym klonie.
Następnie wykonano niezależne obliczenie i `--write` na QA: 63/362/2264 wyniki,
0 błędów, maksymalna różnica względem audytu 0. Sprawdzono wszystkie rekordy,
kafelki MVT, odczyt po kliknięciu GUI bez CSV i trzy warianty nazw warstw.
17+10 testów i smoke-test QA poprawne. Kopie poprzednich wartości są w
`grid.iop_backup_*`, a rollback/raport w lokalnym `output/iop/deploy_qa_20261103/`.
Kod scalono z env-test z zachowaniem istniejących commitów QA.
