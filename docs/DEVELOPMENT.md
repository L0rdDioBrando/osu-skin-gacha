# Как разрабатывать 

Соблюдать единую иерархию структуры проекта.

## Архитектура проекта
- main.py - все импорты.
- modules/ - весь код программы.
- assets/ - ресурсы.
- oauth_worker/ - настройки входа через osu! аккаунт.

## Сборка

На Linux (требуется python 3.12+, gnumake и Tkinter):
```bash
make install
```

На Windows (нужен python 3.12+):

Соберите программу:
```powershell
python -m pip install uv
uv sync
uv run pyinstaller --windowed --add-data "assets;assets" --onefile --name osu-gacha --collect-all customtkinter --collect-all pygame --collect-all rosu_pp_py --collect-all mutagen main.py
```

## Запуск

Linux:
```bash
./dist/skin-gacha
```

Windows:
```powershell
.\dist\skin-gacha
```

## Структура (может устаревать/быть не точной)

```
.
├── assets
│   ├── __init__.py
│   ├── drive_catalog.json
│   ├── gacha-logo.png
│   └── gacha.ico
├── docs
│   ├── ARCHITECTURE.md
│   ├── DEVELOPMENT.md
│   ├── HOW_TO_RUN.txt
│   └── LINUX.md
├── ensure_python.ps1
├── flake.lock
├── flake.nix
├── main.py
├── Makefile
├── modules
│   ├── __init__.py
│   ├── __pycache__
│   │   ├── gacha_api.cpython-313.pyc
│   │   ├── gacha_app.cpython-313.pyc
│   │   ├── gacha_config.cpython-313.pyc
│   │   ├── gacha_connection.cpython-313.pyc
│   │   ├── gacha_insights.cpython-313.pyc
│   │   ├── gacha_previews.cpython-313.pyc
│   │   ├── gacha_reports.cpython-313.pyc
│   │   ├── gacha_rules.cpython-313.pyc
│   │   ├── gacha_settings.cpython-313.pyc
│   │   ├── gacha_setup.cpython-313.pyc
│   │   ├── gacha_skin_apply.cpython-313.pyc
│   │   ├── gacha_skins.cpython-313.pyc
│   │   ├── gacha_sources.cpython-313.pyc
│   │   ├── gacha_storage.cpython-313.pyc
│   │   ├── gacha_updates.cpython-313.pyc
│   │   ├── gacha_widgets.cpython-313.pyc
│   │   └── skin_gacha.cpython-313.pyc
│   ├── gacha_api.py
│   ├── gacha_api_v2.py
│   ├── gacha_app.py
│   ├── gacha_audio.py
│   ├── gacha_bootstrap.py
│   ├── gacha_collection.py
│   ├── gacha_config.py
│   ├── gacha_connection.py
│   ├── gacha_driver.py
│   ├── gacha_insights.py
│   ├── gacha_oauth.py
│   ├── gacha_polish.py
│   ├── gacha_previews.py
│   ├── gacha_python_probe.py
│   ├── gacha_reports.py
│   ├── gacha_rules.py
│   ├── gacha_settings.py
│   ├── gacha_setup.py
│   ├── gacha_skin_apply.py
│   ├── gacha_skin_stats.py
│   ├── gacha_skin_variants.py
│   ├── gacha_skins.py
│   ├── gacha_sources.py
│   ├── gacha_storage.py
│   ├── gacha_team.py
│   ├── gacha_transfer.py
│   ├── gacha_updates.py
│   ├── gacha_widgets.py
│   ├── music_library.py
│   └── skin_gacha.py
├── OAUTH_SETUP.md
├── oauth_worker
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── pnpm-workspace.yaml
│   ├── README.md
│   ├── src
│   │   └── worker.js
│   ├── test
│   │   └── worker.test.mjs
│   └── wrangler.jsonc
├── pyproject.toml
├── README.md
├── shell.nix
└── uv.lock
```
