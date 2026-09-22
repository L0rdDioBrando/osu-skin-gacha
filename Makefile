run:
	python main.py

install:
	python -m pip install uv
	uv sync
	uv run pyinstaller --windowed --add-data "assets:assets" --onefile --name osu-gacha --collect-all customtkinter --collect-all pygame --collect-all rosu_pp_py main.py
