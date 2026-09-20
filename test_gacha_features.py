import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from modules.gacha_config import DEFAULTS
from modules.gacha_storage import SettingsStore, HistoryStore, atomic_json
from modules.gacha_skins import Sandbox, SkinLibrary
from modules.gacha_skin_apply import apply_collection, LIVE_NAME
from modules.gacha_transfer import export_data, import_data, validate_manifest
from modules.gacha_collection import filter_drops
from modules.gacha_insights import comparison_index, daily_rows, session_summary


def record(combo=100,miss=2,mods=0,pp=30,rank='A'):
    return dict(score=dict(beatmap_id='1',enabled_mods=mods,maxcombo=combo,count300=100,count100=0,count50=0,countmiss=miss,pp=pp,rank=rank),map={},reward='A')


class Features(unittest.TestCase):
    def test_comparison_mods_and_time(self):
        first=record();other=record(mods=64);last=record(134,0)
        result=comparison_index([(1,first),(2,other),(3,last)])
        self.assertNotIn(id(other),result)
        self.assertEqual(result[id(last)][0],34);self.assertEqual(result[id(last)][2],-2)
        self.assertGreater(result[id(last)][1],0)

    def test_daily_missing_pp_and_failed(self):
        t=datetime(2026,9,10).timestamp()
        rows=daily_rows([(t,record(pp=None)),(t+1,record(pp=999,rank='F'))],True)
        self.assertEqual(rows[0]['count'],1);self.assertIsNone(rows[0]['pp'])

    def test_summary_actual_drops(self):
        s=dict(started_at='2026-09-10T12:00:00',ended_at='2026-09-10T13:01:02',records=[record(pp=999,rank='F'),record(pp=33)],drops=[dict(rank='A'),dict(rank='special')])
        elapsed,records,best,drops,counts=session_summary(s)
        self.assertEqual(elapsed,3662);self.assertEqual(best['score']['pp'],33);self.assertEqual(counts['special'],1)

    def test_collection_filters(self):
        drops={'1':dict(name='Sakura',rank='A',favorite=True,unlocked_at=datetime.now().astimezone().isoformat()),'2':dict(name='Old',rank='B',unlocked_at='legacy')}
        self.assertEqual([i for i,_ in filter_drops(drops,'SAK','A',True,7)],['1'])
        self.assertEqual([i for i,_ in filter_drops(drops,order='old')],['2','1'])

    def test_apply_idle_and_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'osu'/'Skins').mkdir(parents=True);(root/'pack').mkdir()
            box=Sandbox(root/'osu',root/'pack');lib=SkinLibrary(box)
            source=box.active/'reward';source.mkdir(parents=True);(source/'skin.ini').write_text('[General]');(source/'test.png').write_bytes(b'original')
            lib.drops={'a':dict(id='a',name='Reward',installed_name='reward')};lib.loaded=True
            apply_collection(lib,'a');self.assertIsNone(box.lock_file)
            self.assertEqual((box.skins/LIVE_NAME/'test.png').read_bytes(),b'original')
            box.start(True)
            try:apply_collection(lib,'a');self.assertIsNotNone(box.lock_file)
            finally:box.stop()
            self.assertEqual((source/'test.png').read_bytes(),b'original')

    def transfer_fixture(self,root):
        pack=root/'source';skin=pack/'gacha_active'/'reward';skin.mkdir(parents=True)
        (skin/'skin.ini').write_text('[General]');(skin/'asset.png').write_bytes(b'pixels')
        atomic_json(pack/'modules.gacha_collection.json',{'drops':{'abc':dict(id='abc',name='Skin',rank='A',installed_name='reward',favorite=True,status='complete')}})
        settings=dict(DEFAULTS,api_key='PRIVATE-TEST-KEY',skin_pack_path=str(pack))
        history={'test':dict(id='test',user_id='1',started_at='2026-09-10T12:00:00',records=[record()])}
        file=root/'transfer.zip';export_data(file,settings,history,pack)
        target=root/'target';target.mkdir();(root/'osu'/'Skins').mkdir(parents=True)
        box=Sandbox(root/'osu',target);store=SettingsStore();store.paths=[target/'settings.json'];hs=HistoryStore();hs.paths=[target/'sessions']
        local=dict(DEFAULTS,api_key='LOCAL-KEY',skin_pack_path=str(target),osu_path=str(root/'osu'))
        return file,local,box,store,hs

    def test_transfer_roundtrip_and_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            file,local,box,store,hs=self.transfer_fixture(Path(tmp))
            with zipfile.ZipFile(file) as z:self.assertNotIn(b'PRIVATE-TEST-KEY',z.read('manifest.json'))
            updated,history,count=import_data(file,local,{},box,store,hs)
            self.assertEqual(count,1);self.assertEqual(updated['api_key'],'LOCAL-KEY');self.assertEqual(updated['osu_path'],local['osu_path'])
            self.assertEqual((box.active/'reward'/'asset.png').read_bytes(),b'pixels')
            self.assertTrue(json.loads((box.pack/'modules.gacha_collection.json').read_text())['drops']['abc']['favorite'])
            self.assertEqual(import_data(file,updated,history,box,store,hs)[2],0)

    def test_transfer_reject_traversal_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            file,local,box,store,hs=self.transfer_fixture(Path(tmp))
            with zipfile.ZipFile(file,'a') as z:z.writestr('skins/1/abc/../../escape.txt','bad')
            with self.assertRaises(ValueError):import_data(file,local,{},box,store,hs)
            self.assertFalse((box.pack/'modules.gacha_collection.json').exists());self.assertIsNone(box.lock_file)

    def test_transfer_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            file,local,box,store,hs=self.transfer_fixture(Path(tmp))
            atomic_json(store.paths[0],local);before=store.paths[0].read_bytes()
            def fail(path,data):
                if Path(path)==store.paths[0]:raise OSError('disk full')
                atomic_json(path,data)
            with patch('modules.gacha_transfer.atomic_json',side_effect=fail):
                with self.assertRaises(OSError):import_data(file,local,{},box,store,hs)
            self.assertEqual(store.paths[0].read_bytes(),before);self.assertFalse((box.active/'reward').exists());self.assertFalse((box.pack/'modules.gacha_collection.json').exists())

    def test_download_progress_known_and_unknown_size(self):
        import io
        from unittest.mock import MagicMock
        from modules.gacha_sources import SkinSources
        payload=io.BytesIO()
        with zipfile.ZipFile(payload,'w') as z:z.writestr('skin.ini','[General]')
        raw=payload.getvalue()
        for length in (str(len(raw)),None):
            with tempfile.TemporaryDirectory() as tmp:
                source=SkinSources(DEFAULTS,Path(tmp));updates=[];source.progress=lambda *v:updates.append(v)
                response=MagicMock();response.__enter__.return_value=response
                response.headers={'Content-Type':'application/octet-stream'}
                if length:response.headers['Content-Length']=length
                response.iter_content.return_value=[raw[:20],raw[20:]]
                session=MagicMock();session.__enter__.return_value=session;session.get.return_value=response
                item=dict(kind='drive',source='id.osk',drive_id='id',name='Test')
                with patch('modules.gacha_sources.session_for',return_value=session):
                    result=source.materialize(item,DEFAULTS)
                self.assertTrue(zipfile.is_zipfile(result));self.assertEqual(updates[-1][1],len(raw))
                self.assertEqual(updates[-1][2],int(length or 0));self.assertGreater(updates[-1][3],0)

    def test_transfer_multiple_slots_and_explicit_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file,local,box,store,hs=self.transfer_fixture(root)
            source=root/'source';slot=source/'slots'/'3';skin=slot/'gacha_active'/'third';skin.mkdir(parents=True);(skin/'skin.ini').write_text('[General]')
            atomic_json(slot/'modules.gacha_collection.json',{'drops':{'third':dict(id='third',name='Third',installed_name='third',favorite=True)}})
            export_data(file,dict(local,api_key='EXPLICIT-KEY'),{},source,True)
            updated,_,count=import_data(file,local,{},box,store,hs)
            self.assertEqual(count,2);self.assertEqual(updated['api_key'],'EXPLICIT-KEY')
            self.assertTrue((box.pack/'slots'/'3'/'gacha_active'/'third'/'skin.ini').exists())

    def test_bad_settings_rejected(self):
        data=dict(format='osu-gacha-transfer',version=1,settings={'interval':0},sessions=[],slots={})
        with self.assertRaises(ValueError):validate_manifest(data)

if __name__=='__main__':unittest.main()
