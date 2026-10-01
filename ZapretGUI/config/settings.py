# -*- coding: utf-8 -*-
"""
Хранилище настроек Zapret GUI.

Все настройки хранятся в JSON-файле settings.json рядом с исполняемым файлом,
чтобы интерфейс можно было запускать portable-режиме (внутри папки комплекта
zapret-discord-youtube).
"""

import json
import os
import sys
from dataclasses import dataclass, field, asdict


def app_base_dir() -> str:
    """Каталог, где лежит скрипт/exe (portable-режим)."""
    if getattr(sys, "frozen", False):          # PyInstaller
        return os.path.dirname(sys.executable)
    # config/ -> ZapretGUI/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


DEFAULTS = {
    # путь к распакованному комплекту zapret-discord-youtube
    "zapret_path": "",
    # выбранная стратегия запуска (alt1..alt5 и т.п.)
    "strategy": "alt2",
    # активный профиль списков доменов
    "profile": "discord_youtube",
    # дополнительные флаги, добавляемые к команде
    "custom_args": "",
    # автозапуск сервиса при старте Windows (через планировщик)
    "autostart": False,
    # запускать прокси HTTP/SOCKS (mimikdpi / https-proxy режим)
    "https_proxy": False,
    # использовать NAT вместо прозрачного режима
    "use_nat": True,
    # порт локального прокси
    "proxy_port": 3128,
    # включатьDiscord/YouTube отдельно (тонкая настройка списков)
    "enable_discord": True,
    "enable_youtube": True,
    "enable_reports": False,
    # тема интерфейса: dark / light / system
    "theme": "dark",
    # язык интерфейса: ru / en
    "language": "ru",
    # сворачивать в трей при закрытии окна
    "minimize_to_tray": True,
    # логировать вывод zapret в файл
    "logging_enabled": True,
}


@dataclass
class Settings:
    data: dict = field(default_factory=lambda: dict(DEFAULTS))

    # ---- доступ ----------------------------------------------------------
    def get(self, key, default=None):
        return self.data.get(key, DEFAULTS.get(key, default))

    def set(self, key, value):
        self.data[key] = value

    def __getitem__(self, k):
        return self.get(k)

    def __setitem__(self, k, v):
        self.set(k, v)

    # ---- персистентность --------------------------------------------------
    @staticmethod
    def config_path() -> str:
        return os.path.join(app_base_dir(), "settings.json")

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        path = cls.config_path()
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                if isinstance(stored, dict):
                    merged = dict(DEFAULTS)
                    merged.update(stored)
                    s.data = merged
            except (json.JSONDecodeError, OSError):
                pass  # повреждённый файл — используем значения по умолчанию
        return s

    def save(self):
        path = self.config_path()
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except OSError:
            pass

    # ---- производные значения --------------------------------------------
    def zapret_dir(self) -> str:
        p = self.get("zapret_path") or ""
        return os.path.abspath(p) if p else ""

    def is_zapret_installed(self) -> bool:
        d = self.zapret_dir()
        if not d:
            return False
        # признаки комплекта: папка bin или файлы bp.bat / *.bat в корне
        try:
            entries = os.listdir(d)
        except OSError:
            return False
        return (os.path.isdir(os.path.join(d, "bin"))
                or os.path.isfile(os.path.join(d, "bp.bat"))
                or any(f.lower().endswith((".bat", ".cmd")) for f in entries))

    def active_lists(self):
        """Список активных имён профилей доменов с учётом тонких переключателей."""
        result = []
        profile = self.get("profile")
        if profile == "custom":
            if self.get("enable_discord"):
                result.append("discord")
            if self.get("enable_youtube"):
                result.append("youtube")
            if self.get("enable_reports"):
                result.append("reports_ru_ip")
        else:
            result.append(profile)
        return result or ["other"]
