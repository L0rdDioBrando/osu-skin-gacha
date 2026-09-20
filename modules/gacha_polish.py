"""Release identity, update help and batched scaling of this app's windows only."""
import os
VERSION='v0.5.0'
CODENAME='Connected'
BUILD='2026.09.20'
RELEASES=(('v0.1','First Roll'),('v0.3','Origins · beta3'),('v0.4','Harmony · beta4'),('v0.4.1','Harmony · Usability'),('v0.4.2','Harmony · Polish'),('v0.4.3','Collection'),('v0.5.0','Connected'))


def scale_ui(app,factor):
    import customtkinter as ctk
    # WM_SETREDRAW hid native parents from Tk and left children stale until a
    # window move. Let Tk batch geometry normally, then flush its idle redraws.
    ctk.set_widget_scaling(factor)
    app.update_idletasks()
    app.after_idle(app.update_idletasks)


def open_update_help(app):
    from modules.gacha_widgets import IconWindow
    win=IconWindow(app);win.title('Update' if app.settings['language']=='English' else 'Обновление');win.geometry('650x450')
    win.configure(fg_color=app.theme['bg'])
    ru=app.settings['language']!='English'
    app.label(win,'Как обновить osu!gacha' if ru else 'Updating osu!gacha',size=24,bold=True).pack(padx=20,pady=20)
    message=('1. Заверши сессию. В настройках открой «История» и экспортируй данные для резерва.\n\n'
             '2. Закрой приложение и распакуй новый архив в прежнюю папку с заменой файлов программы.\n\n'
             '3. Не удаляй settings.json, историю, коллекцию и папки скинов. Они не входят в архив обновления.\n\n'
             '4. Запусти run_skin_gacha.cmd. Недостающие зависимости установятся автоматически.\n\n'
             'На другом компьютере распакуй архив отдельно и импортируй экспортированные данные. Автообновления пока нет.' if ru else
             '1. End your session. Export a data backup from Settings → History.\n\n'
             '2. Close the app. Extract the new archive into the existing folder, replacing app files.\n\n'
             '3. Keep settings.json, history, collection and skin folders. The update archive does not include them.\n\n'
             '4. Run run_skin_gacha.cmd. Missing dependencies install automatically.\n\n'
             'On another computer, extract separately and import your data backup. Automatic updates are not available yet.')
    app.label(win,message,wraplength=590,justify='left',anchor='w').pack(fill='both',padx=24,pady=10)
    return win
