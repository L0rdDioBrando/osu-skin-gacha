import requests
import customtkinter as ctk
import tkinter as tk
import webbrowser
from PIL import Image
"""Награды, избранное, смешивание, сетевые ошибки и DT. Только временные папки."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
import zipfile
import queue
from modules import skin_gacha as g


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.osu,self.pack = self.root/'osu',self.root/'pack'
        self.base = self.osu/'Skins'/'My UI'
        self.base.mkdir(parents=True)
        for name,data in {'skin.ini':'[General]\nName: My UI\nVersion: 2.5\n[Fonts]\nScorePrefix: default\nHitCirclePrefix: default\n[Colours]\nCombo1: 1,2,3',
                          'hitcircle.png':'base circle','default-0.png':'base score font','menu-back.png':'base menu','scorebar-bg.png':'base HP'}.items():
            (self.base/name).write_text(data)
        (self.pack/'D').mkdir(parents=True)
        self.source = self.pack/'D'/'Test.osk'
        with zipfile.ZipFile(self.source,'w') as z:
            for name,data in {'skin.ini':'[General]\nName: Test\nVersion: 2.5\n[Fonts]\nHitCirclePrefix: default\nHitCircleOverlap: 2\n[Colours]\nCombo1: 9,8,7',
                              'hitcircle.png':'donor circle','default-0.png':'donor numbers','menu-back.png':'donor menu','normal-hitnormal.wav':'donor sound'}.items():
                z.writestr(name,data)
        self.box = g.Sandbox(self.osu,self.pack)
        self.lib = g.SkinLibrary(self.box)
        self.lib.scan()
        self.settings = dict(g.DEFAULTS,interface_skin='My UI')

    def tearDown(self):
        self.box.release()
        self.tmp.cleanup()

    def test_duplicate_across_sessions_and_categories(self):
        (self.pack/'S').mkdir()
        (self.pack/'S'/'OtherName.osk').write_bytes(self.source.read_bytes())
        catalog = self.lib.scan()['catalog']
        self.assertEqual(len({v['id'] for v in catalog.values()}),1)
        self.box.start()
        first = self.lib.award(self.source,self.settings)
        self.assertRegex(first['installed_name'],r'^!\d{4} ')
        self.box.stop()
        self.lib = g.SkinLibrary(self.box)
        self.lib.scan()
        self.box.start()
        with self.assertRaises(ValueError):
            self.lib.award(self.pack/'S'/'OtherName.osk',self.settings)
        self.box.stop()

    def test_compact_reward_names_preserve_skin_and_ledger(self):
        self.box.start()
        drop = self.lib.award(self.source,self.settings)
        self.box.stop()
        old_name = '! Gacha 99999999 - Test'
        (self.box.active/drop['installed_name']).rename(self.box.active/old_name)
        self.lib.drops[drop['id']]['installed_name'] = old_name
        self.lib.save()
        self.lib.compact_names()
        self.assertEqual(self.lib.drops[drop['id']]['installed_name'],'!1999 Test')
        self.assertTrue((self.box.active/'!1999 Test'/'skin.ini').is_file())
        self.assertTrue(self.base.is_dir())
        self.lib.compact_names()

    def test_legacy_migration(self):
        old = self.box.active/'Test'
        old.mkdir(parents=True)
        with zipfile.ZipFile(self.source) as z:
            z.extractall(old)
        state = self.lib.scan()
        ident = state['catalog'][str(self.source)]['id']
        self.assertIn(ident,state['drops'])
        self.assertEqual(state['drops'][ident]['installed_name'],'Test')

    def test_favourite_export_preserves_original_and_not_duplicated(self):
        self.box.start()
        drop = self.lib.award(self.source,self.settings)
        self.lib.favorite(drop['id'],True)
        exported=self.lib.export(drop['id'])
        self.assertTrue(self.box.lock_file)
        self.assertTrue((self.osu/'Skins'/exported).exists())
        self.box.stop()
        self.assertTrue((self.osu/'Skins'/exported).exists())
        name = self.lib.export(drop['id'])
        self.assertEqual((self.osu/'Skins'/name/'hitcircle.png').read_text(),'donor circle')
        self.assertEqual((self.base/'menu-back.png').read_text(),'base menu')
        self.assertEqual(self.lib.export(drop['id']),name)
        self.assertTrue(g.SkinLibrary(self.box).scan()['drops'][drop['id']]['favorite'])

    def test_personal_export_survives_session_recovery(self):
        self.box.start();drop=self.lib.award(self.source,self.settings)
        self.lib.favorite(drop['id'],True);name=self.lib.export(drop['id'])
        self.box.release()
        restored=g.Sandbox(self.osu,self.pack);restored.stop()
        self.assertTrue((self.osu/'Skins'/name/'skin.ini').is_file())
        self.assertTrue((restored.active/drop['installed_name']/'skin.ini').is_file())

    def test_optimization_ui_gameplay_fonts(self):
        self.box.start()
        drop = self.lib.award(self.source,dict(self.settings,optimize_skins=True))
        installed = self.box.skins/drop['installed_name']
        self.assertEqual((installed/'hitcircle.png').read_text(),'donor circle')
        self.assertEqual((installed/'normal-hitnormal.wav').read_text(),'donor sound')
        self.assertEqual((installed/'menu-back.png').read_text(),'base menu')
        self.assertEqual((installed/'scorebar-bg.png').read_text(),'base HP')
        self.assertEqual((installed/'default-0.png').read_text(),'base score font')
        self.assertEqual((installed/'gacha-hit-0.png').read_text(),'donor numbers')
        ini = g.read_skin_ini(installed)
        self.assertEqual(ini.get('Fonts','HitCirclePrefix'),'gacha-hit')
        self.assertEqual(ini.get('Colours','Combo1'),'9,8,7')
        self.box.stop()

    def test_size_filter_uses_uncompressed_size(self):
        with zipfile.ZipFile(self.source,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('big.bin',b'0'*(30*1024*1024+1))
        self.lib.scan()
        self.assertLess(self.source.stat().st_size,1024*1024)
        self.box.start()
        with self.assertRaises(ValueError):
            self.lib.award(self.source,dict(self.settings,exclude_heavy=True))
        self.assertEqual(self.lib.drops,{})
        self.box.stop()

    def test_failed_install_does_not_consume_reward(self):
        self.box.start()
        with patch.object(self.box,'install',side_effect=OSError('simulated')):
            with self.assertRaises(OSError):
                self.lib.award(self.source,self.settings)
        self.assertEqual(self.lib.drops,{})
        self.lib.award(self.source,self.settings)
        self.box.stop()


class FeatureTests(unittest.TestCase):
    def test_monitor_fun_queues_bonus_once(self):
        score = dict(beatmap_id='12',date='2026-09-06 10:00:00',score='10',rank='A',maxcombo='751',enabled_mods='64',pp='400')
        profile = {'pp_raw':'8000'}
        class Stop:
            count = 0
            def wait(self,seconds):
                self.count += 1
                return self.count > 2
            def is_set(self):
                return False
        class API:
            session = type('Session',(),{'close':lambda self:None})()
            def snapshot(self):
                return profile,[],[score]
            def beatmap(self,*args):
                return {'difficultyrating':'6'}
            def enrich_pp(self,score):
                return score
        app = object.__new__(g.SkinGachaApp)
        app.events = queue.Queue()
        app.history = {}
        app.settings = dict(g.DEFAULTS,difficulty='Fun')
        app.monitor(API(),(profile,[],[]),Stop(),app.settings)
        self.assertEqual([v for k,_,v in app.events.queue if k == 'roll'],['A','DT'])

    def test_modern_score_id_resolution(self):
        response = Mock()
        response.json.return_value = {'id':7359418722}
        with patch.object(requests.Session,'get',return_value=response) as get:
            self.assertEqual(g.resolve_score_url({'score_id':'123'}),'https://osu.ppy.sh/scores/7359418722')
            self.assertNotIn('params',get.call_args.kwargs)
        with patch.object(requests.Session,'get',side_effect=requests.exceptions.Timeout):
            self.assertEqual(g.resolve_score_url({'score_id':'123'}),'https://osu.ppy.sh/scores/osu/123')

    def test_fun_dt_boundaries(self):
        score = {'enabled_mods':64,'maxcombo':750}
        self.assertTrue(g.dt_reward('Fun',8000,score,6))
        score['maxcombo'] = 749
        self.assertFalse(g.dt_reward('Fun',8000,score,6))
        score['maxcombo'] = 751
        self.assertTrue(g.dt_reward('Fun',8000,score,g.stars_threshold(8000)))
        self.assertFalse(g.dt_reward('Fun',8000,score,4.99))
        self.assertTrue(g.dt_reward('Fun',8000,score,5.01))
        score['enabled_mods'] = 512
        self.assertTrue(g.dt_reward('Fun',8000,score,6))
        score['enabled_mods'] = 8
        self.assertFalse(g.dt_reward('Fun',8000,score,6))

    def test_score_link_uses_legacy_namespace(self):
        self.assertEqual(g.score_url({'score_id':'123'}),'https://osu.ppy.sh/scores/osu/123')
        self.assertIsNone(g.score_url({}))

    def test_proxy_diagnostic_redacts_key_and_keeps_tls(self):
        api = g.API(dict(g.DEFAULTS,api_key='SECRET',ignore_proxy=True))
        self.assertFalse(api.session.trust_env)
        self.assertTrue(api.session.verify)
        with patch.object(api.session,'get',side_effect=requests.exceptions.ProxyError('https://osu.ppy.sh?k=SECRET')):
            with self.assertRaises(RuntimeError) as result:
                api.get('get_user')
        self.assertNotIn('SECRET',str(result.exception))
        self.assertIn('прокси',str(result.exception))
        api.session.close()

    def test_best_sorting_per_mode(self):
        app = object.__new__(g.SkinGachaApp)
        app.settings = dict(g.DEFAULTS,user_id='1')
        app.history = {}
        app.records = [dict(score={'beatmap_id':'1','pp':500,'maxcombo':100},map={'difficultyrating':4},position=1),
                       dict(score={'beatmap_id':'2','pp':400,'maxcombo':900},map={'difficultyrating':8},position=2)]
        self.assertEqual(app.best_records('pp')[0]['position'],1)
        self.assertEqual(app.best_records('pp')[0]['position'],1)
        self.assertEqual(app.best_records('combo')[0]['position'],2)


if __name__ == '__main__':
    unittest.main()
