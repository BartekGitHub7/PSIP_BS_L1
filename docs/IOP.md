# IOP v2 — audyt modelu i wizualizacji, 03.11.2026

> Poniżej historyczny stan audytu przed zapisem. Aktualny zapis PostGIS, backupy i rzeczywisty rollback: [wdrożenie](IOP_DEPLOYMENT.md).

Prace wykonano lokalnie na `env-test`. Nie uruchamiano `--write`, nie aktualizowano IOP w PostGIS, nie zmieniano `env-qa` ani `main`, nie wykonano push/merge. Nie wysyłano lokalnych danych GIS do usług zewnętrznych. Dotychczasowe raporty `output/iop/` pozostawiono; nowe wyniki są w `output/iop/audit_20261103/`. Kopia plików sprzed audytu: `backups/iop_audit_20261103_100343/`.

## Co wykazał audyt

| Pytanie | Wniosek i działanie |
|---|---|
| Czy cztery kryteria są zasadne? | Tak jako uproszczony opis pokrycia, przeszkód wodnych, dostępności dróg i zagęszczenia budynków. Nie stanowią pełnego modelu przejazdu konkretnego pojazdu. Zachowano wagi prowadzącego. |
| Czy normalizacja jest poprawna? | Udziały liczymy względem ADJA w m², gęstości długości w km/km². Kryteria i wynik mieszczą się w [-1,1]. Nie każde kryterium musi osiągać oba końce skali. |
| Czy progi są naukowo potwierdzone? | Nie. 20%, 5/10 km/km² i oceny klas są jawnymi hipotezami eksperckimi. Sprawdzono ich wpływ; nie dobierano ich do zielonego koloru. |
| Rowy | Współczynnik 0,25 jest hipotezą, nie pomiarem 25% utraty mobilności. Porównano 0, 0,25, 0,5 i 1. Źródłowa warstwa ma 9092 rowy, szerokości 0,5–4,5 m. Sama agregowana długość nie rozróżnia ich szerokości i miejsc przekroczeń; taka rozpiętość nie uzasadnia uniwersalnego współczynnika. |
| Brak dróg | Neutralne K3=0 jest logiczne dla ruchu także poza drogami: brak infrastruktury nie dowodzi nieprzejezdności. Wariant `bipolar` pozostaje do porównań. Gęstość dróg nie potwierdza ich nośności ani połączenia sieci. |
| Podwójne naliczanie | PTWP/PTZB/PTKM/PTPL neutralne w K1; tylko SKDR w K3, tylko BUBD w K4. Hydrografia używa maksimum, nie sumy kar powierzchniowych i liniowych. Maksimum NIE jest geometryczną deduplikacją: może pomijać dodatkowe rozłączne przeszkody, a suma długości SWRS/SWKN/SWRM też nie jest unią geometrii. |
| Heksagony graniczne | ADJA jest mianownikiem; brakującego obszaru nie traktujemy jako dobrego terenu. Wynik <10% pokrycia oznaczamy w raporcie, na mapie i po kliknięciu; dodatkowo flaga <1%. Nie obniżamy IOP za niepewność, bo jakość danych i utrudnienia to różne informacje. |
| Ujemna skala | K2 i K4 są wyłącznie karami, K3 bonusowy jest nieujemny, K1 ma znaki mieszane. Zero to równowaga przyjętych wkładów, nie fizyczny próg przejezdności. Wynik nie jest prawdopodobieństwem ani procentem. |

Pierwotna walidacja nie sprawdzała `roads_mode` i `ditch_factor`: literówka w trybie wybierała inną punktację, a ujemny współczynnik rowów mógł pomniejszać przeszkody. Dodano odrzucanie takich konfiguracji, nieskończoności, wartości bool w progach/wagach i progów udziałowych >1. Dodano kontrolę ID oraz diagnostykę dominującego składnika hydrografii, nasycenia i wkładów do IOP.

Nie zmieniono kolejny raz punktacji tylko w celu poprawy kolorów. Wariant audytowany zachowuje **dokładnie** wyniki istniejącego eksperymentu (maksymalna różnica 0 na każdej siatce), a dodaje walidację, diagnostykę, analizę wrażliwości i działający podgląd GUI.

## Model i konfiguracja

`app/iop_config.json`: wagi `[1.6,1.2,0.8,0.4]`; ich suma musi wynosić 4. Wzór prowadzącego:

`IOP = (1.6*K1 + 1.2*K2 + 0.8*K3 + 0.4*K4)/4`.

