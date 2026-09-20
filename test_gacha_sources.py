"""Регрессии источников, слотов и офлайн-скоров; пользовательские папки не меняются."""
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from modules import skin_gacha as g
from modules import gacha_sources as s


def string(value):
    data=value.encode()
    assert len(data)<128
    return b'\x0b'+bytes([len(data)])+data if data else b'\x00'


def replay(points=12345):
    return (struct.pack('<Bi',0,20200101)+string('hash')+string('Tester')+string('replay'+str(points))+
        struct.pack('<6HIHBI',3,0,0,0,0,0,points,3,1,0)+string('')+
        struct.pack('<qiq',638000000000000000,-1,123))


MAP = '''osu file format v14
[General]
AudioFilename: song.mp3
Mode: 0
[Metadata]
Title: Test
Artist: Test
Creator: Test
Version: Test
BeatmapID: 1
BeatmapSetID: 1
[Difficulty]
HPDrainRate:5
CircleSize:4
OverallDifficulty:8
ApproachRate:9
SliderMultiplier:1.4
SliderTickRate:1
[TimingPoints]
0,500,4,2,1,70,1,0
[HitObjects]
64,192,1000,1,0,0:0:0:0:
448,192,1250,1,0,0:0:0:0:
64,192,1500,1,0,0:0:0:0:
'''


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.pack=self.root/'pack';self.pack.mkdir()
        self.osu=self.root/'osu';(self.osu/'Skins'/'Personal').mkdir(parents=True)
        self.config=dict(g.DEFAULTS,osu_path=str(self.osu),skin_pack_path=str(self.pack))

    def tearDown(self):
        self.tmp.cleanup()

    def skin(self):
        folder=self.pack/'D';folder.mkdir(exist_ok=True)
        path=folder/'demo.osk'
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('skin.ini','[General]\nName: Demo')
            z.writestr('hitcircle.png',b'demo')
        return path

    def test_nested_zip_only_extracts_selected_skin(self):
        skin=self.skin()
        archive=self.root/'all.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.write(skin,'app/D/demo.osk')
            z.writestr('app/settings.json','PRIVATE')
        cfg=dict(self.config,skin_source='zip',skin_archive=str(archive))
        sources=s.SkinSources(cfg,self.pack)
        catalog=sources.catalog()
        self.assertEqual(len(catalog),1)
        material=sources.materialize(next(iter(catalog.values())),cfg)
        self.assertEqual(material.read_bytes(),skin.read_bytes())
        self.assertFalse((self.pack/'settings.json').exists())

    def test_slots_restore_and_reset_keep_personal_and_source(self):
        source=self.skin()
        for slot in ('1','2','3'):
            box=g.Sandbox(self.osu,self.pack,slot=slot)
            library=g.SkinLibrary(box)
            library.scan();box.start()
            library.award(source,self.config)
            box.stop()
            self.assertEqual(len(list(box.active.iterdir())),1)
        (self.osu/'Skins'/'Exported').mkdir()
        box=g.Sandbox(self.osu,self.pack,slot='3')
        library=g.SkinLibrary(box);library.reset_all()
        self.assertTrue((self.osu/'Skins'/'Personal').exists())
        self.assertTrue((self.osu/'Skins'/'Exported').exists())
        self.assertTrue(source.exists())
        for slot in ('1','2','3'):
            box=g.Sandbox(self.osu,self.pack,slot=slot)
            self.assertFalse(list(box.active.iterdir()))

    def test_recovery_uses_journal_slot(self):
        box=g.Sandbox(self.osu,self.pack,slot='2')
        box.start();box.release()
        other=g.Sandbox(self.osu,self.pack,slot='1')
        self.assertEqual(other.slot,'2')
        other.stop()
        self.assertTrue((self.osu/'Skins'/'Personal').is_dir())

    def test_reset_rejects_traversal(self):
        g.atomic_json(self.pack/'modules.gacha_collection.json',{'drops':{'bad':{'installed_name':'../../osu/Skins/Personal'}}})
        with self.assertRaises(ValueError):
            g.SkinLibrary(g.Sandbox(self.osu,self.pack)).reset_all()
        self.assertTrue((self.osu/'Skins'/'Personal').is_dir())

    def test_offline_drive_does_not_contact_network(self):
        manifest=self.root/'manifest.json'
        s.write_json(manifest,{'files':[dict(rank='D',filename='demo.osk',drive_id='demo12345')]})
        sources=s.SkinSources(dict(self.config,skin_source='drive',offline=True),self.pack,manifest=manifest)
        with patch.object(requests.Session,'get',side_effect=AssertionError('network forbidden')):
            self.assertEqual(sources.catalog(),{})

    def test_binary_roundtrip_and_partial_db(self):
        data=struct.pack('<ii',20200101,1)+string('hash')+struct.pack('<i',1)+replay()
        db=self.osu/'scores.db';db.write_bytes(data)
        scores=s.read_scores_db(db)
        self.assertEqual(scores[0]['maxcombo'],3)
        self.assertEqual(scores[0]['provider'],'offline')
        self.assertIsNone(g.score_url(scores[0]))
        db.write_bytes(data[:-4])
        with self.assertRaises(ValueError):s.read_scores_db(db)

    def test_offline_snapshot_pp_and_top_no_network(self):
        songs=self.osu/'Songs';songs.mkdir()
        path=songs/'test.osu';path.write_text(MAP)
        data=struct.pack('<ii',20200101,1)+string('hash')+struct.pack('<i',1)+replay()
        (self.osu/'scores.db').write_bytes(data)
        api=s.OfflineAPI(dict(self.config,offline=True,offline_username='Tester',offline_total_pp=8000))
        api.maps.loaded=True
        item=dict(path=str(path),file_md5='hash',beatmap_id='1',beatmapset_id='1')
        api.maps.index['hash']=item
        with patch.object(requests.Session,'get',side_effect=AssertionError('network forbidden')):
            user,best,recent=api.snapshot()
            self.assertEqual(user['pp_raw'],8000)
            self.assertEqual(len(best),1)
            self.assertEqual(best[0]['rank'],'X')
            self.assertGreaterEqual(best[0]['pp'],0)
            self.assertEqual(best[0]['pp_source'],'calculated')
            self.assertEqual(len(api.snapshot()[2]),1)
        api.session.close()

    def test_failed_has_no_score_link(self):
        self.assertIsNone(g.score_url(dict(rank='F',score_id=123)))
        self.assertIsNone(g.score_url(dict(rank='F',score_id=123,provider='gatari')))

    def test_drive_timeout_uses_bundled_catalog(self):
        sources = s.SkinSources(dict(self.config,skin_source='drive'),self.pack)
        with patch.object(s,'drive_listing',side_effect=requests.ConnectTimeout('timeout')):
            catalog = sources.catalog()
        self.assertGreater(len(catalog),0)
        self.assertTrue(all(item['kind']=='drive' for item in catalog.values()))

    def test_first_run_and_existing_settings_migration(self):
        store = g.SettingsStore()
        store.paths = [self.pack/'test-settings.json']
        self.assertFalse(store.load()['setup_complete'])
        store.save(dict(user_id='123'))
        self.assertTrue(store.load()['setup_complete'])

    def test_offline_cover_does_not_request_network(self):
        covers = g.Covers(self.osu/'Songs', offline=True)
        with patch.object(requests.Session, 'get', side_effect=AssertionError('network forbidden')):
            self.assertIsNone(covers.get('1', '2'))

    def test_proxy_settings_apply_to_session(self):
        with s.session_for(True) as session:
            self.assertFalse(session.trust_env)

    def test_gatari_normalizes_pp_rank_and_identity(self):
        api=s.GatariAPI(self.config)
        row=dict(beatmap={'beatmap_id':5,'difficulty':6,'fc':1000},id=9,score=123,
            max_combo=800,mods=64,pp=300,completed=2,ranking='A',time=1700000000,count_300=500)
        score=api.normalize(row)
        self.assertEqual(score['provider'],'gatari')
        self.assertEqual(score['pp'],300)
        self.assertEqual(score['rank'],'A')
        api.session.close()


import requests
if __name__=='__main__':
    unittest.main()
