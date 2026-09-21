"""Exercise actual settings/wizard with fake auth and temporary application data."""
import copy,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from modules.gacha_app import SkinGachaApp
from modules.gacha_config import DEFAULTS
from modules.gacha_storage import SettingsStore,HistoryStore
from modules.gacha_oauth import AuthPanel,SessionManager
from tests.test_gacha_oauth import MemoryStore

def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)

class OAuthUI(unittest.TestCase):
    def test_settings_login_logout_and_wizard(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);osu=root/'osu';(osu/'Skins').mkdir(parents=True);(osu/'osu!.exe').touch();(root/'pack').mkdir()
            config=dict(DEFAULTS,setup_complete=True,offline=False,server='bancho',user_id='',api_key='',
                        osu_path=str(osu),skin_pack_path=str(root/'pack'),skin_source='folder',animations=False)
            manager=SessionManager(config,MemoryStore())
            manager.login=Mock(return_value={'session':'a'*64+'.'+'b'*64,'expires_at':9999999999,'user':dict(id=6,username='Fixture',pp=1000)})
            manager.call=Mock(return_value={'ok':True})
            with patch('modules.gacha_oauth._manager',manager),patch.object(SettingsStore,'load',return_value=config),patch.object(HistoryStore,'load',return_value={}),patch.object(SkinGachaApp,'refresh_pool'),patch.object(SkinGachaApp,'request_avatar'):
                app=SkinGachaApp();app.store.paths=[root/'settings.json'];app.history_store.paths=[root/'sessions'];errors=[]
                app.report_callback_exception=lambda *args:errors.append(str(args[1]))
                def tick():
                    until=time.monotonic()+.3
                    while time.monotonic()<until:app.update();time.sleep(.005)
                try:
                    app.open_settings();tick();window=app.settings_window
                    self.assertNotIn('api_key',window.variables);self.assertNotIn('user_id',window.variables)
                    panel=next(w for w in descendants(window) if isinstance(w,AuthPanel));panel.run();tick()
                    self.assertEqual(app.settings['user_id'],'6');self.assertEqual(app.username,'Fixture')
                    panel=next(w for w in descendants(window) if isinstance(w,AuthPanel));panel.run();tick()
                    self.assertEqual(app.settings['user_id'],'');self.assertFalse(manager.available())
                    window.variables['server'].set('gatari');window.changed('server');tick()
                    self.assertIn('user_id',window.variables);self.assertNotIn('api_key',window.variables)
                    window.variables['server'].set('bancho');window.changed('server');tick();window.destroy()
                    app.open_setup();tick()
                    for _ in range(2):
                        next(w for w in descendants(app.setup_window) if getattr(w,'cget',None) and w.winfo_class()=='Frame' and isinstance(w,__import__('customtkinter').CTkButton) and w.cget('text')=='Далее').invoke();tick()
                    self.assertTrue(any(isinstance(w,AuthPanel) for w in descendants(app.setup_window)))
                    self.assertFalse(errors,errors)
                finally:
                    app.on_close()
                    until=time.monotonic()+5
                    while not app.destroyed and time.monotonic()<until:app.update();time.sleep(.01)

if __name__=='__main__':unittest.main()
