# osu!gacha v0.5.0 · Connected

Играй в osu!stable, получай скины за результаты и сравнивай игру с разными скинами.

## Windows: запуск

1. Скачайте Windows ZIP из https://github.com/DimEdrol-prog/osu-skin-gacha/releases.
2. Распакуйте **весь** архив и откройте `osu!gacha.exe`. Python устанавливать не нужно; `_internal` должен оставаться рядом с exe.
3. Выберите Bancho → «Войти через osu!» → подтвердите вход на официальном сайте. Ручной API-ключ не нужен.
4. Для Gatari укажите ID Gatari; также доступен офлайн-режим.

Исходники запускаются через `run_skin_gacha.cmd` или `python main.py` после установки `requirements.txt`.

## Разработка и сборка

Рабочая копия — этот репозиторий. Код находится в `modules/`, ресурсы и каталог Drive — в `assets/`.

```sh
python -m pip install -r requirements.txt
python main.py
python run_tests.py
```

Тесты интерфейса требуют графическую сессию; наборы запускаются отдельно, чтобы не делить глобальное состояние Tk и аудио. Они используют тестовые данные.

Windows-сборка:

```sh
python -m pip install pyinstaller
python build_windows.py
```

Результат: `.dist/osu!gacha/` и `osu!gacha_v0.5.0_windows.zip`.
Архив исходников: `python build_release.py`.
Тесты Worker: `node --test oauth_worker/test/worker.test.mjs` (современный Node.js).

## Linux / NixOS

Сохранены Makefile, shell.nix, flake.nix и flake.lock, подготовленные участниками проекта.
`uv.lock` обновлён под зависимости v0.5.0. Python: 3.12 или новее.

```sh
nix develop
python main.py
# либо сборка Nix:
nix build
# обычная Linux-сборка в окружении с Python и Tcl/Tk:
make install
```

`make install` устанавливает Python-зависимости и создаёт onedir-сборку в `dist/`; AppImage он не создаёт.
**Ограничение v0.5.0:** защищённое сохранение OAuth-сессии пока использует Windows DPAPI. Полноценный Bancho-вход на Linux требует отдельной доработки. Linux/Nix-сборку после объединения нужно проверить на Linux; наличие файлов сборки не означает, что такая проверка уже пройдена.
На Linux пользовательские данные пишутся в `$XDG_DATA_HOME/osu-gacha` (обычно `~/.local/share/osu-gacha`), а не в read-only Nix store. Переменная `OSU_GACHA_DATA_DIR` позволяет явно выбрать каталог данных на любой системе.

## Обновление и данные

Закройте приложение перед заменой сборки. Сохраните настройки, историю, коллекцию и скины; публичные архивы их не содержат. Сохранённый вход привязан к учётной записи Windows — на другом компьютере войдите заново.

Клонирование репозитория не переносит личную историю из предыдущей папки автоматически. Для переноса используйте экспорт/импорт данных приложения. Старую рабочую папку не удаляйте до проверки переноса.

В Git не отправляются личные настройки, `.oauth-session`, история, логи, кэши, окружения и архивы. Публикуйте бинарные сборки в Releases после публикации соответствующих исходников.

## Авторизация

Bancho работает через API v2 и общий Worker с SkillPush. Каждая авторизация создаёт независимую сессию. Client Secret и токены osu! остаются на Worker; desktop хранит только собственную сессию. Исходники сервера и тесты находятся в `oauth_worker/`, инструкция — `OAUTH_SETUP.md`. Для объединения кода переустанавливать или заново публиковать Worker не нужно.

## English

Download the Windows ZIP from Releases, extract it completely and run `osu!gacha.exe`. Keep `_internal` beside the executable. Choose Bancho and sign in through the official osu! website; no Legacy API key is required. Gatari uses its own user ID; offline mode is retained.

For source development install `requirements.txt`, run `python main.py`, then `python run_tests.py`. Build Windows releases with `python build_windows.py` after installing PyInstaller. Nix and Makefile workflows are retained, but Linux validation is pending and persistent Bancho OAuth currently requires Windows DPAPI. Do not publish an old Linux build as v0.5.0.

Keep personal data when upgrading. Use application export/import when moving from an older working folder. Secrets, sessions, histories and caches must never be committed. See `docs/DEVELOPMENT.md` for the merged layout and release checks.
