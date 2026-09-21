import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from modules import gacha_driver as driver


class DriverTests(unittest.TestCase):
    def test_osu_uses_game_folder_and_is_not_minimized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'osu!.exe';path.touch()
            with patch.object(driver.subprocess,'Popen') as launch:
                driver.launch_osu(tmp)
                self.assertEqual(launch.call_args.args[0],[str(path.resolve())])
                self.assertNotIn('startupinfo',launch.call_args.kwargs)
            driver._processes.clear()

    def test_disabled_default_and_launch_without_shell(self):
        from modules.gacha_config import DEFAULTS
        self.assertFalse(DEFAULTS['tablet_driver_enabled'])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'Tablet driver.exe';path.touch()
            process=Mock();process.poll.return_value=None
            with patch.object(driver.subprocess,'Popen',return_value=process) as launch, patch.object(driver.threading,'Thread'):
                self.assertIs(driver.launch_driver(str(path)),process)
                self.assertIs(driver.launch_driver(str(path)),process)
                self.assertEqual(launch.call_count,1)
                self.assertEqual(launch.call_args.args[0],[str(path.resolve())])
                self.assertNotIn('shell',launch.call_args.kwargs)
                self.assertEqual(launch.call_args.kwargs['startupinfo'].wShowWindow,7)
            driver._processes.clear()

    def test_missing_executable_does_not_launch(self):
        with patch.object(driver.subprocess,'Popen') as launch:
            with self.assertRaises(ValueError):driver.launch_driver('')
            launch.assert_not_called()
