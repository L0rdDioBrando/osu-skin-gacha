"""osu! API v2 transport, normalized to the application's existing score model."""
from datetime import datetime, timezone
import copy
import time
import threading
import requests
from modules.gacha_api import API
from modules.gacha_rules import score_key

MODS = dict(NF=1,EZ=2,TD=4,HD=8,HR=16,SD=32,DT=64,RX=128,HT=256,
            NC=512,FL=1024,AT=2048,SO=4096,AP=8192,PF=16384,V2=536870912)

def normalize_score(raw, beatmap_id=None):
    stats=raw.get('statistics') or {}
    bits=0
    for mod in raw.get('mods',[]):
        bits |= MODS.get(mod.get('acronym') if isinstance(mod,dict) else mod,0)
    if bits&512:bits|=64
    if bits&16384:bits|=32
    date=raw.get('ended_at') or raw.get('created_at') or ''
    if date:
        date=datetime.fromisoformat(date.replace('Z','+00:00')).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    result=dict(provider='bancho',beatmap_id=str(beatmap_id or raw.get('beatmap_id') or raw.get('beatmap',{}).get('id','')),
                user_id=str(raw.get('user_id','')),date=date,enabled_mods=bits,
                score=raw.get('legacy_total_score') or raw.get('score') or raw.get('total_score',0),
                maxcombo=raw.get('max_combo',0),pp=raw.get('pp'),
                rank=raw.get('rank','F') if raw.get('passed',True) else 'F',
                score_id=raw.get('legacy_score_id'),modern_id=raw.get('id'),
                count300=stats.get('great',stats.get('count_300',0)),
                count100=stats.get('ok',stats.get('count_100',0)),
                count50=stats.get('meh',stats.get('count_50',0)),
                countmiss=stats.get('miss',stats.get('count_miss',0)),
                countgeki=stats.get('perfect',stats.get('count_geki',0)),
                countkatu=stats.get('good',stats.get('count_katu',0)))
    return result

def normalize_user(raw):
    stat=raw.get('statistics') or {}
    return dict(user_id=str(raw['id']),username=raw['username'],pp_raw=stat.get('pp') or 0,
                pp_rank=stat.get('global_rank'),pp_country_rank=stat.get('country_rank'),
                country=raw.get('country_code',''),avatar_url=raw.get('avatar_url',''),
                accuracy=stat.get('hit_accuracy',0),playcount=stat.get('play_count',0))

def normalize_map(raw):
    group=raw.get('beatmapset') or {}
    return dict(beatmap_id=str(raw['id']),beatmapset_id=str(raw.get('beatmapset_id') or group.get('id','')),
                artist=group.get('artist',''),title=group.get('title',''),creator=group.get('creator',''),
                version=raw.get('version',''),difficultyrating=raw.get('difficulty_rating',0),
                max_combo=raw.get('max_combo'),bpm=raw.get('bpm'),total_length=raw.get('total_length'),
                hit_length=raw.get('hit_length'),playcount=raw.get('playcount',0),
                diff_approach=raw.get('ar'),diff_overall=raw.get('accuracy'),diff_size=raw.get('cs'),
                diff_drain=raw.get('drain'),file_md5=raw.get('checksum'),approved=raw.get('ranked'))

