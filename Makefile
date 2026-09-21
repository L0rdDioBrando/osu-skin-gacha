run:
	python3 main.py

install:
	python3 -m pip install uv && uv sync && python3 -m PyInstaller --noconfirm --onedir --windowed --name osu-gacha --collect-all customtkinter --collect-all pygame --collect-all rosu_pp_py --collect-all mutagen --add-data "assets:assets" main.py

source:
	python3 build_release.py

clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .venv && rm -rf build && rm -rf dist && rm -rf __pycache__
