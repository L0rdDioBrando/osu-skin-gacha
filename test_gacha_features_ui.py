"""New windows on isolated data: no real accounts, folders, or API calls."""
import tempfile,time,copy
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timedelta
from PIL import Image,ImageGrab
import customtkinter as ctk
from modules.gacha_app import SkinGachaApp
from modules.gacha_config import DEFAULTS
from modules.gacha_storage import SettingsStore,HistoryStore,atomic_json
from modules.gacha_previews import PreviewCache
from modules.gacha_insights import open_progress,open_summary,all_records,comparison_index
from modules.gacha_api import Covers
from modules.gacha_skin_apply import LIVE_NAME
from test_gacha_features import record


def run():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);(root/'osu'/'Skins').mkdir(parents=True);(root/'pack').mkdir()
        config=dict(DEFAULTS,setup_complete=True,offline=True,skin_source='folder',osu_path=str(root/'osu'),skin_pack_path=str(root/'pack'))
        with patch.object(SettingsStore,'load',return_value=config),patch.object(HistoryStore,'load',return_value={}),patch.object(Covers,'get',return_value=None),patch.object(PreviewCache,'get',return_value=Image.new('RGB',(208,117),'#554777')):
            app=SkinGachaApp();app.store.paths=[root/'settings.json'];app.history_store.paths=[root/'sessions'];errors=[]
            app.report_callback_exception=lambda *args:errors.append(str(args[1]))
            def tick(n=.3):
                end=time.monotonic()+n
                while time.monotonic()<end:app.update();time.sleep(.01)
            tick()
            app.library.loaded=True
            for i in range(15):
                name=f'Reward {i}';folder=app.sandbox.active/name;folder.mkdir(parents=True);(folder/'skin.ini').write_text('[General]')
                app.library.drops[str(i)]=dict(id=str(i),name=name,installed_name=name,rank='A' if i%2 else 'B',favorite=i%3==0,unlocked_at=datetime.now().astimezone().isoformat(),status='complete')
            app.library.save();app.drops=copy.deepcopy(app.library.drops)
            app.open_collection();tick(.6);gallery=app.collection_window
            assert gallery.pages==2
            gallery.body._parent_canvas.yview_moveto(1);gallery.turn(1);tick();assert gallery.body._parent_canvas.yview()[0]<.01
            gallery.turn(-1)
            gallery.query.set('Reward 14');tick(.6);assert '1' in gallery.count.cget('text')
            gallery.query.set('');gallery.favorite.set(True);gallery.reset();tick();assert '5' in gallery.count.cget('text')
            gallery.favorite.set(False);gallery.reset();gallery.apply('0');tick(.6)
            assert (app.sandbox.skins/LIVE_NAME/'skin.ini').exists()
            app.open_settings();tick();settings=app.settings_window
            assert not settings.include_key.get()
            assert 'allow_skin_delete' in settings.variables and not settings.variables['allow_skin_delete'].get()
            assert settings.variables['show_session_summary'].get() and settings.variables['gatari_launch'].get()
            settings.search_var.set('драйвер');tick()
            assert not any(b.winfo_manager() for b,d in settings.searchable)
            settings.toggle_category('skins');tick()
            visible=[d for block,d in settings.searchable if block.winfo_manager()]
            assert settings.search_headers['skins'].winfo_manager()
            assert visible and all('драйвер' in d.casefold() for d in visible),visible
            settings.search_var.set('шанс');tick();settings.toggle_category('rewards');tick()
            assert any('шанс' in d.casefold() for b,d in settings.searchable if b.winfo_manager())
            settings.navigate_category('rewards');tick();assert settings.search_var.get()=='' and settings.category=='rewards'
            settings.search_var.set('zzznothing');tick();assert not any(f.winfo_manager() for f in settings.category_frames.values())
            settings.search_var.set('');tick()
            for scale in ('90%','125%','100%'):app.apply_live_setting('ui_scale',scale);tick()
            settings.destroy();gallery.geometry('700x600');tick(.5);assert gallery.columns==2
            gallery.geometry('960x740');tick(.5)
            session=dict(id='test',user_id='',server='bancho',slot='1',offline=True,started_at='2026-09-01T12:00:00',ended_at='2026-09-10T13:00:00',records=[],drops=[dict(name='Reward 0',rank='B')])
            for i in range(10):
                r=record(100+i*10,2,pp=20+i);r['key']=[i];r['score']['date']=f'2026-09-{i+1:02d}T12:00:00';r['map']=dict(artist='Artist',title='Test map',version='Hard')
                session['records'].append(r)
            app.history={'test':session};app.comparison_cache=comparison_index(all_records(app))
            graph=open_progress(app);tick();summary=open_summary(app,session);tick()
            from modules.gacha_updates import open_session_search,open_changelog,animate_pp
            from modules.gacha_insights import open_day
            app.history={str(i):dict(session,id=f'session-secret-{i}',started_at=f'2026-09-{i+1:02d}T12:00:00') for i in range(13)}
            app.update_history_menu();tick();assert app.history_search.winfo_manager()
            assert not any('secret' in label for label in app.history_options)
            search=open_session_search(app);tick();search.destroy()
            changes=open_changelog(app);tick();changes.destroy()
            detail=open_day(app,'2026-09-01',False);tick();detail.destroy()
            animate_pp(app,3.14);tick(.15);assert app.pp_bubble.winfo_exists()
            tick(1.3);assert not app.pp_bubble.winfo_exists()
            app.settings['show_session_summary']=False
            original=open_summary
            from modules.gacha_previews import open_preview
            enlarged=open_preview(gallery,dict(item=dict(name='Preview'),image=Image.new('RGB',(208,117),'#554777'),path=None));tick();assert enlarged.winfo_exists();enlarged.destroy()
            # Every score cover carries one audio control; no sound/device/network in this UI test.
            player=app.audio_player
            assert player.buttons
            with patch.object(player,'backend') as backend,patch('modules.gacha_audio.AudioLocator.find',return_value=root/'sample.mp3'):
                backend.busy.return_value=True;backend.duration=120;backend.volume=.35;backend.position.return_value=10
                button=next(b for b in player.buttons if b.winfo_exists())
                key=player.buttons[button]
                player.toggle(button,session['records'][0],key);tick(.4);assert player.state=='playing'
                player.toggle(button,session['records'][0],key);tick(.2);assert player.state=='stopped'


            app.sandbox.start(True);app.state_name='running';app.current_session=dict(session,id='current',ended_at=None,records=[],drops=[]);app.settings['keep_current_skin']=True
            with patch('modules.gacha_app.update_live') as update:
                app.events.put(('installed',None,dict(app.drops['1'])));tick(.5)
                update.assert_not_called()
            with patch('modules.gacha_app.open_summary') as automatic_summary:
                app.stop();tick(.8);automatic_summary.assert_not_called()
            assert app.current_session['drops'][0]['id']=='1'
            app.open_settings();tick();app.settings_window.search_var.set('драйвер');tick()
            out=Path('test-output');out.mkdir(exist_ok=True)
            for win,name in [(gallery,'collection-new.png'),(graph,'score-progress.png'),(summary,'session-summary.png'),(app.settings_window,'settings-search.png')]:
                win.lift();tick(.3)
                ImageGrab.grab(window=int(win.frame(),0)).save(out/name)
            app.on_close()
            while not app.destroyed:tick(.05)
            try:
                while app.winfo_exists():app.update();time.sleep(.01)
            except Exception:pass
            assert not errors,errors
            print('FEATURE UI PASS: gallery, filters, application, search, scale, trends, summary, keep-current, isolated session')
if __name__=='__main__':run()