Parametry mają status `expert_hypotheses_not_calibrated`. `--config plik.json` pozwala użyć innego wariantu.

Niech A = `ot_adja_a_area_m2`, a d(L) = `1000*L_m/A_m2` w km/km².

- K1 = suma(powierzchnia_PT * ocena_PT)/A, z ograniczeniem numerycznym do [-1,1]. PTGN (grunt nieużytkowany) −0,2; PTLZ (las i zadrzewienia) −0,8; PTNZ (pozostały teren niezabudowany) −0,5; PTRK (krzewy) −0,6; PTSO (składowisko odpadów) −0,5; PTTR (trawy i uprawy rolne) +0,6; PTUT (uprawa trwała) −0,3; PTWZ (wyrobisko/zwałowisko) −0,7. PTWP, PTZB, PTKM, PTPL: 0, z zachowaniem A jako mianownika. Szeroka klasa PTTR nie rozróżnia twardego podłoża od rozmokłego pola.
- K2 = `-min(1,max(PTWP/A/0.2, OIMK/A/0.2, OISZ/A/0.2, d(SWRS+SWKN+0.25*SWRM)/5))`. Bez przeszkód 0; nasycenie −1. Wody/obszary podmokłe i szuwary mają próg 20%, a ważona gęstość cieków 5 km/km². Współczynnik rowów konfiguruje `ditch_factor`.
- K3 (`roads_mode="bonus"`) = `min(1,d(SKDR)/10)`: brak dróg 0, 5 km/km² daje +0,5, od 10 km/km² +1. Alternatywny `bipolar` daje `2*min(1,d(SKDR)/10)-1`.
- K4 = `-min(1,BUBD/A/0.2)`: bez budynków 0, od 20% −1.

Matematyczny zakres [-1,1] jest wspólną ramą odniesienia. Przy tych ocenach K1 oraz bonusowym K3 luźna obwiednia algebraiczna wynosi około **[-0,72,+0,44]** (przy dokładnej zgodności sumy PT z A); współwystępowanie klas może ją dodatkowo zawęzić. Nie należy rozciągać wyników do ±1. Tolerancja sum PT może wprowadzać niewielkie odchylenia tej pomocniczej obwiedni; twardy zakres walidacji IOP nadal wynosi [-1,1].

Sprawdzane są: dodatnie powierzchnie, skończone nieujemne dane, 68 kolumn ot_*, unikalne ID, SRID 2180 oraz zgodność sumy PT z ADJA z tolerancją max(2 m²,1% A). NULL nie jest zerem. Niepoprawny wiersz otrzymuje pusty IOP i opis błędu; blokuje zapis. Baza ma już ograniczenia `CHECK` dla skończonego IOP w [-1,1] we wszystkich trzech tabelach; zweryfikowano je odczytem.

## Wyniki przed i po

| Siatka | Liczba | Pierwotny v1: zakres | Eksperyment przed audytem = audytowany: zakres | Pokrycie <10% / <1% |
|---|---:|---|---|---:|
| R6 | 63 | −0,487636…+0,079518 | −0,308891…+0,237053 | 7 / 1 |
| R7 | 362 | −0,791335…+0,384666 | −0,591335…+0,409859 | 26 / 7 |
| R8 | 2264 | −0,770449…+0,440000 | −0,578631…+0,440000 | 66 / 19 |

2689 heksagonów, 0 błędnych obliczeń. W R7 125 komórek ma pokrycie <99%; minimum 0,0992%. W R8 minimum wynosi zaledwie 0,000487%. Ekstremalnie małe fragmenty nie reprezentują całego heksagonu. Wszystkie 2689 wartości przejezdnosc w bazie nadal są NULL. Odciski całych tabel przed i po audycie są identyczne (`source_unchanged=true` w raporcie).

## Analiza wrażliwości

`tools/audit_iop.py` porównuje **29 wariantów** na tych samych wejściach: v1, oddzielną zmianę dróg i rowów, audytowany wariant, współczynnik rowów 0/0,5/1, progi ±25%, oceny PTLZ i PTTR ±0,2 oraz każdą wagę ±25% z ponowną normalizacją sumy do 4. Zachowano niezmienione parametry podstawowe. Wagi nie zostały dostrojone do barw.

Przykłady R7 względem wariantu audytowanego:

