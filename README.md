# osu!gacha v0.5.0 · Connected

Играй в osu!stable, получай скины за результаты и сравнивай игру с разными скинами.

## Windows

- Скачайте Windows ZIP из [Releases](https://github.com/DimEdrol-prog/osu-skin-gacha/releases).
- Распакуйте весь архив и откройте `osu!gacha.exe`. Python устанавливать не нужно. Папка `_internal` должна оставаться рядом с exe.
- Выберите Bancho → «Войти через osu!» → подтвердите вход на официальном сайте. API-ключ и ручной Bancho ID не нужны.

Для Gatari используется ID Gatari; также доступен офлайн-режим.

## Linux

Скачайте `.AppImage` из [Releases](https://github.com/DimEdrol-prog/osu-skin-gacha/releases), разрешите запуск файла в его свойствах и откройте его.

Если удобнее через терминал:

```bash
chmod +x osu-gacha-v0.5.0-linux-preview-x86_64.AppImage
./osu-gacha-v0.5.0-linux-preview-x86_64.AppImage
```

Для сохранения входа нужно разблокированное системное хранилище паролей с поддержкой Secret Service. osu!stable работает через Wine; можно запускать игру отдельно привычным способом. После смены скина нажмите Ctrl+Shift+Alt+S в игре, затем «Скин обновлён» в программе перед следующим скором.

## NixOS

Добавьте в свой /etc/nixos/flake.nix:

```nix
{
  inputs = {
    skin-gacha.url = "github:DimEdrol-prog/osu-skin-gacha";
  };
  # Остальной flake.nix
}
```

Добавьте в environment.systemPackages = with pkgs; или home.packages = with pkgs;:

```nix
inputs.skin-gacha.packages.${pkgs.stdenv.hostPlatform.system}.default
```

## Обновление и данные

Перед обновлением закройте приложение и сохраните настройки, историю, коллекцию и скины. Не удаляйте старую рабочую папку до проверки переноса. Для переноса между компьютерами используйте экспорт/импорт данных и войдите в аккаунт заново.

В Windows данные обычно находятся рядом с программой, в Linux — в `$XDG_DATA_HOME/osu-gacha` (обычно `~/.local/share/osu-gacha`). Авторизация хранится отдельно: Windows DPAPI или системное хранилище Linux. Секрет приложения и токены osu! остаются на сервере.

## Разработчикам

Исходники: `modules/`; ресурсы: `assets/`; проверки: `tests/`; сервер авторизации: `oauth_worker/`.

[Разработка и сборка](docs/DEVELOPMENT.md) · [Сборка AppImage и проверка Linux](docs/LINUX.md) · [OAuth](OAUTH_SETUP.md).
Обычным пользователям эти инструкции сборки не нужны: готовые файлы публикуются в Releases.

## English

Download the Windows ZIP or Linux AppImage from [Releases](https://github.com/DimEdrol-prog/osu-skin-gacha/releases). Windows: extract everything and run `osu!gacha.exe`, keeping `_internal` beside it. Linux: allow execution of the AppImage and run it. No Python installation or manual build is required.

Bancho signs in through the official osu! website. Gatari uses its own ID; offline mode is supported. Linux login persistence requires an unlocked Secret Service keyring. Use Wine for osu!stable and confirm skin reloads with the application's “Skin reloaded” button.

NixOS x86_64: `nix profile install github:DimEdrol-prog/osu-skin-gacha#default` installs the program; `skin-gacha` starts it. Alternatively, `nix run github:DimEdrol-prog/osu-skin-gacha#default` builds and starts it without profile installation. Nix commands and flakes must be enabled. Use `appimage-run` for the prebuilt AppImage.

Close the program and retain your personal data when upgrading. Developer-only build and test instructions are linked above.
