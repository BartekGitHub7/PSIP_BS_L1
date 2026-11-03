# Aplikacja Windows — pobranie, dwuklik i budowanie

## Najprościej: gotowa paczka z GitHub Actions

1. Uruchom Docker Desktop i sprawdź, że baza TEST działa na porcie 5444.
2. Otwórz [udany build Windows](https://github.com/BartekGitHub7/PSIP_BS_L1/actions/runs/40493262781).
3. W sekcji Artifacts kliknij **PSIP_Mapa_Windows**. Pobieranie wymaga zalogowania w GitHub.
4. Rozpakuj ZIP do osobnego katalogu, np. PSIP_Mapa. Nie uruchamiaj EXE wewnątrz ZIP.
5. Uruchom **PSIP_Mapa.exe** dwuklikiem.
6. Kliknij ＋ Dodaj dane, połącz się z localhost:5444 i dodaj siatkę.

**Zachowaj folder _internal obok EXE.** Paczka zawiera interpreter i potrzebne biblioteki. Na komputerze odbiorcy nie jest wymagany osobno Python, ale PostGIS musi być osiągalny. EXE nie uruchamia Dockera, nie instaluje bazy i nie tworzy przejezdności.

Artifacts są przechowywane przez 14 dni. Po tym czasie aplikację można ponownie zbudować ze źródła. Kolejne zmiany gui na feature/gui-tkinter uruchamiają nowy build. Wybieraj ostatni udany run dla właściwej wersji kodu, nie zawsze historyczny link powyżej. Istniejący run można ponowić przez Re-run jobs. Ręczne workflow_dispatch w interfejsie zależy od obecności workflow na domyślnym branchu.

## Start w katalogu źródłowym

Plik **Uruchom_PSIP.cmd** wybiera w kolejności:

1. dist/PSIP_Mapa/PSIP_Mapa.exe;
2. dist/PSIP_Mapa.exe;
3. lokalny interpreter pythonw z .venv-gui;
4. lokalny interpreter pythonw z .venv-build.

Pythonw uruchamia okno bez konsoli. Jeśli niczego nie ma, skrypt podaje informację o potrzebie budowania. Launcher nie aktualizuje automatycznie starszego EXE po zmianie main.py — wtedy trzeba ponowić build.

## Samodzielne budowanie dwuklikiem

Wymagany Python dla Windows z Tkinter i Python Launcher (zalecany 3.12) oraz internet do pobrania zależności. Nie trzeba podawać hasła do bazy.

1. Pobierz kod z brancha feature/gui-tkinter przez Code → Download ZIP lub pobierz go Gitem.
2. Rozpakuj do osobnego katalogu, jeśli Twoja bieżąca kopia ma niezapisane zmiany.
3. Kliknij **Zbuduj_EXE.cmd**.
4. Po komunikacie powodzenia plik będzie w **dist/PSIP_Mapa/PSIP_Mapa.exe**.
5. Możesz użyć Uruchom_PSIP.cmd albo dwukliku na wynikowym EXE.

Skrypt tworzy .venv-build i instaluje wymagania. Krótko otwiera i zamyka okno podczas testu źródła i gotowego EXE — to oczekiwane zachowanie. Po błędzie pozostawia komunikaty do odczytu. Domyślny folder z bibliotekami jest szybszy do uruchamiania i łatwiejszy do sprawdzania niż wariant pojedynczego pliku.

To samo z PowerShell w katalogu repo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\gui\build_windows.ps1
```

Bypass dotyczy tego procesu PowerShell, nie zmienia trwałej polityki systemu.

## Opcjonalnie: pojedynczy plik EXE

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\gui\build_windows.ps1 -OneFile
```

Wynik: **dist/PSIP_Mapa.exe**. Wariant ten rozpakowuje biblioteki przy starcie i może uruchamiać się dłużej. Domyślna paczka z Actions jest wariantem folderowym. Nie deklarujemy, że wariant OneFile został osobno przetestowany w bieżącym buildzie.

## Co sprawdza build

- Instalację zależności w odrębnym środowisku.
- Uruchomienie okna Tkinter z kodu przez --smoke-test.
- Wytworzenie ikony oraz pakowanie PyInstaller.
- Uruchomienie gotowego EXE przez --smoke-test i kod zakończenia.
- Zapis paczki jako artifact i listy wersji bibliotek build-dependencies.txt.

Build nie wymaga sekretów ani połączenia z bazą. Nie jest pełnym testem mapy na rzeczywistych danych. Binaria, build i .venv-build są ignorowane przez Git; repo zawiera kod i instrukcje odtworzenia aplikacji.
