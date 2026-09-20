import requests
import customtkinter as ctk
import tkinter as tk
import webbrowser
from PIL import Image
"""UI-регрессия без API и без изменения пользовательских скинов."""
import tempfile
import time
import zipfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageGrab
from modules import skin_gacha as g


def run():
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root/'osu'/'Skins').mkdir(parents=True)
        (root/'pack').mkdir()
        config = dict(g.DEFAULTS,setup_complete=True,skin_source='folder',osu_path=str(root/'osu'),skin_pack_path=str(root/'pack'))
        with patch.object(g.SettingsStore,'load',return_value=config),patch.object(g.HistoryStore,'load',return_value={}),patch.object(g.Covers,'get',return_value=Image.new('RGB',(208,116),'#415572')),patch.object(g.SkinGachaApp,'fetch_avatar',side_effect=lambda ident,proxy=False,server='bancho':((server,ident,proxy),Image.new('RGBA',(104,104),'#8866aa'))):
            app = g.SkinGachaApp()
            app.store.paths = [root/'settings.json']
            app.history_store.paths = [root/'sessions']
            app.report_callback_exception = lambda *args:errors.append(str(args[1]))
            app.open_logs()
            app.log('Copy log smoke test')
            with patch.object(app,'clipboard_clear') as clear, patch.object(app,'clipboard_append') as append:
                app.copy_logs()
                clear.assert_called_once()
                assert 'Copy log smoke test' in append.call_args.args[0]
            assert 'Миссы: 3' in app.score_stats(dict(maxcombo=327,count300=281,countmiss=3),dict(max_combo=408))
            app.log_window.destroy()
            # Мастер завершает настройку без запуска песочницы или сетевых запросов.
            (root/'osu'/'osu!.exe').touch()
            app.settings['offline'] = True
            app.open_setup()
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            def press(text):
                next(w for w in descendants(app.setup_window) if isinstance(w,ctk.CTkButton) and w.cget('text')==text).invoke()
            press('Далее')
            press('Далее')
            press('Далее')
            press('Далее')
            controls=list(descendants(app.setup_window))
            heavy=next(w for w in controls if isinstance(w,ctk.CTkCheckBox) and w.cget('text')==app.t('exclude_heavy'))
            heavy.toggle()
            app.setup_window.update()
            assert app.setup_window.cget('fg_color')==app.theme['bg']
            press('Далее')
            press('Готово')
            assert app.settings['setup_complete'] and app.settings['offline']
            assert app.settings['exclude_heavy']
            assert app.grab_current() is None
            original_id=app.settings['user_id']
            app.apply_live_setting('user_id','18086030')
            app.apply_live_setting('server','gatari')
            assert app.settings['user_id']==''
            app.apply_live_setting('user_id','1000')
            app.apply_live_setting('server','bancho')
            assert app.settings['user_id']=='18086030'
            app.apply_live_setting('server','gatari')
            assert app.settings['user_id']=='1000'
            app.apply_live_setting('server','bancho')
            app.apply_live_setting('user_id',original_id)
            app.settings['offline'] = False
            def tick(duration=.06):
                end = time.monotonic()+duration
                while time.monotonic()<end:
                    app.update()
                    time.sleep(.005)
            score = dict(beatmap_id='1',maxcombo='840',rank='A',pp='398.23',enabled_mods='72',count300='650',count100='5',count50='0',countmiss='1')
            info = dict(beatmapset_id='1',artist='Neru feat. Kagamine Rin',title='Tokyo Teddy Bear',version='Extra',max_combo='1002',difficultyrating='6.83')
            record = dict(key=('test',),score=score,map=info,reward='SS',position=2)
            for lang in ('Русский','English'):
                for theme in g.THEMES:
                    app.settings.update(language=lang,theme=theme)
                    app.build_ui()
                    app.handle_profile({'username':'DimEl','pp_raw':'8038'})
                    app.add_card(record)
                    app.add_card(dict(record,key=('second',)))
                    tick()
                    assert len(app.cards_frame.pack_slaves()) == 2
                    app.clear_cards()
                    app.add_card(record)
                    tick()
                    assert app.cards_frame.winfo_exists()
            app.settings.update(language='Русский',theme='Dark Classic')
            app.build_ui()
            app.handle_profile({'username':'DimEl','pp_raw':'8038'})
            app.add_card(record)
            app.add_card(dict(record,score=dict(score,rank='S',pp='320.72',enabled_mods='8'),reward='A'))
            app.geometry('1120x840+80+50')
            tick(.2)
            with patch.object(app, 'check_reports'):
                app.open_reports()
                app.receive_reports([dict(number=1,title='Test issue',body='Details',state='open')])
                tick(.1)
                assert app.settings['reports_seen']==1
                app.reports_window.destroy()
            app.report_bug()
            tick(.1)
            report_window=next(w for w in app.winfo_children() if isinstance(w,g.IconWindow) and w.title()==app.t('report_bug'))
            report_window.destroy()
            app.open_settings()
            tick(.2)
            window = app.settings_window
            assert len({app.t("slot_label",n=n) for n in (1,2,3)}) == 3
            assert int(window.geometry().split("x")[0]) >= 740
            assert 'dt_bonus' not in window.variables
            assert not {'drive_folder','color','ui_motion','log_mode'} & window.variables.keys()
            assert 'show_100' in window.variables
            assert 'show_ur' not in window.variables
            assert not any(k.startswith('goal_') for k in window.variables)
            window.variables['custom_rewards'].set(True)
            window.changed('custom_rewards')
            assert app.settings['custom_rewards']
            window.variables['goal_Hard_SS'].set('2')
            window.changed('goal_Hard_SS')
            assert app.settings['goal_Hard_SS']==2
            window.variables['custom_rewards'].set(False)
            window.changed('custom_rewards')
            assert 'hide_failed' in window.variables
            assert 'skin_source' in window.variables and 'slot' in window.variables
            assert hasattr(app,'failed_var')
            assert len(window.category_frames)==6
            assert not window.variables['tablet_driver_enabled'].get()
            assert 'tablet_driver_path' in window.variables
            assert 'osu_launch_enabled' in window.variables
            assert 'rofl_pp' not in window.variables and 'rofl_chance' not in window.variables
            window.variables['custom_special_chance'].set(True)
            window.changed('custom_special_chance')
            window.variables['rofl_chance'].set('12.5')
            window.changed('rofl_chance')
            assert app.settings['rofl_chance']==5
            window.variables['rofl_chance'].set('12')
            window.changed('rofl_chance')
            assert app.settings['rofl_chance']==12 and isinstance(app.settings['rofl_chance'],int)
            window.variables['custom_special_chance'].set(False)
            window.changed('custom_special_chance')
            assert 'rofl_chance' not in window.variables
            team_text = [w.cget('text') for w in descendants(window.category_frames['team']) if isinstance(w,ctk.CTkLabel)]
            assert all(name in team_text for name in ('DimEl','anastasena','naru','scoleopa'))
            window.category_buttons['appearance'].invoke()
            tick(.1)
            assert app.grab_current() is None
            assert not window.transient()
            import ctypes
            from ctypes import wintypes
            user32=ctypes.WinDLL('user32')
            user32.GetParent.argtypes=[wintypes.HWND];user32.GetParent.restype=wintypes.HWND
            user32.GetWindowLongPtrW.argtypes=[wintypes.HWND,ctypes.c_int];user32.GetWindowLongPtrW.restype=ctypes.c_ssize_t
            hwnd=user32.GetParent(window.winfo_id())
            assert user32.GetWindowLongPtrW(hwnd,-20)&0x40000
            assert user32.GetWindowLongPtrW(hwnd,-8)==0
            assert window.category=='appearance'
            window.variables['theme'].set('Nord')
            window.changed('theme')
            assert app.settings['theme'] == 'Nord'
            window.language_changed('English')
            tick(.1)
            assert app.settings['language'] == 'English'
            window.variables['interval'].set('invalid')
            tick(.6)
            assert app.settings['interval'] == 15
            window.variables['interval'].set('20')
            tick(.6)
            assert app.settings['interval'] == 20
            window.destroy()
            assert 'Nord' in (root/'settings.json').read_text()
            app.records.extend(dict(record,key=(str(i),)) for i in range(105))
            app.show_page(0)
            assert len(app.cards) == 105
            app.show_page(1)
            assert len(app.cards) == 105
            app.show_page(-1)
            assert len(app.cards) == 105
            app.records.clear()
            app.clear_cards()
            # Архив не смешивается с текущими скорами; F фильтруется по игровому рангу.
            failed = dict(record,key=('failed',),score=dict(score,rank='F'),reward='SS')
            app.records.extend([record,failed])
            app.current_session = dict(id='20260906_120000_test',started_at='2026-09-06T12:00:00+05:00',
                ended_at=None,user_id='',username='Test',difficulty='Hard',records=[])
            app.persist_history()
            tick(.2)
            assert (root/'sessions/20260906_120000_test.json').exists()
            old_id = app.current_session['id']
            app.current_session = None
            app.records.clear()
            app.update_history_menu()
            old_label = next(k for k,v in app.history_options.items() if v == old_id)
            app.select_history(old_label)
            assert len(app.cards) == 2
            app.apply_live_setting('hide_failed',True)
            assert len(app.cards) == 1
            assert len(app.history[old_id]['records']) == 2
            app.apply_live_setting('hide_failed',False)
            assert len(app.cards) == 2
            app.selected_session = None
            app.show_page(0)
            assert len(app.cards) == 0
            app.handle_profile({'user_id':'123','username':'Avatar Test','pp_raw':'8038'})
            tick(.15)
            assert app.avatar_label.cget('image') is not None
            app.apply_live_setting('ignore_proxy',True)
            tick(.2)
            assert app.avatar_key() in app.avatar_cache
            with patch.object(webbrowser,'open') as opened:
                app.open_profile()
                opened.assert_called_once_with('https://osu.ppy.sh/users/123')
            # Штатная прокрутка CTk использует increment=1 на Windows, новая — 2.
            assert float(app.cards_frame._parent_canvas.cget('yscrollincrement')) == 2
            # Рулетка повторно, затем Stop посреди третьей анимации.
            api = type('TestAPI',(),{'session':type('Session',(),{'close':lambda self:None})()})()
            (root/'pack'/'D').mkdir()
            for index in (1,2):
                with zipfile.ZipFile(root/'pack'/'D'/f'demo{index}.osk','w') as archive:
                    archive.writestr('skin.ini',f'[General]\nName: Demo {index}')
            indexed = app.library.scan()
            app.pool,app.catalog,app.drops = indexed['pool'],indexed['catalog'],indexed['drops']
            app.sandbox.start()
            app.start_monitor(api,({'username':'Test','pp_raw':'8038'},[],[]))
            session_id = app.current_session['id']
            if True:
                app.rolls.append("D")
                if not app.rolling: app.next_roll()
                app.rolls.append("D")
                if not app.rolling: app.next_roll()
                app.apply_live_setting('theme','Steam')
                deadline = time.monotonic()+12
                while app.rolling and time.monotonic()<deadline:
                    tick(.05)
                assert app.unlocked == 2, app.unlocked
                assert not app.rolling
                assert app.roulette_strip.sequence[22]['item']['name'] in app.roulette_label.cget('text')
                from types import SimpleNamespace
                for width in (880,1600,1100):
                    app.geometry(f'{width}x900');tick(.1)
                    strip=app.roulette_strip
                    assert abs(strip.offset+22*strip.PITCH-strip.winfo_width()/2)<1
                    assert strip.entry_at(SimpleNamespace(x=strip.winfo_width()/2)) == strip.sequence[22]
                    bounds=strip.bbox('strip')
                    assert bounds[0]<0 and bounds[2]>strip.winfo_width()
                entry=strip.sequence[22]
                entry['image']=Image.new('RGB',(640,360),'#456789')
                strip.enlarge(SimpleNamespace(x=strip.winfo_width()/2))
                tick(.2)
                popup=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel) and w.title()==entry['item']['name'])
                canvas=next(w for w in popup.winfo_children() if isinstance(w,tk.Canvas))
                canvas.event_generate('<Button-1>',x=3,y=3);tick(.05)
                assert not popup.winfo_exists()
                app.rolls.append("D")
                if not app.rolling: app.next_roll()
                assert app.t('exhausted',rank='D') in app.status_label.cget('text')
                app.stop()
                tick(.2)
                assert app.state_name == 'idle'
                assert app.current_session['ended_at'] is not None
                assert (root/'sessions'/f'{session_id}.json').exists()
            app.open_collection()
            tick(.1)
            ident = next(iter(app.drops))
            app.submit(app.files,'favorites',app.library.favorite,ident,True)
            tick(.15)
            assert app.drops[ident]['favorite']
            app.export_favorite(ident)
            tick(.15)
            assert any(p.is_dir() for p in (root/'osu'/'Skins').iterdir())
            app.apply_live_setting('slot','2')
            tick(.3)
            assert not app.drops
            assert app.sandbox.slot=='2'
            app.apply_live_setting('slot','1')
            tick(.3)
            assert len(app.drops)==2
            app.collection_window.destroy()
            app.open_best()
            tick(.1)
            app.open_settings()
            tick(.1)
            app.settings_window.variables['interval'].set('25')
            app.on_close()
            app.files.shutdown(wait=True)
            app.images.shutdown(wait=True)
            app.network.shutdown(wait=True)
            try:
                if app.winfo_exists():
                    app.finish_close()
            except tk.TclError:
                pass
            assert app.settings['interval'] == 25
            assert not errors, errors
    print('UI PASS: 36 theme/language combinations, live settings, history, F filter, avatar, profile link, 2x scroll, theme during roll')


if __name__ == '__main__':
    run()