| Wariant | Średnia bezwzględna zmiana IOP | Zmiany znaku | Spearman |
|---|---:|---:|---:|
| Pierwotny v1 | 0,15827 | 107 | 0,93076 |
| Drogi bipolarne, rowy 0,25 | 0,10977 | 71 | 0,98026 |
| Drogi bonusowe, rowy 1 | 0,04850 | 44 | 0,95902 |
| Rowy 0 | 0,01547 | 13 | 0,98986 |
| Rowy 0,5 | 0,01705 | 17 | 0,99198 |
| Próg dróg 7,5 km/km² | 0,02860 | 23 | 0,99804 |
| Próg cieków 3,75 km/km² | 0,01333 | 10 | 0,99680 |

Zmiana znaku nie oznacza naukowo potwierdzonej zmiany klasy GO/NO GO. Dla R7 średnie wkłady do IOP: K1 −0,00721; K2 −0,05483; K3 +0,09023; K4 −0,00338. Składnik liniowy jest dominujący w hydrografii w 286/362 komórkach; całe K2 jest nasycone w 8. Hydrografia pozostaje istotna po zmniejszeniu roli rowów.

Pliki `h3_rN_sensitivity_envelope.csv` podają min/max i stabilność znaku po wariantach bonusowych, bez porównawczych wariantów bipolarnych. Znak jest niestabilny w R6:19, R7:95, R8:452 komórkach. **To obwiednia założeń z analizy pojedynczych zmian, nie przedział ufności ani kompleksowa kombinacja wszystkich parametrów.**

## Wizualizacja i GUI

Wspólna implementacja kolorów: `gui/iop_display.py`, używana przez GUI i eksport map. Dostępne są dwie stałe skale:

1. **Referencyjna**: liniowo [-1,1], −1 czerwony `#d73027`, 0 biały, +1 zielony `#1a9850`. Domyślna dla porównań.
2. **Kontrastowa**: stały zakres barw [-0,5,+0,5], transformacja pozycji barwy `sign(IOP)*min(1,abs(IOP)/0.5)^0.65`. Zero nadal białe, znaki zachowane; zmienia się wyłącznie barwa. IOP poza tym zakresem jest nasycony, co jawnie opisano w GUI i na mapach. Legenda pokazuje rzeczywiste IOP; w mapach ma znaczniki końców nasycenia. Brak min–max zależnego od mapy.

Kreskowanie oznacza pokrycie poniżej skonfigurowanego progu, ciemne obrysy rozdzielają heksagony, szary oznacza brak IOP. Lokalny kontekst BDOT pokazuje drogi na czarno, cieki na niebiesko. Nie pobiera podkładu internetowego. Kliknięcie pokazuje pełniejszą wartość IOP, pokrycie, źródło oraz cztery kryteria z dry-run. Tabela atrybutów korzysta z tego samego wybranego źródła.

GUI łączy się z bazową tabelą także po wskazaniu wariantów `_2180` i `_3857`. Wszystkie trzy korzystają z tej samej kolumny wynikowej; nie zmieniano widoków. Wyniki dry-run są nakładane lokalnie według h3_id na istniejące kafelki i geometrię PostGIS. Wczytanie weryfikuje zakresy, liczbę/unikalność ID, zgodność IOP z kryteriami i wagami oraz odcisk danych bazowych. Brakujący rekord podglądu nie powoduje cichego pobrania starego wyniku z bazy. Ponowne połączenie z bazą usuwa lokalny podgląd. Zmiana skali lub źródła odrzuca spóźnione kafelki starego stylu. Panel boczny jest przewijany, żeby kontrolki były dostępne także w mniejszych oknach.

### Demonstracja

Z katalogu repozytorium:

```powershell
.\.venv-gui\Scripts\python.exe gui/main.py
```

Połącz z lokalnym env-test (localhost:5444), wybierz R6/R7/R8, kliknij **Wczytaj wyniki dry-run…** i wskaż `output/iop/audit_20261103`. Włącz skalę kontrastową i opcjonalne tło lokalne. Kliknij komórkę kreskowaną i zwykłą. Przycisk **Pokaż wyniki z PostGIS** wraca do rzeczywistych wartości bazy (obecnie NULL).

Nowe mapy: `preview_r6_reference.png` / `preview_r6_contrast.png`, odpowiednio R7 i R8, a także `preview_r7_context.png`. CSV, porównania i `sensitivity_r7.png` są w tym samym katalogu.

## Odtworzenie obliczeń i testy

