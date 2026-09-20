"""Local music index and shared timing metadata. No network work on the UI thread."""
import csv
import hashlib
import json
import math
import os
import unicodedata
from pathlib import Path
from functools import lru_cache

GENRES={'1':('Не указано','Unspecified'),'2':('Видеоигры','Video game'),'3':('Аниме','Anime'),'4':('Рок','Rock'),'5':('Поп','Pop'),'6':('Другое','Other'),'7':('Юмор','Novelty'),'9':('Хип-хоп','Hip hop'),'10':('Электроника','Electronic'),'11':('Метал','Metal'),'12':('Классика','Classical'),'13':('Фолк','Folk'),'14':('Джаз','Jazz')}
LANGUAGES={'1':('Не указано','Unspecified'),'2':('Английский','English'),'3':('Японский','Japanese'),'4':('Китайский','Chinese'),'5':('Инструментальная','Instrumental'),'6':('Корейский','Korean'),'7':('Французский','French'),'8':('Немецкий','German'),'9':('Шведский','Swedish'),'10':('Испанский','Spanish'),'11':('Итальянский','Italian'),'12':('Русский','Russian'),'13':('Польский','Polish'),'14':('Другой','Other')}

def finite(value):
    try:
        value=float(value)
        return value if math.isfinite(value) and value>0 else 0
    except (ValueError,TypeError):return 0

def clock(seconds):
    seconds=int(max(0,finite(seconds)))
    return f'{seconds//60}:{seconds%60:02d}'

def safe_child(folder,name):
    if not name:return None
    folder=Path(folder).resolve()
    path=(folder/name.strip('"').replace('\\','/')).resolve()
    return path if path.is_relative_to(folder) and path.is_file() else None

def parse_osu(path, timing=True):
    """Read local metadata, uninherited BPM and first-to-last object duration."""
    path=Path(path)
    if path.stat().st_size>8*1024*1024:raise ValueError('Oversized beatmap')
    sections={};section=''
    with path.open(encoding='utf-8-sig',errors='replace') as stream:
        for line in stream:
            line=line.strip()
            if not line or line.startswith('//'):continue
            if line.startswith('['):
                section=line
                if not timing and section=='[HitObjects]':break
                continue
            if not timing and section=='[TimingPoints]':continue
            sections.setdefault(section,[]).append(line)
    meta={}
    for section in ('[General]','[Metadata]','[Difficulty]'):
        for line in sections.get(section,[]):
            if ':' in line:
                key,value=line.split(':',1);meta[key.strip()]=value.strip()
    timings=[]
    for line in sections.get('[TimingPoints]',[]):
        try:
            v=line.split(',');timings.append((float(v[0]),float(v[1]),len(v)<7 or v[6]=='1'))
        except (ValueError,IndexError):continue
    timings.sort()
    red=[(t,b) for t,b,uninherited in timings if uninherited and b>0]
    first=None;last=0;slider=finite(meta.get('SliderMultiplier')) or 1.4
    for line in sections.get('[HitObjects]',[]):
        try:
            v=line.split(',');t=float(v[2]);kind=int(v[3]);end=t
            if kind&8:end=float(v[5])
            elif kind&128:end=float(v[5].split(':')[0])
            elif kind&2:
                beat=500;sv=1
                for time,length,uninherited in timings:
                    if time>t:break
                    if uninherited and length>0:beat=length;sv=1
                    elif length<0:sv=max(.1,min(10,-100/length))
                end=t+float(v[7])*int(v[6])*beat/(slider*100*sv)
            first=t if first is None else min(first,t);last=max(last,end)
        except (ValueError,IndexError,ZeroDivisionError):continue
    weights={}
    for i,(time,beat) in enumerate(red):
        stop=red[i+1][0] if i+1<len(red) else last
        bpm=round(60000/beat,2);weights[bpm]=weights.get(bpm,0)+max(0,min(last,stop)-max(first or 0,time))
    bpm=max(weights,key=weights.get) if weights else 0
    background=None
    for line in sections.get('[Events]',[]):
        try:
            fields=next(csv.reader([line]))
            if fields[0] in ('0','Background'):
                background=safe_child(path.parent,fields[2]);break
        except (IndexError,csv.Error):continue
    audio=safe_child(path.parent,meta.get('AudioFilename',''))
    return dict(path=str(path),audio=str(audio) if audio else '',background=str(background) if background else '',
        title=meta.get('Title',''),artist=meta.get('Artist',''),source=meta.get('Source',''),
        version=meta.get('Version',''),beatmap_id=meta.get('BeatmapID',''),beatmapset_id=meta.get('BeatmapSetID',''),
        bpm=bpm,total_length=max(0,last-(first or 0))/1000)

