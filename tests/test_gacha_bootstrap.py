import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from modules import gacha_bootstrap as b

class BootstrapTests(unittest.TestCase):
    def fixture(self,root):
        exe=root/'.venv'/'Scripts'/'python.exe';exe.parent.mkdir(parents=True);exe.touch()
        (root/'requirements.txt').write_text('requests>=2.31\n')
        (root/'.venv'/'.gacha-requirements').write_text(hashlib.sha256((root/'requirements.txt').read_bytes()).hexdigest())
        return exe

    def test_ready_launch_no_network_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);exe=self.fixture(root)
            with patch.object(b,'ROOT',root),patch.object(b,'ENV_PYTHON',exe),patch.object(b,'probe',return_value=True),patch.object(b,'command') as command,patch.object(b.subprocess,'call',return_value=0) as launch,patch.object(b.sys,'argv',['launcher']):
                self.assertEqual(b.main(),0);command.assert_not_called();launch.assert_called_once()

    def test_missing_dependency_repaired_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);exe=self.fixture(root)
            with patch.object(b,'ROOT',root),patch.object(b,'ENV_PYTHON',exe),patch.object(b,'probe',side_effect=[True,False,True]),patch.object(b,'command') as command,patch.object(b.subprocess,'call',return_value=0),patch.object(b.sys,'argv',['launcher']):
                self.assertEqual(b.main(),0)
                self.assertTrue(any('--force-reinstall' in c.args[0] for c in command.call_args_list))
                self.assertEqual(len(command.call_args_list),3)

    def test_broken_environment_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);exe=self.fixture(root);(root/'settings.json').write_text('personal')
            def command(args,env):
                if 'venv' in args:exe.parent.mkdir(parents=True);exe.touch()
            with patch.object(b,'ROOT',root),patch.object(b,'ENV_PYTHON',exe),patch.object(b,'probe',side_effect=[False,True,False,True]),patch.object(b,'command',side_effect=command),patch.object(b.subprocess,'call',return_value=0),patch.object(b.sys,'argv',['launcher']):
                self.assertEqual(b.main(),0)
                self.assertEqual(len(list(root.glob('.venv-backup-*'))),1)
                self.assertEqual((root/'settings.json').read_text(),'personal')

    def test_install_only_does_not_open_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);exe=self.fixture(root)
            with patch.object(b,'ROOT',root),patch.object(b,'ENV_PYTHON',exe),patch.object(b,'probe',return_value=True),patch.object(b,'command'),patch.object(b.subprocess,'call') as launch,patch.object(b.sys,'argv',['launcher','--install']):
                self.assertEqual(b.main(),0);launch.assert_not_called()

if __name__=='__main__':unittest.main()
