import io, tempfile, unittest, wave, os
from pathlib import Path
from unittest.mock import Mock,patch
from types import SimpleNamespace
import requests,zipfile
from modules.gacha_config import DEFAULTS,RANKS
from modules.gacha_rules import stars_threshold,pp_thresholds,rank_thresholds,reward_for
from modules.gacha_sources import SkinSources
from modules.gacha_skin_apply import LIVE_NAMES,MARKER,OWNER,set_live_language,owned_live
from modules.gacha_storage import atomic_json
from modules.gacha_audio import AudioLocator,MusicBackend
from modules.gacha_insights import map_records

class HarmonyTests(unittest.TestCase):
    def test_balance(self):
        for pp,expected in ((1000,2.32),(8038,5.01),(32191,7.22)):
            self.assertAlmostEqual(stars_threshold(pp),expected,delta=.01)
        self.assertEqual(stars_threshold(100000),7.5)
        for pp in (0,1000,8038,32191,100000):
            values=list(pp_thresholds(pp).values())
            self.assertEqual(values,sorted(values,reverse=True));self.assertGreater(min(values),0);self.assertLessEqual(max(values),900)
            self.assertEqual(reward_for('Medium',pp,dict(rank='A',pp=0),3),'F')
    def test_multiplier_and_failed_scores(self):
        a=dict(DEFAULTS,custom_rewards=True,reward_scale=1)
        b=dict(a,reward_scale=1.5)
        self.assertEqual(stars_threshold(1000,b),stars_threshold(1000,a)*1.5)
        self.assertGreater(rank_thresholds('Fun',b)['SS'],rank_thresholds('Fun',a)['SS'])
        self.assertLessEqual(rank_thresholds('Hard',b)['D'],rank_thresholds('Hard',a)['D'])
        self.assertEqual(reward_for('Fun',1000,dict(rank='F',maxcombo=10000),20,settings=b),'F')
    def test_live_language_roundtrip_and_no_personal_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a=root/LIVE_NAMES[0];a.mkdir();atomic_json(a/MARKER,OWNER);(a/'skin.ini').write_text('original')
            box=SimpleNamespace(skins=root,language='Русский',lock_file=True)
            set_live_language(box,'English');self.assertFalse(a.exists());b=root/LIVE_NAMES[1]
            self.assertEqual((b/'skin.ini').read_text(),'original');self.assertTrue(owned_live(b))
            set_live_language(box,'Русский');self.assertTrue(a.exists())
            b.mkdir();(b/'personal.txt').write_text('keep')
            with self.assertRaises(ValueError):set_live_language(box,'English')
            self.assertEqual((a/'skin.ini').read_text(),'original');self.assertEqual((b/'personal.txt').read_text(),'keep')
            self.assertEqual(box.language,'Русский')
    def test_prepare_live_is_idempotent_and_preserves_reward(self):
        from modules.gacha_skins import Sandbox
        from modules.gacha_skin_apply import ensure_live,live_paths
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'osu'/'Skins').mkdir(parents=True);(root/'pack').mkdir()
            box=Sandbox(root/'osu',root/'pack');box.language='English'
            ensure_live(box);live=live_paths(box)[0]
            self.assertTrue((live/'skin.ini').exists());self.assertTrue(owned_live(live))
            (live/'skin.ini').write_text('reward');ensure_live(box)
            self.assertEqual((live/'skin.ini').read_text(),'reward');self.assertFalse(box.lock_file)
    def test_lower_multiplier(self):
        settings=dict(DEFAULTS,custom_rewards=True,reward_scale=.5)
        self.assertEqual(rank_thresholds('Fun',settings)['A'],375)
        self.assertEqual(stars_threshold(1000,settings),2.5)
        self.assertGreater(rank_thresholds('Hard',settings)['A'],rank_thresholds('Hard',DEFAULTS)['A'])
        self.assertLessEqual(rank_thresholds('Hard',settings)['D'],100)
    def test_fast_audio_lookup_does_not_parse_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'Songs'/'123 Test';folder.mkdir(parents=True)
            (folder/'a.mp3').touch();(folder/'map.osu').write_text('[General]\nAudioFilename:a.mp3\n[Metadata]\nBeatmapID:456')
            locator=AudioLocator(tmp)
            with patch.object(locator.local,'locate',side_effect=AssertionError('slow path')):
                self.assertEqual(locator.find(dict(score=dict(beatmap_id=456),map=dict(beatmapset_id=123))),folder/'a.mp3')
    def test_seek_and_shared_volume(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,SDL_AUDIODRIVER='dummy'):
            path=Path(tmp)/'test.wav'
            with wave.open(str(path),'wb') as out:
                out.setnchannels(1);out.setsampwidth(2);out.setframerate(22050);out.writeframes(b'\0\0'*22050*10)
            backend=MusicBackend()
            try:
                backend.set_volume(.2);backend.play(path);self.assertAlmostEqual(backend.duration,10,delta=.1)
                backend.seek(5);self.assertGreaterEqual(backend.position(),5)
                backend.pause();position=backend.position()
                import time
                time.sleep(.08);self.assertEqual(backend.position(),position)
                backend.resume();self.assertTrue(backend.busy())
                backend.stop();backend.play(path);self.assertAlmostEqual(backend.volume,.2)
            finally:backend.close()
    def test_retry_stream_starts_clean(self):
        payload=io.BytesIO()
        with zipfile.ZipFile(payload,'w') as archive:archive.writestr('skin.ini','[General]')
        data=payload.getvalue()
        bad=Mock();bad.__enter__=Mock(return_value=bad);bad.__exit__=Mock(return_value=False);bad.headers={'Content-Length':str(len(data))}
        def broken(_):
            yield b'partial bytes'
            raise requests.ConnectionError('10054')
        bad.iter_content=broken
        good=Mock();good.__enter__=Mock(return_value=good);good.__exit__=Mock(return_value=False);good.headers={'Content-Length':str(len(data))};good.iter_content.return_value=[data]
        session=Mock();session.__enter__=Mock(return_value=session);session.__exit__=Mock(return_value=False);session.get.side_effect=[bad,good]
        with tempfile.TemporaryDirectory() as tmp,patch('modules.gacha_sources.session_for',return_value=session),patch('modules.gacha_sources.time.sleep'):
            source=SkinSources(dict(DEFAULTS),Path(tmp));item=dict(kind='drive',source='drive-x.osk',drive_id='x',name='winner')
            target=source.materialize(item,dict(DEFAULTS));self.assertEqual(target.read_bytes(),data);self.assertFalse(target.with_suffix('.part').exists());self.assertEqual(session.get.call_count,2)
    def test_map_progress_excludes_other_difficulties(self):
        def record(ident,mods):return dict(score=dict(beatmap_id=ident,enabled_mods=mods),map={})
        a=record('1',0);b=record('1',64);c=record('2',0)
        with patch('modules.gacha_insights.all_records',return_value=[(1,a),(2,b),(3,c)]):
            self.assertEqual(map_records(None,a),[(1,a),(2,b)])

if __name__=='__main__':unittest.main()
