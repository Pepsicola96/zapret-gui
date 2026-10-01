# -*- coding: utf-8 -*-
"""Вкладка «Справка»: описание работы с интерфейсом и ссылки."""

import subprocess
import sys
import webbrowser

import customtkinter as ctk

from ui.scroll import bind_mousewheel

REPO_URL = "https://github.com/Flowseal/zapret-discord-youtube"
ZAPRET_URL = "https://github.com/bol-van/zapret"


class HelpTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.loc = app.loc
        ru = self.loc.lang == "ru"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        card = ctk.CTkFrame(self, corner_radius=12)
        card.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(card, text=self.loc.t("help_title"),
                     font=ctk.CTkFont(size=18, weight="bold")
                     ).grid(row=0, column=0, padx=20, pady=(14, 6), sticky="w")

        text = ctk.CTkTextbox(card, wrap="word",
                              font=ctk.CTkFont(size=13))
        text.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        text.insert("1.0", HELP_RU if ru else HELP_EN)
        text.configure(state="disabled")
        bind_mousewheel(text)

        # ссылки
        links = ctk.CTkFrame(self, corner_radius=12)
        links.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        links.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(links, text=self.loc.t("links"),
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).grid(row=0, column=0, columnspan=2, padx=18,
                            pady=(10, 4), sticky="w")
        ctk.CTkButton(links, text="GitHub: Flowseal/zapret-discord-youtube",
                      fg_color="#5b9bd5", hover_color="#4a83b3",
                      command=lambda: webbrowser.open(REPO_URL)
                      ).grid(row=1, column=0, padx=(18, 6), pady=(0, 12),
                             sticky="ew")
        ctk.CTkButton(links, text="GitHub: bol-van/zapret (ядро)",
                      fg_color="#5b9bd5", hover_color="#4a83b3",
                      command=lambda: webbrowser.open(ZAPRET_URL)
                      ).grid(row=1, column=1, padx=(6, 18), pady=(0, 12),
                             sticky="ew")

        about = ctk.CTkLabel(
            self,
            text=("Zapret GUI v1.0 — неофициальный интерфейс. "
                  "Ядро обхода — проект Zapret (bol-van). "
                  "GUI не модифицирует системные настройки сверх тех, "
                  "что делает сам комплект.")
            if ru else
            ("Zapret GUI v1.0 — unofficial front-end. "
             "Engine: Zapret (bol-van). The GUI changes nothing beyond "
             "what the kit itself does."),
            font=ctk.CTkFont(size=11), text_color="gray55", wraplength=900,
            justify="left")
        about.grid(row=2, column=0, sticky="sw", padx=20, pady=(0, 14))

    def on_show(self):
        pass


