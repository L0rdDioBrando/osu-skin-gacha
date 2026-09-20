"""Editable credits; avatars use the app's background image loader."""
import webbrowser
import customtkinter as ctk

TEAM = [
    ('DimEl', '18086030', 'Главный разработчик', 'Lead developer'),
    ('Solevarchik','38170259','User NixOS btw','User NixOS btw'),
    ('anastasena', '24754751', 'Дизайнер', 'Designer'),
    ('naru', '31129671', 'Плейтестер', 'Playtester'),
    ('scoleopa', '40306760', 'Плейтестер', 'Playtester'),
]


def build_team(window, body):
    app = window.app
    english = app.settings['language']=='English'
    app.label(body,'Команда osu!gacha' if not english else 'osu!gacha team',size=22,bold=True).pack(anchor='w',pady=14)
    cards=ctk.CTkFrame(body,fg_color='transparent')
    cards.pack(fill='x',pady=(0,12))
    for column in range((len(TEAM)+1)//2):
        cards.grid_columnconfigure(column,weight=1,uniform='team')
    for index,(name, ident, ru, en) in enumerate(TEAM):
        row = ctk.CTkFrame(cards,fg_color=app.theme['panel'],corner_radius=16)
        # Fill columns so Solevarchik stays directly below DimEl.
        row.grid(row=index%2,column=index//2,sticky='nsew',padx=6,pady=7)
        avatar = app.label(row,name[:1],width=64,height=64,size=24)
        avatar.pack(padx=14,pady=(18,10))
        app.label(row,name,size=17,bold=True).pack(fill='x',padx=10)
        app.label(row,en if english else ru,muted=True,size=12,wraplength=170,height=46).pack(fill='x',padx=10,pady=(2,8))
        app.button(row,'Profile' if english else 'Профиль',lambda i=ident:webbrowser.open('https://osu.ppy.sh/users/'+i),True,
                   tooltip=(f'Открыть профиль {name} на сайте osu!.',f'Open {name}’s osu! profile.')).pack(fill='x',padx=14,pady=(0,16))
        key = ('bancho',ident,app.settings['ignore_proxy'])
        if key in app.avatar_cache:
            set_avatar(app,avatar,key,app.avatar_cache[key])
        elif not app.settings['offline']:
            def fetch(widget=avatar, ident=ident):
                key,picture=app.fetch_avatar(ident,app.settings['ignore_proxy'],'bancho')
                return widget,key,picture
            app.submit(app.network,'team_avatar',fetch)


def set_avatar(app, widget, key, picture):
    if picture is None: return
    app.avatar_cache[key] = picture
    if widget.winfo_exists():
        image = ctk.CTkImage(light_image=picture,dark_image=picture,size=(64,64))
        widget.configure(image=image,text='')
        widget.avatar = image
