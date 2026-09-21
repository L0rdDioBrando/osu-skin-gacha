import tempfile,time,os,wave
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageGrab
import customtkinter as ctk
from modules.gacha_app import SkinGachaApp
from modules.gacha_config import DEFAULTS
from modules.gacha_storage import SettingsStore,HistoryStore
from modules.gacha_api import Covers
from modules.gacha_insights import open_map_progress
from tests.test_gacha_features import record

with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);(root/'osu'/'Skins').mkdir(parents=True);(root/'pack').mkdir()
 folder=root/'osu'/'Songs'/'123 Test';folder.mkdir(parents=True)
 audio=folder/'a.wav'
 with wave.open(str(audio),'wb') as w:
  w.setnchannels(1);w.setsampwidth(2);w.setframerate(22050);w.writeframes(b'\0\0'*22050*30)
 (folder/'a.osu').write_text('[General]\nAudioFilename:a.wav\n[Metadata]\nBeatmapID:1')
 config=dict(DEFAULTS,setup_complete=True,offline=True,skin_source='folder',osu_path=str(root/'osu'),skin_pack_path=str(root/'pack'),animations=False)
 with patch.dict(os.environ,SDL_AUDIODRIVER='dummy'),patch.object(SettingsStore,'load',return_value=config),patch.object(HistoryStore,'load',return_value={}),patch.object(Covers,'get',return_value=Image.new('RGB',(156,88),'#604979')):
  app=SkinGachaApp();app.store.paths=[root/'settings.json'];app.history_store.paths=[root/'sessions'];errors=[]
  app.report_callback_exception=lambda *args:errors.append(str(args[1]))
  def tick(n=.2):
   end=time.monotonic()+n
   while time.monotonic()<end:app.update();time.sleep(.01)
  tick(.5)
  app.username='VeryLongNicknameTester';app.total_pp=8038;app.update_stats()
  rows=[]
  for i in range(5):
   r=record(200+i*70,4-i,pp=110+i*13);r['key']=[i];r['score'].update(rank='F' if i%2 else 'A',beatmap_id='1',date=f'2026-09-{i+1:02d}T12:00:00')
   r['map']=dict(artist='Artist',title='Local track preview',version='Insane',beatmapset_id='123',path=str(folder/'a.osu'));rows.append(r)
  session=dict(id='test',user_id='',server='bancho',slot='1',offline=True,started_at='2026-09-01T12:00:00',records=rows,drops=[])
  app.history={'test':session};app.selected_session='test';app.show_page(0);tick()
  player=app.audio_player;button=next(b for b in player.buttons if b.winfo_exists());key=player.buttons[button]
  player.toggle(button,rows[-1],key);tick(.6);assert player.state=='playing'
  player.seekbar.set(10);player.seek_to();tick();assert player.backend.position()>=10
  player.pause_resume();tick();assert player.state=='paused';position=player.backend.position();tick();assert player.backend.position()==position
  player.pause_resume();tick();assert player.state=='playing'
  player.stop();tick();assert player.panel.winfo_manager() and player.state=='stopped'
  player.pause_resume();tick();assert player.state=='playing'
  player.hide();tick();assert not player.panel.winfo_manager()
  player.pause_resume();tick();assert player.panel.winfo_manager() and player.state=='playing'
  out=Path('test-output');out.mkdir(exist_ok=True)
  app.geometry('1180x980');app.lift();tick();ImageGrab.grab(window=int(app.frame(),0)).save(out/'harmony-main.png')
  app.geometry('880x720');tick();
  badges=[w for card in app.cards for w in card.winfo_children() if isinstance(w,ctk.CTkLabel) and w.cget('text') in ('F','A')]
  assert len({b.winfo_rootx() for b in badges})==1
  ImageGrab.grab(window=int(app.frame(),0)).save(out/'harmony-small.png')
  graph=open_map_progress(app,rows[-1]);tick();ImageGrab.grab(window=int(graph.frame(),0)).save(out/'harmony-map.png')
  app.open_reward_settings();tick();settings=app.settings_window
  settings.variables['custom_rewards'].set(True);settings.changed('custom_rewards');tick()
  assert abs(float(settings.draft['goal_stars'])-5.01)<.01
  for scale in ('125%','90%','100%'):
   app.apply_live_setting('ui_scale',scale);tick()
   assert abs(app.start_button._get_widget_scaling()-int(scale[:-1])/100)<.01
  settings.lift();tick();ImageGrab.grab(window=int(settings.frame(),0)).save(out/'harmony-rewards.png')
  graph.destroy();settings.destroy();app.show_page(0);tick();assert player.state=='playing'
  (root/'osu'/'osu!.exe').touch();app.settings['offline']=False
  app.open_setup();tick()
  def descendants(widget):
   for child in widget.winfo_children():
    yield child
    yield from descendants(child)
  for _ in range(2):
   next(w for w in descendants(app.setup_window) if isinstance(w,ctk.CTkButton) and w.cget('text')=='Далее').invoke();tick()
  # Bancho setup now offers OAuth instead of the removed Legacy key instructions.
  from modules.gacha_oauth import AuthPanel
  assert any(isinstance(w,AuthPanel) for w in descendants(app.setup_window))
  app.setup_window.destroy();app.settings['offline']=True
  assert not hasattr(app.profile_label,'_copy_menu')
  app.on_close()
  while not app.destroyed:tick(.05)
  assert not errors,errors
  print('HARMONY UI PASS: seek, persistent player, map history, reward initialization, long name, scale')
