# Linux preview: сборка и проверка

## Получить AppImage через GitHub (Windows менять не нужно)

1. В GitHub Desktop сохраните изменения: Summary → Commit → Push origin.
2. Откройте репозиторий на GitHub → **Actions**.
3. Слева выберите **Linux AppImage** → **Run workflow** → ветка `main` → зелёная **Run workflow**.
4. Откройте появившийся запуск. Дождитесь зелёной отметки. Красная означает ошибку сборки, а не готовый выпуск; откройте красный шаг и сохраните его журнал.
5. Внизу страницы запуска, в **Artifacts**, скачайте `osu-gacha-linux-x86_64-preview` (нужен вход в GitHub).
6. Распакуйте ZIP и передайте Дену `.AppImage` вместе с `.sha256`.

Эта задача ничего не публикует в Releases. Она собирает исходники выбранной ветки на Ubuntu 22.04 x86_64, проверяет настоящее хранилище Secret Service с одноразовыми тестовыми данными, затем проверяет запуск упакованной программы через Xvfb. После успешной ручной проверки можно прикрепить AppImage к соответствующему выпуску; укажите commit сборки, не смешивайте её с исходниками старого тега.

## Запуск для тестировщика

Требуются графический сеанс, `xdg-open` и работающий Secret Service (GNOME Keyring либо совместимое хранилище, предоставляющее `org.freedesktop.secrets`). На KDE наличие KWallet само по себе не гарантирует включённый Secret Service. Если вход не сохраняется, включите/разблокируйте это хранилище. Программа не использует открытый файл вместо защищённого хранилища.

```sh
chmod +x osu-gacha-v0.5.0-linux-preview-x86_64.AppImage
./osu-gacha-v0.5.0-linux-preview-x86_64.AppImage
```

Если недоступен FUSE:

```sh
APPIMAGE_EXTRACT_AND_RUN=1 ./osu-gacha-v0.5.0-linux-preview-x86_64.AppImage
```

osu!stable запускается через `wine`, найденный в PATH. Для отдельного префикса запустите AppImage с нужным `WINEPREFIX`; автоматически угадывать префикс Lutris/Bottles программа не пытается. Можно оставить автозапуск osu! выключенным и запустить игру привычным способом. Папка osu! должна содержать `osu!.exe` и `Skins`.

Драйвер планшета: выберите Linux-программу с правом исполнения или `.exe` для Wine. Автоматическое сворачивание драйвера остаётся функцией Windows.

После смены скина нажмите Ctrl+Shift+Alt+S в osu!, затем **«Скин обновлён»** в osu!gacha **до следующего скора**. Это начинает запись статистики нового скина. Глобальное определение сочетания клавиш в чужом окне на Linux не реализовано (особенно ограничено на Wayland).

## Локальная сборка на Linux

Python 3.12+, Tcl/Tk, PyInstaller, `desktop-file-validate`, squashfs-tools и официальный appimagetool x86_64. Установите зависимости `requirements.txt`, затем:

```sh
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --onedir --windowed --name osu-gacha --collect-all customtkinter --collect-all pygame --collect-all rosu_pp_py --collect-all mutagen --add-data "assets:assets" main.py 
```

Результат в `dist/`. Команды установки для чистой Ubuntu приведены в `.github/workflows/linux-appimage.yml`. AppImage предназначен для Linux x86_64 с glibc не старее окружения сборки (Ubuntu 22.04); ARM и старые дистрибутивы требуют отдельной сборки.

На машине разработки Windows Linux-сборка не выполнялась. Успешные Windows-тесты не являются проверкой настоящего D-Bus, Secret Service, Wine или AppImage; такую проверку выполняют GitHub Actions и тестировщик.
