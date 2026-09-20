"""Rebuild only the managed live skin from its original source; keep collection files intact."""
import copy
import shutil
import tempfile
import zipfile
from pathlib import Path
from modules.gacha_skin_apply import copy_live
from modules.gacha_skins import mix_skin


def apply_variant(library,ident,optimize,settings):
    box=library.box;acquired=not box.lock_file
    if acquired:box.acquire()
    try:
        library.load();item=library.drops[ident]
        source=library.sources.materialize(item,settings) if library.sources else Path(item['source'])
        with tempfile.TemporaryDirectory(prefix='.skin-variant-',dir=box.pack) as temporary:
            stage=Path(temporary)/'original';stage.mkdir()
            if source.is_dir():
                for child in source.rglob('*'):
                    if child.is_symlink():raise ValueError('Linked skin file')
                shutil.copytree(source,stage,dirs_exist_ok=True)
            else:
                with zipfile.ZipFile(source) as archive:
                    for info in archive.infolist():
                        name=info.filename.replace('\\','/');dest=(stage/name).resolve()
                        if not dest.is_relative_to(stage.resolve()) or ':' in name or (info.external_attr>>16)&0o170000==0o120000:raise ValueError('Unsafe archive path')
                        if info.is_dir():dest.mkdir(parents=True,exist_ok=True)
                        else:
                            dest.parent.mkdir(parents=True,exist_ok=True)
                            with archive.open(info) as inp,dest.open('wb') as out:shutil.copyfileobj(inp,out)
            children=list(stage.iterdir())
            if len(children)==1 and children[0].is_dir():stage=children[0]
            if optimize:
                name=settings.get('interface_skin','')
                if not name or Path(name).name!=name:raise ValueError('Выберите личный скин для интерфейса / Choose an interface skin')
                base=next((folder/name for folder in (box.backup,box.skins) if (folder/name).is_dir()),None)
                if base is None:raise ValueError('Личный скин интерфейса не найден / Interface skin not found')
                mixed=Path(temporary)/'mixed';mixed.mkdir();mix_skin(stage,base,mixed);stage=mixed
            result=copy_live(box,stage,item['installed_name'])
            item['optimize_override']=bool(optimize);library.save()
            return result
    finally:
        if acquired:box.release()
