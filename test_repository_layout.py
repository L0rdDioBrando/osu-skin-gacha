"""Regression coverage for relocating the application into Den's package layout."""
import ast
from pathlib import Path
import tomllib
import unittest

ROOT=Path(__file__).resolve().parent

class LayoutTests(unittest.TestCase):
    def test_all_internal_imports_use_package(self):
        names={p.stem for p in (ROOT/'modules').glob('*.py')}
        for path in (ROOT/'modules').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
                if isinstance(node,ast.ImportFrom):self.assertNotIn(node.module,names,path.name)
                if isinstance(node,ast.Import):
                    for alias in node.names:self.assertNotIn(alias.name,names,path.name)

    def test_resources_resolve_independently_of_working_directory(self):
        from modules.gacha_config import RESOURCES
        from modules.gacha_sources import SkinSources
        self.assertEqual(RESOURCES,ROOT)
        self.assertTrue((RESOURCES/'assets/gacha.ico').is_file())
        self.assertTrue((RESOURCES/'assets/drive_catalog.json').is_file())
        self.assertGreater(len(SkinSources({},ROOT).known),0)

    def test_packaging_dependencies_match_runtime(self):
        config=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))
        expected={line.strip() for line in (ROOT/'requirements.txt').read_text().splitlines() if line.strip()}
        self.assertEqual(set(config['project']['dependencies']),expected)
        self.assertEqual(config['project']['scripts']['skin-gacha'],'main:main')

    def test_windows_launcher_and_bootstrap_target_main(self):
        self.assertIn('main.py',(ROOT/'run_skin_gacha.cmd').read_text())
        self.assertIn("ROOT / 'main.py'",(ROOT/'modules/gacha_bootstrap.py').read_text(encoding='utf-8'))
        self.assertIn('modules/gacha_python_probe.py',(ROOT/'ensure_python.ps1').read_text())

if __name__=='__main__':unittest.main()
