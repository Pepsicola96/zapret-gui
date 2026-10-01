# -*- coding: utf-8 -*-
"""
Профили (списки доменов и стратегии) для интерфейса Zapret GUI.
Совместимы с проектом zapret-discord-youtube (Flowseal).

Списки доменов соответствуют файлам из комплекта:
  lists/discord_domains.txt, lists/youtube.txt, lists/reports_ru_ip.txt и т.д.
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Профили списков доменов (файлы в папке "lists")
# ---------------------------------------------------------------------------

@dataclass
class DomainProfile:
    id: str                 # имя файла без расширения
    name: str               # отображаемое имя
    description: str        # краткое описание
    builtin: bool = True    # встроенный (есть в комплекте) или пользовательский

DOMAIN_PROFILES = [
    DomainProfile("discord",        "Discord",            "Discord: приложение, API, CDN, голосовые серверы"),
    DomainProfile("youtube",        "YouTube",            "YouTube: видео, стримы, API"),
    DomainProfile("discord_youtube","Discord + YouTube",  "Объединённый профиль: Discord и YouTube вместе"),
    DomainProfile("reports_ru_ip",  "Запрещённые IP РФ/СНГ (Reports)", "Домены, резолвящиеся на запрещённые IP РФ/СНГ"),
    DomainProfile("ipset_all",      "IPSet: все домены",  "Все домены из активных профилей (для ipset/WinDivert)"),
    DomainProfile("openai",         "OpenAI / ChatGPT",   "chatgpt.com, openai.com и связанные сервисы"),
    DomainProfile("other",          "Прочие домены",      "Пользовательский список additional.txt"),
]

DOMAIN_PROFILE_MAP = {p.id: p for p in DOMAIN_PROFILES}


# ---------------------------------------------------------------------------
# Стратегии запуска (соответствуют .bat-файлам комплекта)
# ---------------------------------------------------------------------------

@dataclass
class Strategy:
    id: str                    # идентификатор стратегии
    name: str                  # отображаемое имя
    description: str           # для подсказки в интерфейсе
    args: list = field(default_factory=list)   # аргументы bp.bat / service
    recommended: bool = False
    gamer: bool = False        # геймерский режим (bat-файлы *_gamer в комплекте)
    gamer_note: str = ""       # особенности геймерского режима для UI

STRATEGIES = [
    Strategy(
        "main", "main", "Базовая стратегия: --filter-tcp=2 --filter-udp=80,443. "
        "Работает стабильно почти везде, но может быть недостаточно.",
        ["--tndns-disabled", "--filter-tcp=2", "--filter-udp=80", "--filter-udp=443"],
    ),
    Strategy(
        "alt1", "alt1", "Стратегия alt1: фрагментация TLS. Хороший баланс стабильности и обхода.",
        ["--tndns-disabled", "--filter-tcp=2", "--dpi-desync=fake",
         "--dpi-desync-repeats=6", "--filter-udp=443", "--dpi-desync=fake",
         "--dpi-desync-cutoff=n2", "--dpi-desync-split-pos=1"],
    ),
    Strategy(
        "alt2", "alt2", "Стратегия alt2: fake + мультисегментация. Часто рекомендуется как основная.",
        ["--tndns-disabled", "--filter-tcp=2", "--dpi-desync=fake,multiseq,disorder",
         "--dpi-desync-split-pos=method", "--dpi-desync-repeats=6",
         "--filter-udp=443", "--dpi-desync=fake", "--dpi-desync-cutoff=d2"],
        recommended=True,
    ),
    Strategy(
        "alt3", "alt3", "Стратегия alt3: агрессивная фрагментация. Для сложных случаев.",
        ["--tndns-disabled", "--filter-tcp=2", "--dpi-desync=fake,multiseq,disorder",
         "--dpi-desync-split-pos=2", "--dpi-desync-repeats=8",
         "--dpi-desync-ttl=5", "--filter-udp=443", "--dpi-desync=fake"],
    ),
    Strategy(
        "alt4", "alt4", "Стратегия alt4: discord-ориентированная, UDP-акцент.",
        ["--tndns-disabled", "--filter-tcp=2", "--dpi-desync=fake",
         "--filter-udp=443,50000-65535", "--dpi-desync=fake",
         "--dpi-desync-cutoff=n3"],
    ),
    Strategy(
        "alt5", "alt5", "Стратегия alt5: макс. охват портов TCP/UDP.",
        ["--tndns-disabled", "--filter-tcp=2,8,20,22,25,28,38,46,50,53,59",
         "--dpi-desync=fake,multiseq", "--filter-udp=443,53,80,853"],
    ),
    Strategy(
        "alt10", "alt10", "Стратегия alt10: ECN/диссекция заголовков (экспериментальная).",
        ["--tndns-disabled", "--filter-tcp=2", "--dpi-desync=fake,ecntwo",
         "--filter-udp=443", "--dpi-desync=fake"],
    ),
    Strategy(
        "zaproto", "Zapret Proto", "Экспериментальный режим zaproto (ifb/qdisc не нужны на Windows).",
        ["--tndns-disabled", "--filter-tcp=2", "--filter-udp=443"],
    ),
    # ------------------------------------------------------------------
    # ГЕЙМЕРСКИЙ РЕЖИМ (в комплекте — файлы вида alt_3_proton_gamer.bat,
    # main_gamer.bat и т.п.). Отличие от обычной стратегии: обходятся
    # только игровые домены (Steam, Epic, Battle.net, Roblox, Minecraft,
    # Origin/EA, Riot и пр.), а все остальные сайты идут НАПРЯМУЮ без
    # десинхронизации пакетов. Это снижает лишний трафик и потенциальные
    # задержки/проблемы на сервисах, которые DPI и не блокирует.
    # ВАЖНО: в геймерском режиме Discord/YouTube обходятся ТОЛЬКО если они
    # входят в игровой список комплекта; для обычного D/Y используйте
    # обычные стратегии.
    # ------------------------------------------------------------------
    Strategy(
        "main_gamer", "main (геймерский)",
        "Геймерский режим базовой стратегии: фильтруются только игровые домены, "
        "остальной трафик идёт напрямую. Минимальное вмешательство в сеть.",
        ["--tndns-disabled", "--filter-tcp=2", "--filter-udp=80", "--filter-udp=443"],
        gamer=True,
        gamer_note="Обходятся только игровые домены (Steam/Epic/Battle.net/Roblox/Minecraft...). "
                   "Discord и YouTube в этом режиме могут НЕ работать, если их нет в игровом списке.",
    ),
    Strategy(
        "alt1_gamer", "alt1 (геймерский)",
        "Геймерский вариант alt1: фрагментация TLS только для игровых доменов.",
        ["--tndns-disabled", "--filter-tcp=2", "--dpi-desync=fake",
         "--dpi-desync-repeats=6", "--filter-udp=443", "--dpi-desync=fake",
         "--dpi-desync-cutoff=n2", "--dpi-desync-split-pos=1"],
        gamer=True,
        gamer_note="Тот же приём, что alt1, но список доменов — игровой. "
                   "Остальные сайты не трогаются — меньше риска лагов на сторонних сервисах.",
    ),
    Strategy(
        "alt2_gamer", "alt2 (геймерский)",
        "Геймерский вариант alt2 (fake+multiseq) — рекомендуется для игр.",
        ["--tndns-disabled", "--filter-tcp=2", "--dpi-desync=fake,multiseq,disorder",
         "--dpi-desync-split-pos=method", "--dpi-desync-repeats=6",
         "--filter-udp=443", "--dpi-desync=fake", "--dpi-desync-cutoff=d2"],
        recommended=False, gamer=True,
        gamer_note="Компромисс «стабильность/агрессивность» только для игрового трафика. "
                   "Если игры лагают на обычной alt2 — попробуйте эту.",
    ),
    Strategy(
        "alt3_gamer", "alt3 (геймерский)",
        "Геймерский вариант alt3: агрессивная фрагментация для игровых доменов.",
        ["--tndns-disabled", "--filter-tcp=2", "--dpi-desync=fake,multiseq,disorder",
         "--dpi-desync-split-pos=2", "--dpi-desync-repeats=8",
         "--dpi-desync-ttl=5", "--filter-udp=443", "--dpi-desync=fake"],
        gamer=True,
        gamer_note="Для «упорных» блокировок игровых сервисов. Возможна более высокая "
                   "задержка на самих играх — сравните с alt2_gamer в тестере стратегий.",
    ),
    Strategy(
        "alt4_proton_gamer", "alt4 Proton (геймерский)",
        "Геймерский режим для Proton/Steam Play (Linux-игры на Windows-локальных "
        "серверах, Steam-стриминг): UDP-акцент для игровых портов.",
        ["--tndns-disabled", "--filter-tcp=2", "--dpi-desync=fake",
         "--filter-udp=443,50000-65535", "--dpi-desync=fake",
         "--dpi-desync-cutoff=n3"],
        gamer=True,
        gamer_note="Полезен при проблемах со Steam/Proton-играми и голосовым чатом Steam. "
                   "Широкий диапазон UDP-портов может создавать дополнительную нагрузку — следите за пингом.",
    ),
]

STRATEGY_MAP = {s.id: s for s in STRATEGIES}

DEFAULT_STRATEGY = "alt2"
DEFAULT_PROFILE = "discord_youtube"

# Профиль по умолчанию для нового пользователя — самый популярный кейс.
