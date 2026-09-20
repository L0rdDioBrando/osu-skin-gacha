import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from modules.gacha_skins import Sandbox
from modules.gacha_skin_apply import update_live, recover_live, LIVE_NAME

class LiveTests(unittest.TestCase):
    def test_replace_preserves_originals_and_survives_sessions(self):
        for coexist in (False,True):
            with self.subTest(coexist=coexist), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); (root/'osu'/'Skins'/'personal').mkdir(parents=True); (root/'pack').mkdir()
                box=Sandbox(root/'osu',root/'pack')
                try:
                    box.start(coexist)
                    source=root/'source';source.mkdir();(source/'skin.ini').write_text('[General]')
                    (source/'old.png').write_bytes(b'old')
                    first=box.install(source,target_name='first')
                    update_live(box,first)
                    (source/'old.png').unlink();(source/'new.png').write_bytes(b'new')
                    second=box.install(source,target_name='second')
                    update_live(box,second)
                    live=box.skins/LIVE_NAME
                    self.assertFalse((live/'old.png').exists())
                    self.assertEqual((live/'new.png').read_bytes(),b'new')
                    self.assertEqual((box.skins/first/'old.png').read_bytes(),b'old')
                    with patch('modules.gacha_skin_apply.shutil.copy2',side_effect=OSError('copy failed')):
                        with self.assertRaises(OSError):update_live(box,first)
                    self.assertEqual((live/'new.png').read_bytes(),b'new')
                    live.rename(box.skins/(LIVE_NAME+'.old'))
                    recover_live(box)
                    self.assertTrue(live.exists())
                    box.stop()
                    self.assertTrue(live.exists())
                    self.assertTrue((box.active/first/'old.png').exists())
                    self.assertTrue((box.skins/'personal').exists())
                    box.start(coexist);self.assertTrue(live.exists());box.stop()
                finally:box.release()

    def test_name_collision_keeps_personal_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'osu'/'Skins'/LIVE_NAME).mkdir(parents=True);(root/'pack').mkdir()
            box=Sandbox(root/'osu',root/'pack')
            with self.assertRaises(ValueError):recover_live(box)
            self.assertTrue((box.skins/LIVE_NAME).exists())
