run:
	python main.py

depens:
	python -m pip install uv
	uv sync

build:
	uv run pyinstaller --windowed --add-data "assets:assets" --onefile --name osu-gacha main.py
