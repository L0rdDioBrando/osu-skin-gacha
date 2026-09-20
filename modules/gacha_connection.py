"""Connection state comes from successful requests, never from an assumed timer."""
import time
import customtkinter as ctk
from modules.gacha_reports import redact
from modules.gacha_oauth import has_bancho_auth


def identity(app):
    return (app.settings['server'],str(app.settings['user_id']),app.settings.get('api_key',''),app.settings['offline'])


def state(app):
    ident=identity(app)
    if getattr(app,'connection_state',{}).get('identity')!=ident:
        app.connection_state=dict(identity=ident,checked=None,error='',pending=False)
    return app.connection_state


def mark(app,error='',ident=None):
    if ident is not None and ident!=identity(app):return
    current=state(app);current['checked']=time.monotonic();current['error']=redact(str(error),app.settings.get('api_key',''))


def check(app):
    current=state(app)
    if current['pending'] or app.closing or app.settings['offline']:return
    if not str(app.settings['user_id']).isdigit() or (app.settings['server']=='bancho' and not has_bancho_auth(app.settings)):return
    current['pending']=True;ident=current['identity'];settings=app.settings.copy()
    def work():
        api=None
        try:
            api=app.make_api(settings);api.snapshot()
            return ident,''
        except Exception as error:return ident,redact(str(error),settings.get('api_key',''))
        finally:
            if api is not None:api.session.close()
    app.submit(app.network,'connection_check',work)


def describe(app,now=None):
    current=state(app);english=app.settings['language']=='English';server='Gatari' if app.settings['server']=='gatari' else 'osu!'
    if app.settings['offline']:return ('Offline · local scores' if english else 'Офлайн · локальные скоры'),'neutral'
    if app.settings['server']=='bancho' and not has_bancho_auth(app.settings):return ('Sign in through osu! in Settings' if english else 'Войдите через osu! в настройках'),'neutral'
    if not str(app.settings['user_id']).isdigit():return ('Enter your profile ID in Settings' if english else 'Укажите ID профиля в настройках'),'neutral'
    if app.settings['server']=='bancho' and not has_bancho_auth(app.settings):return ('Sign in through osu! in Settings' if english else 'Войдите через osu! в настройках'),'neutral'
    if current['pending']:return ('Checking '+server+'…' if english else 'Проверка '+server+'…'),'neutral'
    error=current['error']
    if error:
        if ' / ' in error:error=error.split(' / ',1)[1 if english else 0]
        return server+' · '+error[:180],'error'
    if current['checked'] is None:return server+(' · not checked yet' if english else ' · ещё не проверено'),'neutral'
    return server+(' · connected' if english else ' · подключён'),'ok'



class ConnectionIndicator(ctk.CTkFrame):
    def __init__(self,parent,app):
        super().__init__(parent,fg_color='transparent')
        self.app=app;self.timer=None
        self.label=app.label(self,'',muted=True,size=11,anchor='w',justify='left');self.label.pack(side='left',fill='x',expand=True)
        self.retry=app.button(self,'↻',lambda:check(app),True);self.retry.configure(width=110,height=24,font=('Segoe UI',11))
        self.retry.pack(side='right',padx=(8,0))
        self.bind('<Configure>',lambda e:self.label.configure(wraplength=max(150,e.width-130)))
        self.tick()
    def tick(self):
        if not self.winfo_exists():return
        label,kind=describe(self.app);current=state(self.app)
        self.label.configure(text=('● ' if kind=='ok' else '○ ')+label,text_color=self.app.theme['accent'] if kind=='ok' else '#e88a8a' if kind=='error' else self.app.theme['muted'])
        allowed=not current['pending'] and not self.app.settings['offline'] and str(self.app.settings['user_id']).isdigit() and (self.app.settings['server']=='gatari' or has_bancho_auth(self.app.settings))
        self.retry.configure(text='↻ Check again' if self.app.settings['language']=='English' else '↻ Проверить',state='normal' if allowed else 'disabled')
        self.timer=self.after(1000,self.tick)
    def destroy(self):
        if self.timer:self.after_cancel(self.timer);self.timer=None
        super().destroy()
