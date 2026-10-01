# -*- coding: utf-8 -*-
"""Локализованные строки интерфейса (ru / en)."""

LOCALES = {
    "ru": {
        "app_title": "Zapret GUI — управление zapret-discord-youtube",
        # навигация
        "nav_dashboard": "Панель управления",
        "nav_profiles": "Профили и стратегия",
        "nav_test": "Тест стратегий",
        "nav_lists": "Редактор списков",
        "nav_settings": "Настройки",
        "nav_help": "Справка",
        # общее
        "btn_start": "▶  Запустить",
        "btn_stop": "■  Остановить",
        "btn_restart": "⟳  Перезапустить",
        "btn_check": "Проверить доступность",
        "status_running": "Сервис запущен",
        "status_stopped": "Сервис остановлен",
        "uptime": "Время работы",
        "pid": "PID",
        "strategy": "Стратегия",
        "profile": "Профиль",
        "quick_actions": "Быстрые действия",
        "connectivity": "Проверка доступности",
        "log_title": "Журнал работы",
        "btn_clear_log": "Очистить журнал",
        "btn_open_log": "Открыть файл лога",
        "autostart_service": "Автозапуск при входе в Windows",
        "install_service": "Установить службу Zapret",
        "uninstall_service": "Удалить службу Zapret",
        # профили
        "profiles_title": "Профиль списков доменов",
        "strategy_title": "Стратегия обхода DPI",
        "custom_args": "Дополнительные аргументы zapret",
        "custom_args_hint": "Например: --hostlist=lists/my.txt  (осторожно, для опытных)",
        "recommended": "рекомендуется",
        "apply_restarts": "Применить (перезапустить сервис)",
        "btn_apply": "Применить",
        # списки
        "lists_title": "Редактор списков доменов",
        "lists_files": "Файлы списков",
        "btn_new_file": "Новый файл",
        "btn_save": "Сохранить",
        "btn_reload": "Обновить",
        "btn_add_domain": "Добавить домен(ы)",
        "btn_del_domain": "Удалить выбранный",
        "domains_count": "Доменов в файле",
        "add_dialog_title": "Добавление доменов",
        "add_dialog_info": "Введите один или несколько доменов (по одному на строку).\n"
                           "Дубликаты будут пропущены, некорректные строки показаны.",
        "new_file_prompt": "Имя нового файла списка:",
        # настройки
        "settings_title": "Настройки",
        "zapret_path": "Папка с комплектом zapret-discord-youtube",
        "btn_browse": "Обзор…",
        "btn_autodetect": "Определить автоматически",
        "appearance": "Внешний вид",
        "theme": "Тема оформления",
        "theme_dark": "Тёмная",
        "theme_light": "Светлая",
        "language": "Язык интерфейса",
        "behavior": "Поведение",
        "minimize_to_tray": "Сворачивать в трей при закрытии окна",
        "logging_enabled": "Записывать журнал в файл zapret_gui.log",
        "save_settings": "Сохранить настройки",
        "settings_saved": "Настройки сохранены.",
        # тест стратегий
        "test_title": "Тестирование и выбор лучшей стратегии",
        "test_intro": "Автоматически переберёт выбранные стратегии: для каждой "
                      "кратковременно запустит Zapret, проверит доступность "
                      "Discord/YouTube и замерит задержку. В конце покажет рейтинг "
                      "и позволит применить победителя одной кнопкой.",
        "test_select_all": "Выбрать все",
        "test_select_none": "Снять выбор",
        "test_rounds": "Раундов на стратегию",
        "test_settle": "Пауза на поднятие сервиса, сек",
        "btn_test_start": "🧪  Начать тестирование",
        "btn_test_stop": "Остановить тест",
        "test_col_strategy": "Стратегия",
        "test_col_status": "Статус",
        "test_col_success": "Успешных",
        "test_col_latency": "Ср. задержка",
        "test_col_verdict": "Вердикт",
        "test_best": "Лучшая стратегия",
        "btn_apply_best": "Применить лучшую стратегию",
        "test_running": "Тестируется",
        "test_phase_stop": "останавливаю сервис…",
        "test_phase_start": "запускаю стратегию…",
        "test_phase_test": "замеры доступности…",
        "test_phase_cleanup": "завершение…",
        "test_done": "Тестирование завершено.",
        "test_cancelled": "Тестирование остановлено пользователем.",
        "test_need_strategies": "Выберите хотя бы одну стратегию для теста.",
        "test_warning": "Во время теста сервис будет перезапускаться — возможны "
                        "короткие обрывы соединения. Не запускайте во время игры/звонка.",
        # геймерский режим
        "gamer_badge": "🎮 геймерский",
        "gamer_section": "Геймерские режимы (только игровые домены)",
        "gamer_explain": "В геймерском режиме обходятся только игровые домены "
                         "(Steam, Epic, Battle.net, Roblox, Minecraft, Riot и пр.), "
                         "а остальные сайты идут напрямую без десинхронизации — "
                         "меньше риска лагов на сторонних сервисах. Внимание: "
                         "Discord/YouTube в этом режиме могут не работать, если их "
                         "нет в игровом списке комплекта.",
        # справка
        "help_title": "Справка",
        "about": "О программе",
        "links": "Полезные ссылки",
        # сообщения
        "msg_need_path": "Сначала укажите папку с комплектом Zapret в разделе «Настройки».",
        "msg_started": "Сервис запускается…",
        "msg_stopped": "Сервис остановлен.",
        "msg_not_running": "Сервис не запущен.",
        "msg_checking": "Проверяю доступность…",
        "tray_hint": "Приложение работает в фоне. Двойной клик по значку — открыть окно.",
        "btn_cleanup": "Очистить зависшие процессы",
        "cleanup_done": "Очистка завершена.",
    },
    "en": {
        "app_title": "Zapret GUI — control panel for zapret-discord-youtube",
        "nav_dashboard": "Dashboard",
        "nav_profiles": "Profiles & Strategy",
        "nav_test": "Strategy Test",
        "nav_lists": "Domain Lists",
        "nav_settings": "Settings",
        "nav_help": "Help",
        "btn_start": "▶  Start",
        "btn_stop": "■  Stop",
        "btn_restart": "⟳  Restart",
        "btn_check": "Check availability",
        "status_running": "Service running",
        "status_stopped": "Service stopped",
        "uptime": "Uptime",
        "pid": "PID",
        "strategy": "Strategy",
        "profile": "Profile",
        "quick_actions": "Quick actions",
        "connectivity": "Connectivity check",
        "log_title": "Log",
        "btn_clear_log": "Clear log",
        "btn_open_log": "Open log file",
        "autostart_service": "Autostart on Windows login",
        "install_service": "Install Zapret service",
        "uninstall_service": "Uninstall Zapret service",
        "profiles_title": "Domain list profile",
        "strategy_title": "DPI bypass strategy",
        "custom_args": "Extra zapret arguments",
        "custom_args_hint": "e.g. --hostlist=lists/my.txt  (power users only)",
        "recommended": "recommended",
        "apply_restarts": "Apply (restart service)",
        "btn_apply": "Apply",
        "lists_title": "Domain list editor",
        "lists_files": "List files",
        "btn_new_file": "New file",
        "btn_save": "Save",
        "btn_reload": "Reload",
        "btn_add_domain": "Add domain(s)",
        "btn_del_domain": "Remove selected",
        "domains_count": "Domains in file",
        "add_dialog_title": "Add domains",
        "add_dialog_info": "Enter one or more domains (one per line).\nDuplicates are skipped; invalid lines are reported.",
        "new_file_prompt": "Name of the new list file:",
        "settings_title": "Settings",
        "zapret_path": "Folder containing zapret-discord-youtube",
        "btn_browse": "Browse…",
        "btn_autodetect": "Auto-detect",
        "appearance": "Appearance",
        "theme": "Theme",
        "theme_dark": "Dark",
        "theme_light": "Light",
        "language": "Interface language",
        "behavior": "Behavior",
        "minimize_to_tray": "Minimize to tray on close",
        "logging_enabled": "Write log to zapret_gui.log",
        "save_settings": "Save settings",
        "settings_saved": "Settings saved.",
        "test_title": "Strategy testing & best-strategy finder",
        "test_intro": "Automatically iterates over selected strategies: briefly starts "
                      "Zapret with each one, checks Discord/YouTube availability and "
                      "measures latency, then ranks results and lets you apply the winner.",
        "test_select_all": "Select all",
        "test_select_none": "Clear selection",
        "test_rounds": "Rounds per strategy",
        "test_settle": "Service settle time, sec",
        "btn_test_start": "🧪  Start test",
        "btn_test_stop": "Stop test",
        "test_col_strategy": "Strategy",
        "test_col_status": "Status",
        "test_col_success": "Success",
        "test_col_latency": "Avg latency",
        "test_col_verdict": "Verdict",
        "test_best": "Best strategy",
        "btn_apply_best": "Apply best strategy",
        "test_running": "Testing",
        "test_phase_stop": "stopping service…",
        "test_phase_start": "starting strategy…",
        "test_phase_test": "measuring availability…",
        "test_phase_cleanup": "finishing…",
        "test_done": "Testing finished.",
        "test_cancelled": "Testing cancelled by user.",
        "test_need_strategies": "Select at least one strategy to test.",
        "test_warning": "The service will restart during the test — expect short "
                        "connection drops. Do not run while gaming or in a call.",
        "gamer_badge": "🎮 gamer",
        "gamer_section": "Gamer modes (game domains only)",
        "gamer_explain": "Gamer mode bypasses only game domains (Steam, Epic, Battle.net, "
                         "Roblox, Minecraft, Riot etc.); all other traffic goes direct "
                         "without desync — less risk of lag on unrelated services. Note: "
                         "Discord/YouTube may NOT work in this mode unless included in "
                         "the kit's game list.",
        "help_title": "Help",
        "about": "About",
        "links": "Useful links",
        "msg_need_path": "First set the Zapret folder in Settings.",
        "msg_started": "Starting service…",
        "msg_stopped": "Service stopped.",
        "msg_not_running": "Service is not running.",
        "msg_checking": "Checking availability…",
        "tray_hint": "App keeps running in background. Double-click the icon to open.",
        "btn_cleanup": "Clean stuck processes",
        "cleanup_done": "Cleanup finished.",
    },
}


class Loc:
    def __init__(self, lang="ru"):
        self.set_lang(lang)

    def set_lang(self, lang):
        self.lang = lang if lang in LOCALES else "ru"
        self._d = LOCALES[self.lang]

    def t(self, key):
        return self._d.get(key, LOCALES["ru"].get(key, key))

    def __call__(self, key):
        return self.t(key)
