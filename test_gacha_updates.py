import queue
import unittest
from types import SimpleNamespace
from modules.gacha_app import SkinGachaApp
from modules.gacha_config import DEFAULTS, tr
from unittest.mock import Mock, patch
from modules import gacha_bootstrap as bootstrap


class UpdateTests(unittest.TestCase):
    def test_special_gain_boundary_and_default_chance(self):
        from modules.gacha_rules import special_gain, special_chance
        self.assertTrue(special_gain(8038,8038.1))
        self.assertFalse(special_gain(8038,8038.099))
        self.assertFalse(special_gain(8038,8037))
        self.assertEqual(special_chance(dict(rofl_chance=100)),5)
        self.assertEqual(special_chance(dict(custom_special_chance=True,rofl_chance=17)),17)

    def test_cyrillic_paste_for_all_input_classes(self):
        from modules.gacha_widgets import enable_paste
        root=Mock();enable_paste(root)
        classes={call.args[0] for call in root.bind_class.call_args_list}
        self.assertTrue({'Entry','Text','TEntry'}<=classes)
        callback=root.bind_class.call_args_list[0].args[2]
        widget=Mock()
        self.assertEqual(callback(SimpleNamespace(keycode=86,keysym='Cyrillic_em',widget=widget)),'break')
        widget.event_generate.assert_called_once_with('<<Paste>>')

    def test_search_before_top_100_and_case_insensitive(self):
        app = object.__new__(SkinGachaApp)
        app.settings = dict(DEFAULTS)
        app.history = {}
        app.records = [dict(score=dict(beatmap_id=str(i),pp=i,maxcombo=i,rank='A',enabled_mods=64),
                            map=dict(artist='Artist',title='Rare Song' if i==0 else 'Another',version='Insane'))
                       for i in range(120)]
        self.assertEqual(len(app.best_records('pp')),100)
        found=app.best_records('pp',query='RARE dt')
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]['score']['beatmap_id'],'0')
        self.assertEqual(app.best_records('pp',query='does not exist'),[])

    def monitor(self, history):
        app = object.__new__(SkinGachaApp)
        app.settings = dict(DEFAULTS, user_id='42', custom_special_chance=True, rofl_chance=100, rofl_pp=0)
        app.history = history
        app.events = queue.Queue()
        scores = [dict(beatmap_id=b, date=str(n), score=str(n), rank='A',
                       maxcombo=1000, enabled_mods=mods, pp=400)
                  for n, (b, mods) in enumerate([('1',0), ('1',64), ('2',0)])]
        profile = {'pp_raw':8001}
        api = SimpleNamespace(session=SimpleNamespace(close=lambda:None),
            snapshot=lambda:(profile, scores, scores), leaderboard=lambda score:(1,1001),
            beatmap=lambda *a:{'difficultyrating':7}, enrich_pp=lambda s:s)
        waits = iter([False, True])
        stop = SimpleNamespace(wait=lambda _:next(waits), is_set=lambda:False)
        app.monitor(api, ({'pp_raw':8000}, [], []), stop, app.settings)
        events = list(app.events.queue)
        self.assertFalse([v for k,_,v in events if k=='api_failure'])
        return [v for k,_,v in events if k=='roll'], [v for k,_,v in events if k=='score']

    def test_retries_and_mods_do_not_farm(self):
        rolls, records = self.monitor({})
        self.assertEqual(rolls, ['SS','SS','special'])
        self.assertEqual([r['awarded'] for r in records], [True,False,True])

    def test_history_blocks_rewards_and_special_bonus(self):
        history = {'old':dict(user_id='42',slot='1',records=[
            dict(score={'beatmap_id':b},reward='SS') for b in ('1','2')])}
        rolls, records = self.monitor(history)
        self.assertEqual(rolls, [])
        self.assertTrue(all(not r['awarded'] for r in records))
        history['old']['slot']='2'
        self.assertEqual(len(self.monitor(history)[0]), 3)

    def test_best_filter_is_applied_before_top_100(self):
        app = object.__new__(SkinGachaApp)
        app.settings = DEFAULTS.copy()
        app.history = {}
        app.records = [dict(score=dict(beatmap_id=str(n),rank='F',pp=1000),map={}) for n in range(101)]
        app.records.append(dict(score=dict(beatmap_id='ok',rank='A',pp=10),map={}))
        self.assertEqual(len(app.best_records('pp',True)),1)
        self.assertEqual(len(app.records),102)

    def test_slot_labels_are_distinct_in_both_languages(self):
        for language in ('Русский','English'):
            self.assertEqual(len({tr('slot_label',language,n=n) for n in ('1','2','3')}),3)
        self.assertFalse(DEFAULTS['keep_personal'])

    def test_first_launch_installs_dependencies_then_runs(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);exe=root/'.venv'/'Scripts'/'python.exe'
            (root/'requirements.txt').write_text('requests')
            calls=[]
            def command(args,env):
                calls.append(args)
                if 'venv' in args:exe.parent.mkdir(parents=True);exe.touch()
            with patch.object(bootstrap,'ROOT',root),patch.object(bootstrap,'ENV_PYTHON',exe),patch.object(bootstrap,'probe',return_value=True),patch.object(bootstrap,'command',side_effect=command),patch.object(bootstrap.subprocess,'call',return_value=0) as launch,patch.object(bootstrap.sys,'argv',['bootstrap']):
                self.assertEqual(bootstrap.main(),0)
                self.assertTrue(any('venv' in args for args in calls))
                self.assertTrue(any('pip' in args for args in calls));launch.assert_called_once()

    def test_existing_environment_does_not_install_again(self):
        import tempfile
        from pathlib import Path
        from test_gacha_bootstrap import BootstrapTests
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);exe=BootstrapTests().fixture(root)
            with patch.object(bootstrap,'ROOT',root),patch.object(bootstrap,'ENV_PYTHON',exe),patch.object(bootstrap,'probe',return_value=True),patch.object(bootstrap,'command') as command,patch.object(bootstrap.subprocess,'call',return_value=0),patch.object(bootstrap.sys,'argv',['bootstrap']):
                self.assertEqual(bootstrap.main(),0);command.assert_not_called()


