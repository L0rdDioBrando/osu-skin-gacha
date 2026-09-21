from pathlib import Path
import json,zipfile
ROOT=Path(__file__).resolve().parent
NAME='osu!gacha_v0.5.0_source'

def build():
    files=[p for p in ROOT.iterdir() if p.is_file() and p.suffix in ('.py','.md','.txt','.cmd','.ps1')]
    files+=list((ROOT/'modules').glob('*.py'))
    files+=list((ROOT/'tests').glob('*.py'))
    files+=[ROOT/name for name in ('Makefile','pyproject.toml','uv.lock','flake.nix','flake.lock','shell.nix','.gitignore','.gitattributes')]
    files+=list((ROOT/'docs').glob('*'))
    files+=list((ROOT/'packaging/linux').glob('*'))
    files+=list((ROOT/'.github/workflows').glob('*.yml'))
    files+=[ROOT/'oauth_worker'/name for name in ('package.json','pnpm-lock.yaml','pnpm-workspace.yaml','wrangler.jsonc','README.md','src/worker.js','test/worker.test.mjs')]
    files+=list((ROOT/'assets').glob('*'))
    files=[p for p in files if p.is_file()]
    secrets=[]
    for path in [ROOT/'settings.json',ROOT/'music_player_data'/'settings.json']:
        if path.exists():
            data=json.loads(path.read_text(encoding='utf-8-sig'))
            if data.get('api_key'):secrets.append(data['api_key'].encode())
    entries=[(str(p.relative_to(ROOT)).replace('\\','/'),p.read_bytes()) for p in files]
    if any(secret in data for secret in secrets for _,data in entries):raise ValueError('Private key in public files')
    temporary=ROOT/(NAME+'.zip.tmp')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,data in entries:archive.writestr(name,data)
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip():raise ValueError('Archive integrity failure')
    target=ROOT/(NAME+'.zip');temporary.replace(target)
    print(target.name, len(entries),'files',target.stat().st_size,'bytes')
    return target
if __name__=='__main__':build()