HELP_RU = """Как пользоваться Zapret GUI

1. НАСТРОЙКИ → укажите папку, куда распакован комплект
   zapret-discord-youtube (кнопка «Определить автоматически» ищет её сама:
   Рабочий стол, Загрузки, соседние папки).

2. ПАНЕЛЬ УПРАВЛЕНИЯ → большая зелёная кнопка «Запустить» поднимает сервис
   с выбранной стратегией. Красная — останавливает. Рядом — проверка
   доступности Discord/YouTube и живой журнал.

3. ПРОФИЛИ И СТРАТЕГИЯ
   • Профиль — какие домены обходятся (Discord, YouTube, оба и т.д.).
   • Стратегия — способ обхода DPI. Если ничего не работает — перебирайте
     alt1…alt5; ⭐ alt2 подходит большинству пользователей.
   • После смены нажмите «Применить (перезапустить сервис)».

4. ТЕСТ СТРАТЕГИЙ
   Кнопка «Начать тестирование» автоматически переберёт отмеченные
   стратегии: для каждой кратковременно запустит Zapret, проверит
   доступность Discord/YouTube и замерит задержку. По итогам строится
   рейтинг — лучшую стратегию можно применить одной кнопкой 🏆.
   Во время теста возможны короткие обрывы соединения (сервис
   перезапускается), не запускайте тест во время игры или звонка.

5. ГЕЙМЕРСКИЙ РЕЖИМ (🎮)
   В комплекте есть стратегии вида main_gamer / alt*_gamer (в интерфейсе
   помечены 🎮). Особенность: обходятся ТОЛЬКО игровые домены (Steam, Epic,
   Battle.net, Roblox, Minecraft, Riot и пр.), весь остальной трафик идёт
   напрямую без десинхронизации пакетов — меньше риска лагов и лишних
   проблем на сервисах, которые DPI не блокирует. Внимание: в геймерском
   режиме Discord/YouTube могут НЕ работать, если их нет в игровом списке
   комплекта — для них используйте обычные стратегии alt1…alt5.

6. РЕДАКТОР СПИСКОВ
   Открывайте файлы lists/*.txt, добавляйте свои домены (валидация и защита
   от дубликатов встроены), удаляйте лишнее. Ctrl+S — сохранить.
   Свой список подключается полем «Дополнительные аргументы»:
       --hostlist=lists/my.txt

7. ТРЕЙ
   Крестик окна сворачивает приложение в системный трей (если установлен
   pystray + Pillow). Двойной клик по значку возвращает окно.

8. СЛУЖБА / АВТОЗАПУСК
   «Установить службу Zapret» — запуск сервиса без окна (нужны права
   администратора). «Автозапуск при входе в Windows» — GUI стартует вместе
   с системой и сворачивается в трей.

Частые проблемы
• Ничего не обходится → откройте «Тест стратегий» и подберите лучшую,
  или вручную смените стратегию (alt3/alt4), затем перезагрузите ПК.
• Игры лагают, но Discord/YouTube работают → попробуйте 🎮 геймерский
  режим: он трогает только игровой трафик и не мешает остальным сервисам.
• Пропал интернет на время теста → это нормально, тест перезапускает
  сервис; после завершения прежний режим восстанавливается автоматически.
• Ошибка WinDivert → запустите GUI один раз от имени администратора.
• Discord звонит, но видео нет → включите профиль «Discord + YouTube».
• Список обновляется на GitHub комплекта — скачайте свежий release при
  изменениях политики DPI."""

HELP_EN = """Using Zapret GUI

1. SETTINGS → point to the unpacked zapret-discord-youtube folder
   («Auto-detect» searches Desktop, Downloads and neighbouring folders).

2. DASHBOARD → green Start launches the service with the chosen strategy,
   red Stop halts it. Availability check and live log are next to it.

3. PROFILES & STRATEGY
   • Profile selects which domains are bypassed (Discord, YouTube, both…).
   • Strategy is the DPI-evasion method. If something fails, try alt1…alt5;
     ⭐ alt2 works for most users. Use «Apply (restart service)».

4. STRATEGY TEST — «Start test» iterates over the checked strategies,
   briefly starts Zapret with each one, measures Discord/YouTube availability
   and latency, then ranks them; apply the winner 🏆 with one click. Expect
   short connection drops while the service restarts during the test.

5. GAMER MODE (🎮) — kit strategies like main_gamer / alt*_gamer bypass ONLY
   game domains (Steam, Epic, Battle.net, Roblox, Minecraft, Riot…); all other
   traffic goes direct without desync — less lag risk on unrelated services.
   Note: Discord/YouTube may NOT work in gamer mode unless they are in the
   kit's game list; use regular alt1…alt5 strategies for them.

6. DOMAIN LISTS editor opens lists/*.txt with validation and dedupe.
   Ctrl+S saves. Custom list via extra args: --hostlist=lists/my.txt

7. TRAY: closing the window minimizes to tray (needs pystray + Pillow).

8. SERVICE / AUTOSTART: install the Windows service (admin rights required)
   or start the GUI at login minimized."""
