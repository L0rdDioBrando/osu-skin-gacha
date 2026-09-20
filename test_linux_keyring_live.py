"""Opt-in integration test, run only inside CI's disposable D-Bus/keyring session."""
import os
import sys
import tempfile
from pathlib import Path
import unittest
from modules.gacha_oauth import SessionStore

@unittest.skipUnless(sys.platform=='linux' and os.environ.get('OSU_GACHA_TEST_KEYRING')=='1','Requires disposable Linux keyring')
class LiveKeyringTests(unittest.TestCase):
    def test_round_trip_and_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'.oauth-session';store=SessionStore(path)
            data={'session':'ci-fixture-not-a-real-session','user':{'id':1}}
            try:
                store.save(data)
                self.assertFalse(path.exists())
                self.assertEqual(SessionStore(path).load(),data)
            finally:store.clear()
            self.assertEqual(SessionStore(path).load(),{})

if __name__=='__main__':unittest.main()
