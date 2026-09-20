import copy
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from modules.gacha_config import DEFAULTS
from modules.gacha_api_v2 import OAuthAPI,normalize_score,normalize_user
from modules.gacha_oauth import SessionManager,SessionStore,AuthError,SERVER
from modules.gacha_rules import reward_for,score_url

class MemoryStore:
    def __init__(self):self.data={}
    def load(self):return copy.deepcopy(self.data)
    def save(self,data):self.data=copy.deepcopy(data)
    def clear(self):self.data={}

class OAuthTests(unittest.TestCase):
    def test_score_adapter_and_failed_reward(self):
        raw=dict(id=123,legacy_score_id=45,user_id=6,beatmap_id=10,ended_at='2026-09-14T12:00:00Z',legacy_total_score=987,
            max_combo=999,passed=False,rank='A',pp=200,mods=[{'acronym':'NC'}],statistics=dict(great=95,ok=3,meh=1,miss=1))
        score=normalize_score(raw)
        self.assertEqual(score['rank'],'F');self.assertEqual(score['enabled_mods'],576)
        self.assertEqual(score['score'],987);self.assertEqual(score['count100'],3)
        self.assertEqual(score['date'],'2026-09-14 12:00:00')
        self.assertEqual(reward_for('Fun',1000,score,8),'F')
        score['rank']='A';self.assertEqual(score_url(score),'https://osu.ppy.sh/scores/123')

    @patch('modules.gacha_api_v2.time.sleep')
    def test_v2_worker_only_routes_and_modded_stars(self,sleep):
        auth=Mock();auth.account.return_value={'id':6};OAuthAPI._cache.clear()
        def response(path,method,payload,params):
            if path.endswith('/osu'):return dict(id=6,username='Fixture',statistics={'pp':1800})
            if path.endswith('/attributes'):self.assertEqual(payload['mods']&64,64);return {'attributes':{'star_rating':6.9,'max_combo':1234}}
            if path=='/api/v2/beatmaps/10':return dict(id=10,difficulty_rating=4.5,playcount=1001,beatmapset={'title':'Track'})
            return []
        auth.call.side_effect=response;api=OAuthAPI(dict(DEFAULTS,user_id='6'),auth)
        user,best,recent=api.snapshot();self.assertEqual(user['pp_raw'],1800)
        self.assertEqual(api.beatmap(10,576)['difficultyrating'],6.9)
        for call in auth.call.call_args_list:self.assertTrue(call.args[0].startswith('/api/v2/'))
        self.assertEqual(auth.call.call_args_list[2].args[3]['include_fails'],1)
        self.assertFalse(hasattr(auth,'access_token') and auth.access_token.called)
        api.session.close()

    def test_browser_login_binds_verifier_and_sanitizes_response(self):
        store=MemoryStore();manager=SessionManager(DEFAULTS,store);ident='a'*64
        def call(path,method,payload,**kw):
            if path=='/desktop/start':return dict(id=ident,login_url=SERVER+'/login?desktop='+ident)
            return dict(status='complete',session=ident+'.'+payload['verifier'],expires_at=9999999999,
                        access_token='must-not-persist',refresh_token='must-not-persist',user={'id':6,'username':'Fixture','access_token':'must-not-persist'})
        manager.call=Mock(side_effect=call);cancel=Mock();cancel.is_set.return_value=False;cancel.wait.return_value=False
        with patch('modules.gacha_oauth.webbrowser.open',return_value=True):data=manager.login(cancel)
        manager.accept(data)
        self.assertNotIn('must-not-persist',str(store.data))
        self.assertEqual(SessionManager(DEFAULTS,store).account()['id'],6)

    def test_rejects_foreign_browser_url(self):
        manager=SessionManager(DEFAULTS,MemoryStore());manager.call=Mock(return_value={'id':'a'*64,'login_url':'https://attacker.invalid'})
        with patch('modules.gacha_oauth.webbrowser.open') as browser:
            with self.assertRaises(AuthError):manager.login(threading.Event())
            browser.assert_not_called()

    def test_logout_failure_can_be_retried(self):
        store=MemoryStore();store.data={'session':'test','user':{'id':6}}
        manager=SessionManager(DEFAULTS,store);manager.call=Mock(side_effect=AuthError('offline'))
        with self.assertRaises(AuthError):manager.logout()
        self.assertTrue(manager.available())
        manager.call=Mock(return_value={'ok':True});manager.logout();self.assertFalse(manager.available());self.assertEqual(store.data,{})

    def test_dpapi_session_is_not_plaintext(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=SessionStore(Path(temporary)/'session');data={'session':'private-gacha-session','user':{'id':6}}
            store.save(data);self.assertNotIn(b'private-gacha-session',store.path.read_bytes());self.assertEqual(store.load(),data)
            store.clear();self.assertEqual(store.load(),{})

if __name__=='__main__':unittest.main()
