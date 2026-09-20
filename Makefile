.PHONY: run install deps build source test clean
PYTHON ?= python3

run:
	$(PYTHON) main.py

deps:
	$(PYTHON) -m pip install -r requirements.txt

install: deps build

build:
	$(PYTHON) -m pip install pyinstaller
	$(PYTHON) -m PyInstaller --noconfirm --onedir --windowed --name osu-gacha --collect-all customtkinter --collect-all pygame --collect-all rosu_pp_py --collect-all mutagen --add-data "assets:assets" main.py

source:
	$(PYTHON) build_release.py

test:
	$(PYTHON) run_tests.py

clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .venv && rm -rf build && rm -rf dist && rm -rf __pycache__