class CustomRewardTests(unittest.TestCase):
    def test_custom_thresholds_and_default_toggle(self):
        from modules.gacha_rules import reward_for
        settings=dict(DEFAULTS,custom_rewards=True,goal_Hard_SS=1,goal_Medium_SS=900,goal_Fun_SS=2000,goal_stars=8)
        score=dict(rank='A',pp=500,maxcombo=1500)
        self.assertEqual(reward_for('Hard',8000,score,7,2,settings),'S')
        self.assertNotEqual(reward_for('Medium',8000,score,7,None,settings),'SS')
        self.assertEqual(reward_for('Fun',8000,score,7,None,settings),'F')
        settings['custom_rewards']=False
        self.assertEqual(reward_for('Hard',8000,score,7,2,settings),'SS')

    def test_score_display_switches_and_missing_ur(self):
        app=object.__new__(SkinGachaApp);app.settings=dict(DEFAULTS,show_ur=True)
        score=dict(count100=12,count50=3,count300=100)
        text=app.score_stats(score,{})
        self.assertIn('100: 12',text);self.assertIn('50: 3',text)
        self.assertNotIn('UR:',text);self.assertIn('Точность:',text);self.assertNotIn('Accuracy',text)
        app.settings['show_100']=False
        self.assertNotIn('100: 12',app.score_stats(score,{}))


class BestSortingTests(unittest.TestCase):
    def test_pp_and_combo_choose_different_leaders(self):
        app=object.__new__(SkinGachaApp);app.settings=DEFAULTS.copy();app.history={}
        app.records=[dict(score=dict(beatmap_id='1',rank='A',pp=200,maxcombo=100),map={}),
                     dict(score=dict(beatmap_id='2',rank='S',pp=100,maxcombo=900),map={})]
        self.assertEqual(app.best_records('pp')[0]['score']['beatmap_id'],'1')
        self.assertEqual(app.best_records('combo')[0]['score']['beatmap_id'],'2')
        self.assertIn('Комбо: 100/',app.score_stats(app.records[0]['score'],{}))


class ModdedStarsTests(unittest.TestCase):
    def test_dt_nc_request_modded_stars_and_do_not_use_nm_cache(self):
        from modules.gacha_api import API
        api=object.__new__(API);api.maps={}
        api.get=Mock(side_effect=[{'difficultyrating':'4'}])
        api.get.side_effect=None
        api.get.return_value=[{'difficultyrating':'4'}]
        self.assertEqual(api.beatmap('42',0)['difficultyrating'],'4')
        api.get.return_value=[{'difficultyrating':'5.5'}]
        self.assertEqual(api.beatmap('42',64)['difficultyrating'],'5.5')
        api.get.assert_called_with('get_beatmaps',b='42',mods=64)
        self.assertEqual(api.beatmap('42',512)['difficultyrating'],'5.5')
        self.assertEqual(api.get.call_count,2)
