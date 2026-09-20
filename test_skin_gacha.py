import requests
import customtkinter as ctk
import tkinter as tk
import webbrowser
from PIL import Image
"""Регрессионные проверки. Все файловые операции выполняются в TemporaryDirectory."""
import os
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from modules import skin_gacha as g


class RulesTests(unittest.TestCase):
    def test_hard_boundaries(self):
        for pos, expected in ((1,'SS'),(3,'SS'),(4,'S'),(10,'S'),(11,'A'),(25,'A'),(26,'B'),(50,'B'),(51,'C'),(80,'C'),(81,'D'),(100,'D'),(101,'F')):
            self.assertEqual(g.reward_for('Hard',8000,{'rank':'A'},7,pos),expected)

    def test_medium_and_fun(self):
        self.assertEqual(g.pp_thresholds(8038)['SS'],397)
        self.assertEqual(g.pp_thresholds(12000)['SS'],548)
        self.assertEqual(g.reward_for('Medium',8000,{'rank':'S','pp':None},5),'F')
        self.assertEqual(g.reward_for('Fun',8000,{'rank':'A','maxcombo':1500},g.stars_threshold(8000)),'SS')
        self.assertEqual(g.reward_for('Fun',12000,{'rank':'A','maxcombo':1500},g.stars_threshold(12000)-.01),'F')
        self.assertEqual(g.reward_for('Fun',8000,{'rank':'F','maxcombo':1500},8),'F')

    def test_mods_accuracy_and_identity(self):
        self.assertEqual(g.mods_string(64|512|8),'HD+NC')
        self.assertEqual(g.mods_string(32|16384|1024),'FL+PF')
        self.assertEqual(g.mods_string(1|2|256),'NF+EZ+HT')
        self.assertEqual(g.accuracy({'count300':1}),100)
        self.assertEqual(g.score_key({'score_id':'x','date':'2026'}),g.score_key({'date':'2026'}))


class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.osu,self.pack = self.root/'osu',self.root/'pack'
        (self.osu/'Skins'/'same').mkdir(parents=True)
        (self.osu/'Skins'/'same'/'personal.txt').write_text('personal')
        (self.pack/'gacha_active'/'same').mkdir(parents=True)
        (self.pack/'gacha_active'/'same'/'reward.txt').write_text('reward')
        self.box = g.Sandbox(self.osu,self.pack)

    def tearDown(self):
        self.box.release()
        self.tmp.cleanup()

    def test_two_sessions_and_collision(self):
        for _ in range(2):
            self.box.start()
            self.assertFalse((self.osu/'Skins'/'same'/'personal.txt').exists())
            self.assertTrue((self.osu/'Skins'/'same'/'reward.txt').exists())
            self.box.stop()
            self.assertEqual((self.osu/'Skins'/'same'/'personal.txt').read_text(),'personal')
            self.assertTrue((self.pack/'gacha_active'/'same'/'reward.txt').exists())

    def test_interrupted_start(self):
        real = self.box.move
        def fail(source,dest):
            if source.parent == self.box.active:
                raise OSError('simulated')
            real(source,dest)
        with patch.object(self.box,'move',side_effect=fail):
            with self.assertRaises(OSError):
                self.box.start()
        self.box.release()
        self.box = g.Sandbox(self.osu,self.pack)
        self.box.stop()
        self.assertTrue((self.osu/'Skins'/'same'/'personal.txt').exists())
        self.assertTrue((self.pack/'gacha_active'/'same'/'reward.txt').exists())

    def test_interrupted_stop(self):
        self.box.start()
        real = self.box.move
        def fail(source,dest):
            if source.parent == self.box.backup:
                raise OSError('simulated')
            real(source,dest)
        with patch.object(self.box,'move',side_effect=fail):
            with self.assertRaises(OSError):
                self.box.stop()
        self.box.release()
        self.box = g.Sandbox(self.osu,self.pack)
        self.box.stop()
        self.assertTrue((self.osu/'Skins'/'same'/'personal.txt').exists())
        self.assertTrue((self.pack/'gacha_active'/'same'/'reward.txt').exists())

    def test_archive_install_and_traversal(self):
        self.box.start()
        good,bad = self.pack/'good.osk',self.pack/'bad.osk'
        with zipfile.ZipFile(good,'w') as z:
            z.writestr('skin.ini','[General]\nName: demo')
        with zipfile.ZipFile(bad,'w') as z:
            z.writestr('../escape.txt','bad')
        name = self.box.install(good)
        self.assertTrue((self.osu/'Skins'/name/'skin.ini').exists())
        with self.assertRaises(ValueError):
            self.box.install(bad)
        self.box.stop()
        self.assertTrue((self.pack/'gacha_active'/name/'skin.ini').exists())

    def test_second_instance_blocked(self):
        other = g.Sandbox(self.osu,self.pack)
        self.box.start()
        with self.assertRaises(OSError):
            other.acquire()
        other.release()
        self.box.stop()

    def test_alias_and_uppercase_archive(self):
        (self.pack/'особые').mkdir()
        (self.pack/'особые'/'a.OSK').write_bytes(b'')
        self.assertEqual(len(self.box.scan()['special']),1)


