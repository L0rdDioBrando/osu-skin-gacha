# osu!gacha v0.5.0 · Connected

Играй в osu!stable, получай скины за результаты и сравнивай игру с разными скинами.

## Windows

- Скачайте Windows ZIP из [Releases](https://github.com/DimEdrol-prog/osu-skin-gacha/releases).
- Распакуйте весь архив и откройте `osu!gacha.exe`.
- Выберите Bancho → «Войти через osu!» → подтвердите вход на официальном сайте. API-ключ и ручной Bancho ID не нужны.

Для Gatari используется ID Gatari; также доступен офлайн-режим.

## Linux

Скачайте `.AppImage` из [Releases](https://github.com/DimEdrol-prog/osu-skin-gacha/releases), разрешите запуск файла в его свойствах и откройте его.

Если удобнее через терминал:

```bash
chmod +x ./osu-gacha-v0.5.0-linux-x86_64.AppImage
./osu-gacha-v0.5.0-linux-x86_64.AppImage
```

Либо скачайте бинарник в релизах

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

В Windows данные обычно находятся рядом с программой, в Linux — в `$XDG_DATA_HOME/osu-gacha` (обычно `~/.local/share/osu-gacha`). Авторизация хранится отдельно: Windows DPAPI или системное хранилище Linux. Секрет приложения и токены osu! остаются на сервере.
