"""Skin usage is recorded only after a reload shortcut in the osu! window."""
import os,time
from pathlib import Path
from datetime import datetime,timezone
import tkinter as tk
import customtkinter as ctk
from modules.gacha_rules import accuracy
from modules.gacha_widgets import IconWindow,FastScrollableFrame
from modules.gacha_insights import all_records,result_card


def managed_selected(app):
    from modules.gacha_skin_apply import LIVE_NAMES
    try:files=sorted(Path(app.settings['osu_path']).glob('osu!.*.cfg'),key=lambda p:p.stat().st_mtime,reverse=True)
    except OSError:return False
    for path in files:
        try:
            for line in path.read_text(encoding='utf-8-sig',errors='replace').splitlines():
                if line.startswith('Skin ='):return line.split('=',1)[1].strip() in LIVE_NAMES
        except OSError:continue
    return False


def observe_skin_reload(app):
    if os.name!='nt' or app.state_name!='running':return
    import ctypes
    user32=ctypes.windll.user32
    pressed=all(user32.GetAsyncKeyState(key)&0x8000 for key in (0x11,0x10,0x12,0x53))
    previous=getattr(app,'skin_reload_pressed',False);app.skin_reload_pressed=pressed
    if not pressed or previous or not app.applied_skin:return
    from ctypes import wintypes
    user32.GetForegroundWindow.restype=wintypes.HWND
    title=ctypes.create_unicode_buffer(512);user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user32.GetWindowTextW(user32.GetForegroundWindow(),title,512)
    if 'osu!' not in title.value.casefold() or any(v in title.value.casefold() for v in ('gacha','musicplayer','skin preview')):return
    record_skin_reload(app)

def record_skin_reload(app):
    if app.state_name!='running' or not app.applied_skin:return False
    item=next((v for v in app.drops.values() if v.get('installed_name')==app.applied_skin),None)
    if not item or not app.current_session or not managed_selected(app):return
    entry=dict(at=time.time(),skin_id=item['id'],skin_name=item['name'])
    app.current_session.setdefault('skin_usage',[]).append(entry)
    app.schedule_history()
    return True

def confirm_skin_reload(app):
    from tkinter import messagebox
    en=app.settings['language']=='English'
    if messagebox.askyesno('osu!gacha',
        'Select the current osu!gacha skin in osu!, press Ctrl+Shift+Alt+S, then confirm here before playing. Done?' if en else
        'Выбери текущий скин osu!gacha в osu!, нажми Ctrl+Shift+Alt+S, затем подтверди здесь перед игрой. Готово?',parent=app):
        if not record_skin_reload(app):
            messagebox.showinfo('osu!gacha','Start a session and select the current osu!gacha skin first.' if en else 'Сначала начни сессию и выбери текущий скин osu!gacha в игре.',parent=app)


def attribute_score(app,record):
    if record.get('skin_id') or not app.current_session or not managed_selected(app):return
    try:
        when=datetime.fromisoformat(str(record['score']['date']).replace('Z','+00:00'))
        if when.tzinfo is None:when=when.replace(tzinfo=timezone.utc)
        stamp=when.timestamp()
    except (ValueError,KeyError):return
    usage=[u for u in app.current_session.get('skin_usage',[]) if u['at']<=stamp]
    if usage:
        latest=max(usage,key=lambda u:u['at']);record.update(skin_id=latest['skin_id'],skin_name=latest['skin_name'])


def aggregate(records):
    pp=[float(r['score']['pp']) for r in records if r['score'].get('pp') is not None]
    passed=[r for r in records if r['score'].get('rank')!='F' and r['score'].get('pp') is not None]
    return dict(count=len(records),pp=sum(pp)/len(pp) if pp else None,accuracy=sum(accuracy(r['score']) for r in records)/len(records) if records else 0,
                combo=sum(int(r['score'].get('maxcombo') or 0) for r in records)/len(records) if records else 0,
                best=max(passed,key=lambda r:float(r['score']['pp'])) if passed else None)


def grouped(app):
    result={}
    for _,record in all_records(app):
        if record.get('skin_id'):result.setdefault(record['skin_id'],[]).append(record)
    return result