class MonitorTests(unittest.TestCase):
    def test_batch_dedup_and_recent_to_best(self):
        score = dict(beatmap_id='1',date='2026-09-05 10:00:00',score='1000',rank='A',maxcombo='1500',enabled_mods='0')
        profile = {'pp_raw':'8000'}
        class Stop:
            count = 0
            def wait(self,seconds):
                self.count += 1
                return self.count > 3
            def is_set(self):
                return False
        class API:
            def leaderboard(self,score):return 1,1001
            session = type('Session',(),{'close':lambda self:None})()
            def snapshot(self):
                return profile,[dict(score,pp='400')],[score]
            def beatmap(self,*args):
                return {'difficultyrating':'6'}
            def enrich_pp(self,score):
                return score
        app = object.__new__(g.SkinGachaApp)
        app.events = queue.Queue()
        app.history = {}
        app.settings = g.DEFAULTS.copy()
        g.SkinGachaApp.monitor(app,API(),(profile,[],[]),Stop(),g.DEFAULTS)
        events = list(app.events.queue)
        self.assertEqual(sum(kind == 'score' for kind,_,_ in events),1)
        self.assertEqual(sum(kind == 'roll' for kind,_,_ in events),1)


class PersistenceTests(unittest.TestCase):
    def test_history_roundtrip_fallback_and_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            blocked = root/'blocked'
            blocked.write_text('file')
            store = g.HistoryStore()
            store.paths = [blocked/'sessions',root/'fallback']
            record = dict(key=('score',),score={'rank':'F','beatmap_id':'42'},map={},reward='SS')
            session = dict(id='20260906_120000_test',started_at='2026-09-06T12:00:00+05:00',
                           user_id='123',ended_at=None,records=[record])
            store.save(session)
            reloaded = g.HistoryStore()
            reloaded.paths = store.paths
            result = reloaded.load()
            self.assertEqual(result[session['id']]['records'][0]['score']['rank'],'F')
            self.assertEqual(result[session['id']]['started_at'],session['started_at'])
            session['ended_at'] = '2026-09-06T13:00:00+05:00'
            store.save(session)
            self.assertEqual(len(reloaded.load()),1)
            self.assertEqual(reloaded.load()[session['id']]['ended_at'],session['ended_at'])

    def test_filter_is_game_rank_not_reward_and_non_destructive(self):
        app = object.__new__(g.SkinGachaApp)
        failed = dict(score={'rank':'F'},reward='SS')
        passed = dict(score={'rank':'A'},reward='F')
        app.records = [failed,passed]
        app.selected_session = None
        app.settings = dict(g.DEFAULTS,hide_failed=True)
        self.assertEqual(app.visible_records(),[passed])
        app.history = {'old':{'records':[passed,failed]}}
        app.selected_session = 'old'
        self.assertEqual(app.visible_records(),[passed])
        app.settings['hide_failed'] = False
        self.assertEqual(app.visible_records(),[passed,failed])
        self.assertEqual(len(app.records),2)

    def test_corrupt_local_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = g.SettingsStore()
            store.paths = [Path(tmp)/'local.json',Path(tmp)/'fallback.json']
            store.paths[0].write_text('{broken')
            g.atomic_json(store.paths[1],{'theme':'Nord','interval':0})
            result = store.load()
            self.assertEqual(result['theme'],'Nord')
            self.assertEqual(result['interval'],1)

    def test_access_failure_uses_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = g.SettingsStore()
            # Родитель-файл имитирует невозможность записи по первому пути.
            blocked = Path(tmp)/'blocked'
            blocked.write_text('file')
            store.paths = [blocked/'settings.json',Path(tmp)/'fallback.json']
            store.save({'theme':'Steam'})
            self.assertEqual(store.load()['theme'],'Steam')

    def test_local_cover_uses_exact_set_and_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wrong,right = root/'1234 wrong',root/'123 right'
            wrong.mkdir()
            right.mkdir()
            Image.new('RGB',(30,30),'red').save(wrong/'bg.png')
            Image.new('RGB',(30,30),'blue').save(right/'actual.png')
            (right/'map.osu').write_text('BeatmapID:42\n[Events]\n0,0,"actual.png",0,0',encoding='utf-8')
            with patch.object(requests,'get',side_effect=AssertionError('network must not run')):
                image = g.Covers(root).get('42','123')
            self.assertEqual(image.getpixel((0,0)),(0,0,255))


if __name__ == '__main__':
    unittest.main()
