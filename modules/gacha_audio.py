"""Local beatmap music, one stream, asynchronous file lookup and decoding."""
import os
import re
import queue
import struct
import weakref
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from tkinter import messagebox
from modules.gacha_sources import LocalMaps


def audio_from_map(path,songs):
    path=Path(path).resolve();songs=Path(songs).resolve()
    if not path.is_relative_to(songs) or not path.is_file() or path.stat().st_size>8*1024*1024:return None
    section=''
    for line in path.read_text(encoding='utf-8-sig',errors='replace').splitlines():
        line=line.strip()
        if line.startswith('['):section=line
        if section=='[General]' and ':' in line:
            key,value=line.split(':',1)
            if key.strip()=='AudioFilename':
                name=value.strip().strip('"').replace('\\','/')
                audio=(path.parent/name).resolve()
                if name and audio.is_relative_to(path.parent) and audio.is_file():return audio
    return None


class AudioLocator:
    def __init__(self,osu):
        self.local=LocalMaps(osu);self.songs=Path(osu)/'Songs'
    def find(self,record):
        info,score=record['map'],record['score']
        ident=str(score.get('beatmap_id') or info.get('beatmap_id') or '')
        paths=[]
        if info.get('path'):paths.append(Path(info['path']))
        for path in paths:
            audio=audio_from_map(path,self.songs)
            if audio:return audio
        set_id=str(info.get('beatmapset_id') or '')
        # Numbered set folders also work when osu!.db is absent or unsupported.
        if set_id.isdigit() and self.songs.is_dir():
            for folder in self.songs.iterdir():
                if not folder.is_dir() or not re.match(re.escape(set_id)+r'(?:\s|$)',folder.name):continue
                for path in folder.glob('*.osu'):
                    if not path.resolve().is_relative_to(self.songs.resolve()) or path.stat().st_size>8*1024*1024:continue
                    data=path.read_text(encoding='utf-8-sig',errors='replace')
                    if re.search(r'^BeatmapID\s*:\s*'+re.escape(ident)+r'\s*$',data,re.M):
                        audio=audio_from_map(path,self.songs)
                        if audio:return audio
        try:
            item=self.local.locate(score.get('map_hash') or ident)
            if item:paths.append(Path(item['path']))
        except (OSError,ValueError,EOFError,struct.error):pass
        for path in paths:
            audio=audio_from_map(path,self.songs)
            if audio:return audio
        return None


class MusicBackend:
    def __init__(self):self.mixer=None;self.volume=.35;self.offset=0;self.duration=0;self.paused=False;self.pause_position=0
    def play(self,path):
        if self.mixer is None:
            os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
            import pygame.mixer
            self.mixer=pygame.mixer
        if not self.mixer.get_init():self.mixer.init()
        self.mixer.music.load(str(path));self.mixer.music.set_volume(self.volume)
        self.offset=0;self.duration=0;self.paused=False
        try:
            from mutagen import File
            metadata=File(path)
            if metadata is not None:self.duration=float(metadata.info.length)
        except Exception:pass
        self.mixer.music.play(fade_ms=250)
    def seek(self,seconds):
        seconds=max(0,min(seconds,max(0,self.duration-.05)))
        self.mixer.music.play(start=seconds);self.offset=seconds
        if self.paused:self.mixer.music.pause();self.pause_position=seconds
    def pause(self):
        self.pause_position=self.position();self.mixer.music.pause();self.paused=True
    def resume(self):
        self.mixer.music.unpause();self.paused=False
    def position(self):
        if self.paused:return self.pause_position
        return max(0,self.offset+self.mixer.music.get_pos()/1000) if self.busy() else 0
    def set_volume(self,value):
        self.volume=max(0,min(1,value))
        if self.mixer and self.mixer.get_init():self.mixer.music.set_volume(self.volume)
    def stop(self):
        self.paused=False
        if self.mixer and self.mixer.get_init():self.mixer.music.stop();self.mixer.music.unload()
    def busy(self):return bool(self.mixer and self.mixer.get_init() and self.mixer.music.get_busy())
    def close(self):
        self.stop()
        if self.mixer:self.mixer.quit()