```powershell
.\.venv-gui\Scripts\python.exe tools/audit_iop.py
.\.venv-gui\Scripts\python.exe -m unittest discover -s app -v
.\.venv-gui\Scripts\python.exe -m unittest discover -s gui -v
.\.venv-gui\Scripts\python.exe tools/verify_iop_gui.py
.\.venv-gui\Scripts\python.exe gui/main.py --smoke-test
```

Sam audyt zapisuje tylko lokalne artefakty. Przechowuje wejścia i geometrie z odczytu repeatable-read/read-only w `h3_rN_inputs.json`, konfiguracje wariantów, źródłowe odciski i datę UTC w report.json. `sensitivity.csv` zawiera min/kwantyle/średnią, zmiany IOP, znaki i korelacje rang. Powtórzenie nadpisuje wyłącznie pliki wygenerowane w katalogu nowego audytu; `--output` pozwala wybrać inny katalog.

Minimalny dry-run samego algorytmu, z osobnym katalogiem:

```powershell
.\.venv-gui\Scripts\python.exe app/iop.py --dry-run --output output/iop/check_v2
```

Wymagania: Python i istniejące zależności z `gui/requirements.txt`, Git oraz działający Docker Desktop z kontenerem `remote-db-env-test-postgis-1`. Algorytm CLI wymaga tylko standardowej biblioteki Pythona i Docker CLI. Weryfikacja GUI korzysta z lokalnego portu 5444, pobiera hasło kontenera wyłącznie do pamięci i go nie drukuje. Odczyt ma wymuszony tryb read-only.

Wynik: **17/17 testów algorytmu i bezpieczeństwa dry-run; 10/10 testów wizualizacji/CSV; integracja wszystkich trzech rozdzielczości i rzeczywistych kontrolek Tk; smoke-test okna — OK.** Sprawdzono rzeczywiste MVT, zgodność odczytu po kliknięciu z CSV, ostrzeżenie pokrycia, lokalny kontekst BDOT, przełączanie źródła, legendy i odrzucanie starych kafelków. Funkcję kliknięcia wywoływano programowo, bez fizycznego ruchu myszy. Nowej paczki EXE nie budowano; starsze EXE nie zawiera tych zmian.

## Podstawa naukowa i ograniczenia

Pokonieczny (2018), [Comparison of land passability maps created with use of different spatial data bases](https://geografie.cz/123/3/0317/), DOI 10.37040/geografie2018123030317: porównanie m.in. BDOT10k, różnych wielkości pól i mapy opracowanej przez operatora uzasadnia użycie danych cywilnych oraz konieczność niezależnej walidacji. Nie potwierdza naszych współczynników ani progów.

Dawid i Pokonieczny (2021), [Methodology of Using Terrain Passability Maps for Planning the Movement of Troops and Navigation of Unmanned Ground Vehicles](https://www.mdpi.com/1424-8220/21/14/4682), DOI 10.3390/s21144682: osobnym etapem wykorzystania map jest graf i wyznaczanie trasy. Obecny indeks zagregowanej komórki nie analizuje takiej łączności. Wykorzystano informację z abstraktu; pełnej treści tej publikacji nie udało się pobrać z witryny wydawcy podczas audytu.

Znaczenie klas sprawdzono w [Vademecum użytkownika BDOT10k, wydanie 2024, WODGiK](https://wodgik.lubuskie.pl/uploads/VADEMECUM_UZYTKOWNIKA_BDOT10k_2024.pdf). Klasy pokrycia są szerokie i nie oznaczają automatycznie konkretnej odporności na ruch pojazdu.

Brak określonego pojazdu, masy, nacisku, NMT/nachylenia, pogody i terenowej próby przejazdu ogranicza interpretację. Agregat nie zna położenia przeszkody wewnątrz heksagonu, mostów i możliwego obejścia; indeks jest kompensacyjny, więc droga może matematycznie równoważyć część kary za wodę. Mniejsze heksagony dają inne wyniki wskutek rozdzielczości i nieliniowego nasycenia; wyniku rodzica nie należy utożsamiać ze średnią potomków. Niskie pokrycie jest osobnym źródłem niepewności.

**Gotowość:** rozwiązanie jest gotowe do demonstracji i oceny wariantów w dry-run. Dane i zakresy są technicznie zgodne z kolumną PostGIS, ale nie potwierdzono empirycznej trafności modelu. Nie uruchamiano ścieżki trwałego zapisu ani praktycznego rollbacku, więc nie jest ona w tym audycie w pełni zweryfikowana. Zachowany `--write` ma kopie poprzedniej kolumny i SQL odtworzenia, lecz jego wykonanie pozostaje poza zakresem tej sesji.
