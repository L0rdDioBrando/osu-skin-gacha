# Локальная сборка на Linux

Python 3.12+, Tcl/Tk, `desktop-file-validate`, squashfs-tools и официальный appimagetool x86_64. Установите зависимости `requirements.txt`, затем:

```bash
python -m pip install uv && uv sync
python -m PyInstaller --noconfirm --onedir --windowed --name osu-gacha --collect-all customtkinter --collect-all pygame --collect-all rosu_pp_py --collect-all mutagen --add-data "assets:assets" main.py 
```

Результат в `dist/`. Команды установки для чистой Ubuntu приведены в `.github/workflows/linux-appimage.yml`. AppImage предназначен для Linux x86_64 с glibc не старее окружения сборки (Ubuntu 22.04); ARM и старые дистрибутивы требуют отдельной сборки.

На машине разработки Windows Linux-сборка не выполнялась. Успешные Windows-тесты не являются проверкой настоящего D-Bus, Secret Service, Wine или AppImage; такую проверку выполняют GitHub Actions и тестировщик.
