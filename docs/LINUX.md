# Локальная сборка на Linux

Python 3.12+, Tcl/Tk, `desktop-file-validate` и squashfs-tools. Установите зависимости `requirements.txt`, затем:

```bash
python -m pip install uv && uv sync
python -m PyInstaller --noconfirm --onedir --windowed --name osu-gacha --collect-all customtkinter --collect-all pygame --collect-all rosu_pp_py --collect-all mutagen --add-data "assets:assets" main.py 
```
