"""Build a Linux x86_64 AppImage from this checkout (never from Windows binaries)."""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent

def build(tool):
    if sys.platform!='linux' or platform.machine() not in ('x86_64','AMD64'):
        raise SystemExit('Build on Linux x86_64 or use the Linux AppImage GitHub Actions workflow.')
    tool=Path(tool).resolve()
    if not tool.is_file():raise SystemExit('Pass the official appimagetool executable with --appimagetool.')
    work=ROOT/'.build-appimage';work.mkdir(exist_ok=True)
    from PyInstaller.__main__ import run
    run(['--noconfirm','--onedir','--name','osu-gacha',
         '--distpath',str(work/'dist'),'--workpath',str(work/'work'),'--specpath',str(work),
         '--collect-all','customtkinter','--collect-all','pygame','--collect-all','rosu_pp_py',
         '--collect-all','mutagen','--collect-all','keyring','--collect-all','secretstorage',
         '--hidden-import','keyring.backends.SecretService',
         '--add-data',str(ROOT/'assets')+':assets',str(ROOT/'main.py')])
    appdir=work/'osu-gacha.AppDir'
    if appdir.exists():
        if appdir.is_symlink() or appdir.resolve().parent!=work.resolve():raise RuntimeError('Unsafe AppDir')
        shutil.rmtree(appdir)
    bindir=appdir/'usr/bin'
    shutil.copytree(work/'dist/osu-gacha',bindir)
    for name in ('AppRun','osu-gacha.desktop'):
        shutil.copy2(ROOT/'packaging/linux'/name,appdir/name)
    (appdir/'AppRun').chmod(0o755)
    from PIL import Image
    with Image.open(ROOT/'assets/gacha-logo.png') as img:
        img.convert('RGBA').resize((256,256)).save(appdir/'osu-gacha.png')
    shutil.copy2(appdir/'osu-gacha.png',appdir/'.DirIcon')
    subprocess.run(['desktop-file-validate',str(appdir/'osu-gacha.desktop')],check=True)
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    target=out/'osu-gacha-v0.5.0-linux-preview-x86_64.AppImage'
    env=dict(os.environ,ARCH='x86_64',APPIMAGE_EXTRACT_AND_RUN='1')
    subprocess.run([str(tool),str(appdir),str(target)],env=env,check=True,cwd=work)
    target.chmod(0o755)
    target.with_suffix('.AppImage.sha256').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n')
    print(target)
    return target

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--appimagetool',required=True)
    build(parser.parse_args().appimagetool)
