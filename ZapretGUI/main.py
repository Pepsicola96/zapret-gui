# -*- coding: utf-8 -*-
"""
Zapret GUI — главный файл приложения.

Независимый графический интерфейс для комплекта
zapret-discord-youtube (проект Flowseal на GitHub).

Возможности:
  * запуск / остановка / перезапуск Zapret одной кнопкой;
  * выбор профиля доменов (Discord, YouTube, оба и т.д.);
  * выбор стратегии обхода DPI (main, alt1…alt5) с описаниями;
  * редактор списков доменов прямо из интерфейса;
  * проверка доступности Discord/YouTube;
  * журнал работы в реальном времени;
  * автозапуск в Windows, установка службы;
  * светлая/тёмная тема, русский/английский язык.

Требования: Python 3.8+, pip install customtkinter
Запуск:      python main.py
"""

import os
import sys

# чтобы пакет корректно импортировался при запуске из любой папки
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    import customtkinter as ctk
except ImportError:
    print("Не найден модуль customtkinter.")
    print("Установите его командой:  pip install customtkinter")
    if sys.platform.startswith("win"):
        try:
            import tkinter.messagebox as mb
            mb.showerror("Zapret GUI",
                         "Для работы интерфейса нужна библиотека customtkinter.\n\n"
                         "Откройте командную строку и выполните:\n"
                         "    pip install customtkinter")
        except Exception:
            pass
    sys.exit(1)

from config.settings import Settings
from config.locales import Loc
from core.zapret_manager import ZapretManager, find_zapret_root
from ui.scroll import install_global_wheel_router

from ui.dashboard_tab import DashboardTab
from ui.profiles_tab import ProfilesTab
from ui.test_tab import TestTab
from ui.lists_tab import ListsTab
from ui.settings_tab import SettingsTab
from ui.help_tab import HelpTab

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

NAV_ITEMS = [
    ("nav_dashboard", "dashboard"),
    ("nav_profiles",  "profiles"),
    ("nav_test",      "test"),
    ("nav_lists",     "lists"),
    ("nav_settings",  "settings"),
    ("nav_help",      "help"),
]


