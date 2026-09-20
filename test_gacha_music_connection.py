import os,tempfile,wave,unittest,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from modules.gacha_audio import audio_from_map,AudioLocator,MusicBackend
from modules.gacha_connection import state,identity,mark,describe,check
from modules.gacha_config import DEFAULTS
from modules.gacha_updates import CHANGELOG

class LatestTests(unittest.TestCase):
    def test_audio_uses_general_filename_not_hitsounds_or_background(self):
        with tempfile.TemporaryDirectory() as tmp:
            songs=Path(tmp)/'Songs';folder=songs/'123 Artist';folder.mkdir(parents=True)
            (folder/'track ü.ogg').touch();(folder/'normal-hitnormal.wav').touch()
            osu=folder/'map.osu';osu.write_text('[General]\nAudioFilename: track ü.ogg\n[Metadata]\nBeatmapID:456\n',encoding='utf-8-sig')
            self.assertEqual(audio_from_map(osu,songs),folder/'track ü.ogg')
            locator=AudioLocator(tmp)
            self.assertEqual(locator.find(dict(score={'beatmap_id':'456'},map={'beatmapset_id':'123'})),folder/'track ü.ogg')
            self.assertIsNone(locator.find(dict(score={'beatmap_id':'777'},map={'beatmapset_id':'123'})))

    def test_audio_rejects_parent_path_and_unrelated_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'Songs'/'set';folder.mkdir(parents=True);(root/'outside.mp3').touch();osu=folder/'map.osu'
            for text in ('[General]\nAudioFilename: ../../outside.mp3','[Events]\nAudioFilename: ../../outside.mp3'):
                osu.write_text(text);self.assertIsNone(audio_from_map(osu,root/'Songs'))
            self.assertIsNone(audio_from_map(osu,root/'other'))

    def test_audio_backend_decode_and_release_without_speakers(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'SDL_AUDIODRIVER':'dummy','PYGAME_HIDE_SUPPORT_PROMPT':'1'}):
            path=Path(tmp)/'silence.wav'
            with wave.open(str(path),'wb') as w:
                w.setnchannels(1);w.setsampwidth(2);w.setframerate(22050);w.writeframes(b'\0\0'*22050)
            backend=MusicBackend()
            try:
                backend.play(path);self.assertTrue(backend.busy());backend.stop();self.assertFalse(backend.busy())
                path.unlink();self.assertFalse(path.exists())
            finally:backend.close()

    def app(self):return SimpleNamespace(settings=dict(DEFAULTS,server='gatari',user_id='42',offline=False),closing=False)

    def test_connection_time_errors_and_stale_account(self):
        app=self.app();self.assertIn('не проверено',describe(app)[0])
        with patch('modules.gacha_connection.time.monotonic',return_value=100):mark(app)
        label,kind=describe(app,103);self.assertEqual(kind,'ok');self.assertEqual(label,'Gatari · подключён')
        self.assertEqual(describe(app,1000)[1],'ok')
        old=identity(app);app.settings['user_id']='43'
        mark(app,'old error',old);self.assertEqual(state(app)['error'],'');self.assertIsNone(state(app)['checked'])
        app.settings['api_key']='SECRET';mark(app,'api_key=SECRET');self.assertNotIn('SECRET',describe(app)[0]);self.assertEqual(describe(app)[1],'error')
        app.settings['offline']=True;self.assertIn('Офлайн',describe(app)[0])

    def test_manual_check_one_request_pending_and_session_closed(self):
        app=self.app();api=Mock();app.make_api=Mock(return_value=api);app.network=object();jobs=[]
        app.submit=lambda executor,kind,fn:jobs.append(fn)
        check(app);check(app);self.assertEqual(len(jobs),1)
        ident,error=jobs[0]();self.assertEqual(ident,identity(app));self.assertFalse(error);api.session.close.assert_called_once()
        api.snapshot.side_effect=RuntimeError('not connected');state(app)['pending']=False;check(app)
        self.assertIn('not connected',jobs[-1]()[1])

    def test_changelog_covers_history_in_both_languages(self):
        self.assertGreaterEqual(sum(len(items) for _,items in CHANGELOG),70)
        for _,items in CHANGELOG:
            for ru,en in items:self.assertTrue(ru.strip());self.assertTrue(en.strip())

if __name__=='__main__':unittest.main()
