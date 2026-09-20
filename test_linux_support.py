import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from modules.gacha_oauth import SessionStore,AuthError
from modules import gacha_driver as driver

class LinuxSupportTests(unittest.TestCase):
    def test_session_survives_new_store_and_logout_without_plaintext_file(self):
        data={'session':'test-gacha-session','user':{'id':7},'expires_at':9999999999}
        values={};backend=Mock()
        backend.set_password.side_effect=lambda service,account,value:values.__setitem__((service,account),value)
        backend.get_password.side_effect=lambda service,account:values.get((service,account))
        backend.delete_password.side_effect=lambda service,account:values.pop((service,account))
        with tempfile.TemporaryDirectory() as tmp,patch('modules.gacha_oauth.sys.platform','linux'),patch.object(SessionStore,'linux_keyring',return_value=backend):
            path=Path(tmp)/'.oauth-session';first=SessionStore(path);first.save(data)
            self.assertFalse(path.exists());second=SessionStore(path);self.assertEqual(second.load(),data)
            self.assertEqual(SessionStore(Path(tmp)/'other').load(),{})
            second.clear();self.assertEqual(first.load(),{})

    def test_unavailable_keyring_does_not_write_credentials(self):
        with tempfile.TemporaryDirectory() as tmp,patch('modules.gacha_oauth.sys.platform','linux'),patch.object(SessionStore,'linux_keyring',side_effect=RuntimeError('secret details')):
            store=SessionStore(Path(tmp)/'.oauth-session')
            self.assertEqual(store.load(),{})
            with self.assertRaises(AuthError) as error:store.save({'session':'test'})
            self.assertNotIn('secret details',str(error.exception));self.assertFalse(store.path.exists())

    def test_wine_and_native_launch_arguments(self):
        with patch.object(driver,'os',SimpleNamespace(name='posix')),patch.object(driver.shutil,'which',return_value='/usr/bin/wine'):
            self.assertEqual(driver.executable_args(Path('/games/osu!.exe')),['/usr/bin/wine',str(Path('/games/osu!.exe'))])
            self.assertEqual(driver.executable_args(Path('/bin/otd')),[str(Path('/bin/otd'))])
        with patch.object(driver,'os',SimpleNamespace(name='posix')),patch.object(driver.shutil,'which',return_value=None):
            with self.assertRaises(ValueError):driver.executable_args(Path('/games/osu!.exe'))

    def test_external_launch_drops_bundled_libraries(self):
        fake=SimpleNamespace(name='posix',environ={'LD_LIBRARY_PATH':'/app/bundled','WINEPREFIX':'/home/me/osu'})
        with patch.object(driver,'os',fake):
            env=driver.external_environment();self.assertNotIn('LD_LIBRARY_PATH',env);self.assertEqual(env['WINEPREFIX'],'/home/me/osu')

if __name__=='__main__':unittest.main()
