import tempfile,unittest,zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from modules.gacha_skin_stats import aggregate
from modules.gacha_skin_variants import apply_variant

class SkinChanges(unittest.TestCase):
    def test_averages_and_passed_best(self):
        def row(pp,rank,combo):return {'score':dict(pp=pp,rank=rank,maxcombo=combo,count300=100,count100=0,count50=0,countmiss=0)}
        result=aggregate([row(100,'A',100),row(None,'F',20),row(200,'S',300)])
        self.assertEqual(result['count'],3);self.assertEqual(result['pp'],150);self.assertEqual(result['best']['score']['rank'],'S')
        self.assertEqual(aggregate([])['best'],None)
    def test_original_variant_keeps_source_and_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.osk'
            with zipfile.ZipFile(source,'w') as z:z.writestr('skin.ini','[General]\nName: Original\n');z.writestr('menu.png',b'original')
            box=SimpleNamespace(lock_file=True,pack=root,backup=root/'backup',skins=root/'Skins')
            item=dict(id='id',source=str(source),installed_name='!1999 Original')
            library=SimpleNamespace(box=box,drops={'id':item},load=Mock(),save=Mock(),sources=SimpleNamespace(materialize=lambda *_:source))
            def copy(box,stage,name):self.assertEqual((stage/'menu.png').read_bytes(),b'original');return name
            with patch('modules.gacha_skin_variants.copy_live',copy):self.assertEqual(apply_variant(library,'id',False,{}),'!1999 Original')
            self.assertTrue(source.exists());self.assertFalse(item['optimize_override']);library.save.assert_called_once()
if __name__=='__main__':unittest.main()
