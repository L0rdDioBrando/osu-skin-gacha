"""Desktop holds only an opaque gacha session. osu! tokens never cross this boundary."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import queue
import secrets
import threading
import time
import webbrowser
import sys
import subprocess
import requests
import customtkinter as ctk
from modules.gacha_config import BASE

SERVER='https://osu-gacha-auth.therealdimedrol.workers.dev'

class AuthError(RuntimeError):pass

def open_login_browser(url):
    if not sys.platform.startswith('linux'):return webbrowser.open(url)
    from modules.gacha_driver import external_environment
    try:
        subprocess.Popen(['xdg-open',url],env=external_environment(),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return True
    except OSError:return False

class SessionStore:
    def __init__(self,path=None):self.path=Path(path or BASE/'.oauth-session')
    def linux_keyring(self):
        # Explicit backend: never select keyrings.alt/plaintext or environment overrides.
        try:
            from keyring.backends.SecretService import Keyring
            backend=Keyring()
            if backend.priority <= 0:raise RuntimeError('Unavailable')
            return backend
        except Exception:
            raise AuthError('Разблокируйте системное хранилище паролей (Secret Service / GNOME Keyring / совместимый KWallet) и повторите вход. / Unlock your Secret Service keyring and retry.') from None
    def keyring_account(self):
        return hashlib.sha256(str(self.path.resolve()).encode()).hexdigest()
    @staticmethod
    def protect(data,decrypt=False):
        if os.name!='nt':raise AuthError('Защищённое хранение сессии доступно в Windows / Secure session storage requires Windows')
        class Blob(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_char))]
        buffer=ctypes.create_string_buffer(data);source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_char)));target=Blob()
        lib=ctypes.WinDLL('crypt32',use_last_error=True)
        fn=lib.CryptUnprotectData if decrypt else lib.CryptProtectData
        fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        fn.restype=wintypes.BOOL
        if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):raise AuthError('Не удалось открыть защищённую сессию. Войдите снова / Cannot open protected session. Sign in again')
        try:return ctypes.string_at(target.data,target.size)
        finally:
            free=ctypes.WinDLL('kernel32').LocalFree;free.argtypes=[ctypes.c_void_p];free.restype=ctypes.c_void_p;free(target.data)
    def load(self):
        if sys.platform.startswith('linux'):
            try:
                value=self.linux_keyring().get_password('osu!gacha',self.keyring_account())
                data=json.loads(value) if value else {}
                return data if isinstance(data,dict) else {}
            except Exception:return {}
        try:return json.loads(self.protect(self.path.read_bytes(),True))
        except (OSError,ValueError,AuthError):return {}
    def save(self,data):
        if sys.platform.startswith('linux'):
            try:self.linux_keyring().set_password('osu!gacha',self.keyring_account(),json.dumps(data))
            except Exception:
                raise AuthError('Не удалось сохранить вход. Разблокируйте системное хранилище паролей и повторите. / Cannot save login: unlock your system keyring and retry.') from None
            return
        encrypted=self.protect(json.dumps(data).encode())
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_name(self.path.name+'.tmp');temporary.write_bytes(encrypted);temporary.replace(self.path)
    def clear(self):
        if sys.platform.startswith('linux'):
            try:
                backend=self.linux_keyring()
                if backend.get_password('osu!gacha',self.keyring_account()) is not None:
                    backend.delete_password('osu!gacha',self.keyring_account())
            except Exception:
                raise AuthError('Не удалось удалить сохранённый вход. Разблокируйте хранилище паролей. / Unlock your keyring to remove the saved login.') from None
        self.path.unlink(missing_ok=True)

class SessionManager:
    def __init__(self,settings,store=None):
        self.store=store or SessionStore();self.data=self.store.load();self.lock=threading.RLock();self.ignore_proxy=settings.get('ignore_proxy',False)
    def account(self):return dict(self.data.get('user') or {})
    def available(self):return bool(self.data.get('session') and self.account().get('id'))
    def call(self,path,method='GET',payload=None,params=None,authenticated=True):
        if not path.startswith('/') or path.startswith('//') or '?' in path or '#' in path:
            raise AuthError('Invalid authentication route')
        headers={'Accept':'application/json','User-Agent':'osu-gacha/0.5.0'}
        if authenticated:
            with self.lock:token=self.data.get('session')
            if not token:raise AuthError('Войдите через osu! / Sign in through osu!')
            headers['Authorization']='Bearer '+token
        try:
            with requests.Session() as http:
                http.trust_env=not self.ignore_proxy
                response=http.request(method,SERVER+path,json=payload,params=params,headers=headers,timeout=(10,45),allow_redirects=False)
                if authenticated and response.status_code==401:
                    with self.lock:
                        if self.data.get('session')==token:self.data={};self.store.clear()
                    raise AuthError('Сессия истекла. Войдите через osu! снова / Session expired. Sign in through osu! again')
                if response.status_code==404 and not path.startswith('/api/v2/'):
                    raise AuthError('Worker ещё не поддерживает вход из приложения / Worker desktop login is not deployed yet')
                if response.status_code not in (200,202,404):
                    raise AuthError(f'Сервер авторизации: HTTP {response.status_code} / Authentication server: HTTP {response.status_code}')
                if response.status_code==404:return None
                return response.json()
        except (requests.RequestException,ValueError):
            raise AuthError('Нет связи с сервером входа. Проверьте соединение / Cannot reach the login server. Check your connection') from None
    def login(self,cancel):
        verifier=secrets.token_hex(32)
        start=self.call('/desktop/start','POST',{'challenge':hashlib.sha256(verifier.encode()).hexdigest()},authenticated=False)
        ident=start.get('id','');login_url=start.get('login_url','')
        if len(ident)!=64 or any(c not in '0123456789abcdef' for c in ident) or login_url!=SERVER+'/login?desktop='+ident:raise AuthError('Некорректный адрес входа / Invalid login address')
        if cancel.is_set():raise AuthError('Вход отменён / Login cancelled')
        if not open_login_browser(login_url):raise AuthError('Не удалось открыть браузер / Could not open the browser')
        deadline=time.monotonic()+min(600,int(start.get('expires_in',600)))
        while time.monotonic()<deadline:
            if cancel.wait(3):raise AuthError('Вход отменён / Login cancelled')
            data=self.call('/desktop/poll','POST',{'id':ident,'verifier':verifier},authenticated=False)
            if data.get('status')=='pending':continue
            if data.get('status')!='complete' or data.get('session')!=ident+'.'+verifier or not str(data.get('user',{}).get('id','')).isdigit():raise AuthError('Неверный результат входа / Invalid login result')
            # Explicit allowlist; even a malformed response cannot persist upstream tokens.
            user=data['user'];return {'session':data['session'],'expires_at':data['expires_at'],
                'user':{k:user.get(k) for k in ('id','username','avatar_url','pp')}}
        raise AuthError('Время входа истекло. Повторите вход / Login timed out. Try again')
    def accept(self,data):
        clean={'session':data['session'],'expires_at':data['expires_at'],
               'user':{key:data['user'].get(key) for key in ('id','username','avatar_url','pp')}}
        with self.lock:self.store.save(clean);self.data=clean
    def validate(self):
        data=self.call('/session')
        with self.lock:
            self.data.update(user={key:data['user'].get(key) for key in ('id','username','avatar_url','pp')},expires_at=data['expires_at']);self.store.save(self.data)
        return self.account()
    def logout(self):
        # Keep the local credential if server revocation fails, allowing a real logout retry.
        self.call('/logout','POST',{})
        with self.lock:self.store.clear();self.data={}

_manager=None
def session_manager(settings):
    global _manager
    if _manager is None:_manager=SessionManager(settings)
    _manager.ignore_proxy=settings.get('ignore_proxy',False)
    return _manager

def has_bancho_auth(settings):
    manager=session_manager(settings)
    return manager.available() and str(manager.account().get('id'))==str(settings.get('user_id'))

class AuthPanel(ctk.CTkFrame):
    def __init__(self,parent,app,on_change):
        super().__init__(parent,fg_color=app.theme['panel'],corner_radius=12)
        self.app=app;self.on_change=on_change;self.manager=session_manager(app.settings)
        self.pending=False;self.cancel=threading.Event();self.results=queue.Queue();self.timer=None
        self.caption=app.label(self,'',size=15,bold=True,anchor='w');self.caption.pack(fill='x',padx=14,pady=(14,4))
        self.note=app.label(self,'',muted=True,wraplength=540,justify='left');self.note.pack(fill='x',padx=14,pady=4)
        self.action=app.button(self,'',self.run);self.action.pack(anchor='w',padx=14,pady=(4,14))
        self.refresh()
    def refresh(self):
        en=self.app.settings['language']=='English';user=self.manager.account()
        self.caption.configure(text=('osu! · '+str(user['username'])) if user else ('osu! account' if en else 'Аккаунт osu!'))
        self.note.configure(text=('Sign in on the official osu! website. No API key needed.' if en else 'Вход на официальном сайте osu!. API-ключ и ID вводить не нужно.'))
        self.action.configure(text=('Sign out' if en else 'Выйти из аккаунта') if user else ('Sign in through osu!' if en else 'Войти через osu!'),state='normal' if self.app.state_name=='idle' else 'disabled')
    def run(self):
        if self.pending or self.app.state_name!='idle':return
        self.pending=True;self.cancel.clear();self.action.configure(state='disabled')
        logout=self.manager.available()
        self.note.configure(text='Выход… / Signing out…' if logout else 'Подтвердите вход в браузере… / Confirm login in your browser…')
        def work():
            try:
                if logout:self.manager.logout();result=None
                else:result=self.manager.login(self.cancel)
                self.results.put((True,result))
            except Exception as e:self.results.put((False,str(e) if isinstance(e,AuthError) else 'Не удалось завершить вход / Could not finish signing in'))
        threading.Thread(target=work,daemon=True).start();self.tick()
    def tick(self):
        try:ok,result=self.results.get_nowait()
        except queue.Empty:self.timer=self.after(100,self.tick);return
        self.pending=False
        if ok:
            try:
                if result:self.manager.accept(result)
                self.on_change(self.manager.account())
                if self.winfo_exists():self.refresh()
            except (OSError,AuthError) as e:
                if self.winfo_exists():self.refresh();self.note.configure(text=str(e))
        else:self.refresh();self.note.configure(text=result)
    def destroy(self):
        self.cancel.set()
        if self.timer:self.after_cancel(self.timer)
        super().destroy()