class OAuthAPI(API):
    # Repeated status checks share a short cache; respect osu!'s per-resource polling guidance.
    _cache={}
    _cache_lock=threading.RLock()
    def __init__(self,settings,auth=None):
        super().__init__(settings)
        if auth is None:
            from modules.gacha_oauth import session_manager
            auth=session_manager(settings)
        self.auth=auth
        self.user=str(auth.account().get('id',''))
        if not self.user or self.user!=str(settings['user_id']):
            raise RuntimeError('Войдите в выбранный аккаунт osu! / Sign in to the selected osu! account')
        self.min_poll_interval=61

    def request(self,path,method='GET',params=None,payload=None,ttl=61):
        key=(self.user,method,path,str(params),str(payload))
        with self._cache_lock:
            cached=self._cache.get(key)
            if cached and time.monotonic()-cached[0]<ttl:return copy.deepcopy(cached[1])
            with API._request_lock:
                time.sleep(max(0,1.1-(time.monotonic()-API._last_request)))
                API._last_request=time.monotonic()
            data=self.auth.call('/api/v2/'+path,method,payload,params)
            if ttl and data is not None:
                if len(self._cache)>512:self._cache.clear()
                self._cache[key]=(time.monotonic(),copy.deepcopy(data))
            return data

    def profile(self):
        data=self.request(f'users/{self.user}/osu')
        if not data:raise RuntimeError('Профиль не найден / Profile not found')
        return normalize_user(data)

    def scores(self,kind,limit=100):
        data=self.request(f'users/{self.user}/scores/{kind}',params=dict(mode='osu',legacy_only=1,include_fails=1,limit=limit))
        if not isinstance(data,list):raise RuntimeError('Неверный ответ скоров / Invalid scores response')
        return [normalize_score(row) for row in data]

    def snapshot(self):
        return self.profile(),self.scores('best'),self.scores('recent',50)

    def beatmap(self,beatmap_id,mods):
        ident=str(int(beatmap_id));difficulty_mods=mods&(2|16|64|256|512|1024)
        if mods&512:difficulty_mods|=64
        key=(ident,difficulty_mods)
        if key not in self.maps:
            raw=self.request('beatmaps/'+ident,ttl=3600)
            if not raw:raise RuntimeError('Карта недоступна / Beatmap unavailable')
            info=normalize_map(raw)
            if difficulty_mods:
                response=self.request(f'beatmaps/{ident}/attributes','POST',payload=dict(mods=difficulty_mods,ruleset='osu'),ttl=3600)
                attrs=(response or {}).get('attributes',{})
                if 'star_rating' not in attrs:raise RuntimeError('Не получена сложность с модами / Modded difficulty unavailable')
                info.update(difficultyrating=attrs['star_rating'],max_combo=attrs.get('max_combo',info['max_combo']))
            self.maps[key]=info
        return dict(self.maps[key])

    def leaderboard(self,score):
        ident=str(int(score['beatmap_id']));plays=int(self.beatmap(ident,0).get('playcount') or 0)
        if plays<=1000:return None,plays
        data=self.request(f'beatmaps/{ident}/scores',params=dict(mode='osu',legacy_only=1,limit=100)) or {}
        for position,raw in enumerate(data.get('scores',[]),1):
            candidate=normalize_score(raw,ident)
            same=score.get('modern_id') and str(candidate.get('modern_id'))==str(score['modern_id'])
            if candidate['user_id']==self.user and (same or score_key(candidate)==score_key(score)):
                return position,plays
        return None,plays

    def user_map_scores(self,beatmap_id):
        ident=str(int(beatmap_id))
        data=self.request(f'beatmaps/{ident}/scores/users/{self.user}/all',params=dict(ruleset='osu',legacy_only=1)) or {}
        return [normalize_score(row,ident) for row in data.get('scores',[])]

    def enrich_pp(self,score):
        if score.get('pp') is not None:return score
        if score.get('rank')!='F':
            for candidate in self.user_map_scores(score['beatmap_id']):
                if score_key(candidate)==score_key(score):score=dict(score,**{k:candidate[k] for k in ('pp','modern_id','score_id')});break
        if score.get('pp') is None:
            try:score,_=self.local_maps.calculate(score,self.session)
            except (OSError,ValueError,requests.RequestException):pass
        return score

    def get(self,endpoint,**params):
        # Compatibility with internal callers; all network requests above use v2.
        if endpoint=='get_user':return [self.profile()]
        if endpoint=='get_scores':return self.user_map_scores(params['b'])
        if endpoint=='get_beatmaps':return [self.beatmap(params['b'],int(params.get('mods',0)))]
        raise ValueError('Unsupported internal API operation')