class ZapretApp(ctk.CTk):
    def __init__(self, start_minimized: bool = False):
        super().__init__()
        self.settings = Settings.load()
        self.loc = Loc(self.settings.get("language", "ru"))
        self.manager = ZapretManager(self.settings)

        # если путь не задан — пробуем найти комплект автоматически
        if not self.settings.get("zapret_path"):
            found = find_zapret_root(BASE_DIR)
            if found:
                self.settings.set("zapret_path", found)
                self.settings.save()

        self.title(self.loc.t("app_title"))
        self.geometry("1060x720")
        self.minsize(920, 620)

        ctk.set_appearance_mode(self.settings.get("theme", "dark"))

        # ---------- каркас: боковая панель + контент ----------------------
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_rowconfigure(99, weight=1)

        logo = ctk.CTkLabel(self.sidebar, text="🛡  Zapret GUI",
                            font=ctk.CTkFont(size=20, weight="bold"))
        logo.grid(row=0, column=0, padx=20, pady=(22, 4))

        ver = ctk.CTkLabel(self.sidebar, text="для zapret-discord-youtube",
                           font=ctk.CTkFont(size=11),
                           text_color="gray60")
        ver.grid(row=1, column=0, padx=20, pady=(0, 18))

        self.nav_buttons = {}
        for row, (key, name) in enumerate(NAV_ITEMS, start=2):
            btn = ctk.CTkButton(
                self.sidebar, text=self.loc.t(key), anchor="w",
                height=40, corner_radius=8, fg_color="transparent",
                hover_color=("gray80", "gray25"),
                command=lambda n=name: self._select(n))
            btn.grid(row=row, column=0, padx=12, pady=3, sticky="ew")
            self.nav_buttons[name] = btn

        # статус-индикатор внизу панели
        self.status_dot = ctk.CTkLabel(self.sidebar, text="● остановлен",
                                       font=ctk.CTkFont(size=12),
                                       text_color="gray55")
        self.status_dot.grid(row=98, column=0, padx=20, pady=8, sticky="w")

        # ---------- контейнер страниц -------------------------------------
        self.container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.tabs = {
            "dashboard": DashboardTab(self.container, self),
            "profiles":  ProfilesTab(self.container, self),
            "test":      TestTab(self.container, self),
            "lists":     ListsTab(self.container, self),
            "settings":  SettingsTab(self.container, self),
            "help":      HelpTab(self.container, self),
        }
        for tab in self.tabs.values():
            tab.grid(row=0, column=0, sticky="nsew")

        # ---------- события менеджера -> UI --------------------------------
        self.manager.on_log = lambda line: self.after(0, self._append_log, line)
        self.manager.on_status = lambda st: self.after(0, self._refresh_status, st)

        # глобальная маршрутизация колеса мыши (чинит «не скроллит нигде»)
        install_global_wheel_router(self)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._tray = None
        self._build_tray()

        self._select("dashboard")
        self._tick()

        if start_minimized:
            self.withdraw()

    # ------------------------------------------------------------------ UI
    def _select(self, name: str):
        for key, btn in self.nav_buttons.items():
            btn.configure(fg_color=("gray75", "gray28") if key == name
                          else "transparent")
        self.tabs["dashboard"].tkraise()
        self.tabs[name].tkraise()
        refresh = getattr(self.tabs[name], "on_show", None)
        if refresh:
            refresh()

    def _append_log(self, line: str):
        self.tabs["dashboard"].append_log(line)

    def _refresh_status(self, status):
        self.tabs["dashboard"].update_status(status)
        running = status.running
        self.status_dot.configure(
            text=("● запущен" if self.loc.lang == "ru" else "● running")
            if running else
            ("● остановлен" if self.loc.lang == "ru" else "● stopped"),
            text_color="#2fa572" if running else "gray55")

    def _tick(self):
        """Периодическое обновление аптайма и детект завершения процесса."""
        self.manager.is_running()          # синхронизирует статус
        self.tabs["dashboard"].tick()
        self.after(2000, self._tick)

    # --------------------------------------------------------------- tray
    def _build_tray(self):
        if not self.settings.get("minimize_to_tray", True):
            return
        try:
            import pystray                       # необязательная зависимость
            from PIL import Image, ImageDraw
        except ImportError:
            return
        img = Image.new("RGB", (64, 64), (30, 30, 46))
        d = ImageDraw.Draw(img)
        d.ellipse((10, 10, 54, 54), outline=(80, 170, 255), width=6)
        d.line((32, 16, 32, 48), fill=(80, 170, 255), width=6)
        d.line((16, 32, 48, 32), fill=(80, 170, 255), width=6)

        import threading

        def show(_icon=None, _item=None):
            self.after(0, self.deiconify)

        def quit_app(_icon=None, _item=None):
            self.manager.stop()
            self.after(0, self.destroy)

        menu = pystray.Menu(
            pystray.MenuItem("Open", show, default=True),
            pystray.MenuItem("Quit", quit_app))
        self._tray = pystray.Icon("ZapretGUI", img, "Zapret GUI", menu)
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _on_close(self):
        if self._tray is not None:
            self.withdraw()               # сворачиваем в трей
            return
        self.shutdown()

    def shutdown(self):
        try:
            if self._tray:
                self._tray.stop()
        except Exception:
            pass
        self.manager.stop()
        self.settings.save()
        self.destroy()

    # ------------------------------------------------ переключение языка
    def rebuild_locale(self):
        """Пересоздаёт виджеты после смены языка/темы."""
        for widget in self.winfo_children():
            widget.destroy()
        self.__init__()


def main():
    minimized = "--minimized" in sys.argv
    app = ZapretApp(start_minimized=minimized)
    app.mainloop()


if __name__ == "__main__":
    main()