class AudioPlayer:
    def __init__(self,app):
        self.app=app;self.backend=MusicBackend();self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='gacha-music')
        self.events=queue.Queue();self.buttons=weakref.WeakKeyDictionary();self.locators={}
        self.token=0;self.current=None;self.origin=None;self.state='stopped';self.closed=False
        self.panel=None;self.title='';self.seeking=False;self.visible=False;self.last_track=None;self.audio_path=None
        self.timer=app.after(120,self.poll)
    def attach(self,parent,record):
        key=(self.app.settings['osu_path'],str(record['score'].get('beatmap_id') or record['map'].get('path','')))
        button=self.app.button(parent,'▶',lambda:None)
        button.configure(width=42,height=24,corner_radius=6,bg_color=self.app.theme['panel'],font=('Segoe UI',13,'bold'))
        button.configure(command=lambda:self.toggle(button,record,key))
        button.pack(side='right',padx=4,pady=2)
        self.buttons[button]=key;self.paint();return button
    def submit(self,fn):
        self.app.background_tasks[:]=[f for f in self.app.background_tasks if not f.done()]
        future=self.executor.submit(fn);self.app.background_tasks.append(future)
    def mount(self,parent):
        import customtkinter as ctk
        self.panel=ctk.CTkFrame(parent,fg_color=self.app.theme['card'],corner_radius=12)
        self.panel.grid(row=11,column=0,sticky='ew',padx=12,pady=(0,12))
        self.seekbar=ctk.CTkSlider(self.panel,from_=0,to=1,height=16,progress_color=self.app.theme['accent'],button_color=self.app.theme['accent'],button_hover_color=self.app.theme['secondary'],command=lambda _:None)
        self.seekbar.pack(fill='x',padx=12,pady=(12,2));self.seekbar.set(0)
        self.seekbar.bind('<ButtonPress-1>',lambda e:setattr(self,'seeking',True),add='+')
        self.seekbar.bind('<ButtonRelease-1>',lambda e:self.seek_to(),add='+')
        self.track_label=self.app.label(self.panel,self.title,size=11,wraplength=185,justify='left')
        self.track_label.pack(fill='x',padx=10)
        # Keep transport geometry independent of changing glyphs and clock text.
        row=ctk.CTkFrame(self.panel,height=28,fg_color='transparent');row.pack(fill='x',padx=8,pady=(2,8))
        row.grid_propagate(False)
        row.grid_rowconfigure(0,weight=1)
        row.grid_columnconfigure(2,weight=1)
        self.pause_button=self.app.button(row,'Ⅱ',self.pause_resume,True);self.pause_button.configure(width=28,height=24);self.pause_button.grid(row=0,column=0,padx=(0,3))
        b=self.app.button(row,'■',self.stop,True);b.configure(width=28,height=24);b.grid(row=0,column=1)
        self.time_label=ctk.CTkLabel(row,text='0:00',font=('Consolas',11),width=1,height=24,text_color=self.app.theme['text'])
        self.time_label.grid(row=0,column=2,sticky='ew')
        close=self.app.button(row,'×',self.hide,True);close.configure(width=24,height=24);close.grid(row=0,column=3)
        volume_row=ctk.CTkFrame(self.panel,fg_color='transparent');volume_row.pack(fill='x',padx=10,pady=(0,10))
        self.app.label(volume_row,'Громкость' if self.app.settings['language']!='English' else 'Volume',size=11).pack(side='left')
        self.volume_slider=ctk.CTkSlider(volume_row,from_=0,to=1,width=95,height=16,progress_color=self.app.theme['accent'],button_color=self.app.theme['accent'],button_hover_color=self.app.theme['secondary'],command=lambda v:self.submit(lambda:self.backend.set_volume(v)))
        self.volume_slider.set(self.backend.volume);self.volume_slider.pack(side='right',padx=3)
        folder=self.app.button(self.panel,'Открыть файл трека' if self.app.settings['language']!='English' else 'Show audio file',self.open_file,True);folder.configure(height=26);folder.pack(fill='x',padx=10,pady=(0,8))
        self.refresh_panel()
    def open_file(self):
        if self.audio_path and Path(self.audio_path).is_file():
            import subprocess
            if os.name=='nt':subprocess.Popen(['explorer.exe','/select,',str(self.audio_path)])
            else:subprocess.Popen(['xdg-open',str(Path(self.audio_path).parent)])
    def seek_to(self):
        value=self.seekbar.get();self.seeking=False;ticket=self.token
        def work():
            if ticket!=self.token or self.state not in ('playing','paused'):return
            try:self.backend.seek(value)
            except Exception:self.events.put((ticket,'seek'))
        self.submit(work)
    def refresh_panel(self):
        if not self.panel or not self.panel.winfo_exists():return
        if not self.visible:
            if self.panel.winfo_manager():self.panel.grid_remove()
            return
        button_text='Ⅱ' if self.state=='playing' else '▶'
        button_state='disabled' if self.state=='loading' else 'normal'
        if self.pause_button.cget('text')!=button_text or self.pause_button.cget('state')!=button_state:
            self.pause_button.configure(text=button_text,state=button_state)
        if not self.panel.winfo_manager():self.panel.grid()
        if self.track_label.cget('text')!=self.title:self.track_label.configure(text=self.title)
        duration=self.backend.duration
        enabled='normal' if duration and self.state in ('playing','paused') else 'disabled'
        if self.seekbar.cget('to')!=max(1,duration) or self.seekbar.cget('state')!=enabled:
            self.seekbar.configure(to=max(1,duration),state=enabled)
        position=self.backend.position() if self.state in ('playing','paused') else 0
        if not self.seeking and self.seekbar.get()!=position:self.seekbar.set(position)
        caption=f'{int(position)//60}:{int(position)%60:02} / {int(duration)//60}:{int(duration)%60:02}'
        if self.time_label.cget('text')!=caption:self.time_label.configure(text=caption)
    def paint(self):
        for button,key in list(self.buttons.items()):
            if button.winfo_exists():button.configure(text=('…' if self.state=='loading' else '▶' if self.state=='paused' else '■') if key==self.current else '▶')
    def hide(self):
        self.stop();self.visible=False;self.refresh_panel()
    def pause_resume(self):
        if self.state=='stopped':
            if self.last_track:
                button,record,key=self.last_track
                self.toggle(button() if button else None,record,key)
            return
        if self.state not in ('playing','paused'):return
        paused=self.state=='playing';self.state='paused' if paused else 'playing'
        self.submit(self.backend.pause if paused else self.backend.resume);self.paint();self.refresh_panel()
    def stop(self):
        self.token+=1;self.current=None;self.state='stopped';self.origin=None
        self.submit(self.backend.stop);self.paint();self.refresh_panel()
    def toggle(self,button,record,key):
        if self.closed:return
        if self.current==key:
            if self.state=='paused':self.pause_resume()
            else:self.stop()
            return
        self.visible=True;self.audio_path=None;self.last_track=(weakref.ref(button) if button else None,record,key)
        self.title=record['map'].get('artist','')+' — '+record['map'].get('title','')
        self.token+=1;ticket=self.token;self.current=key;self.origin=weakref.ref(button) if button else None;self.state='loading';self.paint()
        def work():
            try:
                self.backend.stop()
                locator=self.locators.setdefault(key[0],AudioLocator(key[0]))
                path=locator.find(record)
                if ticket!=self.token or self.closed:return
                if path is None:raise FileNotFoundError('local-audio')
                self.audio_path=path
                self.backend.play(path)
                self.events.put((ticket,None))
            except FileNotFoundError:self.events.put((ticket,'missing'))
            except Exception:self.events.put((ticket,'playback'))
        self.submit(work)
    def poll(self):
        if self.closed:return
        while not self.events.empty():
            ticket,error=self.events.get()
            if ticket!=self.token:continue
            origin=self.origin() if self.origin else None
            if error=='seek':
                messagebox.showinfo('osu!gacha','Seeking is unavailable for this audio format.' if self.app.settings['language']=='English' else 'Этот формат аудио не поддерживает перемотку.',parent=self.app);continue
            if error:
                self.stop()
                ru='Аудио карты не найдено в папке Songs. Установите карту в osu! и проверьте папку игры в настройках.' if error=='missing' else 'Не удалось воспроизвести трек. Проверьте устройство вывода звука и файл аудио. Обновите зависимости через install_dependencies.cmd, если программа была перенесена вручную.'
                en='Map audio was not found in Songs. Install the map in osu! and check the game folder in settings.' if error=='missing' else 'Could not play this track. Check your audio output and audio file. Run install_dependencies.cmd if you copied the app manually.'
                messagebox.showinfo('Трек карты' if self.app.settings['language']!='English' else 'Map music',en if self.app.settings['language']=='English' else ru,parent=origin.winfo_toplevel() if origin and origin.winfo_exists() else self.app)
            else:self.state='playing';self.paint()
        if self.state=='playing' and not self.backend.busy():self.stop()
        self.refresh_panel()
        self.timer=self.app.after(120,self.poll)
    def close(self):
        if self.closed:return
        self.closed=True;self.token+=1;self.app.after_cancel(self.timer)
        self.submit(self.backend.close);self.executor.shutdown(wait=False)
