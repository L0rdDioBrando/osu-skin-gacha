"""Run each suite in its own process (Tk/audio tests own global interpreters)."""
from pathlib import Path
import subprocess
import sys

def main():
    root=Path(__file__).resolve().parent
    failed=[]
    for path in sorted(root.glob('test*.py')):
        print('\n=== '+path.stem+' ===',flush=True)
        script_ui=path.name.endswith('_ui.py') and path.name!='test_gacha_oauth_ui.py'
        args=[str(path)] if script_ui else ['-m','unittest',path.stem]
        result=subprocess.run([sys.executable,*args],cwd=root)
        if result.returncode:failed.append(path.stem)
    print('\nFailed suites: '+(', '.join(failed) if failed else 'none'))
    return bool(failed)

if __name__=='__main__':raise SystemExit(main())
