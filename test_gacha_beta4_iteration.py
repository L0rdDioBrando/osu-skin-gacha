"""beta4: reward policy, leaderboard evidence, safe cleanup and display data."""
import copy
import queue
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from modules.gacha_app import SkinGachaApp
from modules.gacha_config import DEFAULTS
from modules.gacha_rules import reward_for,dt_reward,claimed_ranks,reward_upgrade,score_url
from modules.gacha_api import API
from modules.gacha_sources import GatariAPI
from modules.gacha_insights import chart_range,smooth_points
from modules.gacha_reports import report_body,report_parts
from modules.gacha_previews import PreviewCache
from modules.gacha_skins import Sandbox,SkinLibrary
from modules.gacha_driver import launch_osu

class Beta4Tests(unittest.TestCase):
    def test_failed_plays_never_reward(self):
        s=dict(rank='F',pp=9999,maxcombo=9999,enabled_mods=64,beatmap_id='1')
        for mode in ('Hard','Medium','Fun'):
            self.assertEqual(reward_for(mode,8000,s,10,1),'F')
            self.assertFalse(dt_reward(mode,8000,s,10,1))
            self.assertFalse(reward_upgrade(s,'SS',{}))

    def test_higher_rank_allowed_lower_and_equal_rejected(self):
        s=dict(beatmap_id='1',rank='S')
        previous=claimed_ranks([dict(score=s,reward='D',awarded=True),dict(score=s,reward='SS',awarded=False),dict(score=dict(s,rank='F'),reward='SS',awarded=True)])
        self.assertTrue(reward_upgrade(dict(s,enabled_mods=64),'C',previous))
        self.assertFalse(reward_upgrade(s,'D',previous))
        previous=claimed_ranks([dict(score=s,reward='A')])
        self.assertFalse(reward_upgrade(s,'C',previous));self.assertTrue(reward_upgrade(s,'SS',previous))

    def test_monitor_upgrades_without_farming_and_failed_special(self):
        app=object.__new__(SkinGachaApp);app.settings=dict(DEFAULTS,user_id='42',difficulty='Fun',custom_special_chance=True,rofl_chance=100)
        app.history={};app.events=queue.Queue()
        scores=[dict(beatmap_id='1',date=str(i),score=i,rank=rank,maxcombo=combo,pp=300,enabled_mods=0) for i,(rank,combo) in enumerate([('F',1600),('A',250),('A',350),('A',350),('F',1800)])]
        api=SimpleNamespace(session=SimpleNamespace(close=lambda:None),snapshot=lambda:({'pp_raw':8001},[],scores),beatmap=lambda *a:{'difficultyrating':6},enrich_pp=lambda s:s)
        waits=iter([False,True]);stop=SimpleNamespace(wait=lambda _:next(waits),is_set=lambda:False)
        app.monitor(api,({'pp_raw':8000},[],[]),stop,app.settings)
        events=list(app.events.queue)
        self.assertFalse([e for e in events if e[0]=='api_failure'])
        self.assertEqual([v for k,_,v in events if k=='roll'],['D','C','special'])
        self.assertEqual([r['awarded'] for k,_,r in events if k=='score'],[False,True,True,False,False])

    def test_bancho_leaderboard_plays_and_exact_attempt(self):
        api=object.__new__(API);api.user='42'
        score=dict(beatmap_id='8',rank='A',score_id='123')
        api.get=Mock(return_value=[dict(playcount='1000')])
        self.assertEqual(api.leaderboard(score),(None,1000));self.assertEqual(api.get.call_count,1)
        api.get=Mock(side_effect=[[dict(playcount='1001')],[dict(user_id='9',score_id='12'),dict(user_id='42',score_id='123')]])
        self.assertEqual(api.leaderboard(score),(2,1001))
        api.get=Mock(side_effect=[[dict(playcount='1001')],[dict(user_id='42',score_id='other',score='999')]])
        self.assertEqual(api.leaderboard(dict(score,score='5')),(None,1001))

    def test_bancho_recent_without_score_id(self):
        api=object.__new__(API);api.user='42'
        score=dict(beatmap_id='8',date='2026-09-13 10:20:30',score='1234',maxcombo='45',enabled_mods='64')
        row=dict(score,user_id='42',score_id='100');row.pop('beatmap_id')
        api.get=Mock(side_effect=[[dict(playcount='1200')],[row]])
        self.assertEqual(api.leaderboard(score),(1,1200))

    def test_gatari_local_playcount_and_score_id(self):
        api=object.__new__(GatariAPI);api.user='42';score=dict(beatmap_id='8',score_id='123')
        api.get=Mock(side_effect=[{'data':[{'playcount':1001}]},{'data':[{'userid':42,'id':123}]}])
        self.assertEqual(api.leaderboard(score),(1,1001))
        api.get.assert_called_with('beatmap/8/scores',mode=0)
        api.get=Mock(return_value={'data':[{'playcount':1000}]})
        self.assertEqual(api.leaderboard(score),(None,1000));self.assertEqual(api.get.call_count,1)
        self.assertIsNone(score_url(dict(score,provider='gatari')))

    def test_roulette_unique_until_pool_exhausted(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=PreviewCache(Path(tmp),{})
            for n in (1,2,6,9,25,60):
                items=[dict(id=str(i),name=str(i)) for i in range(n)]
                with patch.object(cache,'get',return_value=None):sequence=cache.prepare(items,items[-1])
                ids=[e['item']['id'] for e in sequence];span=min(25,n)
                self.assertEqual(ids[22],items[-1]['id'])
                for start in range(26-span):self.assertEqual(len(set(ids[start:start+span])),span)

    def test_graph_range_and_curve_no_overshoot(self):
        low,high=chart_range([95,96,97],'accuracy');self.assertGreater(low,94);self.assertLess(high,98)
        self.assertEqual(chart_range([100,100],'accuracy')[1],100)
        curve=smooth_points([(0,95),(100,97),(200,96)])
        self.assertEqual(curve[:2],[0,95]);self.assertEqual(curve[-2:],[200,96])
        self.assertTrue(all(95<=v<=97 for v in curve[1::2]))

    def test_logs_folded_and_secret_redacted_before_html(self):
        body=report_body('issue',['a <b> secret<&value'],secret='secret<&value')
        self.assertIn('<details>',body);self.assertNotIn('secret',body)
        description,logs=report_parts(body)
        self.assertNotIn('<details>',description);self.assertEqual(logs,'a <b> ***')

    def test_safe_cleanup_preserves_favorites_personal_other_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);box=Sandbox(root/'osu',root/'pack');box.skins.mkdir(parents=True);box.active.mkdir(parents=True)
            library=SkinLibrary(box);library.loaded=True
            for ident,fav in [('keep',True),('remove',False)]:
                (box.active/ident).mkdir();(box.active/ident/'skin.ini').write_text('skin')
                library.drops[ident]=dict(installed_name=ident,favorite=fav)
            (box.skins/'personal').mkdir();(box.pack/'slots'/'2'/'gacha_active'/'other').mkdir(parents=True)
            library.save();result=library.delete_nonfavorites()
            self.assertEqual(set(result),{'keep'});self.assertTrue((box.active/'keep'/'skin.ini').exists());self.assertFalse((box.active/'remove').exists())
            self.assertTrue((box.skins/'personal').exists());self.assertTrue((box.pack/'slots'/'2'/'gacha_active'/'other').exists())

    def test_cleanup_rejects_escape_before_deleting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);box=Sandbox(root/'osu',root/'pack');box.active.mkdir(parents=True)
            good=box.active/'good';good.mkdir()
            library=SkinLibrary(box);library.loaded=True;library.drops={'1':dict(installed_name='good'),'2':dict(installed_name='../personal')}
            with self.assertRaises(ValueError):library.delete_nonfavorites()
            self.assertTrue(good.exists())

    def test_gatari_launch_argument_and_opt_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe=Path(tmp)/'osu!.exe';exe.touch()
            with patch('modules.gacha_driver._processes',{}),patch('modules.gacha_driver.subprocess.Popen') as launch:
                launch_osu(tmp,'gatari');self.assertEqual(launch.call_args.args[0],[str(exe.resolve()),'-devserver','osugatari.ru'])
                launch_osu(tmp,'gatari',False);self.assertEqual(launch.call_args.args[0],[str(exe.resolve())])

    def test_default_cleanup_off_summary_on(self):
        self.assertFalse(DEFAULTS['allow_skin_delete']);self.assertTrue(DEFAULTS['show_session_summary'])

if __name__=='__main__':unittest.main()
