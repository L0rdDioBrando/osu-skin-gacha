"""Entry point for osu! Skin Gacha."""
import os,sys
from pathlib import Path
local_runtime=Path(__file__).resolve().parent.parent/'.runtime'
if local_runtime.is_dir():
    sys.path.insert(0,str(local_runtime))
    os.environ['PYTHONPATH']=str(local_runtime)+os.pathsep+os.environ.get('PYTHONPATH','')
    for name,folder in (('TCL_LIBRARY','tcl8.6'),('TK_LIBRARY','tk8.6')):
        path=Path(sys.executable).parent/'tcl'/folder
        if path.is_dir():os.environ.setdefault(name,str(path))
from modules.gacha_config import BASE, DEV_API_KEY_HASH, RANKS, COMBO, TOP, RANK_COLORS, _PALETTES, THEMES, COLORS, DEFAULTS, TEXT, tr, blend
from modules.gacha_storage import atomic_json, SettingsStore, HistoryStore
from modules.gacha_rules import pp_thresholds, stars_threshold, score_key, accuracy, mods_string, reward_for, dt_reward, score_url, resolve_score_url
from modules.gacha_skins import skin_manifest, read_skin_ini, gameplay_file, mix_skin, SkinLibrary, Sandbox
from modules.gacha_api import API, Covers
from modules.gacha_widgets import FastScrollableFrame, FastTextbox, Particles, bind_api_paste, apply_window_icon, IconWindow
from modules.gacha_settings import SETTING_HELP, SettingsWindow
from modules.gacha_app import SkinGachaApp

def main():
    if len(sys.argv)==3 and sys.argv[1]=='--self-check':
        import json,tkinter,pygame,rosu_pp_py
        from modules.gacha_config import RESOURCES
        root=tkinter.Tk();root.withdraw();root.update();root.destroy()
        Path(sys.argv[2]).write_text(json.dumps({'ok':True,'tk':tkinter.TkVersion,'assets':(RESOURCES/'assets/gacha.ico').is_file(),'frozen':bool(getattr(sys,'frozen',False))}),encoding='utf-8')
    else:
        SkinGachaApp().mainloop()

if __name__ == '__main__':
    main()
