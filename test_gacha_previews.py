import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image
from modules.gacha_sources import SkinSources, DRIVE_FOLDER
from modules.gacha_previews import PreviewCache


class PreviewTests(unittest.TestCase):
    def test_pair_by_stem_within_rank_and_persist(self):
        listings = {
            DRIVE_FOLDER:[dict(id='rankA',name='A',folder=True),dict(id='rankB',name='B',folder=True)],
            'rankA':[dict(id='a',name='Same.osk',folder=False),dict(id='pa',name='Same.JPG',folder=False),
                     dict(id='extra',name='unrelated.png',folder=False)],
            'rankB':[dict(id='b',name='Same.osk',folder=False),dict(id='pb',name='Same.png',folder=False)]}
        with tempfile.TemporaryDirectory() as tmp:
            source = SkinSources({'skin_source':'drive'}, Path(tmp))
            with patch('modules.gacha_sources.drive_listing', side_effect=lambda folder, session:listings[folder]):
                catalog = source.catalog()
            self.assertEqual(catalog['drive-a.osk']['preview_id'], 'pa')
            self.assertEqual(catalog['drive-b.osk']['preview_id'], 'pb')
            with patch('modules.gacha_sources.drive_listing', side_effect=ValueError('offline')):
                self.assertEqual(source.catalog(), catalog)

    def test_download_once_reuse_offline_and_reject_html(self):
        out = io.BytesIO(); Image.new('RGB',(640,360),'red').save(out,format='PNG')
        with tempfile.TemporaryDirectory() as tmp:
            cache = PreviewCache(Path(tmp), {})
            item = dict(preview_id='image',name='skin',rank='A')
            session = MagicMock()
            response = session.__enter__.return_value.get.return_value.__enter__.return_value
            response.iter_content.return_value = [out.getvalue()]
            with patch('modules.gacha_previews.session_for', return_value=session) as get:
                self.assertEqual(cache.get(item).size, (208,117))
                self.assertIsNotNone(cache.get(item))
                self.assertEqual(get.call_count,1)
            offline = PreviewCache(Path(tmp), {'offline':True})
            with patch('modules.gacha_previews.session_for',side_effect=AssertionError('Network must not run')):
                self.assertIsNotNone(offline.get(item))
            item = dict(item,preview_id='bad')
            response.iter_content.return_value = [b'<html>quota exceeded</html>']
            with patch('modules.gacha_previews.session_for', return_value=session):
                self.assertIsNone(cache.get(item))
                self.assertFalse(cache.path(item).exists())

    def test_winner_and_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=PreviewCache(Path(tmp), {}, stopped=lambda:True)
            items=[dict(id=str(i),name=str(i),rank='A',preview_id=str(i)) for i in range(15)]
            with patch('modules.gacha_previews.session_for',side_effect=AssertionError('Cancelled')):
                sequence=cache.prepare(items,items[0])
            self.assertEqual(sequence[22]['item'],items[0])
            self.assertTrue(all(e['image'] is None for e in sequence))


if __name__ == '__main__': unittest.main()