@lru_cache(maxsize=256)
def timing_for(path,stamp):
    info=parse_osu(path)
    return {k:info[k] for k in ('bpm','total_length')}

def local_timing(path):
    try:return timing_for(str(path),Path(path).stat().st_mtime_ns)
    except (OSError,ValueError):return {}

def score_timing(info,score,settings):
    # API/local timing is stored at normal speed. Show the played speed once.
    rate=1.5 if int(score.get('enabled_mods') or 0)&(64|512) else .75 if int(score.get('enabled_mods') or 0)&256 else 1
    result=[];en=settings.get('language')=='English'
    if info.get('path') and (not info.get('bpm') or not info.get('total_length')):
        for key,value in local_timing(info['path']).items():
            if not info.get(key):info[key]=value
    duration=finite(info.get('total_length') or info.get('length'))
    bpm=finite(info.get('bpm'))
    if settings.get('show_length',True):result.append(('Length: ' if en else 'Длина: ')+(clock(duration/rate) if duration else '—'))
    if settings.get('show_bpm',True):result.append('BPM: '+(f'{bpm*rate:g}' if bpm else '—'))
    return result

def read_json(path,default):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return default

def scan_library(songs,previous,stop,progress):
    songs=Path(songs).resolve()
    if not songs.is_dir():raise ValueError('Songs')
    old={v.get('map_path'):v for v in previous};tracks={};count=0;errors=0
    for folder,dirs,files in os.walk(songs,followlinks=False):
        if stop.is_set():return None
        dirs[:]=[d for d in dirs if not Path(folder,d).is_symlink() and not getattr(Path(folder,d),'is_junction',lambda:False)()]
        for name in files:
            if stop.is_set():return None
            if not name.lower().endswith('.osu'):continue
            path=Path(folder,name)
            try:
                if not path.resolve().is_relative_to(songs):continue
                stat=path.stat();cached=old.get(str(path));stamp=[stat.st_mtime_ns,stat.st_size]
                if cached and cached.get('stamp')==stamp and Path(cached['audio']).is_file():item=dict(cached)
                else:
                    info=parse_osu(path,timing=False)
                    if not info['audio']:continue
                    ident=hashlib.sha256(info['audio'].casefold().encode()).hexdigest()[:24]
                    if ident in tracks:
                        if not tracks[ident].get('background') and info.get('background'):tracks[ident]['background']=info['background']
                        count+=1
                        continue
                    item=dict(info,id=ident,map_path=str(path),stamp=stamp,duration=0,genre_id='1',language_id='1')
                    try:
                        from mutagen import File
                        audio=File(info['audio'],easy=True)
                        if audio is not None:
                            item['duration']=float(audio.info.length)
                            item['genre_tag']=str((audio.get('genre') or [''])[0]) if audio.tags else ''
                    except Exception:pass
                if item['id'] not in tracks:tracks[item['id']]=item
                count+=1
                if count%100==0:progress(count,len(tracks),errors)
            except (OSError,ValueError):errors+=1
    progress(count,len(tracks),errors)
    return deduplicate_tracks(list(tracks.values()))[0]


def deduplicate_tracks(tracks):
    """Group difficulties/copies by artist/title and near-identical duration; retain IDs as aliases."""
    def norm(value):return ' '.join(unicodedata.normalize('NFKC',str(value)).casefold().split())
    groups={};result=[];aliases={}
    for original in tracks:
        track=dict(original);name=(norm(track.get('artist','')),norm(track.get('title','')))
        if not all(name):name=('file',norm(track.get('audio',track['id'])))
        duration=finite(track.get('duration'));candidates=groups.setdefault(name,[])
        target=next((t for t in candidates if (duration and finite(t.get('duration')) and abs(duration-finite(t.get('duration')))<=2) or t.get('audio')==track.get('audio')),None)
        if target is None:
            target=track;target['aliases']=list(track.get('aliases',[]));candidates.append(target);result.append(target)
        else:
            if not target.get('background') and track.get('background'):target['background']=track['background']
            for field in ('source','genre_tag'):
                if not target.get(field) and track.get(field):target[field]=track[field]
            for field in ('genre_id','language_id'):
                if str(target.get(field,'1')) in ('0','1') and str(track.get(field,'1')) not in ('0','1'):target[field]=track[field]
        for ident in [track['id']]+track.get('aliases',[]):
            aliases[ident]=target['id']
            if ident!=target['id'] and ident not in target['aliases']:target['aliases'].append(ident)
    return result,aliases
