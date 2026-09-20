"""Build a standalone Windows release without copying user data or server code."""
import os,sys,shutil,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def build():
    if os.name!='nt':raise RuntimeError('Build on Windows with Python + Tcl/Tk')
    for name in ('.build-tools','.runtime'):
        if (ROOT/name).is_dir():sys.path.insert(0,str(ROOT/name))
    from PyInstaller.__main__ import run
    run(['--noconfirm','--onedir','--windowed','--name','osu!gacha',
         '--distpath',str(ROOT/'.dist'),'--workpath',str(ROOT/'.build-native'),
         '--specpath',str(ROOT/'.build-native'),'--paths',str(ROOT/'.runtime'),
         '--collect-all','customtkinter','--collect-all','pygame','--collect-all','rosu_pp_py','--collect-all','mutagen',
         '--add-data',str(ROOT/'assets')+';assets',
         '--icon',str(ROOT/'assets/gacha.ico'),
         '--exclude-module','numpy','--exclude-module','matplotlib','--exclude-module','pandas','--exclude-module','scipy',str(ROOT/'main.py')])
    distribution=ROOT/'.dist'/'osu!gacha'
    for name in ('README.md','HOW_TO_RUN.txt','run_skin_gacha.cmd'):shutil.copy2(ROOT/name,distribution/name)
    files=[distribution/'osu!gacha.exe',*(distribution/name for name in ('README.md','HOW_TO_RUN.txt','run_skin_gacha.cmd'))]
    files.extend(p for p in (distribution/'_internal').rglob('*') if p.is_file())
    target=ROOT/'osu!gacha_v0.5.0_windows.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in files:archive.write(path,path.relative_to(distribution).as_posix())
    with zipfile.ZipFile(target) as archive:
        if archive.testzip():raise RuntimeError('Invalid release archive')
    print('Windows release:',target,'bytes:',target.stat().st_size)
    return target

if __name__=='__main__':build()