def open_skin_stats(app,ident):
    win=IconWindow(app);item=app.drops.get(ident,{})
    win.title(item.get('name','Скин'));win.geometry('850x710');win.configure(fg_color=app.theme['bg'])
    body=FastScrollableFrame(win,fg_color=app.theme['bg']);body.pack(fill='both',expand=True,padx=18,pady=18)
    records=grouped(app).get(ident,[]);stats=aggregate(records);en=app.settings['language']=='English'
    app.label(body,item.get('name','Skin'),size=23,bold=True).pack(anchor='w',pady=10)
    pp='—' if stats['pp'] is None else f"{stats['pp']:.1f}"
    app.label(body,(f"Scores: {stats['count']} · Average PP: {pp}\nAccuracy: {stats['accuracy']:.2f}% · Combo: {stats['combo']:.0f}" if en else f"Скоров: {stats['count']} · Средние PP: {pp}\nТочность: {stats['accuracy']:.2f}% · Комбо: {stats['combo']:.0f}"),size=16,justify='left').pack(anchor='w',pady=12)
    app.label(body,('Tracking starts after Ctrl+Shift+Alt+S in osu! with the managed current skin selected. Older scores without a skin record are excluded.' if en else 'Учёт начинается после Ctrl+Shift+Alt+S в osu! при выбранном текущем скине программы. Старые скоры без записанного скина не учитываются.'),muted=True,wraplength=730,justify='left').pack(anchor='w',pady=8)
    if stats['best']:
        app.label(body,'Best passed score' if en else 'Лучший пройденный скор',bold=True).pack(anchor='w',pady=8);result_card(app,body,stats['best'])
    app.label(body,'Scores with this skin' if en else 'Скоры с этим скином',bold=True).pack(anchor='w',pady=12)
    page=tk.IntVar(value=0);list_frame=ctk.CTkFrame(body,fg_color='transparent');list_frame.pack(fill='x')
    def show():
        for child in list_frame.winfo_children():child.destroy()
        for record in list(reversed(records))[page.get()*20:page.get()*20+20]:result_card(app,list_frame,record)
    controls=ctk.CTkFrame(body,fg_color='transparent');controls.pack(fill='x')
    def turn(delta):page.set(max(0,min(max(0,(len(records)-1)//20),page.get()+delta)));show()
    app.button(controls,'←',lambda:turn(-1),True).pack(side='left');app.button(controls,'→',lambda:turn(1),True).pack(side='right');show()
    return win


def open_skin_comparison(app):
    win=IconWindow(app);en=app.settings['language']=='English';win.title('Compare skins' if en else 'Сравнение скинов');win.geometry('930x700');win.configure(fg_color=app.theme['bg'])
    body=FastScrollableFrame(win,fg_color=app.theme['bg']);body.pack(fill='both',expand=True,padx=18,pady=18)
    app.label(body,'Choose skins with more than 10 scores' if en else 'Выберите скины, с которыми сыграно больше 10 скоров',size=20,bold=True).pack(anchor='w',pady=10)
    records={k:v for k,v in grouped(app).items() if len(v)>10};choices={}
    for ident,rows in records.items():
        var=tk.BooleanVar(value=True);choices[ident]=var;name=app.drops.get(ident,{}).get('name') or rows[0].get('skin_name',ident)
        ctk.CTkCheckBox(body,text=f'{name} · {len(rows)}',variable=var,fg_color=app.theme['accent'],text_color=app.theme['text']).pack(anchor='w',pady=5)
    table=ctk.CTkFrame(body,fg_color=app.theme['panel']);table.pack(fill='x',pady=16)
    def refresh():
        for child in table.winfo_children():child.destroy()
        headers=['Skin','Scores','Avg PP','Accuracy','Combo','Best PP'] if en else ['Скин','Скоры','Средние PP','Точность','Комбо','Лучшие PP']
        for col,label in enumerate(headers):app.label(table,label,bold=True).grid(row=0,column=col,padx=10,pady=10)
        table.grid_columnconfigure(0,weight=1)
        for index,(ident,var) in enumerate((kv for kv in choices.items() if kv[1].get()),1):
            stat=aggregate(records[ident]);best=stat['best'];name=app.drops.get(ident,{}).get('name') or records[ident][0].get('skin_name',ident)
            values=[name,str(stat['count']),'—' if stat['pp'] is None else f"{stat['pp']:.1f}",f"{stat['accuracy']:.2f}%",f"{stat['combo']:.0f}",f"{float(best['score']['pp']):.1f}" if best else '—']
            for col,value in enumerate(values):app.label(table,value,wraplength=270 if col==0 else 90).grid(row=index,column=col,padx=8,pady=10,sticky='w' if col==0 else '')
    for var in choices.values():var.trace_add('write',lambda *_:refresh())
    if not records:app.label(body,'No eligible skins yet.' if en else 'Пока нет скинов с достаточным числом скоров.',muted=True).pack(pady=15)
    refresh();return win
