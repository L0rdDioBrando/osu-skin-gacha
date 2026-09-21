import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from types import SimpleNamespace
from modules.gacha_skins import Sandbox
from modules.gacha_reports import fetch_reports, report_body
from modules.gacha_widgets import bind_api_paste
from modules.gacha_bootstrap import clean_environment


class SessionTests(unittest.TestCase):
    def test_restore_progress_reports_actual_moves(self):
        for n in range(3): (self.osu/'Skins'/str(n)).mkdir()
        self.box.start()
        progress = []
        def moved(done,total):
            progress.append((done,total))
            self.assertEqual(len(list(self.box.backup.iterdir())),total-done)
        self.box.stop(moved)
        self.assertEqual(progress,[(0,4),(1,4),(2,4),(3,4),(4,4)])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.osu, self.pack = self.root/'osu', self.root/'pack'
        self.personal = self.osu/'Skins'/'same'
        self.personal.mkdir(parents=True)
        (self.personal/'personal.txt').write_text('original')
        active = self.pack/'gacha_active'/'same'
        active.mkdir(parents=True)
        (active/'skin.ini').write_text('[General]\nName: reward')
        self.box = Sandbox(self.osu, self.pack)

    def tearDown(self):
        self.box.release()
        self.temp.cleanup()

    def test_coexist_collision_install_and_recovery(self):
        progress = []
        self.box.start(True, lambda a,b: progress.append((a,b)))
        self.assertEqual(progress, [(0,0)])
        self.assertEqual((self.personal/'personal.txt').read_text(), 'original')
        self.assertFalse(any(self.box.backup.iterdir()))
        # Even a newly added personal skin with a Gacha-looking name stays put.
        extra = self.osu/'Skins'/'!1990 personal'
        extra.mkdir()
        source = self.root/'new'
        source.mkdir()
        (source/'skin.ini').write_text('[General]\nName: new')
        installed = self.box.install(source, '!1989 new')
        self.box.release()
        self.box = Sandbox(self.osu, self.pack)
        self.box.stop()
        self.assertTrue(extra.exists())
        self.assertTrue((self.personal/'personal.txt').exists())
        self.assertTrue((self.box.active/installed/'skin.ini').exists())
        self.assertTrue((self.box.active/'same (1)'/'skin.ini').exists())
        self.assertFalse(self.box.journal.exists())

    def test_cancel_mid_backup_restores_all(self):
        for n in range(4):
            (self.osu/'Skins'/str(n)).mkdir()
        stop = threading.Event()
        progress = []
        def moved(done, total):
            progress.append((done,total))
            if done == 2:
                stop.set()
        with self.assertRaisesRegex(RuntimeError, 'cancelled'):
            self.box.start(False, moved, stop)
        self.assertEqual(progress, [(0,5),(1,5),(2,5)])
        self.assertEqual(len(list((self.osu/'Skins').iterdir())), 5)
        self.assertTrue((self.personal/'personal.txt').exists())
        self.assertFalse(self.box.journal.exists())
        self.assertFalse(any(self.box.backup.iterdir()))
        self.assertTrue((self.box.active/'same'/'skin.ini').exists())


class IntegrationTests(unittest.TestCase):
    def test_redaction_and_log_consent(self):
        self.assertNotIn('SECRET', report_body('problem SECRET', ['url?k=SECRET'], 'SECRET'))
        self.assertNotIn('Logs', report_body('problem'))
        self.assertNotIn('abc', report_body('api_key=abc'))

    def test_issue_reader_excludes_pull_requests(self):
        session = Mock()
        session.get.return_value.json.return_value = [
            dict(number=1,title='bug',body='details'),
            dict(number=2,title='PR',pull_request={})]
        with patch('modules.gacha_reports.session_for') as factory:
            factory.return_value.__enter__.return_value=session
            result=fetch_reports(True)
        self.assertEqual([r['number'] for r in result], [1])
        factory.assert_called_once_with(True)
        self.assertEqual(session.get.call_args.kwargs['timeout'], (12,25))

    def test_paste_with_russian_keyboard(self):
        entry=Mock()
        entry.clipboard_get.return_value='  copied-key\n'
        bind_api_paste(entry)
        callback=entry.bind.call_args.args[1]
        self.assertEqual(callback(SimpleNamespace(keycode=86,keysym='Cyrillic_em')), 'break')
        entry.insert.assert_called_once_with(0,'copied-key')

    def test_launcher_ignores_foreign_runtime(self):
        with patch.dict('os.environ', {'PYTHONPATH':'foreign', 'TCL_LIBRARY':'foreign'}):
            env=clean_environment()
        self.assertNotIn('PYTHONPATH', env)
        self.assertNotIn('TCL_LIBRARY', env)


if __name__ == '__main__':
    unittest.main()
